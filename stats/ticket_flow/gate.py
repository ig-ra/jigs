"""Numeric pilot checks; hand-bin explanations remain a one-time report."""
from collections import Counter
from decimal import Decimal, ROUND_HALF_UP
from math import fsum, isclose

from .model import ACTORS, PILOT, TOKENS
from .sources import stamp
from .tables import in_window


def numeric_checks(rows, turns, tables, start, end):
    lines, failures = [], []
    expected = {('IGR-15', 'claude_main'): 63, ('IGR-16', 'claude_main'): 27,
                ('IGR-15', 'codex'): 105, ('IGR-16', 'codex'): 32}
    canonical = [r for r in rows if r['type'] == 'call' and in_window(stamp(r['timestamp']), start, end)]
    identities = Counter((c['provider'], c['id']) for c in tables['calls'])
    correct = identities == Counter((c['provider'], c['id']) for c in canonical)
    lines.append(f'CALL_ID_CONSERVATION {"PASS" if correct else "FAIL"} calls={len(canonical)} audit={sum(identities.values())}')
    if not correct:
        failures.append(lines[-1])
    for ticket in PILOT:
        stages = [r for r in tables['stages'] if r['ticket'] == ticket]
        tickets = [r for r in tables['tickets'] if r['ticket'] == ticket]
        summary = tickets[0] if tickets else {}
        for actor in ACTORS:
            selected = [c for c in canonical if c['ticket'] == ticket and (
                'codex' if c['provider'] == 'codex' else
                'claude_subagents' if c.get('parent_session_id') else 'claude_main') == actor]
            for token in TOKENS:
                metric = f'{actor}_{token}'
                values = [sum(c.get(token) or 0 for c in selected),
                          sum(r[metric] or 0 for r in stages), summary.get(metric)]
                if values[0] != values[1] or values[1] != values[2]:
                    failures.append(f'TOKEN_CONSERVATION FAIL {ticket} {metric} {values}')
            if (ticket, actor) not in expected:
                continue
            metric = actor + '_minutes_raw'
            raw = fsum(t.minutes for t in turns if t.ticket == ticket and t.actor == actor and
                       t.minutes is not None and in_window(t.end, start, end))
            conserved = all(isclose(raw, value, abs_tol=1e-8) for value in (
                fsum(r[metric] for r in stages), summary.get(metric, -1)))
            rounded = int(Decimal(str(raw)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
            good = conserved and rounded == expected[ticket, actor]
            line = f'RAW_MINUTES {"PASS" if good else "FAIL"} {ticket} {actor} raw={raw:.6f} rounded={rounded} expected={expected[ticket, actor]} conserved={conserved}'
            lines.append(line)
            if not good:
                failures.append(line)
    for row in tables['run']:
        if row['metric'] in ('unknown_tokens_pct', 'unknown_minutes_pct') and row.get('value') is not None and row['value'] > 5:
            failures.append(f'UNKNOWN_SHARE FAIL {row["ticket"]} {row["actor"]} {row["metric"]}={row["value"]:.6f}%')
    lines += failures
    lines.append(f'NUMERIC_GATE {"FAIL" if failures else "PASS"} failures={len(failures)}; hand reconciliation requires report')
    return lines, failures
