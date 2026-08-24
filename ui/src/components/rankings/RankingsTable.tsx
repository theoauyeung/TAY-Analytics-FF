import type { Ranking, ColumnKey } from '../../types'
import { COLUMN_LABELS } from '../../types'
import { PlayerRow } from './PlayerRow'
import { Spinner } from '../ui/Spinner'

interface Props {
  rankings: Ranking[]
  visibleColumns: ColumnKey[]
  onPlayerClick: (id: string) => void
  isLoading?: boolean
}

export function RankingsTable({ rankings, visibleColumns, onPlayerClick, isLoading }: Props) {
  const cols = visibleColumns.filter(c => c !== 'rank' && c !== 'player' && c !== 'tier')

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
            {cols.map(col => (
              <th key={col} className="py-2.5 px-3 text-right text-xs font-semibold text-text-muted whitespace-nowrap">
                {COLUMN_LABELS[col]}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="bg-bg-card">
          {rankings.map(ranking => (
            <PlayerRow
              key={ranking.player.id}
              ranking={ranking}
              visibleColumns={visibleColumns.filter(c => c !== 'tier')}
              onClick={() => onPlayerClick(ranking.player.id)}
            />
          ))}
        </tbody>
      </table>
    </div>
  )
}
