"""Small synthetic logs only. No provider writes or network access."""
from collections import Counter
import importlib.machinery
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_loader('usage', importlib.machinery.SourceFileLoader(
    'usage', str(HERE.parents[1] / 'bin/usage')))
usage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(usage)
FIXTURES = HERE / 'fixtures'


def load():
    counts = Counter()
    rows = usage.read_claude(FIXTURES / 'claude.jsonl', counts)
    rows += usage.read_codex(FIXTURES / 'codex.jsonl', counts)
    return usage.normalize(rows, counts), counts


class ReaderTests(unittest.TestCase):
    def test_claude_streaming_duplicates_union_tools_and_result_sizes(self):
        rows, counts = load()
        call = next(r for r in rows if r.get('id') == 'm1')
        self.assertEqual((call['output_tokens'], call['context_tokens']), (5, 130))
        self.assertEqual([a['id'] for a in call['tools']], ['read', 'step'])
        self.assertEqual(call['result_chars'], 5)
        self.assertEqual(call['kind'], 'mixed')
        self.assertEqual((call['cache_write_5m_tokens'], call['cache_write_1h_tokens']), (15, 5))
        self.assertEqual(counts['duplicate'], 2)  # One Claude appearance, one Codex compaction.
        self.assertEqual(counts['synthetic'], 1)
        self.assertNotIn('synth', [r.get('id') for r in rows])

    def test_codex_responses_compaction_and_meter_are_separate(self):
        rows, _ = load()
        calls = [r for r in rows if r['provider'] == 'codex' and r['type'] == 'call']
        self.assertEqual([r['id'] for r in calls], ['r1', 'compaction'])
        self.assertEqual(sum(r['context_tokens'] for r in calls), 500)
        self.assertEqual(sum(r['new_input_tokens'] for r in calls), 300)
        self.assertEqual(sum(r['output_tokens'] for r in calls), 40)
        self.assertEqual(calls[0]['reasoning_tokens'], 5)
        self.assertEqual(calls[0]['parent_session_id'], 'parent')
        self.assertEqual(calls[0]['native_role'], 'reviewer')
        self.assertEqual(calls[0]['tools'][0]['result_chars'], 37)
        meters = [r for r in rows if r.get('event') == 'meter']
        self.assertEqual([r['used_percent'] for r in meters], [17, 18])
        self.assertEqual(sum(r.get('event') == 'compaction' for r in rows), 2)
        self.assertEqual(sum(r.get('event') == 'resume_start' for r in rows), 2)

    def test_ticket_intake_is_temporal_and_successful_phases_are_scoped(self):
        rows, _ = load()
        calls = {r['id']: r for r in rows if r['type'] == 'call'}
        self.assertEqual((calls['m1']['ticket'], calls['m1']['phase']), ('IGR-13', 'unknown'))
        self.assertEqual((calls['m2']['ticket_basis'], calls['m2']['phase']), ('via intake', 'develop'))
        self.assertEqual((calls['m3']['ticket'], calls['m3']['phase']), ('IGR-15', 'design'))
        self.assertEqual(calls['m4']['phase'], 'design')  # Failed review command.
        self.assertEqual(calls['m5']['phase'], 'design')  # Other ticket's command begins in this phase.
        self.assertEqual(calls['m6']['ticket'], 'SAW-42')
        self.assertEqual(calls['m6']['phase'], 'unknown')
        self.assertEqual(calls['m7']['phase'], 'finish')
        steps = [r for r in rows if r.get('event') == 'step']
        self.assertEqual([(r['step'], r['status']) for r in steps], [('implement', 'running'), ('reviews', 'running'), ('implement', 'running')])

    def test_child_link_malformed_unassigned_and_read_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            claude, codex = root / 'claude', root / 'codex'
            claude.mkdir()
            codex.mkdir()
            (claude / 'main.jsonl').write_bytes((FIXTURES / 'claude.jsonl').read_bytes())
            child = claude / 'main/subagents/agent-child.jsonl'
            child.parent.mkdir(parents=True)
            child.write_bytes((FIXTURES / 'child.jsonl').read_bytes())
            (codex / 'rollout-codex-main.jsonl').write_bytes((FIXTURES / 'codex.jsonl').read_bytes())
            (claude / 'broken.jsonl').write_bytes((FIXTURES / 'malformed.jsonl').read_bytes())
            unassigned = json.loads((FIXTURES / 'child.jsonl').read_text())
            unassigned['cwd'] = '/repo'
            unassigned['message']['id'] = 'unassigned'
            (claude / 'unknown.jsonl').write_text(json.dumps(unassigned) + '\n')
            def snapshot():
                return {str(p.relative_to(root)): (p.read_bytes(), p.stat().st_mtime_ns)
                        for p in root.rglob('*') if p.is_file()}
            before = snapshot()
            rows, counts = usage.collect(claude_root=claude, codex_root=codex)
            self.assertEqual(snapshot(), before)
            call = next(r for r in rows if r.get('id') == 'child1')
            self.assertEqual((call['session_id'], call['parent_session_id']), ('agent-child', 'main'))
            self.assertEqual(counts['malformed'], 1)
            self.assertEqual(counts['unassigned'], 1)
            scoped, _ = usage.collect(claude_root=claude, codex_root=codex, session=('claude', 'main'))
            self.assertIn('child1', [r.get('id') for r in scoped])

    def test_window_is_utc_end_exclusive_and_whole_file_metadata_retained(self):
        counts = Counter()
        rows = usage.read_claude(FIXTURES / 'claude.jsonl', counts)
        rows = usage.normalize(rows, counts, usage.stamp('2026-10-08T00:00:04Z'), usage.stamp('2026-10-08T00:00:08Z'))
        self.assertEqual([r.get('id') for r in rows if r['type'] == 'call'], ['m2'])
        self.assertEqual(rows[0]['ticket'], 'IGR-13')
        self.assertEqual(rows[0]['phase'], 'develop')
        self.assertEqual(usage.stamp('2026-10-08T03:00:00+03:00'), usage.stamp('2026-10-08'))

    def test_estimate_fields_are_named_nullable_and_windowed(self):
        totals = usage.estimates(FIXTURES / 'estimates.tsv', usage.stamp('2026-10-08'), usage.stamp('2026-10-09'))
        self.assertEqual(totals[('IGR-15', 'codex')], dict(estimated_rounds_low=3, estimated_rounds_high=6, completed_dispatch_minutes=3))
        self.assertEqual(totals[('IGR-13', 'claude')]['completed_dispatch_minutes'], None)
        self.assertEqual(usage.estimates(FIXTURES / 'absent'), {})


if __name__ == '__main__':
    unittest.main()
