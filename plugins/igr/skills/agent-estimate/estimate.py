#!/usr/bin/env python3
"""Agent-time estimates and run logging (standard library only).

  estimate.py est   <agent> <N|low-high>
  estimate.py start <agent> [<N|low-high> | --review] --task T [--ticket K] [--model M]
  estimate.py done  <id> [--wait MIN | --actual MIN] [--note TEXT]
  estimate.py                                               calibration per agent
"""
import argparse
import csv
import fcntl
import math
import os
import re
import secrets
import statistics
import tempfile
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

LOG = Path(os.environ.get("AGENT_ESTIMATES") or Path.home() / ".claude/agent-estimates.tsv")
FIELDS = ["id", "started", "agent", "model", "ticket", "task",
          "rounds_low", "rounds_high", "est_min", "actual_min", "note"]
REVIEW_AGENT = "claude-review"
DEFAULT_PACE = 3.0
MIN_ROWS = 5
UNCALIBRATED_WIDEN = 1.5


def read_rows():
    if not LOG.exists():
        return []
    with LOG.open() as f:
        return list(csv.DictReader(f, delimiter="\t"))


@contextmanager
def locked():
    LOG.parent.mkdir(parents=True, exist_ok=True)
    # Stable sidecar: the TSV itself is replaced atomically below.
    with LOG.with_suffix(".lock").open("a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        yield


def write_rows(rows):
    fd, name = tempfile.mkstemp(dir=LOG.parent, prefix=".estimate-")
    try:
        with os.fdopen(fd, "w", newline="") as f:
            w = csv.DictWriter(f, FIELDS, delimiter="\t")
            w.writeheader()
            w.writerows(rows)
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, LOG)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def mid(r):
    return (float(r["rounds_low"]) + float(r["rounds_high"])) / 2


def samples(agent, rows):
    return [(mid(r), float(r["actual_min"])) for r in rows
            if r["agent"] == agent and r["actual_min"]
            and r["rounds_low"] and r["rounds_high"]]


def calibration(agent, rows):
    data = samples(agent, rows)
    if len(data) < MIN_ROWS:
        return 0.0, DEFAULT_PACE, 1.0, UNCALIBRATED_WIDEN, len(data), False
    # For each integer overhead up to the median duration, fit a robust pace.
    # Choose the pair with the least mean absolute log error: relative errors
    # matter equally for small and large runs. No guessed outlier cutoff.
    candidates = []
    for overhead in range(math.floor(statistics.median(y for _, y in data)) + 1):
        pace = max(0.0, statistics.median((y - overhead) / x for x, y in data))
        error = statistics.mean(abs(math.log(y / (overhead + pace * x))) for x, y in data)
        candidates.append((error, overhead, pace))
    _, overhead, pace = min(candidates)
    ratios = [y / (overhead + pace * x) for x, y in data]
    quantiles = statistics.quantiles(ratios, n=5, method="inclusive")
    return overhead, pace, quantiles[0], quantiles[3], len(data), True


def basis(model):
    overhead, pace, lower, upper, n, calibrated = model
    if not calibrated:
        return f"{pace:.1f} min/round, uncalibrated n={n}"
    return (f"{overhead:g} min + {pace:.2f} min/round, "
            f"band {lower:.2f}-{upper:.2f}x, calibrated n={n}")


def rounds(value):
    if not re.fullmatch(r"\d+(?:\.\d+)?(?:-\d+(?:\.\d+)?)?", value):
        raise argparse.ArgumentTypeError("rounds must be N or low-high")
    bounds = list(map(float, value.split("-")))
    low, high = bounds[0], bounds[-1]
    if not 0 < low <= high < math.inf:
        raise argparse.ArgumentTypeError("rounds needs 0 < low <= high")
    return low, high


def interval(model, low, high):
    overhead, pace, lower, upper, _, _ = model
    lo = max(1, 5 * math.floor((overhead + pace * low) * lower / 5))
    hi = max(5 * (lo // 5 + 1), 5 * math.ceil((overhead + pace * high) * upper / 5))
    return f"{lo}-{hi}"


def minutes(agent, bounds, rows=None):
    low, high = bounds
    model = calibration(agent, read_rows() if rows is None else rows)
    return interval(model, low, high), basis(model)


def cmd_est(a):
    est, source = minutes(a.agent, a.rounds)
    low, high = a.rounds
    print(f"Agent time: {est} min ({low:g}-{high:g} rounds, {a.agent}, {source})")


def validate_start(agent, bounds, task, ticket, review):
    if review:
        if agent != "claude" or bounds or not ticket or not task:
            raise argparse.ArgumentTypeError("--review needs claude, --ticket and --task, with no rounds")
    elif not (agent and bounds and task):
        raise argparse.ArgumentTypeError("start needs agent, rounds and task")


def cmd_start(a):
    with locked():
        rows = read_rows()
        agent = REVIEW_AGENT if a.review else a.agent
        if a.review:
            # One pass keeps old stats numeric; the separate agent keeps these
            # actuals out of Claude's implementing calibration in both versions.
            est, rounds_low, rounds_high, detail = "", "1", "1", "review, actual time only"
        else:
            est, source = minutes(a.agent, a.rounds, rows)
            low, high = a.rounds
            rounds_low, rounds_high = f"{low:g}", f"{high:g}"
            detail = f"{est} min ({low:g}-{high:g} rounds, {a.agent}, {source})"
        now = datetime.now().astimezone()
        prefix = f"{now:%Y%m%d-%H%M%S}-{agent}"
        ident = f"{prefix}-{secrets.token_hex(3)}"
        while any(r["id"] == ident for r in rows):
            ident = f"{prefix}-{secrets.token_hex(3)}"
        row = {"id": ident,
               "started": now.isoformat(timespec="seconds"), "agent": agent,
               "model": a.model, "ticket": a.ticket, "task": a.task,
               "rounds_low": rounds_low, "rounds_high": rounds_high,
               "est_min": est, "actual_min": "", "note": ""}
        write_rows(rows + [row])
    print(f"Agent time: {detail}. id={row['id']}")


def cmd_done(a):
    with locked():
        rows = read_rows()
        row = next((r for r in rows if r["id"] == a.id), None)
        if row is None:
            raise SystemExit(f"no row with id {a.id} in {LOG}")
        if a.actual is not None:
            actual = a.actual
        else:
            elapsed = (datetime.now().astimezone() - datetime.fromisoformat(row["started"])).total_seconds() / 60
            actual = elapsed - a.wait
        actual_min = f"{max(1, actual):.0f}"
        row["actual_min"], row["note"] = actual_min, a.note
        write_rows(rows)
    print(f"{row['id']}: estimated {row['est_min'] or 'unestimated review'} min, actual {actual_min} min")


def cmd_stats(_):
    rows = read_rows()
    for agent in sorted({r["agent"] for r in rows}):
        if agent == REVIEW_AGENT:
            actuals = [float(r["actual_min"]) for r in rows if r["agent"] == agent and r["actual_min"]]
            median = f"{statistics.median(actuals):g}" if actuals else "n/a"
            print(f"{agent}: count={len(actuals)}, median {median} min/pass, total {sum(actuals):g} min")
        else:
            print(f"{agent}: {basis(calibration(agent, rows))}")
    print(f"log: {LOG}")


def positive(value):
    number = float(value)
    if not 0 < number < math.inf:
        raise argparse.ArgumentTypeError("must be positive and finite")
    return number


def nonnegative(value):
    number = float(value)
    if not 0 <= number < math.inf:
        raise argparse.ArgumentTypeError("must be nonnegative and finite")
    return number


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd")
    e = sub.add_parser("est")
    s = sub.add_parser("start")
    for p in (e, s):
        p.add_argument("agent", choices=["claude", "codex"])
        p.add_argument("rounds", type=rounds, nargs="?" if p is s else None, help="N or low-high, for example 2 or 8-14")
    s.add_argument("--review", action="store_true", help="Claude review; log actual time without estimating rounds")
    s.add_argument("--task", required=True)
    s.add_argument("--ticket", default="")
    s.add_argument("--model", default="")
    d = sub.add_parser("done")
    d.add_argument("id")
    timing = d.add_mutually_exclusive_group()
    timing.add_argument("--wait", type=nonnegative, default=0, help="minutes spent waiting on a human")
    timing.add_argument("--actual", type=positive, help="actual minutes, when closing a run after it ended")
    d.add_argument("--note", default="")
    a = ap.parse_args()
    if a.cmd == "start":
        try:
            validate_start(a.agent, a.rounds, a.task, a.ticket, a.review)
        except argparse.ArgumentTypeError as error:
            ap.error(str(error))
    {"est": cmd_est, "start": cmd_start, "done": cmd_done}.get(a.cmd, cmd_stats)(a)


if __name__ == "__main__":
    main()
