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

    def test_verified_native_tool_kinds_use_truthful_existing_activities(self):
        for name, text, expected in (
                ('ToolSearch', 'select:mcp__linear__get_issue', 'code / doc reading'),
                ('Skill', 'simplify', 'skill / memory reads'),
                ('EnterWorktree', '/repo', 'worktree setup / cleanup'),
                ('ExitWorktree', 'keep', 'worktree setup / cleanup'),
                ('SubagentHandback', 'result', 'agent communication'),
                ('send_message', 'result', 'agent communication'),
                ('Monitor', 'gh pr checks 3', 'github / CI / bot threads'),
                ('Monitor', 'until ready; do sleep 5; done', 'waiting'),
                ('Monitor', '', 'waiting')):
            with self.subTest(name=name, text=text):
                self.assertEqual(activity.classify([(name, text)]), expected)

    def test_custom_exec_classifies_visible_operations_not_the_wrapper(self):
        for code, expected in (
                ('await tools.apply_patch("*** Begin Patch\\n*** End Patch")', 'source edits'),
                ('await tools.mcp__linear_igor__get_issue({id: "IGR-19"})', 'linear'),
                ('const r = await tools.web__run({search_query: [{q: "docs"}]})', 'code / doc reading'),
                ('await tools.exec_command({cmd: "gh pr view 3"})', 'github / CI / bot threads'),
                ('await tools.exec_command({cmd: "pytest"})', 'tests / measurements'),
                ('const r = await tools.exec_command({cmd: "python3 /tmp/opaque.py"})', 'other')):
            with self.subTest(code=code):
                action, = activity.actions({'type':'response_item', 'payload':{
                    'type':'custom_tool_call', 'name':'exec', 'call_id':'c', 'input':code}}, 'codex')
                self.assertEqual(activity.classify([(action[1], activity.tool_text(action[2]))]), expected)

    def test_nested_tool_detection_skips_quoted_examples_and_comments(self):
        code = """const sample = "tools.apply_patch('not a call')";
            // tools.mcp__linear__get_issue({})
            /* tools.apply_patch('also not a call') */
            const template = `tools.apply_patch('example')`;
            await tools.exec_command({cmd: "python3 /tmp/opaque.py"});"""
        self.assertEqual([name for name, _ in activity.expanded_tools([('exec', code)])], ['exec_command'])
        self.assertEqual(activity.classify([('exec', code)]), 'other')

    def test_script_location_does_not_invent_its_activity(self):
        self.assertEqual(activity.classify([('Bash', 'bash /tmp/scratchpad/opaque.sh')]), 'other')
        self.assertEqual(activity.classify([('Bash', 'python3 /tmp/scratchpad/opaque.py')]), 'other')
        self.assertEqual(activity.classify([('Bash', 'gh run view 3'), ('ToolSearch', '')]),
                         'github / CI / bot threads')
