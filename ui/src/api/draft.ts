import type {
  Position, PlayerDetail, LiveDraftState,
  RecommendationState, FutureAvailability, Tier, TierLabel,
  WaitScenario, NextRoundPositionSummary,
} from '../types'
import { apiFetch, SEASON, MODEL_VERSION } from './client'

interface BackendPlayerProjection {
  gsis_id: string
  name: string
  position: string
  team: string
  vor: number
  vor_rank: number
  sim_mean: number
  sim_p10: number
  sim_p90: number
  adp: number
  tier: number | null
}

interface BackendExplanation {
  factor: string
  detail: string
  weight: string
}

interface BackendRecommendation {
  player: BackendPlayerProjection
  draft_score: number
  roster_fit: number
  positional_urgency: number
  future_availability_pct: number
  explanation: BackendExplanation[]
}

interface BackendWaitScenario {
  position: string
  best_now_name: string
  best_now_vor: number
  expected_vor_at_next_pick: number
  vor_cost_of_waiting: number
  cliff_before_next_pick: boolean
  survival_probability: number
}

interface BackendNextRoundSummary {
  position: string
  strong_options_remaining: number
  next_cliff_rank: number | null
  cliff_warning: boolean
}

interface BackendRecommendationState {
  top_pick: BackendRecommendation
  alternatives: BackendRecommendation[]
  positional_needs: string[]
  may_not_make_it_back: BackendPlayerProjection[]
  wait_analysis: BackendWaitScenario[]
  next_round_board: Record<string, BackendNextRoundSummary>
  board_state: { current_pick: number; round: number; picks_until_next: number }
}

const TIER_LABELS: Record<number, TierLabel> = {
  1: 'TIER 1 — ELITE',
  2: 'TIER 2 — HIGH-END',
  3: 'TIER 3 — SOLID STARTER',
  4: 'TIER 4 — STREAMER',
  5: 'TIER 5 — DEEP BENCH',
}

const POSITIONS: Position[] = ['QB', 'RB', 'WR', 'TE']

function clampTier(t: number | null): Tier['number'] {
  return Math.min(5, Math.max(1, t ?? 5)) as Tier['number']
}

function toPlayerDetailFromProjection(p: BackendPlayerProjection): PlayerDetail {
  return {
    id: p.gsis_id,
    name: p.name,
    position: p.position as Position,
    team: p.team,
    byeWeek: 0,
    age: 0,
    experience: 0,
    imageUrl: null,
    injuryStatus: null,
    injuryNote: null,
    projection: {
      mean: p.sim_mean,
      median: p.sim_mean,
      floor: p.sim_p10,
      ceiling: p.sim_p90,
      p10: p.sim_p10,
      p25: 0,
      p75: 0,
      p90: p.sim_p90,
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
}

function mapRecommendation(r: BackendRecommendation): RecommendationState['topPick'] {
  const p = r.player
  const tier = clampTier(p.tier)
  const prob = r.future_availability_pct
  const player = toPlayerDetailFromProjection(p)

  return {
    rank: p.vor_rank,
    positionRank: 0,
    player,
    tier: { number: tier, label: TIER_LABELS[tier] } as Tier,
    projection: p.sim_mean,
    vor: p.vor,
    adp: p.adp,
    modelRank: p.vor_rank,
    adpDelta: 0,
    replacementLevel: 0,
    floor: p.sim_p10,
    ceiling: p.sim_p90,
    targetShare: null,
    rushShare: null,
    snapPct: null,
    routePct: null,
    redZoneUsage: null,
    tdProjection: 0,
    gamesPlayed: 17,
    draftScore: r.draft_score,
    rosterFit: r.roster_fit,
    futureAvailability: {
      playerId: p.gsis_id,
      probability: prob,
      label: prob > 0.7 ? 'urgent' : prob > 0.3 ? 'monitor' : 'safe',
    } as FutureAvailability,
    explanation: r.explanation.map(e => ({
      factor: e.factor,
      detail: e.detail,
      weight: e.weight as 'primary' | 'secondary' | 'risk',
    })),
  }
}

function mapWaitScenario(w: BackendWaitScenario): WaitScenario {
  return {
    position: w.position,
    bestNowName: w.best_now_name,
    bestNowVor: w.best_now_vor,
    expectedVorAtNextPick: w.expected_vor_at_next_pick,
    vorCostOfWaiting: w.vor_cost_of_waiting,
    cliffBeforeNextPick: w.cliff_before_next_pick,
    survivalProbability: w.survival_probability,
  }
}

function mapNextRoundSummary(s: BackendNextRoundSummary): NextRoundPositionSummary {
  return {
    position: s.position,
    strongOptionsRemaining: s.strong_options_remaining,
    nextCliffRank: s.next_cliff_rank,
    cliffWarning: s.cliff_warning,
  }
}

function toDraftStateIn(state: LiveDraftState) {
  return {
    season: SEASON,
    model_version: MODEL_VERSION,
    league_settings: {
      teams: state.config.teams,
      scoring: 'full',
      roster_config: {
        QB: state.config.rosterConfig.QB,
        RB: state.config.rosterConfig.RB,
        WR: state.config.rosterConfig.WR,
        TE: state.config.rosterConfig.TE,
        FLEX: state.config.rosterConfig.FLEX,
      },
    },
    current_pick: state.currentOverallPick,
    total_picks: state.config.teams * state.config.totalRounds,
    user_pick_position: state.config.userPickPosition,
    pick_log: state.picks.map(p => ({
      gsis_id: p.player.id,
      team_number: p.teamNumber,
      position: p.player.position,
    })),
    user_roster: (() => {
      const roster: Record<string, string[]> = {}
      for (const pick of state.picks.filter(p => p.isUserPick)) {
        const pos = pick.player.position
        ;(roster[pos] ??= []).push(pick.player.id)
      }
      return roster
    })(),
  }
}

export async function fetchRecommendation(state: LiveDraftState): Promise<RecommendationState> {
  const data = await apiFetch<BackendRecommendationState>('/draft/recommend', {
    method: 'POST',
    body: JSON.stringify(toDraftStateIn(state)),
  })

  const positionalNeeds = Object.fromEntries(
    POSITIONS.map(pos => {
      const idx = data.positional_needs.indexOf(pos)
      if (idx === -1) return [pos, 0]
      const urgency =
        idx === 0 ? 1.0
        : idx === 1 ? 0.75
        : idx === 2 ? 0.5
        : 0.25
      return [pos, urgency]
    })
  ) as Record<Position, number>

  const mayNotMakeItBack: FutureAvailability[] = data.may_not_make_it_back.map(p => ({
    playerId: p.gsis_id,
    probability: 0.75,
    label: 'urgent' as const,
  }))

  return {
    topPick: mapRecommendation(data.top_pick),
    alternatives: data.alternatives.map(mapRecommendation),
    positionalNeeds,
    waitAnalysis: data.wait_analysis.map(mapWaitScenario),
    nextRoundBoard: Object.fromEntries(
      Object.entries(data.next_round_board).map(([pos, s]) => [pos, mapNextRoundSummary(s)])
    ),
    mayNotMakeItBack,
  }
}

export async function saveSession(sessionId: string, state: LiveDraftState): Promise<void> {
  await apiFetch('/draft/session', {
    method: 'POST',
    body: JSON.stringify({
      session_id: sessionId,
      drafted_ids: state.picks.map(p => p.player.id),
      league_settings: toDraftStateIn(state).league_settings,
    }),
  })
}

export async function loadSession(_sessionId: string): Promise<LiveDraftState | null> {
  return null
}
