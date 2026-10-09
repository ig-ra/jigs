import { atom, read, update } from 'claude-code'
import type { Register } from 'claude-code'

import type { TicketBandStatus, TicketBandStep, TicketLoopState } from '../types'

// The ticket loop (skills/ticket) writes <TMPDIR or /tmp>/igr-ticket/<key>/state.json, the key
// being the session's worktree folder, e.g. .../worktrees/<owner>/saw-11847 -> igr-ticket/saw-11847.
// No file, no band: sessions outside the ticket loop draw nothing.
const raw = atom({ plugin: 'igr', key: 'ticketBandRaw' } as const, null)

const RULE = '─'.repeat(10)

const ICON: Record<TicketBandStatus, string> = { done: '✅', running: '⏳', fixing: '🔧', todo: '⬜', fail: '❌' }

// The three lines, fixed here so no session can add, drop or rename them.
const LINES: ReadonlyArray<{ key: 'implement' | 'reviews' | 'checks'; label: string }> = [
  { key: 'implement', label: 'Implement → rebase on main → open PR' },
  { key: 'reviews', label: 'Reviews: simplify + codex + claude → fix → rebase + re-push' },
  { key: 'checks', label: 'Architect + CI' },
]

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    const refresh = async () => {
      let text: string | null = null
      try {
        const base = (await $.session.cwd()).split('/').pop() ?? ''
        const tmp = ((await $.env.get('TMPDIR')) || '/tmp').replace(/\/+$/, '')
        text = await $.fs.read(`${tmp}/igr-ticket/${base}/state.json`)
      } catch {
        text = null
      }
      if (text !== (await read($, raw))) await update($, raw, () => text)
    }
    await refresh()
    $.clock.every(5000, refresh)
    return next(e)
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const text = await read($, raw)
    if (e.props.hasSurvey || text === null) return next(e)

    let loop: TicketLoopState
    try {
      loop = JSON.parse(text) as TicketLoopState
    } catch {
      return next(e)
    }

    const { Box, Button, Text } = $.ui.resolve(e)
    const { prUrl, ticketUrl } = loop

    // Inside herdr the terminal draws no clickable links, so the ticket and PR open in the browser on press.
    // A plain Button drops the `[ label ]` chrome; the tight brackets around it are drawn here.
    // Fixed pieces never shrink: a shrinking row otherwise eats the brackets and spaces first.
    const bracketed = (key: string, label: string, onPress: () => unknown) => (
      <Box key={key} flexShrink={0}>
        <Text dimColor>[</Text>
        <Button plain dimColor label={label} onPress={onPress} />
        <Text dimColor>]</Text>
      </Box>
    )
    const fixed = (key: string, text: string) => (
      <Box key={key} flexShrink={0}><Text dimColor>{text}</Text></Box>
    )
    return (
      <Box flexDirection="column">
        {/* One dim full-width rule carries the ticket, the PR and hide, so the band stays quiet. */}
        <Box>
          {fixed('lead', `${RULE} `)}
          {ticketUrl
            ? bracketed('ticket', loop.ticket, () => $.process.run(['open', ticketUrl]))
            : fixed('ticket', `[${loop.ticket}]`)}
          {loop.pr ? fixed('mid', ` ${RULE} `) : null}
          {loop.pr && prUrl
            ? bracketed('pr', `PR #${loop.pr}`, () => $.process.run(['open', prUrl]))
            : loop.pr ? fixed('pr', `[PR #${loop.pr}]`) : null}
          {/* The rule fills whatever width is left and is clipped, not truncated with an ellipsis.
              The engine's own `[-]` collapse mark sits right after it, at the end of this row. */}
          <Box flexGrow={1} flexShrink={1} width={0} height={1} marginLeft={1} overflow="hidden">
            <Text dimColor wrap="wrap">{'─'.repeat(400)}</Text>
          </Box>
        </Box>
        {LINES.map(({ key, label }) => {
          const step: TicketBandStep = loop[key] ?? { status: 'todo' }
          // A line appears once its step starts.
          if (step.status === 'todo') return null
          return (
            <Text key={key} dimColor>
              {ICON[step.status]} {label}
              {step.note ? ` — ${step.note}` : ''}
            </Text>
          )
        })}
      </Box>
    )
  })
}
