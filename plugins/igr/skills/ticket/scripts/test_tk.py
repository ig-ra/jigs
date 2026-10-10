"""Stdlib regression tests using wholly synthetic fixtures.

Run: python3 -B -m unittest discover -s plugins/igr/skills/ticket/scripts -p test_tk.py
No private repository recordings, IDs, paths, or comment bodies are used.
"""
import argparse
import copy
import csv
from contextlib import contextmanager
import importlib.machinery
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_loader("tk", importlib.machinery.SourceFileLoader("tk", str(HERE / "tk")))
tk = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = tk
SPEC.loader.exec_module(tk)


def fixture(number):
    name = "pr-merged.json" if number == 1 else "pr-open.json"
    return json.loads((HERE / "fixtures" / name).read_text())


def recording(number):
    return fixture(number)["data"]


def parsed(number):
    with patch.object(tk, "graphql", return_value=recording(number)), \
            patch.object(tk, "gh", return_value=fixture(number)["rules"]):
        return tk.pr_data(tk.Context(HERE, "example/repo"), number, thread_details=True)


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
    with patch.object(tk.time, "monotonic", fake.monotonic), patch.object(tk.time, "sleep", fake.sleep):
        yield fake


@contextmanager
def close_setup(path):
    info = {"worktree": str(path), "branch": "owner/team-7", "default_branch": "main", "key": "TEAM-7"}
    ctx = tk.Context(path, "example/repo")
    prs = [{"number": 7, "state": "MERGED", "headRefOid": "head", "mergeCommit": {"oid": "merge"}, "baseRefName": "main"},
           {"number": 8, "state": "CLOSED"},
           {"number": 9, "state": "MERGED", "headRefOid": "old", "mergeCommit": {"oid": "old-merge"}, "baseRefName": "old-base"}]
    def git(*cmd, **kwargs):
        return {"status": "", "rev-parse": "head" if cmd[1] == "HEAD" else "origin",
                "ls-remote": "origin\trefs/heads/main", "merge-base": ""}[cmd[0]]
    with patch.dict(os.environ, {"HERDR_ENV": "1"}), \
            patch.object(ctx, "git", side_effect=git) as git_api, patch.object(tk, "gh", return_value=prs) as api, \
            patch.object(tk, "herdr", return_value={"panes": []}) as panes:
        yield ctx, info, prs, git, git_api, api, panes


@contextmanager
def ticket_setup():
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder).resolve() / "repo"
        root.mkdir()
        ctx = tk.Context(root)
        ctx.git("init", "-b", "main")
        ctx.git("config", "user.name", "Owner Example")
        ctx.git("config", "user.email", "owner@example.invalid")
        (root / "README.md").write_text("synthetic repo\n")
        ctx.git("add", "README.md")
        ctx.git("commit", "-m", "test: initial fixture")
        ctx.git("update-ref", "refs/remotes/origin/main", "HEAD")
        ctx.git("symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")
        (root / ".git" / "info" / "exclude").write_text(".worktrees/\nigr/\n")
        tree = root / ".worktrees" / "owner" / "team-7"
        ctx.git("worktree", "add", "-b", "owner/team-7", str(tree), "main")
        yield root, tree


class PRTests(unittest.TestCase):
    def test_synthetic_merged_and_superseded_failure(self):
        merged = tk.summary(parsed(1))
        self.assertEqual(tk.verdict(merged), 0)
        self.assertEqual(tk.state_line(merged),
                         "MERGED head=11111111 merge=UNKNOWN review=APPROVED queue=-#- "
                         "req_fail=- req_pending=0 checks=known unresolved=0 mergeCommit=44444444")
        retried = tk.summary(parsed(2))
        self.assertEqual(tk.verdict(retried), 0)
        self.assertEqual(retried["unresolved"], 2)
        self.assertEqual(retried["required_failures"], [])

    def test_same_name_workflows_keep_failures_and_fetch_only_latest_retry(self):
        raw = recording(2)
        checks = raw["repository"]["pullRequest"]["commits"]["nodes"][0]["commit"]["statusCheckRollup"]["contexts"]["nodes"]
        for c in checks:
            if c["name"] == "CI" and tk.check_app(c) == 1:
                c["checkSuite"]["workflowRun"]["workflow"] = {"id": "workflow-a"}
        failure = copy.deepcopy(checks[0])
        failure["databaseId"] = 10
        failure["checkSuite"]["workflowRun"] = {"databaseId": 21, "workflow": {"id": "workflow-b"}}
        older = copy.deepcopy(failure)
        older["databaseId"] = 9
        older["checkSuite"]["workflowRun"]["databaseId"] = 20
        checks.extend([older, failure])
        with patch.object(tk, "graphql", return_value=raw), patch.object(tk, "gh", return_value=fixture(2)["rules"]):
            p = tk.pr_data(tk.Context(HERE, "example/repo"), 2)
        self.assertEqual(tk.verdict(tk.summary(p)), 1)
        self.assertEqual({c["databaseId"] for c in p["checks"] if tk.check_app(c) == 1}, {13, 10})
        with patch.object(tk, "pr_data", return_value=p), patch.object(tk, "gh", return_value={"status": "completed"}) as api, \
                patch.object(tk, "run", return_value="Error: synthetic failure") as logs, \
                patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(tk.failures(tk.Context(HERE, "example/repo"), args(pr="2", limit=10)), 1)
        self.assertIn("/runs/21", api.call_args.args[0][1])
        logs.assert_called_once_with(tk.GH + ["api", "--allow-escape-sequences", "repos/example/repo/actions/jobs/10/logs"], HERE)

    def test_pending_context_cancelled_and_unknown(self):
        self.assertEqual(tk.check_verdict({"__typename": "StatusContext", "state": "PENDING"}), 8)
        self.assertEqual(tk.check_verdict({"__typename": "CheckRun", "status": "IN_PROGRESS"}), 8)
        for state in tk.BAD:
            self.assertEqual(tk.check_verdict({"state": state}), 1)
        with self.assertRaises(tk.TkError):
            tk.check_verdict({"state": "NEW_GITHUB_ENUM"})

    def test_empty_checks_and_missing_required_never_pass(self):
        p = parsed(2)
        p["checks"] = []
        self.assertEqual(tk.verdict(tk.summary(p)), 8)
        p["checks"] = [{"isRequired": False, "context": "optional", "state": "SUCCESS"}]
        p["rules"] = []
        p["baseRef"] = {"branchProtectionRule": {"requiredStatusCheckContexts": ["missing"]}}
        self.assertEqual(tk.summary(p)["required_pending"], 1)
        p = parsed(2)
        p["checks"] = [c for c in p["checks"] if tk.check_app(c) != 1]
        self.assertEqual(tk.summary(p)["required_pending"], 1)
        self.assertEqual(tk.verdict(tk.summary(p)), 8)

    def test_required_union_and_absent_bot_stays_pending(self):
        p = parsed(2)
        p["checks"] = [c for c in p["checks"] if c["name"] != "Review"]
        self.assertEqual(tk.summary(p)["required_pending"], 1)
        self.assertEqual(tk.verdict(tk.summary(p)), 8)
        p["baseRef"] = {"branchProtectionRule": {"requiredStatusCheckContexts": ["Build"]}}
        self.assertEqual(tk.summary(p)["required_pending"], 2)
        p["checks"].append({"__typename": "StatusContext", "context": "Build", "state": "SUCCESS", "isRequired": True})
        self.assertEqual(tk.summary(p)["required_pending"], 1)

    def test_new_queued_run_supersedes_success_and_status_contexts_use_creation_time(self):
        p = parsed(2)
        previous = next(c for c in p["checks"] if c["name"] == "CI" and tk.check_app(c) == 1)
        queued = {**previous, "databaseId": 20, "status": "QUEUED", "conclusion": None}
        p["checks"] = tk.latest_checks(p["checks"] + [queued])
        self.assertEqual(tk.summary(p)["required_pending"], 1)
        self.assertEqual(tk.summary(p)["required_failures"], [])
        contexts = [{"__typename": "StatusContext", "context": "status", "state": "SUCCESS", "createdAt": "2026-01-02T00:00:00Z"},
                    {"__typename": "StatusContext", "context": "status", "state": "FAILURE", "createdAt": "2026-01-01T00:00:00Z"}]
        self.assertEqual(tk.latest_checks(contexts), contexts[:1])

    def test_rule_lookup_failure_is_an_error_and_poll_query_omits_bodies(self):
        ctx = tk.Context(HERE, "example/repo")
        with patch.object(tk, "graphql", return_value=recording(2)), patch.object(tk, "gh", side_effect=tk.TkError("rules denied")), \
                self.assertRaisesRegex(tk.TkError, "rules denied"):
            tk.pr_data(ctx, 2)
        self.assertNotIn("comments(", tk.pr_query())
        self.assertIn("comments(", tk.pr_query(thread_details=True))

    def test_independent_pagination_and_head_change(self):
        one, two = recording(2), recording(2)
        p1, p2 = [d["repository"]["pullRequest"] for d in (one, two)]
        p1["reviewThreads"]["pageInfo"] = {"hasNextPage": True, "endCursor": "next"}
        p2["reviewThreads"]["nodes"] = [copy.deepcopy(p1["reviewThreads"]["nodes"][0])]
        p2["reviewThreads"]["nodes"][0]["id"] = "second-page-thread"
        ctx = tk.Context(HERE, "example/repo")
        count = len(tk.latest_checks(p1["commits"]["nodes"][0]["commit"]["statusCheckRollup"]["contexts"]["nodes"]))
        with patch.object(tk, "graphql", side_effect=[one, two]), patch.object(tk, "gh", return_value=fixture(2)["rules"]):
            result = tk.pr_data(ctx, 2)
        self.assertEqual(len(result["checks"]), count)
        self.assertEqual(result["threads"][-1]["id"], "second-page-thread")
        p2["headRefOid"] = "changed"
        with patch.object(tk, "graphql", side_effect=[one, two]), self.assertRaises(tk.TkError):
            tk.pr_data(ctx, 2)

    def test_graphql_errors_are_not_empty_success(self):
        with patch.object(tk, "gh", return_value={"data": {}, "errors": [{"message": "denied"}]}):
            with self.assertRaisesRegex(tk.TkError, "denied"):
                tk.graphql("query{}", {}, HERE)

    def test_merged_does_not_imply_resolved_threads(self):
        s = tk.summary(parsed(1))
        s["unresolved"] = 1
        self.assertEqual(tk.verdict(s, "threads"), 8)
        self.assertEqual(tk.verdict(s, "merged"), 0)

    def test_first_latest_and_bounded_threads(self):
        threads = parsed(2)["threads"]
        lines = tk.thread_lines(threads, 1)
        self.assertIn("more threads", lines[-1])
        for line in lines:
            self.assertLessEqual(len(line), 360)
        thread = copy.deepcopy(threads[0])
        thread["isResolved"] = False
        thread["comments"]["totalCount"] = 3
        thread["latest"]["nodes"] = [{"id": "followup", "body": "latest question", "author": {"login": "bot"}}]
        self.assertIn("  bot: latest question", tk.thread_lines([thread], 1))
        self.assertIn("  … 1 intervening comments", tk.thread_lines([thread], 1))

    def test_watch_quiet_timeout_and_queue_ejection(self):
        p = parsed(2)
        p["checks"] = [{"isRequired": True, "state": "PENDING", "context": "CI"}]
        p["mergeQueueEntry"] = {"state": "QUEUED", "position": 2}
        ejected = copy.deepcopy(p)
        ejected["mergeQueueEntry"] = None
        a = args(pr="2", until="merged", timeout=10, interval=1)
        with patch.object(tk, "pr_data", side_effect=[p, p, ejected]), patch.object(tk.time, "sleep"), \
                patch("sys.stdout", new_callable=io.StringIO) as out:
            code = tk.watch(tk.Context(HERE), a)
        self.assertEqual(code, 1)
        self.assertEqual(len(out.getvalue().splitlines()), 2)
        with patch.object(tk, "pr_data", return_value=p), clock(), \
                patch("sys.stdout", new_callable=io.StringIO) as out:
            self.assertEqual(tk.watch(tk.Context(HERE), a), 124)
        self.assertTrue(out.getvalue().endswith("TIMEOUT\n"))

    def test_reply_receipt_survives_resolve_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            body = Path(folder) / "reply.md"
            body.write_text("literal `$(not a shell)` reply")
            with patch.object(tk, "graphql", side_effect=[
                    {"addPullRequestReviewThreadReply": {"comment": {"url": "https://example/reply"}}},
                    tk.TkError("resolve failed")]) as api, patch("sys.stdout", new_callable=io.StringIO) as out:
                with self.assertRaises(tk.TkError):
                    tk.reply(tk.Context(HERE), args(body=str(body), thread="thread", resolve=True))
            self.assertEqual(api.call_args_list[0].args[1]["b"], body.read_text())
            self.assertEqual(out.getvalue(), "https://example/reply\n")

    def test_enqueue_uses_guarded_queue_mutation_only(self):
        p = parsed(2)
        queued = copy.deepcopy(p)
        queued["mergeQueueEntry"] = {"state": "QUEUED", "position": 4}
        with patch.object(tk, "pr_data", side_effect=[p, queued]), patch.object(tk, "graphql") as api, \
                patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(tk.enqueue(tk.Context(HERE), args(pr="2")), 0)
        self.assertIn("enqueuePullRequest", api.call_args.args[0])
        self.assertEqual(api.call_args.args[1]["h"], p["headRefOid"])

    def test_failure_fetches_logs_only_after_run_completion(self):
        p = parsed(2)
        p["checks"] = [{"isRequired": True, "__typename": "CheckRun", "name": "CI", "status": "COMPLETED",
                        "conclusion": "FAILURE", "databaseId": 42, "checkSuite": {"workflowRun": {"databaseId": 9}}}]
        for status, fetched in [("in_progress", False), ("completed", True)]:
            with self.subTest(status=status), patch.object(tk, "pr_data", return_value=p), \
                    patch.object(tk, "gh", return_value={"status": status}), \
                    patch.object(tk, "run", return_value="\x1b[31mError: failure\x1b[0m") as logs, \
                    patch("sys.stdout", new_callable=io.StringIO) as out:
                self.assertEqual(tk.failures(tk.Context(HERE, "example/repo"), args(pr="2", limit=10)), 1)
            if fetched:
                logs.assert_called_once_with(tk.GH + ["api", "--allow-escape-sequences", "repos/example/repo/actions/jobs/42/logs"], HERE)
                self.assertIn("Error: failure", out.getvalue())
                self.assertNotIn("\x1b", out.getvalue())
            else:
                logs.assert_not_called()
                self.assertIn("logs not fetched", out.getvalue())

    def test_error_lines_strips_ansi_and_caps_output(self):
        matched = tk.error_lines("\x1b[31mError: red\x1b[0m\n" + "FAIL x\n" * 60)
        self.assertEqual(len(matched), 40)
        self.assertEqual(matched[0], "Error: red")

    def test_fail_never_fetches_superseded_failures(self):
        with patch.object(tk, "pr_data", return_value=parsed(2)), patch.object(tk, "gh") as api, \
                patch.object(tk, "run") as logs, patch("sys.stdout", new_callable=io.StringIO) as out:
            self.assertEqual(tk.failures(tk.Context(HERE), args(pr="2", limit=10)), 0)
        api.assert_not_called()
        logs.assert_not_called()
        self.assertEqual(out.getvalue(), "req_fail=0\n")


class LifecycleTests(unittest.TestCase):
    def test_step_preserves_unrelated_fields_and_serializes_updates(self):
        with ticket_setup() as (root, tree):
            band = tree / "igr" / "state.json"
            band.parent.mkdir()
            original = {"ticket": "TEAM-7", "ticketUrl": "https://example/ticket", "custom": {"keep": 1},
                        "reviews": {"status": "done"}, "implement": {"status": "todo", "extra": True}}
            band.write_text(json.dumps(original))
            a = args(key="tEaM-7", owner="test", line="implement", status="running", pr=None,
                     dispatch=False, report=False, actual_minutes=None, ticket_url="https://example/new-ticket", note="new")
            with patch("sys.stdout", new_callable=io.StringIO):
                self.assertEqual(tk.step(tk.Context(root), a), 0)
            state = json.loads(band.read_text())
            self.assertEqual(state["custom"], original["custom"])
            self.assertEqual(state["reviews"], original["reviews"])
            self.assertTrue(state["implement"]["extra"])
            self.assertEqual(state["implement"]["status"], "running")
            self.assertEqual(state["implement"]["note"], "new")
            self.assertEqual(state["ticketUrl"], "https://example/new-ticket")

    def test_prep_uses_worktree_igr_from_root_or_tree(self):
        with ticket_setup() as (root, tree), patch.dict(os.environ, {"HERDR_ENV": "0"}):
            (root / "igr").mkdir()
            for cwd in (root, tree):
                info = tk.prep(tk.Context(cwd), args(key="tEaM-7", owner=None))
                self.assertEqual(info["worktree"], str(tree))
                self.assertEqual(info["local"], str(tree / "igr"))

    def test_dispatch_and_late_report_close_same_estimate(self):
        with ticket_setup() as (root, tree), patch.dict(os.environ, {
                "AGENT_ESTIMATES": str(root / "estimates.tsv")}), \
                patch("sys.stdout", new_callable=io.StringIO):
            base = ["--cwd", str(tree), "step", "TEAM-7", "implement"]
            self.assertEqual(tk.main(base + ["running", "--dispatch", "--agent", "codex", "--rounds", "1-2",
                                           "--task", "synthetic change", "--model", "test"]), 0)
            band = tree / "igr" / "state.json"
            state = json.loads(band.read_text())
            estimate_id = state["tk"]["estimates"]["implement"]
            state["implement"]["note"] = "visible progress"
            band.write_text(json.dumps(state))
            self.assertEqual(tk.main(base + ["done", "--report", "--actual-minutes", "7",
                                           "--note", "late report"]), 0)
            with (root / "estimates.tsv").open() as log:
                rows = list(csv.DictReader(log, delimiter="\t"))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["id"], estimate_id)
            self.assertEqual(rows[0]["actual_min"], "7")
            self.assertEqual(rows[0]["note"], "late report")
            self.assertEqual(json.loads(band.read_text())["tk"]["estimates"], {})
            self.assertEqual(json.loads(band.read_text())["implement"]["note"], "visible progress")
            self.assertEqual(tk.main(base + ["done", "--actual-minutes", "7"]), 2)

    def test_close_proof_checks_head_merge_dirty_stale_and_unpushed(self):
        with tempfile.TemporaryDirectory() as folder, close_setup(Path(folder)) as setup:
            ctx, info, prs, git, git_api, api, panes = setup
            proof = tk.close_proof(ctx, info)
            self.assertEqual(proof["merge_commit"], "merge")
            git_api.assert_any_call("merge-base", "--is-ancestor", "merge", "origin")
            panes.assert_called_once_with(["pane", "list"])
            self.assertIn("--head", api.call_args.args[0])
            self.assertNotIn("--search", api.call_args.args[0])
            with patch.object(ctx, "git", return_value="dirty"), self.assertRaisesRegex(tk.TkError, "dirty"):
                tk.close_proof(ctx, info)
            with patch.object(tk, "gh", return_value=[{**prs[0], "headRefOid": "different"}]), \
                    self.assertRaisesRegex(tk.TkError, "unpushed"):
                tk.close_proof(ctx, info)
            with patch.object(ctx, "git", side_effect=lambda *cmd, **kw: "stale" if cmd[0] == "ls-remote" else git(*cmd, **kw)), \
                    self.assertRaisesRegex(tk.TkError, "stale"):
                tk.close_proof(ctx, info)

    def test_close_sees_root_and_descendant_agents_and_shells(self):
        with tempfile.TemporaryDirectory() as folder, close_setup(Path(folder).resolve()) as setup:
            ctx, info, _, _, _, _, panes = setup
            for cwd in (Path(folder), Path(folder) / "src"):
                with self.subTest(cwd=cwd):
                    agent = {"agent": "codex", "agent_status": "working", "cwd": str(cwd), "pane_id": "w1:p2"}
                    panes.return_value = {"panes": [agent]}
                    with self.assertRaisesRegex(tk.TkError, "not idle"):
                        tk.close_proof(ctx, info)
                    agent["agent_status"] = "idle"
                    self.assertEqual(tk.close_proof(ctx, info)["pane"], "w1:p2")
                    panes.return_value = {"panes": [{"cwd": str(cwd), "pane_id": "w1:p3"}]}
                    with self.assertRaisesRegex(tk.TkError, "other panes"):
                        tk.close_proof(ctx, info)

    def test_close_outside_herdr_skips_pane_api(self):
        with tempfile.TemporaryDirectory() as folder, close_setup(Path(folder)) as setup:
            ctx, info, _, _, _, _, panes = setup
            with patch.dict(os.environ, {"HERDR_ENV": "0"}):
                self.assertIsNone(tk.close_proof(ctx, info)["pane"])
            panes.assert_not_called()

    def test_step_outside_git_and_prep_failure_are_json_errors(self):
        with tempfile.TemporaryDirectory() as folder, \
                patch("sys.stdout", new_callable=io.StringIO) as out:
            self.assertEqual(tk.main(["--cwd", folder, "--json", "step", "TEAM-1", "checks", "done"]), 3)
            self.assertEqual(json.loads(out.getvalue())["result"], "ERROR")
            out.seek(0); out.truncate()
            self.assertEqual(tk.main(["--cwd", folder, "prep", "TEAM-1"]), 3)
            self.assertEqual(json.loads(out.getvalue())["result"], "ERROR")

    def test_ticket_files_ignored_and_deleted_with_worktree(self):
        with ticket_setup() as (root, tree), patch.dict(os.environ, {"HERDR_ENV": "0"}), \
                patch("sys.stdout", new_callable=io.StringIO):
            ctx = tk.Context(root)
            local = tree / "igr"
            local.mkdir()
            (local / "brief.md").write_text("synthetic brief\n")
            exclude = root / ".git" / "info" / "exclude"
            exclude.write_text(".worktrees/\n")
            self.assertIn("igr/", ctx.git("status", "--porcelain", cwd=tree))
            self.assertEqual(tk.main(["--cwd", str(tree), "step", "TEAM-7", "checks", "done"]), 3)
            self.assertFalse((local / "state.json").exists())
            exclude.write_text(".worktrees/\nigr/\n")
            self.assertEqual(ctx.git("check-ignore", "igr", cwd=tree), "igr")
            self.assertEqual(tk.main(["--cwd", str(tree), "step", "TEAM-7", "checks", "done"]), 0)
            self.assertEqual(ctx.git("status", "--porcelain", cwd=tree), "")
            info = tk.prep(ctx, args(key="TEAM-7", owner=None))
            proof = {"pane": None, "branch": info["branch"], "worktree": str(tree), "head": "synthetic-head"}
            with patch.object(tk, "close_proof", return_value=proof):
                self.assertEqual(tk.close(ctx, args(key="TEAM-7", owner=None, mode="apply")), 0)
            self.assertFalse(tree.exists())
            self.assertFalse((root / "igr").exists())

    def test_close_apply_never_removes_caller_worktree(self):
        info = {"worktree": str(HERE), "key": "TEAM-7"}
        with patch.object(tk, "prep", return_value=info), patch.object(tk, "close_proof", return_value={"pane": None}), \
                patch.object(tk.Context, "git") as git, self.assertRaisesRegex(tk.TkError, "own worktree"):
            tk.close(tk.Context(HERE), args(mode="apply"))
        git.assert_not_called()

    def test_nondefault_keys_and_remote_formats(self):
        self.assertEqual(tk.ticket_key("Abc2-123"), "ABC2-123")
        with self.assertRaises(tk.TkError):
            tk.ticket_key("../escape")
        for remote in ("git@github.com:owner/project.git", "https://github.com/owner/project.git",
                       "ssh://git@github.com/owner/project.git"):
            ctx = tk.Context(HERE)
            with patch.object(ctx, "git", return_value=remote):
                self.assertEqual(ctx.slug(), "owner/project")


if __name__ == "__main__":
    unittest.main()
