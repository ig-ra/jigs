#!/usr/bin/env python3
"""Parked Herdr file handoff CLI; not integrated into the workflow toolbox.

Global --cwd/--json precede send or ping. Standard library only; requires Herdr.
Exit: 0 READY/SENT/ALREADY_SENT, 1 STOPPED, 2 usage, 3 prerequisite error,
124 TIMEOUT. See wf-herdr-codex.md beside this file for the integration handoff.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

JSON = dict[str, Any]
IDLE_GRACE = 30  # No answer: idle must hold across tool/turn flickers before STOPPED.


@dataclass
class Context:
    cwd: Path


class HandoffError(Exception):
    def __init__(self, message: str, code: int = 3, source_code: str | None = None):
        super().__init__(message)
        self.code = code
        self.source_code = source_code


def brief(text: str, limit: int = 300) -> str:
    clean = " ".join(re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text).split())
    return clean[:limit] + ("…" if len(clean) > limit else "")


def run(argv: list[str], cwd: Path | None = None, data: str | None = None,
        timeout: float = 45) -> str:
    try:
        p = subprocess.run(argv, cwd=cwd, input=data, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise HandoffError(f"{argv[0]}: {brief(str(e))}") from e
    if p.returncode:
        detail = p.stderr or p.stdout or 'exit ' + str(p.returncode)
        source_code = None
        try:
            error = json.loads(detail).get("error")
            if isinstance(error, dict):
                source_code = error.get("code")
                detail = f"{error.get('code', 'error')}: {error.get('message', '')}"
        except (ValueError, AttributeError):
            pass
        label = argv[0]
        raise HandoffError(f"{label}: {brief(detail)}", source_code=source_code)
    return p.stdout.strip()


def decode(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise HandoffError("invalid JSON from prerequisite") from e


def herdr(args: list[str], timeout: float = 45) -> JSON:
    if os.environ.get("HERDR_ENV") != "1":
        raise HandoffError("not running inside Herdr")
    result = decode(run(["herdr"] + args, timeout=timeout))
    return result["result"]


def output(value: Any, line: str, as_json: bool) -> None:
    print(json.dumps(value, separators=(",", ":")) if as_json else line, flush=True)


def say(a: argparse.Namespace, word: str, code: int, detail: str = "", **fields: Any) -> int:
    output({"result": word, **fields}, word + (" " + detail if detail else ""), a.json)
    return code


def file_body(path: str) -> str:
    body = Path(path).read_text()
    if not body.strip():
        raise HandoffError(f"empty file: {path}", 2)
    return body


def temp_root() -> Path:
    return Path(os.environ.get("TMPDIR") or "/tmp") / "igr-ticket"


def slot(path: Path) -> tuple[str, str] | None:
    parts = path.resolve().parts
    for i, part in enumerate(parts):
        if part == ".worktrees" and i + 2 < len(parts):
            return parts[i + 1], parts[i + 2]
    return None


@contextmanager
def locked(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        yield


def atomic_json(path: Path, value: Any) -> None:
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=".tk-")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(value, f, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def agents() -> list[JSON]:
    return herdr(["agent", "list"])["agents"]


def agent_cwd(agent: JSON) -> Path:
    return Path(agent.get("foreground_cwd") or agent.get("cwd") or "/").resolve()


def ping(ctx: Context, a: argparse.Namespace) -> int:
    path = Path(a.file).resolve()
    body = file_body(str(path))
    location = slot(ctx.cwd)
    target = a.to or (location[1] if location else None)
    if not target:
        candidates = [p for p in agents() if p["agent"] == "claude" and agent_cwd(p) == ctx.cwd]
        if len(candidates) != 1:
            raise HandoffError("no unique Claude in cwd; use --to", 1)
        target = candidates[0].get("name") or candidates[0]["pane_id"]
    agent = herdr(["agent", "get", target])["agent"]
    if agent["agent"] != "claude":
        raise HandoffError("ping recipient is not Claude", 1)
    identity = [agent["pane_id"], agent.get("agent_session")]
    digest = hashlib.sha256(json.dumps([str(path), body, identity]).encode()).hexdigest()
    receipts = temp_root() / "ping-receipts.json"
    with locked(receipts.with_suffix(".lock")):
        saved = decode(receipts.read_text()) if receipts.exists() else {}
        if digest in saved:
            return say(a, "ALREADY_SENT", 0, str(path), file=str(path))
        if agent["agent_status"] == "blocked":
            return say(a, "STOPPED", 1, "blocked", reason="blocked")
        herdr(["agent", "prompt", target, f"{path} ready"])
        saved[digest] = time.time()
        atomic_json(receipts, saved)
    return say(a, "SENT", 0, f"{target} {path}", file=str(path), to=target)


def fingerprint(path: Path) -> tuple[int, int, str] | None:
    if not path.exists():
        return None
    stat = path.stat()
    return stat.st_mtime_ns, stat.st_size, hashlib.sha256(path.read_bytes()).hexdigest()


def send(ctx: Context, a: argparse.Namespace) -> int:
    source, answer = Path(a.brief).resolve(), Path(a.answer).resolve()
    file_body(str(source))
    before = fingerprint(answer)
    deadline = time.monotonic() + a.timeout
    try:
        herdr(["agent", "prompt", a.agent,
               f"Read and follow {source}; write your answer to {answer}",
               "--wait", "--timeout", str(max(1, int(min(a.timeout, 10) * 1000)))],
              timeout=min(a.timeout, 10) + 2)
    except HandoffError as e:
        # A settled-state timeout can follow successful delivery. Never send twice.
        if e.source_code != "timeout":
            return say(a, "STOPPED", 1, brief(str(e)), reason=str(e))
    stopped = 0
    idle_since = None
    while True:
        try:
            agent = herdr(["agent", "get", a.agent])["agent"]
        except HandoffError as e:
            return say(a, "STOPPED", 1, brief(str(e)), reason=str(e))
        state = agent["agent_status"]
        fresh = fingerprint(answer)
        if state == "blocked":
            return say(a, "STOPPED", 1, "blocked", reason="blocked")
        now = time.monotonic()
        stopped = stopped + 1 if state in {"idle", "done"} else 0
        idle_since = (idle_since if idle_since is not None else now) if stopped else None
        if stopped >= 2:
            ready = fresh is not None and fresh != before and fresh[1] > 0
            if ready:
                return say(a, "READY", 0, str(answer), file=str(answer))
            if now - idle_since >= IDLE_GRACE:
                return say(a, "STOPPED", 1, str(answer), file=str(answer))
        left = deadline - now
        if left <= 0:
            return say(a, "TIMEOUT", 124)
        time.sleep(min(a.interval, left))


def positive(value: str) -> float:
    number = float(value)
    if not 0 < number < float("inf"):
        raise argparse.ArgumentTypeError("must be positive and finite")
    return number


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cwd", type=Path, default=Path.cwd(), help="Herdr recipient context")
    p.add_argument("--json", action="store_true", help="structured output")
    sub = p.add_subparsers(dest="command", required=True)
    cmd = sub.add_parser("send")
    cmd.set_defaults(func=send)
    cmd.add_argument("agent")
    cmd.add_argument("brief")
    cmd.add_argument("answer")
    cmd.add_argument("--timeout", type=positive, default=1800)
    cmd.add_argument("--interval", type=positive, default=2)
    cmd = sub.add_parser("ping")
    cmd.set_defaults(func=ping)
    cmd.add_argument("file")
    cmd.add_argument("--to")
    return p


def main(argv: list[str] | None = None) -> int:
    a = parser().parse_args(argv)
    ctx = Context(a.cwd.resolve())
    try:
        return a.func(ctx, a)
    except Exception as e:
        code = e.code if isinstance(e, HandoffError) else 3
        output({"result": "ERROR", "message": brief(str(e)), "code": code}, "ERROR " + brief(str(e)), a.json)
        return code
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
