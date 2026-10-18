"""Small offline GitHub API-shaped fixtures; dates straddle a submitted review."""
from stats.ticket_flow import github
from support import at


def commit(sha='initial', time=5, additions=100, deletions=20, parents=1, committer=None):
    return dict(sha=sha,commit={'author':{'date':at(time).isoformat()},
        'committer':{'date':at(time if committer is None else committer).isoformat()}},
        parents=[{'sha':f'parent-{i}'} for i in range(parents)],
        stats={'additions':additions,'deletions':deletions,'total':additions+deletions})


def snapshot(number=1, head='igor/igr-15-work'):
    return dict(pr=dict(number=number,head={'ref':head,'sha':'fix'},created_at=at().isoformat(),
        merged_at=at(55).isoformat(),changed_files=3,additions=130,deletions=25,commits=2),
        reviews=[dict(id=1,state='COMMENTED',submitted_at=at(20).isoformat(),commit_id='initial',user={'type':'User'})],
        commits=[commit(),commit('fix',30,30,5)], comments=[],issues=[])


def fact(number=1, repo='ig-ra/jigs', **values):
    return dict(github.interpret('IGR-15',repo,snapshot(number)), **values)
