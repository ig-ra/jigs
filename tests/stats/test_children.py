import json
from pathlib import Path
import tempfile
import unittest

from stats.ticket_flow import children, native
from support import at, call, dump, turn


class ChildTests(unittest.TestCase):
    def test_missing_identity_stays_blank_parent_link_uses_prior_ticket_only(self):
        with tempfile.TemporaryDirectory() as name:
            path = dump(Path(name)/'parent/subagents/child.jsonl', [])
            child = turn(parent='parent', session='child', ticket=None, source=f'{path}:1',
                         calls=[call(ticket=None,session_id='child')])
            index = native.ticket_index([call(session_id='parent',ticket='SAW-100',time=0),
                                         call('later',session_id='parent',ticket='IGR-16',time=30)])
            children.enrich([child], {str(path):'claude'}, index)
            self.assertEqual(child.ticket, 'SAW-100')
            self.assertEqual(child.calls[0]['ticket_basis'], 'recorded_parent_link')
            self.assertIsNone(child.child_type)
            self.assertIsNone(child.child_family)
            child.start = at(0)
            child.ticket = None
            children.enrich([child], {str(path):'claude'}, native.ticket_index([
                call(session_id='parent',time=20)]))
            self.assertIsNone(child.ticket)

    def test_simplify_launch_family_inherited_by_lens_without_truncating_description(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            parent = dump(root/'parent.jsonl', [dict(type='assistant',message={'content':[
                dict(type='tool_use',id='skill',name='Skill',input={'skill':'simplify'}),
                dict(type='tool_use',id='lens',name='Agent',input={'description':'Check reuse'})]})])
            path = dump(root/'parent/subagents/workflows/simplify/child.jsonl', [])
            description = 'Code reuse lens ' + 'full description ' * 10
            path.with_suffix('.meta.json').write_text(json.dumps({
                'agentType':'general-purpose','description':description,'toolUseId':'lens'}))
            child = turn(parent='parent', source=f'{path}:1')
            children.enrich([child], {str(parent):'claude',str(path):'claude'}, {})
            self.assertEqual(child.child_family, 'simplify')
            self.assertEqual(child.child_description, description)
            self.assertEqual(child.child_basis, f'{parent}:1')

    def test_codex_native_metadata_uses_first_identity_and_explicit_role(self):
        with tempfile.TemporaryDirectory() as name:
            path = dump(Path(name)/'child.jsonl', [dict(type='session_meta',payload={
                'source':{'subagent':{'thread_spawn':{'agent_role':'reviewer'}}}}),
                dict(type='session_meta',payload={'source':{'subagent':'explorer'}})])
            detail = children.metadata(str(path),'codex',{})
            self.assertEqual(detail['child_type'], 'reviewer')
            self.assertEqual(detail['child_family'], 'review')
            self.assertIsNone(detail['child_description'])
