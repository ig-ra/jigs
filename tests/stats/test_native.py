from pathlib import Path
import tempfile
import unittest

from stats.ticket_flow import native
from support import at, call, claude_records, dump


class NativeTests(unittest.TestCase):
    def test_claude_duration_deduplication_and_first_call_start(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / 'session.jsonl'
            records = claude_records('/repo/.worktrees/igr-15')
            dump(path, records + [records[-1]])
            turns = native.claude_turns(path, {}, {('claude', 'm1'): call()})
            self.assertEqual(len(turns), 1)
            self.assertEqual(turns[0].minutes, 1/6)
            self.assertEqual(turns[0].start, at(10))
            self.assertEqual(turns[0].start_basis, 'first_call')

    def test_completion_only_duration_and_child_missing_duration(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / 'session.jsonl'
            records = claude_records('/repo/.worktrees/igr-15')
            dump(path, records[-1:])
            turns = native.claude_turns(path, {}, {})
            self.assertEqual(turns[0].ticket, 'IGR-15')
            self.assertEqual(turns[0].start_basis, 'duration_record')
            child = Path(name) / 'parent/subagents/session.jsonl'
            dump(child, records[:2])
            turns = native.claude_turns(child, {}, {('claude', 'm1'): call()})
            self.assertIsNone(turns[0].minutes)
            self.assertEqual(turns[0].actor, 'claude_subagents')

    def test_codex_interleaved_pairs_duplicates_and_unmatched_start(self):
        with tempfile.TemporaryDirectory() as name:
            records = [{'type': 'session_meta', 'payload': {
                'id': 'session', 'cwd': '/repo/.worktrees/igr-15'}, 'timestamp': at().isoformat()}]
            records.append(dict(type='session_meta', timestamp=at().isoformat(),
                payload={'id':'copied-parent','cwd':'/repo/.worktrees/igr-15'}))
            for kind, identity, time in [('task_started','a',0), ('task_started','b',5),
                    ('task_complete','b',10), ('task_complete','a',20),
                    ('task_complete','a',20), ('task_started','c',30)]:
                records.append(dict(type='event_msg', timestamp=at(time).isoformat(),
                                    payload={'type':kind, 'turn_id':identity}))
            path = dump(Path(name) / 'session.jsonl', records)
            turns, unmatched = native.codex_turns(path, {}, {})
            self.assertEqual(unmatched, 1)
            self.assertAlmostEqual(sum(t.minutes or 0 for t in turns), 25/60)
            self.assertEqual(len(turns), 3)
            self.assertEqual({t.session for t in turns}, {'session'})

    def test_ticket_index_uses_prior_evidence_never_future_majority(self):
        index = native.ticket_index([call(time=10), call('m2', ticket='IGR-16', time=20)])
        self.assertIsNone(native.ticket_at(index, 'session', at(5)))
        self.assertEqual(native.ticket_at(index, 'session', at(15)), 'IGR-15')
        self.assertEqual(native.ticket_at(index, 'session', at(25)), 'IGR-16')
