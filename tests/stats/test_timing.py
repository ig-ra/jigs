import unittest
from pathlib import Path
import tempfile

from stats.ticket_flow import timing
from support import at, dump, turn


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

    def test_overlap_is_attributed_to_later_source_not_later_completion(self):
        first = turn('first',start=0,end=40,source='session.jsonl:9')
        later = turn('later',start=10,end=20,source='session.jsonl:10')
        timing.attribute_overlap([later,first])
        self.assertEqual(first.overlap, 0)
        self.assertAlmostEqual(later.overlap, 10/60)

    def test_foreground_result_pairs_union_clip_and_preserve_raw_time(self):
        with tempfile.TemporaryDirectory() as name:
            records = []
            for kind, identity, second in [('tool_use','a',0),('tool_use','b',5),
                                           ('tool_result','a',15),('tool_result','b',20)]:
                block = dict(type=kind,id=identity,name='Bash',input={'command':'sleep 20'}) if kind == 'tool_use' else dict(
                    type=kind,tool_use_id=identity,content='done')
                records.append(dict(timestamp=at(second).isoformat(),message={'content':[block]}))
            path = dump(Path(name)/'session.jsonl',records)
            one = turn(start=5,end=30,source=f'{path}:10')
            timing.attribute_waits([one],timing.wait_intervals({str(path):'claude'}))
            self.assertAlmostEqual(one.wait,15/60)
            self.assertAlmostEqual(one.minutes,25/60)

    def test_unmatched_background_and_parallel_waits(self):
        self.assertFalse(timing.foreground_wait('Bash',{'command':'sleep 10 &'}))
        self.assertFalse(timing.foreground_wait('Bash',{'command':'sleep 10','run_in_background':True}))
        self.assertTrue(timing.foreground_wait('functions.wait',{'cell_id':'1'}))
        a,b = turn(source='a.jsonl:10'),turn('b',session='other',source='b.jsonl:10')
        timing.attribute_waits([a,b],[('a.jsonl',2,at(0),at(15)),('b.jsonl',2,at(0),at(15))])
        self.assertAlmostEqual(a.wait+b.wait,10/60)
        with tempfile.TemporaryDirectory() as name:
            path = dump(Path(name)/'session.jsonl',[dict(timestamp=at().isoformat(),message={'content':[
                dict(type='tool_use',id='a',name='Bash',input={'command':'sleep 10'})]})])
            self.assertEqual(timing.wait_intervals({str(path):'claude'}), [])
