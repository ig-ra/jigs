import unittest

from stats.ticket_flow import table_common
from stats.ticket_flow.model import Marker
from support import at, call, turn


class CommonTests(unittest.TestCase):
    def test_known_empty_and_required_missing(self):
        self.assertEqual(table_common.sum_required([]),0)
        self.assertIsNone(table_common.sum_required([1,None]))
        self.assertEqual(table_common.sum_required([0,1.5]),1.5)

    def test_coverage_describes_gaps_without_nulling_recorded_work(self):
        audit=dict(call(),repo='ig-ra/jigs',activity='reply',stage='design',stage_order='timestamp')
        one=turn(stage='design',wait=0)
        self.assertEqual(table_common.coverage([audit],[one]),'complete')
        for changed in (dict(audit,stage='unknown'),dict(audit,cache_read_tokens=None),
                        dict(audit,missing_reason='missing_child_type')):
            self.assertEqual(table_common.coverage([changed],[one]),'partial')
        self.assertEqual(table_common.coverage([audit],[turn(stage='design',minutes=None)]),'partial')
        self.assertEqual(table_common.coverage([],[turn(stage='design',wait=0,repo=None)]),'partial')
        self.assertEqual(table_common.coverage([audit],[one],[Marker('IGR-15',at(),'native_review','local:1')]),'partial')

    def test_codex_parentage_is_not_a_gap_but_actual_child_gaps_are(self):
        complete = dict(provider='codex', parent='parent', child_type='worker',
                        child_description='review implementation', child_family='review',
                        stage='design', wait=0, calls=[])
        self.assertEqual(table_common.coverage([], [turn(**complete)]), 'complete')
        for changes in ({'child_type': None}, {'child_description': None}, {'child_family': None},
                        {'minutes': None}, {'wait': None}, {'ticket': None}, {'repo': None},
                        {'stage': 'unknown'}, {'order': 'ambiguous'},
                        {'provider': 'claude', 'minutes': None}):
            with self.subTest(changes=changes):
                self.assertEqual(table_common.coverage([], [turn(**dict(complete, **changes))]), 'partial')
