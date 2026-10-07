import { atom, read, update } from 'claude-code'
import type { Register } from 'claude-code'

import type { TicketBandStatus, TicketBandStep, TicketLoopState } from '../types'

// The ticket loop (skills/ticket) writes <TMPDIR or /tmp>/igr-ticket/<key>/state.json, the key
// being the session's worktree folder, e.g. .../worktrees/<owner>/saw-11847 -> igr-ticket/saw-11847.
// No file, no band: sessions outside the ticket loop draw nothing.
const raw = atom({ plugin: 'igr', key: 'ticketBandRaw' } as const, null)
const isHidden = atom({ plugin: 'igr', key: 'ticketBandHidden' } as const, false)

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
    if (e.props.hasSurvey || text === null || (await read($, isHidden))) return next(e)

    let loop: TicketLoopState
    try {
      loop = JSON.parse(text) as TicketLoopState
    } catch {
      return next(e)
    }

    const { Box, Button, Text } = $.ui.resolve(e)
    const { prUrl, ticketUrl } = loop

    // Inside herdr the terminal draws no clickable links, so the ticket and PR open in the browser on press.
    return (
      <Box flexDirection="column">
        <Box>
          {ticketUrl
            ? <Button key="ticket" label={loop.ticket} onPress={() => $.process.run(['open', ticketUrl])} />
            : <Text bold>{loop.ticket}</Text>}
          <Text>{loop.pr ? ' · ' : ' '}</Text>
          {loop.pr && prUrl ? (
            <Button key="pr" label={`PR #${loop.pr}`} onPress={() => $.process.run(['open', prUrl])} />
          ) : loop.pr ? <Text bold>PR #{loop.pr}</Text> : null}
          <Text>{loop.pr ? ' · ' : ' '}</Text>
          <Button key="hide" label="Hide" onPress={() => update($, isHidden, () => true)} />
        </Box>
        {LINES.map(({ key, label }) => {
          const step: TicketBandStep = loop[key] ?? { status: 'todo' }
          return (
            <Text key={key} dimColor={step.status === 'todo'}>
              {ICON[step.status]} {label}
              {step.note ? ` — ${step.note}` : ''}
            </Text>
          )
        })}
      </Box>
    )
  })
}
