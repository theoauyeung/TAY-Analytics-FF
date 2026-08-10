import { TrendingUp, TrendingDown } from 'lucide-react'
import { PositionBadge } from '../ui/Badge'
import type { Ranking } from '../../types'

interface Props {
  rising: Ranking[]
  falling: Ranking[]
}

export function ModelMoversCard({ rising, falling }: Props) {
  return (
    <div className="bg-bg-card border border-border rounded-xl p-4">
      <div className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-3">
        Model vs Market
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <div className="flex items-center gap-1 text-xs text-green-400 mb-2">
            <TrendingUp size={12} /> Rising
          </div>
          <div className="space-y-2">
            {rising.map(r => (
              <div key={r.player.id} className="flex items-center gap-1.5">
                <PositionBadge position={r.player.position} />
                <span className="text-xs text-text-primary truncate flex-1">{r.player.name}</span>
                <span className="text-xs text-green-400 tabular-nums">
                  +{Math.abs(r.adpDelta)}
                </span>
              </div>
            ))}
          </div>
        </div>
        <div>
          <div className="flex items-center gap-1 text-xs text-red-400 mb-2">
            <TrendingDown size={12} /> Falling
          </div>
          <div className="space-y-2">
            {falling.map(r => (
              <div key={r.player.id} className="flex items-center gap-1.5">
                <PositionBadge position={r.player.position} />
                <span className="text-xs text-text-primary truncate flex-1">{r.player.name}</span>
                <span className="text-xs text-red-400 tabular-nums">
                  -{r.adpDelta}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
