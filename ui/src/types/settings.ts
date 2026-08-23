import type { ScoringFormat } from './player'

export interface RosterConfig {
  QB: number
  RB: number
  WR: number
  TE: number
  FLEX: number
  BENCH: number
}

export interface LeagueSettings {
  teams: number          // 8–16
  format: ScoringFormat  // 'ppr'
  rosterConfig: RosterConfig
}

export const DEFAULT_LEAGUE_SETTINGS: LeagueSettings = {
  teams: 12,
  format: 'ppr',
  rosterConfig: { QB: 1, RB: 2, WR: 2, TE: 1, FLEX: 1, BENCH: 6 },
}
