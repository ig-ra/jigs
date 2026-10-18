import unittest

from stats.ticket_flow import population
from stats.ticket_flow.model import Marker
from support import at, call, turn


class PopulationTests(unittest.TestCase):
    def test_selection_and_complete_recorded_history_for_active_tickets(self):
        turns = [turn(ticket='IGR-15', start=0, end=5,
                      calls=[call(time=30, repo='ig-ra/jigs')]),
                 turn(ticket='SAW-100', start=0, end=25, calls=[]),
                 turn(ticket=None, end=25, calls=[]),
                 turn(ticket='SAW-999', end=5, calls=[])]
        markers = [Marker('IGR-15', at(0), 'design', 'early', 'Sawmills/agent-platform'),
                   Marker('IGR-99', at(25), 'finish', 'only', 'ig-ra/jigs')]
        estimates = [dict(ticket='SAW-200', time=at(30))]
        selected = population.selected_tickets(turns, markers, estimates, at(20), at(40))
        self.assertEqual(selected, {'IGR-15', 'SAW-100', 'IGR-99', 'SAW-200', None})
        collected = dict(rows=[call(ticket='SAW-999', repo='Sawmills/condition-curator'),
            call(ticket='IGR-15', repo='Sawmills/condition-curator', time=0)],
            turns=turns, markers=markers)
        self.assertEqual(population.repo_tickets(collected, selected), {
            'ig-ra/jigs': {'IGR-15', 'SAW-100', 'IGR-99'},
            'Sawmills/condition-curator': {'IGR-15'}, 'Sawmills/agent-platform': {'IGR-15'}})
