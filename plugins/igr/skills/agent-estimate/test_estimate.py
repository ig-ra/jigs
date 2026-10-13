"""Synthetic estimator/CLI regressions. Run with stdlib unittest discovery."""
import csv
import argparse
import importlib.util
import io
import os
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("estimate", HERE / "estimate.py")
estimate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(estimate)


def row(x, actual, agent="codex", **extra):
    return {"agent": agent, "rounds_low": str(x), "rounds_high": str(x),
            "actual_min": str(actual), **extra}


class MathTests(unittest.TestCase):
    def test_overhead_recovers_small_and_large_runs(self):
        rows = [row(x, 5 + 2 * x) for x in [1, 2, 3, 4, 5, 8, 12, 20, 40]]
        model = estimate.calibration("codex", rows)
        self.assertEqual(model, (5, 2, 1, 1, 9, True))
        for x in [1, 3, 12, 40]:
            lo, hi = map(int, estimate.interval(model, x, x).split("-"))
            self.assertLessEqual(lo, 5 + 2 * x)
            self.assertGreaterEqual(hi, 5 + 2 * x)
            self.assertGreater(hi, lo)

    def test_empirical_band_contains_most_variable_runs(self):
        rows = [row(x, (4 + 2 * x) * noise) for x in range(1, 11)
                for noise in [.4, .6, .8, 1, 1.2, 1.5, 2, 3]]
        model = estimate.calibration("codex", rows)
        hits = sum(int(lo) <= float(r["actual_min"]) <= int(hi)
                   for r in rows for lo, hi in [estimate.interval(model, estimate.mid(r), estimate.mid(r)).split("-")])
        self.assertGreaterEqual(hits / len(rows), .7)
        self.assertLess(hits / len(rows), .95)
        self.assertLess(model[2], 1)
        self.assertGreater(model[3], 1)

    def test_agents_reviews_and_unfinished_rows_are_separate(self):
        codex = [row(x, 4 + 2 * x) for x in range(1, 9)]
        unrelated = [row(x, 999, "claude") for x in range(1, 9)]
        unrelated += [row(1, 999, kind="review"), row("", 999, "claude", kind="review"), row(1, "")]
        self.assertEqual(estimate.calibration("codex", codex + unrelated), estimate.calibration("codex", codex))
        self.assertEqual(estimate.calibration("claude", [row("", 7, "claude", kind="review")])[-2:], (0, False))

    def test_uncalibrated_fallback_and_rounding(self):
        model = estimate.calibration("claude", [row(2, 10, "claude")] * 4)
        self.assertEqual(model, (0, 3, 1, 1.5, 4, False))
        self.assertEqual(estimate.interval(model, 8, 14), "20-65")
        for low, high in [(.01, .01), (1, 1), (1, 2), (8, 14)]:
            lo, hi = map(int, estimate.interval(model, low, high).split("-"))
            self.assertGreaterEqual(lo, 1)
            self.assertGreater(hi, lo)

    def test_equal_rounds_and_outliers_do_not_break_fit(self):
        rows = [row(3, 10)] * 9
        self.assertEqual(estimate.calibration("codex", rows)[-2:], (9, True))
        rows += [row(3, 7900)]
        model = estimate.calibration("codex", rows)
        self.assertAlmostEqual(model[0] + model[1] * 3, 10)
        self.assertLessEqual(model[3], 1.1)

    def test_bad_rounds(self):
        for value in ["0-2", "3-2", "nan-2", "1-inf", "-1-2", "1", "1-2-3"]:
            with self.subTest(value=value), self.assertRaises(Exception):
                estimate.rounds(value)


class LogTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.log = Path(self.folder.name) / "nested" / "estimates.tsv"
        self.env = {**os.environ, "AGENT_ESTIMATES": str(self.log), "PYTHONDONTWRITEBYTECODE": "1"}

    def cli(self, *args, ok=True):
        result = subprocess.run([sys.executable, "-B", str(HERE / "estimate.py"), *args],
                                env=self.env, text=True, capture_output=True, timeout=15)
        if ok:
            self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def start(self, agent="codex", review=False):
        mode = ["--review"] if review else ["1-2"]
        out = self.cli("start", agent, *mode, "--ticket", "TEAM-1", "--task", "PR #42: synthetic run").stdout
        return out.rsplit("id=", 1)[1].strip()

    def rows(self):
        with self.log.open() as f:
            return list(csv.DictReader(f, delimiter="\t"))

    def test_review_logs_actual_only_and_legacy_rows_survive(self):
        self.log.parent.mkdir(parents=True)
        legacy = {field: "" for field in estimate.FIELDS if field != "kind"}
        legacy.update(id="old", started="2026-01-01T00:00:00+00:00", **row(2, 8), task="legacy")
        with self.log.open("w") as f:
            writer = csv.DictWriter(f, list(legacy), delimiter="\t")
            writer.writeheader(); writer.writerow(legacy)
        ident = self.start("claude", review=True)
        self.cli("done", ident, "--actual", "7", "--note", "synthetic review")
        old, review = self.rows()
        self.assertEqual({k: old[k] for k in legacy}, legacy)
        self.assertEqual(review["kind"], "review")
        self.assertEqual(review["agent"], "claude")
        self.assertEqual(review["ticket"], "TEAM-1")
        self.assertIn("PR #42", review["task"])
        self.assertEqual(review["actual_min"], "7")
        for field in ["rounds_low", "rounds_high", "est_min"]:
            self.assertEqual(review[field], "")
        self.assertIn("claude: 3.0 min/round, uncalibrated n=0", self.cli().stdout)

    def test_parallel_starts_and_mixed_completions_keep_every_row(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            ids = list(pool.map(lambda _: self.start(), range(12)))
            self.assertEqual(len(set(ids)), 12)
            self.assertEqual(len(self.rows()), 12)
            operations = [lambda ident=ident: self.cli("done", ident, "--actual", "9") for ident in ids]
            operations += [lambda: self.start("claude", review=True) for _ in range(6)]
            list(pool.map(lambda op: op(), operations))
        rows = self.rows()
        self.assertEqual(len(rows), 18)
        self.assertEqual({r["id"] for r in rows if r["actual_min"] == "9"}, set(ids))
        self.assertEqual(sum(r["kind"] == "review" for r in rows), 6)

    def test_review_elapsed_time_subtracts_human_wait(self):
        ident = self.start("claude", review=True)
        review = self.rows()[0]
        finished = datetime.fromisoformat(review["started"]) + timedelta(minutes=9)
        with patch.object(estimate, "LOG", self.log), patch.object(estimate, "datetime") as clock, \
                patch("sys.stdout", new_callable=io.StringIO):
            clock.now.return_value = finished
            clock.fromisoformat.side_effect = datetime.fromisoformat
            estimate.cmd_done(argparse.Namespace(id=ident, actual=None, wait=2, note="human wait"))
        self.assertEqual(self.rows()[0]["actual_min"], "7")
        self.assertEqual(self.rows()[0]["note"], "human wait")

    def test_direct_cli_waits_for_same_sidecar_lock_as_tk(self):
        with patch.object(estimate, "LOG", self.log), estimate.locked():
            process = subprocess.Popen([sys.executable, "-B", str(HERE / "estimate.py"), "start", "codex", "1-2",
                                        "--task", "synthetic"], env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                with self.assertRaises(subprocess.TimeoutExpired):
                    process.communicate(timeout=.2)
            except BaseException:
                process.kill(); process.communicate(); raise
        stdout, stderr = process.communicate(timeout=15)
        self.assertEqual(process.returncode, 0, stderr)
        self.assertIn(b"id=", stdout)
        self.assertEqual(len(self.rows()), 1)

    def test_atomic_failure_preserves_previous_log(self):
        self.start()
        before = self.log.read_bytes()
        with patch.object(estimate, "LOG", self.log), patch.object(estimate.os, "replace", side_effect=OSError("synthetic")):
            with self.assertRaises(OSError), estimate.locked():
                estimate.write_rows([])
        self.assertEqual(self.log.read_bytes(), before)
        self.assertEqual(list(self.log.parent.glob(".estimate-*")), [])

    def test_invalid_cli_inputs_do_not_write(self):
        cases = [("start", "codex", "--review", "--ticket", "TEAM-1", "--task", "review"),
                 ("start", "claude", "1-2", "--review", "--ticket", "TEAM-1", "--task", "review"),
                 ("start", "claude", "--review", "--task", "review"),
                 ("start", "codex", "0-2", "--task", "run"),
                 ("done", "missing", "--actual", "nan"), ("done", "missing", "--wait", "-1")]
        for args in cases:
            with self.subTest(args=args):
                self.assertNotEqual(self.cli(*args, ok=False).returncode, 0)
        self.assertFalse(self.log.exists())


if __name__ == "__main__":
    unittest.main()
