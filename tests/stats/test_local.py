from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from stats.ticket_flow import local
from support import at, call, dump


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
