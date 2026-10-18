"""Pure pilot audit and summary assembly; one definition of missing sums."""
from collections import defaultdict
from math import fsum

from .model import ACTORS, TOKENS
from .sources import reference, stamp
from .stages import timeline

AUDIT_FIELDS = ('provider', 'id', 'timestamp', 'ticket', 'ticket_basis', 'repo', 'actor', 'session',
                'parent_session', 'turn', 'turn_start', 'start_basis', 'source',
                'marker_time', 'marker_source', 'marker_repo', 'stage', 'stage_order',
                'review_pass', 'cycle', 'activity', 'activity_basis', 'activity_source',
                'child_type', 'child_description', 'child_family', 'child_basis', *TOKENS, 'missing_reason')
MEASURES = tuple(f'{actor}_{token}' for actor in ACTORS for token in TOKENS) + (
    'claude_main_minutes_raw', 'codex_minutes_raw', 'foreground_wait_min', 'turn_overlap_min',
    'simplify_passes', 'native_review_passes', 'own_review_passes', 'fix_rounds', 'calls', 'turns')
ESTIMATES = ('dispatches', 'estimated_rounds_low', 'estimated_rounds_high',
             'estimated_minutes_low', 'estimated_minutes_high', 'completed_dispatch_minutes')
STAGE_FIELDS = ('ticket', 'stage', 'review_pass', 'cycle', *MEASURES, 'coverage')
TICKET_FIELDS = ('ticket', *MEASURES, *ESTIMATES, 'coverage')
RUN_FIELDS = ('ticket', 'actor', 'metric', 'value', 'numerator', 'denominator',
              'repo', 'pr', 'source')


def in_window(time, start, end):
    return time is not None and start <= time < end


def sum_required(values):
    values = list(values)
    return None if any(v is None for v in values) else (
        fsum(values) if any(isinstance(v, float) for v in values) else sum(values))


def iso(value):
    return value.isoformat() if value else None


def audit_rows(turns, start, end):
    result = []
    for turn in turns:
        marker = turn.marker
        for call in turn.calls:
            if not in_window(stamp(call['timestamp']), start, end):
                continue
            result.append(dict(provider=call['provider'], id=call['id'], timestamp=call['timestamp'], ticket=turn.ticket,
                ticket_basis=call.get('ticket_basis') or turn.ticket_basis, repo=call.get('repo') or turn.repo,
                actor=turn.actor, session=turn.session, parent_session=turn.parent,
                turn=turn.identity, turn_start=iso(turn.start), start_basis=turn.start_basis,
                source=reference(**call['source']), marker_time=iso(marker.time) if marker else None,
                marker_source=marker.source if marker else None, marker_repo=marker.repo if marker else None,
                stage=turn.stage, stage_order=turn.order, review_pass=turn.review_pass, cycle=turn.cycle,
                activity=call.get('activity'), activity_basis=call.get('activity_basis'),
                activity_source=call.get('activity_source'), child_type=turn.child_type,
                child_description=turn.child_description, child_family=turn.child_family, child_basis=turn.child_basis,
                missing_reason=missing_reason(turn, call),
                **{token: call.get(token) for token in TOKENS}))
    return result


def missing_reason(turn, call):
    reasons = []
    if not turn.ticket:
        reasons.append('unassigned_ticket')
    if turn.marker is None:
        reasons.append('no_preceding_marker')
    if call.get('activity_basis') == 'missing_tool_input':
        reasons.append('missing_tool_input')
    if turn.parent:
        for name in ('type', 'description', 'family'):
            if getattr(turn, 'child_' + name) is None:
                reasons.append('missing_child_' + name)
    return ';'.join(reasons) or None


def stage_rows(turns, calls, start, end, markers=()):
    groups = defaultdict(lambda: {'calls': [], 'turns': []})
    for call in calls:
        key = call['ticket'], call['stage'], call['review_pass'], call['cycle']
        groups[key]['calls'].append(call)
    for turn in turns:
        if in_window(turn.end, start, end):
            groups[turn.ticket, turn.stage, turn.review_pass, turn.cycle]['turns'].append(turn)
    events = defaultdict(lambda: defaultdict(int))
    for ticket, line in timeline(markers).items():
        for time, marker, stage, review, cycle, invocation in line:
            if not in_window(time, start, end):
                continue
            key = ticket, stage, review, cycle
            if invocation:
                metric = 'fix_rounds' if invocation == 'fix_round' else invocation + '_passes'
                events[key][metric] += 1
            if events[key]:
                groups[key]
    result = []
    for key, group in groups.items():
        row = dict(zip(STAGE_FIELDS[:4], key))
        for actor in ACTORS:
            bucket = [c for c in group['calls'] if c['actor'] == actor]
            row.update({f'{actor}_{token}': sum_required(c[token] for c in bucket) for token in TOKENS})
        for actor in ('claude_main', 'codex'):
            row[actor + '_minutes_raw'] = fsum(t.minutes for t in group['turns']
                                              if t.actor == actor and t.minutes is not None)
        row['turn_overlap_min'] = fsum(t.overlap for t in group['turns'])
        row['foreground_wait_min'] = sum_required(t.wait for t in group['turns'] if t.minutes is not None)
        row.update({metric: events[key][metric] for metric in (
            'simplify_passes', 'native_review_passes', 'own_review_passes', 'fix_rounds')})
        row['calls'], row['turns'] = len(group['calls']), len(group['turns'])
        row['coverage'] = 'partial'  # Pilot deliberately omits full actor/activity enrichment.
        result.append(row)
    return result


def ticket_rows(stages, estimates=None):
    groups = defaultdict(list)
    for stage in stages:
        groups[stage['ticket']].append(stage)
    result = [dict(ticket=ticket, coverage='partial', **{
        metric: sum_required(r[metric] for r in rows) for metric in MEASURES})
        for ticket, rows in groups.items()]
    for row in result:
        selected = [e for e in estimates or [] if e['ticket'] == row['ticket']]
        row['dispatches'] = len(selected) if estimates is not None else None
        for field, column in zip(ESTIMATES[1:], ('rounds_low', 'rounds_high', 'minutes_low', 'minutes_high', 'actual_minutes')):
            row[field] = sum_required(e[column] for e in selected) if estimates is not None else None
    return result


def source_rows(turns, calls, start, end, prs):
    result = [dict(metric='window_start', value=iso(start)),
              dict(metric='window_end_exclusive', value=iso(end))]
    for ticket in sorted({t.ticket for t in turns}, key=lambda t: t or ''):
        completed = [t for t in turns if t.ticket == ticket and t.minutes is not None
                     and in_window(t.end, start, end)]
        values = {'calls': sum(c['ticket'] == ticket for c in calls),
                  'claude_duration_records': sum(t.actor == 'claude_main' for t in completed),
                  'codex_completed_pairs': sum(t.actor == 'codex' for t in completed),
                  'prs_found': sum(p['ticket'] == ticket for p in prs)}
        result.extend(dict(ticket=ticket, metric=metric, value=value) for metric, value in values.items())
    return result


def run_rows(turns, calls, start, end, counts, unmatched, prs, markers):
    result = source_rows(turns, calls, start, end, prs)
    for metric, value in sorted(counts.items()):
        result.append(dict(metric='reader_' + metric, value=value))
    for ticket in sorted({t.ticket for t in turns}, key=lambda t: t or ''):
        result.append(dict(ticket=ticket, metric='unmatched_starts', value=unmatched[ticket]))
        for actor in ACTORS:
            selected = [c for c in calls if c['ticket'] == ticket and c['actor'] == actor]
            total = sum(sum(c[k] or 0 for k in TOKENS) for c in selected)
            for metric, field, value in (('unknown_tokens_pct', 'stage', 'unknown'),
                                         ('ambiguous_tokens_pct', 'stage_order', 'ambiguous')):
                numerator = sum(sum(c[k] or 0 for k in TOKENS) for c in selected if c[field] == value)
                result.append(dict(ticket=ticket, actor=actor, metric=metric, numerator=numerator,
                                   denominator=total, value=100 * numerator / total if total else None))
            timed = [t for t in turns if t.ticket == ticket and t.actor == actor and
                     t.minutes is not None and in_window(t.end, start, end)]
            for metric, condition in (('unknown_minutes_pct', lambda t: t.stage == 'unknown'),
                                       ('ambiguous_minutes_pct', lambda t: t.order == 'ambiguous')):
                numerator, total_minutes = fsum(t.minutes for t in timed if condition(t)), fsum(t.minutes for t in timed)
                result.append(dict(ticket=ticket, actor=actor, metric=metric, numerator=numerator if timed else None,
                    denominator=total_minutes if timed else None,
                    value=100 * numerator / total_minutes if total_minutes else None))
    for pr in prs:
        for column in ('head_ref', 'created', 'merged', 'first_bot'):
            result.append(dict(ticket=pr['ticket'], repo=pr['repo'], pr=pr['pr'],
                               metric='pr_' + column, value=pr[column]))
    for marker in markers:
        result.append(dict(ticket=marker.ticket, repo=marker.repo, metric='marker_' + marker.kind,
                           value=iso(marker.time), source=marker.source))
    return result


def assemble(turns, start, end, counts, unmatched, prs, markers, estimates=None):
    calls = audit_rows(turns, start, end)
    stages = stage_rows(turns, calls, start, end, markers)
    selected = [e for e in estimates if in_window(e['time'], start, end)] if estimates is not None else None
    result = {'calls': calls, 'stages': stages, 'tickets': ticket_rows(stages, selected),
            'run': run_rows(turns, calls, start, end, counts, unmatched, prs, markers)}
    for estimate in selected or []:
        result['run'].extend(dict(ticket=estimate['ticket'], actor=estimate['agent'], metric='estimate_' + field,
            value=estimate[field], source=estimate['source']) for field in (
                'identity', 'rounds_low', 'rounds_high', 'minutes_low', 'minutes_high', 'actual_minutes'))
    return result
