from pathlib import Path
import tempfile
import unittest

from stats.ticket_flow import estimates
from support import at


class EstimateTests(unittest.TestCase):
    def test_dispatch_bounds_deduplication_missing_values_and_source(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name)/'estimates.tsv'
            path.write_text('id\tstarted\tagent\tticket\ttask\trounds_low\trounds_high\test_min\tactual_min\n'
                'one\t2026-10-17T03:00:00+03:00\tcodex\tsaw-100\tfix findings\t2\t4\t10-30\t20\n'
                'one\t2026-10-17T00:00:00Z\tcodex\tsaw-100\tfix findings\t2\t4\t10-30\t20\n'
                'two\t2026-10-17T00:01:00Z\tclaude-review\tIGR-15\treview\t1\t1\t\t\n')
            rows = estimates.collect(path)
            self.assertEqual(len(rows), 2)
            self.assertEqual((rows[0]['ticket'], rows[0]['time']), ('SAW-100', at()))
            self.assertEqual((rows[0]['minutes_low'],rows[0]['minutes_high']), (10,30))
            self.assertIsNone(rows[1]['minutes_low'])
            self.assertIsNone(rows[1]['actual_minutes'])
            self.assertEqual([m.kind for m in estimates.markers(rows)], ['fix','review'])
            self.assertEqual(rows[0]['source'], f'{path}:2')

    def test_single_zero_and_invalid_ranges(self):
        self.assertEqual(estimates.bounds('0'), (0,0))
        self.assertEqual(estimates.bounds('1.5'), (1.5,1.5))
        for value in ('3-1', 'roughly 20'):
            with self.assertRaises(ValueError):
                estimates.bounds(value)
