"""PR availability, head identity and required multi-PR propagation."""
import unittest
import test_check as support
from stats.ticket_flow.table_common import PR_SUMS


class PRCheckTests(unittest.TestCase):
    setUp = support.CheckTests.setUp
    invoke = support.CheckTests.invoke
    fact = support.CheckTests.fact
    fails = support.CheckTests.fails

    def unavailable(self):
        self.fact('pr_lookup_available')['value'] = 0
        self.fact('prs_found')['value'] = ''
        self.fact('no_pr_tickets')['value'] = ''
        self.data['tickets'][0].update(prs='', coverage='partial', **dict.fromkeys(PR_SUMS, ''))

    def matched(self, number=3, repo='ig-ra/jigs', status='suspect'):
        fields = dict.fromkeys(PR_SUMS, 1)
        fields.update(head_ref='igor/igr-15-example', head_sha='abc', created='2026-10-17T00:00:00+00:00',
                      merged='', first_review='', first_bot='', churn_ratio=1, fix_split_status=status)
        for field, value in fields.items():
            self.data['run'].append(dict(ticket='IGR-15', repo=repo, pr=number,
                                         metric='pr_' + field, value=value))
        n = sum(r['metric'] == 'pr_head_ref' for r in self.data['run'])
        self.fact('prs_found')['value'] = n
        self.fact('no_pr_tickets')['value'] = 0
        self.data['tickets'][0].update(prs=n, churn_ratio=1, fix_split_status=status,
                                      **dict.fromkeys(PR_SUMS, n))
        if status == 'unavailable':
            self.data['tickets'][0]['coverage'] = 'partial'

    def test_unavailable_is_blank_and_partial_known_empty_is_zero(self):
        self.assertEqual(self.invoke()[0], 0)
        self.unavailable()
        self.assertEqual(self.invoke()[0], 0)
        for field in ('prs', *PR_SUMS, 'churn_ratio', 'review_after_bot'):
            with self.subTest(field=field):
                self.data = support.evidence()
                self.unavailable()
                self.data['tickets'][0][field] = 0
                self.fails('PR_MISSINGNESS_FAIL')

    def test_lookup_missing_duplicate_and_wrong_counts(self):
        self.data['run'].append(dict(self.fact('pr_lookup_available')))
        self.fails('missing_evidence_or_duplicate')
        self.data = support.evidence()
        self.fact('prs_found')['value'] = 1
        self.fails('metric=prs_found')
        self.data = support.evidence()
        self.unavailable()
        self.data['tickets'][0]['coverage'] = 'complete'
        self.fails('unavailable_lookup_contradiction')

    def test_matched_multiple_repos_worst_status_and_churn(self):
        self.matched()
        self.matched(4, 'Sawmills/condition-curator', 'unavailable')
        self.assertEqual(self.invoke()[0], 0)
        self.data['tickets'][0]['fix_split_status'] = 'suspect'
        self.fails('metric=fix_split_status')
        self.data['tickets'][0]['fix_split_status'] = 'unavailable'
        self.data['tickets'][0]['churn_ratio'] = '1.1'
        self.fails('metric=churn_ratio')

    def test_missing_required_contribution_propagates_and_head_is_exact(self):
        self.matched()
        row = self.fact('pr_pr_files')
        row['value'] = ''
        self.data['tickets'][0].update(pr_files='', coverage='partial')
        self.assertEqual(self.invoke()[0], 0)
        self.data['tickets'][0]['pr_files'] = 0
        self.fails('metric=pr_files')
        self.data['tickets'][0].update(pr_files='', coverage='partial')
        self.fact('pr_head_ref')['value'] = 'igor/igr-150-collision'
        self.fails('head=igor/igr-150-collision')
        self.data['run'].remove(row)
        self.fails('missing_metrics=')

    def test_duplicate_pr_metric_and_contradictory_unavailable_snapshot(self):
        self.matched()
        self.data['run'].append(dict(self.fact('pr_head_ref')))
        self.fails('duplicate_or_invalid=head_ref')
        self.data = support.evidence()
        self.matched()
        self.unavailable()
        self.fails('unavailable_lookup_contradiction')

    def test_pr_metric_without_identity_cannot_hide_as_known_empty(self):
        self.data['run'].append(dict(ticket='IGR-15', metric='pr_head_ref', value='igor/igr-15-example'))
        self.fails('expected=repo_and_pr_identity')

    def test_global_pr_head_count_is_not_a_snapshot_fact(self):
        self.data['run'].append(dict(metric='pr_heads', value=0))
        self.assertEqual(self.invoke()[0], 0)
