"""Pure current-PR interpretation, plus the retained narrow pilot projection."""
import re

from .model import Marker, PILOT
from .sources import stamp
from .github_fetch import authenticate, request


def matches(ticket, head):
    return bool(re.search(r'(?<![A-Za-z0-9])' + re.escape(ticket) + r'(?![A-Za-z0-9])', head, re.I))


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


def unique(records):
    return list({r['id']: r for r in records}.values())


def submitted(reviews):
    return sorted((r for r in unique(reviews) if r.get('submitted_at') and r.get('state') != 'PENDING'),
                  key=lambda r: (stamp(r['submitted_at']), str(r['id'])))


def bot_facts(reviews, comments, issues):
    reviews, comments, issues = submitted(reviews), unique(comments), unique(issues)
    bots = lambda rows: [r for r in rows if (r.get('user') or {}).get('type') == 'Bot']
    roots = {c['id']: c.get('in_reply_to_id') or c['id'] for c in comments}
    def root(identity):
        seen = set()
        while identity in roots and roots[identity] != identity and identity not in seen:
            seen.add(identity)
            identity = roots[identity]
        return identity
    times = [r['submitted_at'] for r in bots(reviews)]
    times += [r.get('created_at') for r in bots(comments) + bots(issues)]
    return dict(bot_reviews=len(bots(reviews)), bot_comments=len(bots(comments)) + len(bots(issues)),
                bot_threads=len({root(c['id']) for c in bots(comments)}),
                first_bot=min(times, key=stamp) if times and all(times) else None)


def partition(commits, boundary):
    """Current API order is retained for diagnostics; dates alone choose buckets."""
    groups, suspect = {False: [], True: []}, False
    seen_fix = False
    for commit in commits:
        dates = commit.get('commit') or {}
        author = (dates.get('author') or {}).get('date')
        committer = (dates.get('committer') or {}).get('date')
        if author is None:
            return None, False
        fix = stamp(author) >= boundary
        suspect |= seen_fix and not fix
        seen_fix |= fix
        suspect |= committer is not None and (stamp(committer) >= boundary) != fix
        groups[fix].append(commit)
    return groups, suspect


def line_sum(commits, field):
    values = [(c.get('stats') or {}).get(field) if c.get('parents') is not None and len(c['parents']) <= 1
              else None for c in commits]
    return None if any(v is None for v in values) else sum(values)


def split(commits, reviews):
    fields = ('initial_commits', 'fix_commits', 'initial_additions', 'initial_deletions',
              'fix_additions', 'fix_deletions', 'churn_ratio')
    result = dict.fromkeys(fields)
    result['fix_split_status'] = 'unavailable'
    reviews = submitted(reviews)
    if not reviews:
        return result
    boundary = stamp(reviews[0]['submitted_at'])
    groups, suspect = partition(commits, boundary)
    if groups is None:
        return result
    for fix, name in ((False, 'initial'), (True, 'fix')):
        result[name + '_commits'] = len(groups[fix])
        for field in ('additions', 'deletions'):
            result[name + '_' + field] = line_sum(groups[fix], field)
    shas = [c['sha'] for c in commits]
    reviewed = reviews[0].get('commit_id')
    if reviewed in shas:
        cutoff = shas.index(reviewed)
        suspect |= any((i <= cutoff) != (c in groups[False]) for i, c in enumerate(commits))
    lines = [result[k] for k in fields[2:6]]
    if any(v is None for v in lines) or sum(lines[:2]) == 0:
        return result
    result['churn_ratio'] = sum(lines[2:]) / sum(lines[:2])
    result['fix_split_status'] = 'suspect' if suspect else 'author_time_estimate'
    return result


def interpret(ticket, repo, data):
    pr = data['pr']
    if not matches(ticket, pr['head']['ref']):
        raise ValueError(f'{repo}#{pr["number"]}: head no longer matches {ticket}')
    reviews = submitted(data['reviews'])
    result = dict(ticket=ticket, repo=repo, pr=pr['number'], head_ref=pr['head']['ref'],
        head_sha=pr['head']['sha'], created=pr['created_at'], merged=pr.get('merged_at'),
        first_review=reviews[0]['submitted_at'] if reviews else None,
        pr_files=pr.get('changed_files'), pr_additions=pr.get('additions'),
        pr_deletions=pr.get('deletions'), pr_commits=pr.get('commits'))
    result.update(bot_facts(data['reviews'], data['comments'], data['issues']))
    commits = list({c['sha']: c for c in data['commits']}.values())
    result.update(split(commits, data['reviews']))
    return result


def markers_for(fact, data):
    source = f'github:{fact["repo"]}#{fact["pr"]}'
    markers = []
    for kind, column in (('bots_ci', 'created'), ('first_review', 'first_review'),
                         ('bots_ci', 'first_bot'), ('finish', 'merged')):
        if fact[column]:
            markers.append(Marker(fact['ticket'], stamp(fact[column]), kind,
                                  source + ':' + column, fact['repo']))
    if fact['first_review']:
        boundary = stamp(fact['first_review'])
        for commit in data['commits']:
            authored = ((commit.get('commit') or {}).get('author') or {}).get('date')
            if authored and stamp(authored) >= boundary:
                markers.append(Marker(fact['ticket'], stamp(authored), 'commit',
                    source + ':commit:' + commit['sha'], fact['repo'], commit['sha']))
    return list({(m.kind, m.source): m for m in markers}.values())
