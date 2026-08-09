import { useQuery } from '@tanstack/react-query'
import type { Ranking, RankingFilters } from '../types'
import { MOCK_RANKINGS } from '../data'

async function fetchRankings(filters: RankingFilters): Promise<Ranking[]> {
  // Simulate async — swap this function body for a real API call later
  await new Promise((r) => setTimeout(r, 0))

  return MOCK_RANKINGS.filter((r) => {
    if (filters.position !== 'ALL' && r.player.position !== filters.position) return false
    if (filters.search) {
      const q = filters.search.toLowerCase()
      if (!r.player.name.toLowerCase().includes(q) &&
          !r.player.team.toLowerCase().includes(q)) return false
    }
    if (filters.tierFilter !== null && r.tier.number !== filters.tierFilter) return false
    return true
  })
}

export function useRankings(filters: RankingFilters) {
  const { data, isLoading } = useQuery({
    queryKey: ['rankings', filters],
    queryFn: () => fetchRankings(filters),
  })
  return { rankings: data ?? [], isLoading }
}
