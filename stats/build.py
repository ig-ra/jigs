#!/usr/bin/env python3
"""Rebuild the ticket-flow stats CSVs from `bin/usage export`.

    python3 stats/build.py START END [--usage PATH] [--out DIR]

START and END are UTC dates, END exclusive, as in bin/usage. Writes daily.csv,
weekly.csv and tickets.csv into --out (default: this folder). Only Claude and
Codex calls that carry a ticket are counted; `tagged_pct` shows how much of all
Claude calls that is. Sizes are raw tokens: new input + cache read + cache
write + output. Context is the main thread only (subagents excluded).
"""
import argparse
import collections
import csv
import datetime
import json
import statistics
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def pct(xs, p):
    xs = sorted(xs)
    k = (len(xs) - 1) * p
    f = int(k)
    c = min(f + 1, len(xs) - 1)
    return xs[f] + (xs[c] - xs[f]) * (k - f)


def tokens(c):
    return c['cache_read_tokens'] + (c.get('cache_write_tokens') or 0) + c['new_input_tokens'] + c['output_tokens']


def week_of(ts):
    day = datetime.date.fromisoformat(ts[:10])
    return (day - datetime.timedelta(days=day.weekday())).isoformat()


def ctx_stats(calls):
    main = [c['context_tokens'] for c in calls if not c.get('parent_session_id') and c.get('context_tokens')]
    if not main:
        return None
    return dict(main_calls=len(main), ctx_median_k=round(statistics.median(main) / 1e3),
                ctx_p90_k=round(pct(main, .9) / 1e3), ctx_max_k=round(max(main) / 1e3),
                pct_400k_plus=round(100 * sum(1 for x in main if x >= 4e5) / len(main), 1))


def sessions(calls):
    per = collections.Counter(c['session_id'] for c in calls if not c.get('parent_session_id'))
    return dict(main_sessions=len(per), sessions_over_160_calls=sum(1 for v in per.values() if v > 160))


def period_row(label, key, calls, tagged_all):
    tagged = [c for c in calls if c.get('ticket')]
    if not tagged:
        return None
    ctx = ctx_stats(tagged)
    if not ctx:
        return None
    tickets = collections.defaultdict(list)
    for c in tagged:
        tickets[c['ticket']].append(c)
    big = [v for v in tickets.values() if len(v) >= 100]
    row = {label: key, 'tickets': len(tickets), 'claude_calls': len(tagged),
           'tagged_pct': round(100 * len(tagged) / tagged_all, 1) if tagged_all else '',
           'tokens_m': round(sum(tokens(c) for c in tagged) / 1e6)}
    row.update(sessions(tagged))
    row.update(ctx)
    row['subagent_call_pct'] = round(100 * sum(1 for c in tagged if c.get('parent_session_id')) / len(tagged))
    row['opus_call_pct'] = round(100 * sum(1 for c in tagged if 'opus' in c['model']) / len(tagged))
    row['tickets_100plus_calls'] = len(big)
    row['tokens_per_ticket_m_median'] = round(statistics.median(sum(tokens(c) for c in v) for v in big) / 1e6) if big else ''
    row['calls_per_ticket_median'] = round(statistics.median(len(v) for v in big)) if big else ''
    return row


def write(path, rows):
    with open(path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('start')
    ap.add_argument('end')
    ap.add_argument('--usage', default=str(HERE.parent / 'bin' / 'usage'))
    ap.add_argument('--out', default=str(HERE))
    a = ap.parse_args()
    proc = subprocess.Popen([sys.executable, a.usage, 'export', a.start, a.end],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    days, weeks, all_days, all_weeks = (collections.defaultdict(list) for _ in range(4))
    tix = collections.defaultdict(list)
    for line in proc.stdout:
        d = json.loads(line)
        if d.get('type') != 'call':
            continue
        if d['provider'] == 'claude':
            all_days[d['timestamp'][:10]].append(1)
            all_weeks[week_of(d['timestamp'])].append(1)
            days[d['timestamp'][:10]].append(d)
            weeks[week_of(d['timestamp'])].append(d)
        if d.get('ticket'):
            tix[(d['ticket'], d['provider'], d['phase'])].append(d)
    if proc.wait():
        sys.exit('bin/usage export failed')
    out = Path(a.out)
    daily = [r for k in sorted(days) if (r := period_row('day', k, days[k], len(all_days[k])))]
    weekly = [r for k in sorted(weeks) if (r := period_row('week_start', k, weeks[k], len(all_weeks[k])))]
    ticket_rows = []
    for (ticket, provider, phase), cs in sorted(tix.items()):
        row = {'ticket': ticket, 'provider': provider, 'phase': phase, 'calls': len(cs),
               'new_input_tokens': sum(c['new_input_tokens'] for c in cs),
               'cache_read_tokens': sum(c['cache_read_tokens'] for c in cs),
               'cache_write_tokens': sum(c.get('cache_write_tokens') or 0 for c in cs),
               'output_tokens': sum(c['output_tokens'] for c in cs)}
        ctx = ctx_stats(cs) or {}
        for k in ('ctx_median_k', 'ctx_p90_k', 'ctx_max_k'):
            row[k] = ctx.get(k, '')
        ticket_rows.append(row)
    write(out / 'daily.csv', daily)
    write(out / 'weekly.csv', weekly)
    write(out / 'tickets.csv', ticket_rows)
    print(f'{a.start}..{a.end}: {len(daily)} days, {len(weekly)} weeks, {len(ticket_rows)} ticket/provider/phase rows -> {out}')


if __name__ == '__main__':
    main()
