import type { Position, ScoringFormat, DraftType, PlayerDetail } from './player'

export type TierLabel =
  | 'TIER 1 — ELITE'
  | 'TIER 2 — HIGH-END'
  | 'TIER 3 — SOLID STARTER'
  | 'TIER 4 — STREAMER'
  | 'TIER 5 — DEEP BENCH'

export interface Tier {
  number: 1 | 2 | 3 | 4 | 5
  label: TierLabel
}

export interface Ranking {
  rank: number
  positionRank: number
  player: PlayerDetail
  tier: Tier
  projection: number                 // mean fantasy points for selected format
  vor: number                        // value over replacement
  adp: number                        // ESPN ADP
  modelRank: number
  adpDelta: number                   // vor_rank − ADP (negative = model ranks higher = undervalued)
  replacementLevel: number
  // toggleable columns
  floor: number
  ceiling: number
  targetShare: number | null
  rushShare: number | null
  snapPct: number | null
  routePct: number | null
  redZoneUsage: number | null
  tdProjection: number
  gamesPlayed: number
  modelConfidence: number
}

export type ColumnKey =
  | 'rank' | 'player' | 'position' | 'team' | 'bye'
  | 'projection' | 'vor' | 'adp' | 'modelRank' | 'tier'
  | 'floor' | 'ceiling' | 'targetShare' | 'rushShare'
  | 'snapPct' | 'routePct' | 'redZoneUsage' | 'tdProjection'
  | 'gamesPlayed' | 'modelConfidence' | 'adpDelta'

export const CORE_COLUMNS: ColumnKey[] = [
  'rank', 'player', 'position', 'team', 'bye',
  'projection', 'vor', 'adp', 'modelRank',
]

export const OPTIONAL_COLUMNS: ColumnKey[] = [
  'floor', 'ceiling', 'targetShare', 'rushShare',
  'snapPct', 'routePct', 'redZoneUsage', 'tdProjection',
  'gamesPlayed', 'modelConfidence', 'adpDelta',
]

export const COLUMN_LABELS: Record<ColumnKey, string> = {
  rank: 'Rank', player: 'Player', position: 'Pos', team: 'Team', bye: 'Bye',
  projection: 'Proj', vor: 'VOR', adp: 'ADP', modelRank: 'Mdl', tier: 'Tier',
  floor: 'Floor', ceiling: 'Ceil', targetShare: 'Tgt%', rushShare: 'Rush%',
  snapPct: 'Snap%', routePct: 'Route%', redZoneUsage: 'RZ%',
  tdProjection: 'TD Proj', gamesPlayed: 'GP', modelConfidence: 'Conf',
  adpDelta: 'ADP Δ',
}

export interface RankingFilters {
  format: ScoringFormat
  draftType: DraftType
  position: Position | 'ALL'
  search: string
  year: number
  tierFilter: number | null
}
