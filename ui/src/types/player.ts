export type Position = 'QB' | 'RB' | 'WR' | 'TE' | 'K' | 'DST'
export type NFLTeam = string  // 'KC', 'BUF', 'PHI', etc.
export type ScoringFormat = 'standard' | 'half_ppr' | 'ppr'
export type DraftType = 'redraft' | 'best_ball' | 'dynasty'

export interface Projection {
  mean: number
  median: number
  floor: number
  ceiling: number
  p10: number
  p25: number
  p75: number
  p90: number
  stdDev: number
  gamesPlayed: number
}

export interface OpportunityMetrics {
  targetShare: number | null        // 0–1, null for QB/RB
  routeParticipation: number | null
  snapShare: number
  rushShare: number | null          // null for WR/TE
  redZoneUsage: number | null
  targets: number | null
  carries: number | null
}

export interface EfficiencyMetrics {
  yardsPerRouteRun: number | null
  epaPerPlay: number | null
  successRate: number | null
  explosivePlayRate: number | null
  yardsPerCarry: number | null
  yardsPerTarget: number | null
  catchRate: number | null
  completionPct: number | null       // QB only
  yardsPerAttempt: number | null    // QB only
}

export interface Player {
  id: string
  name: string
  position: Position
  team: NFLTeam
  byeWeek: number
  age: number
  experience: number                // years in NFL
  imageUrl: string | null
  injuryStatus: 'healthy' | 'questionable' | 'doubtful' | 'out' | 'ir' | null
  injuryNote: string | null
}

export interface PlayerDetail extends Player {
  projection: Projection
  opportunity: OpportunityMetrics
  efficiency: EfficiencyMetrics
  modelConfidence: number           // 0–1
  rookieYear: boolean
  collegeTeam: string | null
  depthChartPosition: number        // 1 = starter, 2 = backup, etc.
}
