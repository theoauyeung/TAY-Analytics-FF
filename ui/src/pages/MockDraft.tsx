import { useState, useEffect, useRef } from 'react'
import { DraftProvider } from '../state'
import { useDraftState } from '../hooks'
import { useAutoAdvance } from '../state'
import { DraftContextBar, AvailablePlayers, RecommendationPanel } from '../components/draft'
import { DraftBoard, PreDraftConfig } from '../components/mockdraft'

function MockDraftInner() {
  const [started, setStarted] = useState(false)
  const { updateConfig, state, isUserTurn } = useDraftState()
  const { autoAdvancing, startAutoAdvance, stopAutoAdvance } = useAutoAdvance()
  const prevPicksLen = useRef(0)

  const isDraftComplete =
    state.currentOverallPick > state.config.teams * state.config.totalRounds

  // Whenever a pick is added and it's not the user's turn, kick off auto-advance
  useEffect(() => {
    if (!started) return
    const newLen = state.picks.length
    if (newLen > prevPicksLen.current && !isUserTurn && !isDraftComplete) {
      startAutoAdvance()
    }
    prevPicksLen.current = newLen
  }, [state.picks.length, isUserTurn, isDraftComplete, started, startAutoAdvance])

  function handleStart(pickPosition: number) {
    updateConfig({ userPickPosition: pickPosition })
    setStarted(true)
    prevPicksLen.current = 0
    // Kick off auto-advance for picks before user's first turn
    if (pickPosition > 1) {
      startAutoAdvance()
    }
  }

  if (!started) {
    return <PreDraftConfig onStart={handleStart} />
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <DraftContextBar />

      {/* Auto-advance status bar */}
      {!isDraftComplete && (
        <div className="flex items-center gap-3 px-4 py-2 bg-bg-secondary border-b border-border">
          {isUserTurn ? (
            <span className="text-sm text-accent font-medium">
              Your pick
            </span>
          ) : autoAdvancing ? (
            <>
              <span className="text-sm text-text-secondary">Auto-picking opponents…</span>
              <button
                onClick={stopAutoAdvance}
                className="text-xs px-3 py-1 border border-border rounded hover:border-accent text-text-secondary hover:text-text-primary transition-colors"
              >
                Pause
              </button>
            </>
          ) : (
            <button
              onClick={startAutoAdvance}
              className="text-xs px-3 py-1 bg-accent-muted border border-accent/30 text-accent rounded hover:bg-accent hover:text-bg-primary transition-colors"
            >
              Simulate to my turn
            </button>
          )}
        </div>
      )}

      <div className="flex flex-1 overflow-hidden">
        <AvailablePlayers />
        <RecommendationPanel />

        {/* Draft board — right panel */}
        <div className="w-96 border-l border-border bg-bg-secondary overflow-hidden flex flex-col">
          <div className="px-3 py-2 border-b border-border">
            <span className="text-xs font-semibold text-text-secondary uppercase tracking-wider">
              Draft Board
            </span>
          </div>
          <div className="flex-1 overflow-auto p-2">
            <DraftBoard />
          </div>
        </div>
      </div>
    </div>
  )
}

export default function MockDraft() {
  return (
    <DraftProvider>
      <MockDraftInner />
    </DraftProvider>
  )
}
