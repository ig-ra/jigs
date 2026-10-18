"""One bridge to the canonical extensionless usage reader; pilot discovery."""
from collections import Counter
from functools import lru_cache
import importlib.machinery
import importlib.util
import os
from pathlib import Path

from .model import PILOT


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
    home = home or Path.home()
    path = Path(os.path.normpath(cwd or '/'))
    for relative, name in (('my/dev-tools/jigs', 'ig-ra/jigs'),
                           ('work/condition-curator', 'Sawmills/condition-curator'),
                           ('work/agent-platform', 'Sawmills/agent-platform')):
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
