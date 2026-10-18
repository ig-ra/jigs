import unittest

from stats.ticket_flow.model import Marker
from stats.ticket_flow import stages
from support import at, turn


class StageTests(unittest.TestCase):
    def test_whole_turn_latches_and_prior_marker_crosses_provider_and_repo(self):
        markers = [Marker('IGR-15',at(0),'design','a','other/repo'),
                   Marker('IGR-15',at(15),'implement','b')]
        first, second = turn(), turn('second',start=20,end=30)
        stages.assign([first,second],markers)
        self.assertEqual([first.stage,second.stage],['design','implement'])
        self.assertEqual(first.marker.repo,'other/repo')

    def test_only_other_session_same_ticket_overlap_is_ambiguous(self):
        first, same, other, different = turn(),turn('same'),turn('other',session='other'),turn('different',ticket='IGR-16')
        stages.assign([first,same],[])
        self.assertEqual(first.order,'timestamp')
        stages.assign([first,other,different],[])
        self.assertEqual(first.order,'ambiguous')
        self.assertEqual(different.order,'timestamp')
        self.assertEqual(first.stage,'unknown')

    def test_equal_timestamp_stable_tie_is_not_an_ambiguity_detector(self):
        markers = [Marker('IGR-15',at(0),'design','a'),Marker('IGR-15',at(0),'implement','z')]
        result = stages.assign([turn()],list(reversed(markers)))[0]
        self.assertEqual(result.stage,'implement')
        self.assertEqual(result.order,'timestamp')

    def test_review_lenses_do_not_increment_estimate_invocation_pass(self):
        markers = [Marker('IGR-15',at(i),kind,str(i)) for i,kind in enumerate(
            ['review','simplify','native_review','fix','review','simplify'])]
        result = stages.assign([turn()],markers)[0]
        self.assertEqual(result.review_pass,2)
        self.assertEqual(result.cycle,1)
        self.assertEqual(result.stage,'further_review')
