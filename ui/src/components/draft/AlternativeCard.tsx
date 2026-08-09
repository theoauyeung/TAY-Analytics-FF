import clsx from 'clsx'
import type { RecommendationState } from '../../types'
import { PositionBadge } from '../ui/Badge'

type AlternativeItem = RecommendationState['alternatives'][number]

interface Props {
  alt: AlternativeItem
  rank: number
  isSelected: boolean
  onClick: () => void
}

export function AlternativeCard({ alt, rank, isSelected, onClick }: Props) {
  return (
    <button
      onClick={onClick}
      className={clsx(
        'w-full text-left p-3 rounded-xl border transition-colors',
        isSelected
          ? 'border-accent bg-accent-muted'
          : 'border-border bg-bg-elevated hover:border-accent/50 hover:bg-bg-elevated'
      )}
    >
      <div className="flex items-center gap-2 mb-1">
        <div className="w-6 h-6 rounded-full overflow-hidden bg-bg-card flex-shrink-0">
          {alt.player.imageUrl ? (
            <img
              src={alt.player.imageUrl}
              alt={alt.player.name}
              className="w-full h-full object-cover"
              onError={e => { (e.target as HTMLImageElement).style.display = 'none' }}
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-xs font-bold text-text-muted">
              {alt.player.name.charAt(0)}
            </div>
          )}
        </div>
        <span className="text-sm font-semibold text-text-primary flex-1 truncate">
          {alt.player.name}
        </span>
        <PositionBadge position={alt.player.position} />
      </div>

      <div className="flex items-center gap-3 text-xs text-text-muted">
        <span>
          Draft Score: <span className="text-text-secondary font-medium">{alt.draftScore}</span>
        </span>
        <span>
          VOR: <span className={alt.vor >= 0 ? 'text-green-400' : 'text-red-400'}>
            {alt.vor >= 0 ? '+' : ''}{alt.vor.toFixed(1)}
          </span>
        </span>
        {alt.futureAvailability.probability > 0.55 && (
          <span className="text-yellow-400">
            {Math.round(alt.futureAvailability.probability * 100)}% gone
          </span>
        )}
      </div>
    </button>
  )
}
