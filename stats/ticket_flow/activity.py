"""Native tool evidence and the prototype's first-match activity vocabulary."""
import re

from .sources import raw_records, reader, reference


def actions(record, provider):
    if provider == 'claude':
        content = (record.get('message') or {}).get('content', [])
        for block in content if isinstance(content, list) else []:
            kind = block.get('type')
            if kind == 'tool_use':
                yield block['id'], block['name'], block.get('input') or {}, None, False
            elif kind == 'tool_result':
                yield block.get('tool_use_id'), '', {}, reader().text_content(
                    block.get('content', '')), bool(block.get('is_error'))
    else:
        payload = record.get('payload') or {}
        kind = payload.get('type')
        if kind in ('function_call', 'custom_tool_call'):
            value = payload.get('arguments', payload.get('input', ''))
            args = reader().arguments(value)
            yield payload.get('call_id'), payload.get('name', ''), args or {
                'code': value}, None, False
        elif kind in ('function_call_output', 'custom_tool_call_output'):
            yield payload.get('call_id'), '', {}, reader().text_content(payload.get('output', '')), False


def tool_text(args):
    return str(next((args[k] for k in ('command', 'cmd', 'code', 'file_path', 'path', 'pattern')
                     if args.get(k) is not None), ''))


def expanded_tools(tools):
    """Read direct tools.NAME calls; skip JS strings/comments and never execute."""
    pattern = (r"'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"|`(?:\\.|[^`\\])*`|"
               r'//[^\n]*|/\*.*?\*/|\btools\.([A-Za-z_][A-Za-z_0-9]*)\s*\(')
    for name, text in tools:
        names = [m[1] for m in re.finditer(pattern, text, re.S) if m[1]] if name.rsplit('.', 1)[-1] == 'exec' else []
        for nested in names or [name]:
            yield nested, text


def command_activity(command):
    for label, pattern in (
        ('native codex review', r'codex-companion'),
        ('codex management (herdr)', r'\bherdr\b|watch-codex'),
        ('github / CI / bot threads', r'\bgh\b|\btk\s+(?:--cwd\s+\S+\s+)?(?:--json\s+)?pr\b'),
        ('tk bookkeeping (step, estimate)', r'\btk\s+(?:--cwd\s+\S+\s+)?step\b|estimate\.py'),
        ('worktree setup / cleanup', r'\btk\s+(?:--cwd\s+\S+\s+)?(?:prep|close|go)\b|git .*worktree|check-ignore'),
        ('tests / measurements', r'unittest|pytest|go test|bin/usage|python3 -B -|npm (?:test|run)|trunk|\bmake\b'),
        ('git', r'\bgit\b'), ('waiting', r'\bsleep\b|\bwatch\b')):
        if re.search(pattern, command):
            return label


def classify(tools):
    tools = list(expanded_tools(tools))
    names = [name.rsplit('.', 1)[-1] for name, _ in tools]
    command = ' '.join(text for (name, text), short in zip(tools, names)
                       if short in ('Bash', 'exec_command', 'exec', 'write_stdin', 'Monitor'))
    paths = ' '.join(text for (name, text), short in zip(tools, names)
                     if short in ('Read', 'Write', 'Edit', 'apply_patch'))
    if not tools:
        return 'reply / communication (no tool)'
    for label, matches in (
        ('human poll', any(n in ('AskUserQuestion', 'request_user_input', 'request_user_input_async') for n in names)),
        ('subagent dispatch', any(n in ('Agent', 'Task', 'spawn_agent') for n in names)),
        ('agent communication', any(n in ('SubagentHandback', 'SendMessage', 'send_message') for n in names)),
        ('worktree setup / cleanup', any(n in ('EnterWorktree', 'ExitWorktree') for n in names)),
        ('skill / memory reads', 'Skill' in names),
        ('linear', any('linear' in n.lower() for n in names))):
        if matches:
            return label
    command_label = command_activity(command)
    if command_label:
        return command_label
    for label, pattern in (
        ('codex briefs and replies', r'(?:^|/)igr/(brief-|codex-|impl-|compare|findings)'),
        ('design docs (models, plan, KISS)', r'(?:^|/)igr/(model-|A-to-B|kiss-pass|plan-|living|investigation|new-work)'),
        ('review docs', r'(?:^|/)igr/review-'), ('checkpoint', r'(?:^|/)igr/(resume|corrections|state)'),
        ('skill / memory reads', r'SKILL\.md|loop\.md|resume\.md|references/|/memory|MEMORY|remember')):
        if re.search(pattern, paths):
            return label
    if any(n in ('Write', 'Edit', 'apply_patch') for n in names):
        return 'source edits'
    if paths or any(n in ('Grep', 'Glob', 'LSP', 'Read', 'ToolSearch', 'web__run') for n in names) or re.search(
            r'\b(rg|grep|sed|cat|ls|find|head|tail|wc)\b', command):
        return 'code / doc reading'
    if any(n in ('wait', 'wait_agent', 'sleep', 'Monitor') for n in names):
        return 'waiting'
    return 'other'


def enrich(rows, paths):
    tools = {}
    for path, provider in sorted(paths.items()):
        for line, record in raw_records(path, provider):
            for identity, name, args, _, _ in actions(record, provider):
                if name:
                    tools[path, line, identity] = (name, tool_text(args))
    for row in rows:
        if row['type'] != 'call':
            continue
        evidence = [tools.get((a['source']['path'], a['source']['line'], a['id']))
                    for a in row.get('tools', [])]
        missing = any(t is None for t in evidence)
        row['activity'] = 'other' if missing else classify(evidence)
        row['activity_basis'] = 'missing_tool_input' if missing else (
            'native_tool_inputs' if evidence else 'no_tools')
        row['activity_source'] = ';'.join(reference(**a['source']) for a in row.get('tools', [])) or None
    return rows
