export type TicketLoopRow = { step: string; status: 'done' | 'running' | 'fixing' | 'todo' | 'fail'; note?: string }

export type TicketLoopState = {
  ticket: string
  ticketUrl?: string
  pr?: number
  prUrl?: string
  rows: TicketLoopRow[]
}

declare module 'claude-code' {
  interface PluginState {
    igr: { ticketBandRaw: string | null; ticketBandHidden: boolean }
  }
}
