"""Read-only paginated GitHub snapshots through the host keyring."""
import json
import subprocess

PREFIX = ['env', '-u', 'GITHUB_TOKEN', '-u', 'GH_TOKEN', '-u', 'GH_ENTERPRISE_TOKEN', 'gh']


def authenticate():
    subprocess.run(PREFIX + ['auth', 'status'], capture_output=True, text=True,
                   check=True, timeout=30)


def request(endpoint, projection='.', paginate=False):
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


def snapshot(repo, number, fetch):
    prefix = f'repos/{repo}/pulls/{number}'
    pr = fetch(prefix, '.')
    reviews = fetch(prefix + '/reviews?per_page=100', '.', True)
    comments = fetch(prefix + '/comments?per_page=100', '.', True)
    issues = fetch(f'repos/{repo}/issues/{number}/comments?per_page=100', '.', True)
    commits = fetch(prefix + '/commits?per_page=100', '.', True)
    commits = list({c['sha']: c for c in commits}.values())
    if pr.get('commits') is not None and len(commits) != pr['commits']:
        raise ValueError(f'{repo}#{number}: incomplete current commit list')
    details = [fetch(f'repos/{repo}/commits/{c["sha"]}', '.') for c in commits]
    return dict(pr=pr, reviews=reviews, comments=comments, issues=issues, commits=details)


def collect(tickets, fetch=request, auth=authenticate):
    """One listing per repo, all pages; exact joins before expensive PR reads."""
    from .github import matches, interpret, markers_for
    auth()
    markers, facts = [], []
    for repo, keys in sorted(tickets.items()):
        pulls = fetch(f'repos/{repo}/pulls?state=all&per_page=100', '.', True)
        pulls = {p['number']: p for p in pulls}
        for number, pr in sorted(pulls.items()):
            joined = sorted({key.upper() for key in keys if matches(key, pr['head']['ref'])})
            if not joined:
                continue
            data = snapshot(repo, number, fetch)
            for ticket in joined:
                fact = interpret(ticket, repo, data)
                facts.append(fact)
                markers.extend(markers_for(fact, data))
    return markers, facts
