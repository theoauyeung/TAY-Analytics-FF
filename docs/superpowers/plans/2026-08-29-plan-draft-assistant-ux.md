# Draft Assistant UX Improvements — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix four issues in the draft assistant: sort the opponent pick panel by ESPN ADP, add guidance text when the left panel is clicked during opponent turns, show stale recommendations while refreshing, and cache backend projections to reduce recommendation latency.

**Architecture:** Tasks 1–3 are isolated frontend changes to existing components and one hook. Task 4 is a backend-only change to `engine.py` — it adds timing instrumentation and a module-level projection cache. No API contract changes anywhere.

**Tech Stack:** React 18, TypeScript, TanStack Query v5, Python 3.12, DuckDB

## Global Constraints

- TypeScript strict mode — no `any`, no type assertions without justification
- Follow existing Tailwind class patterns (check adjacent components for spacing/color tokens)
- No new npm dependencies
- Backend: Python 3.12, no new pip dependencies
- All frontend files live under `ui/src/`, all backend files under `src/tay/`

---

### Task 1: Sort OpponentPickPanel by ESPN ADP

**Files:**
- Modify: `ui/src/components/draft/OpponentPickPanel.tsx` (lines 48–61)

**Interfaces:**
- Consumes: `rankings` from `useRankings` (each entry has `adp: number | null`)
- Produces: nothing (visual-only change)

- [ ] **Step 1: Add ADP sort to the `available` useMemo**

In `OpponentPickPanel.tsx`, find the `available` useMemo (currently ends at `.slice(0, search ? 20 : 12)`). Insert an explicit sort before the slice:

```tsx
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
```

- [ ] **Step 2: Verify manually**

Start the dev server (`cd ui && npm run dev`). Start a draft, let an opponent's turn come up. Confirm the center panel player list is now ordered by ADP (lowest ADP number at top), not by model rank.

- [ ] **Step 3: Commit**

```bash
git add ui/src/components/draft/OpponentPickPanel.tsx
git commit -m "fix: sort opponent pick panel by ESPN ADP"
```

---

### Task 2: Left Panel Opponent-Turn Guidance

**Files:**
- Modify: `ui/src/components/draft/AvailablePlayers.tsx` (inline expanded row section, around line 208)

**Interfaces:**
- Consumes: `isUserTurn` and `isDraftComplete` already available in scope
- Produces: nothing (visual-only change)

- [ ] **Step 1: Add guidance row for opponent-turn pending state**

In `AvailablePlayers.tsx`, find the inline draft confirmation block (currently: `{isPending && (isUserTurn || isDraftComplete) && ...}`). Add a sibling block immediately after it for the opponent-turn case:

```tsx
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

{/* Guidance when not user's turn */}
{isPending && !isUserTurn && !isDraftComplete && (
  <div
    onMouseDown={e => e.stopPropagation()}
    className="flex items-center px-3 py-2 border-b border-border/30"
  >
    <span className="text-xs text-text-muted italic">
      Use the center panel to log opponent picks
    </span>
  </div>
)}
```

- [ ] **Step 2: Verify manually**

In the dev server, start a draft. During an opponent's turn, click any player in the left panel. Confirm the row expands and shows the italic guidance text. Confirm no draft button appears. Confirm dismissing works (Escape or clicking elsewhere).

- [ ] **Step 3: Commit**

```bash
git add ui/src/components/draft/AvailablePlayers.tsx
git commit -m "feat: show guidance text in left panel during opponent turns"
```

---

### Task 3: Stale Recommendation While Loading

**Files:**
- Modify: `ui/src/hooks/useRecommendation.ts`
- Modify: `ui/src/components/draft/RecommendationPanel.tsx`

**Interfaces:**
- `useRecommendation` now returns `{ recommendation: RecommendationState | null, isRefreshing: boolean, error: Error | null }`
- `RecommendationPanel` destructures `isRefreshing` from the hook

- [ ] **Step 1: Update `useRecommendation` to return stale data while fetching**

Replace the entire `useRecommendation.ts` with:

```ts
import { useRef, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import type { RecommendationState } from '../types'
import { useDraftState } from './useDraftState'
import { picksUntilNextTurn } from '../state/draftState'
import { fetchRecommendation, saveSession } from '../api/draft'

export interface UseRecommendationResult {
  recommendation: RecommendationState | null
  isRefreshing: boolean
  error: Error | null
}

export function useRecommendation(): UseRecommendationResult {
  const { state } = useDraftState()
  const isUserTurn = picksUntilNextTurn(state) === 0
  const sessionIdRef = useRef<string | null>(null)
  const lastRef = useRef<RecommendationState | null>(null)

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

  const totalPicks = state.config.teams * state.config.totalRounds
  const draftStarted = state.picks.length > 0 || state.currentOverallPick > 1
  const isDraftComplete = state.currentOverallPick > totalPicks

  const { data, isFetching, error } = useQuery({
    queryKey: ['recommendation', state.currentOverallPick, state.picks.length],
    queryFn: () => fetchRecommendation(state),
    enabled: isUserTurn && draftStarted && !isDraftComplete,
    staleTime: 0,
    retry: false,
  })

  // Keep last successful recommendation so we can show it while refreshing
  if (data) {
    lastRef.current = data
  }

  const recommendation = data ?? lastRef.current
  const isRefreshing = isFetching && lastRef.current !== null

  return { recommendation, isRefreshing, error: error as Error | null }
}
```

- [ ] **Step 2: Update `RecommendationPanel` to consume `isRefreshing`**

In `RecommendationPanel.tsx`:

1. Change the destructure at the top to include `isRefreshing`:
```tsx
const { recommendation: reco, isRefreshing, error: recoError } = useRecommendation()
```

2. Replace the loading guard (currently `if (!reco) { return <div>Loading recommendations...</div> }`) with one that only shows the blank state on the very first load (no stale data):
```tsx
if (!reco) {
  return (
    <div className="flex-1 flex items-center justify-center text-text-muted text-sm">
      Loading recommendations...
    </div>
  )
}
```
This block is unchanged — it now only triggers when `reco` is null (i.e., no stale data and still loading for the first time).

3. Add the "Updating…" badge in the header label section. Find the header div (currently renders `'Your Pick'` or `'Alternative Pick'`):
```tsx
{/* Header label */}
<div className="flex items-center gap-2">
  <span className="text-xs font-bold tracking-wide text-accent uppercase">
    {isShowingAlt ? 'Alternative Pick' : 'Your Pick'}
  </span>
  {isRefreshing && (
    <span className="flex items-center gap-1 text-xs text-text-muted">
      <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
      Updating…
    </span>
  )}
  {isShowingAlt && (
    <button
      onClick={() => setSelectedAltIdx(null)}
      className="ml-auto text-xs text-text-muted hover:text-text-primary"
    >
      Back to top pick
    </button>
  )}
</div>
```

- [ ] **Step 3: Verify manually**

In the dev server, start a draft. On your first turn, confirm "Loading recommendations..." appears (no stale data yet). On your second turn, confirm the previous recommendation is shown immediately with a pulsing "Updating…" badge until the new response arrives.

- [ ] **Step 4: Commit**

```bash
git add ui/src/hooks/useRecommendation.ts ui/src/components/draft/RecommendationPanel.tsx
git commit -m "feat: show stale recommendation with updating badge while refreshing"
```

---

### Task 4: Backend Projection Cache + Timing Logs

**Files:**
- Modify: `src/tay/draft/engine.py`

**Interfaces:**
- `load_projections` signature unchanged: `(conn, season, model_version, drafted_ids) -> list[PlayerProjection]`
- Internal: module-level `_projection_cache: dict[tuple[int, str], list[PlayerProjection]]` caches the full unfiltered projection list per `(season, model_version)`. Drafted IDs are filtered after cache lookup.

- [ ] **Step 1: Add timing instrumentation to `recommend()`**

Add `import time` and `import logging` at the top of `engine.py`. Add a module-level logger. Wrap the three main stages in `recommend()` with timing:

```python
import time
import logging
import duckdb

from tay.draft.board import build_board_analysis
from tay.draft.models import (
    DraftState, PlayerProjection, RecommendationState,
    WaitScenario, NextRoundPositionSummary,
)
from tay.draft.scoring import score_player

logger = logging.getLogger(__name__)

_LOAD_SQL = """..."""  # unchanged

_projection_cache: dict[tuple[int, str], list[PlayerProjection]] = {}


def load_projections(
    conn: duckdb.DuckDBPyConnection,
    season: int,
    model_version: str,
    drafted_ids: list[str],
) -> list[PlayerProjection]:
    cache_key = (season, model_version)
    if cache_key not in _projection_cache:
        t0 = time.perf_counter()
        rows = conn.execute(_LOAD_SQL, [season, model_version]).fetchall()
        _projection_cache[cache_key] = [
            PlayerProjection(
                gsis_id=r[0], name=r[1], position=r[2], team=r[3],
                vor=r[4], vor_rank=r[5], sim_mean=r[6],
                sim_p10=r[7], sim_p90=r[8], adp=r[9],
                tier=r[10], sim_boom_prob=r[11], sim_bust_prob=r[12],
            )
            for r in rows
        ]
        logger.info("projection DB query: %.0fms", (time.perf_counter() - t0) * 1000)
    else:
        logger.info("projection cache hit for season=%s model=%s", season, model_version)

    drafted_set = set(drafted_ids)
    return [p for p in _projection_cache[cache_key] if p.gsis_id not in drafted_set]


def recommend(
    conn: duckdb.DuckDBPyConnection,
    state: DraftState,
) -> RecommendationState:
    t_start = time.perf_counter()

    players = load_projections(conn, state.season, state.model_version, state.drafted_ids)
    t_proj = time.perf_counter()

    teams = state.league_settings.teams
    total_rounds = state.total_picks // teams
    user_pick_numbers = _compute_next_user_picks(
        current_pick=state.current_pick,
        teams=teams,
        user_pick_position=state.user_pick_position,
        total_rounds=total_rounds,
    )

    board = build_board_analysis(
        players=players,
        pick_log=state.pick_log,
        current_pick=state.current_pick,
        teams=state.league_settings.teams,
        user_pick_numbers=user_pick_numbers,
    )
    t_board = time.perf_counter()

    scored = [score_player(p, state, board) for p in players]
    scored.sort(key=lambda r: r.draft_score, reverse=True)
    t_score = time.perf_counter()

    logger.info(
        "recommend timings — projections: %.0fms, board: %.0fms, scoring: %.0fms, total: %.0fms",
        (t_proj - t_start) * 1000,
        (t_board - t_proj) * 1000,
        (t_score - t_board) * 1000,
        (t_score - t_start) * 1000,
    )

    # rest of recommend() body unchanged from here
    if not scored:
        raise ValueError(
            f'No available players for season={state.season} model={state.model_version}'
        )

    top_pick = scored[0]
    alternatives = scored[1:4]

    wait_analysis = _build_wait_analysis(board, scored)
    next_round_board = _build_next_round_board(board)

    all_positions = list(board.per_position.keys()) + [
        pos for pos in ('QB', 'RB', 'WR', 'TE') if pos not in board.per_position
    ]
    positional_needs = sorted(
        all_positions,
        key=lambda pos: (
            sum(r.positional_urgency for r in scored if r.player.position == pos)
            / max(1, sum(1 for r in scored if r.player.position == pos))
        ) if any(r.player.position == pos for r in scored) else 1.0,
        reverse=True,
    )

    top_id = top_pick.player.gsis_id
    may_not_make_it_back = [
        r.player for r in scored[1:]
        if r.future_availability_pct < 0.35 and r.player.gsis_id != top_id
    ]

    return RecommendationState(
        top_pick=top_pick,
        alternatives=alternatives,
        positional_needs=positional_needs,
        may_not_make_it_back=may_not_make_it_back,
        wait_analysis=wait_analysis,
        next_round_board=next_round_board,
        board_state={
            'current_pick': state.current_pick,
            'round': state.round,
            'picks_until_next': state.picks_until_next,
        },
    )
```

- [ ] **Step 2: Verify timing logs appear**

Start the API server (`python scripts/run_api.py`). Make a draft recommendation request (start the UI, complete setup, let your first turn arrive). In the server terminal, confirm you see lines like:

```
INFO tay.draft.engine: projection DB query: 142ms
INFO tay.draft.engine: recommend timings — projections: 142ms, board: 380ms, scoring: 45ms, total: 567ms
```

On the second turn, confirm you see `projection cache hit` instead of the DB query time.

- [ ] **Step 3: Check the logging config reaches INFO**

If the INFO lines don't appear, the root logger level may be WARNING. In `scripts/run_api.py` (or wherever the server bootstraps), ensure logging is configured:

```python
import logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s %(name)s: %(message)s')
```

Add this near the top of `run_api.py` if missing. Verify the timing lines now appear.

- [ ] **Step 4: Commit**

```bash
git add src/tay/draft/engine.py scripts/run_api.py
git commit -m "perf: cache player projections in memory, add recommendation timing logs"
```
