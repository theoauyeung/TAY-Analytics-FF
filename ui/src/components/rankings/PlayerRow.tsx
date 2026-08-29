import clsx from 'clsx'
import type { Ranking, ColumnKey } from '../../types'
import { PositionBadge, SignalBadge } from '../ui/Badge'
import { StatCell } from '../ui/StatCell'
import { ADP_VALUE_THRESHOLD, ADP_OVERVALUED_THRESHOLD } from '../../lib/thresholds'

interface Props {
  ranking: Ranking
  visibleColumns: ColumnKey[]
  onClick: () => void
  isDrafted?: boolean
}

function fmt(v: number | null, decimals = 1): string {
  if (v === null) return '—'
  return v.toFixed(decimals)
}

function fmtPct(v: number | null): string {
  if (v === null) return '—'
  return `${(v * 100).toFixed(1)}%`
}

export function PlayerRow({ ranking, visibleColumns, onClick, isDrafted = false }: Props) {
  const { player, vor, adpDelta } = ranking

  const isUndervalued = adpDelta <= ADP_VALUE_THRESHOLD
  const isOvervalued  = adpDelta >= ADP_OVERVALUED_THRESHOLD
  const hasInjury     = player.injuryStatus !== null && player.injuryStatus !== 'healthy'

  return (
    <tr
      onClick={onClick}
      className={clsx(
        'border-b border-border/30 cursor-pointer transition-colors group',
        isDrafted
          ? 'opacity-40 pointer-events-none'
          : 'hover:bg-bg-elevated/60'
      )}
    >
      {/* Rank */}
      <td className="py-3 px-4 text-center w-14">
        <span className="text-base font-bold font-mono text-text-muted">{ranking.rank}</span>
      </td>

      {/* Player name — sticky, most prominent */}
      <td className="py-3 px-3 min-w-[200px] sticky left-0 bg-bg-primary group-hover:bg-bg-elevated/60 transition-colors">
        <div className="flex items-center gap-3">
          {/* Headshot */}
          <div className="w-9 h-9 rounded-full overflow-hidden bg-bg-elevated flex-shrink-0">
            {player.imageUrl ? (
              <img
                src={player.imageUrl}
                alt={player.name}
                className="w-full h-full object-cover"
                onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }}
              />
            ) : (
              <div className="w-full h-full flex items-center justify-center text-xs text-text-muted font-bold">
                {player.name.charAt(0)}
              </div>
            )}
          </div>
          <div>
            <div className="font-semibold text-sm text-text-primary leading-tight flex items-center gap-2">
              {player.name}
              {isUndervalued && <SignalBadge signal="value" label="▲ Value" />}
              {isOvervalued && <SignalBadge signal="avoid" label="▼ Fade" />}
              {hasInjury && <SignalBadge signal="injury" label={player.injuryStatus ?? ''} />}
            </div>
            <div className="flex items-center gap-1.5 mt-0.5">
              <PositionBadge position={player.position} />
              <span className="text-xs text-text-muted">{player.team}</span>
            </div>
          </div>
        </div>
      </td>

      {/* Position */}
      {visibleColumns.includes('position') && (
        <td className="py-2.5 px-3 text-center w-14">
          <PositionBadge position={player.position} />
        </td>
      )}

      {/* Team */}
      {visibleColumns.includes('team') && (
        <td className="py-2.5 px-2 text-center text-xs font-mono text-text-secondary w-12">
          {player.team}
        </td>
      )}

      {/* Bye */}
      {visibleColumns.includes('bye') && (
        <td className="py-2.5 px-2 text-center text-xs text-text-muted w-10">
          {player.byeWeek}
        </td>
      )}

      {/* Projection */}
      {visibleColumns.includes('projection') && (
        <td className="py-2.5 px-3 text-right w-20">
          <StatCell
            value={fmt(ranking.projection)}
            positive={ranking.projection >= 250}
            detail={
              <div className="space-y-1">
                <div>Floor: {fmt(ranking.floor)}</div>
                <div>Median: {fmt(ranking.player.projection.median)}</div>
                <div>Ceiling: {fmt(ranking.ceiling)}</div>
              </div>
            }
          />
        </td>
      )}

      {/* VOR */}
      {visibleColumns.includes('vor') && (
        <td className="py-2.5 px-3 text-right w-20">
          <StatCell
            value={vor >= 0 ? `+${fmt(vor)}` : fmt(vor)}
            positive={vor >= 20}
            negative={vor < 0}
            detail={
              <div className="space-y-1">
                <div>VOR: {fmt(vor)}</div>
                <div>Replacement level: {fmt(ranking.replacementLevel)}</div>
                <div className="text-text-muted pt-1">
                  VOR = Projection − Replacement Level at {player.position}
                </div>
              </div>
            }
          />
        </td>
      )}

      {/* ADP */}
      {visibleColumns.includes('adp') && (
        <td className="py-2.5 px-3 text-center w-16">
          <StatCell
            value={ranking.adp}
            detail={
              <div className="space-y-1">
                <div>ESPN ADP: {ranking.adp}</div>
                <div>Model Rank: {ranking.modelRank}</div>
                <div className={adpDelta >= 0 ? 'text-green-400' : 'text-red-400'}>
                  Delta: {adpDelta >= 0 ? '+' : ''}{adpDelta}
                </div>
              </div>
            }
          />
        </td>
      )}

      {/* Model Rank */}
      {visibleColumns.includes('modelRank') && (
        <td className="py-2.5 px-3 text-center w-16">
          <span className="text-sm text-text-secondary font-mono">{ranking.modelRank}</span>
        </td>
      )}

      {/* Tier */}
      {visibleColumns.includes('tier') && (
        <td className="py-2.5 px-3 text-center w-12">
          <span className="text-xs font-bold text-text-muted">{ranking.tier.number}</span>
        </td>
      )}

      {/* Optional columns */}
      {visibleColumns.includes('floor') && (
        <td className="py-2.5 px-3 text-right w-16 text-sm text-text-secondary">{fmt(ranking.floor)}</td>
      )}
      {visibleColumns.includes('ceiling') && (
        <td className="py-2.5 px-3 text-right w-16 text-sm text-text-secondary">{fmt(ranking.ceiling)}</td>
      )}
      {visibleColumns.includes('targetShare') && (
        <td className="py-2.5 px-3 text-right w-16 text-sm text-text-secondary">{fmtPct(ranking.targetShare)}</td>
      )}
      {visibleColumns.includes('rushShare') && (
        <td className="py-2.5 px-3 text-right w-16 text-sm text-text-secondary">{fmtPct(ranking.rushShare)}</td>
      )}
      {visibleColumns.includes('snapPct') && (
        <td className="py-2.5 px-3 text-right w-16 text-sm text-text-secondary">{fmtPct(ranking.snapPct)}</td>
      )}
      {visibleColumns.includes('routePct') && (
        <td className="py-2.5 px-3 text-right w-16 text-sm text-text-secondary">{fmtPct(ranking.routePct)}</td>
      )}
      {visibleColumns.includes('redZoneUsage') && (
        <td className="py-2.5 px-3 text-right w-16 text-sm text-text-secondary">{fmtPct(ranking.redZoneUsage)}</td>
      )}
      {visibleColumns.includes('tdProjection') && (
        <td className="py-2.5 px-3 text-right w-16 text-sm text-text-secondary">{fmt(ranking.tdProjection, 1)}</td>
      )}
      {visibleColumns.includes('gamesPlayed') && (
        <td className="py-2.5 px-3 text-right w-16 text-sm text-text-secondary">{fmt(ranking.gamesPlayed, 1)}</td>
      )}
      {visibleColumns.includes('modelConfidence') && (
        <td className="py-2.5 px-3 text-right w-16 text-sm text-text-secondary">{fmtPct(ranking.modelConfidence)}</td>
      )}
      {visibleColumns.includes('adpDelta') && (
        <td className={clsx('py-2.5 px-3 text-right w-16 text-sm font-medium', adpDelta <= ADP_VALUE_THRESHOLD ? 'text-green-400' : adpDelta >= ADP_OVERVALUED_THRESHOLD ? 'text-red-400' : 'text-text-secondary')}>
          {adpDelta >= 0 ? '+' : ''}{adpDelta}
        </td>
      )}
    </tr>
  )
}
