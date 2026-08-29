import clsx from 'clsx'
import type { WaitScenario } from '../../types'

interface Props {
  scenarios: WaitScenario[]
}

function CostLabel({ cost }: { cost: number }) {
  const colorClass =
    cost > 10 ? 'text-red-400' :
    cost > 5  ? 'text-yellow-400' :
    'text-text-muted'
  const sign = cost >= 0 ? '-' : '+'
  return (
    <span className={clsx('text-sm font-bold font-mono tabular-nums', colorClass)}>
      {sign}{Math.abs(cost).toFixed(1)} VOR
    </span>
  )
}

export function WaitAnalysisPanel({ scenarios }: Props) {
  // Hide panel if every position is the same (nothing to compare)
  const uniquePositions = new Set(scenarios.map(s => s.position))
  if (uniquePositions.size <= 1) return null

  return (
    <div>
      <div className="text-xs font-bold tracking-wide text-text-muted uppercase mb-3">
        What Happens If I Wait?
      </div>
      <div className="space-y-2">
        {scenarios.map(s => (
          <div
            key={s.position}
            className="bg-bg-elevated border border-border rounded-lg p-3"
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-bold text-text-secondary uppercase tracking-wide">
                If you wait on {s.position}
              </span>
              {s.cliffBeforeNextPick && (
                <span className="text-xs font-bold text-red-400 bg-red-900/20 px-1.5 py-0.5 rounded">
                  ⚠ CLIFF
                </span>
              )}
            </div>
            <div className="grid grid-cols-3 gap-2 text-xs">
              <div>
                <div className="text-text-muted mb-0.5">Best now</div>
                <div className="font-semibold text-text-primary truncate">{s.bestNowName}</div>
                <div className="text-text-secondary font-mono">+{s.bestNowVor.toFixed(1)} VOR</div>
              </div>
              <div>
                <div className="text-text-muted mb-0.5">Next pick</div>
                <div className="font-semibold text-text-secondary">~{s.expectedVorAtNextPick.toFixed(1)} expected</div>
                <div className="text-text-muted">
                  {Math.round((1 - s.survivalProbability) * 100)}% chance gone
                </div>
              </div>
              <div className="text-right">
                <div className="text-text-muted mb-0.5">Cost</div>
                <CostLabel cost={s.vorCostOfWaiting} />
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
