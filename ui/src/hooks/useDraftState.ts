import { useCallback } from 'react'
import { useDraftContext, picksUntilNextTurn } from '../state/draftState'
import { MOCK_PLAYERS } from '../data'
import type { PlayerDetail, DraftConfig, DraftedPick, LiveDraftState } from '../types'

export function useDraftState() {
  const { state, dispatch } = useDraftContext()

  const picksUntil = picksUntilNextTurn(state)
  const isUserTurn = picksUntil === 0

  const userPicks: DraftedPick[] = state.picks.filter(p => p.isUserPick)

  const draftedPlayerIds = new Set(state.picks.map(p => p.player.id))
  const availablePlayers: PlayerDetail[] = MOCK_PLAYERS.filter(
    p => !draftedPlayerIds.has(p.id)
  )

  const draftPlayer = useCallback(
    (player: PlayerDetail, isUserPick?: boolean) =>
      dispatch({ type: 'DRAFT_PLAYER', payload: player, ...(isUserPick !== undefined && { isUserPick }) }),
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

  const updateConfig = useCallback(
    (config: Partial<DraftConfig>) => {
      dispatch({ type: 'UPDATE_CONFIG', config: { ...state.config, ...config } })
    },
    [dispatch, state.config]
  )

  return {
    state,
    draftPlayer,
    undoLastPick,
    resetDraft,
    updateConfig,
    isUserTurn,
    picksUntil,
    availablePlayers,
    userPicks,
  }
}
