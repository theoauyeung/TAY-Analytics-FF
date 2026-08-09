import { useEffect } from 'react'
import { X, TrendingUp, TrendingDown, Minus } from 'lucide-react'
import clsx from 'clsx'
import { usePlayer } from '../../hooks/usePlayer'
import { PositionBadge } from '../ui/Badge'
import { Spinner } from '../ui/Spinner'

interface Props {
  playerId: string | null
  onClose: () => void
}

function MetricRow({ label, value, detail }: { label: string; value: string; detail?: string }) {
  return (
    <div className="flex items-center justify-between py-1.5 border-b border-border/40">
      <span className="text-xs text-text-secondary">{label}</span>
      <div className="text-right">
        <span className="text-sm font-medium text-text-primary">{value}</span>
        {detail && <div className="text-xs text-text-muted">{detail}</div>}
      </div>
    </div>
  )
}

function SectionHeader({ title }: { title: string }) {
  return (
    <div className="text-xs font-bold tracking-widest text-accent uppercase mt-5 mb-2">
      {title}
    </div>
  )
}

export function PlayerDrawer({ playerId, onClose }: Props) {
  const { player, isLoading } = usePlayer(playerId)

  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [onClose])

  return (
    <>
      {/* Backdrop */}
      {playerId && (
        <div
          className="fixed inset-0 bg-black/40 z-40 transition-opacity"
          onClick={onClose}
        />
      )}

      {/* Drawer */}
      <aside
        className={clsx(
          'fixed right-0 top-0 h-screen w-96 bg-bg-secondary border-l border-border z-50 flex flex-col transition-transform duration-200',
          playerId ? 'translate-x-0' : 'translate-x-full'
        )}
      >
        {/* Header */}
        <div className="flex items-start justify-between p-5 border-b border-border">
          <div className="flex items-center gap-3">
            {player && (
              <>
                <div className="w-12 h-12 rounded-full overflow-hidden bg-bg-elevated flex-shrink-0">
                  {player.imageUrl ? (
                    <img src={player.imageUrl} alt={player.name} className="w-full h-full object-cover"
                      onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }} />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-lg font-bold text-text-muted">
                      {player.name.charAt(0)}
                    </div>
                  )}
                </div>
                <div>
                  <h2 className="text-lg font-bold text-text-primary">{player.name}</h2>
                  <div className="flex items-center gap-2 mt-0.5">
                    <PositionBadge position={player.position} />
                    <span className="text-xs text-text-secondary">{player.team} · Bye {player.byeWeek}</span>
                  </div>
                </div>
              </>
            )}
          </div>
          <button onClick={onClose} className="text-text-muted hover:text-text-primary transition-colors p-1">
            <X size={18} />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-5">
          {isLoading && <div className="flex justify-center py-10"><Spinner /></div>}

          {player && (
            <>
              {/* Projection band */}
              <div className="bg-bg-elevated rounded-xl p-4 grid grid-cols-3 gap-3 text-center">
                <div>
                  <div className="text-xs text-text-muted mb-1">Floor</div>
                  <div className="text-xl font-bold text-text-secondary">{player.projection.floor.toFixed(0)}</div>
                </div>
                <div>
                  <div className="text-xs text-accent mb-1">Median</div>
                  <div className="text-2xl font-bold text-text-primary">{player.projection.median.toFixed(0)}</div>
                </div>
                <div>
                  <div className="text-xs text-text-muted mb-1">Ceiling</div>
                  <div className="text-xl font-bold text-text-secondary">{player.projection.ceiling.toFixed(0)}</div>
                </div>
              </div>

              {/* Boom/bust */}
              <div className="mt-3 flex gap-3">
                <div className="flex-1 bg-green-900/20 border border-green-800/40 rounded-lg p-2.5 text-center">
                  <div className="text-xs text-text-muted">Boom</div>
                  <div className="text-sm font-bold text-green-400">
                    {(player.projection.boomProbability * 100).toFixed(0)}%
                  </div>
                </div>
                <div className="flex-1 bg-red-900/20 border border-red-800/40 rounded-lg p-2.5 text-center">
                  <div className="text-xs text-text-muted">Bust</div>
                  <div className="text-sm font-bold text-red-400">
                    {(player.projection.bustProbability * 100).toFixed(0)}%
                  </div>
                </div>
                <div className="flex-1 bg-bg-elevated border border-border rounded-lg p-2.5 text-center">
                  <div className="text-xs text-text-muted">GP</div>
                  <div className="text-sm font-bold text-text-primary">
                    {player.projection.gamesPlayed.toFixed(1)}
                  </div>
                </div>
              </div>

              {/* Opportunity */}
              <SectionHeader title="Opportunity" />
              {player.opportunity.targetShare !== null && (
                <MetricRow label="Target Share" value={`${(player.opportunity.targetShare * 100).toFixed(1)}%`} />
              )}
              {player.opportunity.routeParticipation !== null && (
                <MetricRow label="Route Participation" value={`${(player.opportunity.routeParticipation * 100).toFixed(1)}%`} />
              )}
              <MetricRow label="Snap Share" value={`${(player.opportunity.snapShare * 100).toFixed(1)}%`} />
              {player.opportunity.rushShare !== null && (
                <MetricRow label="Rush Share" value={`${(player.opportunity.rushShare * 100).toFixed(1)}%`} />
              )}
              {player.opportunity.redZoneUsage !== null && (
                <MetricRow label="Red Zone Usage" value={`${(player.opportunity.redZoneUsage * 100).toFixed(1)}%`} />
              )}

              {/* Efficiency */}
              <SectionHeader title="Efficiency" />
              {player.efficiency.yardsPerRouteRun !== null && (
                <MetricRow label="Yards/Route Run" value={player.efficiency.yardsPerRouteRun.toFixed(2)} />
              )}
              {player.efficiency.yardsPerTarget !== null && (
                <MetricRow label="Yards/Target" value={player.efficiency.yardsPerTarget.toFixed(1)} />
              )}
              {player.efficiency.catchRate !== null && (
                <MetricRow label="Catch Rate" value={`${(player.efficiency.catchRate * 100).toFixed(1)}%`} />
              )}
              {player.efficiency.yardsPerCarry !== null && (
                <MetricRow label="Yards/Carry" value={player.efficiency.yardsPerCarry.toFixed(1)} />
              )}
              {player.efficiency.completionPct !== null && (
                <MetricRow label="Completion %" value={`${(player.efficiency.completionPct * 100).toFixed(1)}%`} />
              )}
              {player.efficiency.yardsPerAttempt !== null && (
                <MetricRow label="Yards/Attempt" value={player.efficiency.yardsPerAttempt.toFixed(1)} />
              )}
              {player.efficiency.epaPerPlay !== null && (
                <MetricRow label="EPA/Play" value={player.efficiency.epaPerPlay.toFixed(3)} />
              )}

              {/* Model assessment */}
              <SectionHeader title="Model Assessment" />
              <div className="bg-bg-elevated rounded-lg p-3 space-y-1.5 text-xs text-text-secondary">
                <p>This player projects as a strong value relative to current ADP. The model weights their elevated target share and elite route participation as primary upside drivers. Confidence is high given stable team situation and consistent usage patterns.</p>
                <p className="text-text-muted pt-1">
                  Confidence: {(player.modelConfidence * 100).toFixed(0)}% ·
                  Breakout: {(player.breakoutProbability * 100).toFixed(0)}% ·
                  Bust risk: {(player.bustRisk * 100).toFixed(0)}%
                </p>
              </div>
            </>
          )}
        </div>
      </aside>
    </>
  )
}
