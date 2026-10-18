"""Run provenance and source/attribution coverage; no repo aggregate rows."""
from math import fsum

from .model import ACTORS, TOKENS
from .stages import timeline
from .table_common import in_window, iso, sum_required


def share(ticket, actor, metric, numerator, denominator):
    return dict(ticket=ticket, actor=actor, metric=metric, numerator=numerator, denominator=denominator,
                value=100 * numerator / denominator if numerator is not None and denominator else None)


def actor_rows(ticket, actor, turns, calls, start, end):
    result = []
    selected = [c for c in calls if c['ticket'] == ticket and c['actor'] == actor]
    total = sum_required(c[k] for c in selected for k in TOKENS) if selected else None
    for metric, field, value in (('unknown_tokens_pct','stage','unknown'),
                                 ('ambiguous_tokens_pct','stage_order','ambiguous')):
        numerator = sum_required(c[k] for c in selected if c[field] == value for k in TOKENS) if selected else None
        result.append(share(ticket, actor, metric, numerator, total))
    timed = [t for t in turns if t.ticket == ticket and t.actor == actor and
             t.minutes is not None and in_window(t.end, start, end)]
    for metric, condition in (('unknown_minutes_pct',lambda t: t.stage == 'unknown'),
                               ('ambiguous_minutes_pct',lambda t: t.order == 'ambiguous')):
        numerator = fsum(t.minutes for t in timed if condition(t)) if timed else None
        result.append(share(ticket, actor, metric, numerator, fsum(t.minutes for t in timed) if timed else None))
    return result


def source_rows(turns, calls, start, end, prs, counts, unmatched, markers=()):
    result = [dict(metric='window_start',value=iso(start)),dict(metric='window_end_exclusive',value=iso(end))]
    selected = [t for t in turns if in_window(t.end,start,end) or any(
        c['provider'] == t.provider and c['session'] == t.session and c['turn'] == t.identity for c in calls)]
    tickets = {c['ticket'] for c in calls} | {t.ticket for t in selected} | {
        m.ticket for m in markers if in_window(m.time,start,end)}
    repos = {ticket: {c['repo'] for c in calls if c['ticket'] == ticket and c['repo']} |
             {t.repo for t in selected if t.ticket == ticket and t.repo} |
             {p['repo'] for p in prs or [] if p['ticket'] == ticket} for ticket in tickets}
    totals = dict(source_files=len({c['source'].rsplit(':',1)[0] for c in calls} |
        {t.source.rsplit(':',1)[0] for t in selected}),
        sessions=len({(t.provider,t.session) for t in selected}),
        unassigned_calls=sum(c['ticket'] is None for c in calls),
        unknown_calls=sum(c['stage'] == 'unknown' for c in calls),
        ambiguous_turns=sum(t.order == 'ambiguous' for t in selected),
        multi_repo_tickets=sum(len(r) > 1 for r in repos.values()),
        no_pr_tickets=sum(not any(p['ticket'] == t for p in prs) for t in tickets if t) if prs is not None else None,
        pr_heads=len({(p['repo'],p['head_sha']) for p in prs}) if prs is not None and all(
            p.get('head_sha') is not None for p in prs) else None)
    result.extend(dict(metric=k,value=v) for k,v in totals.items())
    result.extend(dict(metric='reader_' + k,value=v) for k,v in sorted(counts.items()))
    for ticket in sorted(tickets, key=lambda t: t or ''):
        completed = [t for t in selected if t.ticket == ticket and t.minutes is not None and in_window(t.end,start,end)]
        values = dict(calls=sum(c['ticket'] == ticket for c in calls), unmatched_starts=unmatched.get(ticket,0),
            claude_duration_records=sum(t.actor == 'claude_main' for t in completed),
            codex_completed_pairs=sum(t.actor == 'codex' for t in completed),
            prs_found=sum(p['ticket'] == ticket for p in prs) if prs is not None else None)
        result.extend(dict(ticket=ticket,metric=k,value=v) for k,v in values.items())
    return result, tickets


def run_rows(turns, calls, start, end, counts, unmatched, prs, markers, estimates=None):
    result, tickets = source_rows(turns,calls,start,end,prs,counts,unmatched,markers)
    for ticket in sorted(tickets,key=lambda t: t or ''):
        for actor in ACTORS:
            result.extend(actor_rows(ticket,actor,turns,calls,start,end))
        result.append(dict(ticket=ticket,metric='native_review_usage_missing',
            value=sum(r[-1] == 'native_review' and in_window(r[0],start,end)
                      for r in timeline(markers).get(ticket, []))))
    for pr in prs or []:
        result.extend(dict(ticket=pr['ticket'],repo=pr['repo'],pr=pr['pr'],metric='pr_' + k,value=v,
            source=f'github:{pr["repo"]}#{pr["pr"]}') for k,v in pr.items() if k not in ('ticket','repo','pr'))
    for marker in markers:
        result.append(dict(ticket=marker.ticket,repo=marker.repo,metric='marker_' + marker.kind,
                           value=iso(marker.time),source=marker.source))
    for estimate in estimates or []:
        result.extend(dict(ticket=estimate['ticket'],actor=estimate['agent'],metric='estimate_' + field,
            value=estimate[field],source=estimate['source']) for field in (
                'identity','rounds_low','rounds_high','minutes_low','minutes_high','actual_minutes'))
    return result
