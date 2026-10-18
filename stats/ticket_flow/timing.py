"""Raw intervals and diagnostics; never subtract waits or overlap from work."""
from collections import defaultdict


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
        for turn in sorted(group, key=lambda t: (t.end, t.source)):
            intervals.append((turn.interval_start, turn.end))
            new_union = union_minutes(intervals)
            turn.overlap = max(0, turn.minutes - (new_union - old_union))
            old_union = new_union


def overlaps(left, right):
    a, b = left.interval_start or left.start, right.interval_start or right.start
    return (a is not None and b is not None and left.end is not None and
            right.end is not None and max(a, b) < min(left.end, right.end))
