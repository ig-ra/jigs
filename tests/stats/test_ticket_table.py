import unittest

from stats.ticket_flow import ticket_table
from github_support import fact


class TicketTableTests(unittest.TestCase):
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
