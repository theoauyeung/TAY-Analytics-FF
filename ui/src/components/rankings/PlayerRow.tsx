import clsx from 'clsx'
import type { Ranking, ColumnKey, Position } from '../../types'
import { StatCell } from '../ui/StatCell'
import { ADP_VALUE_THRESHOLD, ADP_OVERVALUED_THRESHOLD } from '../../lib/thresholds'

interface Props {
  ranking: Ranking
  visibleColumns: ColumnKey[]
  onClick: () => void
  isDrafted?: boolean
  isSelected?: boolean
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
  QB:  'ring-pos-qb/40',
  RB:  'ring-pos-rb/40',
  WR:  'ring-pos-wr/40',
  TE:  'ring-pos-te/40',
  K:   'ring-pos-k/40',
  DST: 'ring-pos-dst/40',
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

export function PlayerRow({ ranking, visibleColumns, onClick, isDrafted = false, isSelected = false }: Props) {
  const { player, vor, adpDelta } = ranking
  const hasInjury = player.injuryStatus !== null && player.injuryStatus !== 'healthy'

  const rowBase = clsx(
    'border-b border-border/20 cursor-pointer transition-colors group relative',
    isDrafted && 'opacity-40 pointer-events-none',
    isSelected
      ? 'bg-accent-muted/30'
      : 'hover:bg-bg-elevated/50'
  )

  return (
    <tr onClick={onClick} className={rowBase}>

      {/* Rank */}
      <td className="py-3 px-4 text-center w-14">
        <span className="text-sm font-tabular font-medium text-text-muted">{ranking.rank}</span>
      </td>

      {/* Player — sticky, dominant */}
      <td className={clsx(
        'py-2.5 px-3 min-w-[200px] sticky left-0 transition-colors',
        'border-l-2',
        isSelected
          ? 'border-accent bg-accent-muted/30'
          : 'border-transparent group-hover:border-accent/40 bg-bg-primary group-hover:bg-bg-elevated/50'
      )}>
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
            {/* Player name + signal — dominant */}
            <div className="flex items-baseline gap-2 leading-tight">
              <span className={clsx(
                'font-semibold text-sm leading-tight transition-colors truncate',
                isSelected ? 'text-accent' : 'text-text-primary group-hover:text-white'
              )}>
                {player.name}
              </span>
              <ModelSignal adpDelta={adpDelta} />
              {hasInjury && (
                <span className="text-[9px] font-condensed font-semibold tracking-wide text-yellow-400 uppercase shrink-0">
                  {player.injuryStatus}
                </span>
              )}
            </div>
            {/* Position + team — compact metadata */}
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
        <td className="py-2.5 px-2 text-center text-xs font-tabular text-text-secondary w-12">
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
          <span className="text-sm font-tabular text-text-secondary">{ranking.modelRank}</span>
        </td>
      )}

      {/* Tier */}
      {visibleColumns.includes('tier') && (
        <td className="py-2.5 px-3 text-center w-12">
          <span className="text-xs font-bold text-text-muted">{ranking.tier.number}</span>
        </td>
      )}

      {/* Optional stat columns */}
      {visibleColumns.includes('floor') && (
        <td className="py-2.5 px-3 text-right w-16 text-sm font-tabular text-text-secondary">{fmt(ranking.floor)}</td>
      )}
      {visibleColumns.includes('ceiling') && (
        <td className="py-2.5 px-3 text-right w-16 text-sm font-tabular text-text-secondary">{fmt(ranking.ceiling)}</td>
      )}
      {visibleColumns.includes('targetShare') && (
        <td className="py-2.5 px-3 text-right w-16 text-sm font-tabular text-text-secondary">{fmtPct(ranking.targetShare)}</td>
      )}
      {visibleColumns.includes('rushShare') && (
        <td className="py-2.5 px-3 text-right w-16 text-sm font-tabular text-text-secondary">{fmtPct(ranking.rushShare)}</td>
      )}
      {visibleColumns.includes('snapPct') && (
        <td className="py-2.5 px-3 text-right w-16 text-sm font-tabular text-text-secondary">{fmtPct(ranking.snapPct)}</td>
      )}
      {visibleColumns.includes('routePct') && (
        <td className="py-2.5 px-3 text-right w-16 text-sm font-tabular text-text-secondary">{fmtPct(ranking.routePct)}</td>
      )}
      {visibleColumns.includes('redZoneUsage') && (
        <td className="py-2.5 px-3 text-right w-16 text-sm font-tabular text-text-secondary">{fmtPct(ranking.redZoneUsage)}</td>
      )}
      {visibleColumns.includes('tdProjection') && (
        <td className="py-2.5 px-3 text-right w-16 text-sm font-tabular text-text-secondary">{fmt(ranking.tdProjection, 1)}</td>
      )}
      {visibleColumns.includes('gamesPlayed') && (
        <td className="py-2.5 px-3 text-right w-16 text-sm font-tabular text-text-secondary">{fmt(ranking.gamesPlayed, 1)}</td>
      )}
      {visibleColumns.includes('adpDelta') && (
        <td className={clsx(
          'py-2.5 px-3 text-right w-16 text-sm font-tabular font-medium',
          adpDelta <= ADP_VALUE_THRESHOLD ? 'text-accent' : adpDelta >= ADP_OVERVALUED_THRESHOLD ? 'text-red-400' : 'text-text-secondary'
        )}>
          {adpDelta >= 0 ? '+' : ''}{adpDelta}
        </td>
      )}
    </tr>
  )
}
