import clsx from 'clsx'
import { useLeagueSettings } from '../hooks'
import type { ScoringFormat } from '../types'

const FORMATS: Array<{ value: ScoringFormat; label: string }> = [
  { value: 'ppr',      label: 'PPR' },
]

const TEAM_COUNTS = [8, 10, 12, 14, 16]

const ROSTER_SLOTS = [
  { key: 'QB',   label: 'QB' },
  { key: 'RB',   label: 'RB' },
  { key: 'WR',   label: 'WR' },
  { key: 'TE',   label: 'TE' },
  { key: 'FLEX', label: 'FLEX' },
  { key: 'BENCH', label: 'Bench' },
] as const

export default function Settings() {
  const { settings, update, reset } = useLeagueSettings()

  return (
    <div className="p-6 max-w-2xl space-y-8 overflow-y-auto h-full">
      <div>
        <h1 className="text-xl font-bold text-text-primary">Settings</h1>
        <p className="text-sm text-text-secondary mt-0.5">League configuration — saved automatically</p>
      </div>

      {/* Scoring Format */}
      <section>
        <h2 className="text-sm font-semibold text-text-primary mb-3">Scoring Format</h2>
        <div className="flex rounded-lg overflow-hidden border border-border bg-bg-secondary w-fit">
          {FORMATS.map(f => (
            <button
              key={f.value}
              onClick={() => update({ format: f.value })}
              className={clsx(
                'px-4 py-2 text-sm font-medium transition-colors',
                settings.format === f.value
                  ? 'bg-accent text-bg-primary'
                  : 'text-text-secondary hover:text-text-primary hover:bg-bg-elevated'
              )}
            >
              {f.label}
            </button>
          ))}
        </div>
      </section>

      {/* League Size */}
      <section>
        <h2 className="text-sm font-semibold text-text-primary mb-3">League Size</h2>
        <div className="flex rounded-lg overflow-hidden border border-border bg-bg-secondary w-fit">
          {TEAM_COUNTS.map(n => (
            <button
              key={n}
              onClick={() => update({ teams: n })}
              className={clsx(
                'px-4 py-2 text-sm font-medium transition-colors',
                settings.teams === n
                  ? 'bg-accent text-bg-primary'
                  : 'text-text-secondary hover:text-text-primary hover:bg-bg-elevated'
              )}
            >
              {n}
            </button>
          ))}
        </div>
      </section>

      {/* Roster Configuration */}
      <section>
        <h2 className="text-sm font-semibold text-text-primary mb-3">Roster Slots</h2>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          {ROSTER_SLOTS.map(({ key, label }) => (
            <div key={key} className="bg-bg-card border border-border rounded-lg p-3">
              <label className="text-xs text-text-secondary block mb-1">{label}</label>
              <input
                type="number"
                min={0}
                max={key === 'BENCH' ? 12 : 4}
                value={settings.rosterConfig[key]}
                onChange={e => update({
                  rosterConfig: {
                    ...settings.rosterConfig,
                    [key]: Math.max(0, parseInt(e.target.value) || 0),
                  }
                })}
                className="w-full bg-bg-elevated border border-border rounded px-2 py-1 text-sm text-text-primary focus:outline-none focus:border-accent"
              />
            </div>
          ))}
        </div>
      </section>

      {/* Reset */}
      <section className="border-t border-border pt-6">
        <button
          onClick={reset}
          className="px-4 py-2 text-sm text-text-secondary border border-border rounded-lg hover:text-text-primary hover:border-accent transition-colors"
        >
          Reset to Defaults
        </button>
      </section>
    </div>
  )
}
