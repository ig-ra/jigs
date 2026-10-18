"""Collect local measurements and timestamped native/estimate markers."""
from pathlib import Path
import re
import subprocess

from .model import Marker
from . import estimates
from .activity import actions
from .invocations import native_review
from .sources import raw_records, reader, reference, repo_for, stamp
from .native import ticket_at, ticket_index


def event_markers(rows):
    markers = []
    for row in rows:
        if row['type'] != 'event':
            continue
        kind = None
        if row.get('event') == 'ticket_command':
            kind = {'start': 'design', 'finish': 'finish'}.get(row['action'])
        elif row.get('event') == 'step':
            if row['status'] == 'fixing':
                kind = 'fix'
            elif row['status'] == 'running':
                kind = 'implement' if row['step'] == 'implement' else (
                    'own_review' if row['step'] == 'reviews' else 'bots_ci')
            elif row['status'] == 'done':
                kind = 'implement' if row['step'] == 'implement' else 'bots_ci'
        if kind:
            markers.append(Marker(row['ticket'], stamp(row['timestamp']), kind,
                                  reference(**row['source']), row.get('repo') or repo_for(row.get('cwd')),
                                  row.get('tool_id')))
    return markers


def estimate_markers(path):
    return estimates.markers(estimates.collect(path))


def invocation_kind(name, arguments):
    skill = str(arguments.get('skill', '')).lower()
    if skill.rsplit(':', 1)[-1] == 'simplify':
        return 'simplify'
    if name.rsplit('.', 1)[-1] in ('Agent', 'Task') and re.search(
            r'\bsimplify\b', arguments.get('description', ''), re.I):
        return 'simplify'
    if native_review(name, arguments):
        return 'native_review'
    return None


def authored_time(sha, repo):
    result = subprocess.run(['git', '-C', str(repo), 'show', '-s', '--format=%aI', sha],
                            capture_output=True, text=True, check=False, timeout=10)
    return stamp(result.stdout.strip()) if result.returncode == 0 else None


def shell_outputs(output):
    """Exec orchestration may wrap shell stdout in one JSON result per line."""
    yield output
    for line in output.splitlines():
        result = reader().arguments(line)
        if result.get('exit_code') == 0 and isinstance(result.get('output'), str):
            yield result['output']


def commit_markers(output, ticket, source, cwd, repo, commit_time):
    result = []
    for text in shell_outputs(output or ''):
        for match in re.finditer(r'^\[[^\]\n]+ ([0-9a-f]{7,40})\]', text, re.M):
            authored = commit_time(match[1], repo)
            if authored is not None:
                result.append(Marker(ticket, authored, 'commit', source,
                                     repo_for(cwd), match[1]))
    return result


def native_markers(paths, rows, repo, commit_time=authored_time):
    result = []
    rows = ticket_index(rows)
    for path, provider in sorted(paths.items()):
        session, cwd, meta_seen = Path(path).stem, None, False
        simplify_group = None
        for line, record in raw_records(path, provider):
            payload = record.get('payload') or {}
            if record.get('type') == 'session_meta' and not meta_seen:
                session, cwd = payload['id'], payload.get('cwd')
                meta_seen = True
            cwd = record.get('cwd') or (payload.get('cwd') if record.get('type') == 'turn_context' else None) or cwd
            if not record.get('timestamp'):
                continue
            time = stamp(record['timestamp'])
            ticket = ticket_at(rows, session, time, cwd, provider)
            if not ticket:
                continue
            source = reference(path, line)
            content = (record.get('message') or {}).get('content', [])
            if record.get('type') == 'user' and isinstance(content, str):
                simplify_group = None
                if re.fullmatch(r'/simplify(?:\s+.*)?', content.strip()) or '<command-name>/simplify</command-name>' in content:
                    simplify_group = source
                    result.append(Marker(ticket, time, 'simplify', source, repo_for(cwd), group=source))
            for identity, name, arguments, output, error in actions(record, provider):
                kind = invocation_kind(name, arguments)
                if kind:
                    group = simplify_group if kind == 'simplify' else None
                    if kind == 'simplify' and name.rsplit('.', 1)[-1] == 'Skill':
                        group = identity or source
                        simplify_group = group
                    result.append(Marker(ticket, time, kind, source, repo_for(cwd), identity, group))
                if not error and reader().successful(output or '', require_exit=provider == 'codex'):
                    result.extend(commit_markers(output, ticket, source, cwd, Path(cwd) if cwd else repo, commit_time))
    return list({(m.ticket, m.time, m.kind, m.source, m.identity): m for m in result}.values())


def collect_markers(paths, rows, home=None, repo=None):
    home = home or Path.home()
    return (event_markers(rows) + estimate_markers(home / '.claude/agent-estimates.tsv') +
            native_markers(paths, rows, repo or Path.cwd()))


def collect(end, home=None):
    """Complete local slice; the entry point's full orchestration is step 4."""
    from . import activity, native, sources, timing
    home = Path(home or Path.home())
    rows, paths, counts = sources.collect_local(end, home)
    activity.enrich(rows, paths)
    turns, unmatched = native.hydrate(paths, rows, end=end)
    dispatches = estimates.collect(home / '.claude/agent-estimates.tsv')
    markers = event_markers(rows) + estimates.markers(dispatches) + native_markers(paths, rows, Path.cwd())
    timing.attribute_overlap(turns)
    timing.attribute_waits(turns, timing.wait_intervals(paths))
    return dict(rows=rows, turns=turns, markers=markers, estimates=dispatches,
                counts=counts, unmatched=unmatched)
