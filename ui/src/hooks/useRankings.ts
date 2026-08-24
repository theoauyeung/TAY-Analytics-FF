import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import type { RankingFilters } from '../types'
import { fetchRankings } from '../api/rankings'

export function useRankings(filters: RankingFilters) {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['rankings', filters.position, filters.format, filters.year],
    queryFn: () => fetchRankings(filters),
    staleTime: 60_000,
  })

  const rankings = useMemo(() => {
    const all = data ?? []
    return all.filter(r => {
      if (filters.search) {
        const q = filters.search.toLowerCase()
        if (!r.player.name.toLowerCase().includes(q) &&
            !r.player.team.toLowerCase().includes(q)) return false
      }
      if (filters.tierFilter !== null && r.tier.number !== filters.tierFilter) return false
      return true
    })
  }, [data, filters.search, filters.tierFilter])

  return { rankings, isLoading, error, refetch }
}
