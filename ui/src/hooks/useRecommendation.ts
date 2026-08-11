import { useRef, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import type { RecommendationState } from '../types'
import { useDraftState } from './useDraftState'
import { picksUntilNextTurn } from '../state/draftState'
import { fetchRecommendation, saveSession } from '../api/draft'

export interface UseRecommendationResult {
  recommendation: RecommendationState | null
  error: Error | null
}

export function useRecommendation(): UseRecommendationResult {
  const { state } = useDraftState()
  const isUserTurn = picksUntilNextTurn(state) === 0
  const sessionIdRef = useRef<string | null>(null)

  useEffect(() => {
    const stored = sessionStorage.getItem('tay-draft-session-id')
    if (stored) {
      sessionIdRef.current = stored
    } else {
      const id = crypto.randomUUID()
      sessionStorage.setItem('tay-draft-session-id', id)
      sessionIdRef.current = id
    }
  }, [])

  // Fire-and-forget session save after each pick
  useEffect(() => {
    const sid = sessionIdRef.current
    if (!sid || state.picks.length === 0) return
    saveSession(sid, state).catch(() => { /* ignore */ })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.picks.length])

  const totalPicks = state.config.teams * state.config.totalRounds
  const draftStarted = state.picks.length > 0 || state.currentOverallPick > 1
  const isDraftComplete = state.currentOverallPick > totalPicks

  const { data, error } = useQuery({
    queryKey: ['recommendation', state.currentOverallPick, state.picks.length],
    queryFn: () => fetchRecommendation(state),
    enabled: isUserTurn && draftStarted && !isDraftComplete,
    staleTime: 0,
    retry: false,
  })

  return { recommendation: data ?? null, error: error as Error | null }
}
