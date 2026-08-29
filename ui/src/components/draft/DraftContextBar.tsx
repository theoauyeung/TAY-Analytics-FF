import { RotateCcw, Undo2, Users } from 'lucide-react'
import clsx from 'clsx'
import { useDraftState } from '../../hooks/useDraftState'

export function DraftContextBar() {
  const { state, undoLastPick, resetDraft, isUserTurn, picksUntil, availablePlayers } = useDraftState()

  const { currentOverallPick, config, picks } = state
  const { teams, totalRounds } = config

  // Calculate current round from overall pick
  const currentRound = Math.ceil(currentOverallPick / teams)

  const totalPicks = teams * totalRounds
  const draftedCount = picks.length
  const remainingCount = availablePlayers.length
  const isDraftComplete = currentOverallPick > totalPicks

  return (
    <div className="h-14 flex-shrink-0 bg-bg-secondary border-b border-border flex items-center px-4 gap-6">
      {/* Round / Pick */}
      <div className="flex items-center gap-3">
        <div className="text-center">
          <div className="text-xs text-text-muted uppercase tracking-wide leading-tight">Round</div>
          <div className="text-lg font-bold text-text-primary leading-tight">{currentRound}</div>
        </div>
        <div className="w-px h-8 bg-border" />
        <div className="text-center">
          <div className="text-xs text-text-muted uppercase tracking-wide leading-tight">Pick</div>
          <div className="text-lg font-bold text-text-primary leading-tight">
            {Math.min(currentOverallPick, totalPicks)}
          </div>
        </div>
      </div>

      <div className="w-px h-8 bg-border" />

      {/* User turn indicator */}
      <div className={clsx(
        'px-3 py-1.5 rounded-lg text-xs font-bold tracking-wide',
        isDraftComplete
          ? 'bg-border text-text-muted'
          : isUserTurn
            ? 'bg-accent text-bg-primary'
            : 'bg-bg-elevated text-text-secondary'
      )}>
        {isDraftComplete
          ? 'DRAFT COMPLETE'
          : isUserTurn
            ? 'YOUR PICK NOW'
            : `YOUR PICK IN ${picksUntil}`
        }
      </div>

      {/* Players remaining */}
      <div className="flex items-center gap-2 text-text-secondary ml-auto">
        <Users size={14} />
        <span className="text-sm">{remainingCount} remaining</span>
        <span className="text-text-muted">·</span>
        <span className="text-sm text-text-muted">{draftedCount}/{totalPicks} picked</span>
      </div>

      {/* Controls */}
      <div className="flex items-center gap-2">
        <button
          onClick={undoLastPick}
          disabled={picks.length === 0}
          className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs text-text-secondary border border-border rounded-lg hover:text-text-primary hover:border-accent transition-colors disabled:opacity-40 disabled:pointer-events-none"
        >
          <Undo2 size={13} />
          Undo
        </button>
        <button
          onClick={resetDraft}
          className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs text-text-secondary border border-border rounded-lg hover:text-red-400 hover:border-red-400 transition-colors"
        >
          <RotateCcw size={13} />
          Reset
        </button>
      </div>
    </div>
  )
}
