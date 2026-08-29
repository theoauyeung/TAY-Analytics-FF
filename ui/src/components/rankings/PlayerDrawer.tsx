import { useEffect } from 'react'
import { X } from 'lucide-react'
import clsx from 'clsx'
import { usePlayer } from '../../hooks/usePlayer'
import { PositionBadge } from '../ui/Badge'
import { Spinner } from '../ui/Spinner'
import type { Position, ProjectedStats } from '../../types'

interface Props {
  playerId: string | null
  onClose: () => void
}

function StatRow({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="flex items-baseline justify-between py-1.5 border-b border-border/30">
      <span className="text-xs text-text-muted">{label}</span>
      <div className="text-right">
        <span className="text-sm font-medium font-mono text-text-primary">{value}</span>
        {sub && <span className="text-xs text-text-muted ml-1.5">{sub}</span>}
      </div>
    </div>
  )
}

function SectionLabel({ title }: { title: string }) {
  return (
    <div className="text-xs font-condensed font-semibold tracking-wide text-text-muted uppercase mt-5 mb-2">
      {title}
    </div>
  )
}

function fmt(v: number | null, decimals = 0): string {
  if (v === null) return '—'
  return v.toFixed(decimals)
}

function fmtPct(v: number | null): string {
  if (v === null) return '—'
  return `${(v * 100).toFixed(1)}%`
}

type StatDef = { label: string; value: string }

function getProjectedStatRows(position: Position, stats: ProjectedStats): StatDef[] {
  switch (position) {
    case 'RB':
      return [
        { label: 'Rush Attempts', value: fmt(stats.rushAttempts) },
        { label: 'Rush Yards',    value: fmt(stats.rushYards) },
        { label: 'Rush TD',       value: fmt(stats.rushTds, 1) },
        { label: 'Targets',       value: fmt(stats.targets) },
        { label: 'Receptions',    value: fmt(stats.receptions) },
        { label: 'Rec Yards',     value: fmt(stats.recYards) },
        { label: 'Rec TD',        value: fmt(stats.recTds, 1) },
      ]
    case 'WR':
    case 'TE':
      return [
        { label: 'Targets',    value: fmt(stats.targets) },
        { label: 'Receptions', value: fmt(stats.receptions) },
        { label: 'Rec Yards',  value: fmt(stats.recYards) },
        { label: 'Rec TD',     value: fmt(stats.recTds, 1) },
        ...(stats.rushAttempts ? [
          { label: 'Rush Attempts', value: fmt(stats.rushAttempts) },
          { label: 'Rush Yards',    value: fmt(stats.rushYards) },
        ] : []),
      ]
    case 'QB':
      return [
        { label: 'Pass Attempts',  value: fmt(stats.passAttempts) },
        { label: 'Completions',    value: fmt(stats.completions) },
        { label: 'Pass Yards',     value: fmt(stats.passYards) },
        { label: 'Pass TD',        value: fmt(stats.passTds, 1) },
        { label: 'Interceptions',  value: fmt(stats.interceptions, 1) },
        { label: 'Rush Attempts',  value: fmt(stats.rushAttempts) },
        { label: 'Rush Yards',     value: fmt(stats.rushYards) },
        { label: 'Rush TD',        value: fmt(stats.rushTds, 1) },
      ]
    default:
      return []
  }
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

  const hasAnyProjectedStats = player && Object.values(player.projectedStats).some(v => v !== null)

  return (
    <>
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
                <div className="w-14 h-14 rounded-full overflow-hidden bg-bg-elevated flex-shrink-0">
                  {player.imageUrl ? (
                    <img src={player.imageUrl} alt={player.name} className="w-full h-full object-cover"
                      onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }} />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-xl font-bold text-text-muted">
                      {player.name.charAt(0)}
                    </div>
                  )}
                </div>
                <div>
                  <h2 className="text-lg font-bold text-text-primary leading-tight">{player.name}</h2>
                  <div className="flex items-center gap-2 mt-0.5">
                    <PositionBadge position={player.position} />
                    <span className="text-xs text-text-muted">{player.team}</span>
                    {player.byeWeek > 0 && (
                      <span className="text-xs text-text-muted">· Bye {player.byeWeek}</span>
                    )}
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
              {/* 1. Projected Production */}
              {hasAnyProjectedStats && (
                <>
                  <SectionLabel title="Projected Production" />
                  {getProjectedStatRows(player.position, player.projectedStats).map(row => (
                    <StatRow key={row.label} label={row.label} value={row.value} />
                  ))}
                </>
              )}

              {/* 2. Fantasy Projection */}
              <SectionLabel title="Fantasy Projection" />
              <div className="flex items-baseline gap-3 py-2 mb-1">
                <span className="text-3xl font-bold font-mono text-text-primary">
                  {player.projection.mean.toFixed(1)}
                </span>
                <span className="text-sm text-text-muted">PPR pts</span>
              </div>

              {/* Projection range */}
              <div className="grid grid-cols-3 gap-3 mb-1">
                {[
                  { label: 'Floor',   value: player.projection.floor.toFixed(0) },
                  { label: 'Median',  value: player.projection.median.toFixed(0) },
                  { label: 'Ceiling', value: player.projection.ceiling.toFixed(0) },
                ].map(({ label, value }) => (
                  <div key={label} className="text-center border-t border-border pt-2">
                    <div className="text-xs text-text-muted mb-0.5">{label}</div>
                    <div className="text-base font-bold font-mono text-text-secondary">{value}</div>
                  </div>
                ))}
              </div>

              {/* 3. Draft Value */}
              <SectionLabel title="Draft Value" />
              <StatRow label="VOR" value={player.projection.mean > 0 ? `+${(player.projection.mean - 100).toFixed(1)}` : '—'} />
              <StatRow label="ADP" value="—" />

              {/* 4. Opportunity */}
              <SectionLabel title="Usage" />
              {player.opportunity.targetShare !== null && (
                <StatRow label="Target Share" value={fmtPct(player.opportunity.targetShare)} />
              )}
              {player.opportunity.routeParticipation !== null && (
                <StatRow label="Route Participation" value={fmtPct(player.opportunity.routeParticipation)} />
              )}
              <StatRow label="Snap Share" value={fmtPct(player.opportunity.snapShare)} />
              {player.opportunity.rushShare !== null && (
                <StatRow label="Rush Share" value={fmtPct(player.opportunity.rushShare)} />
              )}
              {player.opportunity.redZoneUsage !== null && (
                <StatRow label="Red Zone Usage" value={fmtPct(player.opportunity.redZoneUsage)} />
              )}

              {/* 5. Efficiency */}
              <SectionLabel title="Efficiency" />
              {player.efficiency.yardsPerRouteRun !== null && (
                <StatRow label="Yards/Route Run" value={player.efficiency.yardsPerRouteRun.toFixed(2)} />
              )}
              {player.efficiency.yardsPerTarget !== null && (
                <StatRow label="Yards/Target" value={player.efficiency.yardsPerTarget.toFixed(1)} />
              )}
              {player.efficiency.catchRate !== null && (
                <StatRow label="Catch Rate" value={fmtPct(player.efficiency.catchRate)} />
              )}
              {player.efficiency.yardsPerCarry !== null && (
                <StatRow label="Yards/Carry" value={player.efficiency.yardsPerCarry.toFixed(1)} />
              )}
              {player.efficiency.completionPct !== null && (
                <StatRow label="Completion %" value={fmtPct(player.efficiency.completionPct)} />
              )}
              {player.efficiency.yardsPerAttempt !== null && (
                <StatRow label="Yards/Attempt" value={player.efficiency.yardsPerAttempt.toFixed(1)} />
              )}
              {player.efficiency.epaPerPlay !== null && (
                <StatRow label="EPA/Play" value={player.efficiency.epaPerPlay.toFixed(3)} />
              )}
            </>
          )}
        </div>
      </aside>
    </>
  )
}
