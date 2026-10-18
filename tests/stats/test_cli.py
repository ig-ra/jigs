from contextlib import redirect_stdout, redirect_stderr
import io
import unittest
from unittest.mock import patch

from stats.ticket_flow import __main__ as cli


class CliTests(unittest.TestCase):
    def test_invalid_window_does_not_collect_or_publish(self):
        with patch.object(cli,'measure') as measure, patch.object(cli.csvio,'publish') as publish:
            with redirect_stderr(io.StringIO()):
                status=cli.main(['2026-10-18','2026-10-17'])
            self.assertEqual(status,2)
            measure.assert_not_called()
            publish.assert_not_called()

    def test_source_failure_does_not_publish(self):
        with patch.object(cli,'measure',side_effect=OSError('source unavailable')):
            with patch.object(cli.csvio,'publish') as publish,redirect_stderr(io.StringIO()):
                self.assertEqual(cli.main(['2026-10-17','2026-10-18']),2)
                publish.assert_not_called()

    def test_numeric_failure_publishes_pilot_evidence_and_nonzero_status(self):
        with patch.object(cli,'measure',return_value=({},['NUMERIC_GATE FAIL'],['failed'])):
            with patch.object(cli.csvio,'publish') as publish,redirect_stdout(io.StringIO()):
                self.assertEqual(cli.main(['2026-10-17','2026-10-18']),1)
                publish.assert_called_once()
