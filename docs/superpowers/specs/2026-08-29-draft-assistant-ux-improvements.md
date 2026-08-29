# Draft Assistant UX Improvements

**Date:** 2026-08-29
**Scope:** Four targeted improvements to the draft assistant UI and backend recommendation latency.

---

## 1. OpponentPickPanel — Sort by ESPN ADP

**Problem:** The opponent pick panel sorts available players by our model's rank (implicit via `useRankings` return order). This is disorienting during a live draft where ESPN ADP is the shared reference point everyone uses.

**Change:** In `OpponentPickPanel`, add an explicit `.sort((a, b) => (a.adp ?? 999) - (b.adp ?? 999))` after the filter step in the `available` useMemo. No other changes needed — the left `AvailablePlayers` panel already uses this sort and can serve as the reference implementation.

---

## 2. Left Panel — Opponent-Turn Guidance

**Problem:** When it is not the user's turn, clicking a player in `AvailablePlayers` highlights it (pending state) but shows no actionable UI and no explanation of why. Users don't know to use the center panel to log opponent picks.

**Change:** In the inline expanded row (`isPending && !isUserTurn && !isDraftComplete`), render a small guidance message — e.g., *"Use the center panel to log opponent picks"* — instead of leaving the row empty. Style it as muted/secondary text consistent with other hint text in the panel. No behavioral change.

---

## 3. Stale Recommendation While Loading (UX)

**Problem:** When the user's turn starts, `useRecommendation` fires a fresh fetch and the panel shows "Loading recommendations..." with a blank screen until the response arrives.

**Change:**

- In `useRecommendation`, track the last successful recommendation in a `useRef<RecommendationState | null>`. On each successful `data` response, update the ref. Return `{ recommendation, isRefreshing, error }` where:
  - `recommendation` = `data ?? lastRef.current` (live data if available, otherwise stale)
  - `isRefreshing` = `isFetching && lastRef.current !== null`
- In `RecommendationPanel`, consume `isRefreshing`. When true, show a small "Updating…" badge (e.g., a pulsing dot + text) in the header area, overlaid over the stale recommendation content. The "Loading recommendations..." blank state only shows on the very first pick of the draft when there is no prior recommendation to fall back on.

---

## 4. Backend Recommendation Latency (Performance)

**Problem:** The `/draft/recommend` endpoint is slow, causing the blank-screen wait in (3). Root cause is unknown.

**Approach:**

1. Add coarse timing logs at key steps in `src/tay/draft/pipeline.py` (or wherever the recommendation pipeline runs) using `time.perf_counter()`. Log stage durations at the INFO level so they appear in server output.
2. Identify the slowest stage. Likely candidates:
   - Player projection lookups hitting the DB on every call
   - Monte Carlo simulation re-running from scratch per request
   - Unindexed queries in the board/session fetch
3. Cache player season projections in memory (module-level dict keyed by `(season, model_version)`). Projections don't change during a draft session, so a per-process cache is safe. Invalidate on server restart.
4. No API contract changes. No changes to the frontend beyond what (3) already handles.

---

## Out of Scope

- Pre-fetching recommendations before the user's turn (rejected: stale picks would invalidate the pre-fetched recommendation).
- Allowing self-picks from the left panel during opponent turns.
- Reordering alternatives in the `RecommendationPanel` (alternatives remain sorted by draft score).
