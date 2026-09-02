import clsx from 'clsx'
import { useDraftState } from '../../hooks/useDraftState'
import { PositionBadge } from '../ui/Badge'

export function PickHistoryBoard() {
  const { state } = useDraftState()
  const { picks } = state

  if (picks.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center text-xs text-text-muted italic px-4 text-center">
        No picks yet — picks will appear here as the draft progresses.
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto px-3 py-2 space-y-0.5">
      {picks.map((pick) => {
        const roundLabel = `${pick.round}.${String(pick.pickInRound).padStart(2, '0')}`
        return (
          <div
            key={pick.overallPick}
            className={clsx(
              'flex items-center gap-2 px-2.5 py-1.5 rounded-lg',
              pick.isUserPick
                ? 'bg-accent/10 border border-accent/20'
                : 'bg-bg-elevated'
            )}
          >
            {/* Overall pick number */}
            <span className="text-xs font-mono text-text-muted w-6 flex-shrink-0 text-right">
              {pick.overallPick}
            </span>

            {/* Round.Pick */}
            <span className={clsx(
              'text-xs font-mono w-9 flex-shrink-0',
              pick.isUserPick ? 'text-accent font-bold' : 'text-text-muted'
            )}>
              {roundLabel}
            </span>

            {/* Position badge */}
            <PositionBadge position={pick.player.position} />

            {/* Player info */}
            <div className="flex-1 min-w-0">
              <div className={clsx(
                'text-xs truncate',
                pick.isUserPick ? 'font-semibold text-text-primary' : 'text-text-secondary'
              )}>
                {pick.player.name}
              </div>
            </div>

            {/* Team number */}
            <span className={clsx(
              'text-xs font-mono flex-shrink-0 w-8 text-right',
              pick.isUserPick ? 'text-accent font-bold' : 'text-text-muted'
            )}>
              {pick.isUserPick ? 'YOU' : `T${pick.teamNumber}`}
            </span>
          </div>
        )
      })}
    </div>
  )
}
