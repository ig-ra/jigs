#!/usr/bin/env python3
"""Build site/data.json: token usage by day, ticket, stage and tool, plus the milestone commits to compare it with.

    python3 stats/build_flow.py START END --usage PATH [--repo DIR] [--milestones FILE] [--out FILE]

START and END are UTC dates, END exclusive, as in bin/usage. Only calls that carry a ticket are
counted. Days and ticket start times are in this machine's local time zone. Milestones are the commits
listed in milestones.json (hash, label, expected effect, why), looked up in --repo.

Per call, `raw` is new input + cache read + cache write + output. `weighted` is the IGR-14 proxy
from bin/usage (uncalibrated) and exists for Claude only; Codex calls carry raw tokens only.
"""
import argparse
import collections
import datetime
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

# Same weights as bin/usage: price relative to a new input token.
WEIGHTS = {'input': 1, 'cw5m': 1.25, 'cw1h': 2, 'read': .1, 'output': 5}
MODEL_WEIGHTS = {'opus': 1, 'fable': 1, 'sonnet': .6, 'haiku': .2}


def raw(c):
    return c['new_input_tokens'] + c['cache_read_tokens'] + (c.get('cache_write_tokens') or 0) + c['output_tokens']


def weighted(c):
    if c['provider'] != 'claude':
        return 0
    model = (c.get('model') or '').lower()
    mult = next((w for k, w in MODEL_WEIGHTS.items() if k in model), None)
    if mult is None:
        return 0
    return mult * (c['new_input_tokens'] * WEIGHTS['input']
                   + (c.get('cache_write_5m_tokens') or 0) * WEIGHTS['cw5m']
                   + (c.get('cache_write_1h_tokens') or 0) * WEIGHTS['cw1h']
                   + c['cache_read_tokens'] * WEIGHTS['read']
                   + c['output_tokens'] * WEIGHTS['output'])


def local(ts):
    return datetime.datetime.fromisoformat(ts.replace('Z', '+00:00')).astimezone()


def rows_of(bucket):
    return [[*k, v[0], round(v[1]), round(v[2])] for k, v in sorted(bucket.items())]


def milestones(repo, path):
    """The hand-picked commits in `path`, each with its commit time. Order in the file is irrelevant."""
    result = []
    for m in json.loads(Path(path).read_text()):
        ts = subprocess.run(['git', '-C', repo, 'show', '-s', '--format=%aI', m['hash']],
                            capture_output=True, text=True, check=True).stdout.strip()
        result.append({**m, 'ts': datetime.datetime.fromisoformat(ts).astimezone().isoformat()})
    return sorted(result, key=lambda m: m['ts'])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('start')
    ap.add_argument('end')
    ap.add_argument('--usage', required=True)
    ap.add_argument('--repo', default=str(HERE.parent))
    ap.add_argument('--milestones', default=str(HERE / 'milestones.json'))
    ap.add_argument('--out', default=str(HERE / 'site' / 'data.json'))
    a = ap.parse_args()

    proc = subprocess.Popen([sys.executable, a.usage, 'export', a.start, a.end],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    zero = lambda: [0, 0, 0]
    days = collections.defaultdict(lambda: collections.defaultdict(zero))
    tickets = collections.defaultdict(lambda: {'start': None, 'rows': collections.defaultdict(zero)})
    data_end = None
    for line in proc.stdout:
        c = json.loads(line)
        if c.get('type') != 'call' or not c.get('ticket'):
            continue
        when = local(c['timestamp'])
        data_end = max(data_end or when, when)
        key = (c['provider'], c['phase'], c['kind'])
        for bucket in (days[when.date().isoformat()][key], tickets[c['ticket']]['rows'][key]):
            bucket[0] += 1
            bucket[1] += raw(c)
            bucket[2] += weighted(c)
        t = tickets[c['ticket']]
        if t['start'] is None or when < t['start']:
            t['start'] = when
    if proc.wait():
        sys.exit('bin/usage export failed')

    data = {
        'generated': datetime.datetime.now().astimezone().isoformat(timespec='minutes'),
        'data_end': data_end.isoformat(),
        'columns': ['provider', 'phase', 'kind', 'calls', 'raw', 'weighted'],
        'days': [{'day': d, 'rows': rows_of(days[d])} for d in sorted(days)],
        'tickets': sorted(({'id': k, 'start': v['start'].isoformat(), 'rows': rows_of(v['rows'])}
                           for k, v in tickets.items()), key=lambda t: t['start']),
        'milestones': milestones(a.repo, a.milestones),
    }
    Path(a.out).write_text(json.dumps(data, separators=(',', ':')))
    print(f"{a.start}..{a.end}: {len(data['days'])} days, {len(data['tickets'])} tickets, "
          f"{len(data['milestones'])} milestones -> {a.out}")


if __name__ == '__main__':
    main()
