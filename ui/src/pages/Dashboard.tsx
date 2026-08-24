import { useQuery } from '@tanstack/react-query'
import { useRankings } from '../hooks/useRankings'
import { fetchScarcity } from '../api/rankings'
import { TopValuesCard, PositionLeadersCard, ScarcityCard } from '../components/dashboard'
import type { Ranking } from '../types'
import { ADP_VALUE_THRESHOLD } from '../lib/thresholds'

const DEFAULT_FILTERS = {
  position: 'ALL' as const,
  search: '',
  format: 'ppr' as const,
  draftType: 'redraft' as const,
  year: 2026,
  tierFilter: null,
}

export default function Dashboard() {
  const { rankings, isLoading } = useRankings(DEFAULT_FILTERS)

  const { data: scarcityRaw } = useQuery({
    queryKey: ['scarcity'],
    queryFn: fetchScarcity,
    staleTime: 60_000,
  })

  const topValues: Ranking[] = rankings
    .filter(r => r.adpDelta <= ADP_VALUE_THRESHOLD)
    .sort((a, b) => a.adpDelta - b.adpDelta)
    .slice(0, 8)

  const positionLeaders: Record<string, Ranking> = Object.fromEntries(
    (['QB', 'RB', 'WR', 'TE'] as const)
      .map(pos => [pos, rankings.find(r => r.player.position === pos)] as [string, Ranking | undefined])
      .filter((entry): entry is [string, Ranking] => entry[1] !== undefined)
  )

  const scarcityOverview: Record<string, number> = Object.fromEntries(
    (scarcityRaw ?? []).map(s => [s.position, s.top_tier_count])
  )

  return (
    <div className="p-6 space-y-6 overflow-y-auto h-full">
      <div>
        <h1 className="text-xl font-bold text-text-primary">Dashboard</h1>
        <p className="text-sm text-text-secondary mt-0.5">2026 Season — Live Data</p>
      </div>

      {isLoading ? (
        <div className="text-sm text-text-muted">Loading…</div>
      ) : (
        <>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <TopValuesCard rankings={topValues} />
            <PositionLeadersCard leaders={positionLeaders} />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <ScarcityCard scarcity={scarcityOverview} />
          </div>
        </>
      )}

      <div className="bg-bg-card border border-border rounded-xl p-4">
        <div className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-2">
          Model Status
        </div>
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-green-400" />
          <span className="text-sm text-text-secondary">Connected to live backend — 2026 neural-v1 model</span>
        </div>
      </div>
    </div>
  )
}
