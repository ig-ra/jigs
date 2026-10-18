import unittest

from stats.ticket_flow import ticket_table
from github_support import fact
from stats.ticket_flow import tables
from stats.ticket_flow.model import Marker
from support import at


class TicketTableTests(unittest.TestCase):
    def test_completed_estimate_without_repo_is_unavailable_not_observed_empty(self):
        estimate = dict(ticket='IGR-15', time=at(), identity='only', agent='codex',
                        source='estimate:2', rounds_low=1, rounds_high=2,
                        minutes_low=1, minutes_high=2, actual_minutes=1)
        marker = Marker('IGR-15', at(), 'implement', 'estimate:2')
        for queried, available in ((set(), False), ({'IGR-15'}, True)):
            with self.subTest(available=available):
                result = tables.assemble([], at(), at(60), {}, {}, [], [marker], [estimate], queried)
                row, = result['tickets']
                self.assertEqual(row['coverage'], 'complete' if available else 'partial')
                for field in ('prs', 'pr_commits', 'bot_reviews', 'bot_comments', 'bot_threads'):
                    self.assertEqual(row[field], 0 if available else None)
                global_count = next(r['value'] for r in result['run'] if r['metric'] == 'no_pr_tickets')
                self.assertEqual(global_count, 1 if available else None)

    def test_all_pr_contributions_ratio_and_worst_status(self):
        one=fact()
        two=fact(2,'Sawmills/agent-platform',initial_additions=10,initial_deletions=0,
                 fix_additions=10,fix_deletions=0,churn_ratio=1.0,fix_split_status='suspect')
        row=ticket_table.pr_totals([one,two,one])
        self.assertEqual(row['prs'],2)
        self.assertAlmostEqual(row['churn_ratio'],45/130)
        self.assertEqual(row['fix_split_status'],'suspect')
        self.assertEqual(row['pr_files'],6)

    def test_missing_pr_contribution_is_never_excluded_from_ratio(self):
        one=fact()
        two=fact(2,fix_additions=None,churn_ratio=None,fix_split_status='unavailable')
        row=ticket_table.pr_totals([one,two])
        self.assertEqual(row['pr_commits'],4)
        self.assertEqual(row['fix_commits'],2)
        self.assertIsNone(row['fix_additions'])
        self.assertIsNone(row['churn_ratio'])
        self.assertEqual(row['fix_split_status'],'unavailable')

    def test_uncollected_and_known_no_pr_are_distinct(self):
        missing=ticket_table.pr_totals(None)
        empty=ticket_table.pr_totals([])
        self.assertIsNone(missing['prs'])
        self.assertIsNone(missing['pr_commits'])
        self.assertEqual(empty['prs'],0)
        self.assertEqual(empty['pr_commits'],0)
        self.assertIsNone(empty['churn_ratio'])
