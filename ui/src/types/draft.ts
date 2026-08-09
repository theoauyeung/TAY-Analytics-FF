import type { Position, PlayerDetail, ScoringFormat } from './player'

export interface RosterConfig {
  QB: number
  RB: number
  WR: number
  TE: number
  FLEX: number
  BENCH: number
  K: number
  DST: number
}

export interface RosterSlot {
  slotType: Position | 'FLEX' | 'BENCH' | 'IR'
  player: PlayerDetail | null
}

export interface Roster {
  slots: RosterSlot[]
  totalProjection: number
  floor: number
  ceiling: number
  positionalStrength: Record<Position, 'elite' | 'strong' | 'average' | 'weak' | 'empty'>
  primaryNeed: Position | null
}

export interface DraftConfig {
  teams: number               // e.g. 12
  userPickPosition: number    // 1-indexed pick in round 1 (e.g. 6)
  scoringFormat: ScoringFormat
  rosterConfig: RosterConfig
  totalRounds: number         // sum of all rosterConfig values
}

export interface DraftedPick {
  player: PlayerDetail
  overallPick: number         // 1-indexed overall pick number
  round: number
  pickInRound: number         // 1-indexed within the round
  teamNumber: number          // which team picked (1-indexed)
  isUserPick: boolean
}

export interface LiveDraftState {
  config: DraftConfig
  picks: DraftedPick[]        // all picks made so far in order
  currentOverallPick: number  // next pick to be made (1-indexed)
}

// Legacy — kept for type compatibility, not used by Draft Assistant
export interface DraftState {
  leagueId: string
  teams: number
  scoringFormat: ScoringFormat
  rosterConfig: Record<string, number>
  currentRound: number
  currentPick: number
  userDraftPosition: number
  picksUntilNextTurn: number
  draftedPlayerIds: string[]
  userRoster: Roster
}
