"""Small written evidence and deliberately corrupted copies, without collection."""
from contextlib import redirect_stdout
import copy
import csv
import io
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest
from unittest.mock import patch

from stats.ticket_flow import check, checks, csvio
from stats.ticket_flow.model import ACTORS, TOKENS
from stats.ticket_flow.table_common import MEASURES, PR_SUMS


def evidence():
    stage = dict(ticket='IGR-15', stage='design', review_pass='', cycle='', coverage='complete',
                 **dict.fromkeys(MEASURES, 0))
    calls = []
    for i, actor in enumerate(('claude_main', 'codex')):
        call = dict.fromkeys(csvio.SCHEMAS['calls'], '')
        call.update(provider='claude' if i == 0 else 'codex', id=str(i), ticket='IGR-15',
                    timestamp='2026-10-17T12:00:00+00:00', actor=actor, stage='design',
                    repo='ig-ra/jigs', activity='code reading', **dict.fromkeys(TOKENS, 10))
        calls.append(call)
        for token in TOKENS:
            stage[actor + '_' + token] = 10
    stage.update(claude_main_minutes_raw=1, codex_minutes_raw=2, calls=2, turns=2)
    ticket = dict.fromkeys(csvio.SCHEMAS['tickets'], 0)
    ticket.update({k: v for k, v in stage.items() if k in ticket})
    ticket.update(prs=0, churn_ratio='', fix_split_status='unavailable', review_after_bot='')
    facts = [dict(metric='window_start', value='2026-10-17T00:00:00+00:00'),
             dict(metric='window_end_exclusive', value='2026-10-18T00:00:00+00:00'),
             dict(metric='no_pr_tickets', value=1)]
    for metric, value in dict(claude_duration_records=1, codex_completed_pairs=1,
                              pr_lookup_available=1, prs_found=0, native_review_usage_missing=0).items():
        facts.append(dict(ticket='IGR-15', metric=metric, value=value))
    for actor in ACTORS:
        for metric in ('unknown_minutes_pct', 'ambiguous_minutes_pct', 'unknown_tokens_pct', 'ambiguous_tokens_pct'):
            denominator = (1 if actor == 'claude_main' else 2) if 'minutes' in metric else 40
            if actor == 'claude_subagents':
                denominator = ''
            facts.append(dict(ticket='IGR-15', actor=actor, metric=metric,
                              numerator=0 if denominator else '', denominator=denominator,
                              value=0 if denominator else ''))
    return dict(calls=calls, stages=[stage], tickets=[ticket], run=facts)


class CheckTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name) / 'run'
        self.data = evidence()

    def invoke(self, *args):
        csvio.publish(self.directory, self.data)
        output = io.StringIO()
        with redirect_stdout(output):
            status = check.main([str(self.directory), *args])
        return status, output.getvalue()

    def fact(self, metric, actor=''):
        return next(r for r in self.data['run'] if r['metric'] == metric and r.get('actor', '') == actor)

    def fails(self, message, *args):
        status, output = self.invoke(*args)
        self.assertEqual(status, 1, output)
        self.assertIn(message, output)
        self.assertIn('OUTPUT_CHECK_FAIL', output)
        self.assertNotIn('Traceback', output)

    def test_good_run_is_offline_and_imports_have_no_collection(self):
        with patch('stats.ticket_flow.local.collect', side_effect=AssertionError('logs')), \
             patch('stats.ticket_flow.github_fetch.request', side_effect=AssertionError('network')):
            status, output = self.invoke()
        self.assertEqual(status, 0, output)
        for family in ('IDENTITY', 'CONSERVATION', 'ACTIVITY', 'PR_MISSINGNESS', 'NATIVE'):
            self.assertIn(family + '_PASS', output)
        self.assertIn('OUTPUT_CHECK_PASS checks=', output)
        self.assertIn('RECORDED_SHARE', output)

    def test_module_cli_missing_evidence_has_no_traceback(self):
        self.data['calls'][0]['activity'] = ''
        self.invoke()
        result = subprocess.run([sys.executable, '-B', '-m', 'stats.ticket_flow.check', str(self.directory)],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('missing_activity_or_tokens', result.stdout)
        self.assertIn('OUTPUT_CHECK_FAIL', result.stdout)
        self.assertNotIn('Traceback', result.stderr)

    def test_duplicate_call_ticket_and_stage_keys(self):
        for name in ('calls', 'tickets', 'stages'):
            with self.subTest(name=name):
                self.data = evidence()
                self.data[name].append(copy.deepcopy(self.data[name][0]))
                self.fails('duplicate_key=')

    def test_empty_identity_invalid_actor_window_and_moved_call(self):
        for field, value, message in (
            ('id', '', 'empty_identity'), ('actor', 'claude_child', 'invalid_actor'),
            ('provider', 'other', 'invalid_actor'), ('timestamp', '2026-10-18T00:00:00+00:00', 'outside_window'),
            ('stage', 'fix', 'missing_stage='), ('ticket', 'IGR-99', 'missing_stage=')):
            with self.subTest(field=field):
                self.data = evidence()
                self.data['calls'][0][field] = value
                self.fails(message)

    def test_lost_call_and_each_independent_bucket(self):
        for token in TOKENS:
            with self.subTest(token=token):
                self.data = evidence()
                self.data['calls'][0][token] = 11
                self.fails('metric=claude_main_' + token)
        self.data = evidence()
        self.data['calls'].pop()
        self.fails('TOKEN_CONSERVATION_FAIL')

    def test_missing_bucket_propagates_but_is_not_an_activity_pass(self):
        self.data['calls'][0][TOKENS[0]] = ''
        self.fails('TOKEN_CONSERVATION_FAIL')
        self.data['stages'][0]['claude_main_' + TOKENS[0]] = ''
        self.data['tickets'][0]['claude_main_' + TOKENS[0]] = ''
        status, output = self.invoke()
        self.assertEqual(status, 1)
        self.assertIn('CONSERVATION_PASS', output)
        self.assertIn('missing_activity_or_tokens', output)

    def test_ticket_and_overall_conservation(self):
        self.data['tickets'][0]['codex_output_tokens'] = 11
        self.fails('file=tickets.csv')

    def test_minutes_serialization_allowance_and_denominators(self):
        self.data['stages'][0]['codex_minutes_raw'] = '2.000002'
        self.assertEqual(self.invoke()[0], 0)
        self.data['stages'][0]['codex_minutes_raw'] = '2.000004'
        self.fails('tolerance=0.000003')
        for value in ('', 3):
            self.data = evidence()
            self.fact('unknown_minutes_pct', 'codex')['denominator'] = value
            self.fails('denominator_agreement')

    def test_missing_duration_and_zero_completed_duration(self):
        self.data['run'].remove(self.fact('unknown_minutes_pct', 'codex'))
        self.fails('missing_evidence')
        self.data = evidence()
        self.fact('codex_completed_pairs')['value'] = 0
        for metric in ('unknown_minutes_pct', 'ambiguous_minutes_pct'):
            self.fact(metric, 'codex').update(denominator='', numerator='', value='')
        self.data['stages'][0]['codex_minutes_raw'] = 0
        self.data['tickets'][0]['codex_minutes_raw'] = 0
        self.assertEqual(self.invoke()[0], 0)

    def test_orphan_population_and_extra_run_ticket(self):
        self.data['run'].append(dict(ticket='IGR-99', metric='calls', value=0))
        self.fails('extra_ticket=IGR-99')
        self.data = evidence()
        self.data['calls'] = []
        self.fact('claude_duration_records')['value'] = 0
        self.fact('codex_completed_pairs')['value'] = 0
        self.fails('missing_local_window_evidence')

    def test_marker_and_estimate_only_population_and_blank_ticket(self):
        for fact in (dict(metric='marker_design', value='2026-10-17T01:00:00+00:00', source='local:1'),
                     dict(metric='estimate_identity', value='dispatch-1', source='estimates:1')):
            self.data = evidence()
            self.data['calls'] = []
            self.fact('claude_duration_records')['value'] = 0
            self.fact('codex_completed_pairs')['value'] = 0
            self.data['run'].append(dict(ticket='IGR-15', **fact))
            self.invoke()
            with redirect_stdout(io.StringIO()):
                report = check.Report()
                checks.identity(check.Run(self.directory), report)
            self.assertEqual(report.failures, 0)
        self.data = evidence()
        for rows in self.data.values():
            for row in rows:
                if row.get('ticket') == 'IGR-15':
                    row['ticket'] = ''
        self.fact('no_pr_tickets')['value'] = 0
        self.assertEqual(self.invoke()[0], 0)

    def test_activity_mix_is_diagnostic_unless_target_requested(self):
        self.data['calls'][0]['activity'] = 'other'
        status, output = self.invoke()
        self.assertEqual(status, 0, output)
        self.assertIn('ACTIVITY_SHARE overall other_tokens=40 all_tokens=80 pct=50.000000000', output)
        self.assertIn('ACTIVITY_TARGET_NOT_REQUESTED', output)
        self.assertNotIn('ACTIVITY_TARGET_PASS', output)
        self.fails('ACTIVITY_TARGET_FAIL', '--activity-target')
        self.data['tickets'][0]['codex_output_tokens'] = 11
        self.fails('TOKEN_CONSERVATION_FAIL')
        self.fails('TOKEN_CONSERVATION_FAIL', '--activity-target')

    def test_activity_target_cli_pass_names_numbers(self):
        self.invoke()
        result = subprocess.run([sys.executable, '-B', '-m', 'stats.ticket_flow.check',
                                 str(self.directory), '--activity-target'],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('ACTIVITY_TARGET_PASS other_tokens=0 all_tokens=80 pct=0.000000000 target_pct<5', result.stdout)
        self.assertIn('OUTPUT_CHECK_PASS', result.stdout)

    def test_activity_strict_boundary_missing_label_and_zero_denominator(self):
        for amount, expected in ((19, 0), (20, 1)):
            self.data = evidence()
            for call in self.data['calls']:
                call.update(**dict.fromkeys(TOKENS, 0))
            self.data['calls'][0].update(activity='other', output_tokens=amount)
            self.data['calls'][1]['output_tokens'] = 380
            self.invoke()
            with redirect_stdout(io.StringIO()):
                report = check.Report()
                checks.activity(check.Run(self.directory), report, enforce_target=True)
            self.assertEqual(report.failures, expected)
        self.data = evidence()
        self.data['calls'][0]['activity'] = ''
        self.fails('missing_activity_or_tokens')
        self.fails('missing_activity_or_tokens', '--activity-target')
        self.data = evidence()
        for call in self.data['calls']:
            call.update(**dict.fromkeys(TOKENS, 0))
        for row in (self.data['stages'][0], self.data['tickets'][0]):
            row.update({f'{actor}_{token}': 0 for actor in ACTORS for token in TOKENS})
        status, output = self.invoke()
        self.assertEqual(status, 0, output)
        self.assertIn('ACTIVITY_SHARE overall other_tokens=0 all_tokens=0 pct=unavailable', output)
        self.fails('ACTIVITY_TARGET_FAIL', '--activity-target')

    def test_native_grouped_counts_are_not_raw_markers(self):
        for i in range(2):
            self.data['run'].append(dict(ticket='IGR-15', metric='marker_native_review',
                                         source=f'local:{i}', value='2026-10-17T12:00:00+00:00'))
        self.data['stages'][0]['native_review_passes'] = 1
        self.data['tickets'][0]['native_review_passes'] = 1
        self.fact('native_review_usage_missing')['value'] = 1
        self.assertEqual(self.invoke()[0], 0)
        self.fact('native_review_usage_missing')['value'] = 2
        self.fails('NATIVE_REVIEW_FAIL')

    def test_missing_file_column_fact_malformed_numeric_and_window(self):
        for value in ('NaN', 'Infinity', '-1', '1.5', 'bad'):
            self.data = evidence()
            self.data['calls'][0]['output_tokens'] = value
            self.fails('invalid_number=')
        self.data = evidence()
        self.data['run'].remove(self.fact('pr_lookup_available'))
        self.fails('missing_evidence')
        self.data = evidence()
        self.fact('window_start')['value'] = '2026-10-18T00:00:00+00:00'
        self.fails('invalid_window')
        self.data = evidence()
        self.invoke()
        (self.directory / 'calls.csv').write_text('id\n1\n')
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(check.main([str(self.directory)]), 1)
        self.assertIn('missing_columns=', output.getvalue())
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(check.main([str(self.directory / 'absent')]), 1)
        self.assertIn('missing_evidence', output.getvalue())
