import clsx from 'clsx'
import { PositionBadge } from '../ui/Badge'
import type { Ranking } from '../../types'

interface Props {
  ranking: Ranking
  selected: boolean
  onClick: () => void
}

export function PlayerListRow({ ranking, selected, onClick }: Props) {
  const { player, rank, projection, vor, adpDelta } = ranking
  return (
    <button
      onClick={onClick}
      className={clsx(
        'w-full flex items-center gap-2 px-3 py-2 text-left transition-colors border-b border-border/50',
        selected
          ? 'bg-accent-muted border-l-2 border-accent'
          : 'hover:bg-bg-elevated'
      )}
    >
      <span className="text-xs text-text-muted w-6 text-right flex-shrink-0">{rank}</span>
      {player.imageUrl && (
        <img
          src={player.imageUrl}
          alt=""
          className="w-7 h-7 rounded-full object-cover flex-shrink-0 bg-bg-elevated"
          onError={e => { (e.target as HTMLImageElement).style.display = 'none' }}
        />
      )}
      <div className="flex-1 min-w-0">
        <div className="text-sm text-text-primary truncate">{player.name}</div>
        <div className="flex items-center gap-1 mt-0.5">
          <PositionBadge position={player.position} />
          <span className="text-xs text-text-muted">{player.team}</span>
        </div>
      </div>
      <div className="text-right flex-shrink-0">
        <div className="text-xs text-text-primary tabular-nums">{projection.toFixed(0)}</div>
        <div className={clsx('text-xs tabular-nums', adpDelta < 0 ? 'text-accent' : adpDelta > 0 ? 'text-red-400' : 'text-text-muted')}>
          VOR {vor.toFixed(0)}
        </div>
      </div>
    </button>
  )
}
