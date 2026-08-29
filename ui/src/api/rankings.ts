import type { Position, PlayerDetail, Ranking, RankingFilters, Tier, TierLabel } from '../types'
import { apiFetch, SEASON, MODEL_VERSION } from './client'

interface BackendRanking {
  rank: number
  gsis_id: string
  espn_id: string | null
  name: string
  position: string
  team: string | null
  vor: number | null
  vor_rank: number | null
  adp: number | null
  adp_delta: number | null
  tier: number | null
  mean_projection: number | null
  sim_mean: number | null
  sim_p10: number | null
  sim_p90: number | null

  avail_mean: number | null
}

export interface BackendScarcity {
  position: string
  total_players: number
  top_tier_count: number
  vor_dropoff: number | null
}

const TIER_LABELS: Record<number, TierLabel> = {
  1: 'TIER 1 — ELITE',
  2: 'TIER 2 — HIGH-END',
  3: 'TIER 3 — SOLID STARTER',
  4: 'TIER 4 — STREAMER',
  5: 'TIER 5 — DEEP BENCH',
}

function clampTier(t: number | null): Tier['number'] {
  return Math.min(5, Math.max(1, t ?? 5)) as Tier['number']
}

export function toRanking(r: BackendRanking, positionRank: number): Ranking {
  const tier = clampTier(r.tier)
  const player: PlayerDetail = {
    id: r.gsis_id,
    name: r.name,
    position: r.position as Position,
    team: r.team ?? '',
    byeWeek: 0,
    age: 0,
    experience: 0,
    imageUrl: r.espn_id
      ? `https://a.espncdn.com/i/headshots/nfl/players/full/${r.espn_id}.png`
      : null,
    injuryStatus: null,
    injuryNote: null,
    projection: {
      mean: r.mean_projection ?? 0,
      median: r.sim_mean ?? 0,
      floor: r.sim_p10 ?? 0,
      ceiling: r.sim_p90 ?? 0,
      p10: r.sim_p10 ?? 0,
      p25: 0,
      p75: 0,
      p90: r.sim_p90 ?? 0,
      stdDev: 0,
      gamesPlayed: 17,
    },
    opportunity: {
      targetShare: null,
      routeParticipation: null,
      snapShare: 0,
      rushShare: null,
      redZoneUsage: null,
      targets: null,
      carries: null,
    },
    efficiency: {
      yardsPerRouteRun: null,
      epaPerPlay: null,
      successRate: null,
      explosivePlayRate: null,
      yardsPerCarry: null,
      yardsPerTarget: null,
      catchRate: null,
      completionPct: null,
      yardsPerAttempt: null,
    },
    projectedStats: {
      targets: null,
      receptions: null,
      recYards: null,
      recTds: null,
      rushAttempts: null,
      rushYards: null,
      rushTds: null,
      passAttempts: null,
      completions: null,
      passYards: null,
      passTds: null,
      interceptions: null,
    },
    rookieYear: false,
    collegeTeam: null,
    depthChartPosition: 1,
  }
  return {
    rank: r.rank,
    positionRank,
    player,
    tier: { number: tier, label: TIER_LABELS[tier] },
    projection: r.mean_projection ?? 0,
    vor: r.vor ?? 0,
    adp: r.adp ?? 999,
    modelRank: r.vor_rank ?? 999,
    adpDelta: Math.round(r.adp_delta ?? 0),
    replacementLevel: 0,
    floor: r.sim_p10 ?? 0,
    ceiling: r.sim_p90 ?? 0,
    targetShare: null,
    rushShare: null,
    snapPct: null,
    routePct: null,
    redZoneUsage: null,
    tdProjection: 0,
    gamesPlayed: 17,
  }
}

export async function fetchRankings(filters: RankingFilters): Promise<Ranking[]> {
  const params = new URLSearchParams({
    season: String(SEASON),
    model_version: MODEL_VERSION,
    sort: 'vor_rank',
  })
  if (filters.position !== 'ALL') params.set('position', filters.position)
  const data = await apiFetch<BackendRanking[]>(`/rankings?${params}`)
  const posCounters: Record<string, number> = {}
  return data.map(r => {
    posCounters[r.position] = (posCounters[r.position] ?? 0) + 1
    return toRanking(r, posCounters[r.position])
  })
}

export async function fetchScarcity(): Promise<BackendScarcity[]> {
  const params = new URLSearchParams({ season: String(SEASON), model_version: MODEL_VERSION })
  return apiFetch<BackendScarcity[]>(`/scarcity?${params}`)
}
