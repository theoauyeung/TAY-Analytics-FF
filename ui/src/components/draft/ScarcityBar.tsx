import clsx from 'clsx'
import type { WaitScenario } from '../../types'

interface Props {
  waitAnalysis: WaitScenario[]
}

export function ScarcityBar({ waitAnalysis }: Props) {
  if (waitAnalysis.length === 0) return null

  const maxCost = Math.max(...waitAnalysis.map(s => s.vorCostOfWaiting), 1)

  return (
    <div>
      <div className="text-xs font-bold tracking-wide text-text-muted uppercase mb-3">
        Positional Scarcity
      </div>
      <div className="space-y-2.5">
        {waitAnalysis.map(s => {
          const pct = Math.min(1, Math.max(0, s.vorCostOfWaiting / maxCost))
          const isHigh = s.vorCostOfWaiting > 10
          const isMed = s.vorCostOfWaiting > 5 && s.vorCostOfWaiting <= 10

          return (
            <div key={s.position}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-medium text-text-secondary">{s.position}</span>
                <span className={clsx(
                  'text-xs font-mono',
                  isHigh ? 'text-red-400' : isMed ? 'text-yellow-400' : 'text-text-muted'
                )}>
                  -{s.vorCostOfWaiting.toFixed(1)} VOR cost
                </span>
              </div>
              <div className="h-2 bg-bg-elevated rounded-full overflow-hidden">
                <div
                  className={clsx(
                    'h-full rounded-full transition-all',
                    isHigh ? 'bg-red-500' : isMed ? 'bg-yellow-500' : 'bg-accent'
                  )}
                  style={{ width: `${Math.round(pct * 100)}%` }}
                />
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
