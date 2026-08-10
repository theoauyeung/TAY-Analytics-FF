import { useMemo } from 'react'
import type { LiveDraftState, RosterConfig } from '../types'
import type {
  Ranking, RecommendationState, PositionalScarcity,
  FutureAvailability, RecommendationExplanation,
} from '../types'
import { MOCK_RANKINGS } from '../data'
import { computeUserPickNumbers } from '../state'

function clamp(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v))
}

/**
 * Roster fit score (0–1) for a position given the user's current roster.
 * Key insight: QBs have drastically lower marginal value after the first
 * in a 1-QB league — the model must reflect this.
 */
function rosterFitScore(
  position: string,
  userPositions: string[],
  config: RosterConfig
): number {
  const count = userPositions.filter(p => p === position).length

  if (position === 'QB') {
    if (count === 0) return 1.0
    if (count === 1) return 0.12   // backup QB has minimal value in 1-QB
    return 0.04
  }

  const starterSlots = (config[position as keyof RosterConfig] as number | undefined) ?? 0
  const flexSlots = (position === 'RB' || position === 'WR' || position === 'TE')
    ? config.FLEX : 0
  const benchSlots = Math.floor(config.BENCH / 4)   // rough bench depth allowance per position

  if (count < starterSlots) return 1.0
  if (count < starterSlots + flexSlots) return 0.72
  if (count < starterSlots + flexSlots + benchSlots) return 0.28
  return 0.05
}

interface ScoredRanking {
  ranking: Ranking
  draftScore: number
  rosterFit: number
  futureAvailability: FutureAvailability
  explanation: RecommendationExplanation[]
}

function buildExplanation(
  ranking: Ranking,
  components: { vor: number; fit: number; scarcity: number; urgency: number },
  pGone: number,
  userPositions: string[],
): RecommendationExplanation[] {
  const result: RecommendationExplanation[] = []
  const pos = ranking.player.position

  // Primary: projection value
  if (components.vor > 50) {
    result.push({
      factor: 'Strong Model Value',
      detail: `${ranking.projection.toFixed(0)} projected pts · VOR ${ranking.vor >= 0 ? '+' : ''}${ranking.vor.toFixed(1)} · Model rank #${ranking.modelRank}`,
      weight: 'primary',
    })
  }

  // Roster fit
  if (components.fit > 65) {
    const count = userPositions.filter(p => p === pos).length
    result.push({
      factor: count === 0 ? `No ${pos} Yet` : `${pos} Depth`,
      detail: count === 0
        ? `You have no ${pos} — fills a critical starting slot`
        : `Adds depth at ${pos} — fills flex or bench need`,
      weight: 'secondary',
    })
  }

  // Scarcity
  if (components.scarcity > 55) {
    result.push({
      factor: `${pos} Scarcity`,
      detail: `Viable ${pos}s running low — positional run likely soon`,
      weight: 'secondary',
    })
  }

  // Urgency
  if (pGone > 0.64) {
    result.push({
      factor: 'May Not Make It Back',
      detail: `~${Math.round(pGone * 100)}% chance drafted before your next pick`,
      weight: 'primary',
    })
  }

  // Market value
  if (ranking.adpDelta >= 5) {
    result.push({
      factor: 'Undervalued',
      detail: `Model ranks ${ranking.adpDelta} spots ahead of ESPN ADP`,
      weight: 'secondary',
    })
  }

  // Risk flags
  if (ranking.player.injuryStatus && ranking.player.injuryStatus !== 'healthy') {
    result.push({
      factor: 'Injury Risk',
      detail: `Currently ${ranking.player.injuryStatus} — monitor before draft`,
      weight: 'risk',
    })
  }
  if (ranking.player.rookieYear) {
    result.push({
      factor: 'Rookie Uncertainty',
      detail: 'Higher variance — production range is wide',
      weight: 'risk',
    })
  }

  return result.slice(0, 5)   // cap at 5 explanation bullets
}

export function useMockRecommendation(state: LiveDraftState): RecommendationState | null {
  return useMemo(() => {
    const draftedIds = new Set(state.picks.map(p => p.player.id))
    const available = MOCK_RANKINGS.filter(r => !draftedIds.has(r.player.id))

    if (available.length === 0) return null

    const userPickNumbers = computeUserPickNumbers(state.config)
    const nextUserPick = userPickNumbers.find(n => n >= state.currentOverallPick)
    const picksUntilNext = nextUserPick === undefined ? 0 : nextUserPick - state.currentOverallPick

    const userPositions = state.picks
      .filter(p => p.isUserPick)
      .map(p => p.player.position as string)

    // VOR normalization
    const vors = available.map(r => r.vor)
    const maxVOR = Math.max(...vors)
    const minVOR = Math.min(...vors)
    const vorRange = Math.max(1, maxVOR - minVOR)

    // Viable player counts per position (VOR > 0 = "viable")
    const viableCounts: Record<string, number> = {}
    for (const r of available) {
      if (r.vor > 0) {
        viableCounts[r.player.position] = (viableCounts[r.player.position] ?? 0) + 1
      }
    }

    // Score every available player
    const scored: ScoredRanking[] = available.map(ranking => {
      const pos = ranking.player.position

      // Component 1: VOR (35%)
      const vorScore = clamp((ranking.vor - minVOR) / vorRange, 0, 1) * 100

      // Component 2: Roster Fit (30%)
      const fitRaw = rosterFitScore(pos, userPositions, state.config.rosterConfig)
      const fitScore = fitRaw * 100

      // Component 3: Positional Scarcity (20%) — higher score = more scarce
      const viable = viableCounts[pos] ?? 0
      const scarcityScore = clamp(1 - viable / 18, 0, 1) * 100

      // Component 4: Urgency / Future Availability (15%)
      // P(gone before next pick) — if ADP is near current pick and many picks until user's turn, very urgent
      const adpGap = Math.max(1, ranking.adp - state.currentOverallPick + 1)
      const pGone = clamp(picksUntilNext / adpGap, 0, 1)
      const urgencyScore = pGone * 100

      const draftScore = Math.round(
        vorScore      * 0.35 +
        fitScore      * 0.30 +
        scarcityScore * 0.20 +
        urgencyScore  * 0.15
      )

      const futureAvailability: FutureAvailability = {
        playerId: ranking.player.id,
        probability: pGone,
        label: pGone > 0.75 ? 'urgent' : pGone > 0.55 ? 'monitor' : 'safe',
      }

      const components = { vor: vorScore, fit: fitScore, scarcity: scarcityScore, urgency: urgencyScore }
      const explanation = buildExplanation(ranking, components, pGone, userPositions)

      return { ranking, draftScore, rosterFit: fitRaw, futureAvailability, explanation }
    })

    scored.sort((a, b) => b.draftScore - a.draftScore)
    const [top, ...rest] = scored

    // Positional scarcity output
    const POSITIONS = ['QB', 'RB', 'WR', 'TE'] as const
    const scarcity: PositionalScarcity[] = POSITIONS.map(pos => ({
      position: pos,
      viableRemaining: viableCounts[pos] ?? 0,
      scarcityScore: clamp(1 - (viableCounts[pos] ?? 0) / 18, 0, 1),
      tierRemaining: available.filter(r => r.player.position === pos && r.tier.number <= 3).length,
    }))

    // Positional needs (0–1 urgency score per position)
    const positionalNeeds = Object.fromEntries(
      POSITIONS.map(pos => [pos, rosterFitScore(pos, userPositions, state.config.rosterConfig)])
    ) as Record<string, number>

    // May Not Make It Back — P(gone) > 0.64
    const mayNotMakeItBack: FutureAvailability[] = available
      .map(r => {
        const gap = Math.max(1, r.adp - state.currentOverallPick + 1)
        const prob = clamp(picksUntilNext / gap, 0, 1)
        return { playerId: r.player.id, probability: prob, label: prob > 0.75 ? 'urgent' : 'monitor' } as FutureAvailability
      })
      .filter(x => x.probability > 0.64)
      .sort((a, b) => b.probability - a.probability)
      .slice(0, 5)

    function toItem(s: ScoredRanking) {
      return {
        ...s.ranking,
        draftScore: s.draftScore,
        rosterFit: s.rosterFit,
        futureAvailability: s.futureAvailability,
        explanation: s.explanation,
      }
    }

    return {
      topPick: toItem(top),
      alternatives: rest.slice(0, 5).map(toItem),
      positionalNeeds,
      scarcity,
      mayNotMakeItBack,
    }
  }, [state])
}
