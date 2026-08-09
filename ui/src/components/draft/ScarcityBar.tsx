import clsx from 'clsx'
import type { PositionalScarcity } from '../../types'

interface Props {
  scarcity: PositionalScarcity[]
}

const MAX_VIABLE = 18   // baseline for 100% bar width

export function ScarcityBar({ scarcity }: Props) {
  if (scarcity.length === 0) return null

  return (
    <div>
      <div className="text-xs font-bold tracking-widest text-text-muted uppercase mb-3">
        Positional Scarcity
      </div>
      <div className="space-y-2.5">
        {scarcity.map(s => {
          const pctRemaining = Math.min(1, s.viableRemaining / MAX_VIABLE)
          const isLow = s.viableRemaining <= 6
          const isMed = s.viableRemaining > 6 && s.viableRemaining <= 12

          return (
            <div key={s.position}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-medium text-text-secondary">{s.position}</span>
                <span className={clsx(
                  'text-xs font-mono',
                  isLow ? 'text-red-400' : isMed ? 'text-yellow-400' : 'text-text-muted'
                )}>
                  {s.viableRemaining} viable
                </span>
              </div>
              <div className="h-2 bg-bg-elevated rounded-full overflow-hidden">
                <div
                  className={clsx(
                    'h-full rounded-full transition-all',
                    isLow ? 'bg-red-500' : isMed ? 'bg-yellow-500' : 'bg-accent'
                  )}
                  style={{ width: `${Math.round(pctRemaining * 100)}%` }}
                />
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
