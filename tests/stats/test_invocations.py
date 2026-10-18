import json
from pathlib import Path
import unittest

from stats.ticket_flow import invocations, local, stages
from stats.ticket_flow.model import Marker
from support import at, turn


class InvocationTests(unittest.TestCase):
    def test_cited_memory_write_and_delegated_sender_receiver(self):
        evidence = json.loads((Path(__file__).parent / 'fixtures/native-review-actions.json').read_text())
        self.assertFalse(invocations.native_review('Bash', evidence['memory_write']))
        self.assertFalse(invocations.native_review('Bash', evidence['delegated_sender']))
        self.assertTrue(invocations.native_review('exec', evidence['delegated_receiver']))

    def test_prose_search_wait_help_and_non_shell_tools_are_not_review_runs(self):
        for command in (
            'echo "codex-companion.mjs review --wait"',
            "rg 'codex-companion.mjs review' docs/",
            '# node /scripts/codex-companion.mjs review\necho done',
            'until ! pgrep -f "codex-companion.mjs review" >/dev/null; do sleep 15; done',
            'while pgrep -f "codex-companion review"; do sleep 5; done',
            'node /scripts/codex-companion.mjs review --help 2>&1 | head -30',
            'codex-companion review -h',
            "cat <<'DOC'\nnode /scripts/codex-companion.mjs review --wait\nDOC",
            "python3 -c 'print(\"codex-companion review\")'",
        ):
            with self.subTest(command=command):
                self.assertFalse(invocations.native_review('Bash', {'command': command}))
        for name, args in (
            ('Read', {'file_path': 'codex-companion review'}),
            ('Write', {'content': 'codex-companion review'}),
            ('Agent', {'prompt': 'Run codex-companion review'}),
            ('functions.exec', {'code': 'text("tools.exec_command({cmd: codex-companion review})")'}),
            ('exec', {'code': '// tools.exec_command({cmd:"codex-companion review"})'}),
            ('exec', {'code': 'tools.send_message({message:"codex-companion review"})'}),
        ):
            with self.subTest(name=name, args=args):
                self.assertIsNone(local.invocation_kind(name, args))

    def test_genuine_shell_commands_and_nested_wrappers(self):
        for command in (
            'codex-companion review --wait',
            'node /scripts/codex-companion.mjs review --base origin/main > igr/review.md 2>&1',
            'cd /repo && git fetch origin; node /scripts/codex-companion.mjs review --wait',
            'env -u GH_TOKEN X=yes timeout 120 node /scripts/codex-companion.mjs review --wait',
            "bash -lc 'node /scripts/codex-companion.mjs review --wait'",
            'if true; then node /scripts/codex-companion.mjs review --wait; fi',
        ):
            with self.subTest(command=command):
                self.assertTrue(invocations.native_review('Bash', {'command': command}))
                code = 'text(await tools.exec_command({cmd:' + json.dumps(command) + ',workdir:"/repo"}));'
                self.assertTrue(invocations.native_review('functions.exec', {'code': code}))
        # Dynamic JS is not evaluated or mistaken for a recorded literal execution.
        self.assertFalse(invocations.native_review('exec', {'code':
            'tools.exec_command({cmd:"codex-companion review" + suffix})'}))

    def test_downstream_passes_keep_receiver_and_genuine_rerun(self):
        evidence = json.loads((Path(__file__).parent / 'fixtures/native-review-actions.json').read_text())
        markers = [Marker('SAW-12992', at(), 'design', 'start')]
        actions = [('Bash', evidence['delegated_sender']), ('exec', evidence['delegated_receiver']),
                   ('exec', evidence['delegated_receiver'])]
        for index, (name, args) in enumerate(actions, 1):
            kind = local.invocation_kind(name, args)
            if kind:
                markers.append(Marker('SAW-12992', at(index * 10), kind, f'source:{index}', identity=str(index)))
        turns = stages.assign([turn(ticket='SAW-12992', start=25),
                               turn('rerun', ticket='SAW-12992', start=35)], markers)
        self.assertEqual([(t.stage, t.review_pass) for t in turns], [('first_review', 1), ('further_review', 2)])
        self.assertEqual(sum(r[-1] == 'native_review' for r in stages.timeline(markers)['SAW-12992']), 2)
