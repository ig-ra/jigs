"""Pure ticket marker ordering and whole-turn latching."""
from bisect import bisect_right
from collections import defaultdict

from .timing import overlaps


def invocation_group(marker, family, seen, active):
    identity = family, marker.group or marker.identity or marker.source
    if identity in seen:
        return None
    seen.add(identity)
    grouped = family in ('own_review', 'fix_round')
    # A running/fixing receipt and its first estimate dispatch are one invocation,
    # in either order. Another explicit dispatch group is a rerun/round.
    new = not (grouped and family in active and (not marker.group or not active[family]))
    if grouped:
        active[family] = active.get(family, False) or bool(marker.group)
    return family if new else None


def timeline(markers):
    grouped = defaultdict(list)
    for marker in markers:
        grouped[marker.ticket].append(marker)
    result = {}
    for ticket, group in grouped.items():
        stage, review, cycle = 'unknown', 0, 0
        seen, active = set(), {}
        ordered = []
        for marker in sorted(group, key=lambda m: (m.time, m.source, m.identity or '')):
            kind = marker.kind
            invocation = None
            if kind in ('review', 'simplify', 'native_review', 'own_review'):
                family = 'own_review' if kind == 'review' else kind
                invocation = invocation_group(marker, family, seen, active)
                review += int(invocation is not None)
                active.pop('fix_round', None)
                stage = 'first_review' if review == 1 else 'further_review'
            elif kind in ('fix', 'commit'):
                if kind == 'fix' or review or stage == 'fix':
                    cycle += int(stage != 'fix')
                    stage = 'fix'
                    if kind == 'fix':
                        invocation = invocation_group(marker, 'fix_round', seen, active)
                else:
                    stage = 'implement'
                active.pop('own_review', None)
            else:
                stage = kind
                active.clear()
            ordered.append((marker.time, marker, stage, review or None, cycle or None, invocation))
        result[ticket] = ordered
    return result


def assign(turns, markers):
    lines = timeline(markers)
    for turn in turns:
        line = lines.get(turn.ticket, [])
        index = bisect_right([row[0] for row in line], turn.start) - 1 if turn.start else -1
        if index >= 0:
            _, turn.marker, turn.stage, turn.review_pass, turn.cycle = line[index][:5]
        else:
            turn.stage, turn.marker = 'unknown', None
            turn.review_pass, turn.cycle = None, None
        turn.order = 'ambiguous' if turn.ticket and any(
            other.ticket == turn.ticket and
            (other.provider, other.session) != (turn.provider, turn.session) and
            overlaps(turn, other) for other in turns) else 'timestamp'
    return turns
