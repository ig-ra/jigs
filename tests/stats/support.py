"""Small synthetic inputs shared by focused ticket-flow tests."""
import json
from pathlib import Path

from stats.ticket_flow.model import Turn
from stats.ticket_flow.sources import stamp


def at(second=0):
    return stamp(f'2026-10-17T00:{second // 60:02}:{second % 60:02}Z')


def call(identity='m1', ticket='IGR-15', time=10, **values):
    row = dict(type='call', provider='claude', id=identity, session_id='session',
               timestamp=at(time).isoformat(), ticket=ticket, ticket_basis='cwd',
               cwd='/repo/.worktrees/igr-15', parent_session_id=None,
               source={'path': 'session.jsonl', 'line': 2}, new_input_tokens=10,
               cache_read_tokens=20, cache_write_tokens=0, output_tokens=5)
    return dict(row, **values)


def turn(identity='t1', ticket='IGR-15', start=10, end=20, **values):
    row = dict(provider='claude', session='session', identity=identity, ticket=ticket,
               repo='ig-ra/jigs', start=at(start), end=at(end), start_basis='first_call',
               source='session.jsonl:3', interval_start=at(start), minutes=(end-start)/60,
               calls=[call()])
    row.update(values)
    return Turn(**row)


def dump(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(r) + '\n' for r in records))
    return path


def claude_records(cwd):
    common = dict(cwd=str(cwd), sessionId='session')
    return [dict(common, type='user', timestamp=at(0).isoformat(),
                 message={'content': '/igr:ticket start IGR-15'}),
            dict(common, type='assistant', timestamp=at(10).isoformat(), message={
                'id': 'm1', 'model': 'claude-sonnet', 'content': [],
                'usage': {'input_tokens': 10, 'cache_read_input_tokens': 20,
                          'cache_creation_input_tokens': 0, 'output_tokens': 5}}),
            dict(common, type='system', subtype='turn_duration', uuid='d1',
                 timestamp=at(20).isoformat(), durationMs=10000)]
