import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
} from 'recharts'
import type { PlayerDetail } from '../../types'

interface Props { player: PlayerDetail }

const PERCENTILE_COLORS = ['#556070', '#3A7FBF', '#60B4FF', '#3A7FBF', '#556070']

export function ProjectionChart({ player }: Props) {
  const { p10, p25, median, p75, p90 } = player.projection
  const data = [
    { label: 'p10',    value: Math.round(p10) },
    { label: 'p25',    value: Math.round(p25) },
    { label: 'Median', value: Math.round(median) },
    { label: 'p75',    value: Math.round(p75) },
    { label: 'p90',    value: Math.round(p90) },
  ]

  return (
    <div>
      <div className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-2">
        Projection Distribution
      </div>
      <ResponsiveContainer width="100%" height={120}>
        <BarChart data={data} margin={{ top: 4, right: 0, bottom: 0, left: -20 }}>
          <XAxis
            dataKey="label"
            tick={{ fill: '#8B98A8', fontSize: 10 }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            tick={{ fill: '#8B98A8', fontSize: 10 }}
            axisLine={false}
            tickLine={false}
            domain={['auto', 'auto']}
          />
          <Tooltip
            contentStyle={{ background: '#1C2230', border: '1px solid #2D3748', borderRadius: 8 }}
            labelStyle={{ color: '#E8EDF5', fontSize: 12 }}
            itemStyle={{ color: '#60B4FF', fontSize: 12 }}
            formatter={(v: number) => [`${v} pts`, 'Projection']}
          />
          <Bar dataKey="value" radius={[3, 3, 0, 0]}>
            {data.map((_, i) => (
              <Cell key={i} fill={PERCENTILE_COLORS[i]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <div className="flex justify-between mt-1">
        <div className="text-center">
          <div className="text-xs text-text-muted">Floor</div>
          <div className="text-sm font-medium text-text-primary">{Math.round(player.projection.floor)}</div>
        </div>
        <div className="text-center">
          <div className="text-xs text-text-muted">Ceiling</div>
          <div className="text-sm font-medium text-text-primary">{Math.round(player.projection.ceiling)}</div>
        </div>
      </div>
    </div>
  )
}
