"""Measure ticket-flow tokens and recorded agent time for two UTC dates (END exclusive)."""
import argparse
from datetime import date
from pathlib import Path
import subprocess
import sys

from . import csvio, github_fetch, local, sources, stages, tables


def measure(start, end):
    collected = local.collect(end)
    tickets = {repo: set() for _, repo in sources.REPOS}
    evidence = collected['rows'] + [vars(t) for t in collected['turns']] + [
        vars(m) for m in collected['markers']]
    for row in evidence:
        if row.get('ticket') and row.get('repo') in tickets:
            tickets[row['repo']].add(row['ticket'])
    remote, prs = github_fetch.collect(tickets)
    markers = collected['markers'] + remote
    stages.assign(collected['turns'], markers)
    return tables.assemble(collected['turns'], start, end, collected['counts'],
                           collected['unmatched'], prs, markers, collected['estimates'])


def utc_date(value):
    if date.fromisoformat(value).isoformat() != value:
        raise ValueError('dates must use YYYY-MM-DD')
    return sources.stamp(value)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('START', help='UTC date, YYYY-MM-DD (inclusive)')
    parser.add_argument('END', help='UTC date, YYYY-MM-DD (exclusive)')
    args = parser.parse_args(argv)
    try:
        start, end = utc_date(args.START), utc_date(args.END)
        if start >= end:
            raise ValueError('END must be later than START')
        result = measure(start, end)
        directory = Path('stats/runs') / f'{args.START}_{args.END}'
        csvio.publish(directory, result)
        print(f'TICKET_FLOW_OUTPUT_WRITTEN {directory}')
        return 0
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(f'ticket_flow: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
