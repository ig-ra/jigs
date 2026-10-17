"""Small synthetic logs only. No provider writes or network access."""
from collections import Counter
from contextlib import redirect_stdout, redirect_stderr
import copy
import io
import importlib.machinery
import importlib.util
import json
import os
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

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
        self.assertEqual(call['result_chars'], 27)
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
        self.assertEqual(calls[0]['tools'][0]['result_chars'], 59)
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
        finish['cwd'] = '/repo/.worktrees/igr-13'
        normalized = usage.normalize(rows, Counter())
        call = next(r for r in normalized if r.get('id') == 'm7')
        self.assertEqual((call['ticket'], call['phase']), ('IGR-15', 'design'))

    def test_keyless_finish_scope_and_done_updates(self):
        rows = usage.read_claude(FIXTURES / 'claude.jsonl', Counter())
        finish = next(r for r in rows if r.get('action') == 'finish')
        self.assertNotIn('marker_ticket', finish)
        final_call = next(r for r in rows if r.get('id') == 'm7')
        for index, line in enumerate(('implement', 'reviews', 'checks'), 20):
            rows.append(usage.event(dict(finish, timestamp=f'2026-10-08T00:00:{index}Z',
                source={'path': 'cleanup', 'line': index}, record_id=f'done-{index}'),
                'step', marker_ticket='IGR-15', step=line, status='done'))
        rows.append(dict(final_call, id='cleanup', timestamp='2026-10-08T00:00:24Z'))
        calls = {r['id']: r for r in usage.normalize(rows, Counter()) if r['type'] == 'call'}
        self.assertEqual(calls['cleanup']['phase'], 'finish')
        for cwd, expected in (('/repo/.worktrees/igr-42', 'IGR-42'), ('/repo', None)):
            marker = dict(finish, cwd=cwd)
            following = dict(final_call, cwd=cwd)
            parsed = usage.normalize([marker, following], Counter())
            call = next(r for r in parsed if r['type'] == 'call')
            self.assertEqual(call['ticket'], expected)
            self.assertEqual(call['phase'], 'finish' if expected else 'unknown')
        # Explicit new work can leave finish; done-only bookkeeping cannot.
        rows.append(usage.event(dict(finish, timestamp='2026-10-08T00:00:25Z',
            source={'path': 'cleanup', 'line': 25}, record_id='new-work'),
            'step', marker_ticket='IGR-15', step='implement', status='running'))
        rows.append(dict(final_call, id='new-work', timestamp='2026-10-08T00:00:26Z'))
        parsed = usage.normalize(rows, Counter())
        self.assertEqual(next(r['phase'] for r in parsed if r.get('id') == 'new-work'), 'develop')

    def test_step_requires_literal_invocation_and_native_success_receipt(self):
        common = {'provider': 'claude', 'session_id': 'session',
                  'timestamp': '2026-10-08T00:00:00Z', 'source': {'path': 'fixture', 'line': 1}}
        receipt = 'IGR-15 reviews=running'
        direct = '/repo/tk --cwd /repo/.worktrees/igr-15 step IGR-15 reviews running'
        commands = ['echo "tk step IGR-15 reviews running"',
            'rg "tk step IGR-15 reviews running" docs',
            'python3 -c "print(\"tk step IGR-15 reviews running\")"',
            "cat <<'EOF'\ntk step IGR-15 reviews running\nEOF"]
        for command in commands:
            action = usage.tool('tool', 'Bash', {'command': command}, common['source'])
            with self.subTest(command=command):
                self.assertEqual(usage.step_events(common, action, receipt), [])
        opaque = usage.tool('opaque', 'exec', 'run({cmd:"tk step IGR-15 reviews running"})', common['source'])
        self.assertEqual(usage.step_events(common, opaque, receipt), [])
        opaque_json = usage.tool('opaque', 'exec', json.dumps({'cmd': direct}), common['source'])
        self.assertEqual(usage.step_events(common, opaque_json, receipt), [])
        action = usage.tool('tool', 'Bash', {'command': 'cd /repo && ' + direct}, common['source'])
        for output, is_error in [('ok', False), ('ERROR estimate already open for this line', False),
                ('Command running in background with ID: task', False), (receipt, True)]:
            self.assertEqual(usage.step_events(common, action, output, is_error), [])
        self.assertEqual(usage.step_events(common, action, receipt)[0]['step'], 'reviews')
        with patch.object(usage, 'successful', side_effect=AssertionError('unrelated result scanned')):
            read = usage.tool('read', 'Read', {}, common['source'])
            self.assertEqual(usage.step_events(common, read, 'large unrelated result'), [])

    def test_steps_outside_closed_heredocs_keep_receipts_but_not_body_examples(self):
        common = {'provider': 'claude', 'session_id': 'session',
                  'timestamp': '2026-10-08T00:00:00Z', 'source': {'path': 'fixture', 'line': 1}}
        direct = '/repo/tk step IGR-15 reviews running'
        body = "prose with an unmatched ' quote\ntk step IGR-15 checks done\n"
        commands = [
            direct + "\ncat <<'EOF'\n" + body + 'EOF\n',
            'cat <<"EOF"\n' + body + 'EOF\n' + direct,
            "cat <<A\n" + body + 'A\n' + direct + "\ncat <<B\n" + body + 'B\n',
            'cat <<A <<B\n' + body + 'A\n' + body + 'B\n' + direct,
            "cat <<-'EOF'\n" + body + '\tEOF\n' + direct,
            "cat <<- 'EOF'\n" + body + '\tEOF\n' + direct,
            'echo "<<"\n' + direct,
        ]
        for command in commands:
            with self.subTest(command=command):
                action = usage.tool('tool', 'Bash', {'command': command}, common['source'])
                events = usage.step_events(common, action, 'IGR-15 reviews=running\nIGR-15 checks=done')
                self.assertEqual([(r['step'], r['status']) for r in events], [('reviews', 'running')])
                self.assertEqual(usage.step_events(common, action, 'IGR-15 reviews=running', True), [])
                self.assertEqual(usage.step_events(common, action, 'Command running in background with ID: task'), [])

    def test_unclosed_or_unsupported_heredocs_do_not_prove_steps(self):
        direct = 'tk step IGR-15 reviews running'
        commands = [direct + '\ncat <<EOF\nunclosed',
            'cat <<$END\nbody\nEND\n' + direct,
            'cat <<EOF#suffix\nbody\nEOF\n' + direct,
            'cat <<< "body"\n' + direct,
            'cat <<EOF\\\nbody\nEOF\n' + direct,
            'cat <<EOF\nbody\n EOF\n' + direct,
            'cat <<A <<B\nbody\nA\n' + direct,
            'cat <<\n' + direct]
        for command in commands:
            with self.subTest(command=command):
                self.assertEqual(usage.step_candidates(command), [])

    def test_native_event_identity_deduplicates_copies_not_distinct_meter_times(self):
        rows = usage.read_claude(FIXTURES / 'claude.jsonl', Counter())
        copies = copy.deepcopy(rows)
        for row in copies:
            row['source']['path'] = 'another-project/' + Path(row['source']['path']).name
        rows += copies + usage.read_codex(FIXTURES / 'codex.jsonl', Counter())
        for row in rows:
            if row.get('event') == 'meter':
                row['used_percent'] = 17
        normalized = usage.normalize(rows, Counter())
        self.assertEqual(sum(r.get('event') == 'compaction' for r in normalized), 2)
        self.assertEqual(sum(r.get('event') == 'ticket_command' for r in normalized), 4)
        self.assertEqual(sum(r.get('event') == 'resume_start' for r in normalized), 2)
        meters = [r for r in normalized if r.get('event') == 'meter']
        self.assertEqual(len(meters), 2)
        self.assertNotEqual(meters[0]['timestamp'], meters[1]['timestamp'])

    def test_codex_native_string_subagent_role(self):
        rows = usage.normalize(usage.read_codex(FIXTURES / 'codex-review.jsonl', Counter()), Counter())
        call = next(r for r in rows if r['type'] == 'call')
        self.assertEqual(call['native_role'], 'review')
        self.assertEqual(call['parent_session_id'], 'parent')
        self.assertEqual(call['new_input_tokens'], 100)

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

    def test_cli_uses_writer_estimates_environment_path(self):
        rows, _ = load()
        with tempfile.TemporaryDirectory() as directory:
            override = Path(directory) / 'estimates.tsv'
            override.write_bytes((FIXTURES / 'estimates.tsv').read_bytes())
            output = io.StringIO()
            with patch.dict(os.environ, {'AGENT_ESTIMATES': str(override)}), \
                    patch.object(sys, 'argv', ['usage', 'tickets', '2026-10-08', '2026-10-09']), \
                    patch.object(usage, 'collect', return_value=(rows, Counter())), \
                    redirect_stdout(output), redirect_stderr(io.StringIO()):
                usage.main()
            lines = output.getvalue().splitlines()
            headers = lines[1].split('\t')
            ticket = next(dict(zip(headers, row.split('\t'))) for row in lines[2:] if row.startswith('IGR-15\t'))
            self.assertEqual(ticket['claude_review_minutes'], '2.00')
            self.assertEqual(ticket['codex.completed_dispatch_minutes'], '3.00')


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
        self.assertEqual(ticket['claude_review_minutes'], '2.00')
        self.assertEqual(ticket['claude.estimated_rounds_low'], 'null')
        self.assertEqual(ticket['claude.estimated_rounds_high'], 'null')
        self.assertEqual(parsed['IGR-13']['claude_review_minutes'], 'null')
        self.assertEqual(ticket['codex.resume_starts'], '1')
        self.assertEqual(sum(v['calls'] for v in json.loads(ticket['claude.phase_totals']).values()), 4)
        out = io.StringIO()
        usage.render('export', rows, out)
        exported = [json.loads(line) for line in out.getvalue().splitlines()]
        self.assertEqual(exported, rows)
        self.assertTrue(all('_steps' not in action for r in exported for action in r.get('tools', [])))

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
        self.assertEqual(counts['duplicate'], 14)  # 8 calls and 6 copied native events.


if __name__ == '__main__':
    unittest.main()
