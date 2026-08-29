import { PositionBadge } from '../ui/Badge'
import type { Ranking } from '../../types'

interface Props { rankings: Ranking[] }

export function TopValuesCard({ rankings }: Props) {
  return (
    <div className="bg-bg-card border border-border rounded-md p-4">
      <div className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-3">
        Best Values
      </div>
      <div className="space-y-2">
        {rankings.map(r => (
          <div key={r.player.id} className="flex items-center gap-2">
            <span className="text-xs text-text-muted w-5 text-right">{r.rank}</span>
            <PositionBadge position={r.player.position} />
            <span className="text-sm text-text-primary flex-1 truncate">{r.player.name}</span>
            <span className="text-xs text-text-secondary">{r.player.team}</span>
            <span className="text-xs font-medium text-accent tabular-nums">
              {r.adpDelta < 0 ? `+${Math.abs(r.adpDelta)}` : `-${r.adpDelta}`}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
