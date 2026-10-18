"""Deliberate host integration tests. Discovery does no authentication or log reads."""
from collections import Counter
from contextlib import contextmanager
import csv
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from stats.ticket_flow import github, github_fetch
from stats.ticket_flow.sources import stamp

ROOT = Path(__file__).resolve().parents[2]
REPO, PR, TICKET = 'ig-ra/jigs', 3, 'IGR-15'


@contextmanager
def counted_requests(counts):
    """Count actual GET pages from gh diagnostics; never print headers/credentials."""
    original = subprocess.run

    def run(args, **kwargs):
        if args[:len(github_fetch.PREFIX)] != github_fetch.PREFIX:
            return original(args, **kwargs)
        counts['gh_commands'] += 1
        environment = dict(os.environ, GH_DEBUG='api')
        result = original(args, **dict(kwargs, env=environment))
        counts['get_pages'] += len(re.findall(r'^> GET ', result.stderr, re.MULTILINE))
        return result

    with patch.object(github_fetch.subprocess, 'run', side_effect=run):
        yield


@unittest.skipUnless(os.environ.get('TICKET_FLOW_LIVE') == '1', 'set TICKET_FLOW_LIVE=1 outside sandbox')
class LiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.started = time.monotonic()
        cls.counts = Counter()
        cls.addClassCleanup(cls.report)
        with counted_requests(cls.counts):
            github_fetch.authenticate()
            cls.data = github_fetch.snapshot(REPO, PR, github_fetch.request)

    @classmethod
    def report(cls):
        print(f'LIVE_DIRECT_REQUESTS gh_commands={cls.counts["gh_commands"]} '
              f'get_pages={cls.counts["get_pages"]} suite_elapsed_s={time.monotonic()-cls.started:.3f}', flush=True)

    def pages(self, endpoint, limit=1000):
        result, pages = [], 0
        for page in range(1, limit + 1):
            rows = github_fetch.request(endpoint + f'&page={page}')
            self.assertIsInstance(rows, list)
            if not rows:
                return result, pages
            pages += 1
            result.extend(rows)
        self.fail(f'pagination guard exhausted endpoint={endpoint} limit={limit}')

    def test_01_keyring_complete_snapshot_and_ticket_join(self):
        data, pr = self.data, self.data['pr']
        self.assertEqual(pr['number'], PR)
        self.assertTrue(pr['head']['sha'])
        self.assertTrue(github.matches(TICKET, pr['head']['ref']))
        self.assertIsNotNone(stamp(pr['created_at']))
        if pr.get('merged_at'):
            self.assertGreaterEqual(stamp(pr['merged_at']), stamp(pr['created_at']))
        for field in ('changed_files', 'additions', 'deletions', 'commits'):
            self.assertIsInstance(pr[field], int)
            self.assertGreaterEqual(pr[field], 0)
        shas = [c['sha'] for c in data['commits']]
        self.assertEqual(len(shas), len(set(shas)))
        self.assertEqual(len(shas), pr['commits'])
        for commit in data['commits']:
            self.assertIsNotNone(stamp(commit['commit']['author']['date']))
            self.assertIsNotNone(stamp(commit['commit']['committer']['date']))
            for field in ('additions', 'deletions', 'total'):
                self.assertIsInstance(commit['stats'][field], int)
        with counted_requests(self.counts):
            for surface, endpoint in (
                ('reviews', f'repos/{REPO}/pulls/{PR}/reviews'),
                ('comments', f'repos/{REPO}/pulls/{PR}/comments'),
                ('issues', f'repos/{REPO}/issues/{PR}/comments')):
                independent, pages = self.pages(endpoint + '?per_page=100')
                ids = [r['id'] for r in data[surface]]
                self.assertEqual(len(ids), len(set(ids)))
                self.assertEqual(set(ids), {r['id'] for r in independent})
                print(f'LIVE_SURFACE {surface} nonempty_pages={pages} records={len(ids)}', flush=True)
        fact = github.interpret(TICKET, REPO, data)
        for field, expected in dict(ticket=TICKET, repo=REPO, pr=PR, head_ref=pr['head']['ref'],
                                    head_sha=pr['head']['sha']).items():
            self.assertEqual(fact[field], expected)
        markers = github.markers_for(fact, data)
        self.assertTrue(markers)
        self.assertTrue(all(m.ticket == TICKET and m.repo == REPO and
                            m.source.startswith(f'github:{REPO}#{PR}:') for m in markers))

    def test_02_real_multiple_page_commits(self):
        endpoint = f'repos/{REPO}/pulls/{PR}/commits?per_page=1'
        with counted_requests(self.counts):
            paginated = github_fetch.request(endpoint, '.', True)
            independent, pages = self.pages(endpoint)
        self.assertGreaterEqual(pages, 2, 'known PR must exercise multiple nonempty pages')
        shas = [c['sha'] for c in paginated]
        self.assertEqual(shas, [c['sha'] for c in independent])
        self.assertEqual(len(shas), len(set(shas)))
        self.assertEqual(set(shas), {c['sha'] for c in self.data['commits']})
        self.assertEqual(len(shas), self.data['pr']['commits'])
        self.assertGreater(self.counts['get_pages'], 0, 'gh GET-page diagnostics unavailable')
        print(f'LIVE_PAGINATION nonempty_pages={pages} commits={len(shas)}', flush=True)

    def test_03_real_one_day_command_and_output_check(self):
        for relative in ('.claude/projects', '.codex/sessions'):
            self.assertTrue((Path.home() / relative).is_dir(), f'prerequisite: real ~/{relative} required')
        self.assertTrue((Path.home() / '.claude/agent-estimates.tsv').is_file(), 'prerequisite: real estimate TSV required')
        environment = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE='1')
        started = time.monotonic()
        with tempfile.TemporaryDirectory(prefix='ticket-flow-live-') as directory:
            result = subprocess.run([sys.executable, '-B', '-m', 'stats.ticket_flow', '2026-10-17', '2026-10-18'],
                cwd=directory, env=environment, capture_output=True, text=True, timeout=3600)
            print(f'LIVE_COMMAND elapsed_s={time.monotonic()-started:.3f} returncode={result.returncode} '
                  'request_count=unmeasured_child_command', flush=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('TICKET_FLOW_OUTPUT_WRITTEN', result.stdout)
            run = Path(directory) / 'stats/runs/2026-10-17_2026-10-18'
            for name in ('calls', 'stages', 'tickets', 'run'):
                self.assertTrue((run / (name + '.csv')).is_file())
            with (run / 'calls.csv').open(newline='') as stream:
                calls = list(csv.DictReader(stream))
            self.assertTrue(calls)
            self.assertTrue({TICKET, 'IGR-16'} <= {c['ticket'] for c in calls})
            with (run / 'tickets.csv').open(newline='') as stream:
                tickets = {r['ticket']: r for r in csv.DictReader(stream)}
            for ticket in (TICKET, 'IGR-16'):
                for field in ('claude_main_minutes_raw', 'codex_minutes_raw'):
                    self.assertGreater(float(tickets[ticket][field]), 0, f'{ticket} {field}')
            result = subprocess.run([sys.executable, '-B', '-m', 'stats.ticket_flow.check', str(run)],
                cwd=directory, env=environment, capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('OUTPUT_CHECK_PASS', result.stdout)
            self.assertIn('ACTIVITY_TARGET_NOT_REQUESTED', result.stdout)
            for line in result.stdout.splitlines():
                if line.startswith(('ACTIVITY_SHARE overall ', 'ACTIVITY_TARGET_')):
                    print(line, flush=True)
            print(result.stdout.splitlines()[-1], flush=True)
