from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from stats.ticket_flow import local
from support import at, call, claude_records, dump


class LocalTests(unittest.TestCase):
    def test_event_and_estimate_markers_use_timestamped_evidence(self):
        row = dict(call(), type='event', event='step', status='fixing', step='reviews')
        self.assertEqual(local.event_markers([row])[0].kind, 'fix')
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / 'estimates.tsv'
            path.write_text('id\tstarted\tagent\tticket\ttask\n'
                            'r1\t2026-10-17T03:00:00+03:00\tclaude-review\tIGR-15\treview\n'
                            'f1\t2026-10-17T00:01:00Z\tcodex\tIGR-15\tfindings and fix\n')
            markers = local.estimate_markers(path)
            self.assertEqual([m.kind for m in markers], ['review','fix'])
            self.assertEqual(markers[0].time, at())

    def test_invocations_only_from_actual_tool_arguments(self):
        self.assertEqual(local.invocation_kind('Skill', {'skill':'simplify'}), 'simplify')
        self.assertEqual(local.invocation_kind('Bash', {'command':'codex-companion review --wait'}), 'native_review')
        self.assertEqual(local.invocation_kind('Bash', {'command':'node /scripts/codex-companion.mjs review --wait'}), 'native_review')
        self.assertEqual(local.invocation_kind('functions.exec', {'code':
            'await tools.exec_command({cmd: "node /scripts/codex-companion.mjs review --wait"})'}), 'native_review')
        self.assertIsNone(local.invocation_kind('Read', {'file_path':'review.md'}))

    def test_native_markers_use_local_authored_time_and_source(self):
        with tempfile.TemporaryDirectory() as name:
            records = [dict(type='user', cwd='/repo/.worktrees/igr-15', timestamp=at(30).isoformat(),
                message={'content':[dict(type='tool_result',content='[branch abcdef1] fix')]})]
            path = dump(Path(name)/'session.jsonl', records)
            markers = local.native_markers({str(path):'claude'}, [], Path(name),
                                            commit_time=lambda sha, repo: at(20))
            self.assertEqual(markers[0].time, at(20))
            self.assertEqual(markers[0].identity, 'abcdef1')
            self.assertIn(':1', markers[0].source)
            wrapped = 'Script completed\n{"exit_code":0,"output":"[branch abcdef1] fix\\n"}'
            markers = local.commit_markers(wrapped,'IGR-15','source:2','/repo',Path(name),
                                           lambda sha, repo: at(20))
            self.assertEqual(markers[0].identity,'abcdef1')

    def test_missing_estimate_log_is_not_empty_evidence(self):
        with self.assertRaises(FileNotFoundError):
            local.estimate_markers(Path('/nonexistent/igr19-estimates'))

    def test_successful_done_transitions_and_nonpilot_events(self):
        rows = [dict(call(ticket='SAW-100'), type='event', event='step', step='reviews',status=status)
                for status in ('running','done','todo','fail')]
        markers = local.event_markers(rows)
        self.assertEqual([m.kind for m in markers], ['own_review','bots_ci'])
        self.assertEqual({m.ticket for m in markers}, {'SAW-100'})

    def test_simplify_lens_dispatch_shares_skill_invocation_group(self):
        from stats.ticket_flow.stages import timeline
        with tempfile.TemporaryDirectory() as name:
            path = dump(Path(name)/'session.jsonl',[dict(type='assistant',cwd='/repo/.worktrees/saw-100',
                timestamp=at().isoformat(),message={'content':[
                    dict(type='tool_use',id='skill',name='Skill',input={'skill':'simplify'}),
                    dict(type='tool_use',id='lens',name='Agent',input={'description':'Simplify reuse lens'})]})])
            markers = local.native_markers({str(path):'claude'}, [], Path(name))
            self.assertEqual(len(markers), 2)
            self.assertEqual(sum(row[-1] is not None for row in timeline(markers)['SAW-100']), 1)

    def test_failed_commit_output_is_not_a_fix_marker(self):
        with tempfile.TemporaryDirectory() as name:
            path = dump(Path(name)/'session.jsonl', [dict(type='response_item',
                timestamp=at().isoformat(),payload={'type':'function_call_output',
                    'output':'Process exited with code 1\n[branch abcdef1] fix'},cwd='/repo/.worktrees/igr-15')])
            self.assertEqual(local.native_markers({str(path):'codex'},[],Path(name)), [])

    def test_complete_local_collection_attaches_activity_waits_and_estimates(self):
        with tempfile.TemporaryDirectory() as name:
            home = Path(name)
            (home/'.codex/sessions').mkdir(parents=True)
            root = home/'.claude/projects'/str(home/'my/dev-tools/jigs').replace('/', '-')
            dump(root/'session.jsonl',claude_records(home/'my/dev-tools/jigs/.worktrees/igr-15'))
            (home/'.claude/agent-estimates.tsv').write_text('id\tstarted\tagent\tticket\ttask\n'
                'one\t2026-10-17T00:00:00Z\tcodex\tIGR-15\timplement\n')
            result = local.collect(at(60), home)
            one, = result['turns']
            self.assertEqual(one.calls[0]['activity'], 'reply / communication (no tool)')
            self.assertEqual(one.wait, 0)
            self.assertEqual(len(result['estimates']), 1)
            self.assertTrue(any(m.kind == 'design' for m in result['markers']))

    def test_end_retained_unmatched_starts_control_historical_coverage(self):
        from stats.ticket_flow import stages, tables
        from stats.ticket_flow.model import Marker
        with tempfile.TemporaryDirectory() as name:
            home = Path(name)
            (home / '.claude/projects').mkdir(parents=True)
            (home / '.claude/agent-estimates.tsv').write_text('id\tstarted\tagent\tticket\ttask\n')
            meta = dict(type='session_meta', payload={'id': 'session',
                'cwd': str(home / 'my/dev-tools/jigs/.worktrees/igr-15')})
            def event(kind, identity, second):
                return dict(type='event_msg', timestamp=at(second).isoformat(),
                            payload={'type': kind, 'turn_id': identity})
            done = [meta, event('task_started', 'done', 5), event('task_complete', 'done', 20)]
            for extra, expected in (([], 0),
                    ([event('task_started', 'future', 70)], 0),
                    ([event('task_started', 'exactly-end', 60)], 0),
                    ([event('task_started', 'pre-start', 0)], 1),
                    ([event('task_started', 'in-window', 30)], 1)):
                with self.subTest(extra=extra):
                    dump(home / '.codex/sessions/session.jsonl', done + extra)
                    with patch.object(Path, 'home', return_value=home):
                        collected = local.collect(at(60), home)
                    self.assertEqual(sum(collected['unmatched'].values()), expected)
                    self.assertTrue(all(t.start < at(60) for t in collected['turns']))
                    markers = [Marker('IGR-15', at(), 'design', 'start')]
                    stages.assign(collected['turns'], markers)
                    result = tables.assemble(collected['turns'], at(10), at(60), {},
                        collected['unmatched'], [], markers, [], {'IGR-15'})
                    row, = result['tickets']
                    self.assertEqual(row['coverage'], 'partial' if expected else 'complete')
                    self.assertAlmostEqual(row['codex_minutes_raw'], 15 / 60)
                    self.assertEqual(next(r['value'] for r in result['run']
                                          if r['metric'] == 'unmatched_starts'), expected)
