import copy
import subprocess
import unittest
from unittest.mock import patch

from stats.ticket_flow import github_fetch
from github_support import snapshot


class FetchTests(unittest.TestCase):
    def test_paginated_keyring_get_and_authenticate(self):
        with patch.object(github_fetch.subprocess,'run') as run:
            run.return_value.stdout='[{"id":1}]\n[]\n[{"id":2}]\n'
            self.assertEqual(len(github_fetch.request('repos/example/pulls','.',True)),2)
            args=run.call_args.args[0]
            self.assertEqual(args[:len(github_fetch.PREFIX)],github_fetch.PREFIX)
            self.assertIn('--paginate',args)
            self.assertNotIn('--slurp',args)
            self.assertEqual(args[args.index('--method')+1],'GET')
            github_fetch.authenticate()
            self.assertEqual(run.call_args.args[0],github_fetch.PREFIX+['auth','status'])

    def test_many_prs_exact_join_all_surfaces_and_commits_share_fetcher(self):
        data=snapshot()
        seen=[]
        def fetch(endpoint,projection,paginate=False):
            seen.append((endpoint,paginate))
            if 'pulls?state' in endpoint:
                return [dict(number=1,head={'ref':'igor/igr-15-one'}),
                        dict(number=2,head={'ref':'igor/IGR-15_two'}),
                        dict(number=3,head={'ref':'igor/igr-150-other'})]
            if '/commits/' in endpoint:
                return next(c for c in data['commits'] if c['sha'] == endpoint.rsplit('/',1)[1])
            if endpoint.endswith(('/1','/2')):
                number=int(endpoint[-1])
                return snapshot(number,f'igor/igr-15-{number}')['pr']
            for suffix,key in (('/reviews?per_page=100','reviews'),('/comments?per_page=100','comments'),
                               ('/commits?per_page=100','commits')):
                if endpoint.endswith(suffix):
                    return copy.deepcopy(data[key])
            self.fail(endpoint)
        with patch.object(github_fetch,'authenticate') as auth:
            markers,facts=github_fetch.collect({'ig-ra/jigs':{'IGR-15'}},fetch,auth)
            auth.assert_called_once()
        self.assertEqual([p['pr'] for p in facts],[1,2])
        self.assertEqual(len([m for m in markers if m.kind=='commit']),2)
        self.assertTrue(all(paginate for endpoint,paginate in seen if '?' in endpoint))
        self.assertFalse(any('/pulls/3' in endpoint for endpoint,_ in seen))

    def test_known_no_pr_and_failed_source_are_distinct(self):
        self.assertEqual(github_fetch.collect({'ig-ra/jigs':['IGR-15']},lambda *a:[],lambda:None),([],[]))
        with self.assertRaises(subprocess.CalledProcessError):
            github_fetch.collect({'ig-ra/jigs':['IGR-15']},
                lambda *a: (_ for _ in ()).throw(subprocess.CalledProcessError(1,'gh')),lambda:None)

    def test_incomplete_current_commit_list_aborts_snapshot(self):
        data=snapshot()
        def fetch(endpoint,*args):
            if endpoint.endswith('/1'):
                return data['pr']
            return []
        with self.assertRaisesRegex(ValueError,'incomplete current commit'):
            github_fetch.snapshot('ig-ra/jigs',1,fetch)
