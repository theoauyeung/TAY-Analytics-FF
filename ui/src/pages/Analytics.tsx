import { useEffect, useState } from 'react'
import { fetchDraftValue, type DraftValueData, type UndervaluedPlayer } from '../api/analytics'
import { Spinner } from '../components/ui/Spinner'

const POSITION_COLORS: Record<string, string> = {
  QB: 'text-red-400',
  RB: 'text-green-400',
  WR: 'text-blue-400',
  TE: 'text-yellow-400',
}

function EfficiencyBadge({ factor }: { factor: number }) {
  const color = factor > 0.5 ? 'text-green-400' : factor < -0.5 ? 'text-red-400' : 'text-text-muted'
  const label = factor > 0 ? `+${factor.toFixed(2)}` : factor.toFixed(2)
  return <span className={`font-mono text-xs ${color}`}>{label}</span>
}

export function Analytics() {
  const [data, setData] = useState<DraftValueData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchDraftValue()
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="flex items-center justify-center h-64"><Spinner size={32} /></div>
  if (error)   return <div className="p-6 text-red-400">Error: {error}</div>
  if (!data)   return null

  const noData = data.undervalued.length === 0

  return (
    <div className="p-6 space-y-8">
      <div>
        <h1 className="text-xl font-semibold text-text-primary">Draft Analytics</h1>
        <p className="text-sm text-text-muted mt-1">
          Players whose model projection significantly outperforms or underperforms their ADP bucket peers.
        </p>
      </div>

      {noData ? (
        <div className="rounded-lg border border-border p-8 text-center text-text-muted">
          <p className="font-medium">No analytics data yet.</p>
          <p className="text-sm mt-1">
            Run <code className="bg-bg-secondary px-1 rounded">uv run python -c "from tay.analytics.draft_value import compute_draft_value; from tay.db import get_conn, init_schema; c=get_conn(); init_schema(c); compute_draft_value(c); c.close()"</code> to populate.
          </p>
        </div>
      ) : (
        <section>
          <h2 className="text-base font-semibold text-text-primary mb-3">
            Historically Undervalued Players
          </h2>
          <div className="overflow-auto rounded-lg border border-border">
            <table className="w-full text-sm border-collapse">
              <thead className="sticky top-0 bg-bg-secondary border-b border-border">
                <tr>
                  <th className="py-2 px-3 text-left text-xs font-semibold text-text-muted">Player</th>
                  <th className="py-2 px-3 text-left text-xs font-semibold text-text-muted">Pos</th>
                  <th className="py-2 px-3 text-right text-xs font-semibold text-text-muted">ADP</th>
                  <th className="py-2 px-3 text-right text-xs font-semibold text-text-muted">Bucket</th>
                  <th className="py-2 px-3 text-right text-xs font-semibold text-text-muted">Proj vs Peers</th>
                  <th className="py-2 px-3 text-right text-xs font-semibold text-text-muted">Efficiency</th>
                  <th className="py-2 px-3 text-right text-xs font-semibold text-text-muted">Samples</th>
                </tr>
              </thead>
              <tbody className="bg-bg-card">
                {data.undervalued.map((p: UndervaluedPlayer) => (
                  <tr key={`${p.name}-${p.position}`} className="border-b border-border last:border-0 hover:bg-bg-secondary">
                    <td className="py-2 px-3 font-medium text-text-primary">{p.name}</td>
                    <td className={`py-2 px-3 font-semibold text-xs ${POSITION_COLORS[p.position] ?? ''}`}>{p.position}</td>
                    <td className="py-2 px-3 text-right text-text-muted">{p.adp < 900 ? p.adp.toFixed(1) : '—'}</td>
                    <td className="py-2 px-3 text-right text-text-muted">{p.adp_bucket}</td>
                    <td className="py-2 px-3 text-right text-text-primary">
                      {p.avg_pts_above > 0 ? '+' : ''}{p.avg_pts_above.toFixed(1)}
                    </td>
                    <td className="py-2 px-3 text-right"><EfficiencyBadge factor={p.efficiency_factor} /></td>
                    <td className="py-2 px-3 text-right text-text-muted">{p.sample_size}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  )
}
