"""Parked handoff regressions; all data synthetic, no live Herdr calls.

Run: python3 -B -m unittest discover -s plugins/igr/docs/plans -p test_wf_herdr_handoff.py
"""
import argparse
from contextlib import contextmanager
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("herdr_handoff", HERE / "wf-herdr-handoff.py")
hand = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = hand
SPEC.loader.exec_module(hand)


def args(**values):
    return argparse.Namespace(json=False, **values)


class FakeClock:
    def __init__(self):
        self.now = 0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


@contextmanager
def clock():
    fake = FakeClock()
    with patch.object(hand.time, "monotonic", fake.monotonic), patch.object(hand.time, "sleep", fake.sleep):
        yield fake


class HandoffTests(unittest.TestCase):
    def test_structured_error_code_and_local_timeout_are_distinct(self):
        response = Mock(returncode=1, stderr=json.dumps({"error": {"code": "agent_blocked", "message": "timeout-agent blocked"}}), stdout="")
        with patch.object(hand.subprocess, "run", return_value=response):
            with self.assertRaises(hand.HandoffError) as error:
                hand.run(["herdr", "agent", "prompt", "timeout-agent", "brief", "--timeout", "1000"])
        self.assertEqual(error.exception.source_code, "agent_blocked")
        with patch.object(hand.subprocess, "run", side_effect=subprocess.TimeoutExpired(["herdr", "--timeout"], 1)):
            with self.assertRaises(hand.HandoffError) as error:
                hand.run(["herdr", "--timeout", "1000"])
        self.assertIsNone(error.exception.source_code)

    def test_ping_derived_recipient_quoted_and_deduplicated(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            cwd = root / ".worktrees" / "owner" / "team-12"
            cwd.mkdir(parents=True)
            file = root / "answer $(literal).md"
            file.write_text("answer")
            agent = {"agent": "claude", "agent_status": "idle", "pane_id": "w1:p2", "agent_session": {"value": "session"}}
            with patch.object(hand, "herdr", return_value={"agent": agent}) as api, \
                    patch.object(hand, "temp_root", return_value=root), patch("sys.stdout", new_callable=io.StringIO) as out:
                for _ in range(2):
                    self.assertEqual(hand.ping(hand.Context(cwd), args(file=str(file), to=None)), 0)
            prompts = [call.args[0] for call in api.call_args_list if call.args[0][1] == "prompt"]
            self.assertEqual(prompts, [["agent", "prompt", "team-12", f"{file.resolve()} ready"]])
            self.assertIn("ALREADY_SENT", out.getvalue())

    def test_blocked_ping_has_no_receipt_or_raw_input(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            file = root / "answer.md"
            file.write_text("answer")
            agent = {"agent": "claude", "agent_status": "blocked", "pane_id": "w1:p2"}
            with patch.object(hand, "herdr", return_value={"agent": agent}) as api, \
                    patch.object(hand, "temp_root", return_value=root), patch("sys.stdout", new_callable=io.StringIO):
                self.assertEqual(hand.ping(hand.Context(root), args(file=str(file), to="claude")), 1)
            self.assertEqual(api.call_count, 1)
            self.assertFalse((root / "ping-receipts.json").exists())

    def test_send_idle_grace_for_stale_file_and_two_observations_for_fresh_answer(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, answer = root / "brief.md", root / "answer.md"
            source.write_text("brief")
            answer.write_text("old answer")
            a = args(brief=str(source), answer=str(answer), agent="codex", timeout=60, interval=0.01)
            with patch.object(hand, "herdr", return_value={"agent": {"agent_status": "idle"}}), \
                    clock(), \
                    patch("sys.stdout", new_callable=io.StringIO) as out:
                self.assertEqual(hand.send(hand.Context(root), a), 1)
            self.assertIn("STOPPED", out.getvalue())
            def respond(command, **kwargs):
                if command[1] == "prompt":
                    answer.write_text("new answer")
                return {"agent": {"agent_status": "idle"}}
            with patch.object(hand, "herdr", side_effect=respond), clock(), \
                    patch("sys.stdout", new_callable=io.StringIO) as out:
                self.assertEqual(hand.send(hand.Context(root), a), 0)
            self.assertIn("READY", out.getvalue())

    def test_idle_flicker_resets_grace_then_fresh_answer_finishes(self):
        with tempfile.TemporaryDirectory() as folder:
            source, answer = Path(folder) / "brief.md", Path(folder) / "answer.md"
            source.write_text("brief")
            def respond(command, **kwargs):
                if command[1] == "prompt":
                    return {}
                state = "idle" if fake.now < 20 else "working" if fake.now < 22 else "done"
                if fake.now >= 48:
                    answer.write_text("fresh answer")
                return {"agent": {"agent_status": state}}
            a = args(brief=str(source), answer=str(answer), agent="codex", timeout=60, interval=2)
            with patch.object(hand, "herdr", side_effect=respond), clock() as fake, \
                    patch("sys.stdout", new_callable=io.StringIO) as out:
                self.assertEqual(hand.send(hand.Context(Path(folder)), a), 0)
            self.assertIn("READY", out.getvalue())

    def test_send_never_matches_timeout_word_in_a_blocked_agent_name(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "brief.md"
            source.write_text("brief")
            a = args(brief=str(source), answer=str(Path(folder) / "answer.md"), agent="timeout-agent", timeout=60, interval=2)
            with patch.object(hand, "herdr", side_effect=hand.HandoffError("timeout-agent blocked", source_code="agent_blocked")) as api, \
                    patch("sys.stdout", new_callable=io.StringIO):
                self.assertEqual(hand.send(hand.Context(Path(folder)), a), 1)
            self.assertEqual(api.call_count, 1)


if __name__ == "__main__":
    unittest.main()
