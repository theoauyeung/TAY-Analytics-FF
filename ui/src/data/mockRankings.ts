import type { Ranking, Tier } from '../types'
import { MOCK_PLAYERS } from './mockPlayers'

const REPLACEMENT_LEVELS: Record<string, number> = {
  QB:  215,
  RB:  130,
  WR:  145,
  TE:   80,
  K:   100,
  DST: 100,
}

function assignTier(vor: number): Tier {
  if (vor >= 50) return { number: 1, label: 'TIER 1 — ELITE' }
  if (vor >= 25) return { number: 2, label: 'TIER 2 — HIGH-END' }
  if (vor >= 10) return { number: 3, label: 'TIER 3 — SOLID STARTER' }
  if (vor >= 0)  return { number: 4, label: 'TIER 4 — STREAMER' }
  return { number: 5, label: 'TIER 5 — DEEP BENCH' }
}

// Deterministic ADP offset — no Math.random() so values are stable across renders
function adpNoise(rank: number): number {
  const offset = rank % 3 === 0 ? -2 : rank % 3 === 1 ? 3 : -1
  return Math.max(1, rank + offset)
}

const ranked = MOCK_PLAYERS
  .map((player) => {
    const repl = REPLACEMENT_LEVELS[player.position] ?? 100
    const proj = player.projection.mean
    const vor = Math.round((proj - repl) * 10) / 10
    const tier = assignTier(vor)
    return { player, proj, vor, tier }
  })
  .sort((a, b) => b.vor - a.vor)
  .map((item, i): Omit<Ranking, 'positionRank'> => {
    const modelRank = i + 1
    const adp = adpNoise(modelRank)
    return {
      rank: modelRank,
      player: item.player,
      tier: item.tier,
      projection: item.proj,
      vor: item.vor,
      adp,
      modelRank,
      adpDelta: modelRank - adp,
      replacementLevel: REPLACEMENT_LEVELS[item.player.position] ?? 100,
      floor: item.player.projection.floor,
      ceiling: item.player.projection.ceiling,
      targetShare: item.player.opportunity.targetShare,
      rushShare: item.player.opportunity.rushShare,
      snapPct: item.player.opportunity.snapShare,
      routePct: item.player.opportunity.routeParticipation,
      redZoneUsage: item.player.opportunity.redZoneUsage,
      tdProjection: Math.round(item.proj / 22),
      gamesPlayed: item.player.projection.gamesPlayed,
      modelConfidence: item.player.modelConfidence,
    }
  })

// Back-fill positionRank in place
const positionCounts: Record<string, number> = {}
export const MOCK_RANKINGS: Ranking[] = ranked.map((r) => {
  const pos = r.player.position
  positionCounts[pos] = (positionCounts[pos] ?? 0) + 1
  return { ...r, positionRank: positionCounts[pos] }
})
