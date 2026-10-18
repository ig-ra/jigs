"""Select locally evidenced window tickets before fetching remote provenance."""
from .sources import REPOS, stamp
from .table_common import in_window


def selected_tickets(turns, markers, estimates, start, end):
    tickets = {t.ticket for t in turns if in_window(t.end, start, end)}
    tickets.update(t.ticket for t in turns for c in t.calls
                   if in_window(stamp(c['timestamp']), start, end))
    tickets.update(m.ticket for m in markers if in_window(m.time, start, end))
    tickets.update(e['ticket'] for e in estimates or [] if in_window(e['time'], start, end))
    return tickets


def repo_tickets(collected, selected):
    """All recorded associations for selected tickets, including earlier history."""
    result = {repo: set() for _, repo in REPOS}
    evidence = collected['rows'] + [vars(t) for t in collected['turns']] + [
        vars(m) for m in collected['markers']] + [c for t in collected['turns'] for c in t.calls]
    for row in evidence:
        ticket, repo = row.get('ticket'), row.get('repo')
        if ticket and ticket in selected and repo in result:
            result[repo].add(ticket)
    return {repo: keys for repo, keys in result.items() if keys}
