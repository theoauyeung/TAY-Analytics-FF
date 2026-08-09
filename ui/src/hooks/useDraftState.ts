import { useCallback } from 'react'
import { useDraftContext, computeUserPickNumbers, picksUntilNextTurn } from '../state/draftState'
import type { PlayerDetail } from '../types'

export function useDraftState() {
  const { state, dispatch } = useDraftContext()
  const { config, picks, currentOverallPick } = state

  const currentRound = Math.min(
    config.totalRounds,
    Math.ceil(currentOverallPick / config.teams)
  )

  const userPickNumbers = computeUserPickNumbers(config)
  const picksUntilNext = picksUntilNextTurn(state)

  const draftedIds = new Set(picks.map(p => p.player.id))
  const userRoster = picks.filter(p => p.isUserPick).map(p => p.player)

  const draftPlayer = useCallback(
    (player: PlayerDetail, isUserPick: boolean) => {
      dispatch({ type: 'DRAFT_PLAYER', player, isUserPick })
    },
    [dispatch]
  )

  const undoLastPick = useCallback(
    () => dispatch({ type: 'UNDO_LAST_PICK' }),
    [dispatch]
  )

  const resetDraft = useCallback(
    () => dispatch({ type: 'RESET_DRAFT' }),
    [dispatch]
  )

  const isUserTurn = picksUntilNext === 0 && currentOverallPick <= config.teams * config.totalRounds
  const isDraftComplete = currentOverallPick > config.teams * config.totalRounds

  return {
    state,
    config,
    picks,
    currentOverallPick,
    currentRound,
    picksUntilNext,
    userPickNumbers,
    draftedIds,
    userRoster,
    isUserTurn,
    isDraftComplete,
    draftPlayer,
    undoLastPick,
    resetDraft,
  }
}
