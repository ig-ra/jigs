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

    def test_review_kinds_reruns_and_grouped_lenses(self):
        markers = [Marker('IGR-15', at(0), 'review', '0', group='dispatch'),
                   Marker('IGR-15', at(1), 'own_review', '1'),
                   Marker('IGR-15', at(2), 'simplify', '2', group='s1'),
                   Marker('IGR-15', at(3), 'simplify', '3', group='s1'),
                   Marker('IGR-15', at(4), 'native_review', '4', identity='native'),
                   Marker('IGR-15', at(5), 'fix', '5', identity='fix-dispatch'),
                   Marker('IGR-15', at(6), 'commit', '6', identity='abc'),
                   Marker('IGR-15', at(7), 'review', '7', group='rerun'),
                   Marker('IGR-15', at(8), 'simplify', '8', group='s2')]
        result = stages.assign([turn()],markers)[0]
        self.assertEqual(result.review_pass,5)
        self.assertEqual(result.cycle,1)
        self.assertEqual(result.stage,'further_review')

    def test_consecutive_fix_dispatches_are_rounds_within_one_cycle(self):
        markers = [Marker('IGR-15',at(i),kind,str(i)) for i,kind in enumerate(
            ['review','fix','fix','commit','review','fix','commit'])]
        result = stages.assign([turn()], markers)[0]
        self.assertEqual((result.cycle, result.stage), (2, 'fix'))

    def test_own_review_receipt_before_dispatch_is_the_same_invocation(self):
        markers = [Marker('IGR-15',at(0),'own_review','step',identity='receipt'),
                   Marker('IGR-15',at(1),'review','estimate',group='dispatch'),
                   Marker('IGR-15',at(2),'review','rerun',group='dispatch-two')]
        result = stages.assign([turn()],markers)[0]
        self.assertEqual(result.review_pass, 2)

    def test_fixing_receipt_and_dispatch_group_in_both_orders(self):
        for kinds in [('receipt','dispatch'),('dispatch','receipt')]:
            markers = [Marker('IGR-15',at(i),'fix',kind,group='one' if kind == 'dispatch' else None)
                       for i,kind in enumerate(kinds)]
            markers += [Marker('IGR-15',at(3),'commit','commit'),
                        Marker('IGR-15',at(4),'fix','rerun',group='two')]
            events = stages.timeline(markers)['IGR-15']
            self.assertEqual(sum(row[-1] == 'fix_round' for row in events), 2)
            self.assertEqual(events[-1][4], 1)
