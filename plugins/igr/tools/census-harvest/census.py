#!/usr/bin/env python3
"""
census — SCIP-driven code-census tool for the igr:dev plan method.

Subcommands (the deterministic rails; the model fills the two judgment gaps between them):
  doctor    preflight  : check venv/protobuf/scip_pb2 (exit 2) + the indexer for --lang (exit 1)
  scaffold  P0 assist  : Scope template + candidate entry symbols + boundary preview
  harvest   P1 skeleton: symbols/signatures/edges/boundary-coupling/test-flag  -> skeleton.json
  merge     assemble   : skeleton.json + model's judgment.json -> census.md

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
    out += ["\n### Coverage checklist (FILL from the spec — what 'done' means)", "- [ ] "]
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

def cmd_verify_plan(args):
    plan_lines = open(args.plan, errors="replace").read().splitlines()
    plan_text = "\n".join(plan_lines)
    skel = json.load(open(args.skeleton))
    lang = skel.get("lang", "rust")
    sig_cfg = SIG_CFG.get(lang)                       # None -> this lang gets citation checks only, no sig-diff
    census_names = {r["name"] for r in skel["records"]}
    idx, scip = load_index(args.index, args.deps)
    definfo, def_loc, _, _ = build_tables(idx)
    by_name = defaultdict(list)                       # name -> [{sig, loc}] across the WHOLE index
    for sym, info in definfo.items():
        # display_name-or-descriptor fallback, same as harvest records — scip-typescript leaves
        # display_name empty, which would empty the index name-set and mislabel every
        # exists-in-code cite as dangling.
        nm = info.display_name or member_label(sym)
        if not nm: continue
        sig = sig_of(info)
        by_name[nm].append({"sig": sig, "loc": def_loc.get(sym)})
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

    out = ["# verify-plan report",
           f"plan: {args.plan}  ·  index: {skel.get('index_tool','?')}  ·  census rows: {len(census_names)}  ·  cites: {len(cites)}",
           "\n*Structured claims only (code-block sigs + [C:] cites) — deterministic. "
           "FALLIBILITY = high-signal (Result added/dropped). Type diffs may be intended port abstraction — verify.*"]
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
    text = "\n".join(out) + "\n"
    if args.out:
        with open(args.out, "w") as f: f.write(text)
    sys.stdout.write(text)
    sys.stderr.write(f"verify-plan: {len(dangling)} dangling, {len(cite_gap)} cite-not-in-census, "
                     f"{len(fallib)} FALLIBILITY, {len(typ)} type-diff, {len(argm)} arg-mismatch, {len(ambig)} ambiguous\n")

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

    v = sub.add_parser("verify-plan", help="P3a: diff the plan's factual claims (cites/sigs/return-types) vs SCIP")
    v.add_argument("--plan", required=True); v.add_argument("--skeleton", required=True)
    v.add_argument("--index", required=True); v.add_argument("--deps", default=DEPS)
    v.add_argument("--out")
    v.set_defaults(func=cmd_verify_plan)

    dc = sub.add_parser("doctor", help="preflight: check venv/protobuf/scip_pb2 (exit 2 if broken) + the indexer for --lang (exit 1 if missing)")
    dc.add_argument("--lang", default="rust", choices=["rust", "go", "ts", "none"])
    dc.set_defaults(func=cmd_doctor)

    args = ap.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
