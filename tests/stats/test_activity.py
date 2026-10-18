from pathlib import Path
import tempfile
import unittest

from stats.ticket_flow import activity
from support import call, dump


class ActivityTests(unittest.TestCase):
    def test_prototype_precedence_and_native_codex_tools(self):
        for tools, expected in [([], 'reply / communication (no tool)'),
                ([('Bash','gh pr view 3; git diff')], 'github / CI / bot threads'),
                ([('functions.exec_command','pytest')], 'tests / measurements'),
                ([('functions.exec','await tools.exec_command({cmd: "herdr agent get review"})')], 'codex management (herdr)'),
                ([('Read','igr/brief-go-2.md')], 'codex briefs and replies'),
                ([('functions.apply_patch','patch')], 'source edits'),
                ([('mcp__linear__get_issue','')], 'linear'),
                ([('Agent',''),('Bash','gh pr view')], 'subagent dispatch')]:
            with self.subTest(tools=tools):
                self.assertEqual(activity.classify(tools), expected)

    def test_raw_join_and_missing_tool_inputs_remain_auditable(self):
        with tempfile.TemporaryDirectory() as name:
            path = dump(Path(name)/'session.jsonl', [dict(type='assistant', message={'content':[
                dict(type='tool_use', id='t', name='Read', input={'file_path':'src.py'})]})])
            action = dict(id='t', source={'path':str(path),'line':1})
            good = call(tools=[action])
            missing = call('missing', tools=[dict(id='absent', source=action['source'])])
            activity.enrich([good, missing], {str(path):'claude'})
            self.assertEqual(good['activity'], 'code / doc reading')
            self.assertEqual(good['activity_source'], f'{path}:1')
            self.assertEqual(missing['activity_basis'], 'missing_tool_input')
            self.assertEqual(missing['activity'], 'other')

    def test_custom_source_is_read_as_text_never_executed(self):
        action, = activity.actions({'type':'response_item','payload':{
            'type':'custom_tool_call','name':'functions.exec','call_id':'c',
            'input':'await tools.exec_command({cmd: "gh pr view 3"})'}}, 'codex')
        self.assertEqual(activity.classify([(action[1],activity.tool_text(action[2]))]), 'github / CI / bot threads')
