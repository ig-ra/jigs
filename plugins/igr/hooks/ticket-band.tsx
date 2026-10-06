import { atom, read, update } from 'claude-code'
import type { Register } from 'claude-code'

import type { TicketLoopRow, TicketLoopState } from '../types'

// The ticket loop (skills/ticket) writes <loop dir>/state.json; the loop dir is named
// after the session's worktree folder, e.g. .../worktrees/igor/saw-11847 -> saw-11847-loop.
// No file, no band: sessions outside the ticket loop draw nothing.
const LOOP_ROOT = '/private/tmp/claude-501'

const raw = atom({ plugin: 'igr', key: 'ticketBandRaw' } as const, null)
const isHidden = atom({ plugin: 'igr', key: 'ticketBandHidden' } as const, false)

const ICON: Record<TicketLoopRow['status'], string> = { done: '✅', running: '⏳', fixing: '🔧', todo: '⬜', fail: '❌' }

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    const refresh = async () => {
      let text: string | null = null
      try {
        const base = (await $.session.cwd()).split('/').pop() ?? ''
        text = await $.fs.read(`${LOOP_ROOT}/${base}-loop/state.json`)
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
        {loop.rows.map(row => (
          <Text key={row.step} dimColor={row.status === 'todo'}>
            {ICON[row.status]} {row.step}
            {row.note ? ` — ${row.note}` : ''}
          </Text>
        ))}
      </Box>
    )
  })
}
