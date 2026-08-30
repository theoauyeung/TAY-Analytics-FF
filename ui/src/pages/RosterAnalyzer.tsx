import { useState } from 'react'
import type { PlayerDetail } from '../types'
import { RosterBuilder, RosterProjection, PositionStrengthBars } from '../components/roster'
import { useLeagueSettings } from '../hooks'

const POSITIONS = ['QB', 'RB', 'WR', 'TE'] as const

export default function RosterAnalyzer() {
  const [roster, setRoster] = useState<PlayerDetail[]>([])
  const { settings } = useLeagueSettings()
  const config = settings.rosterConfig

  function addPlayer(p: PlayerDetail) {
    setRoster(prev => prev.find(x => x.id === p.id) ? prev : [...prev, p])
  }

  function removePlayer(id: string) {
    setRoster(prev => prev.filter(p => p.id !== id))
  }

  // Primary need: first position where drafted count < required starters
  const primaryNeed = POSITIONS.find(pos => {
    const count = roster.filter(p => p.position === pos).length
    return count < config[pos]
  }) ?? null

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      <div className="border-b-2 border-border px-6 pt-5 pb-4 bg-bg-secondary flex-shrink-0">
        <h1 className="text-4xl font-condensed font-bold tracking-tight text-text-primary uppercase leading-none">
          Roster Analyzer
        </h1>
        <p className="text-[11px] font-condensed tracking-[0.12em] text-text-muted uppercase mt-1.5">
          {settings.teams}-team · {settings.format.toUpperCase()} · 2026 Season
        </p>
      </div>
      <div className="flex flex-1 overflow-hidden">
      {/* Left: roster builder */}
      <div className="w-80 flex-shrink-0 flex flex-col border-r border-border bg-bg-secondary overflow-hidden p-4 gap-4">
        <div>
          <h2 className="text-sm font-semibold text-text-primary mb-0.5">Build Your Roster</h2>
          <p className="text-xs text-text-secondary">
            {roster.length} players · {settings.teams}-team {settings.format.toUpperCase()}
          </p>
        </div>
        <RosterBuilder roster={roster} onAdd={addPlayer} onRemove={removePlayer} />
      </div>

      {/* Right: analysis */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        <div>
          <h1 className="text-xl font-bold text-text-primary">Roster Analysis</h1>
          <p className="text-sm text-text-secondary mt-0.5">
            Starter projections based on your league settings
          </p>
        </div>

        {/* Projected totals */}
        <section>
          <h2 className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-3">
            Starter Projections
          </h2>
          <RosterProjection roster={roster} rosterConfig={config} />
        </section>

        {/* Position strength */}
        <section>
          <h2 className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-3">
            Positional Strength
          </h2>
          <div className="bg-bg-card border border-border rounded-md p-4">
            <PositionStrengthBars roster={roster} rosterConfig={config} />
          </div>
        </section>

        {/* Primary need */}
        {primaryNeed && (
          <section>
            <h2 className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-3">
              Primary Need
            </h2>
            <div className="bg-bg-card border border-accent/30 rounded-md p-4">
              <div className="text-sm text-text-primary">
                You need more <span className="font-semibold text-accent">{primaryNeed}</span>. Starter slot unfilled.
              </div>
            </div>
          </section>
        )}

        {roster.length === 0 && (
          <div className="text-center text-text-muted text-sm pt-8">
            Add players from the left panel to begin analysis
          </div>
        )}
      </div>
      </div>
    </div>
  )
}
