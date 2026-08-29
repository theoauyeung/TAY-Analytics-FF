import clsx from 'clsx'
import type { NextRoundPositionSummary } from '../../types'

interface Props {
  board: Record<string, NextRoundPositionSummary>
}

const POSITION_ORDER = ['QB', 'RB', 'WR', 'TE']

export function NextRoundBoardPanel({ board }: Props) {
  const positions = POSITION_ORDER.filter(pos => pos in board)
  if (positions.length === 0) return null

  return (
    <div>
      <div className="text-xs font-bold tracking-wide text-text-muted uppercase mb-3">
        Likely Available Next Pick
      </div>
      <div className="grid grid-cols-4 gap-2">
        {positions.map(pos => {
          const summary = board[pos]
          return (
            <div
              key={pos}
              className={clsx(
                'bg-bg-elevated border rounded-lg p-2.5 text-center',
                summary.cliffWarning ? 'border-red-400/30' : 'border-border'
              )}
            >
              <div className="text-xs font-bold text-text-secondary mb-1">{pos}</div>
              <div className={clsx(
                'text-lg font-bold',
                summary.strongOptionsRemaining <= 2 ? 'text-red-400' :
                summary.strongOptionsRemaining <= 4 ? 'text-yellow-400' :
                'text-text-primary'
              )}>
                {summary.strongOptionsRemaining}
              </div>
              <div className="text-xs text-text-muted leading-tight">
                {summary.strongOptionsRemaining === 1 ? 'option' : 'options'}
              </div>
              {summary.cliffWarning && (
                <div className="text-xs text-red-400 mt-1 font-semibold">⚠ cliff</div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
