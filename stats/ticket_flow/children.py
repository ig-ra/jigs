"""Recorded child identities and launch-family evidence; no majority attribution."""
import json
from pathlib import Path
import re

from .activity import actions
from .sources import raw_records, reference


def family(description):
    text = (description or '').lower()
    for name, pattern in (('simplify', r'\bsimplify\b'),
                          ('review', r'\breview(?:er)?\b'), ('explore', r'\bexplor')):
        if re.search(pattern, text):
            return name
    return None


def launches(paths):
    """Skill -> lens dispatch is a recorded same-turn link, never a time window."""
    result = {}
    for path, provider in sorted(paths.items()):
        active = None
        for line, record in raw_records(path, provider):
            content = (record.get('message') or {}).get('content', [])
            if record.get('type') == 'user' and (isinstance(content, str) or any(
                    b.get('type') == 'text' for b in content)):
                active = None
            for identity, name, args, _, _ in actions(record, provider):
                if name.rsplit('.', 1)[-1] == 'Skill' and str(args.get('skill', '')).split(':')[-1] == 'simplify':
                    active = reference(path, line)
                if name.rsplit('.', 1)[-1] in ('Agent', 'Task', 'spawn_agent'):
                    result[path, identity] = dict(child_type=args.get('subagent_type') or args.get('agent_type'),
                        child_description=args.get('description'), child_family='simplify' if active else family(
                            args.get('description')), child_basis=active or reference(path, line))
    return result


def metadata(path, provider, launch):
    if provider == 'claude':
        sidecar = Path(path).with_suffix('.meta.json')
        if not sidecar.exists():
            return {}
        # A malformed present sidecar is a source failure, not known-empty metadata.
        value = json.loads(sidecar.read_text())
        parts = Path(path).parts
        parent_path = str(Path(*parts[:parts.index('subagents')]).with_suffix('.jsonl')) if 'subagents' in parts else ''
        linked = launch.get((parent_path, value.get('toolUseId')), {})
        description = value.get('description') or linked.get('child_description')
        return dict(child_type=value.get('agentType') or linked.get('child_type'),
                    child_description=description, child_family=linked.get('child_family') or family(description),
                    child_basis=linked.get('child_basis') or str(sidecar))
    for line, record in raw_records(path, provider):
        if record.get('type') != 'session_meta':
            continue
        payload = record.get('payload') or {}
        source = payload.get('source') or {}
        agent = source.get('subagent') if isinstance(source, dict) else None
        spawn = agent.get('thread_spawn', {}) if isinstance(agent, dict) else {}
        role = spawn.get('agent_role') or (agent if isinstance(agent, str) else None)
        return dict(child_type=role, child_description=payload.get('agent_description'),
                    child_family=family(role), child_basis=reference(path, line))
    return {}


def enrich(turns, paths, index):
    from .native import ticket_at
    launch = launches(paths)
    details = {path: metadata(path, provider, launch) for path, provider in sorted(paths.items())}
    for turn in turns:
        if not turn.parent:
            continue
        path = turn.source.rsplit(':', 1)[0]
        for key, value in details.get(path, {}).items():
            setattr(turn, key, value)
        if not turn.ticket and turn.start:
            turn.ticket = ticket_at(index, turn.parent, turn.start, provider=turn.provider)
            if turn.ticket:
                turn.ticket_basis = 'recorded_parent_link'
        for call in turn.calls:
            if not call.get('ticket') and turn.ticket:
                call['ticket'], call['ticket_basis'] = turn.ticket, turn.ticket_basis
    return turns
