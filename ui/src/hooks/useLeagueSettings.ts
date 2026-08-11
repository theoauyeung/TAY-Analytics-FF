import { useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import type { LeagueSettings } from '../types'
import { DEFAULT_LEAGUE_SETTINGS } from '../types'
import { fetchLeagueSettings, saveLeagueSettings } from '../api/league'

export function useLeagueSettings() {
  const queryClient = useQueryClient()

  const { data: settings = DEFAULT_LEAGUE_SETTINGS, isLoading } = useQuery({
    queryKey: ['leagueSettings'],
    queryFn: fetchLeagueSettings,
    staleTime: 300_000,
  })

  const { mutate: saveMutation, isPending: isSaving } = useMutation({
    mutationFn: saveLeagueSettings,
    onSuccess: (_data, variables) => {
      queryClient.setQueryData(['leagueSettings'], variables)
    },
  })

  const update = useCallback((patch: Partial<LeagueSettings>) => {
    const next = { ...settings, ...patch }
    saveMutation(next)
  }, [settings, saveMutation])

  const reset = useCallback(() => {
    saveMutation(DEFAULT_LEAGUE_SETTINGS)
  }, [saveMutation])

  return { settings, update, reset, isLoading, isSaving }
}
