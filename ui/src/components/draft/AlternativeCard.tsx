import clsx from 'clsx'
import type { ScoredPlayer } from '../../types'
import { PositionBadge } from '../ui/Badge'

interface Props {
  player: ScoredPlayer
  onDraftMe?: () => void
  // optional extras
  isSelected?: boolean
  onClick?: () => void
}

export function AlternativeCard({ player, onDraftMe, isSelected, onClick }: Props) {
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') onClick?.() }}
      className={clsx(
        'w-full text-left p-3 rounded-xl border transition-colors',
        isSelected
          ? 'border-accent bg-accent-muted'
          : 'border-border bg-bg-elevated hover:border-accent/50 hover:bg-bg-elevated'
      )}
    >
      <div className="flex items-center gap-2 mb-1">
        <div className="w-6 h-6 rounded-full overflow-hidden bg-bg-card flex-shrink-0">
          {player.player.imageUrl ? (
            <img
              src={player.player.imageUrl}
              alt={player.player.name}
              className="w-full h-full object-cover"
              onError={e => { (e.target as HTMLImageElement).style.display = 'none' }}
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-xs font-bold text-text-muted">
              {player.player.name.charAt(0)}
            </div>
          )}
        </div>
        <span className="text-sm font-semibold text-text-primary flex-1 truncate">
          {player.player.name}
        </span>
        <PositionBadge position={player.player.position} />
      </div>

      <div className="h-1 bg-bg-elevated rounded-full mt-1">
        <div
          className="h-1 bg-accent rounded-full"
          style={{ width: `${Math.round(player.score * 100)}%` }}
        />
      </div>

      {onDraftMe && (
        <button
          onClick={e => { e.stopPropagation(); onDraftMe() }}
          className="mt-2 w-full py-1 bg-accent text-bg-primary text-xs font-bold rounded-lg hover:bg-accent-dim transition-colors"
        >
          Draft {player.player.name}
        </button>
      )}
    </div>
  )
}
