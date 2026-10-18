"""Stable CSV formatting and publication after all collection succeeds."""
import csv
import os
from pathlib import Path
import tempfile

from .tables import AUDIT_FIELDS, RUN_FIELDS, STAGE_FIELDS, TICKET_FIELDS

SCHEMAS = {'calls': AUDIT_FIELDS, 'stages': STAGE_FIELDS, 'tickets': TICKET_FIELDS, 'run': RUN_FIELDS}


def cell(value):
    return f'{value:.6f}' if isinstance(value, float) else '' if value is None else str(value)


def write(path, rows, fields):
    ordered = sorted(rows, key=lambda r: tuple(cell(r.get(f)) for f in fields))
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream, lineterminator='\n')
        writer.writerow(fields)
        writer.writerows([cell(row.get(f)) for f in fields] for row in ordered)


def publish(directory, tables):
    directory = Path(directory)
    directory.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.ticket-flow-', dir=directory.parent) as staging:
        for name, fields in SCHEMAS.items():
            write(Path(staging) / f'{name}.csv', tables[name], fields)
        directory.mkdir(exist_ok=True)
        for name in SCHEMAS:
            os.replace(Path(staging) / f'{name}.csv', directory / f'{name}.csv')
