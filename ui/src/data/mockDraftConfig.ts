import type { DraftConfig } from '../types'

export const DEFAULT_DRAFT_CONFIG: DraftConfig = {
  teams: 12,
  userPickPosition: 6,
  scoringFormat: 'ppr',
  rosterConfig: {
    QB: 1,
    RB: 2,
    WR: 2,
    TE: 1,
    FLEX: 1,
    BENCH: 6,
    K: 0,
    DST: 0,
  },
  totalRounds: 13,   // 1+2+2+1+1+6 = 13
}
