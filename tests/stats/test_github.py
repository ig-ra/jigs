import unittest

from stats.ticket_flow import github
from support import at
from github_support import commit, snapshot


class GithubTests(unittest.TestCase):
    def test_exact_case_insensitive_head_key(self):
        self.assertTrue(github.matches('IGR-15','owner/igr-15-tool'))
        self.assertTrue(github.matches('IGR-15','IGR-15'))
        self.assertTrue(github.matches('IGR-15','owner/igr-15_review'))
        self.assertTrue(github.matches('IGR-15','owner/igr-15/review'))
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

    def test_mismatched_head_is_failure(self):
        with self.assertRaises(ValueError):
            github.pilot_markers(lambda *a:dict(head='release'),lambda:None)

    def test_bot_ids_surfaces_thread_roots_and_submitted_reviews(self):
        data=snapshot()
        bot=dict(type='Bot', login='cubic-dev-ai[bot]')
        review=dict(id=2,state='COMMENTED',submitted_at=at(25).isoformat(),user=bot)
        data['reviews'] += [review,review,dict(id=3,state='PENDING',user=bot)]
        data['comments']=[dict(id=10,user={'type':'User'},created_at=at(20).isoformat()),
            dict(id=11,in_reply_to_id=10,user=bot,created_at=at(30).isoformat()),
            dict(id=12,in_reply_to_id=11,user=bot,created_at=at(35).isoformat()),
            dict(id=20,user=bot,created_at=at(40).isoformat())]
        data['comments'].append(data['comments'][1])
        data['issues']=[dict(id=11,user=bot,created_at=at(45).isoformat()),
            dict(id=99,user={'type':'User','login':'pretend[bot]'},created_at=at(1).isoformat())]
        result=github.interpret('IGR-15','ig-ra/jigs',data)
        self.assertEqual((result['bot_reviews'],result['bot_comments'],result['bot_threads']),(1,4,2))
        self.assertEqual(result['first_bot'],at(25).isoformat())
        self.assertEqual(result['first_review'],at(20).isoformat())


    def test_named_bots_exclude_linear_and_human_keep_all_thread_roots_and_boundary(self):
        data = snapshot()
        def account(login, kind='Bot'):
            return dict(login=login, type=kind)
        linear, human = account('linear-code[bot]'), account('ig-ra', 'User')
        data['reviews'] = [dict(id=1, user=linear, state='COMMENTED',
            submitted_at=at(15).isoformat(), commit_id='initial'),
            dict(id=2, user=human, state='APPROVED', submitted_at=at(20).isoformat())]
        data['comments'] = [dict(id=10, user=linear, created_at=at(1).isoformat()),
            dict(id=11, user=human, in_reply_to_id=10, created_at=at(2).isoformat())]
        for i, login in enumerate(sorted(github.REVIEW_BOTS), 12):
            data['comments'].append(dict(id=i, user=account(login), in_reply_to_id=11,
                                        created_at=at(i + 20).isoformat()))
        data['issues'] = [dict(id=20, user=linear, created_at=at(0).isoformat()),
            dict(id=21, user=account('baz-reviewer[bot]'), created_at=at(2).isoformat()),
            dict(id=22, user=account('coderabbitai[bot]'), created_at=at(3).isoformat())]
        result = github.interpret('IGR-15', 'ig-ra/jigs', data)
        self.assertEqual((result['bot_reviews'], result['bot_comments'], result['bot_threads']), (0, 3, 1))
        self.assertEqual(result['first_bot'], at(32).isoformat())
        self.assertEqual(result['first_review'], at(15).isoformat())
        self.assertEqual(result['fix_commits'], 1)
        from stats.ticket_flow import stages
        from stats.ticket_flow.model import Marker
        review = Marker('IGR-15', at(25), 'own_review', 'local:1')
        self.assertEqual(stages.review_after_bot([review], [result], at(), at(60)), 0)

    def test_author_time_partition_boundary_and_ratio(self):
        data=snapshot()
        data['commits'][1]=commit('fix',20,30,5)
        result=github.interpret('IGR-15','ig-ra/jigs',data)
        self.assertEqual(result['fix_commits'],1)
        self.assertEqual(result['initial_additions'],100)
        self.assertAlmostEqual(result['churn_ratio'],35/120)
        self.assertEqual(result['fix_split_status'],'author_time_estimate')
        markers=github.markers_for(result,data)
        self.assertEqual(sum(m.kind=='commit' for m in markers),1)
        self.assertTrue(all(m.repo=='ig-ra/jigs' for m in markers))

    def test_visible_interleaving_review_sha_and_author_committer_divergence(self):
        for reason in ('interleaved','review_sha','committer'):
            data=snapshot()
            if reason=='interleaved':
                data['commits'].append(commit('late-old',10))
            elif reason=='review_sha':
                data['reviews'][0]['commit_id']='fix'
            else:
                data['commits'][0]=commit(committer=30)
            with self.subTest(reason=reason):
                result=github.interpret('IGR-15','ig-ra/jigs',data)
                self.assertEqual(result['fix_split_status'],'suspect')
                self.assertIsNotNone(result['churn_ratio'])

    def test_unavailable_components_preserve_known_counts(self):
        for reason in ('missing_stats','multi_parent','no_boundary','zero_denominator','missing_author'):
            data=snapshot()
            if reason=='missing_stats':
                data['commits'][1].pop('stats')
            elif reason=='multi_parent':
                data['commits'][1]=commit('fix',30,parents=2)
            elif reason=='no_boundary':
                data['reviews']=[]
            elif reason=='missing_author':
                data['commits'][0]['commit']['author']={}
            else:
                data['commits'][0]=commit(additions=0,deletions=0)
            with self.subTest(reason=reason):
                result=github.interpret('IGR-15','ig-ra/jigs',data)
                self.assertEqual(result['fix_split_status'],'unavailable')
                self.assertIsNone(result['churn_ratio'])
                self.assertEqual(result['pr_commits'],2)
                if reason in ('missing_stats','multi_parent'):
                    self.assertEqual((result['initial_commits'],result['fix_commits']),(1,1))
                    self.assertEqual(result['initial_additions'],100)
                    self.assertIsNone(result['fix_additions'])
                elif reason in ('no_boundary','missing_author'):
                    self.assertIsNone(result['fix_commits'])

    def test_missing_bot_time_is_blank_while_counts_remain_known(self):
        result=github.bot_facts([], [dict(id=1,user={'type':'Bot', 'login':'cubic-dev-ai[bot]'})], [])
        self.assertEqual(result['bot_comments'],1)
        self.assertIsNone(result['first_bot'])
