import { PositionBadge } from '../ui/Badge'
import type { Ranking } from '../../types'

interface Props { leaders: Record<string, Ranking> }

const POSITIONS = ['QB', 'RB', 'WR', 'TE'] as const

export function PositionLeadersCard({ leaders }: Props) {
  return (
    <div className="bg-bg-card border border-border rounded-xl p-4">
      <div className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-3">
        Position Leaders
      </div>
      <div className="space-y-3">
        {POSITIONS.map(pos => {
          const r = leaders[pos]
          if (!r) return null
          return (
            <div key={pos} className="flex items-center gap-2">
              <PositionBadge position={pos} />
              <span className="text-sm text-text-primary flex-1 truncate">{r.player.name}</span>
              <span className="text-xs text-text-secondary tabular-nums">{r.projection.toFixed(0)} pts</span>
              <span className="text-xs text-text-muted tabular-nums">VOR {r.vor.toFixed(0)}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
