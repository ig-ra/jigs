import unittest

from stats.ticket_flow import stage_table, stages, tables
from stats.ticket_flow.model import Marker
from support import at, call, turn


class StageTableTests(unittest.TestCase):
    def test_completed_child_codex_work_and_raw_bucket_conservation(self):
        first=turn(stage='design',wait=0,calls=[call(activity='reply')])
        child=turn('child',provider='codex',session='child',parent='session',stage='design',wait=0,
                   calls=[call('c',provider='codex',session_id='child',activity='source edits')])
        markers=[Marker('IGR-15',at(),'design','start')]
        stages.assign([first,child],markers)
        audit=tables.audit_rows([first,child],at(),at(60))
        rows=stage_table.stage_rows([first,child],audit,at(),at(60),markers)
        self.assertEqual(sum(r['claude_main_new_input_tokens'] for r in rows),10)
        self.assertEqual(sum(r['codex_new_input_tokens'] for r in rows),10)
        self.assertAlmostEqual(sum(r['codex_minutes_raw'] for r in rows),child.minutes)
        self.assertEqual(rows[0]['coverage'],'partial')

    def test_many_fix_commits_do_not_become_rounds_or_cycles(self):
        markers=[Marker('IGR-15',at(1),'first_review','review')]
        markers += [Marker('IGR-15',at(i),'commit',str(i),identity=str(i)) for i in range(2,8)]
        turns=stages.assign([turn()],markers)
        rows=stage_table.stage_rows(turns,tables.audit_rows(turns,at(),at(60)),at(),at(60),markers)
        self.assertEqual(sum(r['fix_cycles'] for r in rows),1)
        self.assertEqual(sum(r['fix_rounds'] for r in rows),0)

    def test_future_completion_supplies_calls_without_in_window_minutes(self):
        one=turn(end=70,calls=[call(activity='reply')])
        audit=tables.audit_rows([one],at(),at(60))
        rows=stage_table.stage_rows([one],audit,at(),at(60))
        self.assertEqual(rows[0]['calls'],1)
        self.assertEqual(rows[0]['claude_main_minutes_raw'],0)
