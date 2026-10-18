"""Hydrate native turns without parsing token counters a second time."""
from collections import defaultdict
from bisect import bisect_right
from datetime import timedelta
from pathlib import Path

from .model import Turn
from .sources import raw_records, reader, reference, repo_for, stamp
from .timing import minutes


def ticket_index(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[row['provider'], row['session_id']].append((stamp(row['timestamp']), row.get('ticket')))
    return {session: sorted(values, key=lambda pair: pair[0]) for session, values in groups.items()}


def ticket_at(index, session, time, cwd=None, provider='claude'):
    ticket = reader().ticket_from_cwd(cwd)
    if ticket:
        return ticket
    if time is None:
        return None
    candidates = index.get((provider, session), [])
    position = bisect_right([item[0] for item in candidates], time) - 1
    return candidates[position][1] if position >= 0 else None


def make_turn(provider, session, identity, path, line, calls, end, duration,
              rows, cwd=None, start=None, parent=None):
    first = min(calls, key=lambda c: stamp(c['timestamp'])) if calls else None
    interval = end - timedelta(minutes=duration) if duration is not None else start
    basis = 'native_start' if start else ('first_call' if first else 'duration_record')
    start = start or (stamp(first['timestamp']) if first else interval)
    ticket = first.get('ticket') if first else ticket_at(rows, session, start or end, cwd, provider)
    turn = Turn(provider, session, str(identity), ticket, repo_for(cwd), start, end,
                basis, reference(path, line), duration, interval, parent, calls)
    turn.ticket_basis = first.get('ticket_basis') if first else ('cwd' if reader().ticket_from_cwd(cwd) else 'prior_session_marker')
    return turn


def claude_turns(path, rows, calls):
    session, pending, seen, used, result = path.stem, {}, set(), set(), []
    parent = path.parts[path.parts.index('subagents') - 1] if 'subagents' in path.parts else None
    last_time, cwd, last_line, start = None, None, 0, None
    for number, record in raw_records(path, 'claude'):
        if not record.get('timestamp'):
            continue
        last_time, last_line = stamp(record['timestamp']), number
        cwd = record.get('cwd') or cwd
        message = record.get('message') or {}
        content = message.get('content', [])
        if record.get('type') == 'user' and not pending and (isinstance(content, str) or any(
                b.get('type') == 'text' for b in content)):
            start = start or last_time
        call = calls.get(('claude', message.get('id')))
        if call and call['session_id'] == session and call['id'] not in used:
            pending[call['id']] = call
        if record.get('subtype') != 'turn_duration':
            continue
        identity = record.get('uuid') or f'{path}:{number}'
        if identity in seen:
            continue
        seen.add(identity)
        duration = record['durationMs'] / 60000 if not parent else None
        result.append(make_turn('claude', session, identity, path, number,
                                list(pending.values()), last_time, duration, rows,
                                cwd, start=start, parent=parent))
        used.update(pending)
        pending.clear()
        start = None
    if pending or start:
        first = next(iter(pending), f'user-{last_line}')
        result.append(make_turn('claude', session, 'open-' + first, path, last_line,
                                list(pending.values()), None, None, rows, cwd,
                                start=start, parent=parent))
    return result


def codex_turns(path, rows, calls):
    session, cwd, parent = path.stem, None, None
    metadata_seen = False
    starts, complete, grouped, result = {}, {}, defaultdict(dict), []
    for number, record in raw_records(path, 'codex'):
        payload = record.get('payload') or {}
        if record.get('type') == 'session_meta' and not metadata_seen:
            session, cwd = payload['id'], payload.get('cwd')
            source = payload.get('source') or {}
            subagent = source.get('subagent', {}) if isinstance(source, dict) else {}
            spawn = subagent.get('thread_spawn', {}) if isinstance(subagent, dict) else {}
            parent = payload.get('parent_thread_id') or spawn.get('parent_thread_id')
            metadata_seen = True
        if record.get('type') == 'turn_context':
            cwd = payload.get('cwd', cwd)
        if not record.get('timestamp'):
            continue
        time = stamp(record['timestamp'])
        kind, identity = payload.get('type'), payload.get('turn_id')
        if record.get('type') == 'event_msg' and identity:
            if kind == 'task_started':
                starts.setdefault(identity, (time, number, cwd))
            elif kind == 'task_complete':
                complete.setdefault(identity, (time, number, cwd))
        usage = payload if record.get('type') == 'token_usage_record' else (
            payload.get('latest_token_usage_record') if record.get('type') == 'compacted' else None)
        if usage:
            call = calls.get(('codex', usage.get('response_id')))
            if call and call['session_id'] == session:
                grouped[usage.get('turn_id') or 'unidentified'][call['id']] = call
    for identity in sorted(starts.keys() | complete.keys() | grouped.keys()):
        begin, line, turn_cwd = starts.get(identity, (None, 0, cwd))
        end, end_line, _ = complete.get(identity, (None, line, turn_cwd))
        duration = minutes(begin, end) if begin is not None and end is not None else None
        selected = list(grouped[identity].values())
        end_line = end_line or (selected[0]['source']['line'] if selected else line)
        turn = make_turn('codex', session, identity, path, end_line, selected,
                         end, duration, rows, turn_cwd, begin, parent)
        result.append(turn)
    return result, len(starts.keys() - complete.keys())


def hydrate(paths, rows, tickets=None):
    calls = {(r['provider'], r['id']): r for r in rows if r['type'] == 'call'}
    rows = ticket_index(rows)
    turns, unmatched = {}, defaultdict(int)
    for path, provider in sorted(paths.items()):
        file = Path(path)
        if provider == 'claude':
            batch = claude_turns(file, rows, calls)
        else:
            batch, _ = codex_turns(file, rows, calls)
        for turn in batch:
            key = ('claude', turn.identity) if provider == 'claude' and not turn.identity.startswith('open-') else turn.key
            old = turns.get(key)
            if old is None:
                turns[key] = turn
            else:
                quality = lambda t: (t.minutes is not None, t.start_basis == 'native_start', len(t.calls))
                winner = max((old, turn), key=quality)
                winner.calls = list({c['id']: c for c in old.calls + turn.calls}.values())
                turns[key] = winner
    from .children import enrich
    enrich(list(turns.values()), paths, rows)
    if tickets is not None:
        turns = {key: t for key, t in turns.items() if t.ticket in tickets}
    # Each canonical call belongs to one native turn, including copied durations.
    used = set()
    for turn in sorted(turns.values(), key=lambda t: (t.source.rsplit(':', 1)[0], int(t.source.rsplit(':', 1)[1]))):
        selected = []
        for call in turn.calls:
            key = call['provider'], call['id']
            if key not in used:
                selected.append(call)
                used.add(key)
        turn.calls = selected
    for turn in turns.values():
        if turn.provider == 'codex' and turn.start_basis == 'native_start' and turn.minutes is None:
            unmatched[turn.ticket] += 1
    return list(turns.values()), unmatched
