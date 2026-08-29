import { useState, useEffect, useRef, useMemo } from 'react'
import { Search } from 'lucide-react'
import clsx from 'clsx'
import { useDraftState } from '../../hooks/useDraftState'
import { useRankings } from '../../hooks/useRankings'
import { PositionBadge } from '../ui/Badge'
import { getPickingTeam, computeUserPickNumbers } from '../../state/draftState'

export function OpponentPickPanel() {
  const { state, draftPlayer, picksUntil } = useDraftState()
  const { currentOverallPick, config, picks } = state
  const { teams, totalRounds } = config

  const { rankings } = useRankings({
    position: 'ALL',
    search: '',
    format: 'ppr',
    draftType: 'redraft',
    year: 2026,
    tierFilter: null,
  })

  const [search, setSearch] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  // Auto-focus search on every opponent pick
  useEffect(() => {
    inputRef.current?.focus()
    setSearch('')
  }, [currentOverallPick])

  const round = Math.ceil(currentOverallPick / teams)
  const pickInRound = ((currentOverallPick - 1) % teams) + 1
  const pickingTeam = getPickingTeam(currentOverallPick, teams)

  // Next user pick
  const userPicks = computeUserPickNumbers(config)
  const nextUserPick = userPicks.find(n => n > currentOverallPick)
  const nextUserRound = nextUserPick ? Math.ceil(nextUserPick / teams) : null

  // Drafted IDs for fast lookup
  const draftedSet = useMemo(
    () => new Set(picks.map(p => p.player.id)),
    [picks]
  )

  // Available players filtered by search, sorted by ADP
  const available = useMemo(() => {
    return rankings
      .filter(r => !draftedSet.has(r.player.id))
      .filter(r => {
        if (!search) return true
        const q = search.toLowerCase()
        return (
          r.player.name.toLowerCase().includes(q) ||
          r.player.team.toLowerCase().includes(q) ||
          r.player.position.toLowerCase().includes(q)
        )
      })
      .sort((a, b) => (a.adp ?? 999) - (b.adp ?? 999))
      .slice(0, search ? 20 : 12)
  }, [rankings, draftedSet, search])

  function handleOpponentPick(player: import('../../types').PlayerDetail) {
    draftPlayer(player, false)
    setSearch('')
  }

  return (
    <div className="flex-1 flex flex-col overflow-hidden px-6 py-5">
      {/* Pick context header */}
      <div className="mb-5">
        <div className="flex items-center gap-3 mb-1">
          <span className="text-xs font-bold tracking-wide text-text-muted uppercase">
            Round {round} · Pick {pickInRound}
          </span>
          <span className="text-xs text-text-muted">·</span>
          <span className="text-xs text-text-muted">
            Overall #{currentOverallPick}
          </span>
        </div>
        <div className="text-xl font-bold text-text-primary">
          Team {pickingTeam} is on the clock
        </div>
        {picksUntil > 0 && (
          <div className="text-sm text-text-secondary mt-0.5">
            Your pick in{' '}
            <span className="text-accent font-semibold">{picksUntil}</span>
            {nextUserRound && (
              <span className="text-text-muted"> · Round {nextUserRound}</span>
            )}
          </div>
        )}
      </div>

      {/* Search */}
      <div className="relative mb-4">
        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
        <input
          ref={inputRef}
          type="text"
          placeholder="Who did they pick? Search by name or team…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="w-full bg-bg-elevated border border-border rounded-md pl-9 pr-4 py-2.5 text-sm text-text-primary placeholder-text-muted focus:outline-none focus:border-accent"
        />
      </div>

      {/* Player list */}
      <div className="flex-1 overflow-y-auto space-y-1">
        {available.map(ranking => (
          <button
            key={ranking.player.id}
            onClick={() => handleOpponentPick(ranking.player)}
            className={clsx(
              'w-full flex items-center gap-3 px-3 py-2.5 rounded-md border border-transparent',
              'hover:bg-bg-elevated hover:border-border transition-colors text-left'
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
                  onError={e => { (e.target as HTMLImageElement).style.display = 'none' }}
                />
              ) : (
                <span className="text-xs font-bold text-text-muted">
                  {ranking.player.name.charAt(0)}
                </span>
              )}
            </div>

            {/* Name + team */}
            <div className="flex-1 min-w-0">
              <div className="text-sm font-semibold text-text-primary truncate">
                {ranking.player.name}
              </div>
              <div className="text-xs text-text-muted">{ranking.player.team}</div>
            </div>

            <PositionBadge position={ranking.player.position} />

            <span className="text-xs font-mono text-text-secondary flex-shrink-0">
              {ranking.projection.toFixed(0)} pts
            </span>

            <span className="text-xs text-text-muted flex-shrink-0 w-16 text-right">
              ADP {ranking.adp ?? '–'}
            </span>
          </button>
        ))}

        {available.length === 0 && (
          <div className="flex items-center justify-center h-24 text-text-muted text-sm">
            No players found
          </div>
        )}
      </div>
    </div>
  )
}
