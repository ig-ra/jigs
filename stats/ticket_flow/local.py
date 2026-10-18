"""Collect timestamped local and estimate markers for the coverage pilot."""
import csv
from pathlib import Path
import re
import subprocess

from .model import Marker, PILOT
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
        if kind:
            markers.append(Marker(row['ticket'], stamp(row['timestamp']), kind,
                                  reference(**row['source']), repo_for(row.get('cwd'))))
    return markers


def estimate_markers(path):
    if not path.exists():
        raise FileNotFoundError(f'estimate log unavailable: {path}')
    markers = []
    with path.open(newline='') as stream:
        for line, row in enumerate(csv.DictReader(stream, delimiter='\t'), 2):
            if row.get('ticket') not in PILOT:
                continue
            task = row.get('task', '').lower()
            kind = 'review' if row['agent'] == 'claude-review' else (
                'fix' if re.search(r'findings|\bfix|round \d|final review', task) else 'implement')
            markers.append(Marker(row['ticket'], stamp(row['started']), kind,
                                  reference(path, line), identity=row['id']))
    return markers


def invocation_kind(name, arguments):
    skill = str(arguments.get('skill', '')).lower()
    command = arguments.get('command') or arguments.get('cmd') or ''
    if skill.rsplit(':', 1)[-1] == 'simplify':
        return 'simplify'
    if re.search(r'\bcodex-companion(?:\.mjs)?\s+review\b', command):
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


def record_actions(record, provider):
    if provider == 'claude':
        content = (record.get('message') or {}).get('content', [])
        if isinstance(content, list):
            for block in content:
                if block.get('type') == 'tool_use':
                    yield block['name'], block.get('input') or {}, None
                elif block.get('type') == 'tool_result' and not block.get('is_error'):
                    yield '', {}, reader().text_content(block.get('content', ''))
    else:
        payload = record.get('payload') or {}
        kind = payload.get('type')
        if kind in ('function_call', 'custom_tool_call'):
            yield payload.get('name', ''), reader().arguments(
                payload.get('arguments', payload.get('input', ''))), None
        elif kind in ('function_call_output', 'custom_tool_call_output'):
            yield '', {}, reader().text_content(payload.get('output', ''))


def native_markers(paths, rows, repo, commit_time=authored_time):
    result = []
    rows = ticket_index(rows)
    for path, provider in sorted(paths.items()):
        session, cwd = Path(path).stem, None
        for line, record in raw_records(path, provider):
            payload = record.get('payload') or {}
            if record.get('type') == 'session_meta':
                session, cwd = payload['id'], payload.get('cwd')
            cwd = record.get('cwd') or (payload.get('cwd') if record.get('type') == 'turn_context' else None) or cwd
            if not record.get('timestamp'):
                continue
            time = stamp(record['timestamp'])
            ticket = ticket_at(rows, session, time, cwd)
            if ticket not in PILOT:
                continue
            source = reference(path, line)
            for name, arguments, output in record_actions(record, provider):
                kind = invocation_kind(name, arguments)
                if kind:
                    result.append(Marker(ticket, time, kind, source, repo_for(cwd)))
                result.extend(commit_markers(output, ticket, source, cwd, repo, commit_time))
    return list({(m.ticket, m.time, m.kind, m.source, m.identity): m for m in result}.values())


def collect_markers(paths, rows, home=None, repo=None):
    home = home or Path.home()
    return (event_markers(rows) + estimate_markers(home / '.claude/agent-estimates.tsv') +
            native_markers(paths, rows, repo or Path.cwd()))
