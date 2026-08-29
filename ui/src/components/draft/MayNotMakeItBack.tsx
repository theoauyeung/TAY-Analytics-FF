import { AlertCircle } from 'lucide-react'
import clsx from 'clsx'
import type { FutureAvailability, Ranking } from '../../types'
import { PositionBadge } from '../ui/Badge'

interface Props {
  items: FutureAvailability[]
  allRankings: Ranking[]
}

export function MayNotMakeItBack({ items, allRankings }: Props) {
  if (items.length === 0) return null

  const withPlayers = items
    .map(item => ({
      item,
      ranking: allRankings.find(r => r.player.id === item.playerId),
    }))
    .filter((x): x is { item: FutureAvailability; ranking: Ranking } => x.ranking !== undefined)

  if (withPlayers.length === 0) return null

  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <AlertCircle size={13} className="text-yellow-400" />
        <span className="text-xs font-bold tracking-wide text-yellow-400 uppercase">
          May Not Make It Back
        </span>
      </div>
      <div className="space-y-1.5">
        {withPlayers.map(({ item, ranking }) => (
          <div
            key={item.playerId}
            className="flex items-center gap-2.5 px-3 py-2 bg-yellow-900/10 border border-yellow-400/20 rounded-lg"
          >
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold text-text-primary truncate">
                  {ranking.player.name}
                </span>
                <PositionBadge position={ranking.player.position} />
              </div>
              <div className="text-xs text-text-muted">{ranking.player.team}</div>
            </div>
            <div className="text-right flex-shrink-0">
              <div className={clsx(
                'text-sm font-bold',
                item.probability > 0.80 ? 'text-red-400' : 'text-yellow-400'
              )}>
                {Math.round(item.probability * 100)}%
              </div>
              <div className="text-xs text-text-muted">gone</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
