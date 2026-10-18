from collections import Counter, defaultdict
import unittest

from stats.ticket_flow import stages, tables
from stats.ticket_flow.model import Marker
from support import at, call, turn


class TableTests(unittest.TestCase):
    def assemble(self, turns):
        return tables.assemble(turns,at(0),at(60),Counter(),defaultdict(int),[],[])

    def test_completion_only_turn_and_out_of_window_calls_are_separate_populations(self):
        one = turn(calls=[call(time=70)])
        result = self.assemble([one])
        self.assertEqual(result['calls'],[])
        self.assertEqual(result['tickets'][0]['claude_main_minutes_raw'],1/6)
        self.assertEqual(result['tickets'][0]['claude_main_new_input_tokens'],0)
        records=next(r for r in result['run'] if r['metric']=='claude_duration_records')
        self.assertEqual(records['value'],1)

    def test_missing_is_blank_but_known_empty_is_zero(self):
        one=turn(calls=[call(cache_read_tokens=None)])
        result=self.assemble([one])
        self.assertIsNone(result['tickets'][0]['claude_main_cache_read_tokens'])
        self.assertEqual(result['tickets'][0]['codex_new_input_tokens'],0)
        self.assertIsNone(tables.sum_required([0,None]))

    def test_no_duplicate_repo_rows_and_unknown_preserves_tokens(self):
        turns=[turn(),turn('two',repo='other/repo',calls=[call('m2')])]
        result=self.assemble(turns)
        self.assertEqual(len(result['tickets']),1)
        self.assertEqual(result['tickets'][0]['claude_main_new_input_tokens'],20)
        self.assertEqual(result['stages'][0]['stage'],'unknown')
        self.assertNotIn('repo',result['tickets'][0])
        metric=next(r for r in result['run'] if r['metric']=='unknown_tokens_pct' and r['actor']=='claude_main')
        self.assertEqual((metric['numerator'],metric['denominator'],metric['value']),(70,70,100))

    def test_call_marker_provenance_is_retained(self):
        turns=stages.assign([turn()],[Marker('IGR-15',at(0),'design','marker:1','repo')])
        row=self.assemble(turns)['calls'][0]
        self.assertEqual(row['marker_source'],'marker:1')
        self.assertEqual(row['start_basis'],'first_call')
        self.assertEqual(row['timestamp'],at(10).isoformat())
