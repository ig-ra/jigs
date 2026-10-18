"""Ticket aggregation, required PR contributions and ticket-wide indicators."""
from collections import defaultdict

from .stages import review_after_bot
from .table_common import ESTIMATES, MEASURES, PR_SUMS, sum_required


def pr_totals(prs):
    if prs is None:
        return dict(prs=None, fix_split_status='unavailable', churn_ratio=None,
                    **dict.fromkeys(PR_SUMS))
    prs = list({(p['repo'], p['pr']): p for p in prs}.values())
    result = dict(prs=len(prs), **{key: sum_required(p.get(key) for p in prs) for key in PR_SUMS})
    rank = {'author_time_estimate': 0, 'suspect': 1, 'unavailable': 2}
    result['fix_split_status'] = max((p.get('fix_split_status', 'unavailable') for p in prs),
                                   key=rank.get, default='unavailable')
    lines = [result[k] for k in ('initial_additions','initial_deletions','fix_additions','fix_deletions')]
    usable = prs and all(p.get('churn_ratio') is not None for p in prs) and all(v is not None for v in lines)
    result['churn_ratio'] = sum(lines[2:]) / sum(lines[:2]) if usable and sum(lines[:2]) else None
    return result


def ticket_rows(stages, estimates=None, prs=None, markers=None, start=None, end=None, unmatched=None):
    groups = defaultdict(list)
    for stage in stages:
        groups[stage['ticket']].append(stage)
    result = []
    for ticket, rows in groups.items():
        row = dict(ticket=ticket, **{metric: sum_required(r[metric] for r in rows) for metric in MEASURES})
        selected = [e for e in estimates or [] if e['ticket'] == ticket]
        row['dispatches'] = len(selected) if estimates is not None else None
        for field, column in zip(ESTIMATES[1:], ('rounds_low','rounds_high','minutes_low','minutes_high','actual_minutes')):
            row[field] = sum_required(e[column] for e in selected) if estimates is not None else None
        related = [p for p in prs if p['ticket'] == ticket] if prs is not None else None
        row.update(pr_totals(related))
        local = [m for m in markers if m.ticket == ticket] if markers is not None else None
        row['review_after_bot'] = review_after_bot(local, related, start, end) if start is not None else None
        partial = any(r['coverage'] == 'partial' for r in rows) or any(row[k] is None for k in ESTIMATES)
        partial |= related is None or bool(related) and (row['fix_split_status'] == 'unavailable' or
            any(row[k] is None for k in PR_SUMS))
        partial |= any((p.get('bot_reviews',0) or p.get('bot_comments',0)) and not p.get('first_bot') for p in related or [])
        partial |= bool(unmatched and unmatched.get(ticket, 0))
        row['coverage'] = 'partial' if partial else 'complete'
        result.append(row)
    return result
