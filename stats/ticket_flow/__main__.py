"""Pilot entry point: two-ticket coverage slice; full command follows in step 4."""
import argparse
from pathlib import Path
import subprocess
import sys

from . import csvio, gate, github, local, native, sources, stages, tables, timing
from .model import PILOT


def measure(start, end):
    rows, paths, counts = sources.collect_pilot(end)
    turns, unmatched = native.hydrate(paths, rows, tickets=PILOT)
    markers = local.collect_markers(paths, rows)
    remote, prs = github.pilot_markers()
    markers += remote
    turns = [t for t in turns if t.start is None or t.start < end]
    timing.attribute_overlap(turns)
    stages.assign(turns, markers)
    result = tables.assemble(turns, start, end, counts, unmatched, prs, markers)
    lines, failures = gate.numeric_checks(rows, turns, result, start, end)
    return result, lines, failures


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('START')
    parser.add_argument('END')
    args = parser.parse_args(argv)
    try:
        start, end = sources.stamp(args.START), sources.stamp(args.END)
        if start >= end:
            raise ValueError('END must be later than START')
        result, lines, failures = measure(start, end)
        csvio.publish(Path('stats/runs') / f'{args.START}_{args.END}', result)
        print('\n'.join(lines))
        print('PILOT_OUTPUT_WRITTEN; complete enrichment and hand reconciliation not implied')
        return 1 if failures else 0
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(f'ticket_flow: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
