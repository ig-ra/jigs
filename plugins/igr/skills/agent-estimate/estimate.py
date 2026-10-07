#!/usr/bin/env python3
"""Agent-time estimates: convert rounds to minutes from logged actuals, and log runs.

  estimate.py est   <agent> <low-high>                       print minutes, log nothing
  estimate.py start <agent> <low-high> --task T [--ticket K] [--model M]
  estimate.py done  <id> [--wait MIN | --actual MIN] [--note TEXT]   fill actual minutes
  estimate.py                                                pace per agent
"""
import argparse
import csv
import os
import statistics
from datetime import datetime
from pathlib import Path

LOG = Path(os.environ.get("AGENT_ESTIMATES", Path.home() / ".claude/agent-estimates.tsv"))
FIELDS = ["id", "started", "agent", "model", "ticket", "task",
          "rounds_low", "rounds_high", "est_min", "actual_min", "note"]
DEFAULT_PACE = 3.0  # minutes per round until MIN_ROWS actuals exist
MIN_ROWS = 5
UNCALIBRATED_WIDEN = 1.5  # stretch the high end while uncalibrated


def read_rows():
    if not LOG.exists():
        return []
    with LOG.open() as f:
        return list(csv.DictReader(f, delimiter="\t"))


def write_rows(rows):
    with LOG.open("w", newline="") as f:
        w = csv.DictWriter(f, FIELDS, delimiter="\t")
        w.writeheader()
        w.writerows(rows)


def pace(agent):
    done = [r for r in read_rows() if r["agent"] == agent and r["actual_min"]]
    if len(done) < MIN_ROWS:
        return DEFAULT_PACE, len(done), False
    per_round = [float(r["actual_min"]) / mid(r) for r in done]
    return statistics.median(per_round), len(done), True


def mid(r):
    return (float(r["rounds_low"]) + float(r["rounds_high"])) / 2


def minutes(agent, rounds):
    low, high = (float(x) for x in rounds.split("-"))
    p, n, calibrated = pace(agent)
    lo, hi = low * p, high * p * (1 if calibrated else UNCALIBRATED_WIDEN)
    basis = f"{p:.1f} min/round, {'calibrated' if calibrated else 'uncalibrated'} n={n}"
    return f"{round5(lo)}-{round5(hi)}", basis, (low, high)


def round5(x):
    return max(5, int(5 * round(x / 5)))


def cmd_est(a):
    est, basis, (low, high) = minutes(a.agent, a.rounds)
    print(f"Agent time: {est} min ({low:g}-{high:g} rounds, {a.agent}, {basis})")


def cmd_start(a):
    est, basis, (low, high) = minutes(a.agent, a.rounds)
    now = datetime.now().astimezone()
    row = {"id": f"{now:%Y%m%d-%H%M%S}-{a.agent}", "started": now.isoformat(timespec="minutes"),
           "agent": a.agent, "model": a.model, "ticket": a.ticket, "task": a.task,
           "rounds_low": f"{low:g}", "rounds_high": f"{high:g}", "est_min": est,
           "actual_min": "", "note": ""}
    write_rows(read_rows() + [row])
    print(f"Agent time: {est} min ({low:g}-{high:g} rounds, {a.agent}, {basis}). id={row['id']}")


def cmd_done(a):
    rows = read_rows()
    row = next((r for r in rows if r["id"] == a.id), None)
    if row is None:
        raise SystemExit(f"no row with id {a.id} in {LOG}")
    if a.actual is not None:
        actual = a.actual
    else:
        elapsed = (datetime.now().astimezone() - datetime.fromisoformat(row["started"])).total_seconds() / 60
        actual = elapsed - a.wait
    row["actual_min"] = f"{max(1, actual):.0f}"
    row["note"] = a.note
    write_rows(rows)
    print(f"{row['id']}: estimated {row['est_min']} min, actual {row['actual_min']} min")


def cmd_stats(_):
    for agent in sorted({r["agent"] for r in read_rows()}):
        p, n, calibrated = pace(agent)
        print(f"{agent}: {p:.1f} min/round, {'calibrated' if calibrated else 'uncalibrated'} n={n}")
    print(f"log: {LOG}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd")
    e = sub.add_parser("est")
    s = sub.add_parser("start")
    for p in (e, s):
        p.add_argument("agent", choices=["claude", "codex"])
        p.add_argument("rounds", help="low-high, for example 8-14")
    s.add_argument("--task", required=True)
    s.add_argument("--ticket", default="")
    s.add_argument("--model", default="")
    d = sub.add_parser("done")
    d.add_argument("id")
    d.add_argument("--wait", type=float, default=0, help="minutes spent waiting on a human")
    d.add_argument("--actual", type=float, help="actual minutes, when closing a run after it ended")
    d.add_argument("--note", default="")
    a = ap.parse_args()
    {"est": cmd_est, "start": cmd_start, "done": cmd_done}.get(a.cmd, cmd_stats)(a)


if __name__ == "__main__":
    main()
