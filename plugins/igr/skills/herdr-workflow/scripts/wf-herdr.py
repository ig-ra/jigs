#!/usr/bin/env python3
"""wf-herdr.py — herdr socket toolbox for the igr workflow scripts.

One-shot JSON-RPC over $HERDR_SOCKET_PATH. The wire is newline-framed JSON; every request needs
id + method + params (params required even when empty). Each subcommand wraps one herdr method (or a
tiny composition); `rpc` is the raw escape hatch. Prints the useful field to stdout; errors -> stderr,
exit 1. Used by wf-herdr.sh and callable directly for the socket-only ops the `herdr` CLI lacks
(pane.move to a new tab/workspace, event streaming, terminal_id -> pane_id resolution).

  tab-create    <ws> <label> [--cwd DIR]                 -> "<pane_id>\t<terminal_id>"
  split         <pane> <right|down> [--cwd DIR]          -> "<pane_id>\t<terminal_id>"   (same tab)
  run           <pane> <command>                         -> send command text + Enter (launch a shell cmd/agent)
  send-keys     <pane> <key>...                          -> e.g. enter / escape / ctrl+c
  wait-output   <pane> <pattern> [--timeout MS] [--regex]-> exit 0 on match, 1 on timeout
  agent-session <pane>                                   -> agent session id (uuid) or ""
  move          <pane> --new-tab <ws> [--label L]        -> new pane_id  (break a split out / cross-workspace)
  move          <pane> --new-workspace [--label L]       -> new pane_id
  move          <pane> --tab <tab> [--target <pane>] [--split right|down] -> new pane_id  (merge in as a split)
  resolve       <terminal_id>                            -> current pane_id (move-proof: pane_id changes on move)
  subscribe     <event.type>...                          -> stream matching events, one JSON per line
  rpc           <method> [params-json]                   -> raw result JSON
"""
import argparse
import json
import os
import socket
import sys


def _conn():
    path = os.environ.get("HERDR_SOCKET_PATH")
    if not path:
        sys.exit("wf-herdr: HERDR_SOCKET_PATH unset (run inside a herdr pane)")
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect(path)
    return s


def _readline(s, buf=b""):
    while b"\n" not in buf:
        chunk = s.recv(65536)
        if not chunk:
            break
        buf += chunk
    line, _, rest = buf.partition(b"\n")
    return line, rest


def rpc(method, params=None, timeout=30.0):
    """Send one request, return its `result` dict. Exits 1 on an error response."""
    s = _conn()
    s.settimeout(timeout)
    s.sendall((json.dumps({"id": "wf", "method": method, "params": params or {}}) + "\n").encode())
    line, _ = _readline(s)
    s.close()
    resp = json.loads(line)
    if "error" in resp:
        err = resp["error"]
        sys.exit("wf-herdr: %s: %s" % (method, err.get("message", err) if isinstance(err, dict) else err))
    return resp["result"]


def _pane_line(pane):
    return "%s\t%s" % (pane.get("pane_id", ""), pane.get("terminal_id", ""))


def cmd_tab_create(a):
    params = {"workspace_id": a.ws, "label": a.label}
    if a.cwd:
        params["cwd"] = a.cwd
    print(_pane_line(rpc("tab.create", params)["root_pane"]))


def cmd_split(a):
    params = {"target_pane_id": a.pane, "direction": a.direction, "focus": False}
    if a.cwd:
        params["cwd"] = a.cwd
    print(_pane_line(rpc("pane.split", params)["pane"]))


def cmd_run(a):
    rpc("pane.send_input", {"pane_id": a.pane, "text": a.command, "keys": ["enter"]})


def cmd_send_keys(a):
    rpc("pane.send_keys", {"pane_id": a.pane, "keys": a.keys})


def cmd_wait_output(a):
    match = {"type": "regex" if a.regex else "substring", "value": a.pattern}
    # server holds the connection up to timeout_ms; give the socket read a little more headroom.
    rpc("pane.wait_for_output",
        {"pane_id": a.pane, "match": match, "source": a.source, "timeout_ms": a.timeout},
        timeout=a.timeout / 1000 + 5)
    # match -> rpc returned normally -> exit 0. timeout -> rpc exited 1 already.


def cmd_agent_session(a):
    result = rpc("pane.get", {"pane_id": a.pane})
    pane = result.get("pane", result)
    print((pane.get("agent_session") or {}).get("value") or "")


def cmd_move(a):
    if a.new_tab is not None:
        dest = {"type": "new_tab", "workspace_id": a.new_tab}
        if a.label:
            dest["label"] = a.label
    elif a.new_workspace:
        dest = {"type": "new_workspace"}
        if a.label:
            dest["tab_label"] = a.label
    elif a.tab:
        dest = {"type": "tab", "tab_id": a.tab, "split": a.split or "right"}
        if a.target:
            dest["target_pane_id"] = a.target
    else:
        sys.exit("move: need --new-tab WS | --new-workspace | --tab TAB")
    result = rpc("pane.move", {"pane_id": a.pane, "destination": dest})
    moved = result.get("move_result", result).get("pane", {})
    print(moved.get("pane_id", ""))


def cmd_resolve(a):
    for pane in rpc("pane.list", {}).get("panes", []):
        if pane.get("terminal_id") == a.terminal_id:
            print(pane.get("pane_id", ""))
            return
    sys.exit("resolve: no live pane with terminal_id %s" % a.terminal_id)


def cmd_subscribe(a):
    s = _conn()
    subs = [{"type": t} for t in a.events]
    s.sendall((json.dumps({"id": "sub", "method": "events.subscribe",
                           "params": {"subscriptions": subs}}) + "\n").encode())
    buf = b""
    while True:
        line, buf = _readline(s, buf)
        if not line and not buf:
            break
        print(line.decode(), flush=True)


def cmd_rpc(a):
    json.dump(rpc(a.method, json.loads(a.params) if a.params else {}), sys.stdout)


def main():
    ap = argparse.ArgumentParser(prog="wf-herdr.py", description="herdr socket toolbox")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("tab-create"); p.add_argument("ws"); p.add_argument("label"); p.add_argument("--cwd"); p.set_defaults(fn=cmd_tab_create)
    p = sub.add_parser("split"); p.add_argument("pane"); p.add_argument("direction", choices=["right", "down"]); p.add_argument("--cwd"); p.set_defaults(fn=cmd_split)
    p = sub.add_parser("run"); p.add_argument("pane"); p.add_argument("command"); p.set_defaults(fn=cmd_run)
    p = sub.add_parser("send-keys"); p.add_argument("pane"); p.add_argument("keys", nargs="+"); p.set_defaults(fn=cmd_send_keys)
    p = sub.add_parser("wait-output"); p.add_argument("pane"); p.add_argument("pattern"); p.add_argument("--timeout", type=int, default=120000); p.add_argument("--regex", action="store_true"); p.add_argument("--source", choices=["visible", "recent", "recent_unwrapped", "detection"], default="recent_unwrapped"); p.set_defaults(fn=cmd_wait_output)
    p = sub.add_parser("agent-session"); p.add_argument("pane"); p.set_defaults(fn=cmd_agent_session)
    p = sub.add_parser("move"); p.add_argument("pane"); p.add_argument("--new-tab"); p.add_argument("--new-workspace", action="store_true"); p.add_argument("--tab"); p.add_argument("--target"); p.add_argument("--split", choices=["right", "down"]); p.add_argument("--label"); p.set_defaults(fn=cmd_move)
    p = sub.add_parser("resolve"); p.add_argument("terminal_id"); p.set_defaults(fn=cmd_resolve)
    p = sub.add_parser("subscribe"); p.add_argument("events", nargs="+"); p.set_defaults(fn=cmd_subscribe)
    p = sub.add_parser("rpc"); p.add_argument("method"); p.add_argument("params", nargs="?"); p.set_defaults(fn=cmd_rpc)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
