import { useQuery } from '@tanstack/react-query'
import type { PlayerDetail } from '../types'
import { MOCK_PLAYERS } from '../data'

async function fetchPlayer(id: string): Promise<PlayerDetail | undefined> {
  await new Promise((r) => setTimeout(r, 0))
  return MOCK_PLAYERS.find((p) => p.id === id)
}

export function usePlayer(id: string | null) {
  const { data, isLoading } = useQuery({
    queryKey: ['player', id],
    queryFn: () => fetchPlayer(id!),
    enabled: id !== null,
  })
  return { player: data, isLoading }
}
