import type { Position, PlayerDetail } from './player'
import type { Ranking } from './ranking'

export interface FutureAvailability {
  playerId: string
  probability: number    // 0–1, probability player is GONE before user's next pick
  label: 'safe' | 'monitor' | 'urgent'
}

export interface RecommendationExplanation {
  factor: string
  detail: string
  weight: 'primary' | 'secondary' | 'risk'
}

export interface ScoredPlayer {
  player: PlayerDetail
  score: number
  explanation: RecommendationExplanation[]
}

export interface WaitScenario {
  position: string
  bestNowName: string
  bestNowVor: number
  expectedVorAtNextPick: number
  vorCostOfWaiting: number
  cliffBeforeNextPick: boolean
  survivalProbability: number
}

export interface NextRoundPositionSummary {
  position: string
  strongOptionsRemaining: number
  nextCliffRank: number | null
  cliffWarning: boolean
}

export interface RecommendationState {
  topPick: Ranking & {
    draftScore: number
    rosterFit: number
    futureAvailability: FutureAvailability
    explanation: RecommendationExplanation[]
  }
  alternatives: Array<Ranking & {
    draftScore: number
    rosterFit: number
    futureAvailability: FutureAvailability
    explanation: RecommendationExplanation[]
  }>
  positionalNeeds: Record<Position, number>   // 0–1 urgency
  waitAnalysis: WaitScenario[]
  nextRoundBoard: Record<string, NextRoundPositionSummary>
  mayNotMakeItBack: FutureAvailability[]
}
