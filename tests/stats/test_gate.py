from collections import Counter, defaultdict
import unittest

from stats.ticket_flow import gate, stages, tables
from stats.ticket_flow.model import Marker
from support import at, call, turn


class GateTests(unittest.TestCase):
    def dataset(self):
        turns=[]
        for ticket, claude, codex in [('IGR-15',62.51,104.86),('IGR-16',27.1,31.89)]:
            for provider, minutes in [('claude',claude),('codex',codex)]:
                row=call(f'{ticket}-{provider}',ticket,provider=provider)
                turns.append(turn(f'{ticket}-{provider}',ticket,provider=provider,
                    session=ticket+'-'+provider,minutes=minutes,calls=[row]))
        stages.assign(turns,[Marker(ticket,at(),'design',ticket) for ticket in ('IGR-15','IGR-16')])
        assembled=tables.assemble(turns,at(),at(60),Counter(),defaultdict(int),[],[])
        return [t.calls[0] for t in turns],turns,assembled

    def test_known_population_conserves_and_required_rounding_passes(self):
        rows,turns,result=self.dataset()
        lines,failures=gate.numeric_checks(rows,turns,result,at(),at(60))
        self.assertEqual(failures,[])
        self.assertIn('NUMERIC_GATE PASS',lines[-1])

    def test_loss_unknown_and_rounding_miss_are_failures(self):
        rows,turns,result=self.dataset()
        result['calls'].pop()
        result['run'].append(dict(ticket='IGR-15',actor='claude_main',metric='unknown_tokens_pct',value=5.01))
        turns[0].minutes=61
        _,failures=gate.numeric_checks(rows,turns,result,at(),at(60))
        self.assertTrue(any('CALL_ID_CONSERVATION FAIL' in f for f in failures))
        self.assertTrue(any('RAW_MINUTES FAIL' in f for f in failures))
        self.assertTrue(any('UNKNOWN_SHARE FAIL' in f for f in failures))
