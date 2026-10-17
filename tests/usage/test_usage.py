"""Small synthetic logs only. No provider writes or network access."""
from collections import Counter
import io
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

    def test_finish_marker_does_not_replace_latest_start_resume_intake(self):
        rows = usage.read_claude(FIXTURES / 'claude.jsonl', Counter())
        finish = next(r for r in rows if r.get('action') == 'finish')
        finish['marker_ticket'] = 'IGR-13'
        normalized = usage.normalize(rows, Counter())
        call = next(r for r in normalized if r.get('id') == 'm7')
        self.assertEqual((call['ticket'], call['phase']), ('IGR-15', 'design'))

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

    def test_nested_workflow_subagents_link_to_main_and_stay_out_of_main_context(self):
        with tempfile.TemporaryDirectory() as directory:
            child = Path(directory) / 'main/subagents/workflows/wf-example/agent-worker.jsonl'
            child.parent.mkdir(parents=True)
            child.write_bytes((FIXTURES / 'child.jsonl').read_bytes())
            rows = usage.normalize(usage.read_claude(child, Counter()), Counter())
            self.assertEqual(rows[0]['parent_session_id'], 'main')
            out = io.StringIO()
            usage.summary(rows, out)
            self.assertIn('main_sessions\t0\t0', out.getvalue())
            self.assertIn('child_sessions\t1\t0', out.getvalue())

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


class ReportTests(unittest.TestCase):
    def test_phase_and_ticket_splits_reconcile_calls_and_raw_buckets(self):
        rows, _ = load()
        for provider in ('claude', 'codex'):
            selected = [r for r in rows if r['provider'] == provider]
            total = usage.aggregate(selected)
            phases = usage.phase_totals(selected)
            tickets = [usage.aggregate([r for r in selected if r['ticket'] == key])
                       for key in {r['ticket'] for r in selected}]
            for key in ('calls',) + usage.BUCKETS:
                self.assertEqual(sum(v[key] or 0 for v in phases.values()), total[key] or 0)
                self.assertEqual(sum(v[key] or 0 for v in tickets), total[key] or 0)
        self.assertEqual(usage.percentile([1, 2, 3, 4], .9), 3.7)
        self.assertEqual(usage.percentile([], .5), None)
        call = next(r for r in rows if r.get('id') == 'm1')
        # 10 new + 15*1.25 + 5*2 write + 100*.1 read + 5*5 output.
        self.assertEqual(usage.weighted(call), 73.75)
        self.assertEqual(usage.weighted(dict(call, model='claude-sonnet')), 44.25)
        self.assertEqual(usage.weighted(dict(call, model='unknown')), None)
        self.assertEqual(usage.weighted(dict(call, provider='codex')), None)

    def test_summary_export_and_one_ticket_row_with_both_providers(self):
        rows, _ = load()
        out = io.StringIO()
        usage.render('summary', rows, out)
        rendered = out.getvalue()
        self.assertIn('calls\t7\t2', rendered)
        self.assertIn(usage.PROXY_LABEL, rendered)
        self.assertIn('claude\tmixed\t1', rendered)
        self.assertIn('Phase totals (all calls; unknown included)', rendered)
        out = io.StringIO()
        usage.render('tickets', rows, out, usage.estimates(FIXTURES / 'estimates.tsv'))
        lines = out.getvalue().splitlines()
        headers = lines[0].split('\t')
        parsed = {cells[0]: dict(zip(headers, cells)) for cells in (line.split('\t') for line in lines[1:])}
        self.assertEqual(set(parsed), {'IGR-13', 'IGR-15', 'SAW-42', 'unassigned'})
        ticket = parsed['IGR-15']
        self.assertEqual((ticket['claude.calls'], ticket['codex.calls']), ('4', '2'))
        self.assertEqual(ticket['codex.estimated_rounds_low'], '3.00')
        self.assertEqual(ticket['codex.completed_dispatch_minutes'], '3.00')
        self.assertEqual(ticket['claude.completed_dispatch_minutes'], 'null')
        self.assertEqual(ticket['codex.resume_starts'], '1')
        self.assertEqual(sum(v['calls'] for v in json.loads(ticket['claude.phase_totals']).values()), 4)
        out = io.StringIO()
        usage.render('export', rows, out)
        exported = [json.loads(line) for line in out.getvalue().splitlines()]
        self.assertEqual(exported, rows)
        self.assertTrue(all('_command' not in action for r in exported for action in r.get('tools', [])))

    def test_session_links_claude_children_but_codex_shows_own_thread_only(self):
        rows, _ = load()
        main = next(r for r in rows if r.get('id') == 'm1')
        child = dict(main, id='child', session_id='agent-child', parent_session_id='claude')
        own = next(r for r in rows if r.get('id') == 'r1')
        descendant = dict(own, id='child-codex', session_id='codex-child', parent_session_id='codex-main')
        out = io.StringIO()
        usage.timeline(rows + [child], 'claude', 'claude', out)
        self.assertIn('agent-child', out.getvalue())
        self.assertIn('idle_gap_seconds', out.getvalue())
        out = io.StringIO()
        usage.timeline(rows + [descendant], 'codex', 'codex-main', out)
        self.assertIn('Codex thread: codex-main', out.getvalue())
        self.assertIn('meter', out.getvalue())
        self.assertIn('compaction', out.getvalue())
        self.assertNotIn('codex-child', out.getvalue())
        self.assertNotIn('parent_session_id', out.getvalue())

    def test_global_duplicate_keeps_union_and_largest_usage(self):
        rows = usage.read_claude(FIXTURES / 'claude.jsonl', Counter())
        counts = Counter()
        normalized = usage.normalize(rows + rows, counts)
        self.assertEqual(sum(r['type'] == 'call' for r in normalized), 7)
        self.assertEqual(next(r['output_tokens'] for r in normalized if r.get('id') == 'm1'), 5)
        self.assertEqual(counts['duplicate'], 8)


if __name__ == '__main__':
    unittest.main()
