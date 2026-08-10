import { MOCK_RANKINGS } from './mockRankings'
import type { Ranking } from '../types'

export const TOP_VALUES: Ranking[] = MOCK_RANKINGS
  .filter(r => r.adpDelta < -5)
  .sort((a, b) => a.adpDelta - b.adpDelta)
  .slice(0, 8)

export const POSITION_LEADERS: Record<string, Ranking> = Object.fromEntries(
  (['QB', 'RB', 'WR', 'TE'] as const).map(pos => [
    pos,
    MOCK_RANKINGS.find(r => r.player.position === pos)!,
  ])
)

export const SCARCITY_OVERVIEW: Record<string, number> = Object.fromEntries(
  (['QB', 'RB', 'WR', 'TE'] as const).map(pos => [
    pos,
    MOCK_RANKINGS.filter(r => r.player.position === pos && r.vor > 0).length,
  ])
)

export const MODEL_MOVERS: { rising: Ranking[]; falling: Ranking[] } = {
  rising:  MOCK_RANKINGS.filter(r => r.adpDelta < -8).slice(0, 5),
  falling: MOCK_RANKINGS.filter(r => r.adpDelta > 8).slice(0, 5),
}
