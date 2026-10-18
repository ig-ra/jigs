import unittest
from unittest.mock import patch

from stats.ticket_flow import github
from support import at


class GithubTests(unittest.TestCase):
    def test_exact_case_insensitive_head_key(self):
        self.assertTrue(github.matches('IGR-15','owner/igr-15-tool'))
        self.assertTrue(github.matches('IGR-15','IGR-15'))
        for head in ('owner/igr-150-tool','owner/xigr-15-tool','release','igr-15x'):
            self.assertFalse(github.matches('IGR-15',head))

    def test_pilot_projects_only_markers_and_checks_every_bot_surface(self):
        requests = []
        def fetch(endpoint, projection, paginate=False):
            requests.append((endpoint,projection,paginate))
            if endpoint.endswith(('/3','/4')):
                number = int(endpoint[-1])
                return dict(number=number,head=f'owner/igr-{number+12}-work',
                            created=at().isoformat(),merged=at(50).isoformat())
            return [at(30).isoformat(),at(20).isoformat()]
        markers, prs = github.pilot_markers(fetch,lambda:None)
        self.assertEqual(len(markers),6)
        self.assertEqual(prs[0]['first_bot'],at(20).isoformat())
        self.assertEqual(len([r for r in requests if r[2]]),6)
        self.assertFalse(any('commits' in r[0] for r in requests))

    def test_paginated_access_keeps_host_keyring_prefix_and_get(self):
        with patch('stats.ticket_flow.github.subprocess.run') as run:
            run.return_value.stdout='["2026-10-17T00:00:00Z"]\n[]\n["2026-10-17T00:01:00Z"]\n'
            result=github.request('repos/example/pulls','.[]',True)
            self.assertEqual(len(result),2)
            args=run.call_args.args[0]
            self.assertEqual(args[:len(github.PREFIX)],github.PREFIX)
            self.assertIn('--paginate',args)
            self.assertNotIn('--slurp',args)
            self.assertEqual(args[args.index('--method')+1],'GET')

    def test_mismatched_head_is_failure(self):
        with self.assertRaises(ValueError):
            github.pilot_markers(lambda *a:dict(head='release'),lambda:None)
