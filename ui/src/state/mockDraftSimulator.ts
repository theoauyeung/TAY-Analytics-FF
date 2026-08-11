import { useState, useEffect, useCallback } from 'react'
import type { PlayerDetail, Ranking } from '../types'
import { useDraftState } from '../hooks/useDraftState'
import { useRankings } from '../hooks/useRankings'

export function bestAvailablePlayer(draftedIds: string[], rankings: Ranking[]): PlayerDetail | null {
  const pick = rankings.find(r => !draftedIds.includes(r.player.id))
  return pick?.player ?? null
}

export function useAutoAdvance() {
  const { state, draftPlayer, isUserTurn } = useDraftState()
  const { rankings } = useRankings({
    position: 'ALL',
    search: '',
    format: 'ppr',
    draftType: 'redraft',
    year: 2026,
    tierFilter: null,
  })
  const [autoAdvancing, setAutoAdvancing] = useState(false)

  const isDraftComplete =
    state.currentOverallPick > state.config.teams * state.config.totalRounds

  useEffect(() => {
    if (!autoAdvancing) return
    if (isUserTurn || isDraftComplete) {
      setAutoAdvancing(false)
      return
    }
    if (rankings.length === 0) return  // still loading
    const draftedIds = state.picks.map(p => p.player.id)
    const pick = bestAvailablePlayer(draftedIds, rankings)
    if (!pick) {
      setAutoAdvancing(false)
      return
    }
    const timer = setTimeout(() => draftPlayer(pick), 150)
    return () => clearTimeout(timer)
  }, [autoAdvancing, isUserTurn, isDraftComplete, state.picks, draftPlayer, rankings])

  const startAutoAdvance = useCallback(() => setAutoAdvancing(true), [])
  const stopAutoAdvance = useCallback(() => setAutoAdvancing(false), [])

  return { autoAdvancing, startAutoAdvance, stopAutoAdvance }
}
