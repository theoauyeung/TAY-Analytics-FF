import type { PlayerDetail } from '../../types'

interface Config { QB: number; RB: number; WR: number; TE: number; FLEX: number; BENCH: number }
interface Props { roster: PlayerDetail[]; rosterConfig: Config }

const FLEX_ELIGIBLE: PlayerDetail['position'][] = ['RB', 'WR', 'TE']

function fillStarters(roster: PlayerDetail[], config: Config): PlayerDetail[] {
  const pool = [...roster]
  const starters: PlayerDetail[] = []
  const slots: Array<{ pos: PlayerDetail['position'] | 'FLEX'; count: number }> = [
    { pos: 'QB', count: config.QB },
    { pos: 'RB', count: config.RB },
    { pos: 'WR', count: config.WR },
    { pos: 'TE', count: config.TE },
    { pos: 'FLEX', count: config.FLEX },
  ]
  for (const { pos, count } of slots) {
    for (let i = 0; i < count; i++) {
      const idx = pool.findIndex(p =>
        pos === 'FLEX' ? FLEX_ELIGIBLE.includes(p.position) : p.position === pos
      )
      if (idx === -1) break
      starters.push(pool.splice(idx, 1)[0])
    }
  }
  return starters
}

export function RosterProjection({ roster, rosterConfig }: Props) {
  const starters = fillStarters(roster, rosterConfig)

  const mean = starters.reduce((s, p) => s + p.projection.mean, 0)
  const floor = mean * 0.75
  const ceiling = mean * 1.35

  if (starters.length === 0) {
    return (
      <div className="text-sm text-text-muted text-center py-6">
        Add starters to see projections
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-3">
        {[
          { label: 'Floor',   value: floor.toFixed(0),   color: 'text-text-secondary' },
          { label: 'Mean',    value: mean.toFixed(0),    color: 'text-text-primary' },
          { label: 'Ceiling', value: ceiling.toFixed(0), color: 'text-accent' },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-bg-card border border-border rounded-lg p-3 text-center">
            <div className="text-xs text-text-muted mb-1">{label}</div>
            <div className={`text-2xl font-bold tabular-nums ${color}`}>{value}</div>
            <div className="text-xs text-text-muted">pts</div>
          </div>
        ))}
      </div>
      <div className="space-y-1">
        <div className="text-xs font-bold tracking-wide text-text-muted uppercase mb-2">Starters</div>
        {starters.map(p => (
          <div key={p.id} className="flex items-center gap-2 bg-bg-elevated rounded-lg px-3 py-2">
            <span className="text-xs font-mono text-text-muted w-6">{p.position}</span>
            <span className="text-sm text-text-primary flex-1 truncate">{p.name}</span>
            <span className="text-xs text-text-secondary tabular-nums">{p.projection.mean.toFixed(1)} pts</span>
          </div>
        ))}
      </div>
    </div>
  )
}
