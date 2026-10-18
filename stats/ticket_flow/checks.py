"""Indexed assertions over serialized evidence; independent of table assembly."""
from collections import defaultdict
from decimal import Decimal
import re

from .check import EvidenceError, key, number, timestamp, total
from .model import ACTORS, TOKENS
from .table_common import PR_SUMS


def unique(rows, fields, report, file):
    seen = set()
    for row in rows:
        identity = tuple(row[f] for f in fields)
        report.require(identity not in seen, f'IDENTITY_FAIL file={file} duplicate_key={identity} expected=unique actual=duplicate')
        seen.add(identity)
    return seen


def identity(run, report):
    ids = unique(run.rows['calls'], ('provider', 'id'), report, 'calls.csv')
    tickets = {k[0] for k in unique(run.rows['tickets'], ('ticket',), report, 'tickets.csv')}
    stage_keys = unique(run.rows['stages'], ('ticket', 'stage', 'review_pass', 'cycle'), report, 'stages.csv')
    report.require(tickets == set(run.stages), 'IDENTITY_FAIL file=stages.csv metric=ticket_population '
                   f'expected={sorted(tickets)} actual={sorted(run.stages)}')
    for call in run.rows['calls']:
        detail = f'IDENTITY_FAIL file=calls.csv key={(call["provider"], call["id"])}'
        report.require(bool(call['provider'] and call['id']), detail + ' empty_identity')
        report.require(run.start <= timestamp(call['timestamp']) < run.end, detail + ' outside_window')
        report.require(key(call) in stage_keys, detail + f' missing_stage={key(call)}')
        report.require((call['provider'], call['actor']) in (
            ('claude', 'claude_main'), ('claude', 'claude_subagents'), ('codex', 'codex')),
            detail + f' invalid_actor={call["actor"]}')
    evidence = {c['ticket'] for c in run.rows['calls']}
    for row in run.rows['run']:
        ticket, metric = row['ticket'], row['metric']
        report.require(not ticket or ticket in tickets,
                       f'IDENTITY_FAIL file=run.csv extra_ticket={ticket} metric={metric}')
        if metric.startswith('marker_'):
            time = timestamp(row['value'])
            if run.start <= time < run.end and row['source'] and not row['source'].startswith('github:'):
                evidence.add(ticket)
        if metric == 'estimate_identity' and row['value'] and row['source']:
            evidence.add(ticket)
    for ticket in tickets:
        durations = [run.value(ticket, m) for m in ('claude_duration_records', 'codex_completed_pairs')]
        report.require(all(n is not None for n in durations),
                       f'IDENTITY_FAIL ticket={ticket!r} missing_completed_duration_counts')
        report.require(ticket in evidence or any(n for n in durations),
                       f'IDENTITY_FAIL ticket={ticket!r} missing_local_window_evidence')
    print(f'IDENTITY calls={len(ids)} tickets={len(tickets)} stages={len(stage_keys)}')


def conservation(run, report):
    columns = [f'{a}_{t}' for a in ACTORS for t in TOKENS]
    overall = defaultdict(list)
    for stage in run.rows['stages']:
        group = run.calls[key(stage)]
        for actor in ACTORS:
            calls = [c for c in group if c['actor'] == actor]
            for token in TOKENS:
                field = f'{actor}_{token}'
                expected = total(number(c[token], 'calls.csv ' + token) for c in calls)
                actual = number(stage[field], 'stages.csv ' + field)
                report.equal(expected, actual, f'TOKEN_CONSERVATION_FAIL file=stages.csv key={key(stage)} metric={field}')
                overall[field].append(expected)
    for ticket in run.rows['tickets']:
        name = ticket['ticket']
        stages = run.stages[name]
        for field in columns:
            expected = total(number(s[field], 'stages.csv ' + field) for s in stages)
            report.equal(expected, number(ticket[field], 'tickets.csv ' + field),
                         f'TOKEN_CONSERVATION_FAIL file=tickets.csv ticket={name!r} metric={field}')
        minute_conservation(run, report, ticket, stages)
    for field in columns:
        expected = total(overall[field])
        actual = total(number(t[field], 'tickets.csv ' + field) for t in run.rows['tickets'])
        report.equal(expected, actual, f'TOKEN_CONSERVATION_FAIL overall metric={field}')


def minute_conservation(run, report, ticket, stages):
    name = ticket['ticket']
    for metric in ('unknown_minutes_pct', 'ambiguous_minutes_pct'):
        child = run.fact(name, 'claude_subagents', metric)
        report.require(child['denominator'] == '',
                       f'RAW_MINUTES_FAIL file=run.csv ticket={name!r} actor=claude_subagents invented_denominator')
    tolerance = Decimal(len(stages) + 2) * Decimal('0.000001')
    for actor, count in (('claude_main', 'claude_duration_records'), ('codex', 'codex_completed_pairs')):
        field = actor + '_minutes_raw'
        stage_sum = total(number(s[field], 'stages.csv ' + field) for s in stages)
        actual = number(ticket[field], 'tickets.csv ' + field)
        detail = f'RAW_MINUTES_FAIL file=tickets.csv ticket={name!r} actor={actor} metric={field}'
        report.equal(stage_sum, actual, detail, tolerance)
        denominators = [number(run.fact(name, actor, metric)['denominator'], 'run.csv ' + metric)
                        for metric in ('unknown_minutes_pct', 'ambiguous_minutes_pct')]
        report.equal(denominators[0], denominators[1], detail + ' denominator_agreement')
        completed = run.value(name, count)
        report.require(completed is not None, detail + ' missing_completed_count')
        expected = denominators[0] if completed else Decimal(0)
        report.require((completed and denominators[0] is not None) or
                       (completed == 0 and denominators[0] is None), detail + ' invalid_denominator_availability')
        report.equal(expected, actual, detail + f' run_denominator={denominators[0]}', tolerance)


def activity(run, report, *, enforce_target=False):
    groups = defaultdict(lambda: [Decimal(0), Decimal(0)])
    for call in run.rows['calls']:
        amount = total(number(call[t], 'calls.csv ' + t) for t in TOKENS)
        if amount is None or not call['activity']:
            raise EvidenceError(f'file=calls.csv key={(call["provider"], call["id"])} missing_activity_or_tokens')
        for group in ('overall', 'actor=' + call['actor'], 'repo=' + (call['repo'] or 'unmapped')):
            groups[group][0] += amount if call['activity'] == 'other' else 0
            groups[group][1] += amount
    numerator, denominator = groups['overall']
    for group, (n, d) in sorted(groups.items()):
        pct = f'{100*n/d:.9f}' if d else 'unavailable'
        print(f'ACTIVITY_SHARE {group} other_tokens={n} all_tokens={d} pct={pct}')
    if not enforce_target:
        print('ACTIVITY_TARGET_NOT_REQUESTED target_pct<5')
        return
    passed = denominator > 0 and numerator * 100 < denominator * 5
    report.require(passed,
        f'ACTIVITY_TARGET_FAIL file=calls.csv metric=other_share other_tokens={numerator} '
        f'all_tokens={denominator} actual_pct={100*numerator/denominator if denominator else "unavailable"} target_pct<5')
    if passed:
        print(f'ACTIVITY_TARGET_PASS other_tokens={numerator} all_tokens={denominator} '
              f'pct={100*numerator/denominator:.9f} target_pct<5')


def pr_facts(run, ticket, report):
    snapshots = []
    required = (*PR_SUMS, 'head_ref', 'head_sha', 'created', 'merged', 'first_review',
                'first_bot', 'churn_ratio', 'fix_split_status')
    for (name, repo, pr), rows in run.prs.items():
        if name != ticket:
            continue
        fields = {}
        for row in rows:
            field = row['metric'].removeprefix('pr_')
            report.require(row['metric'].startswith('pr_') and field not in fields,
                           f'PR_MISSINGNESS_FAIL ticket={ticket} repo={repo} pr={pr} duplicate_or_invalid={field}')
            fields[field] = row['value']
        missing = set(required) - fields.keys()
        if missing:
            raise EvidenceError(f'file=run.csv ticket={ticket} repo={repo} pr={pr} missing_metrics={sorted(missing)}')
        report.require(bool(repo) and pr.isdigit() and int(pr) > 0,
                       f'PR_MISSINGNESS_FAIL invalid_identity repo={repo} pr={pr}')
        pattern = r'(?<![A-Za-z0-9])' + re.escape(ticket) + r'(?![A-Za-z0-9])'
        report.require(bool(ticket and re.search(pattern, fields['head_ref'], re.I)),
                       f'PR_MISSINGNESS_FAIL ticket={ticket} repo={repo} pr={pr} head={fields["head_ref"]}')
        snapshots.append(fields)
    return snapshots


def pr_missingness(run, report):
    empty, unavailable_named = 0, False
    for row in run.rows['run']:
        if row['metric'].startswith('pr_') and row['metric'] not in ('pr_lookup_available', 'pr_heads'):
            report.require(bool(row['pr'] and row['repo']),
                f'PR_MISSINGNESS_FAIL file=run.csv ticket={row["ticket"]!r} metric={row["metric"]} '
                f'expected=repo_and_pr_identity actual={(row["repo"], row["pr"])}')
    for ticket in run.rows['tickets']:
        name = ticket['ticket']
        available = run.value(name, 'pr_lookup_available')
        report.require(available in (0, 1), f'PR_MISSINGNESS_FAIL ticket={name!r} invalid_lookup={available}')
        found = run.value(name, 'prs_found')
        snapshots = pr_facts(run, name, report)
        detail = f'PR_MISSINGNESS_FAIL file=tickets.csv ticket={name!r}'
        report.equal(Decimal(len(snapshots)) if available else None, found, detail + ' metric=prs_found')
        report.equal(found, number(ticket['prs'], 'tickets.csv prs'), detail + ' metric=prs')
        if not available:
            unavailable_named |= bool(name)
            report.require(not snapshots and ticket['coverage'] == 'partial', detail + ' unavailable_lookup_contradiction')
        elif not snapshots:
            empty += bool(name)
        for field in PR_SUMS:
            expected = total(number(p[field], 'run.csv pr_' + field) for p in snapshots) if available else None
            report.equal(expected, number(ticket[field], 'tickets.csv ' + field), detail + ' metric=' + field)
        if any(p['fix_split_status'] == 'unavailable' or any(p[f] == '' for f in PR_SUMS) for p in snapshots):
            report.require(ticket['coverage'] == 'partial', detail + ' missing_PR_components_require_partial')
        pr_split(ticket, snapshots, report)
        if not available or not snapshots:
            report.require(ticket['review_after_bot'] == '', detail + ' metric=review_after_bot expected=blank')
    report.equal(None if unavailable_named else Decimal(empty), run.value('', 'no_pr_tickets'),
                 'PR_MISSINGNESS_FAIL file=run.csv metric=no_pr_tickets')


def pr_split(ticket, snapshots, report):
    rank = {'author_time_estimate': 0, 'suspect': 1, 'unavailable': 2}
    statuses = [p['fix_split_status'] for p in snapshots]
    detail = f'PR_MISSINGNESS_FAIL file=tickets.csv ticket={ticket["ticket"]!r}'
    if any(s not in rank for s in statuses):
        raise EvidenceError(detail + f' invalid_split_status={statuses}')
    expected = max(statuses, key=rank.get, default='unavailable')
    report.require(ticket['fix_split_status'] == expected,
                   detail + f' metric=fix_split_status expected={expected} actual={ticket["fix_split_status"]}')
    lines = [total(number(p[field], 'run.csv pr_' + field) for p in snapshots) for field in
             ('initial_additions', 'initial_deletions', 'fix_additions', 'fix_deletions')]
    usable = snapshots and all(p['churn_ratio'] for p in snapshots) and None not in lines and sum(lines[:2]) > 0
    ratio = sum(lines[2:]) / sum(lines[:2]) if usable else None
    report.equal(ratio, number(ticket['churn_ratio'], 'tickets.csv churn_ratio'),
                 detail + ' metric=churn_ratio', Decimal('0.000001'))


def native(run, report):
    for ticket in run.rows['tickets']:
        name = ticket['ticket']
        stages = total(number(s['native_review_passes'], 'stages.csv native_review_passes') for s in run.stages[name])
        report.equal(stages, number(ticket['native_review_passes'], 'tickets.csv native_review_passes'),
                     f'NATIVE_REVIEW_FAIL ticket={name!r} stage_ticket_agreement')
        report.equal(stages, run.value(name, 'native_review_usage_missing'),
                     f'NATIVE_REVIEW_FAIL ticket={name!r} metric=native_review_usage_missing')
    raw = sum(r['metric'] == 'marker_native_review' and run.start <= timestamp(r['value']) < run.end
              for r in run.rows['run'])
    print(f'NATIVE_REVIEW raw_window_markers={raw} (grouped invocations may differ)')
