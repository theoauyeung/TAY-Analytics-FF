import { useCallback, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useDraftContext, picksUntilNextTurn } from '../state/draftState'
import { fetchPlayers } from '../api/players'
import { STATIC_UNRANKED_PLAYERS } from '../api/staticPlayers'
import type { PlayerDetail, DraftConfig, DraftedPick } from '../types'

export function useDraftState() {
  const { state, dispatch } = useDraftContext()

  const picksUntil = picksUntilNextTurn(state)
  const isUserTurn = picksUntil === 0

  const userPicks: DraftedPick[] = state.picks.filter(p => p.isUserPick)

  const { data: allPlayers = [] } = useQuery({
    queryKey: ['players'],
    queryFn: () => fetchPlayers(),
    staleTime: 300_000,
  })

  const draftedPlayerIds = new Set(state.picks.map(p => p.player.id))
  const allPlayersWithStatic = useMemo(
    () => [...allPlayers, ...STATIC_UNRANKED_PLAYERS],
    [allPlayers]
  )
  const availablePlayers: PlayerDetail[] = allPlayersWithStatic.filter(p => !draftedPlayerIds.has(p.id))

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
