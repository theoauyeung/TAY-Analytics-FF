interface Props { scarcity: Record<string, number> }

const POSITIONS = ['QB', 'RB', 'WR', 'TE'] as const
const MAX_VIABLE = 30

function barColor(count: number): string {
  if (count < 6)  return 'bg-red-500'
  if (count <= 12) return 'bg-yellow-500'
  return 'bg-accent'
}

export function ScarcityCard({ scarcity }: Props) {
  return (
    <div className="bg-bg-card border border-border rounded-xl p-4">
      <div className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-3">
        Positional Scarcity
      </div>
      <div className="space-y-3">
        {POSITIONS.map(pos => {
          const count = scarcity[pos] ?? 0
          const width = Math.min(100, Math.round((count / MAX_VIABLE) * 100))
          return (
            <div key={pos}>
              <div className="flex justify-between mb-1">
                <span className="text-xs text-text-secondary">{pos}</span>
                <span className="text-xs text-text-muted">{count} viable</span>
              </div>
              <div className="h-1.5 bg-bg-elevated rounded-full">
                <div
                  className={`h-1.5 rounded-full transition-all ${barColor(count)}`}
                  style={{ width: `${width}%` }}
                />
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
