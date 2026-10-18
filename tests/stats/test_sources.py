from collections import Counter
from pathlib import Path
import tempfile
import unittest

from stats.ticket_flow import sources
from support import at, claude_records, dump


class SourceTests(unittest.TestCase):
    def test_bridge_uses_existing_usage_fixture_and_reuses_loaded_module(self):
        reader = sources.reader()
        fixture = Path('tests/usage/fixtures/claude.jsonl')
        rows = reader.normalize(reader.read_claude(fixture, Counter()), Counter())
        call = next(r for r in rows if r.get('id') == 'm1')
        self.assertEqual(call['output_tokens'], 5)
        self.assertIs(reader, sources.reader())

    def test_collect_preserves_prior_markers_and_deduplicates(self):
        with tempfile.TemporaryDirectory() as name:
            home = Path(name)
            (home / '.codex/sessions').mkdir(parents=True)
            root = home / '.claude/projects' / str(home / 'my/dev-tools/jigs').replace('/', '-')
            records = claude_records(home / 'my/dev-tools/jigs/.worktrees/igr-15')
            dump(root / 'session.jsonl', records + records[1:2])
            rows, paths, counts = sources.collect_pilot(at(30), home)
            self.assertEqual(len([r for r in rows if r['type'] == 'call']), 1)
            self.assertTrue(any(r.get('action') == 'start' for r in rows))
            self.assertEqual(len(paths), 1)
            self.assertGreater(counts['duplicate'], 0)

    def test_missing_log_root_is_not_known_empty(self):
        with tempfile.TemporaryDirectory() as name:
            with self.assertRaises(FileNotFoundError):
                list(sources.codex_pilot_files(Path(name)))

    def test_lexical_repo_mapping_does_not_require_existing_directory(self):
        home = Path('/a/person')
        self.assertEqual(sources.repo_for('/a/person/my/dev-tools/jigs/.worktrees/gone', home), 'ig-ra/jigs')
        self.assertIsNone(sources.repo_for('/a/person/my/dev-tools/jigs-other', home))
        self.assertEqual(sources.stamp('2026-10-17T03:00:00+03:00'), at())
