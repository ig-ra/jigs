#!/usr/bin/env python3
"""Golden + unit tests for the census tool.

Run: tests/run   (wraps: venv python -m unittest discover -s tests)

Golden tests run the real CLI against VENDORED .scip indexes (no indexer needed at test
time) and diff outputs vs fixtures/<lang>-mini/goldens/. Regenerate goldens intentionally
with tests/regen.sh and hand-review the diff. Volatile fields (index tool version,
absolute plan path) are masked before comparison. A language with no vendored index or
goldens is skipped loudly, not failed (go until its index is vendored).
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.abspath(os.path.join(HERE, ".."))
CENSUS = os.path.join(TOOL, "census")
FX = os.path.join(HERE, "fixtures")

sys.path.insert(0, TOOL)
import census as C  # noqa: E402  (unit-test the pure helpers directly; stdlib-only at import)

LANGS = {
    "rust": {"dir": "rust-mini", "files": ["src/engine.rs"]},
    "go": {"dir": "go-mini", "files": ["engine/engine.go", "engine/engine_test.go"]},
    "ts": {"dir": "ts-mini", "files": ["src/engine.ts", "src/engine.test.ts"]},
}


def mask(text):
    text = re.sub(r"index: .*? · ", "index: MASKED · ", text)
    text = re.sub(r"plan: \S*plan-defects\.md", "plan: MASKED", text)
    text = re.sub(r"\*SCIP-harvested skeleton \(.*?\) \+", "*SCIP-harvested skeleton (MASKED) +", text)
    return text


def run_census(*argv, check=True):
    p = subprocess.run([CENSUS, *argv], capture_output=True, text=True)
    if check and p.returncode != 0:
        raise AssertionError(f"census {argv[0]} failed rc={p.returncode}\n{p.stderr}")
    return p


def fixture(lang):
    cfg = LANGS[lang]
    d = os.path.join(FX, cfg["dir"])
    if not os.path.exists(os.path.join(d, "index.scip")):
        raise unittest.SkipTest(f"{lang}: no vendored index.scip — run tests/regen.sh with the {lang} indexer installed")
    if not os.path.isdir(os.path.join(d, "goldens")):
        raise unittest.SkipTest(f"{lang}: no goldens/ — run tests/regen.sh")
    return d, cfg["files"]


class GoldenPipeline(unittest.TestCase):
    """harvest / scaffold / merge / verify-plan output == goldens, per language."""

    maxDiff = None

    def _pipeline(self, lang):
        d, files = fixture(lang)
        gold = os.path.join(d, "goldens")
        file_args = [a for f in files for a in ("--file", f)]
        with tempfile.TemporaryDirectory() as tmp:
            skel_json = os.path.join(tmp, "skeleton.json")
            run_census("harvest", "--index", os.path.join(d, "index.scip"), "--repo", d,
                       *file_args, "--boundary-struct", "Store",
                       "--grep-token", "store", "--grep-token", "s", "--lang", lang,
                       "--json", skel_json, "--out", os.path.join(tmp, "skeleton.md"))
            run_census("scaffold", "--index", os.path.join(d, "index.scip"), "--repo", d,
                       *file_args, "--boundary-struct", "Store", "--lang", lang,
                       "--out", os.path.join(tmp, "scaffold.md"))
            run_census("merge", "--skeleton", skel_json,
                       "--judgment", os.path.join(d, "judgment.json"),
                       "--out", os.path.join(tmp, "census-body.md"))
            # --no-fail: the fixture plans are all-defects by design, so verify-plan exits 3
            # (asserted separately in VerifyPlanExit). Same flag regen.sh uses, so the golden
            # text and the compared text come from an identical invocation.
            run_census("verify-plan", "--plan", os.path.join(d, "plan-defects.md"),
                       "--skeleton", skel_json, "--index", os.path.join(d, "index.scip"),
                       "--no-fail", "--out", os.path.join(tmp, "verify-plan.md"))

            got = json.load(open(skel_json))
            want = json.load(open(os.path.join(gold, "skeleton.json")))
            got["index_tool"] = want["index_tool"] = "MASKED"
            self.assertEqual(want, got, f"{lang}: skeleton.json diverged from golden")

            for name in ("skeleton.md", "scaffold.md", "census-body.md", "verify-plan.md"):
                got_t = mask(open(os.path.join(tmp, name)).read())
                want_t = mask(open(os.path.join(gold, name)).read())
                self.assertEqual(want_t, got_t, f"{lang}: {name} diverged from golden")
            return got

    def test_rust(self):
        skel = self._pipeline("rust")
        by_name = {r["name"]: r for r in skel["records"]}
        # trait/impl boundary dimension ([Store]) — rust-only
        self.assertIn("Store::persist", by_name["compact"]["boundary_members"])
        # #[cfg(test)] island flagged, and its boundary touches stay off the floor
        self.assertTrue(by_name["compact_helper"]["test"])
        self.assertNotIn("Store::new", [b["member"] for b in skel["boundary_summary"]])
        # visibility ladder
        self.assertEqual(by_name["compact"]["visibility"], "public")
        self.assertEqual(by_name["plan_compaction"]["visibility"], "package")
        self.assertEqual(by_name["estimate"]["visibility"], "private")
        self.assertEqual(skel["counts"]["grep_only_flags"], 0)

    def test_go(self):
        skel = self._pipeline("go")
        by_name = {r["name"]: r for r in skel["records"]}
        self.assertTrue(any(r["file"].endswith("_test.go") and r["test"] for r in skel["records"]))
        self.assertEqual(by_name["Compact"]["visibility"], "public")
        self.assertEqual(by_name["planCompaction"]["visibility"], "private")

    def test_ts(self):
        skel = self._pipeline("ts")
        by_name = {r["name"]: r for r in skel["records"] if r["name"]}
        # regression: scip-typescript param symbols must not evict the fn as enclosing
        # container (single-line-sig fns lost their edges/boundary attribution)
        self.assertIn("Store#getObject", by_name["compact"]["boundary_members"])
        self.assertIn("Store#stats", by_name["report"]["boundary_members"])
        self.assertGreater(by_name["compact"]["edges_out"], 0)
        # regression: grep cross-check must skip test FILES like the SCIP floor does
        self.assertEqual(skel["counts"]["grep_only_flags"], 0)
        # *.test.ts flagged
        self.assertTrue(by_name["compactHelper"]["test"])
        # visibility from source line
        self.assertEqual(by_name["compact"]["visibility"], "public")
        self.assertEqual(by_name["estimate"]["visibility"], "private")


class VerifyPlanSemantics(unittest.TestCase):
    """Planted defects land in exactly the right buckets (independent of golden text)."""

    def _report(self, lang):
        d, _ = fixture(lang)
        with open(os.path.join(d, "goldens", "verify-plan.md")) as f:
            return f.read()

    def test_rust_buckets(self):
        r = self._report("rust")
        self.assertIn("[C:ghost_fn]", r.split("### Cited but not in census")[0])
        self.assertIn("[C:run]", r.split("### Cited but not in census")[1].split("###")[0])
        self.assertIn("`stats`", r.split("### FALLIBILITY")[1].split("###")[0])
        self.assertIn("`report`", r.split("### Other return-type diffs")[1].split("###")[0])
        self.assertIn("`put_object`", r.split("### Arg-count mismatches")[1].split("###")[0])
        self.assertIn("`estimate`", r.split("### Ambiguous pins")[1])
        # correct + deferred pins must NOT be flagged
        self.assertNotIn("`compact`", r)
        self.assertNotIn("`plan_compaction`", r)

    def test_go_buckets(self):
        r = self._report("go")
        self.assertIn("[C:GhostFn]", r)
        self.assertIn("[C:Run]", r.split("### Cited but not in census")[1].split("###")[0])
        self.assertIn("`Stats`", r.split("### FALLIBILITY")[1].split("###")[0])
        self.assertIn("`PutObject`", r.split("### Arg-count mismatches")[1].split("###")[0])
        self.assertIn("`Report`", r.split("### Ambiguous pins")[1])
        self.assertNotIn("`Compact`", r)
        self.assertNotIn("`MergeRanges`", r)

    def test_ts_degrades_loudly(self):
        r = self._report("ts")
        self.assertIn("sig-diff UNSUPPORTED for lang=ts", r)
        self.assertIn("[C:ghostFn]", r.split("### Cited but not in census")[0])
        # regression: exists-in-code cite classified cite-gap, not dangling
        # (display_name is empty in scip-typescript — member_label fallback)
        self.assertIn("[C:run]", r.split("### Cited but not in census")[1].split("###")[0])
        # the deliberately-wrong ts sig claim must NOT be flagged (sig-diff off)
        self.assertIn("(0)\n- none", r.split("### FALLIBILITY")[1].split("###")[0])


class PlanStructure(unittest.TestCase):
    """The plan-vs-itself lint: planted structural defects land in the right buckets, in every
    language (the checks are language-neutral — same block appended to all three fixtures)."""

    def _report(self, lang):
        d, _ = fixture(lang)
        with open(os.path.join(d, "goldens", "verify-plan.md")) as f:
            return f.read().split("## Plan structure")[1]

    def _bucket(self, report, title):
        return report.split(f"### {title}")[1].split("###")[0]

    def test_structural_buckets_all_langs(self):
        for lang in ("rust", "go", "ts"):
            with self.subTest(lang=lang):
                r = self._report(lang)
                self.assertIn("Task 2 — steps [1, 2, 4]", self._bucket(r, "Step numbering gaps"))
                self.assertIn("Task 2", self._bucket(r, "Declared file never staged"))
                self.assertIn("consumes `render_label` — produced by Task 4",
                              self._bucket(r, "Forward references"))
                self.assertIn("never_defined_thing", self._bucket(r, "Undeclared consumes"))
                self.assertIn("`TODO`", self._bucket(r, "Placeholders"))
                self.assertIn("Task 3 Step 2", self._bucket(r, "`Expected: FAIL` with no"))
                self.assertIn("Task 4", self._bucket(r, "Vacuous-by-construction"))
                self.assertIn("normalize_host", self._bucket(r, "Reinvention candidates"))
                # Task 1 is the clean control for every DEFECT bucket. (It does appear under
                # Reinvention — that bucket is a trigger on the name it adds, not a defect.)
                self.assertNotIn("Task 1", r.split("### Reinvention candidates")[0])
                # tasks are 1..4 — the numbering bucket stays empty
                self.assertIn("- none", self._bucket(r, "Task numbering gaps"))

    def test_consumes_of_existing_code_symbol_not_flagged(self):
        # Task 1 consumes a symbol that exists in the index but no task produces — the index
        # lookup is what keeps that out of `undeclared`.
        for lang, sym in (("rust", "compact"), ("go", "Compact"), ("ts", "compact")):
            with self.subTest(lang=lang):
                self.assertNotIn(f"`{sym}`", self._bucket(self._report(lang), "Undeclared consumes"))

    def test_staged_union_reported(self):
        self.assertIn("3 files:", self._report("rust").split("### Staged-file union")[1])


class VerifyPlanExit(unittest.TestCase):
    """Exit contract: 3 = HIGH findings present (distinct from doctor's 1/2 = env/tool)."""

    def _args(self, lang):
        d, _ = fixture(lang)
        return ["verify-plan", "--plan", os.path.join(d, "plan-defects.md"),
                "--skeleton", os.path.join(d, "goldens", "skeleton.json"),
                "--index", os.path.join(d, "index.scip")]

    def test_exit3_on_high_findings(self):
        self.assertEqual(run_census(*self._args("rust"), check=False).returncode, 3)

    def test_no_fail_restores_exit0(self):
        self.assertEqual(run_census(*self._args("rust"), "--no-fail", check=False).returncode, 0)

    def test_structure_only_run_without_skeleton_or_index(self):
        d, _ = fixture("rust")
        p = run_census("verify-plan", "--plan", os.path.join(d, "plan-defects.md"), check=False)
        self.assertEqual(p.returncode, 3)                      # structural HIGHs alone trip it
        self.assertIn("no --index", p.stdout)                  # and it says what it skipped
        self.assertIn("no --skeleton", p.stdout)
        self.assertIn("Step numbering gaps (HIGH", p.stdout)

    def test_unrecognized_structure_is_loud_not_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = os.path.join(tmp, "not-a-plan.md")
            with open(plan, "w") as f:
                f.write("# A document\n\nNo tasks here at all.\n")
            p = run_census("verify-plan", "--plan", plan, check=False)
            self.assertEqual(p.returncode, 0)                  # no findings -> clean exit
            self.assertIn("STRUCTURE-UNRECOGNIZED", p.stdout)  # but never a clean BILL
            self.assertIn("did NOT run", p.stdout)


class UnitPlanLint(unittest.TestCase):
    PLAN = """
### Task 1: Add a host normalizer

**Files:**
- Create: `src/normalize.rs`
- Test: `src/normalize_test.rs`

**Interfaces:**
- Produces: `normalize_host`

- [ ] **Step 1: Write the failing test**

```rust
fn test_n() { assert_eq!(normalize_host("a"), "a"); }
```

- [ ] **Step 3: Commit**

```bash
git add src/normalize.rs
```
""".splitlines()

    def test_parse_plan(self):
        t = C.parse_plan(self.PLAN)[0]
        self.assertEqual(t["n"], 1)
        self.assertEqual(t["produces"], ["normalize_host"])
        self.assertEqual(t["files"], [("create", "src/normalize.rs"), ("test", "src/normalize_test.rs")])
        self.assertEqual([s["n"] for s in t["steps"]], [1, 3])
        self.assertEqual(t["git_adds"], ["src/normalize.rs"])

    def test_lint_step_gap_and_unstaged(self):
        L = C.lint_plan(C.parse_plan(self.PLAN), self.PLAN)
        self.assertEqual(L["step_gaps"][0]["got"], [1, 3])
        self.assertEqual(L["unstaged"][0]["path"], "src/normalize_test.rs")

    def test_reinvention_points_at_a_differently_named_sibling(self):
        # the field case: a hand-rolled `normalizeHostLabel` beside `httpsOrigin`, whose name
        # matches no shape pattern — so the check must key on the NEW name, not the neighbour's.
        locs = {"httpsOrigin": ("src/resolver.rs", 274), "far": ("other/x.rs", 3)}
        L = C.lint_plan(C.parse_plan(self.PLAN), self.PLAN, set(locs), locs)
        self.assertEqual(L["reinvention"][0]["name"], "normalize_host")
        self.assertEqual(L["reinvention"][0]["near"], ["httpsOrigin"])   # same dir only

    def test_reinvention_without_index_still_triggers(self):
        L = C.lint_plan(C.parse_plan(self.PLAN), self.PLAN)
        self.assertEqual(L["reinvention"][0]["near"], [])
        self.assertEqual(L["reinvention"][0]["dirs"], ["src"])

    def test_unrecognized_shape_yields_no_tasks(self):
        self.assertEqual(C.parse_plan(["# Doc", "prose only", "- [ ] a checkbox"]), [])

    def test_bt_names_requires_backticks(self):
        self.assertEqual(C._bt_names("`render_label`, `Store::persist(x)`"), ["render_label", "persist"])
        self.assertEqual(C._bt_names("the thing produced by the earlier task"), [])

    def test_paths_drops_flags_and_globs(self):
        self.assertEqual(C._paths("src/a.rs tests/b.rs"), ["src/a.rs", "tests/b.rs"])
        self.assertEqual(C._paths("-A"), [])
        self.assertEqual(C._paths("."), [])
        self.assertEqual(C._paths("$OUT/a.rs"), [])
        # a fill-slot tail names no file — drop ALL of it, not just the bracketed tokens
        # (cherry-picking left the bare middle word "command" in a real plan's staged union)
        self.assertEqual(C._paths("<confirmed command path>"), [])

    def test_task_with_no_git_add_is_one_finding_not_one_per_file(self):
        plan = """
### Task 1: T

**Files:**
- Create: `a.rs`
- Modify: `b.rs`
- Test: `c.rs`
""".splitlines()
        L = C.lint_plan(C.parse_plan(plan), plan)
        self.assertEqual(L["unstaged"], [])
        self.assertEqual(len(L["no_staging"]), 1)
        self.assertEqual(L["no_staging"][0]["files"], ["a.rs", "b.rs", "c.rs"])

    def test_clean_path_strips_line_range(self):
        self.assertEqual(C._clean_path("`exact/path/existing.py:123-145`"), "exact/path/existing.py")

    def test_staged_match_tolerates_relative_roots(self):
        self.assertTrue(C._staged_match("pkg/src/a.ts", ["src/a.ts"]))
        self.assertFalse(C._staged_match("src/a.ts", ["src/b.ts"]))

    def test_vacuous_needs_a_failing_stage_and_disjoint_names(self):
        plan = """
### Task 1: T

**Interfaces:**
- Produces: `render_label`

- [ ] **Step 1: Write the failing test**

```rust
fn t() { helper_unrelated(); }
```

- [ ] **Step 2: Run it**

Expected: FAIL with "nope"
fails if: helper_unrelated is deleted
""".splitlines()
        L = C.lint_plan(C.parse_plan(plan), plan)
        self.assertEqual(L["vacuous"][0]["task"], 1)
        self.assertEqual(L["vacuous"][0]["changes"], ["render_label"])
        self.assertNotIn("fn", L["vacuous"][0]["tests"])      # keywords filtered out of the evidence


class UnitAdapters(unittest.TestCase):
    def test_visibility_rust(self):
        self.assertEqual(C.visibility("rust", "pub fn f()"), "public")
        self.assertEqual(C.visibility("rust", "pub(crate) fn f()"), "package")
        self.assertEqual(C.visibility("rust", "fn f()"), "private")

    def test_visibility_go(self):
        # callers pass display_name-or-member_label output: a plain identifier
        self.assertEqual(C.visibility("go", "", name="Compact"), "public")
        self.assertEqual(C.visibility("go", "", name="planCompaction"), "private")

    def test_visibility_ts(self):
        self.assertEqual(C.visibility("ts", "", src_line="export function f() {"), "public")
        self.assertEqual(C.visibility("ts", "", src_line="  private count: number;"), "private")
        self.assertEqual(C.visibility("ts", "", src_line="  protected bump(): void {"), "package")
        self.assertEqual(C.visibility("ts", "", src_line="function local() {"), "private")

    def test_rust_test_spans(self):
        lines = ["fn a() {}", "#[cfg(test)]", "mod tests {", "  fn t() {}", "}", "fn b() {}"]
        self.assertEqual(C.rust_test_spans(lines), [(1, 4)])
        lines2 = ['#[cfg(any(test, feature = "test-utils"))]', "fn helper() {", "}"]
        self.assertEqual(C.rust_test_spans(lines2), [(0, 2)])

    def test_parse_sig(self):
        self.assertEqual(C.parse_sig("rust", "pub fn compact(store: &mut Store, key: &str) -> Result<u64, String>"),
                         ("compact", 2, "Result<u64, String>"))
        self.assertEqual(C.parse_sig("rust", "fn plan_compaction(store: &Store) ->  "),
                         ("plan_compaction", 1, ""))  # deferred pin: arrow, type omitted
        self.assertEqual(C.parse_sig("go", "func (s *Store) GetObject(key string) ([]byte, error)"),
                         ("GetObject", 1, "([]byte, error)"))
        self.assertEqual(C.parse_sig("ts", "function compact(store: Store, key: string): Promise<number>"),
                         ("compact", 2, "Promise<number>"))
        # nested generics/tuples don't split params
        self.assertEqual(C.parse_sig("rust", "fn f(a: HashMap<K, V>, b: (u8, u8)) -> ()")[1], 2)

    def test_norm_rt(self):
        self.assertEqual(C.norm_rt("rust", "store::Stats"), "Stats")
        self.assertEqual(C.norm_rt("go", "store.Stats"), "Stats")
        self.assertEqual(C.norm_rt("rust", "Result<Stats, String>"), "Result<Stats,String>")

    def test_kind_of_inferred_when_kind_unset(self):
        class Info:
            kind = 0
        self.assertEqual(C.kind_of(Info(), None, "p/Store#"), "Class")
        self.assertEqual(C.kind_of(Info(), None, "p/compact()."), "Function")
        self.assertEqual(C.kind_of(Info(), None, "p/Store#stats()."), "Method")
        self.assertEqual(C.kind_of(Info(), None, "p/Store#cfg."), "Field")

    def test_member_label(self):
        self.assertEqual(C.member_label("x impl#[Store]persist().", ("Store",)), "Store::persist")
        self.assertEqual(C.member_label("p/Store#cfg."), "Store#cfg")


class Doctor(unittest.TestCase):
    BARE_PATH = "/usr/bin:/bin"

    def _doctor(self, lang, path):
        return subprocess.run([CENSUS, "doctor", "--lang", lang],
                              capture_output=True, text=True,
                              env={**os.environ, "PATH": path})

    def test_exit0_lang_none(self):
        self.assertEqual(self._doctor("none", self.BARE_PATH).returncode, 0)

    def test_exit1_missing_indexer(self):
        p = self._doctor("rust", self.BARE_PATH)
        self.assertEqual(p.returncode, 1)
        self.assertIn("Path B", p.stderr)

    def test_exit0_with_indexer(self):
        import shutil as sh
        if not sh.which("rust-analyzer"):
            self.skipTest("rust-analyzer not installed")
        self.assertEqual(self._doctor("rust", os.environ["PATH"]).returncode, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
