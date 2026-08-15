import { useState, useEffect, useCallback } from 'react'
import type { PlayerDetail, Ranking } from '../types'
import { useDraftState } from '../hooks/useDraftState'
import { useRankings } from '../hooks/useRankings'
import { getPickingTeam } from './draftState'

// Max times a team will draft each position in a 13-round snake draft
const POS_LIMITS: Record<string, number> = { QB: 2, RB: 5, WR: 5, TE: 2 }

// Round threshold before an opponent will draft their first QB
const QB_FIRST_ROUND_MIN = 6

/**
 * Simulate an opponent's pick using positional need.
 *
 * Strategy:
 * 1. Count how many of each position the picking team already has.
 * 2. Block positions that are at their cap.
 * 3. Suppress QB until round 6+ (mirrors real draft behaviour).
 * 4. From the filtered pool, take the highest-ADP player.
 */
export function bestAvailablePlayer(
  draftedIds: string[],
  rankings: Ranking[],
  teamRoster: Record<string, number>,  // position → count already drafted by this team
  currentRound: number,
): PlayerDetail | null {
  const draftedSet = new Set(draftedIds)

  const available = rankings.filter(r => !draftedSet.has(r.player.id))

  // Filter by positional need
  const needed = available.filter(r => {
    const pos = r.player.position
    const count = teamRoster[pos] ?? 0
    const limit = POS_LIMITS[pos] ?? 3

    if (count >= limit) return false

    // Don't let opponent grab their first QB before round QB_FIRST_ROUND_MIN
    if (pos === 'QB' && count === 0 && currentRound < QB_FIRST_ROUND_MIN) return false

    return true
  })

  // Fall back to best available if every position is at its cap (very late rounds)
  const pool = needed.length > 0 ? needed : available

  // Pick lowest ADP (= consensus earliest expected pick)
  const sorted = [...pool].sort((a, b) => (a.adp ?? 999) - (b.adp ?? 999))
  return sorted[0]?.player ?? null
}

export function useAutoAdvance() {
  const { state, draftPlayer, isUserTurn } = useDraftState()
  const { rankings } = useRankings({
    position: 'ALL',
    search: '',
    format: 'ppr',
    draftType: 'redraft',
    year: 2026,
    tierFilter: null,
  })
  const [autoAdvancing, setAutoAdvancing] = useState(false)

  const isDraftComplete =
    state.currentOverallPick > state.config.teams * state.config.totalRounds

  useEffect(() => {
    if (!autoAdvancing) return
    if (isUserTurn || isDraftComplete) {
      setAutoAdvancing(false)
      return
    }
    if (rankings.length === 0) return

    const { currentOverallPick, config, picks } = state
    const { teams } = config

    const pickingTeam = getPickingTeam(currentOverallPick, teams)
    const currentRound = Math.ceil(currentOverallPick / teams)

    // Build this team's current roster from prior picks
    const teamRoster: Record<string, number> = {}
    for (const p of picks) {
      if (p.teamNumber === pickingTeam) {
        const pos = p.player.position
        teamRoster[pos] = (teamRoster[pos] ?? 0) + 1
      }
    }

    const draftedIds = picks.map(p => p.player.id)
    const pick = bestAvailablePlayer(draftedIds, rankings, teamRoster, currentRound)

    if (!pick) {
      setAutoAdvancing(false)
      return
    }

    const timer = setTimeout(() => draftPlayer(pick), 150)
    return () => clearTimeout(timer)
  }, [autoAdvancing, isUserTurn, isDraftComplete, state.picks, draftPlayer, rankings, state])

  const startAutoAdvance = useCallback(() => setAutoAdvancing(true), [])
  const stopAutoAdvance = useCallback(() => setAutoAdvancing(false), [])

  return { autoAdvancing, startAutoAdvance, stopAutoAdvance }
}
