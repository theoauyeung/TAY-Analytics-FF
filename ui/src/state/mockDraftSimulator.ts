import { useState, useEffect } from 'react'
import { MOCK_RANKINGS } from '../data'
import type { PlayerDetail } from '../types'
import { useDraftState } from '../hooks/useDraftState'

/** Pure function — returns the highest-VOR undrafted player. */
export function bestAvailablePlayer(draftedIds: string[]): PlayerDetail | null {
  const pick = MOCK_RANKINGS.find(r => !draftedIds.includes(r.player.id))
  return pick?.player ?? null
}

/**
 * Fires one auto-pick per render frame (via setTimeout) until isUserTurn is
 * true or the draft is complete. Calling startAutoAdvance() begins the loop;
 * it stops automatically when the user's turn arrives.
 */
export function useAutoAdvance() {
  const { state, draftPlayer, isUserTurn } = useDraftState()
  const [autoAdvancing, setAutoAdvancing] = useState(false)

  const isDraftComplete =
    state.currentOverallPick > state.config.teams * state.config.totalRounds

  useEffect(() => {
    if (!autoAdvancing) return
    if (isUserTurn || isDraftComplete) {
      setAutoAdvancing(false)
      return
    }
    const draftedIds = state.picks.map(p => p.player.id)
    const pick = bestAvailablePlayer(draftedIds)
    if (!pick) {
      setAutoAdvancing(false)
      return
    }
    // 150ms delay gives a visual "picks happening" feel
    const timer = setTimeout(() => draftPlayer(pick), 150)
    return () => clearTimeout(timer)
  }, [autoAdvancing, isUserTurn, isDraftComplete, state.picks, draftPlayer])

  return {
    autoAdvancing,
    startAutoAdvance: () => setAutoAdvancing(true),
    stopAutoAdvance: () => setAutoAdvancing(false),
  }
}
