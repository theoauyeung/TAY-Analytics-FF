import { useQuery } from '@tanstack/react-query'
import type { PlayerDetail } from '../types'
import { fetchPlayer } from '../api/players'

export function usePlayer(id: string | null) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['player', id],
    queryFn: () => fetchPlayer(id!),
    enabled: id !== null,
    staleTime: 60_000,
  })
  return { player: data as PlayerDetail | undefined, isLoading, error }
}
