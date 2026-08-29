import { useState, useMemo, useEffect } from 'react'
import { Search } from 'lucide-react'
import clsx from 'clsx'
import type { Position, PlayerDetail } from '../../types'
import { useRankings } from '../../hooks/useRankings'
import { useDraftState } from '../../hooks/useDraftState'
import { PositionBadge } from '../ui/Badge'
import { ADP_VALUE_THRESHOLD, ADP_OVERVALUED_THRESHOLD } from '../../lib/thresholds'
import { useDraftContext } from '../../state/draftState'

const POSITION_FILTERS: Array<Position | 'ALL'> = ['ALL', 'QB', 'RB', 'WR', 'TE']

export function AvailablePlayers() {
  const { availablePlayers, draftPlayer, isUserTurn } = useDraftState()
  const { state } = useDraftContext()
  const [search, setSearch] = useState('')
  const [posFilter, setPosFilter] = useState<Position | 'ALL'>('ALL')
  const [pendingId, setPendingId] = useState<string | null>(null)

  const totalPicks = state.config.teams * state.config.totalRounds
  const isDraftComplete = state.currentOverallPick > totalPicks

  const { rankings } = useRankings({
    position: 'ALL',
    search: '',
    format: 'ppr',
    draftType: 'redraft',
    year: 2026,
    tierFilter: null,
  })

  // Build a set of available player IDs for fast lookup
  const availableIds = useMemo(
    () => new Set(availablePlayers.map(p => p.id)),
    [availablePlayers]
  )

  const available = useMemo(() => {
    return rankings
      .filter(r => availableIds.has(r.player.id))
      .filter(r => posFilter === 'ALL' || r.player.position === posFilter)
      .filter(r => {
        if (!search) return true
        const q = search.toLowerCase()
        return (
          r.player.name.toLowerCase().includes(q) ||
          r.player.team.toLowerCase().includes(q)
        )
      })
      .sort((a, b) => (a.adp ?? 999) - (b.adp ?? 999))
  }, [rankings, availableIds, posFilter, search])

  // Dismiss pending on Escape
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') setPendingId(null)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [])

  // Dismiss pending on click outside
  useEffect(() => {
    if (!pendingId) return
    function onMouseDown() {
      setPendingId(null)
    }
    document.addEventListener('mousedown', onMouseDown)
    return () => document.removeEventListener('mousedown', onMouseDown)
  }, [pendingId])

  function handleDraft(player: PlayerDetail, isUserPick: boolean) {
    draftPlayer(player, isUserPick)
    setPendingId(null)
  }

  return (
    <div className="flex flex-col h-full border-r border-border w-80 flex-shrink-0">
      {/* Header */}
      <div className="px-3 pt-3 pb-2 border-b border-border flex-shrink-0">
        <div className="text-xs font-bold tracking-wide text-text-muted uppercase mb-2">
          Available Players
        </div>

        {/* Search */}
        <div className="relative mb-2">
          <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-text-muted" />
          <input
            type="text"
            placeholder="Search…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full bg-bg-elevated border border-border rounded-lg pl-8 pr-3 py-1.5 text-xs text-text-primary placeholder-text-muted focus:outline-none focus:border-accent"
          />
        </div>

        {/* Position filter tabs */}
        <div className="flex gap-0.5">
          {POSITION_FILTERS.map(pos => (
            <button
              key={pos}
              onClick={() => setPosFilter(pos)}
              className={clsx(
                'flex-1 py-1 text-xs transition-colors border-b',
                posFilter === pos
                  ? 'text-text-primary font-semibold border-accent'
                  : 'text-text-muted hover:text-text-secondary border-transparent'
              )}
            >
              {pos}
            </button>
          ))}
        </div>
      </div>

      {/* Player list */}
      <div
        className="flex-1 overflow-y-auto"
        onClick={e => {
          // Dismiss pending if clicking the scroll container itself
          if (e.target === e.currentTarget) setPendingId(null)
        }}
      >
        {available.map(ranking => {
          const isPending = pendingId === ranking.player.id
          const { adpDelta } = ranking

          return (
            <div key={ranking.player.id}>
              {/* Player row */}
              <div
                onClick={() => setPendingId(isPending ? null : ranking.player.id)}
                className={clsx(
                  'flex items-center gap-2.5 px-3 py-2.5 cursor-pointer border-b border-border/40 transition-colors',
                  isPending ? 'bg-accent/10' : 'hover:bg-bg-elevated'
                )}
              >
                {/* ADP position */}
                <span className="text-xs font-mono text-text-muted w-6 text-right flex-shrink-0">
                  {ranking.adp ? Math.round(ranking.adp) : '–'}
                </span>

                {/* Headshot */}
                <div className="w-8 h-8 rounded-full overflow-hidden bg-bg-elevated flex-shrink-0 flex items-center justify-center">
                  {ranking.player.imageUrl ? (
                    <img
                      src={ranking.player.imageUrl}
                      alt={ranking.player.name}
                      className="w-full h-full object-cover"
                      onError={e => {
                        ;(e.target as HTMLImageElement).style.display = 'none'
                      }}
                    />
                  ) : (
                    <span className="text-xs font-bold text-text-muted">
                      {ranking.player.name.charAt(0)}
                    </span>
                  )}
                </div>

                {/* Name + team */}
                <div className="flex-1 min-w-0">
                  <div className="text-xs font-semibold text-text-primary truncate">
                    {ranking.player.name}
                  </div>
                  <div className="text-xs text-text-muted">{ranking.player.team}</div>
                </div>

                {/* Position badge */}
                <PositionBadge position={ranking.player.position} />

                {/* TAY rank — our model's ranking */}
                <span
                  className={clsx(
                    'text-xs font-mono font-bold flex-shrink-0 px-1.5 py-0.5 rounded',
                    adpDelta <= ADP_VALUE_THRESHOLD
                      ? 'text-green-400 bg-green-400/10'
                      : adpDelta >= ADP_OVERVALUED_THRESHOLD
                      ? 'text-red-400 bg-red-400/10'
                      : 'text-text-muted bg-bg-elevated'
                  )}
                  title={`TAY rank #${ranking.rank} · ADP ${ranking.adp}`}
                >
                  #{ranking.rank}
                </span>
              </div>

              {/* Inline draft confirmation — only on user's turn or draft complete */}
              {isPending && (isUserTurn || isDraftComplete) && (
                <div
                  onMouseDown={e => e.stopPropagation()}
                  className="flex items-center gap-2 px-3 py-2 bg-accent/10 border-b border-accent/30"
                >
                  <span className="text-xs text-text-secondary flex-1 truncate">
                    Draft {ranking.player.name}?
                  </span>
                  <button
                    onClick={e => {
                      e.stopPropagation()
                      handleDraft(ranking.player, true)
                    }}
                    className="px-2.5 py-1 text-xs font-bold bg-accent text-bg-primary rounded-lg hover:opacity-90 transition-opacity"
                  >
                    Pick for my team
                  </button>
                  <button
                    onClick={e => {
                      e.stopPropagation()
                      setPendingId(null)
                    }}
                    className="text-xs text-text-muted hover:text-text-primary transition-colors"
                  >
                    ×
                  </button>
                </div>
              )}
            </div>
          )
        })}

        {available.length === 0 && (
          <div className="flex items-center justify-center h-32 text-text-muted text-sm">
            No players found
          </div>
        )}
      </div>
    </div>
  )
}
