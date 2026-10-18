from collections import Counter, defaultdict
import unittest

from stats.ticket_flow import tables
from github_support import fact
from support import at, call, turn


class RunTableTests(unittest.TestCase):
    def test_multi_repo_no_pr_unassigned_and_head_provenance(self):
        turns=[turn(calls=[call(repo='ig-ra/jigs')]),
               turn('two',ticket='IGR-16',calls=[call('two',ticket='IGR-16')]),
               turn('unassigned',ticket=None,calls=[call('none',ticket=None)])]
        prs=[fact(),fact(2,'Sawmills/agent-platform')]
        rows=tables.assemble(turns,at(),at(60),Counter(malformed=1),defaultdict(int),prs,[],queried={'IGR-15','IGR-16'})['run']
        overall={r['metric']:r['value'] for r in rows if 'ticket' not in r}
        self.assertEqual(overall['unassigned_calls'],1)
        self.assertEqual(overall['multi_repo_tickets'],1)
        self.assertEqual(overall['no_pr_tickets'],1)
        heads=[r for r in rows if r['metric']=='pr_head_sha']
        self.assertEqual(len(heads),2)
        self.assertEqual({r['repo'] for r in heads},{'ig-ra/jigs','Sawmills/agent-platform'})
        self.assertTrue(all(r['source'].startswith('github:') for r in heads))

    def test_missing_token_bucket_has_no_fabricated_share_denominator(self):
        one=turn(calls=[call(cache_read_tokens=None)])
        rows=tables.assemble([one],at(),at(60),Counter(),defaultdict(int),[],[])['run']
        token=next(r for r in rows if r['metric']=='unknown_tokens_pct' and r['actor']=='claude_main')
        self.assertIsNone(token['denominator'])
        self.assertIsNone(token['value'])
        child=next(r for r in rows if r['metric']=='unknown_minutes_pct' and r['actor']=='claude_subagents')
        self.assertIsNone(child['denominator'])

    def test_completed_pairs_counts_use_completion_window(self):
        one=turn(provider='codex',end=70,calls=[call(provider='codex')])
        rows=tables.assemble([one],at(),at(60),Counter(),defaultdict(int),[],[])['run']
        count=next(r for r in rows if r['metric']=='codex_completed_pairs')
        self.assertEqual(count['value'],0)

    def test_completion_only_turns_supply_repo_coverage_and_absent_heads_stay_missing(self):
        turns=[turn(calls=[],repo='ig-ra/jigs'),
               turn('other',calls=[],repo='Sawmills/agent-platform')]
        rows=tables.assemble(turns,at(),at(60),Counter(),{},[fact(head_sha=None)],[])['run']
        totals={r['metric']:r['value'] for r in rows if 'ticket' not in r}
        self.assertEqual(totals['multi_repo_tickets'],1)
        self.assertIsNone(totals['pr_heads'])
