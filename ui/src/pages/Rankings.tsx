import { useState } from 'react'
import { RankingsControls } from '../components/rankings/RankingsControls'
import { ColumnToggle } from '../components/rankings/ColumnToggle'
import { RankingsTable } from '../components/rankings/RankingsTable'
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

  const { rankings, isLoading } = useRankings(filters)

  function updateFilters(partial: Partial<RankingFilters>) {
    setFilters((f) => ({ ...f, ...partial }))
  }

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      {/* Page header */}
      <div className="border-b border-border px-6 pt-5 pb-3 bg-bg-secondary flex-shrink-0">
        <div className="flex items-start justify-between mb-4">
          <div>
            <h1 className="text-2xl font-bold text-text-primary">Rankings</h1>
            <p className="text-xs text-text-muted mt-0.5 font-condensed tracking-wide">PPR · 2026 Projections</p>
          </div>
          <ColumnToggle visibleColumns={visibleColumns} onChange={setVisibleColumns} />
        </div>
        <RankingsControls filters={filters} onChange={updateFilters} />
      </div>

      {/* Table */}
      <div className="flex-1 overflow-hidden px-0 py-0">
        <div className="h-full overflow-auto">
          <RankingsTable
            rankings={rankings}
            visibleColumns={visibleColumns}
            isLoading={isLoading}
          />
        </div>
      </div>
    </div>
  )
}
