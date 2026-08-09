import type { Position } from './player'
import type { Ranking } from './ranking'

export interface FutureAvailability {
  playerId: string
  probability: number    // 0–1, probability player is GONE before user's next pick
  label: 'safe' | 'monitor' | 'urgent'
}

export interface PositionalScarcity {
  position: Position
  viableRemaining: number
  scarcityScore: number   // 0–1
  tierRemaining: number
}

export interface RecommendationExplanation {
  factor: string
  detail: string
  weight: 'primary' | 'secondary' | 'risk'
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
  scarcity: PositionalScarcity[]
  mayNotMakeItBack: FutureAvailability[]
}
