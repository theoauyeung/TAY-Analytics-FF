# Draft Assistant — Dynamic Positional Scarcity & Future Board Analysis

**Date:** 2026-08-29  
**Status:** Approved  

## Problem

The current Draft Score is a ranking system with a roster filter attached. It scores players individually using static positional caps and a single-pick ADP survival estimate. It does not ask: "If I pass on this player now, what is my realistic alternative at this position when I pick again?" The recommendation cannot distinguish between positions with deep benches (wait is cheap) and positions where a tier cliff is imminent (wait is costly).

## Goal

Turn the recommendation engine into a dynamic decision engine that is:
- **Value-aware**: scores based on VOR and tier position
- **Future-aware**: models what the board will look like at the user's next 3 pick opportunities
- **Roster-aware**: weights urgency by what the user's current roster actually needs
- **Opponent-aware**: adjusts survival probabilities based on other teams' positional needs

## Architecture Overview

Introduce a new `board.py` module (Approach B from design review). Board analysis runs once per recommendation request against the full available player pool, producing a `BoardAnalysis` object. `scoring.py` consumes `BoardAnalysis` as context rather than computing positional state from scratch per player.

```
recommend() in engine.py
  └─ build_board_analysis()  ← new, runs once
  └─ score_player() × N      ← now receives BoardAnalysis
  └─ build_wait_analysis()   ← new, runs after scoring
  └─ build_next_round_board() ← new, runs after scoring
```

## New Module: `src/tay/draft/board.py`

### Data structures

```python
@dataclass
class TierCliff:
    before_player: PlayerProjection   # last player in the current tier
    after_player: PlayerProjection    # first player in the next tier
    vor_drop: float                   # before.vor - after.vor
    tier_jump: int                    # e.g. 2→3
    rank_at_cliff: int                # position rank of before_player

@dataclass
class PositionBoardState:
    position: str
    available: list[PlayerProjection]         # sorted by VOR desc
    tier_cliffs: list[TierCliff]
    survival_probs: dict[str, list[float]]    # gsis_id → [P(next pick), P(+1 pick), P(+2 picks)]
    run_in_progress: bool                     # True if 3+ of last 5 picks at this position

@dataclass
class BoardAnalysis:
    per_position: dict[str, PositionBoardState]
    opponent_rosters: dict[int, dict[str, int]]  # team_num → {pos: count}
```

### `build_board_analysis(players, pick_log, teams, user_pick_numbers)`

**Opponent rosters**: Walk the ordered `pick_log` (list of `{gsis_id, team_number}`). Look up each player's position from the loaded projections. Increment `opponent_rosters[team_num][pos]`. This reconstructs every team's position-count map.

**Run detection**: Look at the last 5 entries in `pick_log`. If 3 or more share the same position, mark that position's `run_in_progress = True`.

**Survival probability**: For each player, compute the base ADP z-score survival probability at the user's next pick (same formula as current `future_availability()`). Then adjust for opponent pressure: for each team picking before the user that has 0 or 1 starters at the player's position, add `+0.05` demand weight per hungry team. During a positional run, add `+0.03` per team still to pick in the current round. Clamp result to `[0, 1]`. Note: higher demand weight means the player is *more likely to be drafted*, so the survival probability is `base_prob - demand_adjustment`.

**Tier cliffs**: For each position, walk the VOR-sorted available list. Whenever `players[i+1].tier > players[i].tier`, record a `TierCliff`.

## Updated `src/tay/draft/scoring.py`

### Revised `score_player()` signature

```python
def score_player(
    player: PlayerProjection,
    state: DraftState,
    board: BoardAnalysis,
) -> Recommendation:
```

`available_by_position` and `replacement_spots` parameters are removed.

### Draft Score formula

```
player_value    = player.vor
urgency_factor  = 1.0 + cliff_premium + scarcity_premium
roster_factor   = roster_fit() result  [0.5, 1.2]
now_vs_wait     = 1.5 - 0.5 * survival_prob

draft_score = player_value * urgency_factor * roster_factor * now_vs_wait
```

**cliff_premium** (`+0.3`): fires when the player is the last available in their tier at their position (i.e. the next available player at the position has a higher tier number).

**scarcity_premium** (`0.0–0.5`): replaces the static-cap `positional_urgency`. Counts remaining tier-1-through-3 players at the position. Scales linearly from 0 (at or above threshold) to 0.5 (exhausted). Thresholds: RB/WR = 8, QB/TE = 4.

**survival_prob**: looked up from `board.per_position[pos].survival_probs[player.gsis_id][0]` (next-pick horizon). Falls back to the existing ADP z-score if the player is not in the board (e.g. undrafted K/DST).

**`WaitScenario.expected_vor_at_next_pick`**: computed in `build_wait_analysis()` in `engine.py`. For each position, iterate available players at that position and compute the probability-weighted expected VOR: `sum(player.vor * survival_probs[player.gsis_id][0] for each player)`, normalized by the sum of survival probs. This gives the expected best VOR the user can realistically expect at their next pick, accounting for all players that might still be available rather than just a single ADP cutoff.

**QB patience suppression**: unchanged from current logic.

### Explanation generation

Structured `{factor, detail, weight}` objects:
- `weight="primary"`: cliff warning, high VOR cost of waiting (> 10), strong VOR (> 20)
- `weight="risk"`: survival probability < 0.35
- `weight="secondary"`: roster fit bonus, upside, ADP value

## Updated `src/tay/draft/models.py`

### New dataclasses

```python
@dataclass
class WaitScenario:
    position: str
    best_now_name: str
    best_now_vor: float
    expected_vor_at_next_pick: float
    vor_cost_of_waiting: float        # best_now_vor - expected_vor_at_next_pick
    cliff_before_next_pick: bool
    survival_probability: float       # P(best_now still available)

@dataclass
class NextRoundPositionSummary:
    position: str
    strong_options_remaining: int     # tier ≤ 3 players likely to survive (prob > 0.3)
    next_cliff_rank: int | None       # position rank where next cliff occurs
    cliff_warning: bool
```

### Updated `RecommendationState`

Add two new fields:
```python
wait_analysis: list[WaitScenario]
next_round_board: dict[str, NextRoundPositionSummary]
```

## Updated `src/tay/api/routers/draft.py` and schemas

### API input change

`DraftStateIn.drafted_ids: list[str]` is replaced by `DraftStateIn.pick_log: list[PickEntry]` where:

```python
class PickEntry(BaseModel):
    gsis_id: str
    team_number: int
```

`drafted_ids` is derived on the backend as `[e.gsis_id for e in pick_log]`.

### API output

`dataclasses.asdict(result)` already serializes new fields automatically. No router changes needed beyond accepting the new input schema.

## Frontend changes

### `ui/src/api/draft.ts`

- `toDraftStateIn()`: send `pick_log: state.picks.map(p => ({gsis_id: p.player.id, team_number: p.teamNumber}))` instead of `drafted_ids`.
- Add `BackendWaitScenario` and `BackendNextRoundSummary` interfaces mapping snake_case backend fields.
- Map backend response into frontend `WaitScenario[]` and `NextRoundBoard` types.

### New component: `ui/src/components/draft/WaitAnalysisPanel.tsx`

Renders one row per position in `reco.waitAnalysis`. Shows all positions that appear among the top 5 scored players. If the top pick and all 4 alternatives are the same position, the panel is hidden entirely (no value showing a single-position comparison to itself).

Each row:
```
IF YOU WAIT ON {POS}
  Best now:   {name}  +{vor} VOR   [⚠ CLIFF if cliff_before_next_pick]
  Next pick:  ~+{expected} VOR expected
  Cost:       -{cost} VOR   (red if > 10, yellow if 5–10, neutral if < 5)
```

### New component: `ui/src/components/draft/NextRoundBoardPanel.tsx`

Compact 4-column grid showing expected board state at user's next pick:

```
LIKELY AVAILABLE NEXT PICK
QB          RB          WR          TE
6 options   2 options   8 options   4 options
            ⚠ cliff
```

`strong_options_remaining` = tier ≤ 3 players with survival prob > 0.3. `⚠ cliff` badge shown when `cliff_warning: true`.

### Updated `ui/src/components/draft/RecommendationPanel.tsx`

Render order (unchanged sections omitted):
1. Main player card (unchanged)
2. WHY section (unchanged)
3. **`WaitAnalysisPanel`** (new)
4. **`NextRoundBoardPanel`** (new)
5. Alternatives (unchanged)
6. ScarcityBar — populate from `wait_analysis[pos].vor_cost_of_waiting` instead of empty `[]`
7. MayNotMakeItBack (unchanged)

### Updated `ui/src/components/draft/ScarcityBar.tsx`

Receives `wait_analysis` instead of the current stub `scarcity: []`. Bar intensity per position = `vor_cost_of_waiting` normalized against the max cost across positions.

### Frontend types

Add to `ui/src/types/draft.ts`:
```typescript
export interface WaitScenario {
  position: string
  bestNowName: string
  bestNowVor: number
  expectedVorAtNextPick: number
  vorCostOfWaiting: number
  cliffBeforeNextPick: boolean
  survivalProbability: number
}

export interface NextRoundPositionSummary {
  position: string
  strongOptionsRemaining: number
  nextCliffRank: number | null
  cliffWarning: boolean
}
```

Update `RecommendationState` in `ui/src/types/index.ts` to include `waitAnalysis: WaitScenario[]` and `nextRoundBoard: Record<string, NextRoundPositionSummary>`.

## Testing

### `tests/draft/test_board.py` (new)
- Tier cliff detection: given players with known tier values, assert correct `TierCliff` records
- Survival probability: opponent pressure reduces survival prob; run-in-progress increases demand
- Run detection: 3+ of last 5 same position → flagged; mixed positions → not flagged
- Opponent roster reconstruction: ordered pick log produces correct position counts per team

### `tests/draft/test_scoring.py` (extend)
- Update `score_player()` calls to pass `BoardAnalysis` instead of old parameters
- Assert cliff premium fires when player is last in tier
- Assert scarcity premium scales from 0 → 0.5 as tier-1-3 players thin out
- Assert `now_vs_wait` factor matches expected shape given survival prob

### `tests/draft/test_engine.py` (extend)
- Assert `wait_analysis` and `next_round_board` fields present in `RecommendationState`
- Assert a board with a sharp RB tier cliff produces higher `vor_cost_of_waiting` for RB than a flat WR board

### `tests/api/test_draft.py` (extend)
- Update request fixture to use `pick_log` instead of `drafted_ids`
- Assert new response fields (`wait_analysis`, `next_round_board`) are present and well-formed

## What does NOT change
- `session.py` — session persistence is unaffected
- `pipeline.py` — data ingestion pipeline is unaffected
- `DraftState` model — unchanged; `drafted_ids` is derived from `pick_log` in the router before constructing `DraftState`
- Mock draft (`MockDraft.tsx`, `mockDraftSimulator.ts`) — separate feature, not touched
- Draft setup screen — unchanged
- Available players list — unchanged
