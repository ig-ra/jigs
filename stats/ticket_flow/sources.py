"""One bridge to the canonical extensionless usage reader and fixed-root discovery."""
from collections import Counter
from functools import lru_cache
import importlib.machinery
import importlib.util
import os
from pathlib import Path

from .model import PILOT

REPOS = (('my/dev-tools/jigs', 'ig-ra/jigs'),
         ('work/condition-curator', 'Sawmills/condition-curator'),
         ('work/agent-platform', 'Sawmills/agent-platform'))


@lru_cache(maxsize=1)
def reader():
    path = Path(__file__).resolve().parents[2] / 'bin/usage'
    loader = importlib.machinery.SourceFileLoader('ticket_flow_usage', str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def stamp(value):
    return reader().stamp(value)


def reference(path, line):
    return f'{path}:{line}'


def repo_for(cwd, home=None):
    home = Path(home or Path.home())
    path = Path(os.path.normpath(cwd or '/'))
    for relative, name in REPOS:
        if path.is_relative_to(home / relative):
            return name
    return None


def raw_records(path, provider, counts=None):
    return reader().json_lines(Path(path), counts if counts is not None else Counter(), provider)


def pilot_roots(home):
    """Directory selection only; ticket attribution stays in the canonical reader."""
    prefix = str(home / 'my/dev-tools').replace('/', '-')
    root = home / '.claude/projects'
    return sorted(p for p in root.iterdir() if p.is_dir() and
                  (p.name == prefix or p.name.startswith(prefix + '-jigs')))


def codex_pilot_files(home):
    root = home / '.codex/sessions'
    if not root.is_dir():
        raise FileNotFoundError(f'Codex log root unavailable: {root}')
    for path in sorted(root.rglob('*.jsonl')):
        records = raw_records(path, 'codex')
        try:
            _, record = next(records)
        except StopIteration:
            continue
        finally:
            records.close()
        meta = record.get('payload') or {}
        cwd = meta.get('cwd')
        if record.get('type') == 'session_meta' and (
                repo_for(cwd, home) == 'ig-ra/jigs' or cwd == str(home / 'my/dev-tools')):
            yield path, meta['id']


def collect_pilot(end, home=None):
    """Retain pre-window context. Step 1 deliberately limits outputs to two tickets."""
    home = home or Path.home()
    rows, paths, counts = [], {}, Counter()
    for root in pilot_roots(home):
        batch, tally = reader().collect(end=end, claude_root=root,
                                        session=('claude', ''))
        rows.extend(batch)
        counts.update(tally)
        paths.update((str(p), 'claude') for p in root.rglob('*.jsonl'))
    for path, session in codex_pilot_files(home):
        batch, tally = reader().collect(end=end, codex_root=path.parent,
                                        session=('codex', session))
        rows.extend(batch)
        counts.update(tally)
        paths[str(path)] = 'codex'
    rows = reader().normalize(rows, counts, end=end)
    rows = [r for r in rows if r.get('ticket') in PILOT]
    return rows, paths, counts


def local_files(home):
    """Fixed lexical roots plus their parent projects; never resolve deleted cwd paths."""
    root = home / '.claude/projects'
    if not root.is_dir():
        raise FileNotFoundError(f'Claude log root unavailable: {root}')
    prefixes = [str(home / relative).replace('/', '-') for relative, _ in REPOS]
    parents = {str((home / relative).parent).replace('/', '-') for relative, _ in REPOS}
    parent_paths = {str((home / relative).parent) for relative, _ in REPOS}
    for project in sorted(root.iterdir()):
        if project.is_dir() and (project.name in parents or any(
                project.name == p or project.name.startswith(p + '-') for p in prefixes)):
            for path in sorted(project.rglob('*.jsonl')):
                # Encoded project names lose slash/hyphen distinctions. Check native cwd.
                records = raw_records(path, 'claude')
                try:
                    cwd = next((r['cwd'] for _, r in records if r.get('cwd')), None)
                finally:
                    records.close()
                if cwd is None or repo_for(cwd, home) or cwd in parent_paths:
                    yield path, 'claude'
    root = home / '.codex/sessions'
    if not root.is_dir():
        raise FileNotFoundError(f'Codex log root unavailable: {root}')
    for path in sorted(root.rglob('*.jsonl')):
        records = raw_records(path, 'codex')
        try:
            first = next(records, (None, {}))[1]
        finally:
            records.close()
        cwd = (first.get('payload') or {}).get('cwd')
        if first.get('type') == 'session_meta' and (repo_for(cwd, home) or cwd in parent_paths):
            yield path, 'codex'


def collect_local(end, home=None):
    """Canonical reader collection without a start cutoff, preserving earlier context."""
    home = Path(home or Path.home())
    paths, rows, counts = {}, [], Counter()
    for path, provider in local_files(home):
        # The exact path session filter selects one file through canonical collect().
        batch, tally = reader().collect(end=end, session=(provider, str(path)), **{
            provider + '_root': path.parent})
        rows.extend(batch)
        counts.update(tally)
        paths[str(path)] = provider
    rows = reader().normalize(rows, counts, end=end)
    for row in rows:
        row['repo'] = repo_for(row.get('cwd'), home)
    return rows, paths, counts
