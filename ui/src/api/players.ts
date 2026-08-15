import type { Position, PlayerDetail } from '../types'
import { apiFetch, SEASON, MODEL_VERSION } from './client'

interface BackendPlayer {
  gsis_id: string
  name: string
  position: string
  team: string | null
  season: number
  model_version: string
  mean_projection: number | null
  vor: number | null
  vor_rank: number | null
  tier: number | null
  adp_delta: number | null
  adp: number | null
  sim_mean: number | null
  sim_p10: number | null
  sim_p90: number | null
  avail_mean: number | null
}

function toPlayerDetail(p: BackendPlayer): PlayerDetail {
  return {
    id: p.gsis_id,
    name: p.name,
    position: p.position as Position,
    team: p.team ?? '',
    byeWeek: 0,
    age: 0,
    experience: 0,
    imageUrl: null,
    injuryStatus: null,
    injuryNote: null,
    projection: {
      mean: p.mean_projection ?? 0,
      median: p.sim_mean ?? 0,
      floor: p.sim_p10 ?? 0,
      ceiling: p.sim_p90 ?? 0,
      p10: p.sim_p10 ?? 0,
      p25: 0,
      p75: 0,
      p90: p.sim_p90 ?? 0,
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
    modelConfidence: p.avail_mean ?? 0,
    rookieYear: false,
    collegeTeam: null,
    depthChartPosition: 1,
  }
}

export async function fetchPlayers(filters?: { position?: string }): Promise<PlayerDetail[]> {
  const params = new URLSearchParams({ season: String(SEASON), model_version: MODEL_VERSION })
  if (filters?.position) params.set('position', filters.position)
  const data = await apiFetch<BackendPlayer[]>(`/players?${params}`)
  return data.map(toPlayerDetail)
}

export async function fetchPlayer(id: string): Promise<PlayerDetail> {
  const params = new URLSearchParams({ season: String(SEASON), model_version: MODEL_VERSION })
  const data = await apiFetch<BackendPlayer>(`/players/${id}?${params}`)
  return toPlayerDetail(data)
}
