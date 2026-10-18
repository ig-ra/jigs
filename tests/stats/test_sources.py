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

    def test_complete_collection_three_roots_cross_repo_and_unassigned(self):
        with tempfile.TemporaryDirectory() as name:
            home = Path(name)
            (home/'.codex/sessions').mkdir(parents=True)
            for index, (relative, repo) in enumerate(sources.REPOS):
                cwd = home/relative/'.worktrees/igor/saw-100'
                records = claude_records(cwd)
                records[0]['message']['content'] = '/igr:ticket start SAW-100'
                records[1]['message']['id'] = f'm{index}'
                root = home/'.claude/projects'/str(home/relative).replace('/', '-')
                dump(root/f's{index}.jsonl', records)
            records = claude_records(home/'my/dev-tools/jigs')
            records[1]['message']['id'] = 'unassigned'
            dump(root/'unassigned.jsonl', records[1:2])
            sibling = home/'.claude/projects'/str(home/'my/dev-tools/jigs-other').replace('/', '-')
            dump(sibling/'sibling.jsonl',claude_records(home/'my/dev-tools/jigs-other/.worktrees/igr-16'))
            rows, paths, _ = sources.collect_local(at(30), home)
            calls = [r for r in rows if r['type'] == 'call']
            self.assertEqual({r['repo'] for r in calls}, {r for _, r in sources.REPOS})
            self.assertEqual(sum(r['ticket'] == 'SAW-100' for r in calls), 3)
            self.assertEqual(sum(r['ticket'] is None for r in calls), 1)
            self.assertEqual(len(paths), 4)
            self.assertNotIn(str(sibling/'sibling.jsonl'),paths)

    def test_complete_codex_collection_includes_children_and_pre_window_context(self):
        with tempfile.TemporaryDirectory() as name:
            home = Path(name)
            (home/'.claude/projects').mkdir(parents=True)
            records = Path('tests/usage/fixtures/codex.jsonl').read_text().replace(
                '/repo/.worktrees/igr-15', str(home/'work/agent-platform/.worktrees/igor/saw-100'))
            path = home/'.codex/sessions/day/child.jsonl'
            path.parent.mkdir(parents=True)
            path.write_text(records)
            rows, paths, _ = sources.collect_local(at(30), home)
            calls = [r for r in rows if r['type'] == 'call']
            self.assertTrue(calls)
            self.assertEqual(calls[0]['repo'], 'Sawmills/agent-platform')
            self.assertIn(str(path), paths)
            self.assertTrue(any(r['type'] == 'event' for r in rows))
