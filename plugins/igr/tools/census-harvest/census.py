#!/usr/bin/env python3
"""
census — SCIP-driven code-census tool for the igr:dev plan method.

Subcommands (the deterministic rails; the model fills the two judgment gaps between them):
  doctor      preflight  : check venv/protobuf/scip_pb2 (exit 2) + the indexer for --lang (exit 1)
  scaffold    P0 assist  : Scope template + candidate entry symbols + boundary preview
  harvest     P1 skeleton: symbols/signatures/edges/boundary-coupling/test-flag  -> skeleton.json
  merge       assemble   : skeleton.json + model's judgment.json -> census.md
  verify-plan P3a        : (A) the plan's claims vs CODE — cites/sigs/return-types/fallibility;
                           (B) the plan vs ITSELF — task/step structure, staging, forward refs,
                           placeholders, red-stage validity.  Exit 3 = HIGH findings.

Boundary is repo-agnostic: name the god-struct(s) you decouple from with --boundary-struct X.
The tool matches SCIP symbols `/X#` (fields + inherent methods) AND `[X]` (trait/impl methods) —
derived from the ONE type name, no trait enumeration. (--boundary-type = raw-substring fallback,
e.g. a module.) A --grep-token receiver cross-check catches anything SCIP misses (macro/dynamic).

Languages (--lang rust|go|ts|none): the SCIP symbol/anchor/edge skeleton is generic; --lang selects
a per-language adapter (see LANGS + visibility/sig_of/kind_of/parse_sig) for test detection,
visibility, signature source, and sig parsing. Indexer per lang: rust-analyzer scip / scip-go /
scip-typescript. Go/TS drop rust's [Trait]impl boundary dimension; verify-plan sig-diff = rust+go.
"""
import argparse, sys, os, json, re, bisect, shutil
from collections import defaultdict

DEF_ROLE = 0x1
CONTAINER_KINDS = {"Function", "Method", "StaticMethod", "Constructor"}
LANGS = ("rust", "go", "ts", "none")

# ---------- per-language adapters ----------
# The SCIP consumption (symbols / anchors / edges) is language-neutral. These carry the
# per-language bits: test detection, visibility, signature parsing, and whether the boundary
# matcher also looks for a trait/impl symbol encoding ([X], rust-analyzer only).

CFG_TEST = re.compile(r'^\s*#\[\s*cfg\s*\(\s*(any\s*\(\s*)?\s*(test\b|feature\s*=\s*"test-utils")')
TS_TEST_FILE = re.compile(r'(\.(test|spec)\.[cm]?[jt]sx?$)|(^|/)__tests__/')
FN_RE = {                                     # locates the fn NAME; parse_sig finds the param list after it
    "rust": re.compile(r'\bfn\s+(\w+)'),
    "go":   re.compile(r'\bfunc\s+(?:\([^)]*\)\s*\.?\s*)?(\w+)'),   # optional receiver, both forms: func (r T) Name( / scip-go's func (*T).Name(
    "ts":   re.compile(r'\b(?:function\s+)?([A-Za-z_$][\w$]*)\s*(?:<[^>]*>)?\s*\('),
}

def lang_boundary_trait(lang):
    return lang == "rust"                     # only rust-analyzer emits the [Trait]impl encoding

# ---------- shared helpers ----------

def load_index(path, deps):
    sys.path.insert(0, deps); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import scip_pb2
    idx = scip_pb2.Index()
    with open(path, "rb") as f:
        idx.ParseFromString(f.read())
    return idx, scip_pb2

def visibility(lang, sig, name="", src_line=""):
    if lang == "rust":
        if sig.startswith(("pub(crate)", "pub(super)", "pub(in")): return "package"
        if sig.startswith("pub "): return "public"
        return "private"
    if lang == "go":                          # exported iff the identifier starts uppercase
        base = re.split(r'[.:#/]', name.rstrip("()"))[-1] if name else ""
        return "public" if base[:1].isupper() else "private"
    if lang == "ts":                          # from the SOURCE line — scip-typescript hover omits export/private
        s = src_line.strip()
        if not s: return "?"
        if re.search(r'\b(private|#\w)', s) and not s.startswith("export"): return "private"
        if re.search(r'\bprotected\b', s): return "package"
        if s.startswith(("export ", "export default ", "export abstract ")): return "public"
        return "private"                      # top-level non-export = module-local
    return "?"

DOC_FENCE = re.compile(r'```[A-Za-z0-9]*\s*\n?(.*?)```', re.S)
DOC_HOVER_PREFIX = re.compile(r'^\((?:method|property|getter|setter|local var|local function|class|'
                              r'interface|enum|enum member|type|type alias|alias|function|constructor|'
                              r'namespace|module|parameter|var|let|const)\)\s*')

def sig_of(info):
    """Signature text. rust-analyzer fills signature_documentation; scip-typescript / scip-go put the
    type in `documentation` as a fenced code block — fall back to its first code line (hover prefix stripped)."""
    if info.HasField("signature_documentation"):
        t = info.signature_documentation.text.replace("\n", " ").strip()
        if t: return t
    for doc in info.documentation:
        m = DOC_FENCE.search(doc)
        if m:
            for ln in m.group(1).splitlines():
                if ln.strip(): return DOC_HOVER_PREFIX.sub("", ln.strip()).strip()
    return ""

def kind_of(info, KindName, sym):
    """SCIP kind, or inferred from the symbol descriptor when the indexer leaves kind unset
    (scip-typescript emits kind=0). Descriptors: `X#`=type, `f().`=method/fn, `x.`=term, `p/`=namespace."""
    if info.kind: return KindName(info.kind)
    tail = sym.split(" ")[-1]
    if tail.endswith("#"): return "Class"
    if tail.endswith(")."): return "Method" if "#" in tail else "Function"
    if tail.endswith("/"): return "Module"
    if tail.endswith("."): return "Field" if "#" in tail else "Variable"
    return "?"

def strip_comment(line):
    s = line.lstrip()
    if s.startswith(("//", "/*", "*")): return ""
    i = line.find("//")
    return line[:i] if i >= 0 else line

def member_label(sym, structs=()):
    tail = sym.split(" ")[-1].rstrip(".").rstrip("()")
    for n in structs:                     # impl/trait method: ...impl#[Type]..method -> Type::method
        if "[" + n + "]" in tail:
            method = re.split(r'[\]#/]', tail)[-1] or n
            return f"{n}::{method}"
    for seg in reversed(tail.split("/")):
        if "#" in seg: return seg
    return tail.split("/")[-1]

def rust_test_spans(lines):
    """0-based [start,end] spans under a #[cfg(test)]-family attribute (brace-matched)."""
    spans, i, n = [], 0, len(lines)
    while i < n:
        if CFG_TEST.match(lines[i]):
            j = i + 1
            while j < n and (lines[j].strip().startswith("#[") or lines[j].strip() == ""):
                j += 1
            if j >= n: break
            depth, started, k, end = 0, False, j, j
            while k < n:
                for ch in lines[k]:
                    if ch == "{": depth += 1; started = True
                    elif ch == "}": depth -= 1
                if started and depth == 0: end = k; break
                if not started and ";" in lines[k]: end = k; break
                k += 1
            else:
                end = n - 1
            spans.append((i, end)); i = end + 1
        else:
            i += 1
    return spans

def make_boundary(structs, raw_types, trait_match=True):
    # `/X#` = the type descriptor (struct/class + its members) — generic across SCIP indexers.
    # `[X]` = rust-analyzer's trait/impl-method encoding — matched only when trait_match (rust).
    def is_boundary(sym):
        if any(bt in sym for bt in raw_types): return True
        return any(("/" + n + "#") in sym or (trait_match and ("[" + n + "]") in sym) for n in structs)
    def is_member(sym):   # real access (field/method) vs a bare type mention (&Store, Arc<StreamState>)
        if not is_boundary(sym): return False
        if trait_match and any(("[" + n + "]") in sym for n in structs): return True   # impl/trait method = always a member
        tail = sym.rstrip(".").rstrip("()")
        if any(tail.endswith("/" + n + "#") for n in structs): return False
        if any(tail.endswith(bt.rstrip("#") + "#") for bt in raw_types): return False
        return True
    return is_boundary, is_member

def build_tables(idx):
    definfo, def_loc = {}, {}
    refs = defaultdict(list)
    def_by_line = defaultdict(dict)
    for d in idx.documents:
        rp = d.relative_path
        for s in d.symbols:
            if not s.symbol.startswith("local") and "().(" not in s.symbol: definfo.setdefault(s.symbol, s)
        for o in d.occurrences:
            if not o.symbol or o.symbol.startswith("local"): continue
            # scip-typescript emits PARAMETER defs as non-local symbols (`fn().(param)`) ON the fn's
            # def line — last-write-wins in def_by_line would evict the fn as enclosing container and
            # mis-attribute its body's edges/boundary accesses. Sub-fn granularity — skip everywhere.
            if "().(" in o.symbol: continue
            line0 = o.range[0]
            if o.symbol_roles & DEF_ROLE:
                def_loc.setdefault(o.symbol, (rp, line0)); def_by_line[rp][line0] = o.symbol
            else:
                refs[o.symbol].append((rp, line0))
    return definfo, def_loc, refs, def_by_line

def build_test(args, targets):
    src_lines = {}
    for rp in targets:
        try:
            src_lines[rp] = open(os.path.join(args.repo, rp), "r", errors="replace").read().splitlines()
        except OSError:
            src_lines[rp] = []
    lang = args.lang
    test_spans = {}
    for rp in targets:
        spans = rust_test_spans(src_lines[rp]) if lang == "rust" else []   # only rust is span-based
        test_spans[rp] = ([s for s, _ in spans], spans)
    tline = args.test_line
    def is_test_file(rp):                     # go/ts flag whole files by name/path
        if lang == "go": return rp.endswith("_test.go")
        if lang == "ts": return bool(TS_TEST_FILE.search(rp))
        return False
    def is_test(rp, line0, sym):
        if "/tests/" in sym or is_test_file(rp): return True
        starts, spans = test_spans.get(rp, ([], []))
        i = bisect.bisect_right(starts, line0) - 1
        if i >= 0 and spans[i][0] <= line0 <= spans[i][1]: return True
        if tline and line0 + 1 >= tline: return True
        return False
    return src_lines, test_spans, is_test, is_test_file

def build_enclosing(targets, def_by_line, definfo, KindName):
    cont_lines, cont_sym = {}, {}
    for rp in targets:
        lines, m = [], {}
        for line0, sym in def_by_line.get(rp, {}).items():
            info = definfo.get(sym)
            if info and kind_of(info, KindName, sym) in CONTAINER_KINDS:
                lines.append(line0); m[line0] = sym
        lines.sort(); cont_lines[rp] = lines; cont_sym[rp] = m
    def enclosing_fn(rp, line0):
        lines = cont_lines.get(rp) or []
        i = bisect.bisect_right(lines, line0) - 1
        return cont_sym[rp][lines[i]] if i >= 0 else None
    return enclosing_fn

def scan_boundary(idx, targets, is_boundary, is_member, is_test, enclosing_fn, structs):
    edges_out = defaultdict(set)
    bnd_members = defaultdict(set)
    boundary_by_member = defaultdict(list)
    scip_boundary_lines = defaultdict(set)
    typeref = 0
    for d in idx.documents:
        rp = d.relative_path
        if rp not in targets: continue
        for o in d.occurrences:
            if not o.symbol or o.symbol.startswith("local") or (o.symbol_roles & DEF_ROLE): continue
            line0 = o.range[0]
            enc = enclosing_fn(rp, line0)
            if enc is not None: edges_out[enc].add(o.symbol)
            if is_boundary(o.symbol):
                if not is_member(o.symbol):
                    typeref += 1; continue
                lbl = member_label(o.symbol, structs)
                if enc is not None: bnd_members[enc].add(lbl)
                if not is_test(rp, line0, o.symbol):
                    boundary_by_member[lbl].append((rp, line0)); scip_boundary_lines[rp].add(line0)
    return edges_out, bnd_members, boundary_by_member, scip_boundary_lines, typeref

def grep_reconcile(tokens, targets, src_lines, test_spans, scip_boundary_lines, is_test_file=lambda rp: False):
    recon = {"per_file": {}, "grep_only_flags": []}
    pats = [re.compile(r'\b' + re.escape(t) + r'\b\s*\.\s*[A-Za-z_]\w*') for t in tokens]
    if not pats: return recon
    for rp in targets:
        if is_test_file(rp): continue         # the SCIP floor excludes test files — mirror it (go/ts)
        starts, spans = test_spans[rp]
        scip_lines = scip_boundary_lines.get(rp, set())
        hits = 0
        for i, line in enumerate(src_lines[rp]):
            j = bisect.bisect_right(starts, i) - 1
            if j >= 0 and spans[j][0] <= i <= spans[j][1]: continue
            code = strip_comment(line)
            if code and any(p.search(code) for p in pats):
                hits += 1
                if i not in scip_lines:
                    recon["grep_only_flags"].append({"file": rp, "line": i + 1, "text": line.strip()[:120]})
        recon["per_file"][rp] = {"scip_member_lines": len(scip_lines), "grep_hit_lines": hits}
    return recon

# ---------- subcommand: harvest ----------

def cmd_harvest(args):
    targets = set(args.file)
    if not args.json and not args.out: sys.exit("harvest: need --json and/or --out")
    idx, scip = load_index(args.index, args.deps)
    KindName = scip.SymbolInformation.Kind.Name
    structs = args.boundary_struct
    definfo, def_loc, refs, def_by_line = build_tables(idx)
    src_lines, test_spans, is_test, is_test_file = build_test(args, targets)
    enclosing_fn = build_enclosing(targets, def_by_line, definfo, KindName)
    is_boundary, is_member = make_boundary(structs, args.boundary_type, lang_boundary_trait(args.lang))
    edges_out, bnd_members, boundary_by_member, scip_boundary_lines, typeref = \
        scan_boundary(idx, targets, is_boundary, is_member, is_test, enclosing_fn, structs)

    records = []
    for sym, (rp, line0) in def_loc.items():
        if rp not in targets: continue
        if "().(" in sym: continue            # scip-typescript emits parameters as symbols — not census rows
        info = definfo.get(sym)
        if info is None: continue
        sig = sig_of(info)
        name = info.display_name or member_label(sym, structs)
        srcl = src_lines.get(rp, []); src_line = srcl[line0] if 0 <= line0 < len(srcl) else ""
        vis = visibility(args.lang, sig, name, src_line)          # rust=sig, go=name-case, ts=source line
        if args.lang == "rust" and not sig: vis = "?"
        records.append({"symbol": sym, "name": name,
                        "kind": kind_of(info, KindName, sym), "file": rp, "line": line0 + 1,
                        "signature": sig, "visibility": vis,
                        "edges_in": len(refs.get(sym, [])), "edges_out": len(edges_out.get(sym, ())),
                        "boundary_members": sorted(bnd_members.get(sym, ())), "test": is_test(rp, line0, sym)})
    records.sort(key=lambda r: (r["file"], r["line"]))
    boundary_summary = sorted(({"member": k, "accesses": len(v)} for k, v in boundary_by_member.items()),
                              key=lambda x: -x["accesses"])
    recon = grep_reconcile(args.grep_token, targets, src_lines, test_spans, scip_boundary_lines, is_test_file)
    prod = [r for r in records if not r["test"]]
    payload = {"index_tool": idx.metadata.tool_info.version if idx.metadata.tool_info else "",
               "lang": args.lang,
               "files": args.file, "boundary_structs": structs, "boundary_types": args.boundary_type,
               "counts": {"symbols": len(records), "prod": len(prod), "test": len(records) - len(prod),
                          "boundary_accesses": sum(b["accesses"] for b in boundary_summary),
                          "boundary_members": len(boundary_summary), "type_mentions_excluded": typeref,
                          "grep_only_flags": len(recon["grep_only_flags"])},
               "records": records, "boundary_summary": boundary_summary, "reconciliation": recon}
    if args.json:
        with open(args.json, "w") as f: json.dump(payload, f, indent=1)
    if args.out:
        md = ["## Census skeleton (SCIP-harvested; mechanical only — judgment via `census merge`)\n",
              "| symbol | kind | anchor | signature | vis | in | out | boundary members | test? |",
              "|---|---|---|---|---|---|---|---|---|"]
        for r in records:
            sc = ("`"+r["signature"][:90]+"`") if r["signature"] else ""
            md.append(f"| `{r['name']}` | {r['kind']} | {r['file']}:{r['line']} | {sc} | {r['visibility']} "
                      f"| {r['edges_in']} | {r['edges_out']} | {', '.join(r['boundary_members'])} | {'TEST' if r['test'] else ''} |")
        md += ["\n## Boundary coupling (coverage floor — member accesses only, prod)\n", "| member | accesses |\n|---|---|"]
        for b in boundary_summary: md.append(f"| `{b['member']}` | {b['accesses']} |")
        if args.grep_token:
            md.append("\n## SCIP<->grep reconciliation\n| file | SCIP member-lines | grep hit-lines |\n|---|---|---|")
            for rp, r in recon["per_file"].items():
                md.append(f"| {rp} | {r['scip_member_lines']} | {r['grep_hit_lines']} |")
            gof = recon["grep_only_flags"]
            md.append(f"\n**grep-only lines (SCIP didn't resolve — review): {len(gof)}**")
            for g in gof[:40]: md.append(f"- {g['file']}:{g['line']}  `{g['text']}`")
        with open(args.out, "w") as f: f.write("\n".join(md) + "\n")
    c = payload["counts"]
    sys.stderr.write(f"harvest: {c['symbols']} symbols ({c['prod']} prod / {c['test']} test); boundary "
                     f"{c['boundary_accesses']} accesses / {c['boundary_members']} members; "
                     f"{c['grep_only_flags']} grep-only flags\n")

# ---------- subcommand: scaffold (P0 assist) ----------

def cmd_scaffold(args):
    targets = set(args.file)
    idx, scip = load_index(args.index, args.deps)
    KindName = scip.SymbolInformation.Kind.Name
    structs = args.boundary_struct
    definfo, def_loc, refs, def_by_line = build_tables(idx)
    src_lines, test_spans, is_test, _is_test_file = build_test(args, targets)
    enclosing_fn = build_enclosing(targets, def_by_line, definfo, KindName)
    is_boundary, is_member = make_boundary(structs, args.boundary_type, lang_boundary_trait(args.lang))
    _, bnd_members, boundary_by_member, _, _ = \
        scan_boundary(idx, targets, is_boundary, is_member, is_test, enclosing_fn, structs)

    # candidate entries: non-test exported/public fns/methods in target files
    cands = []
    for sym, (rp, line0) in def_loc.items():
        if rp not in targets: continue
        info = definfo.get(sym)
        if info is None or kind_of(info, KindName, sym) not in ("Function", "Method", "StaticMethod"): continue
        if is_test(rp, line0, sym): continue
        sig = sig_of(info)
        name = info.display_name or member_label(sym, structs)
        srcl = src_lines.get(rp, []); src_line = srcl[line0] if 0 <= line0 < len(srcl) else ""
        if visibility(args.lang, sig, name, src_line) == "private": continue
        cands.append((rp, line0 + 1, name, sig, len(bnd_members.get(sym, ()))))
    cands.sort(key=lambda c: (c[0], c[1]))
    boundary_summary = sorted(({"member": k, "accesses": len(v)} for k, v in boundary_by_member.items()),
                              key=lambda x: -x["accesses"])

    out = [f"# Code Census — {', '.join(args.file)}\n",
           "## Scope",
           "*(P0 — SCAFFOLDED by `census scaffold`. PRUNE the candidate entries to the real change "
           "frontier; fill the boundary note + checklist from the spec. This is a starting point, not a decision.)*\n",
           f"### Boundary\ngod-struct(s): {', '.join(structs) or '(none — not a decoupling)'}"
           + (f"  ·  raw: {', '.join(args.boundary_type)}" if args.boundary_type else ""),
           "SCIP match: `/X#` (fields + inherent methods) + `[X]` (trait/impl methods).\n",
           "### Candidate entry symbols (pub/pub(crate) fns in target files — PRUNE to the frontier)",
           "| candidate | anchor | signature | boundary-members touched |", "|---|---|---|---|"]
    for rp, ln, name, sig, bn in cands:
        out.append(f"| `{name}` | {rp}:{ln} | `{sig[:80]}` | {bn} |")
    out += ["\n### Boundary preview (coverage floor — top members)", "| member | accesses |", "|---|---|"]
    for b in boundary_summary[:25]: out.append(f"| `{b['member']}` | {b['accesses']} |")
    # Emitted as an explicit EMPTY hole rather than left to memory: the coverage floor above is
    # SYMBOL-keyed, and an integration test that drives the changed behavior through an
    # HTTP/CLI/queue path names none of these symbols. A real run's symbol reconciliation reported
    # 101 hits / 100% mapped / zero drops and still missed such a file, which then blocked implement.
    out += ["\n### Behavioral nouns (FILL from the spec — P1 greps these too)",
            "*Domain nouns, NOT code identifiers: vendor / provider / feature / entity names. The "
            "symbol grep above cannot see integration tests that reach the behavior without naming a "
            "symbol; P1 runs `rg -irln <noun> <pkg>/test/` for each of these and reconciles both "
            "sweeps. Leaving this empty means the census covers symbols only — say so if that is "
            "deliberate.*",
            "- [ ] ",
            "\n### Coverage checklist (FILL from the spec — what 'done' means)", "- [ ] "]
    with open(args.out, "w") as f: f.write("\n".join(out) + "\n")
    sys.stderr.write(f"scaffold: {len(cands)} candidate entries, {len(boundary_summary)} boundary members "
                     f"-> {args.out}\n")

# ---------- subcommand: merge ----------

def cmd_merge(args):
    skel = json.load(open(args.skeleton)); judg = json.load(open(args.judgment))
    by_anchor = {f"{r['file']}:{r['line']}": r for r in skel["records"]}
    missing = [k for k in judg if k not in by_anchor]
    if missing:
        sys.stderr.write(f"WARNING: {len(missing)} judgment anchors not in skeleton: "
                         + ", ".join(missing[:8]) + ("..." if len(missing) > 8 else "") + "\n")
    chosen = {k: by_anchor[k] for k in judg if k in by_anchor}
    if args.include_untriaged_prod:
        for a, r in by_anchor.items():
            if a not in chosen and not r["test"]: chosen[a] = r
    rows = sorted(chosen.values(), key=lambda r: (r["file"], r["line"]))
    out = ["## Appendix: Code Census\n",
           f"*SCIP-harvested skeleton ({skel['index_tool']}) + model judgment. {len(rows)} in-scope rows. "
           "Anchors re-resolve at implement HEAD.*\n",
           "| symbol | kind | anchor | signature | vis | in | out | boundary | behavior (judgment) | disposition |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        a = f"{r['file']}:{r['line']}"; j = judg.get(a, {})
        sig = ("`"+r["signature"][:80]+"`") if r["signature"] else ""
        out.append(f"| `{r['name']}` | {r['kind']} | {a} | {sig} | {r['visibility']} | {r['edges_in']} "
                   f"| {r['edges_out']} | {', '.join(r['boundary_members'])} "
                   f"| {(j.get('behavior') or '').replace('|', '\\|')} | {(j.get('disposition') or '').replace('|', '\\|')} |")
    c = skel["counts"]
    out += ["\n## Reconciliation (deterministic coverage floor)\n",
            f"- boundary coupling: **{c['boundary_accesses']} member-accesses / {c['boundary_members']} members** "
            f"(prod; {c['type_mentions_excluded']} bare type-mentions excluded).",
            f"- symbols harvested: {c['symbols']} ({c['prod']} prod / {c['test']} test); in-scope: {len(rows)}.",
            f"- SCIP<->grep grep-only flags: {c.get('grep_only_flags', 0)} (review in the skeleton).\n",
            "| boundary member | accesses |\n|---|---|"]
    for b in skel["boundary_summary"]: out.append(f"| `{b['member']}` | {b['accesses']} |")
    with open(args.out, "w") as f: f.write("\n".join(out) + "\n")
    sys.stderr.write(f"merge: {len(rows)} rows -> {args.out}"
                     + (f" ({len(missing)} unmatched judgment keys)" if missing else "") + "\n")

# ---------- subcommand: verify-plan (P3a mechanical pre-pass) ----------

SIG_CFG = {                                   # per-lang sig-diff config; langs absent here -> citations only
    "rust": {"kw": "fn ",   "fallible": "Result"},   # fallibility marker in the return type
    "go":   {"kw": "func ", "fallible": "error"},
}

def _paren_slice(s, oc="(", cc=")"):
    """(inside, rest_after_close) for the first balanced oc..cc in s, else (None, None)."""
    i = s.find(oc)
    if i < 0: return None, None
    depth = 0
    for k in range(i, len(s)):
        if s[k] == oc: depth += 1
        elif s[k] == cc:
            depth -= 1
            if depth == 0: return s[i+1:k], s[k+1:]
    return None, None

def _top_commas(argstr):
    """count top-level (depth-0) comma-separated params, ignoring <> () [] {} nesting."""
    if not argstr.strip(): return 0
    pairs = {'<': '>', '(': ')', '[': ']', '{': '}'}; stack = []; n = 1
    for c in argstr:
        if c in pairs: stack.append(pairs[c])
        elif stack and c == stack[-1]: stack.pop()
        elif c == ',' and not stack: n += 1
    return n

def parse_sig(lang, s):
    """(name, argcount, return_type) from a fn/func/function sig; RT '()' if unit; '' if the type is
    present-but-omitted (deferred pin); None if not parseable. Best-effort per language."""
    s = s.replace("\n", " ")
    rx = FN_RE.get(lang)
    if not rx: return None
    m = rx.search(s)
    if not m: return None
    name = m.group(1)
    p = s.find("(", m.start(1))                      # param list = first '(' at/after the name
    if p < 0: return None
    args, rest = _paren_slice(s[p:])
    if args is None: return None
    rt = "()"
    r = (rest or "").strip()
    if lang == "rust":
        if r.startswith("->"):
            r = r[2:]
            for stop in ("{", " where ", ";"):
                j = r.find(stop)
                if j >= 0: r = r[:j]
            rt = r.strip()                           # "" = arrow present, type omitted (deferred pin)
    elif lang == "ts":
        if r.startswith(":"):
            r = r[1:]
            for stop in ("{", "=>", ";"):
                j = r.find(stop)
                if j >= 0: r = r[:j]
            rt = r.strip()
    elif lang == "go":                               # return type(s) sit between params and the body/EOL
        for stop in ("{", ";"):
            j = r.find(stop)
            if j >= 0: r = r[:j]
        rt = r.strip() or "()"
    return name, _top_commas(args), rt

def norm_rt(lang, rt):
    rt = rt or "()"
    sep = r'\b(?:\w+::)+' if lang == "rust" else r'\b(?:\w+\.)+'   # strip path/pkg qualifiers
    rt = re.sub(sep, '', rt)
    return re.sub(r'\s+', '', rt)

# ---------- plan-internal lint (the structural half of P3a) ----------
#
# The checks above diff the plan against CODE. These check the plan against ITSELF — the
# bookkeeping class that dominated a measured field run (9 codex rounds, 21 defects, nearly all
# plan-authoring churn) even though every one of them is decidable from the plan text for zero
# rounds. Two of those rounds went to contradictions the reviewer's OWN earlier folds introduced.
#
# Parses the `superpowers:writing-plans` task shape (### Task N / **Files:** / **Interfaces:** /
# - [ ] **Step N** / Expected: / git add). That is a coupling to a format this tool does not own,
# so it FAILS SOFT: no recognizable tasks -> STRUCTURE-UNRECOGNIZED and the structural half is
# reported as NOT RUN. Never a false clean.

TASK_RE     = re.compile(r'^#{2,4}\s+Task\s+(\d+)\s*[:.]\s*(.*)$')
STEP_RE     = re.compile(r'^\s*[-*]\s*\[[ xX]?\]\s*\*\*\s*Step\s+(\d+)\s*[:.]?\s*(.*?)\*\*')
FILES_RE    = re.compile(r'^\s*[-*]\s*(Create|Modify|Test|Delete)\s*:\s*(.+)$', re.I)
IFACE_RE    = re.compile(r'^\s*[-*]\s*(Consumes|Produces)\s*:\s*(.*)$', re.I)
GITADD_RE   = re.compile(r'\bgit\s+add\s+(.+)$')
EXPECT_RE   = re.compile(r'^\s*(?:\*\*)?\s*Expected\s*(?:\*\*)?\s*:\s*(.+)$', re.I)
FAILSIF_RE  = re.compile(r'\bfails?\s+if\s*:', re.I)
DEFN_RE     = re.compile(r'\b(?:fn|func|function|def|class|interface|type|struct|impl|const|let|var)\s+'
                         r'([A-Za-z_$][\w$]*)')
IDENT_RE    = re.compile(r'[A-Za-z_$][\w$]*')
TESTY_RE    = re.compile(r'\btest|\bspec\b', re.I)
# keywords + assertion vocabulary: present in every test body, so they carry no signal about WHAT
# a test exercises — dropped from the vacuity comparison and from its (human-read) evidence list.
STOP_IDENTS = frozenset("""_ fn func function def class const let var return import from export await async
new self this t T err error nil None True False true false if else for while match case switch
assert assert_eq assert_ne assert_that expect describe it should toBe toEqual toBeUndefined
require testing Error String int str usize u8 u16 u32 u64 i32 i64 bool void number string boolean""".split())
# writing-plans' own "No Placeholders" list, as a grep. Its Self-Review asks the author to scan for
# these; a regex does it for free and does not get tired on round 9.
PLACEHOLDER_RES = [re.compile(p, re.I) for p in (
    r'\bTBD\b', r'\bTODO\b', r'\bFIXME\b', r'implement later', r'fill in (?:the )?details',
    r'add appropriate error handling', r'\badd validation\b', r'handle edge cases',
    r'similar to task\s+\d', r'write tests for the above')]
# name-shapes that almost always already exist in a repo or its stdlib
REINVENT_RE = re.compile(r'normaliz|canonical|parse|valid|sanitiz|slugif|escape|format|serial', re.I)


def _bt_names(s):
    """Exact names from an Interfaces bullet — backticked only. writing-plans says 'exact function
    names'; requiring backticks keeps prose out of the dependency graph (silence beats noise, and
    the unparsed count is reported so silence stays visible)."""
    out = []
    for raw in re.findall(r'`([^`]+)`', s):
        nm = re.sub(r'[(<].*', '', raw).strip().rstrip(":,.")
        nm = nm.split("::")[-1].split(".")[-1]
        if nm and IDENT_RE.fullmatch(nm): out.append(nm)
    return out


def _paths(s):
    """File paths from a `git add ...` tail: drop flags, shell operators, and the everything-globs
    (`.` / `-A`) — those stage more than the plan declares and can't be diffed against Files:."""
    # `git add <confirmed command path>` — a fill-slot naming no real file. Drop the WHOLE tail, not
    # the bracketed tokens: cherry-picking left the unbracketed middle word ("command") in the
    # staged union. Seen in a real plan.
    if "<" in s or ">" in s: return []
    out = []
    for tok in re.split(r'\s+', s.strip()):
        tok = tok.strip("`'\"")
        if not tok or tok in (".", "-A", "--all", "&&", ";", "\\"): continue
        if tok.startswith("-") or tok.startswith("#"): break
        if tok in ("&&", "||"): break
        if any(c in tok for c in "$*"): continue          # shell var / glob — not a literal path
        out.append(tok)
    return out


def _clean_path(s):
    s = s.strip().strip("`'\"")
    s = re.sub(r'\s*\(.*$', '', s)                  # trailing "(new file)" notes
    return s.split(":")[0].strip().strip("`")       # drop a :123-145 line range


def parse_plan(body):
    """[task] for a writing-plans document; [] when the shape isn't recognized (caller must then
    report UNRECOGNIZED, never a clean bill)."""
    tasks, cur, step, in_fence, fence = [], None, None, False, None
    for i, raw in enumerate(body):
        s = raw.lstrip()
        if s.startswith("```"):
            if in_fence:
                if cur is not None and fence is not None:
                    cur["fences"].append({"lang": fence[0], "line": fence[1],
                                          "code": "\n".join(fence[2]), "step": fence[3]})
                in_fence, fence = False, None
            else:
                in_fence = True
                fence = [s[3:].strip(), i + 1, [], (step["title"] if step else "")]
            continue
        if in_fence:
            if fence is not None: fence[2].append(raw)
            if cur is not None:
                g = GITADD_RE.search(raw)
                if g: cur["git_adds"] += _paths(g.group(1))
            continue
        m = TASK_RE.match(raw)
        if m:
            cur = {"n": int(m.group(1)), "title": m.group(2).strip(), "line": i + 1,
                   "files": [], "consumes": [], "produces": [], "unparsed_iface": 0,
                   "steps": [], "git_adds": [], "fences": []}
            tasks.append(cur); step = None; continue
        if cur is None: continue
        st = STEP_RE.match(raw)
        if st:
            step = {"n": int(st.group(1)), "title": st.group(2).strip(), "line": i + 1,
                    "expected": "", "fails_if": False}
            cur["steps"].append(step); continue
        f = FILES_RE.match(raw)
        if f:
            cur["files"].append((f.group(1).lower(), _clean_path(f.group(2)))); continue
        v = IFACE_RE.match(raw)
        if v:
            names = _bt_names(v.group(2))
            cur[v.group(1).lower()] += names
            if not names and v.group(2).strip(): cur["unparsed_iface"] += 1
            continue
        e = EXPECT_RE.match(raw)
        if e and step is not None:
            step["expected"] = e.group(1).strip(); continue
        if FAILSIF_RE.search(raw) and step is not None: step["fails_if"] = True
        g = GITADD_RE.search(raw)
        if g: cur["git_adds"] += _paths(g.group(1))
    return tasks


def _staged_match(path, staged):
    """A Files: entry counts as staged if some `git add` token names the same file. Tolerant of
    differing relative roots (plan paths are repo-relative; a task may cd) — suffix match both ways."""
    for t in staged:
        if t == path or t.endswith("/" + path) or path.endswith("/" + t): return True
    return False


def lint_plan(tasks, body, index_names=frozenset(), index_locs=None):
    """Plan-vs-itself findings. index_names/index_locs are optional: without an index the
    forward-reference check cannot tell 'consumes a pre-existing repo symbol' from 'consumes
    something nobody defines', so it reports the softer bucket, and reinvention is skipped."""
    L = {"task_gaps": [], "step_gaps": [], "unstaged": [], "no_staging": [], "forward_refs": [],
         "undeclared": [], "placeholders": [], "missing_fails_if": [], "vacuous": [],
         "reinvention": [], "staged_union": [], "unparsed_iface": 0, "drift": [], "recognized": {}}

    # PARTIAL-drift guard. STRUCTURE-UNRECOGNIZED covers the case where nothing parses. The likelier
    # failure is partial: superpowers renames `**Files:**` but keeps `### Task N:`, so tasks parse,
    # files do not, and the staging checks report (0) — indistinguishable from clean. Same for steps:
    # with no `- [ ] **Step N**` match, `Expected:` lines attach to no step, so step-gaps AND
    # red-stage validity both silently vanish. A check that did not run must never read as a pass.
    R = {"tasks": len(tasks),
         "with_files": sum(1 for t in tasks if t["files"]),
         "with_steps": sum(1 for t in tasks if t["steps"]),
         "with_git_add": sum(1 for t in tasks if t["git_adds"]),
         "with_interfaces": sum(1 for t in tasks if t["produces"] or t["consumes"])}
    L["recognized"] = R
    # NB the parser keys on the BULLETS (`- Create:` / `- Modify:` / `- Test:`), not the `**Files:**`
    # header — renaming the header alone does not break it. Name the thing actually matched.
    if tasks and not R["with_files"]:
        L["drift"].append({"field": "- Create:/Modify:/Test: bullets",
                           "dead": "staging checks (unstaged / no-staging)"})
    if tasks and not R["with_steps"]:
        L["drift"].append({"field": "- [ ] **Step N**",
                           "dead": "step-numbering AND red-stage validity (`Expected:` needs a step)"})

    nums = [t["n"] for t in tasks]
    if nums != list(range(1, len(nums) + 1)):
        L["task_gaps"].append({"got": nums, "want": list(range(1, len(nums) + 1))})

    produced = {}                                    # name -> first task number that produces it
    for t in tasks:
        for nm in t["produces"]: produced.setdefault(nm, t["n"])

    for t in tasks:
        L["unparsed_iface"] += t["unparsed_iface"]
        sn = [s["n"] for s in t["steps"]]
        if sn and sn != list(range(1, len(sn) + 1)):
            L["step_gaps"].append({"task": t["n"], "line": t["line"], "got": sn})

        staged = t["git_adds"]; L["staged_union"] += staged
        declared = [p for role, p in t["files"] if role in ("create", "modify", "test")]
        if declared and not staged:
            # one finding for the task, not one per file — a task with no `git add` at all is a
            # single omission (the commit step), and fanning it out buries the precise cases below.
            L["no_staging"].append({"task": t["n"], "line": t["line"], "files": declared})
        else:
            for p in declared:
                if not _staged_match(p, staged):
                    L["unstaged"].append({"task": t["n"], "line": t["line"], "path": p,
                                          "staged": sorted(set(staged))})

        for nm in t["consumes"]:
            src = produced.get(nm)
            if src is not None and src >= t["n"]:
                L["forward_refs"].append({"task": t["n"], "line": t["line"], "name": nm, "from": src})
            elif src is None and nm not in index_names:
                L["undeclared"].append({"task": t["n"], "line": t["line"], "name": nm})

        # red-stage: an `Expected: FAIL` step must say what mutation makes it fail
        for s in t["steps"]:
            if "FAIL" in s["expected"].upper() and not s["fails_if"]:
                L["missing_fails_if"].append({"task": t["n"], "step": s["n"], "line": s["line"]})

        # vacuous-by-construction: the test exercises nothing this task changes, so it is green
        # from an EARLIER task's work and cannot be the red gate the plan claims.
        changed = set(t["produces"])
        tested = set()
        for fc in t["fences"]:
            names = set(DEFN_RE.findall(fc["code"]))
            if TESTY_RE.search(fc["step"] or "") or TESTY_RE.search(fc["lang"] or ""):
                tested |= {x for x in IDENT_RE.findall(fc["code"])
                           if x not in STOP_IDENTS and not TESTY_RE.search(x)}
            else:
                changed |= names
        if changed and tested and not (changed & tested) and \
                any("FAIL" in s["expected"].upper() for s in t["steps"]):
            L["vacuous"].append({"task": t["n"], "line": t["line"],
                                 "changes": sorted(changed)[:6], "tests": sorted(tested)[:6]})

        # Reinvention TRIGGER. Deliberately NOT "an existing same-shape name is nearby": the
        # motivating field case hand-rolled `normalizeHostLabel` two functions away from
        # `httpsOrigin` — a url.Parse-based helper doing the same job under a name matching no
        # shape pattern. Keying on the neighbour's name would have missed the very defect this
        # exists for. So the tool supplies the trigger (this plan adds a normalize/parse/validate-
        # shaped helper) plus the resolve-list (its directory's existing symbols) and the MODEL
        # decides — the same fact-vs-judgment split the rest of the method uses.
        dirs = {os.path.dirname(p) for _r, p in t["files"] if p}
        for nm in sorted(changed):
            if nm in index_names or not REINVENT_RE.search(nm): continue
            near = sorted({en for en, loc in (index_locs or {}).items()
                           if en != nm and loc and os.path.dirname(loc[0]) in dirs})[:8]
            L["reinvention"].append({"task": t["n"], "line": t["line"], "name": nm,
                                     "dirs": sorted(d for d in dirs if d), "near": near})

    L["staged_union"] = sorted(set(L["staged_union"]))

    in_fence = False
    for i, raw in enumerate(body):
        if raw.lstrip().startswith("```"): in_fence = not in_fence; continue
        for rx in PLACEHOLDER_RES:
            m = rx.search(raw)
            if m:
                L["placeholders"].append({"line": i + 1, "hit": m.group(0),
                                          "text": raw.strip()[:100], "in_code": in_fence})
                break
    return L


def cmd_verify_plan(args):
    plan_lines = open(args.plan, errors="replace").read().splitlines()
    # --skeleton/--index are OPTIONAL: without them the code-diff half is skipped and the
    # plan-vs-itself lint still runs (a cheap authoring-time pass, before a census exists).
    skel = json.load(open(args.skeleton)) if args.skeleton else None
    lang = skel.get("lang", "rust") if skel else args.lang
    sig_cfg = SIG_CFG.get(lang) if (skel and args.index) else None   # None -> no sig-diff for this run
    census_names = {r["name"] for r in skel["records"]} if skel else set()
    by_name, index_names, index_locs = defaultdict(list), set(), {}
    if args.index:
        idx, scip = load_index(args.index, args.deps)
        definfo, def_loc, _, _ = build_tables(idx)
        for sym, info in definfo.items():             # name -> [{sig, loc}] across the WHOLE index
            # display_name-or-descriptor fallback, same as harvest records — scip-typescript leaves
            # display_name empty, which would empty the index name-set and mislabel every
            # exists-in-code cite as dangling.
            nm = info.display_name or member_label(sym)
            if not nm: continue
            by_name[nm].append({"sig": sig_of(info), "loc": def_loc.get(sym)})
            index_locs.setdefault(nm, def_loc.get(sym))
        index_names = set(by_name)

    dangling, cite_gap, fallib, typ, argm, ambig = [], [], [], [], [], []

    # claims live in the plan BODY; the folded `## Appendix: Code Census` table is reference data (and
    # its markdown rows would misparse as sigs) — cut it off.
    body = plan_lines
    for i, raw in enumerate(plan_lines):
        if raw.startswith("## Appendix"): body = plan_lines[:i]; break

    # 1. citation validity: every [C:name] resolves to a census row (else: exists-in-code / dangling)
    cites = sorted(set(re.findall(r'\[C:([^\]]+)\]', "\n".join(body))))
    for c in cites:
        nm = c.strip()
        if nm in census_names: continue
        (cite_gap if nm in index_names else dangling).append(nm)

    # 2. pinned sig: return-type / fallibility / arg-count vs the real symbol (by name, from the index).
    # ONLY inside ```-fenced blocks (where sigs are pinned) — skips prose + the census table. Buffer
    # multi-line sigs; strip //-and-/* */ comments; a deferred pin (empty `->`, or a `/*…at HEAD*/`
    # standing in for omitted args/type) is NOT a defect.
    def check_sig(buf, lineno):
        raw_code = " ".join(x.split("//")[0] for x in buf)
        if sig_cfg["kw"] not in raw_code: return     # cheap skip: no fn/func keyword in this fence
        low = " ".join(buf).lower()
        raw_inside, _ = _paren_slice(raw_code)                    # arg text BEFORE comment-strip
        defer_args = (raw_inside is not None and "/*" in raw_inside) or "re-resolve" in low
        p = parse_sig(lang, re.sub(r'/\*.*?\*/', '', raw_code))   # strip block comments for the real parse
        if not p: return
        name, argc, rt = p
        defs = by_name.get(name)
        if not defs: return                          # new/renamed port method — not name-verifiable
        real_rts, real_argcs = set(), set()
        for d in defs:
            rp = parse_sig(lang, re.sub(r'/\*.*?\*/', '', d["sig"])) if d["sig"] else None
            if rp: real_rts.add(norm_rt(lang, rp[2])); real_argcs.add(rp[1])
        if not real_rts: return
        loc = defs[0]["loc"]
        if len(real_rts) > 1:
            ambig.append({"name": name, "line": lineno, "n": len(defs)}); return
        defer_rt = (rt == "") or "re-resolve" in low             # type omitted = deferred pin
        plan_rt = norm_rt(lang, rt); real_rt = next(iter(real_rts))
        F = sig_cfg["fallible"]                       # fallibility marker: rust=Result, go=error
        if not defer_rt and plan_rt != real_rt:
            e = {"name": name, "line": lineno, "plan": rt.strip(), "real": real_rt, "loc": loc}
            (fallib if (F in plan_rt) != (F in real_rt) else typ).append(e)
        if argc not in real_argcs and not defer_args:
            argm.append({"name": name, "line": lineno, "plan": argc, "real": sorted(real_argcs), "loc": loc})

    if sig_cfg:                                       # sig-diff only for langs with a keyword+fallibility model (rust/go)
        in_fence, buf, buf_start = False, [], 0
        for i, raw in enumerate(body):
            if raw.lstrip().startswith("```"):
                if buf: check_sig(buf, buf_start+1); buf = []
                in_fence = not in_fence; continue
            if not in_fence: continue
            if not buf: buf_start = i
            buf.append(raw)
            if ";" in raw or "{" in raw:                         # decl boundary (trait sigs end with ;)
                check_sig(buf, buf_start+1); buf = []

    def sec(title, items, fmt=lambda x: str(x)):
        return [f"\n### {title} ({len(items)})"] + ([f"- {fmt(x)}" for x in items] or ["- none"])

    # 3. plan-vs-itself: the bookkeeping class, decided from the plan text (no model, no rounds).
    tasks = parse_plan(body)
    lint = lint_plan(tasks, body, index_names, index_locs) if tasks else None

    out = ["# verify-plan report",
           f"plan: {args.plan}  ·  index: {(skel or {}).get('index_tool','?')}  ·  census rows: "
           f"{len(census_names)}  ·  cites: {len(cites)}  ·  tasks: {len(tasks)}",
           "\n*Deterministic checks only: (A) structured claims vs CODE — code-block sigs + [C:] cites; "
           "(B) the plan vs ITSELF — task/step structure. FALLIBILITY = high-signal (Result added/dropped). "
           "Type diffs may be intended port abstraction — verify.*"]
    if not skel:
        out.append("\n**NOTE: no --skeleton — census-coverage and citation checks were SKIPPED "
                   "(structure-only run).**")
    if not args.index:
        out.append("\n**NOTE: no --index — every code-diff check was SKIPPED (structure-only run). "
                   "Re-run with --index before treating P3a as done.**")
    if not sig_cfg:
        out.append(f"\n**NOTE: sig-diff UNSUPPORTED for lang={lang} — citations checked only; "
                   "return-type/fallibility/arg-count checks were SKIPPED. The P3b codex angles must "
                   "carry the whole signature surface for this plan.**")
    out += sec("Dangling citations — [C:name] not found in code at all", dangling, lambda x: f"[C:{x}]")
    out += sec("Cited but not in census — exists in code, missing from census rows", cite_gap, lambda x: f"[C:{x}]")
    out += sec("FALLIBILITY mismatches (HIGH — Result invented/dropped)", fallib,
               lambda e: f"plan:{e['line']} `{e['name']}` — plan `{e['plan']}` vs real `{e['real']}`  @{e['loc']}")
    out += sec("Other return-type diffs (candidates — may be intended abstraction)", typ,
               lambda e: f"plan:{e['line']} `{e['name']}` — plan `{e['plan']}` vs real `{e['real']}`  @{e['loc']}")
    out += sec("Arg-count mismatches", argm,
               lambda e: f"plan:{e['line']} `{e['name']}` — plan {e['plan']} vs real {e['real']}  @{e['loc']}")
    out += sec("Ambiguous pins (multiple real defs w/ differing sigs — verify manually)", ambig,
               lambda e: f"plan:{e['line']} `{e['name']}` ({e['n']} defs)")

    out.append("\n## Plan structure (plan vs itself)")
    if lint is None:
        out += ["\n**STRUCTURE-UNRECOGNIZED — no `### Task N:` headings found, so the structural half "
                "did NOT run.** This is not a clean bill. Either the plan is not in "
                "`superpowers:writing-plans` shape, or the shape changed and this parser needs "
                "updating; check the plan by hand before treating P3a as done."]
        nhigh_struct = 0
    else:
        R = lint["recognized"]
        out.append(f"\nrecognized: {R['tasks']} tasks · {R['with_files']} with `Files:` · "
                   f"{R['with_steps']} with steps · {R['with_git_add']} with `git add` · "
                   f"{R['with_interfaces']} with `Interfaces:`")
        if lint["drift"]:
            out.append("\n**PARSER-DRIFT (HIGH) — tasks parsed but a required field did NOT, so the "
                       "checks below that depend on it reported (0) without ever running.** Likely a "
                       "`superpowers:writing-plans` format change; update the parser. Do NOT read "
                       "those sections as clean:")
            out += [f"- `{d['field']}` matched in 0 tasks → dead: {d['dead']}" for d in lint["drift"]]
        out += sec("Task numbering gaps", lint["task_gaps"],
                   lambda e: f"tasks are {e['got']} — expected {e['want']}")
        out += sec("Step numbering gaps (HIGH — a task's steps must be 1..N)", lint["step_gaps"],
                   lambda e: f"plan:{e['line']} Task {e['task']} — steps {e['got']}")
        out += sec("Declared file never staged (HIGH — in Files:, absent from this task's `git add`)",
                   lint["unstaged"],
                   lambda e: f"plan:{e['line']} Task {e['task']} — `{e['path']}` not in {e['staged']}")
        out += sec("Task declares files but has no `git add` at all (HIGH)", lint["no_staging"],
                   lambda e: f"plan:{e['line']} Task {e['task']} — {len(e['files'])} declared: {e['files']}")
        out += sec("Forward references (HIGH — consumes a name a LATER task produces)", lint["forward_refs"],
                   lambda e: f"plan:{e['line']} Task {e['task']} consumes `{e['name']}` — produced by Task {e['from']}")
        out += sec("Undeclared consumes (name not produced by any task and not found in code)",
                   lint["undeclared"],
                   lambda e: f"plan:{e['line']} Task {e['task']} consumes `{e['name']}`")
        out += sec("Placeholders (HIGH — writing-plans forbids these)", lint["placeholders"],
                   lambda e: f"plan:{e['line']} `{e['hit']}`{' [in code block]' if e['in_code'] else ''} — {e['text']}")
        out += sec("`Expected: FAIL` with no `fails if:` clause (HIGH — unverifiable red stage)",
                   lint["missing_fails_if"],
                   lambda e: f"plan:{e['line']} Task {e['task']} Step {e['step']}")
        out += sec("Vacuous-by-construction tests (candidates — test touches nothing this task changes)",
                   lint["vacuous"],
                   lambda e: f"plan:{e['line']} Task {e['task']} — changes {e['changes']}, test names {e['tests']}")
        out += sec("Reinvention candidates (new normalize/parse/validate-shaped helper — read the "
                   "siblings and the stdlib BEFORE accepting it)", lint["reinvention"],
                   lambda e: f"plan:{e['line']} Task {e['task']} adds `{e['name']}` — check {e['dirs'] or '(no dir)'}"
                             + (f", existing there: {e['near']}" if e['near'] else " (no indexed siblings)"))
        out += ["\n### Staged-file union (compare against the scope guard / impl handoff)",
                f"- {len(lint['staged_union'])} files: " + (", ".join(f"`{p}`" for p in lint["staged_union"]) or "none")]
        if lint["unparsed_iface"]:
            out.append(f"\n*{lint['unparsed_iface']} Consumes/Produces entries had no backticked name — "
                       "not checked for forward references. Backtick exact names to include them.*")
        nhigh_struct = sum(len(lint[k]) for k in
                           ("step_gaps", "unstaged", "no_staging", "forward_refs", "placeholders",
                            "missing_fails_if", "drift"))

    nhigh = len(dangling) + len(fallib) + nhigh_struct
    out += [f"\n## Verdict\n**HIGH findings: {nhigh}** "
            + ("— fix or explicitly justify each before P3b." if nhigh else "— none.")]
    text = "\n".join(out) + "\n"
    if args.out:
        with open(args.out, "w") as f: f.write(text)
    sys.stdout.write(text)
    L = lint or {k: [] for k in ("step_gaps", "unstaged", "no_staging", "forward_refs",
                                 "placeholders", "missing_fails_if", "vacuous", "reinvention",
                                 "drift")}
    sys.stderr.write(f"verify-plan: {len(dangling)} dangling, {len(cite_gap)} cite-not-in-census, "
                     f"{len(fallib)} FALLIBILITY, {len(typ)} type-diff, {len(argm)} arg-mismatch, "
                     f"{len(ambig)} ambiguous | structure: "
                     + ("UNRECOGNIZED" if lint is None else
                        f"{len(tasks)} tasks, {len(L['step_gaps'])} step-gaps, "
                        f"{len(L['unstaged']) + len(L['no_staging'])} staging, "
                        f"{len(L['forward_refs'])} forward-refs, {len(L['placeholders'])} placeholders, "
                        f"{len(L['missing_fails_if'])} missing-fails-if, {len(L['vacuous'])} vacuous, "
                        f"{len(L['drift'])} PARSER-DRIFT, "
                        f"{len(L['reinvention'])} reinvention")
                     + f" | HIGH={nhigh}\n")
    # Exit 3 = HIGH findings present. Distinct from 1 (usage) and doctor's 1/2, so a caller can tell
    # "the plan has defects" from "the tool broke". --no-fail restores the old always-0 behavior.
    if nhigh and not args.no_fail:
        sys.exit(3)

# ---------- subcommand: doctor (preflight) ----------

INDEXERS = {"rust": "rust-analyzer", "go": "scip-go", "ts": "scip-typescript", "none": None}
INDEXER_HINT = {
    "rust": "rustup component add rust-analyzer   (or: brew install rust-analyzer)",
    "go":   "install `go`, or: go install github.com/scip-code/scip-go/cmd/scip-go@latest",
    "ts":   "install `bun` (for `bunx @sourcegraph/scip-typescript`) — or `npm i -g @sourcegraph/scip-typescript`",
}
MARK = {"OK": "✓", "FAIL": "✗", "MISSING": "✗", "SKIP": "·"}

def cmd_doctor(args):
    """Single preflight source of truth. Checks the tool's own deps (venv/protobuf/scip_pb2 —
    exit 2 if broken) AND the external indexer for --lang (exit 1 if missing = Path B trigger).
    Run under the `census` wrapper so the interpreter is the tool-local venv python."""
    tool_dir = os.path.dirname(os.path.abspath(__file__))
    venv_py = os.path.join(tool_dir, "venv", "bin", "python")
    ok_marker = os.path.join(tool_dir, "venv", ".deps-ok")
    rows, hard_fail, indexer_fail = [], False, False

    if sys.version_info[:2] >= (3, 12):
        rows.append(("python3", "OK", f"{sys.version.split()[0]}  {sys.executable}"))
    else:
        rows.append(("python3", "FAIL", f"{sys.version.split()[0]} — census.py needs >= 3.12 (f-string syntax); "
                                        "rebuild the venv with a 3.12+ interpreter"))
        hard_fail = True

    if os.path.exists(venv_py):
        rows.append(("venv", "OK", venv_py + ("  (deps-ok)" if os.path.exists(ok_marker) else "  (NO deps-ok marker — build incomplete)")))
    else:
        rows.append(("venv", "FAIL", f"missing {venv_py} — run any census command once to bootstrap, or: "
                                     "python3 -m venv venv && venv/bin/pip install -r requirements.txt"))
        hard_fail = True

    try:
        import google.protobuf as _pb
        rows.append(("protobuf", "OK", getattr(_pb, "__version__", "?")))
    except Exception as e:
        rows.append(("protobuf", "FAIL", f"import google.protobuf failed ({e.__class__.__name__}) — "
                                         "fix: venv/bin/pip install -r requirements.txt"))
        hard_fail = True

    sys.path.insert(0, tool_dir)
    try:
        import scip_pb2  # noqa: F401
        rows.append(("scip_pb2", "OK", "vendored, importable"))
    except Exception as e:
        rows.append(("scip_pb2", "FAIL", f"{e.__class__.__name__}: {e} — regenerate: "
                                         "venv/bin/pip install grpcio-tools && venv/bin/python -m grpc_tools.protoc -I. --python_out=. scip.proto"))
        hard_fail = True

    lang = args.lang
    idx_bin = INDEXERS.get(lang)
    if idx_bin is None:
        rows.append(("indexer", "SKIP", f"lang={lang} needs no external indexer"))
    else:
        path = shutil.which(idx_bin)
        if path:
            rows.append((f"indexer:{lang}", "OK", f"{idx_bin}  {path}"))
        elif lang == "ts" and shutil.which("bunx"):        # zero-install: bunx @sourcegraph/scip-typescript
            rows.append((f"indexer:{lang}", "OK", f"{idx_bin} via `bunx @sourcegraph/scip-typescript`  ({shutil.which('bunx')})"))
        elif lang == "go" and shutil.which("go"):           # zero-install: go run github.com/scip-code/scip-go@latest
            rows.append((f"indexer:{lang}", "OK", f"{idx_bin} via `go run github.com/scip-code/scip-go/cmd/scip-go@latest`  ({shutil.which('go')})"))
        else:
            rows.append((f"indexer:{lang}", "MISSING", f"{idx_bin} not on PATH — {INDEXER_HINT[lang]}"))
            indexer_fail = True

    w = max(len(r[0]) for r in rows)
    for name, st, detail in rows:
        sys.stderr.write(f"  {MARK.get(st, '?')} {name.ljust(w)}  {st:8} {detail}\n")
    if hard_fail:
        sys.stderr.write("census doctor: TOOL BROKEN (venv/protobuf/scip_pb2) — exit 2\n"); sys.exit(2)
    if indexer_fail:
        sys.stderr.write("census doctor: no indexer for this lang -> Path B (live-LSP fallback) — exit 1\n"); sys.exit(1)
    sys.stderr.write("census doctor: all checks passed — exit 0\n")

# ---------- CLI ----------

def main():
    ap = argparse.ArgumentParser(prog="census", description="SCIP-driven code census (scaffold/harvest/merge)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    DEPS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "venv", "lib")

    def add_scip_args(p):
        p.add_argument("--index", required=True); p.add_argument("--repo", default=".")
        p.add_argument("--file", action="append", required=True)
        p.add_argument("--boundary-struct", action="append", default=[],
                       help="god-struct TYPE NAME to decouple from (e.g. Store) — matches /Name# + [Name]")
        p.add_argument("--boundary-type", action="append", default=[],
                       help="advanced: raw SCIP symbol substring (e.g. a module)")
        p.add_argument("--lang", default="rust", choices=list(LANGS))
        p.add_argument("--test-line", type=int, default=None)
        p.add_argument("--deps", default=DEPS)

    h = sub.add_parser("harvest", help="P1: emit the mechanical skeleton")
    add_scip_args(h)
    h.add_argument("--grep-token", action="append", default=[], help="receiver token for the grep cross-check")
    h.add_argument("--json"); h.add_argument("--out"); h.set_defaults(func=cmd_harvest)

    s = sub.add_parser("scaffold", help="P0 assist: Scope template + candidate entries + boundary preview")
    add_scip_args(s); s.add_argument("--out", required=True); s.set_defaults(func=cmd_scaffold)

    m = sub.add_parser("merge", help="assemble census.md from skeleton + judgment")
    m.add_argument("--skeleton", required=True); m.add_argument("--judgment", required=True)
    m.add_argument("--out", required=True); m.add_argument("--include-untriaged-prod", action="store_true")
    m.set_defaults(func=cmd_merge)

    v = sub.add_parser("verify-plan", help="P3a: diff the plan's claims (cites/sigs/return-types) vs SCIP "
                                           "AND lint the plan against itself (task/step structure). Exit 3 = HIGH findings.")
    v.add_argument("--plan", required=True)
    v.add_argument("--skeleton", help="census skeleton.json; omit for a structure-only run")
    v.add_argument("--index", help="SCIP index; omit for a structure-only run")
    v.add_argument("--lang", default="rust", choices=list(LANGS),
                   help="only used when --skeleton is absent (it carries the lang otherwise)")
    v.add_argument("--deps", default=DEPS)
    v.add_argument("--out")
    v.add_argument("--no-fail", action="store_true", help="always exit 0, even with HIGH findings")
    v.set_defaults(func=cmd_verify_plan)

    dc = sub.add_parser("doctor", help="preflight: check venv/protobuf/scip_pb2 (exit 2 if broken) + the indexer for --lang (exit 1 if missing)")
    dc.add_argument("--lang", default="rust", choices=["rust", "go", "ts", "none"])
    dc.set_defaults(func=cmd_doctor)

    args = ap.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
