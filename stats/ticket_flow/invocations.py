"""Recognize executable native-review commands without evaluating recorded text."""
from pathlib import PurePosixPath
import re
import shlex


def shell_text(command):
    """Exclude heredoc bodies: their text is input, not shell commands."""
    pending = []
    for line in command.splitlines():
        if pending:
            if line.strip() == pending[0]:
                pending.pop(0)
            continue
        yield line
        pending.extend(m[2] for m in re.finditer(r"<<-?\s*(['\"]?)([\w-]+)\1", line))


def shell_segments(command):
    lexer = shlex.shlex('\n'.join(shell_text(command)), posix=True, punctuation_chars=';&|()<>\n')
    lexer.whitespace = ' \t\r'
    try:
        tokens = list(lexer)
    except ValueError:
        return
    segment = []
    for token in tokens + [';']:
        if token and all(c in ';&|()\n' for c in token):
            if segment:
                yield segment
                segment = []
        else:
            segment.append(token)


def review_segment(words):
    """Only executable positions count; arguments to echo/grep/herdr never do."""
    words = list(words)
    while words:
        name = PurePosixPath(words[0]).name
        if name in ('if', 'then', 'elif', 'do', 'while', 'until', '!', 'command', 'exec', 'nohup', 'time'):
            words.pop(0)
        elif re.fullmatch(r'[A-Za-z_][\w]*=.*', words[0]):
            words.pop(0)
        elif name == 'env':
            words.pop(0)
            while words and words[0].startswith('-'):
                option = words.pop(0)
                if option in ('-u', '--unset') and words:
                    words.pop(0)
        elif name == 'timeout':
            words.pop(0)
            while words and words[0].startswith('-'):
                option = words.pop(0)
                if option in ('-s', '--signal', '-k', '--kill-after') and words:
                    words.pop(0)
            if words:
                words.pop(0)
        elif name in ('bash', 'sh', 'zsh') and len(words) >= 3 and 'c' in words[1]:
            return shell_review(words[2])
        else:
            if name in ('node', 'nodejs'):
                words.pop(0)
                while words and words[0].startswith('--'):
                    words.pop(0)
            return bool(len(words) >= 2 and PurePosixPath(words[0]).name in (
                'codex-companion', 'codex-companion.mjs') and words[1] == 'review' and
                not any(w in ('--help', '-h') for w in words[2:]))
    return False


def shell_review(command):
    return any(review_segment(words) for words in shell_segments(command))


def js_escape(body, position):
    """Decode one ECMAScript module escape; return its value and next position."""
    match = re.match(r'\\(?:u\{([0-9a-fA-F]+)\}|u([0-9a-fA-F]{4})|x([0-9a-fA-F]{2})|\r\n|.)',
                     body[position:], re.S)
    if not match:
        raise ValueError('incomplete escape')
    escaped = match[0][1:]
    if any(match.groups()):
        codepoint = int(next(g for g in match.groups() if g is not None), 16)
        if codepoint > 0x10ffff:
            raise ValueError('invalid code point')
        value = chr(codepoint)
    elif escaped in ('\n', '\r', '\r\n', '\u2028', '\u2029'):
        value = ''
    elif escaped[0] in 'ux123456789' or escaped == '0' and body[position + 2:position + 3].isdigit():
        raise ValueError('invalid escape')
    else:
        value = {'b': '\b', 'f': '\f', 'n': '\n', 'r': '\r', 't': '\t', 'v': '\v', '0': '\0'}.get(escaped, escaped)
    return value, position + len(match[0])


def js_string(literal):
    """Read a static JS literal, never evaluate code or template substitutions."""
    if len(literal) < 2 or literal[0] not in '\'"`' or literal[-1] != literal[0]:
        raise ValueError('not a string literal')
    quote, body = literal[0], literal[1:-1]
    if quote == '`':
        body = body.replace('\r\n', '\n').replace('\r', '\n')
    result, position = [], 0
    while position < len(body):
        char = body[position]
        if char == '\\':
            value, position = js_escape(body, position)
            result.append(value)
            continue
        if char == quote or quote == '`' and body.startswith('${', position):
            raise ValueError('non-static literal')
        if quote != '`' and char in '\r\n':
            raise ValueError('unescaped newline')
        result.append(char)
        position += 1
    return ''.join(result).encode('utf-16', 'surrogatepass').decode('utf-16', 'surrogatepass')


def nested_commands(code):
    """Literal cmd fields of direct tools.exec_command calls in Codex JS wrappers."""
    pattern = (r"'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"|`(?:\\.|[^`\\])*`|"
               r'//[^\n]*|/\*.*?\*/|[A-Za-z_$][\w$]*|[^\s]')
    tokens = [m[0] for m in re.finditer(pattern, code, re.S)
              if not m[0].startswith(('//', '/*'))]
    for index in range(len(tokens) - 5):
        if tokens[index:index + 5] != ['tools', '.', 'exec_command', '(', '{']:
            continue
        depth = 1
        for position in range(index + 5, len(tokens) - 3):
            token = tokens[position]
            if token in ('{', '['):
                depth += 1
            elif token in ('}', ']'):
                depth -= 1
                if depth == 0:
                    break
            if depth != 1 or token.strip('\'"') not in ('cmd', 'command') or tokens[position + 1] != ':':
                continue
            literal = tokens[position + 2]
            if tokens[position + 3] not in (',', '}'):
                continue
            try:
                value = js_string(literal)
            except ValueError:
                continue
            yield value


def native_review(name, arguments):
    short = name.rsplit('.', 1)[-1]
    if short in ('Bash', 'Monitor', 'exec_command'):
        command = arguments.get('command', arguments.get('cmd', ''))
        return isinstance(command, str) and shell_review(command)
    if short == 'exec':
        return any(shell_review(command) for command in nested_commands(arguments.get('code', '')))
    return False
