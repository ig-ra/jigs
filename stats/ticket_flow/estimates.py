"""Dispatch estimates with bounds and original row provenance, read once."""
import csv
import re

from .model import Marker
from .sources import reference, stamp


def bounds(value):
    if not value or not value.strip():
        return None, None
    parts = re.fullmatch(r'\s*(\d+(?:\.\d+)?)(?:\s*[-–]\s*(\d+(?:\.\d+)?))?\s*', value)
    if not parts:
        raise ValueError(f'invalid estimate bounds: {value!r}')
    low, high = float(parts[1]), float(parts[2] or parts[1])
    if high < low:
        raise ValueError(f'reversed estimate bounds: {value!r}')
    return low, high


def collect(path):
    result, seen = [], set()
    with path.open(newline='', encoding='utf-8') as stream:
        for line, row in enumerate(csv.DictReader(stream, delimiter='\t'), 2):
            if not row.get('ticket') or row['id'] in seen:
                continue
            seen.add(row['id'])
            low, high = bounds(row.get('est_min'))
            result.append(dict(ticket=row['ticket'].upper(), identity=row['id'],
                time=stamp(row['started']), agent=row['agent'], task=row.get('task', ''),
                rounds_low=bounds(row.get('rounds_low'))[0],
                rounds_high=bounds(row.get('rounds_high'))[1], minutes_low=low, minutes_high=high,
                actual_minutes=bounds(row.get('actual_min'))[0], source=reference(path, line)))
    return result


def markers(rows):
    result = []
    for row in rows:
        kind = 'review' if row['agent'] == 'claude-review' else (
            'fix' if re.search(r'findings|\bfix|round \d|final review', row['task'].lower()) else 'implement')
        result.append(Marker(row['ticket'], row['time'], kind, row['source'],
                             identity=row['identity'], group=row['identity']))
    return result
