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
  const cols = visibleColumns.filter(c => c !== 'rank' && c !== 'player' && c !== 'tier' && c !== 'position' && c !== 'team')

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Spinner size={32} />
      </div>
    )
  }

  return (
    <div className="overflow-auto">
      <table className="w-full text-sm border-collapse">
        <thead className="sticky top-0 z-10 bg-bg-secondary">
          <tr className="border-b-2 border-border">
            <th className="py-2 px-4 text-center text-xs font-condensed font-semibold text-text-muted tracking-wide uppercase w-14">RK</th>
            <th className="py-2 px-3 text-left text-xs font-condensed font-semibold text-text-muted tracking-wide uppercase min-w-[200px] sticky left-0 bg-bg-secondary">Player</th>
            {cols.map(col => (
              <th key={col} className="py-2 px-3 text-right text-xs font-condensed font-semibold text-text-muted tracking-wide uppercase whitespace-nowrap">
                {COLUMN_LABELS[col]}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rankings.map(ranking => (
            <PlayerRow
              key={ranking.player.id}
              ranking={ranking}
              visibleColumns={cols}
              onClick={() => onPlayerClick(ranking.player.id)}
            />
          ))}
        </tbody>
      </table>
    </div>
  )
}
