"""Pure audit assembly and orchestration of the three summary tables."""
from .model import TOKENS
from .sources import reference, stamp
from .table_common import (AUDIT_FIELDS, STAGE_FIELDS, TICKET_FIELDS, RUN_FIELDS,
                           in_window, iso, sum_required)
from .stage_table import stage_rows
from .ticket_table import ticket_rows
from .run_table import run_rows


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


def assemble(turns, start, end, counts, unmatched, prs, markers, estimates=None):
    calls = audit_rows(turns, start, end)
    identities = [(c['provider'], c['id']) for c in calls]
    if len(identities) != len(set(identities)):
        raise ValueError('duplicate canonical call in audit')
    stages = stage_rows(turns, calls, start, end, markers)
    selected = [e for e in estimates if in_window(e['time'], start, end)] if estimates is not None else None
    tickets = ticket_rows(stages, selected, prs, markers, start, end, unmatched)
    if counts.get('malformed', 0):
        for row in stages + tickets:
            row['coverage'] = 'partial'
    return {'calls': calls, 'stages': stages, 'tickets': tickets,
            'run': run_rows(turns, calls, start, end, counts, unmatched, prs, markers, selected)}
