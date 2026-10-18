import unittest

from stats.ticket_flow import timing
from support import at, turn


class TimingTests(unittest.TestCase):
    def test_union_and_overlap_conserve_raw_work(self):
        turns = [turn('a',start=0,end=20), turn('b',start=10,end=30)]
        timing.attribute_overlap(turns)
        self.assertAlmostEqual(sum(t.overlap for t in turns), 10/60)
        self.assertAlmostEqual(sum(t.minutes for t in turns), 40/60)
        self.assertAlmostEqual(timing.union_minutes([(at(0),at(20)),(at(10),at(30))]), 30/60)

    def test_parallel_sessions_are_not_subtracted(self):
        turns = [turn(),turn('other',session='other')]
        timing.attribute_overlap(turns)
        self.assertEqual(sum(t.overlap for t in turns), 0)
        self.assertTrue(timing.overlaps(*turns))
        self.assertFalse(timing.overlaps(turn(end=20),turn(start=20,end=30)))

    def test_negative_interval_rejected(self):
        with self.assertRaises(ValueError):
            timing.union_minutes([(at(20),at(10))])
