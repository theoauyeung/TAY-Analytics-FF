import { useState, useCallback } from 'react'
import clsx from 'clsx'
import { useDraftContext } from '../../state/draftState'
import type { DraftConfig } from '../../types'

const TEAM_OPTIONS = [8, 10, 12]
const ROUNDS = 13

export function DraftSetupScreen() {
  const { state, dispatch } = useDraftContext()
  const [teams, setTeams] = useState(state.config.teams)
  const [pickPos, setPickPos] = useState(state.config.userPickPosition)

  // Keep pickPos in range when teams changes
  const handleTeamsChange = useCallback((t: number) => {
    setTeams(t)
    if (pickPos > t) setPickPos(t)
  }, [pickPos])

  function handleStart() {
    const config: DraftConfig = {
      ...state.config,
      teams,
      userPickPosition: pickPos,
      totalRounds: ROUNDS,
    }
    dispatch({ type: 'UPDATE_CONFIG', config })
    dispatch({ type: 'START_DRAFT' })
  }

  return (
    <div className="h-screen flex items-center justify-center bg-bg-primary">
      <div className="w-full max-w-md mx-4 bg-bg-card border border-border rounded-lg p-8 space-y-8">
        {/* Title */}
        <div className="text-center">
          <h1 className="text-2xl font-bold text-text-primary">Draft Setup</h1>
          <p className="text-sm text-text-muted mt-1">Configure your league before the draft starts</p>
        </div>

        {/* Teams */}
        <div className="space-y-3">
          <label className="text-xs font-bold tracking-wide text-text-muted uppercase">
            League Size
          </label>
          <div className="flex gap-2">
            {TEAM_OPTIONS.map(t => (
              <button
                key={t}
                onClick={() => handleTeamsChange(t)}
                className={clsx(
                  'flex-1 py-2.5 rounded-md text-sm font-bold border transition-colors',
                  teams === t
                    ? 'bg-accent text-bg-primary border-accent'
                    : 'bg-bg-elevated text-text-secondary border-border hover:border-accent hover:text-text-primary'
                )}
              >
                {t} Teams
              </button>
            ))}
          </div>
        </div>

        {/* Pick position grid */}
        <div className="space-y-3">
          <label className="text-xs font-bold tracking-wide text-text-muted uppercase">
            Your Draft Position
          </label>
          <div className="grid grid-cols-6 gap-2">
            {Array.from({ length: teams }, (_, i) => i + 1).map(pos => (
              <button
                key={pos}
                onClick={() => setPickPos(pos)}
                className={clsx(
                  'py-2.5 rounded-md text-sm font-bold border transition-colors',
                  pickPos === pos
                    ? 'bg-accent text-bg-primary border-accent'
                    : 'bg-bg-elevated text-text-secondary border-border hover:border-accent hover:text-text-primary'
                )}
              >
                {pos}
              </button>
            ))}
          </div>
          <p className="text-xs text-text-muted text-center">
            Pick {pickPos} of {teams} · Snake draft · {ROUNDS} rounds
          </p>
        </div>

        {/* Start button */}
        <button
          onClick={handleStart}
          className="w-full py-3.5 bg-accent text-bg-primary text-sm font-bold rounded-md hover:opacity-90 transition-opacity"
        >
          Start Draft
        </button>
      </div>
    </div>
  )
}
