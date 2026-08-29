import { DraftProvider } from '../state'
import { DraftContextBar } from '../components/draft/DraftContextBar'
import { AvailablePlayers } from '../components/draft/AvailablePlayers'
import { RecommendationPanel } from '../components/draft/RecommendationPanel'
import { OpponentPickPanel } from '../components/draft/OpponentPickPanel'
import { DraftSetupScreen } from '../components/draft/DraftSetupScreen'
import { MyRoster } from '../components/draft/MyRoster'
import { useDraftContext } from '../state/draftState'
import { useDraftState } from '../hooks/useDraftState'

function DraftAssistantInner() {
  const { state } = useDraftContext()
  const { isUserTurn } = useDraftState()

  if (state.draftPhase === 'setup') {
    return <DraftSetupScreen />
  }

  const totalPicks = state.config.teams * state.config.totalRounds
  const isDraftComplete = state.currentOverallPick > totalPicks

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      <DraftContextBar />
      <div className="flex flex-1 overflow-hidden">
        <AvailablePlayers />
        {isDraftComplete || isUserTurn
          ? <RecommendationPanel />
          : <OpponentPickPanel />
        }
        <MyRoster />
      </div>
    </div>
  )
}

export default function DraftAssistant() {
  return (
    <DraftProvider>
      <DraftAssistantInner />
    </DraftProvider>
  )
}
