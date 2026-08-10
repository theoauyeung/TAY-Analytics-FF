import { DraftProvider } from '../state'
import { DraftContextBar } from '../components/draft/DraftContextBar'
import { AvailablePlayers } from '../components/draft/AvailablePlayers'
import { RecommendationPanel } from '../components/draft/RecommendationPanel'
import { MyRoster } from '../components/draft/MyRoster'

function DraftAssistantInner() {
  return (
    <div className="h-screen flex flex-col overflow-hidden">
      <DraftContextBar />
      <div className="flex flex-1 overflow-hidden">
        <AvailablePlayers />
        <RecommendationPanel />
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
