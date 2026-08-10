import { TopValuesCard, PositionLeadersCard, ScarcityCard, ModelMoversCard } from '../components/dashboard'
import { TOP_VALUES, POSITION_LEADERS, SCARCITY_OVERVIEW, MODEL_MOVERS } from '../data'

export default function Dashboard() {
  return (
    <div className="p-6 space-y-6 overflow-y-auto h-full">
      <div>
        <h1 className="text-xl font-bold text-text-primary">Dashboard</h1>
        <p className="text-sm text-text-secondary mt-0.5">2026 Season — Mock Data</p>
      </div>

      {/* Top row: values + movers */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <TopValuesCard rankings={TOP_VALUES} />
        <ModelMoversCard rising={MODEL_MOVERS.rising} falling={MODEL_MOVERS.falling} />
      </div>

      {/* Bottom row: leaders + scarcity */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <PositionLeadersCard leaders={POSITION_LEADERS} />
        <ScarcityCard scarcity={SCARCITY_OVERVIEW} />
      </div>

      {/* Model status placeholder */}
      <div className="bg-bg-card border border-border rounded-xl p-4">
        <div className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-2">
          Model Status
        </div>
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-yellow-400" />
          <span className="text-sm text-text-secondary">Running on mock data — backend not connected</span>
        </div>
      </div>
    </div>
  )
}
