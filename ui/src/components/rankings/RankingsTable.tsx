import type { Ranking, ColumnKey } from '../../types'
import { COLUMN_LABELS } from '../../types'
import { PlayerRow } from './PlayerRow'
import { Spinner } from '../ui/Spinner'

interface Props {
  rankings: Ranking[]
  visibleColumns: ColumnKey[]
  isLoading?: boolean
}

const COLUMN_GROUPS: { label: string; cols: ColumnKey[] }[] = [
  { label: 'PROJECTION', cols: ['projection', 'floor', 'ceiling'] },
  { label: 'VALUE',      cols: ['vor', 'modelRank'] },
  { label: 'MARKET',     cols: ['adp', 'adpDelta'] },
  { label: 'USAGE',      cols: ['targetShare', 'rushShare', 'snapPct', 'routePct', 'redZoneUsage'] },
  { label: 'SCORING',    cols: ['tdProjection', 'gamesPlayed', 'bye'] },
]

const GROUPED_COLS = new Set(COLUMN_GROUPS.flatMap(g => g.cols))

export function RankingsTable({ rankings, visibleColumns, isLoading }: Props) {
  const cols = visibleColumns.filter(c => c !== 'rank' && c !== 'player' && c !== 'tier' && c !== 'position' && c !== 'team')

  const activeGroups = COLUMN_GROUPS
    .map(g => ({ ...g, span: g.cols.filter(c => cols.includes(c)).length }))
    .filter(g => g.span > 0)

  const extraCols = cols.filter(c => !GROUPED_COLS.has(c))

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

          {/* Group label row */}
          <tr>
            <th className="pt-2 pb-0 px-4 w-14" />
            <th className="pt-2 pb-0 px-3 text-left min-w-[200px] sticky left-0 bg-bg-secondary" />
            {activeGroups.map(g => (
              <th
                key={g.label}
                colSpan={g.span}
                className="pt-2 pb-0 px-3 text-center"
              >
                <span className="text-[9px] font-condensed font-semibold tracking-[0.15em] text-text-muted/50 uppercase">
                  {g.label}
                </span>
              </th>
            ))}
            {extraCols.map(col => <th key={col} className="pt-2 pb-0 px-3" />)}
          </tr>

          {/* Column name row */}
          <tr className="border-b-2 border-border">
            <th className="py-1.5 px-4 text-center text-[10px] font-condensed font-semibold text-text-muted tracking-widest uppercase w-14">
              RK
            </th>
            <th className="py-1.5 px-3 text-left text-[10px] font-condensed font-semibold text-text-muted tracking-widest uppercase min-w-[200px] sticky left-0 bg-bg-secondary">
              Player
            </th>
            {cols.map(col => (
              <th key={col} className="py-1.5 px-3 text-right text-[10px] font-condensed font-semibold text-text-muted tracking-widest uppercase whitespace-nowrap">
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
            />
          ))}
        </tbody>
      </table>
    </div>
  )
}
