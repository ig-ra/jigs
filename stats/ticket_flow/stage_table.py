"""Pure stage totals of recorded calls, completed time and invocation counts."""
from collections import defaultdict
from math import fsum

from .model import ACTORS, TOKENS
from .stages import timeline
from .table_common import STAGE_FIELDS, coverage, in_window, sum_required


def invocation_counts(markers, start, end):
    events = defaultdict(lambda: defaultdict(int))
    for ticket, line in timeline(markers).items():
        for time, marker, stage, review, cycle, invocation in line:
            if in_window(time, start, end) and invocation:
                metric = 'fix_rounds' if invocation == 'fix_round' else invocation + '_passes'
                events[ticket, stage, review, cycle][metric] += 1
    return events


def stage_row(key, group, events, markers):
    row = dict(zip(STAGE_FIELDS[:4], key))
    for actor in ACTORS:
        bucket = [c for c in group['calls'] if c['actor'] == actor]
        row.update({f'{actor}_{token}': sum_required(c[token] for c in bucket) for token in TOKENS})
    for actor in ('claude_main', 'codex'):
        row[actor + '_minutes_raw'] = fsum(t.minutes for t in group['turns']
                                          if t.actor == actor and t.minutes is not None)
    row['turn_overlap_min'] = fsum(t.overlap for t in group['turns'])
    row['foreground_wait_min'] = sum_required(t.wait for t in group['turns'] if t.minutes is not None)
    row.update({metric: events[metric] for metric in (
        'simplify_passes', 'native_review_passes', 'own_review_passes', 'fix_rounds')})
    row['calls'], row['turns'] = len(group['calls']), len(group['turns'])
    row['fix_cycles'] = int(key[1] == 'fix' and key[3] is not None)
    row['coverage'] = coverage(group['calls'], group['context'], markers)
    return row


def stage_rows(turns, calls, start, end, markers=()):
    groups = defaultdict(lambda: {'calls': [], 'turns': [], 'context': []})
    for call in calls:
        groups[call['ticket'], call['stage'], call['review_pass'], call['cycle']]['calls'].append(call)
    for turn in turns:
        key = turn.ticket, turn.stage, turn.review_pass, turn.cycle
        if in_window(turn.end, start, end):
            groups[key]['turns'].append(turn)
        if in_window(turn.end, start, end) or any(c['session'] == turn.session and
                c['turn'] == turn.identity and c['provider'] == turn.provider for c in calls):
            groups[key]['context'].append(turn)
    # Marker-only work is published even without a call or completed turn.
    for ticket, line in timeline(markers).items():
        for time, marker, stage, review, cycle, invocation in line:
            if in_window(time, start, end):
                groups[ticket, stage, review, cycle]
    events = invocation_counts(markers, start, end)
    for key in events:
        groups[key]
    return [stage_row(key, group, events[key], [m for m in markers if m.ticket == key[0] and
        in_window(m.time, start, end)]) for key, group in groups.items()]
