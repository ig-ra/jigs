"""Pure ticket marker ordering and whole-turn latching."""
from bisect import bisect_right
from collections import defaultdict

from .timing import overlaps


def timeline(markers):
    grouped = defaultdict(list)
    for marker in markers:
        grouped[marker.ticket].append(marker)
    result = {}
    for ticket, group in grouped.items():
        stage, review, cycle = 'unknown', 0, 0
        ordered = []
        for marker in sorted(group, key=lambda m: (m.time, m.source, m.identity or '')):
            kind = marker.kind
            if kind == 'review':
                review += 1
                stage = 'first_review' if review == 1 else 'further_review'
            elif kind in ('simplify', 'native_review', 'own_review'):
                if not review:
                    review = 1
                stage = 'first_review' if review == 1 else 'further_review'
            elif kind in ('fix', 'commit'):
                if kind == 'fix' or review:
                    cycle += int(stage != 'fix')
                    stage = 'fix'
                else:
                    stage = 'implement'
            else:
                stage = kind
            ordered.append((marker.time, marker, stage, review or None, cycle or None))
        result[ticket] = ordered
    return result


def assign(turns, markers):
    lines = timeline(markers)
    for turn in turns:
        line = lines.get(turn.ticket, [])
        index = bisect_right([row[0] for row in line], turn.start) - 1 if turn.start else -1
        if index >= 0:
            _, turn.marker, turn.stage, turn.review_pass, turn.cycle = line[index]
        else:
            turn.stage, turn.marker = 'unknown', None
        turn.order = 'ambiguous' if turn.ticket and any(
            other.ticket == turn.ticket and
            (other.provider, other.session) != (turn.provider, turn.session) and
            overlaps(turn, other) for other in turns) else 'timestamp'
    return turns
