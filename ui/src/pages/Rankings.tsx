import { useState } from 'react'
import { RankingsControls } from '../components/rankings/RankingsControls'
import { ColumnToggle } from '../components/rankings/ColumnToggle'
import { RankingsTable } from '../components/rankings/RankingsTable'
import { PlayerDrawer } from '../components/rankings/PlayerDrawer'
import { useRankings } from '../hooks/useRankings'
import type { RankingFilters, ColumnKey } from '../types'
import { CORE_COLUMNS } from '../types'

const DEFAULT_FILTERS: RankingFilters = {
  format: 'ppr',
  draftType: 'redraft',
  position: 'ALL',
  search: '',
  year: 2026,
  tierFilter: null,
}

const DEFAULT_VISIBLE: ColumnKey[] = [
  ...CORE_COLUMNS,
  'floor', 'ceiling', 'adpDelta',
]

export default function Rankings() {
  const [filters, setFilters] = useState<RankingFilters>(DEFAULT_FILTERS)
  const [visibleColumns, setVisibleColumns] = useState<ColumnKey[]>(DEFAULT_VISIBLE)
  const [selectedPlayerId, setSelectedPlayerId] = useState<string | null>(null)

  const { rankings, isLoading } = useRankings(filters)

  function updateFilters(partial: Partial<RankingFilters>) {
    setFilters((f) => ({ ...f, ...partial }))
  }

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      {/* Page header */}
      <div className="border-b border-border px-6 py-4 bg-bg-secondary flex-shrink-0">
        <div className="flex items-start justify-between mb-3">
          <div>
            <h1 className="text-2xl font-bold text-text-primary">Fantasy Rankings</h1>
            <div className="flex items-center gap-3 mt-1 text-xs text-text-muted">
              <span>{filters.format.replace('_', '-').toUpperCase()}</span>
              <span>·</span>
              <span>12 Teams</span>
              <span>·</span>
              <span>2026 Projections</span>
              <span>·</span>
              <span className="text-text-secondary">Last updated: mock data</span>
            </div>
          </div>
          <ColumnToggle visibleColumns={visibleColumns} onChange={setVisibleColumns} />
        </div>
        <RankingsControls filters={filters} onChange={updateFilters} />
      </div>

      {/* Table — takes remaining height with internal scroll */}
      <div className="flex-1 overflow-hidden px-6 py-4">
        <div className="h-full overflow-auto">
          <RankingsTable
            rankings={rankings}
            visibleColumns={visibleColumns}
            onPlayerClick={setSelectedPlayerId}
            isLoading={isLoading}
          />
        </div>
      </div>

      {/* Player drawer */}
      <PlayerDrawer
        playerId={selectedPlayerId}
        onClose={() => setSelectedPlayerId(null)}
      />
    </div>
  )
}
