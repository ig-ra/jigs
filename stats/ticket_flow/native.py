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
        groups[row['session_id']].append((stamp(row['timestamp']), row.get('ticket')))
    return {session: sorted(values, key=lambda pair: pair[0]) for session, values in groups.items()}


def ticket_at(index, session, time, cwd=None):
    ticket = reader().ticket_from_cwd(cwd)
    if ticket:
        return ticket
    candidates = index.get(session, [])
    position = bisect_right([item[0] for item in candidates], time) - 1
    return candidates[position][1] if position >= 0 else None


def make_turn(provider, session, identity, path, line, calls, end, duration,
              rows, cwd=None, start=None, parent=None):
    first = min(calls, key=lambda c: stamp(c['timestamp'])) if calls else None
    interval = end - timedelta(minutes=duration) if duration is not None else start
    basis = 'native_start' if start else ('first_call' if first else 'duration_record')
    start = start or (stamp(first['timestamp']) if first else interval)
    ticket = first.get('ticket') if first else ticket_at(rows, session, end, cwd)
    return Turn(provider, session, str(identity), ticket, repo_for(cwd), start, end,
                basis, reference(path, line), duration, interval, parent, calls)


def claude_turns(path, rows, calls):
    session, pending, seen, result = path.stem, {}, set(), []
    parent = path.parts[path.parts.index('subagents') - 1] if 'subagents' in path.parts else None
    last_time, cwd, last_line = None, None, 0
    for number, record in raw_records(path, 'claude'):
        if not record.get('timestamp'):
            continue
        last_time, last_line = stamp(record['timestamp']), number
        cwd = record.get('cwd') or cwd
        message = record.get('message') or {}
        call = calls.get(('claude', message.get('id')))
        if call and call['session_id'] == session:
            pending[call['id']] = call
        if record.get('subtype') != 'turn_duration':
            continue
        identity = record.get('uuid') or f'{path}:{number}'
        if identity in seen:
            continue
        seen.add(identity)
        duration = record['durationMs'] / 60000
        result.append(make_turn('claude', session, identity, path, number,
                                list(pending.values()), last_time, duration, rows,
                                cwd, parent=parent))
        pending.clear()
    if pending:
        first = next(iter(pending))
        result.append(make_turn('claude', session, 'open-' + first, path, last_line,
                                list(pending.values()), last_time, None, rows, cwd,
                                parent=parent))
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
            if call:
                grouped[usage.get('turn_id') or 'unidentified'][call['id']] = call
    for identity in sorted(starts.keys() | complete.keys() | grouped.keys()):
        begin, line, turn_cwd = starts.get(identity, (None, 0, cwd))
        end, end_line, _ = complete.get(identity, (None, line, turn_cwd))
        duration = minutes(begin, end) if begin is not None and end is not None else None
        selected = list(grouped[identity].values())
        fallback = max((stamp(c['timestamp']) for c in selected), default=begin)
        turn = make_turn('codex', session, identity, path, end_line, selected,
                         end or fallback, duration, rows, turn_cwd, begin, parent)
        result.append(turn)
    return result, len(starts.keys() - complete.keys())


def hydrate(paths, rows):
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
            if turn.ticket not in ('IGR-15', 'IGR-16'):
                continue
            old = turns.get(turn.key)
            if old is None or len(turn.calls) > len(old.calls):
                turns[turn.key] = turn
    for turn in turns.values():
        if turn.provider == 'codex' and turn.start_basis == 'native_start' and turn.minutes is None:
            unmatched[turn.ticket] += 1
    return list(turns.values()), unmatched
