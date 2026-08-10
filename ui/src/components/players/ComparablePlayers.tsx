import { PositionBadge } from '../ui/Badge'
import type { Ranking } from '../../types'

interface Props {
  ranking: Ranking
  allRankings: Ranking[]
}

export function ComparablePlayers({ ranking, allRankings }: Props) {
  const comps = allRankings
    .filter(r =>
      r.player.id !== ranking.player.id &&
      r.player.position === ranking.player.position
    )
    .sort((a, b) => Math.abs(a.vor - ranking.vor) - Math.abs(b.vor - ranking.vor))
    .slice(0, 3)

  if (comps.length === 0) return null

  return (
    <div>
      <div className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-2">
        Comparable Players
      </div>
      <div className="space-y-2">
        {comps.map(r => (
          <div key={r.player.id} className="flex items-center gap-2">
            <PositionBadge position={r.player.position} />
            <span className="text-sm text-text-primary flex-1 truncate">{r.player.name}</span>
            <span className="text-xs text-text-secondary">{r.player.team}</span>
            <span className="text-xs text-text-muted tabular-nums">VOR {r.vor.toFixed(0)}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
