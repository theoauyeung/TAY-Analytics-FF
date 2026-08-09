import { useMemo } from 'react'
import type { Ranking, ColumnKey } from '../../types'
import { COLUMN_LABELS } from '../../types'
import { PlayerRow } from './PlayerRow'
import { TierSeparator } from './TierSeparator'
import { Spinner } from '../ui/Spinner'

interface Props {
  rankings: Ranking[]
  visibleColumns: ColumnKey[]
  onPlayerClick: (id: string) => void
  isLoading?: boolean
}

export function RankingsTable({ rankings, visibleColumns, onPlayerClick, isLoading }: Props) {
  // Build rows with tier separators injected between tier groups
  const rows = useMemo(() => {
    const result: Array<{ type: 'player'; ranking: Ranking } | { type: 'tier'; tier: Ranking['tier'] }> = []
    let lastTier = 0
    for (const ranking of rankings) {
      if (ranking.tier.number !== lastTier) {
        result.push({ type: 'tier', tier: ranking.tier })
        lastTier = ranking.tier.number
      }
      result.push({ type: 'player', ranking })
    }
    return result
  }, [rankings])


  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Spinner size={32} />
      </div>
    )
  }

  return (
    <div className="overflow-auto rounded-lg border border-border">
      <table className="w-full text-sm border-collapse">
        <thead className="sticky top-0 z-10 bg-bg-secondary border-b border-border">
          <tr>
            <th className="py-2.5 px-3 text-center text-xs font-semibold text-text-muted w-12">RK</th>
            <th className="py-2.5 px-3 text-left text-xs font-semibold text-text-muted min-w-[200px] sticky left-0 bg-bg-secondary">PLAYER</th>
            {visibleColumns.filter((c) => c !== 'rank' && c !== 'player').map((col) => (
              <th key={col} className="py-2.5 px-3 text-right text-xs font-semibold text-text-muted whitespace-nowrap">
                {COLUMN_LABELS[col]}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="bg-bg-card">
          {rows.map((row, i) =>
            row.type === 'tier' ? (
              <TierSeparator key={`tier-${row.tier.number}`} tier={row.tier} />
            ) : (
              <PlayerRow
                key={row.ranking.player.id}
                ranking={row.ranking}
                visibleColumns={visibleColumns}
                onClick={() => onPlayerClick(row.ranking.player.id)}
              />
            )
          )}
        </tbody>
      </table>
    </div>
  )
}
