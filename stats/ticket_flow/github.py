"""Read-only, paginated host-keyring access; step-1 PR marker projection only."""
import json
import re
import subprocess

from .model import Marker, PILOT
from .sources import stamp

PREFIX = ['env', '-u', 'GITHUB_TOKEN', '-u', 'GH_TOKEN', '-u', 'GH_ENTERPRISE_TOKEN', 'gh']


def authenticate():
    subprocess.run(PREFIX + ['auth', 'status'], capture_output=True, text=True,
                   check=True, timeout=30)


def request(endpoint, projection, paginate=False):
    args = PREFIX + ['api', '--method', 'GET', endpoint]
    if paginate:
        args += ['--paginate']
    result = subprocess.run(args + ['--jq', projection], capture_output=True,
                            text=True, check=True, timeout=45)
    if not paginate:
        return json.loads(result.stdout)
    decoder, pages, remaining = json.JSONDecoder(), [], result.stdout.strip()
    while remaining:
        page, offset = decoder.raw_decode(remaining)
        pages.extend(page)
        remaining = remaining[offset:].lstrip()
    return pages


def matches(ticket, head):
    return bool(re.search(r'(?<![A-Za-z0-9])' + re.escape(ticket) + r'(?:-|$)', head, re.I))


def pilot_markers(fetch=request, auth=authenticate):
    auth()
    markers, provenance = [], []
    for ticket, number in zip(PILOT, (3, 4)):
        prefix = f'repos/ig-ra/jigs/pulls/{number}'
        pr = fetch(prefix, '{number, head: .head.ref, created: .created_at, merged: .merged_at}')
        if not matches(ticket, pr['head']):
            raise ValueError(f'PR {number}: head does not match {ticket}')
        times = []
        for endpoint in (prefix + '/reviews', prefix + '/comments',
                         f'repos/ig-ra/jigs/issues/{number}/comments'):
            times += fetch(endpoint + '?per_page=100',
                           '[.[] | select(.user.type == "Bot") | (.submitted_at // .created_at)]', True)
        facts = {'ticket': ticket, 'repo': 'ig-ra/jigs', 'pr': number,
                 'head_ref': pr['head'], 'created': pr['created'],
                 'merged': pr['merged'], 'first_bot': min(times) if times else None}
        provenance.append(facts)
        for kind, column in (('bots_ci', 'created'), ('finish', 'merged'), ('bots_ci', 'first_bot')):
            if facts[column]:
                markers.append(Marker(ticket, stamp(facts[column]), kind,
                                      f'github:ig-ra/jigs#{number}:{column}', 'ig-ra/jigs'))
    return markers, provenance
