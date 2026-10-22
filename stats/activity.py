#!/usr/bin/env python3
"""Split Claude tokens by what each call did, and list subagents.

    python3 stats/activity.py START END [--usage PATH] [--out DIR]

Joins `bin/usage export` (tokens, ticket, phase, context) with the tool inputs
in the raw transcripts, one read per file. Writes activity-daily.csv,
activity-tickets.csv (main thread only) and subagents.csv. Tokens are raw:
new input + cache read + cache write + output. A call costs its whole context,
so a text-only turn weighs as much as the context it re-reads. Classification
is pattern matching on the tool inputs, first match wins; check activity
"other" and a sample of calls before trusting a small share.
"""
import argparse
import collections
import csv
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TK_PR = r'tk\S*\s+(--cwd\s+\S+\s+)?(--json\s+)?pr\b'
TK_STEP = r'tk\S*\s+(--cwd\s+\S+\s+)?step|estimate\.py'
TK_SETUP = r'tk\S*\s+(--cwd\s+\S+\s+)?(prep|close|go)\b|git .*worktree|check-ignore'


def classify(tools):
    names = [t[0] for t in tools]
    cmd = ' '.join(t[1] for t in tools if t[0] == 'Bash')
    paths = ' '.join(t[1] for t in tools if t[0] in ('Read', 'Write', 'Edit'))
    if not tools:
        return 'reply / communication (no tool)'
    if 'AskUserQuestion' in names:
        return 'human poll'
    if 'Agent' in names or 'Task' in names:
        return 'subagent dispatch'
    if any(n.startswith('mcp__linear') for n in names):
        return 'linear'
    if cmd:
        if 'codex-companion' in cmd:
            return 'native codex review'
        if re.search(r'\bherdr\b|watch-codex', cmd):
            return 'codex management (herdr)'
        if re.search(r'\bgh\b|' + TK_PR, cmd):
            return 'github / CI / bot threads'
        if re.search(TK_STEP, cmd):
            return 'tk bookkeeping (step, estimate)'
        if re.search(TK_SETUP, cmd):
            return 'worktree setup / cleanup'
        if re.search(r'unittest|pytest|go test|bin/usage|python3 -B -', cmd):
            return 'tests / measurements'
        if re.search(r'\bgit\b', cmd):
            return 'git'
        if re.search(r'\bsleep\b|\bwatch\b', cmd):
            return 'waiting'
    if paths:
        if re.search(r'/igr/(brief-|codex-|impl-|compare|findings)', paths):
            return 'codex briefs and replies'
        if re.search(r'/igr/(model-|A-to-B|kiss-pass|plan-|living|investigation|new-work)', paths):
            return 'design docs (models, plan, KISS)'
        if re.search(r'/igr/review-', paths):
            return 'review docs'
        if re.search(r'/igr/(resume|corrections|state)', paths):
            return 'checkpoint'
        if re.search(r'SKILL\.md|loop\.md|resume\.md|references/|/memory|MEMORY|remember', paths):
            return 'skill / memory reads'
        if any(t[0] in ('Write', 'Edit') for t in tools):
            return 'source edits'
        return 'code / doc reading'
    if any(n in ('Grep', 'Glob', 'LSP', 'Read') for n in names) or re.search(r'\b(rg|grep|sed|cat|ls|find|head|tail|wc)\b', cmd):
        return 'code / doc reading'
    return 'other'


def tokens(c):
    return c['cache_read_tokens'] + (c.get('cache_write_tokens') or 0) + c['new_input_tokens'] + c['output_tokens']


def tool_text(block):
    i = block.get('input') or {}
    return i.get('command') or i.get('file_path') or i.get('pattern') or i.get('path') or ''


def write(path, rows, fields):
    with open(path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
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
    calls, need = [], collections.defaultdict(set)
    for line in proc.stdout:
        d = json.loads(line)
        if d.get('type') != 'call' or d['provider'] != 'claude':
            continue
        c = dict(day=d['timestamp'][:10], session=d['session_id'], parent=d.get('parent_session_id'),
                 ticket=d.get('ticket') or '', phase=d['phase'], tokens=tokens(d), ctx=d.get('context_tokens') or 0,
                 path=d['source']['path'], tools=[(t['id'], t['name'], t['source']['path'], t['source']['line']) for t in d.get('tools') or []])
        for _, _, p, ln in c['tools']:
            need[p].add(ln)
        calls.append(c)
    if proc.wait():
        sys.exit('bin/usage export failed')
    text = {}
    for p, lines in need.items():
        try:
            with open(p, errors='replace') as f:
                for n, raw in enumerate(f, 1):
                    if n not in lines:
                        continue
                    try:
                        rec = json.loads(raw)
                    except ValueError:
                        continue
                    for b in (rec.get('message') or {}).get('content') or []:
                        if isinstance(b, dict) and b.get('type') == 'tool_use':
                            text[b['id']] = (b['name'], tool_text(b), (b.get('input') or {}).get('subagent_type'))
        except OSError:
            continue
    # a child inherits its ticket from the main session it belongs to
    by_session = collections.defaultdict(collections.Counter)
    for c in calls:
        if not c['parent'] and c['ticket']:
            by_session[c['session']][c['ticket']] += 1
    daily, tix, subs = (collections.defaultdict(lambda: [0, 0, 0]) for _ in range(3))
    metas = {}
    for c in calls:
        tools = [(text[t[0]][0], text[t[0]][1]) for t in c['tools'] if t[0] in text]
        act = classify(tools) if len(tools) == len(c['tools']) else 'other'
        if not c['parent']:
            for key, agg in (((c['day'], act), daily), ((c['ticket'], c['phase'], act), tix)):
                agg[key][0] += 1
                agg[key][1] += c['tokens']
                agg[key][2] += c['ctx']
        else:
            meta = metas.get(c['path'])
            if meta is None:
                try:
                    meta = json.load(open(re.sub(r'\.jsonl$', '.meta.json', c['path'])))
                except (OSError, ValueError):
                    meta = {}
                metas[c['path']] = meta
            ticket = c['ticket'] or (by_session[c['parent']].most_common(1) or [('', 0)])[0][0]
            key = (c['day'], ticket, meta.get('agentType', 'unknown'), (meta.get('description') or '')[:60], act)
            subs[key][0] += 1
            subs[key][1] += c['tokens']
    out = Path(a.out)
    write(out / 'activity-daily.csv',
          [dict(day=k[0], activity=k[1], calls=v[0], tokens_m=round(v[1] / 1e6, 2), ctx_mean_k=round(v[2] / v[0] / 1e3)) for k, v in sorted(daily.items())],
          ['day', 'activity', 'calls', 'tokens_m', 'ctx_mean_k'])
    write(out / 'activity-tickets.csv',
          [dict(ticket=k[0], phase=k[1], activity=k[2], calls=v[0], tokens_m=round(v[1] / 1e6, 2), ctx_mean_k=round(v[2] / v[0] / 1e3)) for k, v in sorted(tix.items())],
          ['ticket', 'phase', 'activity', 'calls', 'tokens_m', 'ctx_mean_k'])
    write(out / 'subagents.csv',
          [dict(day=k[0], ticket=k[1], agent_type=k[2], description=k[3], activity=k[4], calls=v[0], tokens_m=round(v[1] / 1e6, 2)) for k, v in sorted(subs.items())],
          ['day', 'ticket', 'agent_type', 'description', 'activity', 'calls', 'tokens_m'])
    print(f'{a.start}..{a.end}: {len(calls)} Claude calls -> {out}')


if __name__ == '__main__':
    main()
