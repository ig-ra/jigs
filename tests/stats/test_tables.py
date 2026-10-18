from collections import Counter, defaultdict
import unittest

from stats.ticket_flow import stages, tables, timing
from stats.ticket_flow.model import Marker
from support import at, call, turn


class TableTests(unittest.TestCase):
    def assemble(self, turns):
        return tables.assemble(turns,at(0),at(60),Counter(),defaultdict(int),[],[])

    def test_completion_only_turn_and_out_of_window_calls_are_separate_populations(self):
        one = turn(calls=[call(time=70)])
        result = self.assemble([one])
        self.assertEqual(result['calls'],[])
        self.assertEqual(result['tickets'][0]['claude_main_minutes_raw'],1/6)
        self.assertEqual(result['tickets'][0]['claude_main_new_input_tokens'],0)
        records=next(r for r in result['run'] if r['metric']=='claude_duration_records')
        self.assertEqual(records['value'],1)

    def test_missing_is_blank_but_known_empty_is_zero(self):
        one=turn(calls=[call(cache_read_tokens=None)])
        result=self.assemble([one])
        self.assertIsNone(result['tickets'][0]['claude_main_cache_read_tokens'])
        self.assertEqual(result['tickets'][0]['codex_new_input_tokens'],0)
        self.assertIsNone(tables.sum_required([0,None]))

    def test_no_duplicate_repo_rows_and_unknown_preserves_tokens(self):
        turns=[turn(),turn('two',repo='other/repo',calls=[call('m2')])]
        result=self.assemble(turns)
        self.assertEqual(len(result['tickets']),1)
        self.assertEqual(result['tickets'][0]['claude_main_new_input_tokens'],20)
        self.assertEqual(result['stages'][0]['stage'],'unknown')
        self.assertNotIn('repo',result['tickets'][0])
        metric=next(r for r in result['run'] if r['metric']=='unknown_tokens_pct' and r['actor']=='claude_main')
        self.assertEqual((metric['numerator'],metric['denominator'],metric['value']),(70,70,100))

    def test_call_marker_provenance_is_retained(self):
        turns=stages.assign([turn()],[Marker('IGR-15',at(0),'design','marker:1','repo')])
        row=self.assemble(turns)['calls'][0]
        self.assertEqual(row['marker_source'],'marker:1')
        self.assertEqual(row['start_basis'],'first_call')
        self.assertEqual(row['timestamp'],at(10).isoformat())

    def test_wait_overlap_invocation_counts_and_fix_rounds_conserve(self):
        turns = [turn('a',start=10,end=30,source='session.jsonl:9'),
                 turn('b',start=15,end=25,source='session.jsonl:10',calls=[call('m2',time=16)])]
        markers = [Marker('IGR-15',at(0),'simplify','m0',group='launch'),
                   Marker('IGR-15',at(1),'simplify','m1',group='launch'),
                   Marker('IGR-15',at(12),'fix','m2',group='one'),
                   Marker('IGR-15',at(13),'fix','m3',group='two'),
                   Marker('IGR-15',at(14),'commit','m4',identity='abc')]
        timing.attribute_overlap(turns)
        timing.attribute_waits(turns,[('session.jsonl',8,at(12),at(16))])
        stages.assign(turns,markers)
        result = tables.assemble(turns,at(),at(60),Counter(),defaultdict(int),[],markers)
        ticket, = result['tickets']
        self.assertEqual(ticket['simplify_passes'], 1)
        self.assertEqual(ticket['fix_rounds'], 2)
        self.assertEqual(ticket['fix_cycles'], 1)
        self.assertAlmostEqual(ticket['foreground_wait_min'],4/60)
        self.assertAlmostEqual(ticket['turn_overlap_min'],10/60)
        for metric in ('foreground_wait_min','turn_overlap_min','claude_main_minutes_raw'):
            self.assertAlmostEqual(sum(row[metric] for row in result['stages']), ticket[metric])

    def test_child_audit_and_required_estimate_missingness(self):
        one = turn(parent='parent',child_description='full description',
                   calls=[call(activity='other',activity_basis='missing_tool_input')])
        estimate = dict(ticket='IGR-15',time=at(),identity='dispatch',agent='codex',source='estimates:2',
                        rounds_low=1,rounds_high=2,minutes_low=None,minutes_high=None,actual_minutes=None)
        result = tables.assemble([one],at(),at(60),Counter(),defaultdict(int),[],[],[estimate])
        row, = result['calls']
        self.assertIn('missing_child_type',row['missing_reason'])
        self.assertIn('missing_tool_input',row['missing_reason'])
        self.assertIsNone(row['child_family'])
        self.assertEqual(row['child_description'],'full description')
        ticket, = result['tickets']
        self.assertEqual(ticket['dispatches'],1)
        self.assertEqual(ticket['estimated_rounds_high'],2)
        self.assertIsNone(ticket['estimated_minutes_low'])
        self.assertTrue(any(r['source'] == 'estimates:2' for r in result['run'] if 'source' in r))

    def test_available_empty_sources_can_be_complete_and_unmatched_keeps_work(self):
        markers=[Marker('IGR-15',at(),'design','start')]
        one=stages.assign([turn(wait=0,calls=[call(activity='reply',repo='ig-ra/jigs')])],markers)[0]
        result=tables.assemble([one],at(),at(60),Counter(),{},[],markers,[], {'IGR-15'})
        self.assertEqual(result['tickets'][0]['coverage'],'complete')
        self.assertEqual(result['tickets'][0]['prs'],0)
        partial=tables.assemble([one],at(),at(60),Counter(),{'IGR-15':1},[],markers,[], {'IGR-15'})
        self.assertEqual(partial['tickets'][0]['coverage'],'partial')
        self.assertEqual(partial['tickets'][0]['claude_main_minutes_raw'],one.minutes)

    def test_ticket_indicator_is_not_duplicated_across_repos(self):
        from github_support import fact
        markers=[Marker('IGR-15',at(20),'simplify','review')]
        prs=[fact(first_bot=at(10).isoformat()),fact(2,'Sawmills/agent-platform')]
        result=tables.assemble([turn()],at(),at(60),Counter(),{},prs,markers,queried={'IGR-15'})
        self.assertEqual(len(result['tickets']),1)
        self.assertEqual(result['tickets'][0]['review_after_bot'],1)
        self.assertEqual(result['tickets'][0]['prs'],2)
        self.assertEqual(sum(s['claude_main_new_input_tokens'] for s in result['stages']),10)

    def test_duplicate_canonical_call_cannot_publish_double_counted_work(self):
        with self.assertRaisesRegex(ValueError,'duplicate canonical call'):
            self.assemble([turn(),turn('second')])

    def test_every_raw_bucket_and_duration_conserves_including_unknown_and_missing(self):
        from stats.ticket_flow.model import ACTORS, TOKENS
        values=dict(new_input_tokens=2,cache_read_tokens=3,cache_write_tokens=5,output_tokens=7,activity='reply')
        turns=[turn(wait=0,calls=[call(repo='ig-ra/jigs',**values)]),
               turn('child',ticket='IGR-16',session='child',parent='session',start=30,end=40,minutes=None,
                    calls=[call('child',ticket='IGR-16',session_id='child',time=35,**dict(values,cache_write_tokens=None))]),
               turn('codex',provider='codex',session='codex-child',parent='session',start=40,end=50,wait=0,
                    calls=[call('codex',provider='codex',session_id='codex-child',time=45,**values)])]
        markers=[Marker('IGR-15',at(),'design','start')]
        stages.assign(turns,markers)
        result=tables.assemble(turns,at(),at(60),Counter(),{},[],markers)
        for ticket in result['tickets']:
            group=[t for t in turns if t.ticket==ticket['ticket']]
            rows=[r for r in result['stages'] if r['ticket']==ticket['ticket']]
            for actor in ACTORS:
                for token in TOKENS:
                    metric=f'{actor}_{token}'
                    expected=tables.sum_required(c[token] for t in group if t.actor==actor for c in t.calls)
                    self.assertEqual(ticket[metric],expected)
                    self.assertEqual(tables.sum_required(r[metric] for r in rows),expected)
            for actor in ('claude_main','codex'):
                metric=actor+'_minutes_raw'
                expected=sum(t.minutes for t in group if t.actor==actor and t.minutes is not None)
                self.assertAlmostEqual(ticket[metric],expected)
                self.assertAlmostEqual(sum(r[metric] for r in rows),expected)
        self.assertTrue(any(row['stage']=='unknown' for row in result['stages']))
