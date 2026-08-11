# API Integration Design

**Date:** 2026-08-11

## Goal

Replace all mock data in the React frontend with live calls to the FastAPI backend, wiring rankings, players, league settings, and the draft recommendation engine (including session persistence) to real data.

## Architecture

A centralized `ui/src/api/` module with four domain files sits between the React Query hooks and the network. Each domain file exports typed async functions; hooks import from those files and delete their mock-data imports. A single `client.ts` base layer handles the base URL and error normalization. Mock data files in `ui/src/data/` are deleted once the hooks are updated.

**Tech stack:** native `fetch` (no new npm dependencies), Vite env vars for base URL, existing React Query hooks for state management.

## Global Constraints

- API base URL: `VITE_API_URL=http://localhost:8000` (Vite env var)
- Fixed query params on every request: `season=2026`, `model_version=neural-v1`
- Backend uses snake_case; frontend uses camelCase — API modules own the translation
- Player identity: backend uses `gsis_id`; frontend uses `player.id` — map `gsis_id → id` in API responses
- Scoring format translation: frontend `'half_ppr'` → backend `'half'` (and reverse)
- Backend roster_config only accepts `QB, RB, WR, TE, FLEX` — omit `BENCH` when sending
- `from __future__ import annotations` not applicable (TypeScript files)
- All new files are TypeScript (`.ts`); components are `.tsx`

---

## File Structure

**Create:**
- `ui/.env` — `VITE_API_URL=http://localhost:8000`
- `ui/.env.example` — same content, committed to git
- `ui/src/api/client.ts` — `apiFetch` wrapper + `ApiError` class + shared constants
- `ui/src/api/rankings.ts` — `fetchRankings`, `fetchTiers`, `fetchScarcity`
- `ui/src/api/players.ts` — `fetchPlayers`, `fetchPlayer`
- `ui/src/api/draft.ts` — `fetchRecommendation`, `saveSession`, `loadSession`
- `ui/src/api/league.ts` — `fetchLeagueSettings`, `saveLeagueSettings`

**Modify:**
- `ui/src/hooks/useRankings.ts` — replace mock fetch with `fetchRankings`
- `ui/src/hooks/usePlayer.ts` — replace mock fetch with `fetchPlayer`
- `ui/src/hooks/useDraftState.ts` — import live player pool from `fetchPlayers` instead of `MOCK_PLAYERS`
- `ui/src/hooks/useMockRecommendation.ts` → rename to `useRecommendation.ts` — replace client-side engine with `fetchRecommendation`
- `ui/src/hooks/useLeagueSettings.ts` — replace localStorage with API calls
- Dashboard data source — derive `TOP_VALUES` and `POSITION_LEADERS` from rankings; `SCARCITY_OVERVIEW` from scarcity endpoint; remove `MODEL_MOVERS` widget
- Any component importing `useMockRecommendation` — update import to `useRecommendation`

**Delete:**
- `ui/src/data/mockPlayers.ts`
- `ui/src/data/mockRankings.ts`
- `ui/src/data/mockDashboard.ts`
- `ui/src/data/mockDraftConfig.ts`
- `ui/src/data/index.ts`

---

## Section 1: API Client Layer (`client.ts`)

```typescript
export const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
export const SEASON = 2026
export const MODEL_VERSION = 'neural-v1'

export class ApiError extends Error {
  constructor(public status: number, message: string) {
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
    const body = await res.json().catch(() => ({}))
    throw new ApiError(res.status, body.detail ?? res.statusText)
  }
  return res.json() as Promise<T>
}
```

---

## Section 2: Domain API Modules

### `rankings.ts`

```typescript
import { apiFetch, SEASON, MODEL_VERSION } from './client'
import type { Ranking, RankingFilters } from '../types'

export async function fetchRankings(filters: RankingFilters): Promise<Ranking[]>
// GET /rankings?season=2026&model_version=neural-v1&sort=vor_rank[&position=QB]
// Filter position only if filters.position !== 'ALL'
// Maps snake_case response fields to camelCase Ranking type
// Derives tier from backend tier_number (1–5) → TierLabel lookup
// Maps player_id (gsis_id) → player.id

export async function fetchScarcity(): Promise<ScarcityPositionOut[]>
// GET /scarcity?season=2026&model_version=neural-v1
```

The `search` and `tierFilter` filters are applied client-side after fetching (same as mock implementation) since the backend has no search/tier-filter query params.

**Backend → Frontend field map for Ranking:**

| Backend field | Frontend field | Notes |
|---|---|---|
| `player_id` | `player.id` | gsis_id |
| `name` | `player.name` | |
| `position` | `player.position` | |
| `team` | `player.team` | |
| `vor_rank` | `rank` | |
| `position_rank` | `positionRank` | |
| `vor` | `vor` | |
| `adp` | `adp` | null → 999 |
| `projected_points` | `projection` | |
| `floor` | `floor` | |
| `ceiling` | `ceiling` | |
| `tier_number` | `tier.number` | |
| `adp_delta` | `adpDelta` | |
| Missing fields | `0` or `null` | `targetShare`, `rushShare`, etc. |

`tier.label` is derived from `tier.number` using this lookup:
```typescript
const TIER_LABELS = {
  1: 'TIER 1 — ELITE',
  2: 'TIER 2 — HIGH-END',
  3: 'TIER 3 — SOLID STARTER',
  4: 'TIER 4 — STREAMER',
  5: 'TIER 5 — DEEP BENCH',
}
```

### `players.ts`

```typescript
export async function fetchPlayers(filters?: { position?: string }): Promise<PlayerDetail[]>
// GET /players?season=2026&model_version=neural-v1[&position=QB]
// Maps backend PlayerOut (snake_case) → frontend PlayerDetail (camelCase)
// Maps gsis_id → id

export async function fetchPlayer(id: string): Promise<PlayerDetail>
// GET /players/{id}?season=2026&model_version=neural-v1
// Throws ApiError(404) if not found
```

**Backend → Frontend field map for PlayerDetail (key fields):**

| Backend field | Frontend field |
|---|---|
| `gsis_id` | `id` |
| `name` | `name` |
| `position` | `position` |
| `team` | `team` |
| `projected_points` | `projection.mean` |
| `floor` | `projection.floor` |
| `ceiling` | `projection.ceiling` |
| Missing projection fields | `0` |
| Missing opportunity/efficiency fields | `null` |

### `draft.ts`

The most complex module. Handles bidirectional mapping between `LiveDraftState` (frontend) and `DraftStateIn` (backend), and maps the backend's `RecommendationState` response to the frontend's type.

```typescript
export async function fetchRecommendation(state: LiveDraftState): Promise<RecommendationState>
// POST /draft/recommend
// Throws ApiError(422) if draft pool is exhausted

export async function saveSession(sessionId: string, state: LiveDraftState): Promise<void>
// POST /draft/session
// Fire-and-forget — caller should not await or handle errors

export async function loadSession(sessionId: string): Promise<LiveDraftState | null>
// GET /draft/session/{sessionId}
// Returns null on 404
```

**`LiveDraftState` → `DraftStateIn` mapping:**

```typescript
function toDraftStateIn(state: LiveDraftState): DraftStateIn {
  const userPicks = state.picks.filter(p => p.isUserPick)
  const userRoster: Record<string, string[]> = { QB: [], RB: [], WR: [], TE: [], FLEX: [] }
  for (const pick of userPicks) {
    const pos = pick.player.position
    if (pos in userRoster) userRoster[pos].push(pick.player.id)
  }

  return {
    season: SEASON,
    model_version: MODEL_VERSION,
    league_settings: {
      teams: state.config.teams,
      scoring: normalizeScoringFormat(state.config.scoringFormat), // 'half_ppr' → 'half'
      roster_config: {
        QB: state.config.rosterConfig.QB,
        RB: state.config.rosterConfig.RB,
        WR: state.config.rosterConfig.WR,
        TE: state.config.rosterConfig.TE,
        FLEX: state.config.rosterConfig.FLEX,
        // BENCH omitted — backend does not accept it
      },
    },
    current_pick: state.currentOverallPick,
    total_picks: state.config.teams * state.config.totalRounds,
    user_pick_position: state.config.userPickPosition,
    drafted_ids: state.picks.map(p => p.player.id),
    user_roster: userRoster,
  }
}

function normalizeScoringFormat(f: ScoringFormat): string {
  return f === 'half_ppr' ? 'half' : f
}
```

**Backend `RecommendationState` → frontend `RecommendationState` mapping:**

The backend returns (snake_case):
```json
{
  "top_pick": { "player": {...}, "draft_score": 0.87, "roster_fit": 0.9, "future_availability": 0.6, "explanation": [] },
  "alternatives": [...],
  "positional_needs": { "QB": 0.2, "RB": 0.8, ... },
  "board_state": { "current_pick": 5, "round": 1, "picks_until_next": 0 }
}
```

Map to frontend type:
- `top_pick` → `topPick` (apply `mapRecommendation()` below)
- `alternatives` → `alternatives` (same mapping)
- `positional_needs` → `positionalNeeds`
- `board_state` → dropped
- `scarcity` → `[]` (backend does not return; use empty array)
- `mayNotMakeItBack` → `[]` (backend does not return; use empty array)

`mapRecommendation()` converts a backend pick to the frontend shape:
- `player` fields: `player_id → id`, `name`, `position`, `team`, `projected_points → projection.mean` (other projection fields default to 0)
- `draft_score` → `draftScore`
- `roster_fit` → `rosterFit`
- `future_availability` (float 0–1) → `futureAvailability: { playerId: player.player_id, probability: future_availability, label: deriveLabel(future_availability) }`
  - `label` derivation: `< 0.3 → 'safe'`, `0.3–0.7 → 'monitor'`, `> 0.7 → 'urgent'`
- `explanation` → `explanation` (pass through as-is; backend returns `[{factor, detail, weight}]`)
- All `Ranking` fields not in backend response (`rank`, `positionRank`, `vor`, `adp`, `tier`, etc.) → `0` or `null`

**Session flow:**

`useRecommendation` manages `sessionId` in `sessionStorage`:
- On mount: check `sessionStorage.getItem('tay-draft-session-id')`. If present, call `loadSession(id)` to restore `LiveDraftState`. If 404 or absent, start fresh.
- On draft start: generate `crypto.randomUUID()`, store in `sessionStorage`.
- After each pick: call `saveSession(sessionId, currentState)` in a fire-and-forget `useEffect`.

### `league.ts`

```typescript
export async function fetchLeagueSettings(): Promise<LeagueSettings>
// GET /league/settings
// Maps backend { teams, scoring, roster_config } → frontend LeagueSettings
// Normalizes scoring: 'half' → 'half_ppr'

export async function saveLeagueSettings(settings: LeagueSettings): Promise<void>
// POST /league/settings
// Maps frontend LeagueSettings → backend shape (normalize scoring, omit BENCH)
```

---

## Section 3: Hook Updates

### `useRankings.ts`
Replace the mock `fetchRankings` function body with a call to `api/rankings.fetchRankings`. Apply `search` and `tierFilter` client-side after the API response (no change to filter logic, only data source changes). Add `error` to the return value: `{ rankings, isLoading, error }`.

### `usePlayer.ts`
Replace mock fetch with `api/players.fetchPlayer(id)`. Return `{ player, isLoading, error }`.

### `useDraftState.ts`
Replace `MOCK_PLAYERS` import with a `useQuery` call to `api/players.fetchPlayers()`. The `availablePlayers` derivation (filter out drafted IDs) stays the same — only the source pool changes.

### `useMockRecommendation.ts` → `useRecommendation.ts`
File renamed. Replace the entire client-side scoring engine with:
```typescript
const { data, isLoading, error } = useQuery({
  queryKey: ['recommendation', draftState],
  queryFn: () => fetchRecommendation(draftState),
  enabled: isUserTurn,
})
```
Session persistence side-effects live in `useEffect` hooks within this file.

### `useLeagueSettings.ts`
Replace `useState` + `localStorage` with:
- `useQuery` for fetching (queryKey: `['leagueSettings']`)
- `useMutation` for saving
- Keep `DEFAULT_LEAGUE_SETTINGS` as the initial data / placeholder while loading

---

## Section 4: Dashboard Adaptation

The dashboard currently imports from `mockDashboard.ts`. Replace with data derived from the rankings and scarcity queries:

- **TOP_VALUES** — top 5 players from `useRankings({ position: 'ALL', sort: 'vor_rank' })` ordered by VOR
- **POSITION_LEADERS** — first player per position (QB/RB/WR/TE) from the same rankings response
- **SCARCITY_OVERVIEW** — `useScarcity()` hook wrapping `fetchScarcity()`
- **MODEL_MOVERS** — removed; the widget is deleted from the dashboard layout

---

## Section 5: Error Handling

Each page that fetches data gets an `error` state from its React Query hook. When `error` is non-null, render:
```tsx
<div>
  <p>{error.message}</p>
  <button onClick={() => refetch()}>Retry</button>
</div>
```

The draft page specifically handles `ApiError` with `status === 422` by showing "No available players — the draft pool is exhausted" instead of the generic message.

Loading states (skeletons/spinners) already exist in the UI — no changes needed there.

---

## Testing

No new unit tests are added for the API modules (they are thin wrappers over `fetch`). Verification is done by running the dev server against the live FastAPI backend and exercising each page:

1. `make api` to start the FastAPI server
2. `cd ui && npm run dev` to start the frontend
3. Verify: rankings page shows real player data, player drawer opens with real stats, draft assistant gets real recommendations, league settings save and reload, dashboard shows live top values and scarcity

The existing Python backend test suite (`pytest`) remains the source of truth for API correctness.
