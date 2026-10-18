"""Exercise the command with native files and API responses; no live inputs."""
from contextlib import chdir, redirect_stderr, redirect_stdout
import csv
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from stats.ticket_flow import __main__ as cli, github_fetch, sources
from stats.ticket_flow.model import ACTORS, TOKENS
from support import dump

FIXTURE = Path(__file__).parent / 'fixtures/pipeline.json'


class PipelineTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.home = self.root / 'home'
        self.fixture = json.loads(FIXTURE.read_text().replace('{home}', str(self.home)))
        (self.home / '.claude/projects').mkdir(parents=True)
        (self.home / '.codex/sessions').mkdir(parents=True)
        for name, records in self.fixture['files'].items():
            if name == 'codex.jsonl':
                path = self.home / '.codex/sessions' / name
            else:
                cwd = records[0]['cwd'].split('/.worktrees/')[0]
                path = self.home / '.claude/projects' / cwd.replace('/', '-') / name
            dump(path, records)
        (self.home / '.claude/agent-estimates.tsv').write_text(self.fixture['estimates'])
        self.auth = Mock()
        self.requests = []
        self.collect = github_fetch.collect

    def fetch(self, endpoint, projection='.', paginate=False):
        self.auth.assert_called_once_with()
        self.requests.append(endpoint)
        return self.fixture['api'][endpoint]

    def command(self, start='2026-10-17', end='2026-10-18', fetch=None):
        output, errors = io.StringIO(), io.StringIO()
        self.auth.reset_mock()
        with chdir(self.root), patch.object(Path, 'home', return_value=self.home):
            with patch.object(cli.github_fetch, 'collect', side_effect=lambda tickets:
                    self.collect(tickets, fetch=fetch or self.fetch, auth=self.auth)):
                with redirect_stdout(output), redirect_stderr(errors):
                    status = cli.main([start, end])
        return status, output.getvalue(), errors.getvalue()

    def directory(self, window='2026-10-17_2026-10-18'):
        return self.root / 'stats/runs' / window

    def contents(self, directory=None):
        return {p.name: p.read_bytes() for p in (directory or self.directory()).iterdir()}

    def rows(self, name):
        with (self.directory() / (name + '.csv')).open(newline='') as stream:
            return list(csv.DictReader(stream))

    def test_complete_command_conservation_missingness_order_and_identical_bytes(self):
        self.assertEqual(self.command()[0], 0)
        before = self.contents()
        self.assertEqual(set(before), {name + '.csv' for name in cli.csvio.SCHEMAS})
        self.assertEqual(set(self.requests), set(self.fixture['api']))
        self.assertFalse(any('/88' in endpoint for endpoint in self.requests))
        self.assertFalse(any(r['ticket'] == 'IGR-88' for r in self.rows('run')))
        audit, stages, tickets = self.rows('calls'), self.rows('stages'), self.rows('tickets')
        self.assertEqual({r['id'] for r in audit}, {'main', 'child', 'curator', 'response'})
        self.assertEqual({r['repo'] for r in audit}, {'ig-ra/jigs', 'Sawmills/condition-curator'})
        self.assertEqual({r['actor'] for r in audit}, set(ACTORS))
        self.assertEqual({r['ticket'] for r in tickets}, {'IGR-15', 'SAW-100'})
        self.assert_conservation(audit, stages, tickets)
        main = next(r for r in audit if r['id'] == 'main')
        codex = next(r for r in audit if r['id'] == 'response')
        self.assertEqual(main['stage'], 'design')  # Pre-window start marker retained.
        self.assertEqual(codex['stage'], 'implement')
        by_ticket = {r['ticket']: r for r in tickets}
        self.assertEqual(by_ticket['IGR-15']['bot_reviews'], '1')
        self.assertEqual(by_ticket['IGR-15']['bot_comments'], '0')
        self.assertEqual(by_ticket['IGR-15']['review_after_bot'], '0')
        self.assertEqual(by_ticket['IGR-15']['completed_dispatch_minutes'], '')
        self.assertEqual(by_ticket['IGR-15']['fix_commits'], '0')
        self.assertEqual(by_ticket['IGR-15']['churn_ratio'], '0.000000')
        self.assertEqual(by_ticket['SAW-100']['prs'], '0')
        self.assertEqual(by_ticket['SAW-100']['review_after_bot'], '')
        self.assertEqual(by_ticket['SAW-100']['claude_main_minutes_raw'], '1.000000')
        provenance = self.rows('run')
        self.assertTrue(any(r['repo'] == 'ig-ra/jigs' and r['pr'] == '7' for r in provenance))
        self.assertTrue(any(r['metric'] == 'marker_design' and
                            r['repo'] == 'Sawmills/agent-platform' for r in provenance))
        for name, fields in cli.csvio.SCHEMAS.items():
            ordered = [tuple(r[f] for f in fields) for r in self.rows(name)]
            self.assertEqual(ordered, sorted(ordered))
        self.assertEqual(self.command()[0], 0)
        self.assertEqual(self.contents(), before)

    def assert_conservation(self, audit, stages, tickets):
        expected_tokens = {'claude_main': [20, 40, 6, 10],
                           'claude_subagents': [10, 20, 3, 5], 'codex': [100, 100, 0, 20]}
        for actor, expected in expected_tokens.items():
            for token, value in zip(TOKENS, expected):
                column = actor + '_' + token
                self.assertEqual(sum(int(r[token]) for r in audit if r['actor'] == actor), value)
                self.assertEqual(sum(int(r[column]) for r in stages), value)
                self.assertEqual(sum(int(r[column]) for r in tickets), value)
        for actor, expected in (('claude_main', 2.5), ('codex', 1.0)):
            column = actor + '_minutes_raw'
            self.assertAlmostEqual(sum(float(r[column]) for r in stages), expected, places=6)
            self.assertAlmostEqual(sum(float(r[column]) for r in tickets), expected, places=6)
        for ticket in ('IGR-15', 'SAW-100'):
            groups = [r for r in stages if r['ticket'] == ticket]
            total = next(r for r in tickets if r['ticket'] == ticket)
            for actor in ACTORS:
                for token in TOKENS:
                    column = actor + '_' + token
                    self.assertEqual(sum(int(r[column]) for r in groups), int(total[column]))
            for column in ('claude_main_minutes_raw', 'codex_minutes_raw'):
                self.assertAlmostEqual(sum(float(r[column]) for r in groups), float(total[column]), places=6)

    def test_empty_window_has_summary_headers_and_no_fabricated_work(self):
        self.assertEqual(self.command('2026-10-15', '2026-10-16')[0], 0)
        directory = self.directory('2026-10-15_2026-10-16')
        for name in ('calls', 'stages', 'tickets'):
            self.assertEqual((directory / (name + '.csv')).read_text(),
                             ','.join(cli.csvio.SCHEMAS[name]) + '\n')
        with (directory / 'run.csv').open() as stream:
            metrics = list(csv.DictReader(stream))
        self.assertTrue(any(r['metric'] == 'source_files' and r['value'] == '0' for r in metrics))

    def test_past_window_has_no_historical_ticket_rows_or_requests(self):
        self.assertEqual(self.command('2026-10-19', '2026-10-20')[0], 0)
        directory = self.directory('2026-10-19_2026-10-20')
        counts = {}
        for path in directory.glob('*.csv'):
            with path.open() as stream:
                rows = list(csv.DictReader(stream))
            counts[path.stem] = len(rows)
            self.assertFalse(any(r.get('ticket') for r in rows))
        self.assertEqual(counts, dict(calls=0, stages=0, tickets=0, run=14))
        self.assertEqual(self.requests, [])
        self.auth.assert_not_called()

    def test_marker_only_and_estimate_only_tickets_survive_without_guessed_repo(self):
        path = self.home / '.claude/projects' / str(
            self.home / 'my/dev-tools/jigs').replace('/', '-') / 'marker.jsonl'
        dump(path, [dict(type='user', cwd=str(self.home / 'my/dev-tools/jigs'),
            timestamp='2026-10-17T01:00:00Z', message={'content': '/igr:ticket start IGR-99'})])
        with (self.home / '.claude/agent-estimates.tsv').open('a') as stream:
            stream.write('only\t2026-10-17T02:00:00Z\tcodex\tSAW-999\timplement\t1\t1\t2\t\n')
        self.assertEqual(self.command()[0], 0)
        self.assertTrue({'IGR-99', 'SAW-999'} <= {r['ticket'] for r in self.rows('tickets')})
        self.assertTrue(any(r['ticket'] == 'IGR-99' and r['metric'] == 'marker_design'
                            for r in self.rows('run')))
        self.assertFalse(any('999' in endpoint for endpoint in self.requests))
        tickets = {r['ticket']: r for r in self.rows('tickets')}
        self.assertEqual(tickets['IGR-99']['prs'], '0')
        self.assertEqual(tickets['SAW-999']['coverage'], 'partial')
        for field in ('prs', 'pr_commits', 'bot_reviews', 'bot_comments', 'review_after_bot'):
            self.assertEqual(tickets['SAW-999'][field], '')
        metrics = {(r['ticket'], r['metric']): r['value'] for r in self.rows('run')}
        self.assertEqual(metrics['SAW-999', 'pr_lookup_available'], '0')
        self.assertEqual(metrics['SAW-999', 'prs_found'], '')
        self.assertEqual(metrics['IGR-99', 'pr_lookup_available'], '1')
        self.assertEqual(metrics['', 'no_pr_tickets'], '')

    def test_failed_fetch_preserves_previous_set_and_never_publishes_fresh_set(self):
        self.assertEqual(self.command()[0], 0)
        before = self.contents()
        def failing(endpoint, projection='.', paginate=False):
            if endpoint.endswith('/commits/initial'):
                raise subprocess.CalledProcessError(1, ['gh', 'api'])
            return self.fetch(endpoint, projection, paginate)
        status, output, errors = self.command(fetch=failing)
        self.assertEqual(status, 2)
        self.assertEqual(output, '')
        self.assertIn('ticket_flow:', errors)
        self.assertEqual(self.contents(), before)
        self.assertEqual(self.command('2026-10-16', '2026-10-18', fetch=failing)[0], 2)
        self.assertFalse(self.directory('2026-10-16_2026-10-18').exists())

    def test_missing_local_source_preserves_previous_set_before_github(self):
        self.assertEqual(self.command()[0], 0)
        before = self.contents()
        with patch.object(sources, 'local_files', side_effect=FileNotFoundError('log root unavailable')):
            self.assertEqual(self.command()[0], 2)
        self.auth.assert_not_called()
        self.assertEqual(self.contents(), before)
