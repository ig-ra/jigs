"""Offline validation of one written ticket-flow run, including its ignored audit."""
import argparse
from collections import defaultdict
import csv
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
import sys

from .csvio import SCHEMAS
from .model import TOKENS
from .table_common import ESTIMATES, MEASURES, PR_SUMS


class EvidenceError(ValueError):
    """Required serialized evidence is absent or malformed."""


def number(value, where, integer=False):
    if value == '':
        return None
    try:
        result = Decimal(value)
    except InvalidOperation:
        raise EvidenceError(f'{where} invalid_number={value!r}') from None
    if not result.is_finite() or result < 0 or integer and result != result.to_integral_value():
        raise EvidenceError(f'{where} invalid_number={value!r}')
    return result


def timestamp(value):
    try:
        result = datetime.fromisoformat(value)
        if result.tzinfo is None or result.utcoffset().total_seconds() != 0:
            raise ValueError()
        return result.astimezone(timezone.utc)
    except ValueError:
        raise EvidenceError(f'run/calls timestamp invalid_utc={value!r}') from None


def total(values):
    values = list(values)
    return None if None in values else sum(values, Decimal(0))


def key(row):
    return tuple(row[f] for f in ('ticket', 'stage', 'review_pass', 'cycle'))


class Run:
    def __init__(self, directory):
        self.rows = {}
        for name, fields in SCHEMAS.items():
            path = Path(directory) / f'{name}.csv'
            with path.open(encoding='utf-8', newline='') as stream:
                reader = csv.DictReader(stream)
                missing = set(fields) - set(reader.fieldnames or ())
                if missing:
                    raise EvidenceError(f'file={path.name} missing_columns={",".join(sorted(missing))}')
                self.rows[name] = list(reader)
            for i, row in enumerate(self.rows[name], 2):
                if None in row or None in row.values():
                    raise EvidenceError(f'file={path.name} row={i} malformed_csv')
        self.validate_numbers()
        self.stages, self.calls, self.facts, self.prs = (defaultdict(list) for _ in range(4))
        for row in self.rows['stages']:
            self.stages[row['ticket']].append(row)
        for row in self.rows['calls']:
            self.calls[key(row)].append(row)
        for row in self.rows['run']:
            self.facts[row['ticket'], row['actor'], row['metric']].append(row)
            if row['pr']:
                self.prs[row['ticket'], row['repo'], row['pr']].append(row)
        self.start = timestamp(self.fact('', '', 'window_start')['value'])
        self.end = timestamp(self.fact('', '', 'window_end_exclusive')['value'])
        if self.start >= self.end:
            raise EvidenceError('file=run.csv invalid_window START>=END')

    def validate_numbers(self):
        for name, rows in self.rows.items():
            for i, row in enumerate(rows, 2):
                fields = ()
                if name == 'calls':
                    fields = (*TOKENS, 'review_pass', 'cycle')
                elif name in ('stages', 'tickets'):
                    fields = ('review_pass', 'cycle') + MEASURES if name == 'stages' else MEASURES
                    fields += (ESTIMATES + ('prs', *PR_SUMS, 'churn_ratio', 'review_after_bot')
                                         if name == 'tickets' else ())
                for field in fields:
                    integer = not any(s in field for s in ('minutes', '_min', 'ratio'))
                    number(row[field], f'file={name}.csv row={i} metric={field}', integer)
                if name == 'run':
                    metric = row['metric']
                    numeric = not (metric.startswith('marker_') or metric.startswith('window_') or
                        metric in ('pr_head_ref', 'pr_head_sha', 'pr_created', 'pr_merged',
                                   'pr_first_review', 'pr_first_bot', 'pr_fix_split_status', 'estimate_identity'))
                    if numeric:
                        number(row['value'], f'file=run.csv row={i} metric={metric}',
                               not any(s in metric for s in ('minutes', 'pct', 'ratio')))
                    for field in ('numerator', 'denominator'):
                        number(row[field], f'file=run.csv row={i} metric={metric}.{field}')

    def fact(self, ticket, actor, metric):
        rows = self.facts[ticket, actor, metric]
        if len(rows) != 1:
            raise EvidenceError(f'file=run.csv ticket={ticket!r} actor={actor} metric={metric} '
                                f'missing_evidence_or_duplicate expected=1 actual={len(rows)}')
        return rows[0]

    def value(self, ticket, metric, actor=''):
        return number(self.fact(ticket, actor, metric)['value'], f'run.csv {ticket} {metric}')


class Report:
    def __init__(self):
        self.checks = self.failures = 0

    def require(self, condition, detail):
        self.checks += 1
        if not condition:
            self.failures += 1
            print(detail)

    def equal(self, expected, actual, detail, tolerance=Decimal(0)):
        valid = expected == actual if expected is None or actual is None else abs(expected - actual) <= tolerance
        self.require(valid, f'{detail} expected={expected} actual={actual} tolerance={tolerance}')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('RUN_DIR')
    parser.add_argument('--activity-target', action='store_true',
                        help='require overall other tokens <5%%; use for published-run acceptance')
    args = parser.parse_args(argv)
    report = Report()
    try:
        run = Run(args.RUN_DIR)
        from . import checks
        for family in (checks.identity, checks.conservation, checks.activity, checks.pr_missingness, checks.native):
            before = report.failures
            try:
                if family is checks.activity:
                    family(run, report, enforce_target=args.activity_target)
                else:
                    family(run, report)
            except ValueError as error:
                report.require(False, f'{family.__name__.upper()}_FAIL missing_evidence {error}')
            if report.failures == before:
                print(f'{family.__name__.upper()}_PASS')
        for row in run.rows['run']:
            if row['metric'] in ('unknown_tokens_pct', 'ambiguous_tokens_pct',
                                  'unknown_minutes_pct', 'ambiguous_minutes_pct'):
                print('RECORDED_SHARE ' + ' '.join(f'{k}={row[k] or "blank"}' for k in
                      ('ticket', 'actor', 'metric', 'numerator', 'denominator', 'value')))
    except (OSError, csv.Error, EvidenceError) as error:
        report.require(False, f'INPUT_FAIL missing_evidence_or_invalid_input {error}')
    print(f'OUTPUT_CHECK_FAIL failures={report.failures}' if report.failures else
          f'OUTPUT_CHECK_PASS checks={report.checks}')
    return int(bool(report.failures))


if __name__ == '__main__':
    sys.exit(main())
