# API Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace all mock data in the React frontend with live calls to the FastAPI backend, wiring rankings, players, league settings, and the draft recommendation engine (including session persistence) to real data.

**Architecture:** A centralized `ui/src/api/` module with four domain files sits between the React Query hooks and the network. Each domain file exports typed async functions; hooks import from those files and delete their mock-data imports. A single `client.ts` base layer handles base URL and error normalization. Mock data files in `ui/src/data/` are deleted in the final task once all consumers are updated.

**Tech Stack:** Native `fetch` (no new npm dependencies), Vite env vars, React Query (already installed), TypeScript 6.

## Global Constraints

- API base URL via `VITE_API_URL` env var, default `http://localhost:8000`
- Fixed query params on every backend request: `season=2026`, `model_version=neural-v1`
- Backend uses snake_case; frontend uses camelCase — API modules own all translation
- Player identity: backend `gsis_id` → frontend `player.id`
- Scoring format: frontend `'half_ppr'` ↔ backend `'half'`
- Backend `roster_config` accepts only `QB, RB, WR, TE, FLEX` — omit `BENCH` when sending
- TypeScript check command: `cd ui && npx tsc --noEmit`
- Backend start: `make api` (runs `python scripts/run_api.py`)
- Frontend start: `cd ui && npm run dev` (Vite dev server on port 5173)
- No new npm packages
- No new Python files

---

## File Structure

**Create:**
- `ui/.env` — `VITE_API_URL=http://localhost:8000`
- `ui/.env.example` — same content (committed)
- `ui/src/api/client.ts` — `apiFetch`, `ApiError`, `API_BASE`, `SEASON`, `MODEL_VERSION`
- `ui/src/api/rankings.ts` — `fetchRankings`, `fetchScarcity`
- `ui/src/api/players.ts` — `fetchPlayers`, `fetchPlayer`
- `ui/src/api/draft.ts` — `fetchRecommendation`, `saveSession`, `loadSession`
- `ui/src/api/league.ts` — `fetchLeagueSettings`, `saveLeagueSettings`
- `ui/src/hooks/useRecommendation.ts` — replaces `useMockRecommendation.ts`

**Modify:**
- `ui/src/hooks/useRankings.ts`
- `ui/src/hooks/usePlayer.ts`
- `ui/src/hooks/useDraftState.ts`
- `ui/src/hooks/useLeagueSettings.ts`
- `ui/src/hooks/index.ts`
- `ui/src/pages/Dashboard.tsx`
- `ui/src/pages/Players.tsx`
- `ui/src/components/draft/AvailablePlayers.tsx`
- `ui/src/components/draft/RecommendationPanel.tsx`
- `ui/src/components/draft/MyRoster.tsx`
- `ui/src/components/draft/MayNotMakeItBack.tsx`
- `ui/src/components/roster/RosterBuilder.tsx`
- `ui/src/components/roster/RosterProjection.tsx`
- `ui/src/state/mockDraftSimulator.ts`

**Delete (Task 6 only):**
- `ui/src/data/mockPlayers.ts`
- `ui/src/data/mockRankings.ts`
- `ui/src/data/mockDashboard.ts`
- `ui/src/data/mockDraftConfig.ts`
- `ui/src/data/index.ts`

---

### Task 1: API Client Layer

**Files:**
- Create: `ui/.env`
- Create: `ui/.env.example`
- Create: `ui/src/api/client.ts`

**Interfaces:**
- Produces: `apiFetch<T>(path, init?) → Promise<T>`, `ApiError(status, message)`, `API_BASE: string`, `SEASON: 2026`, `MODEL_VERSION: 'neural-v1'`

- [ ] **Step 1: Create `ui/.env`**

```
VITE_API_URL=http://localhost:8000
```

- [ ] **Step 2: Create `ui/.env.example`**

```
VITE_API_URL=http://localhost:8000
```

- [ ] **Step 3: Create `ui/src/api/client.ts`**

```typescript
export const API_BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? 'http://localhost:8000'
export const SEASON = 2026
export const MODEL_VERSION = 'neural-v1'

export class ApiError extends Error {
  constructor(public readonly status: number, message: string) {
    super(message)
    this.name = 'ApiError'
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({})) as { detail?: string }
    throw new ApiError(res.status, body.detail ?? res.statusText)
  }
  return res.json() as Promise<T>
}
```

- [ ] **Step 4: Verify TypeScript compiles**

Run: `cd ui && npx tsc --noEmit`
Expected: 0 errors

- [ ] **Step 5: Commit**

```bash
git add ui/.env.example ui/src/api/client.ts
git commit -m "feat: API client layer — apiFetch, ApiError, env config"
```

Note: `ui/.env` is gitignored; only `ui/.env.example` is committed.

---

### Task 2: Rankings API Module + useRankings Hook

**Files:**
- Create: `ui/src/api/rankings.ts`
- Modify: `ui/src/hooks/useRankings.ts`

**Interfaces:**
- Consumes: `apiFetch`, `SEASON`, `MODEL_VERSION` from `../api/client`
- Produces:
  - `fetchRankings(filters: RankingFilters): Promise<Ranking[]>` — GET /rankings
  - `fetchScarcity(): Promise<BackendScarcity[]>` — GET /scarcity
  - Updated `useRankings(filters)` returns `{ rankings, isLoading, error, refetch }`

- [ ] **Step 1: Create `ui/src/api/rankings.ts`**

```typescript
import type { Position, PlayerDetail, Ranking, RankingFilters, Tier, TierLabel } from '../types'
import { apiFetch, SEASON, MODEL_VERSION } from './client'

interface BackendRanking {
  rank: number
  gsis_id: string
  name: string
  position: string
  team: string | null
  vor: number | null
  vor_rank: number | null
  adp: number | null
  adp_delta: number | null
  tier: number | null
  mean_projection: number | null
  sim_mean: number | null
  sim_p10: number | null
  sim_p90: number | null
  sim_boom_prob: number | null
  sim_bust_prob: number | null
  avail_mean: number | null
}

export interface BackendScarcity {
  position: string
  total_players: number
  top_tier_count: number
  vor_dropoff: number | null
}

const TIER_LABELS: Record<number, TierLabel> = {
  1: 'TIER 1 — ELITE',
  2: 'TIER 2 — HIGH-END',
  3: 'TIER 3 — SOLID STARTER',
  4: 'TIER 4 — STREAMER',
  5: 'TIER 5 — DEEP BENCH',
}

function clampTier(t: number | null): Tier['number'] {
  return Math.min(5, Math.max(1, t ?? 5)) as Tier['number']
}

export function toRanking(r: BackendRanking, positionRank: number): Ranking {
  const tier = clampTier(r.tier)
  const player: PlayerDetail = {
    id: r.gsis_id,
    name: r.name,
    position: r.position as Position,
    team: r.team ?? '',
    byeWeek: 0,
    age: 0,
    experience: 0,
    imageUrl: null,
    injuryStatus: null,
    injuryNote: null,
    projection: {
      mean: r.mean_projection ?? 0,
      median: r.sim_mean ?? 0,
      floor: r.sim_p10 ?? 0,
      ceiling: r.sim_p90 ?? 0,
      p10: r.sim_p10 ?? 0,
      p25: 0,
      p75: 0,
      p90: r.sim_p90 ?? 0,
      stdDev: 0,
      boomProbability: r.sim_boom_prob ?? 0,
      bustProbability: r.sim_bust_prob ?? 0,
      gamesPlayed: 17,
    },
    opportunity: {
      targetShare: null,
      routeParticipation: null,
      snapShare: 0,
      rushShare: null,
      redZoneUsage: null,
      targets: null,
      carries: null,
    },
    efficiency: {
      yardsPerRouteRun: null,
      epaPerPlay: null,
      successRate: null,
      explosivePlayRate: null,
      yardsPerCarry: null,
      yardsPerTarget: null,
      catchRate: null,
      completionPct: null,
      yardsPerAttempt: null,
    },
    modelConfidence: r.avail_mean ?? 0,
    breakoutProbability: r.sim_boom_prob ?? 0,
    bustRisk: r.sim_bust_prob ?? 0,
    rookieYear: false,
    collegeTeam: null,
    depthChartPosition: 1,
  }
  return {
    rank: r.rank,
    positionRank,
    player,
    tier: { number: tier, label: TIER_LABELS[tier] },
    projection: r.mean_projection ?? 0,
    vor: r.vor ?? 0,
    adp: r.adp ?? 999,
    modelRank: r.vor_rank ?? 999,
    adpDelta: Math.round(r.adp_delta ?? 0),
    replacementLevel: 0,
    floor: r.sim_p10 ?? 0,
    ceiling: r.sim_p90 ?? 0,
    targetShare: null,
    rushShare: null,
    snapPct: null,
    routePct: null,
    redZoneUsage: null,
    tdProjection: 0,
    gamesPlayed: 17,
    modelConfidence: r.avail_mean ?? 0,
  }
}

export async function fetchRankings(filters: RankingFilters): Promise<Ranking[]> {
  const params = new URLSearchParams({
    season: String(SEASON),
    model_version: MODEL_VERSION,
    sort: 'vor_rank',
  })
  if (filters.position !== 'ALL') params.set('position', filters.position)
  const data = await apiFetch<BackendRanking[]>(`/rankings?${params}`)
  const posCounters: Record<string, number> = {}
  return data.map(r => {
    posCounters[r.position] = (posCounters[r.position] ?? 0) + 1
    return toRanking(r, posCounters[r.position])
  })
}

export async function fetchScarcity(): Promise<BackendScarcity[]> {
  const params = new URLSearchParams({ season: String(SEASON), model_version: MODEL_VERSION })
  return apiFetch<BackendScarcity[]>(`/scarcity?${params}`)
}
```

- [ ] **Step 2: Update `ui/src/hooks/useRankings.ts`**

Replace the entire file:

```typescript
import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import type { Ranking, RankingFilters } from '../types'
import { fetchRankings } from '../api/rankings'

export function useRankings(filters: RankingFilters) {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['rankings', filters.position],
    queryFn: () => fetchRankings(filters),
    staleTime: 60_000,
  })

  const rankings = useMemo(() => {
    const all = data ?? []
    return all.filter(r => {
      if (filters.search) {
        const q = filters.search.toLowerCase()
        if (!r.player.name.toLowerCase().includes(q) &&
            !r.player.team.toLowerCase().includes(q)) return false
      }
      if (filters.tierFilter !== null && r.tier.number !== filters.tierFilter) return false
      return true
    })
  }, [data, filters.search, filters.tierFilter])

  return { rankings, isLoading, error, refetch }
}
```

- [ ] **Step 3: Verify TypeScript compiles**

Run: `cd ui && npx tsc --noEmit`
Expected: 0 errors (there will still be unused-import errors in other files that still import `MOCK_RANKINGS` — those are fixed in later tasks; ignore them for now)

- [ ] **Step 4: Manual smoke test**

In terminal 1: `make api`
In terminal 2: `cd ui && npm run dev`
Open `http://localhost:5173/rankings` — rankings list should show real players from the DB.

- [ ] **Step 5: Commit**

```bash
git add ui/src/api/rankings.ts ui/src/hooks/useRankings.ts
git commit -m "feat: rankings API module + live useRankings hook"
```

---

### Task 3: Players API Module + All Player Consumers

**Files:**
- Create: `ui/src/api/players.ts`
- Modify: `ui/src/hooks/usePlayer.ts`
- Modify: `ui/src/hooks/useDraftState.ts`
- Modify: `ui/src/pages/Players.tsx`
- Modify: `ui/src/components/draft/AvailablePlayers.tsx`
- Modify: `ui/src/components/roster/RosterBuilder.tsx`
- Modify: `ui/src/components/roster/RosterProjection.tsx`
- Modify: `ui/src/state/mockDraftSimulator.ts`

**Interfaces:**
- Consumes: `apiFetch`, `SEASON`, `MODEL_VERSION` from `../api/client`; `useRankings` from `../hooks/useRankings`
- Produces:
  - `fetchPlayers(filters?) → Promise<PlayerDetail[]>` — GET /players
  - `fetchPlayer(id) → Promise<PlayerDetail>` — GET /players/{id}

- [ ] **Step 1: Create `ui/src/api/players.ts`**

```typescript
import type { Position, PlayerDetail } from '../types'
import { apiFetch, SEASON, MODEL_VERSION } from './client'

interface BackendPlayer {
  gsis_id: string
  name: string
  position: string
  team: string | null
  season: number
  model_version: string
  mean_projection: number | null
  vor: number | null
  vor_rank: number | null
  tier: number | null
  adp_delta: number | null
  adp: number | null
  sim_mean: number | null
  sim_p10: number | null
  sim_p90: number | null
  sim_boom_prob: number | null
  sim_bust_prob: number | null
  avail_mean: number | null
}

function toPlayerDetail(p: BackendPlayer): PlayerDetail {
  return {
    id: p.gsis_id,
    name: p.name,
    position: p.position as Position,
    team: p.team ?? '',
    byeWeek: 0,
    age: 0,
    experience: 0,
    imageUrl: null,
    injuryStatus: null,
    injuryNote: null,
    projection: {
      mean: p.mean_projection ?? 0,
      median: p.sim_mean ?? 0,
      floor: p.sim_p10 ?? 0,
      ceiling: p.sim_p90 ?? 0,
      p10: p.sim_p10 ?? 0,
      p25: 0,
      p75: 0,
      p90: p.sim_p90 ?? 0,
      stdDev: 0,
      boomProbability: p.sim_boom_prob ?? 0,
      bustProbability: p.sim_bust_prob ?? 0,
      gamesPlayed: 17,
    },
    opportunity: {
      targetShare: null,
      routeParticipation: null,
      snapShare: 0,
      rushShare: null,
      redZoneUsage: null,
      targets: null,
      carries: null,
    },
    efficiency: {
      yardsPerRouteRun: null,
      epaPerPlay: null,
      successRate: null,
      explosivePlayRate: null,
      yardsPerCarry: null,
      yardsPerTarget: null,
      catchRate: null,
      completionPct: null,
      yardsPerAttempt: null,
    },
    modelConfidence: p.avail_mean ?? 0,
    breakoutProbability: p.sim_boom_prob ?? 0,
    bustRisk: p.sim_bust_prob ?? 0,
    rookieYear: false,
    collegeTeam: null,
    depthChartPosition: 1,
  }
}

export async function fetchPlayers(filters?: { position?: string }): Promise<PlayerDetail[]> {
  const params = new URLSearchParams({ season: String(SEASON), model_version: MODEL_VERSION })
  if (filters?.position) params.set('position', filters.position)
  const data = await apiFetch<BackendPlayer[]>(`/players?${params}`)
  return data.map(toPlayerDetail)
}

export async function fetchPlayer(id: string): Promise<PlayerDetail> {
  const params = new URLSearchParams({ season: String(SEASON), model_version: MODEL_VERSION })
  const data = await apiFetch<BackendPlayer>(`/players/${id}?${params}`)
  return toPlayerDetail(data)
}
```

- [ ] **Step 2: Update `ui/src/hooks/usePlayer.ts`**

Replace the entire file:

```typescript
import { useQuery } from '@tanstack/react-query'
import type { PlayerDetail } from '../types'
import { fetchPlayer } from '../api/players'

export function usePlayer(id: string | null) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['player', id],
    queryFn: () => fetchPlayer(id!),
    enabled: id !== null,
    staleTime: 60_000,
  })
  return { player: data as PlayerDetail | undefined, isLoading, error }
}
```

- [ ] **Step 3: Update `ui/src/hooks/useDraftState.ts`**

Replace the entire file:

```typescript
import { useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useDraftContext, picksUntilNextTurn } from '../state/draftState'
import { fetchPlayers } from '../api/players'
import type { PlayerDetail, DraftConfig, DraftedPick } from '../types'

export function useDraftState() {
  const { state, dispatch } = useDraftContext()

  const picksUntil = picksUntilNextTurn(state)
  const isUserTurn = picksUntil === 0

  const userPicks: DraftedPick[] = state.picks.filter(p => p.isUserPick)

  const { data: allPlayers = [] } = useQuery({
    queryKey: ['players'],
    queryFn: () => fetchPlayers(),
    staleTime: 300_000,
  })

  const draftedPlayerIds = new Set(state.picks.map(p => p.player.id))
  const availablePlayers: PlayerDetail[] = allPlayers.filter(p => !draftedPlayerIds.has(p.id))

  const draftPlayer = useCallback(
    (player: PlayerDetail, isUserPick?: boolean) =>
      dispatch({ type: 'DRAFT_PLAYER', payload: player, ...(isUserPick !== undefined && { isUserPick }) }),
    [dispatch]
  )

  const undoLastPick = useCallback(
    () => dispatch({ type: 'UNDO_LAST_PICK' }),
    [dispatch]
  )

  const resetDraft = useCallback(
    () => dispatch({ type: 'RESET_DRAFT' }),
    [dispatch]
  )

  const updateConfig = useCallback(
    (config: Partial<DraftConfig>) => {
      dispatch({ type: 'UPDATE_CONFIG', config: { ...state.config, ...config } })
    },
    [dispatch, state.config]
  )

  return {
    state,
    draftPlayer,
    undoLastPick,
    resetDraft,
    updateConfig,
    isUserTurn,
    picksUntil,
    availablePlayers,
    userPicks,
  }
}
```

- [ ] **Step 4: Update `ui/src/pages/Players.tsx`**

Replace the entire file:

```typescript
import { useState, useMemo, useEffect } from 'react'
import type { Ranking } from '../types'
import { useRankings } from '../hooks/useRankings'
import { PlayerSearch, PlayerListRow, ProjectionChart, ComparablePlayers } from '../components/players'
import { PositionBadge } from '../components/ui/Badge'

export default function Players() {
  const [search, setSearch] = useState('')
  const [position, setPosition] = useState('ALL')
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const { rankings, isLoading, error, refetch } = useRankings({
    position: position as 'ALL' | 'QB' | 'RB' | 'WR' | 'TE',
    search,
    format: 'ppr',
    draftType: 'redraft',
    year: 2026,
    tierFilter: null,
  })

  useEffect(() => {
    if (rankings.length > 0 && selectedId === null) {
      setSelectedId(rankings[0].player.id)
    }
  }, [rankings, selectedId])

  const selectedRanking: Ranking | undefined = useMemo(
    () => rankings.find(r => r.player.id === selectedId),
    [rankings, selectedId]
  )

  if (error) {
    return (
      <div className="flex h-full items-center justify-center flex-col gap-3 text-text-secondary">
        <p>Failed to load players</p>
        <button onClick={() => refetch()} className="text-sm text-accent underline">Retry</button>
      </div>
    )
  }

  return (
    <div className="flex h-full overflow-hidden">
      {/* Left: search + list */}
      <div className="w-72 flex-shrink-0 flex flex-col border-r border-border bg-bg-secondary overflow-hidden">
        <div className="p-3 border-b border-border">
          <PlayerSearch
            search={search}
            position={position}
            onSearchChange={setSearch}
            onPositionChange={setPosition}
          />
        </div>
        <div className="flex-1 overflow-y-auto">
          {isLoading && (
            <p className="text-sm text-text-muted p-4 text-center">Loading…</p>
          )}
          {rankings.map(r => (
            <PlayerListRow
              key={r.player.id}
              ranking={r}
              selected={r.player.id === selectedId}
              onClick={() => setSelectedId(r.player.id)}
            />
          ))}
          {!isLoading && rankings.length === 0 && (
            <p className="text-sm text-text-muted p-4 text-center">No players found</p>
          )}
        </div>
      </div>

      {/* Right: player detail */}
      {selectedRanking ? (
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          <div className="flex items-start gap-4">
            {selectedRanking.player.imageUrl && (
              <img
                src={selectedRanking.player.imageUrl}
                alt=""
                className="w-16 h-16 rounded-full object-cover bg-bg-elevated flex-shrink-0"
                onError={e => { (e.target as HTMLImageElement).style.display = 'none' }}
              />
            )}
            <div>
              <h1 className="text-2xl font-bold text-text-primary">{selectedRanking.player.name}</h1>
              <div className="flex items-center gap-2 mt-1">
                <PositionBadge position={selectedRanking.player.position} />
                <span className="text-sm text-text-secondary">{selectedRanking.player.team}</span>
                {selectedRanking.player.byeWeek > 0 && (
                  <span className="text-sm text-text-muted">· Bye {selectedRanking.player.byeWeek}</span>
                )}
                {selectedRanking.player.age > 0 && (
                  <span className="text-sm text-text-muted">· Age {selectedRanking.player.age}</span>
                )}
              </div>
            </div>
            <div className="ml-auto text-right">
              <div className="text-2xl font-bold text-text-primary tabular-nums">
                {selectedRanking.projection.toFixed(0)}
              </div>
              <div className="text-xs text-text-secondary">Projected pts</div>
              <div className="text-xs text-accent tabular-nums mt-0.5">
                VOR {selectedRanking.vor.toFixed(0)}
              </div>
            </div>
          </div>

          <div className="bg-bg-card border border-border rounded-xl p-4">
            <ProjectionChart player={selectedRanking.player} />
          </div>

          <div className="grid grid-cols-3 gap-3">
            {[
              { label: 'Model Confidence', value: `${Math.round(selectedRanking.player.modelConfidence * 100)}%` },
              { label: 'Breakout Prob', value: `${Math.round(selectedRanking.player.breakoutProbability * 100)}%` },
              { label: 'Bust Risk', value: `${Math.round(selectedRanking.player.bustRisk * 100)}%` },
              { label: 'ADP', value: selectedRanking.adp },
              { label: 'Model Rank', value: selectedRanking.modelRank },
              { label: 'ADP Delta', value: selectedRanking.adpDelta < 0 ? `+${Math.abs(selectedRanking.adpDelta)}` : `${selectedRanking.adpDelta}` },
            ].map(({ label, value }) => (
              <div key={label} className="bg-bg-card border border-border rounded-lg p-3 text-center">
                <div className="text-xs text-text-secondary mb-1">{label}</div>
                <div className="text-lg font-bold text-text-primary">{value}</div>
              </div>
            ))}
          </div>

          <div className="bg-bg-card border border-border rounded-xl p-4">
            <ComparablePlayers ranking={selectedRanking} allRankings={rankings} />
          </div>
        </div>
      ) : (
        <div className="flex-1 flex items-center justify-center text-text-muted text-sm">
          {isLoading ? 'Loading…' : 'Select a player'}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 5: Update `ui/src/components/draft/AvailablePlayers.tsx`**

Replace only the import block and the `available` useMemo — keep all JSX identical. Specifically, replace:

```typescript
import { MOCK_RANKINGS } from '../../data'
```

with:

```typescript
import { useRankings } from '../../hooks/useRankings'
```

And replace the `available` useMemo block (the one that starts `return MOCK_RANKINGS`) plus add the `useRankings` call inside the component:

After `const { availablePlayers, draftPlayer } = useDraftState()`, add:

```typescript
  const { rankings } = useRankings({
    position: 'ALL',
    search: '',
    format: 'ppr',
    draftType: 'redraft',
    year: 2026,
    tierFilter: null,
  })
```

Then change the `available` useMemo to:

```typescript
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
  }, [rankings, availableIds, posFilter, search])
```

- [ ] **Step 6: Update `ui/src/components/roster/RosterBuilder.tsx`**

Replace:

```typescript
import { MOCK_RANKINGS } from '../../data'
```

with:

```typescript
import { useRankings } from '../../hooks/useRankings'
```

Inside the `RosterBuilder` component, after the `useState('')` call, add:

```typescript
  const { rankings } = useRankings({
    position: 'ALL',
    search: '',
    format: 'ppr',
    draftType: 'redraft',
    year: 2026,
    tierFilter: null,
  })
```

Change the `suggestions` useMemo to use `rankings` instead of `MOCK_RANKINGS`:

```typescript
  const suggestions = useMemo(() => {
    if (!search.trim()) return []
    const rosterIds = new Set(roster.map(p => p.id))
    const q = search.toLowerCase()
    return rankings
      .filter(r => !rosterIds.has(r.player.id) &&
        (r.player.name.toLowerCase().includes(q) || r.player.team.toLowerCase().includes(q))
      )
      .slice(0, 8)
  }, [search, roster, rankings])
```

- [ ] **Step 7: Update `ui/src/components/roster/RosterProjection.tsx`**

Remove the MOCK_RANKINGS import and `rankingMap` useMemo entirely. Use `player.projection.mean` directly.

Replace the entire file:

```typescript
import type { PlayerDetail } from '../../types'

interface Config { QB: number; RB: number; WR: number; TE: number; FLEX: number; BENCH: number }
interface Props { roster: PlayerDetail[]; rosterConfig: Config }

const FLEX_ELIGIBLE: PlayerDetail['position'][] = ['RB', 'WR', 'TE']

function fillStarters(roster: PlayerDetail[], config: Config): PlayerDetail[] {
  const pool = [...roster]
  const starters: PlayerDetail[] = []
  const slots: Array<{ pos: PlayerDetail['position'] | 'FLEX'; count: number }> = [
    { pos: 'QB', count: config.QB },
    { pos: 'RB', count: config.RB },
    { pos: 'WR', count: config.WR },
    { pos: 'TE', count: config.TE },
    { pos: 'FLEX', count: config.FLEX },
  ]
  for (const { pos, count } of slots) {
    for (let i = 0; i < count; i++) {
      const idx = pool.findIndex(p =>
        pos === 'FLEX' ? FLEX_ELIGIBLE.includes(p.position) : p.position === pos
      )
      if (idx === -1) break
      starters.push(pool.splice(idx, 1)[0])
    }
  }
  return starters
}

export function RosterProjection({ roster, rosterConfig }: Props) {
  const starters = fillStarters(roster, rosterConfig)

  const mean = starters.reduce((s, p) => s + p.projection.mean, 0)
  const floor = mean * 0.75
  const ceiling = mean * 1.35

  if (starters.length === 0) {
    return (
      <div className="text-sm text-text-muted text-center py-6">
        Add starters to see projections
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-3">
        {[
          { label: 'Floor',   value: floor.toFixed(0),   color: 'text-text-secondary' },
          { label: 'Mean',    value: mean.toFixed(0),    color: 'text-text-primary' },
          { label: 'Ceiling', value: ceiling.toFixed(0), color: 'text-accent' },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-bg-card border border-border rounded-lg p-3 text-center">
            <div className="text-xs text-text-muted mb-1">{label}</div>
            <div className={`text-2xl font-bold tabular-nums ${color}`}>{value}</div>
            <div className="text-xs text-text-muted">pts</div>
          </div>
        ))}
      </div>
      <div className="space-y-1">
        <div className="text-xs font-bold tracking-widest text-text-muted uppercase mb-2">Starters</div>
        {starters.map(p => (
          <div key={p.id} className="flex items-center gap-2 bg-bg-elevated rounded-lg px-3 py-2">
            <span className="text-xs font-mono text-text-muted w-6">{p.position}</span>
            <span className="text-sm text-text-primary flex-1 truncate">{p.name}</span>
            <span className="text-xs text-text-secondary tabular-nums">{p.projection.mean.toFixed(1)} pts</span>
          </div>
        ))}
      </div>
    </div>
  )
}
```

- [ ] **Step 8: Update `ui/src/state/mockDraftSimulator.ts`**

Replace the entire file:

```typescript
import { useState, useEffect, useCallback } from 'react'
import type { PlayerDetail, Ranking } from '../types'
import { useDraftState } from '../hooks/useDraftState'
import { useRankings } from '../hooks/useRankings'

export function bestAvailablePlayer(draftedIds: string[], rankings: Ranking[]): PlayerDetail | null {
  const pick = rankings.find(r => !draftedIds.includes(r.player.id))
  return pick?.player ?? null
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
    const draftedIds = state.picks.map(p => p.player.id)
    const pick = bestAvailablePlayer(draftedIds, rankings)
    if (!pick) {
      setAutoAdvancing(false)
      return
    }
    const timer = setTimeout(() => draftPlayer(pick), 150)
    return () => clearTimeout(timer)
  }, [autoAdvancing, isUserTurn, isDraftComplete, state.picks, draftPlayer, rankings])

  const startAutoAdvance = useCallback(() => setAutoAdvancing(true), [])
  const stopAutoAdvance = useCallback(() => setAutoAdvancing(false), [])

  return { autoAdvancing, startAutoAdvance, stopAutoAdvance }
}
```

- [ ] **Step 9: Verify TypeScript compiles**

Run: `cd ui && npx tsc --noEmit`
Expected: 0 errors (files still importing from `../../data` will error — those are fixed in Tasks 4–6)

Note: if there are remaining errors only from files that still import `MOCK_RANKINGS`/`MOCK_PLAYERS`, they are expected — proceed.

- [ ] **Step 10: Commit**

```bash
git add ui/src/api/players.ts ui/src/hooks/usePlayer.ts ui/src/hooks/useDraftState.ts \
  ui/src/pages/Players.tsx ui/src/components/draft/AvailablePlayers.tsx \
  ui/src/components/roster/RosterBuilder.tsx ui/src/components/roster/RosterProjection.tsx \
  ui/src/state/mockDraftSimulator.ts
git commit -m "feat: players API module + wire all player consumers to live data"
```

---

### Task 4: League Settings API + Hook

**Files:**
- Create: `ui/src/api/league.ts`
- Modify: `ui/src/hooks/useLeagueSettings.ts`

**Interfaces:**
- Consumes: `apiFetch` from `./client`; `LeagueSettings`, `DEFAULT_LEAGUE_SETTINGS` from `../types`
- Produces:
  - `fetchLeagueSettings(): Promise<LeagueSettings>` — GET /league/settings
  - `saveLeagueSettings(settings: LeagueSettings): Promise<void>` — POST /league/settings
  - Updated `useLeagueSettings()` returns `{ settings, update, reset, isLoading, isSaving }`

- [ ] **Step 1: Create `ui/src/api/league.ts`**

```typescript
import type { LeagueSettings, ScoringFormat } from '../types'
import { DEFAULT_LEAGUE_SETTINGS } from '../types'
import { apiFetch } from './client'

interface BackendLeagueSettings {
  teams: number
  scoring: string
  roster_config: Record<string, number>
}

function fromBackend(s: BackendLeagueSettings): LeagueSettings {
  return {
    teams: s.teams,
    format: (s.scoring === 'half' ? 'half_ppr' : s.scoring) as ScoringFormat,
    rosterConfig: {
      QB: s.roster_config['QB'] ?? 1,
      RB: s.roster_config['RB'] ?? 2,
      WR: s.roster_config['WR'] ?? 2,
      TE: s.roster_config['TE'] ?? 1,
      FLEX: s.roster_config['FLEX'] ?? 1,
      BENCH: DEFAULT_LEAGUE_SETTINGS.rosterConfig.BENCH,
    },
  }
}

function toBackend(s: LeagueSettings): BackendLeagueSettings {
  return {
    teams: s.teams,
    scoring: s.format === 'half_ppr' ? 'half' : s.format,
    roster_config: {
      QB: s.rosterConfig.QB,
      RB: s.rosterConfig.RB,
      WR: s.rosterConfig.WR,
      TE: s.rosterConfig.TE,
      FLEX: s.rosterConfig.FLEX,
    },
  }
}

export async function fetchLeagueSettings(): Promise<LeagueSettings> {
  return apiFetch<BackendLeagueSettings>('/league/settings').then(fromBackend)
}

export async function saveLeagueSettings(settings: LeagueSettings): Promise<void> {
  await apiFetch('/league/settings', {
    method: 'POST',
    body: JSON.stringify(toBackend(settings)),
  })
}
```

- [ ] **Step 2: Update `ui/src/hooks/useLeagueSettings.ts`**

Replace the entire file:

```typescript
import { useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import type { LeagueSettings } from '../types'
import { DEFAULT_LEAGUE_SETTINGS } from '../types'
import { fetchLeagueSettings, saveLeagueSettings } from '../api/league'

export function useLeagueSettings() {
  const queryClient = useQueryClient()

  const { data: settings = DEFAULT_LEAGUE_SETTINGS, isLoading } = useQuery({
    queryKey: ['leagueSettings'],
    queryFn: fetchLeagueSettings,
    staleTime: 300_000,
  })

  const { mutate: saveMutation, isPending: isSaving } = useMutation({
    mutationFn: saveLeagueSettings,
    onSuccess: (_data, variables) => {
      queryClient.setQueryData(['leagueSettings'], variables)
    },
  })

  const update = useCallback((patch: Partial<LeagueSettings>) => {
    const next = { ...settings, ...patch }
    saveMutation(next)
  }, [settings, saveMutation])

  const reset = useCallback(() => {
    saveMutation(DEFAULT_LEAGUE_SETTINGS)
  }, [saveMutation])

  return { settings, update, reset, isLoading, isSaving }
}
```

- [ ] **Step 3: Verify TypeScript compiles**

Run: `cd ui && npx tsc --noEmit`
Expected: 0 errors in the modified files

- [ ] **Step 4: Manual smoke test**

With the API running (`make api`), open `http://localhost:5173/settings`. Change a setting — it should POST to `/league/settings`. Refresh the page — the setting should persist (GET from backend, not localStorage).

- [ ] **Step 5: Commit**

```bash
git add ui/src/api/league.ts ui/src/hooks/useLeagueSettings.ts
git commit -m "feat: league settings API module + live useLeagueSettings hook"
```

---

### Task 5: Draft Recommendation API + Hook + Consumers

**Files:**
- Create: `ui/src/api/draft.ts`
- Create: `ui/src/hooks/useRecommendation.ts`
- Modify: `ui/src/hooks/index.ts`
- Modify: `ui/src/components/draft/RecommendationPanel.tsx`
- Modify: `ui/src/components/draft/MyRoster.tsx`
- Modify: `ui/src/components/draft/MayNotMakeItBack.tsx`

**Interfaces:**
- Consumes: `apiFetch`, `SEASON`, `MODEL_VERSION` from `./client`; `LiveDraftState` from `../types`
- Produces:
  - `fetchRecommendation(state: LiveDraftState): Promise<RecommendationState>`
  - `saveSession(sessionId: string, state: LiveDraftState): Promise<void>`
  - `loadSession(sessionId: string): Promise<LiveDraftState | null>`
  - `useRecommendation(state: LiveDraftState): RecommendationState | null`

**Session persistence note:** The backend `SessionOut` stores only `drafted_ids` and `league_settings`, which is insufficient to reconstruct `LiveDraftState` (pick order and team attribution are lost). `saveSession` sends state to the backend after each pick. `loadSession` always returns `null` — full restore is deferred to a future plan when the backend can store complete pick history.

- [ ] **Step 1: Create `ui/src/api/draft.ts`**

```typescript
import type {
  Position, PlayerDetail, LiveDraftState,
  RecommendationState, FutureAvailability, Tier, TierLabel,
} from '../types'
import { apiFetch, SEASON, MODEL_VERSION } from './client'

interface BackendPlayerProjection {
  gsis_id: string
  name: string
  position: string
  team: string
  vor: number
  vor_rank: number
  sim_mean: number
  sim_p10: number
  sim_p90: number
  adp: number
  tier: number | null
  sim_boom_prob: number
  sim_bust_prob: number
}

interface BackendRecommendation {
  player: BackendPlayerProjection
  draft_score: number
  roster_fit: number
  positional_urgency: number
  future_availability_pct: number
  explanation: string[]
}

interface BackendRecommendationState {
  top_pick: BackendRecommendation
  alternatives: BackendRecommendation[]
  positional_needs: string[]
  may_not_make_it_back: BackendPlayerProjection[]
  board_state: { current_pick: number; round: number; picks_until_next: number }
}

const TIER_LABELS: Record<number, TierLabel> = {
  1: 'TIER 1 — ELITE',
  2: 'TIER 2 — HIGH-END',
  3: 'TIER 3 — SOLID STARTER',
  4: 'TIER 4 — STREAMER',
  5: 'TIER 5 — DEEP BENCH',
}

const POSITIONS: Position[] = ['QB', 'RB', 'WR', 'TE']

function clampTier(t: number | null): Tier['number'] {
  return Math.min(5, Math.max(1, t ?? 5)) as Tier['number']
}

function toPlayerDetail(p: BackendPlayerProjection): PlayerDetail {
  return {
    id: p.gsis_id,
    name: p.name,
    position: p.position as Position,
    team: p.team,
    byeWeek: 0,
    age: 0,
    experience: 0,
    imageUrl: null,
    injuryStatus: null,
    injuryNote: null,
    projection: {
      mean: p.sim_mean,
      median: p.sim_mean,
      floor: p.sim_p10,
      ceiling: p.sim_p90,
      p10: p.sim_p10,
      p25: 0,
      p75: 0,
      p90: p.sim_p90,
      stdDev: 0,
      boomProbability: p.sim_boom_prob,
      bustProbability: p.sim_bust_prob,
      gamesPlayed: 17,
    },
    opportunity: {
      targetShare: null,
      routeParticipation: null,
      snapShare: 0,
      rushShare: null,
      redZoneUsage: null,
      targets: null,
      carries: null,
    },
    efficiency: {
      yardsPerRouteRun: null,
      epaPerPlay: null,
      successRate: null,
      explosivePlayRate: null,
      yardsPerCarry: null,
      yardsPerTarget: null,
      catchRate: null,
      completionPct: null,
      yardsPerAttempt: null,
    },
    modelConfidence: 0,
    breakoutProbability: p.sim_boom_prob,
    bustRisk: p.sim_bust_prob,
    rookieYear: false,
    collegeTeam: null,
    depthChartPosition: 1,
  }
}

function mapRecommendation(r: BackendRecommendation): RecommendationState['topPick'] {
  const p = r.player
  const tier = clampTier(p.tier)
  const prob = r.future_availability_pct
  return {
    rank: p.vor_rank,
    positionRank: 0,
    player: toPlayerDetail(p),
    tier: { number: tier, label: TIER_LABELS[tier] },
    projection: p.sim_mean,
    vor: p.vor,
    adp: p.adp,
    modelRank: p.vor_rank,
    adpDelta: 0,
    replacementLevel: 0,
    floor: p.sim_p10,
    ceiling: p.sim_p90,
    targetShare: null,
    rushShare: null,
    snapPct: null,
    routePct: null,
    redZoneUsage: null,
    tdProjection: 0,
    gamesPlayed: 17,
    modelConfidence: 0,
    draftScore: r.draft_score,
    rosterFit: r.roster_fit,
    futureAvailability: {
      playerId: p.gsis_id,
      probability: prob,
      label: prob > 0.7 ? 'urgent' : prob > 0.3 ? 'monitor' : 'safe',
    },
    explanation: r.explanation.map(s => ({
      factor: '',
      detail: s,
      weight: 'secondary' as const,
    })),
  }
}

function toDraftStateIn(state: LiveDraftState) {
  const userRoster: Record<string, string[]> = { QB: [], RB: [], WR: [], TE: [], FLEX: [] }
  for (const pick of state.picks.filter(p => p.isUserPick)) {
    const pos = pick.player.position as string
    if (pos in userRoster) userRoster[pos].push(pick.player.id)
  }
  return {
    season: SEASON,
    model_version: MODEL_VERSION,
    league_settings: {
      teams: state.config.teams,
      scoring: state.config.scoringFormat === 'half_ppr' ? 'half' : state.config.scoringFormat,
      roster_config: {
        QB: state.config.rosterConfig.QB,
        RB: state.config.rosterConfig.RB,
        WR: state.config.rosterConfig.WR,
        TE: state.config.rosterConfig.TE,
        FLEX: state.config.rosterConfig.FLEX,
      },
    },
    current_pick: state.currentOverallPick,
    total_picks: state.config.teams * state.config.totalRounds,
    user_pick_position: state.config.userPickPosition,
    drafted_ids: state.picks.map(p => p.player.id),
    user_roster: userRoster,
  }
}

export async function fetchRecommendation(state: LiveDraftState): Promise<RecommendationState> {
  const data = await apiFetch<BackendRecommendationState>('/draft/recommend', {
    method: 'POST',
    body: JSON.stringify(toDraftStateIn(state)),
  })

  const positionalNeeds = Object.fromEntries(
    POSITIONS.map(pos => {
      const idx = data.positional_needs.indexOf(pos)
      return [pos, idx === -1 ? 0 : 1 - idx / Math.max(1, data.positional_needs.length - 1)]
    })
  ) as Record<Position, number>

  const mayNotMakeItBack: FutureAvailability[] = data.may_not_make_it_back.map(p => ({
    playerId: p.gsis_id,
    probability: 0.75,
    label: 'urgent' as const,
  }))

  return {
    topPick: mapRecommendation(data.top_pick),
    alternatives: data.alternatives.map(mapRecommendation),
    positionalNeeds,
    scarcity: [],
    mayNotMakeItBack,
  }
}

export async function saveSession(sessionId: string, state: LiveDraftState): Promise<void> {
  await apiFetch('/draft/session', {
    method: 'POST',
    body: JSON.stringify({ session_id: sessionId, state: toDraftStateIn(state) }),
  })
}

// Backend SessionOut cannot reconstruct full LiveDraftState (pick order/team lost).
// Save is supported; restore is deferred to a future plan.
export async function loadSession(_sessionId: string): Promise<LiveDraftState | null> {
  return null
}
```

- [ ] **Step 2: Create `ui/src/hooks/useRecommendation.ts`**

```typescript
import { useRef, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import type { LiveDraftState, RecommendationState } from '../types'
import { picksUntilNextTurn } from '../state/draftState'
import { fetchRecommendation, saveSession } from '../api/draft'

export interface UseRecommendationResult {
  recommendation: RecommendationState | null
  error: Error | null
}

export function useRecommendation(state: LiveDraftState): UseRecommendationResult {
  const isUserTurn = picksUntilNextTurn(state) === 0
  const sessionIdRef = useRef<string | null>(null)

  useEffect(() => {
    const stored = sessionStorage.getItem('tay-draft-session-id')
    if (stored) {
      sessionIdRef.current = stored
    } else {
      const id = crypto.randomUUID()
      sessionStorage.setItem('tay-draft-session-id', id)
      sessionIdRef.current = id
    }
  }, [])

  // Fire-and-forget session save after each pick
  useEffect(() => {
    const sid = sessionIdRef.current
    if (!sid || state.picks.length === 0) return
    saveSession(sid, state).catch(() => { /* ignore */ })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.picks.length])

  const { data, error } = useQuery({
    queryKey: ['recommendation', state.currentOverallPick, state.picks.length],
    queryFn: () => fetchRecommendation(state),
    enabled: isUserTurn,
    staleTime: 0,
    retry: false,
  })

  return { recommendation: data ?? null, error: error as Error | null }
}
```

- [ ] **Step 3: Update `ui/src/hooks/index.ts`**

Replace:

```typescript
export { useMockRecommendation } from './useMockRecommendation'
```

with:

```typescript
export { useRecommendation } from './useRecommendation'
```

- [ ] **Step 4: Update `ui/src/components/draft/RecommendationPanel.tsx`**

Change the import of `useMockRecommendation` from:

```typescript
import { useMockRecommendation } from '../../hooks/useMockRecommendation'
```

to:

```typescript
import { useRecommendation } from '../../hooks/useRecommendation'
import { useRankings } from '../../hooks/useRankings'
import { ApiError } from '../../api/client'
```

Change the hook call from:

```typescript
  const reco = useMockRecommendation(state)
```

to:

```typescript
  const { recommendation: reco, error: recoError } = useRecommendation(state)
  const { rankings } = useRankings({ position: 'ALL', search: '', format: 'ppr', draftType: 'redraft', year: 2026, tierFilter: null })
```

After the `isDraftComplete` check (before the `if (!reco)` check), add a 422 error guard:

```tsx
  if (recoError instanceof ApiError && recoError.status === 422) {
    return (
      <div className="flex-1 flex items-center justify-center text-text-muted">
        <div className="text-center">
          <div className="text-lg font-bold mb-1">Draft Pool Exhausted</div>
          <div className="text-sm">No available players to recommend.</div>
        </div>
      </div>
    )
  }
```

Find the `<MayNotMakeItBack ... />` JSX and add the `allRankings` prop:

```tsx
<MayNotMakeItBack items={reco.mayNotMakeItBack} allRankings={rankings} />
```

- [ ] **Step 5: Update `ui/src/components/draft/MyRoster.tsx`**

Change the import from `useMockRecommendation` to `useRecommendation`:

```typescript
import { useRecommendation } from '../../hooks/useRecommendation'
```

Change:

```typescript
  const reco = useMockRecommendation(state)
```

to:

```typescript
  const { recommendation: reco } = useRecommendation(state)
```

- [ ] **Step 6: Update `ui/src/components/draft/MayNotMakeItBack.tsx`**

Remove the `MOCK_RANKINGS` import. Update the `withPlayers` lookup to use `allRankings` prop:

Replace the entire file:

```typescript
import { AlertCircle } from 'lucide-react'
import clsx from 'clsx'
import type { FutureAvailability, Ranking } from '../../types'
import { PositionBadge } from '../ui/Badge'

interface Props {
  items: FutureAvailability[]
  allRankings: Ranking[]
}

export function MayNotMakeItBack({ items, allRankings }: Props) {
  if (items.length === 0) return null

  const withPlayers = items
    .map(item => ({
      item,
      ranking: allRankings.find(r => r.player.id === item.playerId),
    }))
    .filter((x): x is { item: FutureAvailability; ranking: Ranking } => x.ranking !== undefined)

  if (withPlayers.length === 0) return null

  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <AlertCircle size={13} className="text-yellow-400" />
        <span className="text-xs font-bold tracking-widest text-yellow-400 uppercase">
          May Not Make It Back
        </span>
      </div>
      <div className="space-y-1.5">
        {withPlayers.map(({ item, ranking }) => (
          <div
            key={item.playerId}
            className="flex items-center gap-2.5 px-3 py-2 bg-yellow-900/10 border border-yellow-400/20 rounded-lg"
          >
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold text-text-primary truncate">
                  {ranking.player.name}
                </span>
                <PositionBadge position={ranking.player.position} />
              </div>
              <div className="text-xs text-text-muted">{ranking.player.team}</div>
            </div>
            <div className="text-right flex-shrink-0">
              <div className={clsx(
                'text-sm font-bold',
                item.probability > 0.80 ? 'text-red-400' : 'text-yellow-400'
              )}>
                {Math.round(item.probability * 100)}%
              </div>
              <div className="text-xs text-text-muted">gone</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
```

- [ ] **Step 7: Verify TypeScript compiles**

Run: `cd ui && npx tsc --noEmit`
Expected: 0 errors in Task 5 files. Remaining errors from `ui/src/data/` imports are expected (cleaned up in Task 6).

- [ ] **Step 8: Manual smoke test**

With `make api` running, open `http://localhost:5173/draft`. Start a draft. When it's your turn, the recommendation panel should show a real recommendation from the backend (not the client-side engine). Check the network tab — you should see `POST /draft/recommend` requests.

- [ ] **Step 9: Commit**

```bash
git add ui/src/api/draft.ts ui/src/hooks/useRecommendation.ts ui/src/hooks/index.ts \
  ui/src/components/draft/RecommendationPanel.tsx ui/src/components/draft/MyRoster.tsx \
  ui/src/components/draft/MayNotMakeItBack.tsx
git commit -m "feat: draft recommendation API + live useRecommendation hook + session persistence"
```

---

### Task 6: Dashboard Update + Delete All Mock Data

**Files:**
- Modify: `ui/src/pages/Dashboard.tsx`
- Delete: `ui/src/data/mockPlayers.ts`
- Delete: `ui/src/data/mockRankings.ts`
- Delete: `ui/src/data/mockDashboard.ts`
- Delete: `ui/src/data/mockDraftConfig.ts`
- Delete: `ui/src/data/index.ts`

**Interfaces:**
- Consumes: `useRankings` from `../hooks/useRankings`; `fetchScarcity` from `../api/rankings`

- [ ] **Step 1: Replace `ui/src/pages/Dashboard.tsx`**

```typescript
import { useQuery } from '@tanstack/react-query'
import { useRankings } from '../hooks/useRankings'
import { fetchScarcity } from '../api/rankings'
import { TopValuesCard, PositionLeadersCard, ScarcityCard } from '../components/dashboard'
import type { Ranking } from '../types'

const DEFAULT_FILTERS = {
  position: 'ALL' as const,
  search: '',
  format: 'ppr' as const,
  draftType: 'redraft' as const,
  year: 2026,
  tierFilter: null,
}

export default function Dashboard() {
  const { rankings, isLoading } = useRankings(DEFAULT_FILTERS)

  const { data: scarcityRaw } = useQuery({
    queryKey: ['scarcity'],
    queryFn: fetchScarcity,
    staleTime: 60_000,
  })

  const topValues: Ranking[] = rankings
    .filter(r => r.adpDelta < -5)
    .sort((a, b) => a.adpDelta - b.adpDelta)
    .slice(0, 8)

  const positionLeaders: Record<string, Ranking> = Object.fromEntries(
    (['QB', 'RB', 'WR', 'TE'] as const)
      .map(pos => [pos, rankings.find(r => r.player.position === pos)])
      .filter((entry): entry is [string, Ranking] => entry[1] !== undefined)
  )

  const scarcityOverview: Record<string, number> = Object.fromEntries(
    (scarcityRaw ?? []).map(s => [s.position, s.top_tier_count])
  )

  return (
    <div className="p-6 space-y-6 overflow-y-auto h-full">
      <div>
        <h1 className="text-xl font-bold text-text-primary">Dashboard</h1>
        <p className="text-sm text-text-secondary mt-0.5">2026 Season — Live Data</p>
      </div>

      {isLoading ? (
        <div className="text-sm text-text-muted">Loading…</div>
      ) : (
        <>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <TopValuesCard rankings={topValues} />
            <PositionLeadersCard leaders={positionLeaders} />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <ScarcityCard scarcity={scarcityOverview} />
          </div>
        </>
      )}

      <div className="bg-bg-card border border-border rounded-xl p-4">
        <div className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-2">
          Model Status
        </div>
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-green-400" />
          <span className="text-sm text-text-secondary">Connected to live backend — 2026 neural-v1 model</span>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Delete all mock data files**

```bash
rm ui/src/data/mockPlayers.ts
rm ui/src/data/mockRankings.ts
rm ui/src/data/mockDashboard.ts
rm ui/src/data/mockDraftConfig.ts
rm ui/src/data/index.ts
```

- [ ] **Step 3: Verify TypeScript compiles with 0 errors**

Run: `cd ui && npx tsc --noEmit`
Expected: **0 errors** — if any file still imports from `'../data'` or `'../../data'`, it will error here. Fix those imports before committing.

- [ ] **Step 4: Full end-to-end smoke test**

With `make api` running:
1. `cd ui && npm run dev`
2. `/dashboard` — shows real top values, position leaders, scarcity; status dot is green
3. `/rankings` — real player list, position filter works, player drawer opens
4. `/players` — real player list, search works, projection chart renders
5. `/draft` — start a draft, auto-advance fires, recommendation appears on your turn
6. `/settings` — save a league setting, refresh, verify it persists

- [ ] **Step 5: Commit**

```bash
git add ui/src/pages/Dashboard.tsx
git rm ui/src/data/mockPlayers.ts ui/src/data/mockRankings.ts \
        ui/src/data/mockDashboard.ts ui/src/data/mockDraftConfig.ts \
        ui/src/data/index.ts
git commit -m "feat: wire dashboard to live data, delete all mock data files"
```
