export type TicketBandStatus = 'done' | 'running' | 'fixing' | 'todo' | 'fail'

export type TicketBandStep = { status: TicketBandStatus; note?: string }

/** The band owns its three lines; the file only says where each one stands. */
export type TicketLoopState = {
  ticket: string
  ticketUrl?: string
  pr?: number
  prUrl?: string
  implement?: TicketBandStep
  reviews?: TicketBandStep
  checks?: TicketBandStep
}

declare module 'claude-code' {
  interface PluginState {
    igr: { ticketBandRaw: string | null }
  }
}
