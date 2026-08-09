import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/layout/Layout'
import Rankings from './pages/Rankings'
import DraftAssistant from './pages/DraftAssistant'
import Dashboard from './pages/Dashboard'
import Players from './pages/Players'
import MockDraft from './pages/MockDraft'
import RosterAnalyzer from './pages/RosterAnalyzer'
import Settings from './pages/Settings'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="rankings" element={<Rankings />} />
        <Route path="draft" element={<DraftAssistant />} />
        <Route path="players" element={<Players />} />
        <Route path="mock-draft" element={<MockDraft />} />
        <Route path="roster" element={<RosterAnalyzer />} />
        <Route path="settings" element={<Settings />} />
      </Route>
    </Routes>
  )
}
