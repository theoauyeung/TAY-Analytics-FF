import type { Position, PlayerDetail, ScoringFormat } from './player'

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

export interface DraftState {
  leagueId: string
  teams: number
  scoringFormat: ScoringFormat
  rosterConfig: Record<string, number>  // { QB: 1, RB: 2, WR: 2, TE: 1, FLEX: 1, BENCH: 6 }
  currentRound: number
  currentPick: number
  userDraftPosition: number
  picksUntilNextTurn: number
  draftedPlayerIds: string[]
  userRoster: Roster
}
