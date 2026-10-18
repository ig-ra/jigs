from contextlib import redirect_stdout, redirect_stderr
import importlib
import io
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from stats.ticket_flow import __main__ as cli
from stats.ticket_flow.model import Marker
from support import at, call, turn


class CliTests(unittest.TestCase):
    def test_invalid_window_does_not_collect_or_publish(self):
        for window in (['2026-10-18', '2026-10-17'], ['2026-10-17'] * 2,
                       ['2026-10-17T12:00:00Z', '2026-10-18'],
                       ['20261017', '2026-10-18'], ['2026-02-30', '2026-10-18'],
                       ['../2026-10-17', '2026-10-18']):
            with self.subTest(window=window), patch.object(cli, 'measure') as measure:
                with patch.object(cli.csvio, 'publish') as publish, redirect_stderr(io.StringIO()):
                    self.assertEqual(cli.main(window), 2)
                    measure.assert_not_called()
                    publish.assert_not_called()

    def test_requires_exactly_two_positional_arguments(self):
        for argv in ([], ['2026-10-17'], ['2026-10-17', '2026-10-18', 'extra']):
            with self.subTest(argv=argv), redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    cli.main(argv)
                self.assertEqual(raised.exception.code, 2)

    def test_source_failure_does_not_publish_or_print_success(self):
        for error in (OSError('source unavailable'), ValueError('incomplete PR'),
                      subprocess.CalledProcessError(1, ['gh'])):
            with patch.object(cli, 'measure', side_effect=error):
                with patch.object(cli.csvio, 'publish') as publish:
                    output, errors = io.StringIO(), io.StringIO()
                    with redirect_stdout(output), redirect_stderr(errors):
                        self.assertEqual(cli.main(['2026-10-17', '2026-10-18']), 2)
                    publish.assert_not_called()
                    self.assertEqual(output.getvalue(), '')
                    self.assertIn('ticket_flow:', errors.getvalue())

    def test_success_uses_utc_boundaries_and_publishes_complete_result(self):
        result = {name: [] for name in cli.csvio.SCHEMAS}
        with patch.object(cli, 'measure', return_value=result) as measure:
            with patch.object(cli.csvio, 'publish') as publish, redirect_stdout(io.StringIO()) as output:
                self.assertEqual(cli.main(['2026-10-17', '2026-10-18']), 0)
                measure.assert_called_once_with(at(), cli.sources.stamp('2026-10-18'))
                publish.assert_called_once_with(Path('stats/runs/2026-10-17_2026-10-18'), result)
                self.assertIn('TICKET_FLOW_OUTPUT_WRITTEN', output.getvalue())

    def test_measure_joins_three_repos_from_call_completion_and_marker_evidence(self):
        completed = turn(ticket='SAW-100', repo='Sawmills/condition-curator', calls=[])
        marker = Marker('SAW-200', at(), 'design', 'marker:1', 'Sawmills/agent-platform')
        collected = dict(rows=[call(repo='ig-ra/jigs'), call(ticket=None, repo='ig-ra/jigs')],
                         turns=[completed], markers=[marker], estimates=[], counts={}, unmatched={})
        remote = Marker('SAW-100', at(), 'first_review', 'github:1')
        with patch.object(cli.local, 'collect', return_value=collected) as collect:
            with patch.object(cli.github_fetch, 'collect', return_value=([remote], [])) as fetch:
                with patch.object(cli.stages, 'assign') as assign, patch.object(cli.tables, 'assemble') as assemble:
                    self.assertIs(cli.measure(at(), at(60)), assemble.return_value)
                    collect.assert_called_once_with(at(60))
                    fetch.assert_called_once_with({'ig-ra/jigs': {'IGR-15'},
                        'Sawmills/condition-curator': {'SAW-100'}, 'Sawmills/agent-platform': {'SAW-200'}})
                    assign.assert_called_once_with([completed], [marker, remote])
                    assemble.assert_called_once_with([completed], at(), at(60), {}, {}, [], [marker, remote], [])

    def test_import_has_no_collection_or_publication_side_effect(self):
        with patch.object(cli.local, 'collect') as collect, patch.object(cli.github_fetch, 'collect') as fetch:
            with patch.object(cli.csvio, 'publish') as publish:
                importlib.reload(cli)
                collect.assert_not_called()
                fetch.assert_not_called()
                publish.assert_not_called()
