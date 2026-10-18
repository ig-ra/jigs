"""Raw intervals and diagnostics; never subtract waits or overlap from work."""
from collections import defaultdict
import re

from .activity import actions, tool_text
from .sources import raw_records, stamp


def minutes(start, end):
    return (end - start).total_seconds() / 60


def union_minutes(intervals):
    total, right = 0.0, None
    for start, end in sorted(intervals):
        if end < start:
            raise ValueError('negative recorded interval')
        total += minutes(max(start, right) if right else start, end) if (
            right is None or end > right) else 0
        right = max(right, end) if right else end
    return total


def attribute_overlap(turns):
    groups = defaultdict(list)
    for turn in turns:
        if turn.minutes is not None:
            groups[turn.provider, turn.session].append(turn)
    for group in groups.values():
        intervals, old_union = [], 0.0
        for turn in sorted(group, key=source_order):
            intervals.append((turn.interval_start, turn.end))
            new_union = union_minutes(intervals)
            turn.overlap = max(0, turn.minutes - (new_union - old_union))
            old_union = new_union


def overlaps(left, right):
    a, b = left.interval_start or left.start, right.interval_start or right.start
    return (a is not None and b is not None and left.end is not None and
            right.end is not None and max(a, b) < min(left.end, right.end))


def source_order(turn):
    path, line = turn.source.rsplit(':', 1)
    return path, int(line)


def foreground_wait(name, args):
    command = tool_text(args)
    if args.get('run_in_background') or re.search(r'(?<!&)&(?!&)|--background\b', command):
        return False
    return name.rsplit('.', 1)[-1] in ('wait', 'wait_agent', 'sleep') or bool(re.search(
        r'\b(?:sleep|watch|watch-codex)\b|\bherdr\b[^\n]*(?:\bwait\b|--wait\b)|\bgh\b[^\n]*\bwatch\b', command))


def wait_intervals(paths):
    """Only matched foreground invocation/result pairs; missing results give no interval."""
    result = []
    for path, provider in sorted(paths.items()):
        pending = {}
        for line, record in raw_records(path, provider):
            if not record.get('timestamp'):
                continue
            time = stamp(record['timestamp'])
            for identity, name, args, output, _ in actions(record, provider):
                if name and foreground_wait(name, args):
                    pending.setdefault(identity, (time, line))
                elif output is not None and identity in pending:
                    start, source_line = pending.pop(identity)
                    if time >= start:
                        result.append((path, source_line, start, time))
    return result


def attribute_waits(turns, intervals):
    """Charge each observed interval once, to its source-ordered enclosing turn."""
    grouped = defaultdict(list)
    for turn in turns:
        if turn.minutes is not None:
            turn.wait = 0.0
            grouped[source_order(turn)[0]].append(turn)
    by_turn = defaultdict(list)
    for path, line, start, end in intervals:
        candidates = [t for t in grouped[path] if source_order(t)[1] >= line and
                      max(t.interval_start, start) < min(t.end, end)]
        if candidates:
            turn = min(candidates, key=source_order)
            by_turn[turn.key].append((max(turn.interval_start, start), min(turn.end, end)))
    for group in grouped.values():
        for turn in group:
            turn.wait = union_minutes(by_turn[turn.key])
