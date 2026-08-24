import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/layout/Layout'
import Rankings from './pages/Rankings'
import DraftAssistant from './pages/DraftAssistant'
import Players from './pages/Players'
import MockDraft from './pages/MockDraft'
import RosterAnalyzer from './pages/RosterAnalyzer'
import Settings from './pages/Settings'
import { Analytics } from './pages/Analytics'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Navigate to="/rankings" replace />} />
        <Route path="rankings" element={<Rankings />} />
        <Route path="draft" element={<DraftAssistant />} />
        <Route path="players" element={<Players />} />
        <Route path="mock-draft" element={<MockDraft />} />
        <Route path="roster" element={<RosterAnalyzer />} />
        <Route path="analytics" element={<Analytics />} />
        <Route path="settings" element={<Settings />} />
      </Route>
    </Routes>
  )
}
