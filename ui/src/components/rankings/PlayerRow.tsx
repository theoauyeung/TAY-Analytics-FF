import clsx from 'clsx'
import type { Ranking, ColumnKey, Position } from '../../types'
import { StatCell } from '../ui/StatCell'
import { ADP_VALUE_THRESHOLD, ADP_OVERVALUED_THRESHOLD } from '../../lib/thresholds'

interface Props {
  ranking: Ranking
  visibleColumns: ColumnKey[]
  isDrafted?: boolean
}

const POS_COLORS: Record<Position, string> = {
  QB:  'text-pos-qb',
  RB:  'text-pos-rb',
  WR:  'text-pos-wr',
  TE:  'text-pos-te',
  K:   'text-pos-k',
  DST: 'text-pos-dst',
}

const POS_RING: Record<Position, string> = {
  QB:  'ring-[#E8844A]/30',
  RB:  'ring-[#4AE8A0]/30',
  WR:  'ring-[#60B4FF]/30',
  TE:  'ring-[#C47EE8]/30',
  K:   'ring-[#E8E04A]/30',
  DST: 'ring-[#E84A4A]/30',
}

function fmt(v: number | null, decimals = 1): string {
  if (v === null) return '—'
  return v.toFixed(decimals)
}

function fmtPct(v: number | null): string {
  if (v === null) return '—'
  return `${(v * 100).toFixed(1)}%`
}

function ModelSignal({ adpDelta }: { adpDelta: number }) {
  if (adpDelta <= ADP_VALUE_THRESHOLD) {
    return (
      <span className="text-[10px] font-condensed font-semibold tracking-wide text-accent tabular-nums">
        ↑{Math.abs(adpDelta)}
      </span>
    )
  }
  if (adpDelta >= ADP_OVERVALUED_THRESHOLD) {
    return (
      <span className="text-[10px] font-condensed font-semibold tracking-wide text-red-400 tabular-nums">
        ↓{adpDelta}
      </span>
    )
  }
  return null
}

export function PlayerRow({ ranking, visibleColumns, isDrafted = false }: Props) {
  const { player, vor, adpDelta } = ranking
  const hasInjury = player.injuryStatus !== null && player.injuryStatus !== 'healthy'

  return (
    <tr className={clsx(
      'border-b border-border/20 hover:bg-bg-elevated/40 transition-colors group even:bg-white/[0.018]',
      isDrafted && 'opacity-40 pointer-events-none'
    )}>

      {/* Rank */}
      <td className="py-3 px-4 text-center w-14">
        <span className="text-base tabular-nums font-bold text-text-secondary">{ranking.rank}</span>
      </td>

      {/* Player — sticky */}
      <td className="py-2.5 px-3 min-w-[200px] sticky left-0 bg-bg-primary group-hover:bg-bg-elevated/40 transition-colors">
        <div className="flex items-center gap-3">
          {/* Headshot with position-colored ring */}
          <div className={clsx(
            'w-9 h-9 rounded-full overflow-hidden bg-bg-elevated flex-shrink-0 ring-1',
            POS_RING[player.position]
          )}>
            {player.imageUrl ? (
              <img
                src={player.imageUrl}
                alt={player.name}
                className="w-full h-full object-cover"
                onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }}
              />
            ) : (
              <div className="w-full h-full flex items-center justify-center text-xs font-bold text-text-muted">
                {player.name.charAt(0)}
              </div>
            )}
          </div>

          <div className="min-w-0">
            <div className="flex items-baseline gap-2 leading-tight">
              <span className="font-semibold text-sm text-text-primary group-hover:text-white transition-colors truncate">
                {player.name}
              </span>
              <ModelSignal adpDelta={adpDelta} />
              {hasInjury && (
                <span className="text-[9px] font-condensed font-semibold tracking-wide text-yellow-400 uppercase shrink-0">
                  {player.injuryStatus}
                </span>
              )}
            </div>
            <div className="flex items-center gap-1.5 mt-0.5">
              <span className={clsx('text-[10px] font-condensed font-semibold tracking-wide', POS_COLORS[player.position])}>
                {player.position}
              </span>
              <span className="text-[10px] text-text-muted">·</span>
              <span className="text-[10px] text-text-muted font-medium">{player.team}</span>
            </div>
          </div>
        </div>
      </td>

      {/* Position */}
      {visibleColumns.includes('position') && (
        <td className="py-2.5 px-3 text-center w-14">
          <span className={clsx('text-xs font-condensed font-semibold tracking-wide', POS_COLORS[player.position])}>
            {player.position}
          </span>
        </td>
      )}

      {/* Team */}
      {visibleColumns.includes('team') && (
        <td className="py-2.5 px-2 text-center text-xs tabular-nums text-text-secondary w-12">
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
            hero
            positive={vor >= 60}
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
          <span className="text-sm tabular-nums text-text-secondary">{ranking.modelRank}</span>
        </td>
      )}

      {/* Tier */}
      {visibleColumns.includes('tier') && (
        <td className="py-2.5 px-3 text-center w-12">
          <span className="text-xs font-bold text-text-muted">{ranking.tier.number}</span>
        </td>
      )}

      {visibleColumns.includes('floor') && (
        <td className="py-2.5 px-3 text-right w-16 text-sm tabular-nums text-text-secondary">{fmt(ranking.floor)}</td>
      )}
      {visibleColumns.includes('ceiling') && (
        <td className="py-2.5 px-3 text-right w-16 text-sm tabular-nums text-text-secondary">{fmt(ranking.ceiling)}</td>
      )}
      {visibleColumns.includes('targetShare') && (
        <td className="py-2.5 px-3 text-right w-16 text-sm tabular-nums text-text-secondary">{fmtPct(ranking.targetShare)}</td>
      )}
      {visibleColumns.includes('rushShare') && (
        <td className="py-2.5 px-3 text-right w-16 text-sm tabular-nums text-text-secondary">{fmtPct(ranking.rushShare)}</td>
      )}
      {visibleColumns.includes('snapPct') && (
        <td className="py-2.5 px-3 text-right w-16 text-sm tabular-nums text-text-secondary">{fmtPct(ranking.snapPct)}</td>
      )}
      {visibleColumns.includes('routePct') && (
        <td className="py-2.5 px-3 text-right w-16 text-sm tabular-nums text-text-secondary">{fmtPct(ranking.routePct)}</td>
      )}
      {visibleColumns.includes('redZoneUsage') && (
        <td className="py-2.5 px-3 text-right w-16 text-sm tabular-nums text-text-secondary">{fmtPct(ranking.redZoneUsage)}</td>
      )}
      {visibleColumns.includes('tdProjection') && (
        <td className="py-2.5 px-3 text-right w-16 text-sm tabular-nums text-text-secondary">{fmt(ranking.tdProjection, 1)}</td>
      )}
      {visibleColumns.includes('gamesPlayed') && (
        <td className="py-2.5 px-3 text-right w-16 text-sm tabular-nums text-text-secondary">{fmt(ranking.gamesPlayed, 1)}</td>
      )}
      {visibleColumns.includes('adpDelta') && (
        <td className={clsx(
          'py-2.5 px-3 text-right w-16 text-sm tabular-nums font-medium',
          adpDelta <= ADP_VALUE_THRESHOLD ? 'text-accent' : adpDelta >= ADP_OVERVALUED_THRESHOLD ? 'text-red-400' : 'text-text-secondary'
        )}>
          {adpDelta >= 0 ? '+' : ''}{adpDelta}
        </td>
      )}
    </tr>
  )
}
