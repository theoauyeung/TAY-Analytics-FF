# Draft Assistant — Dynamic Positional Scarcity & Future Board Analysis

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the draft recommendation engine's static scoring with a dynamic BoardAnalysis-driven system that models tier cliffs, opponent needs, and the cost of waiting at each position.

**Architecture:** A new `board.py` module analyzes the full available player pool once per request — computing tier cliffs, survival probabilities (opponent-adjusted), and opponent rosters. `scoring.py` then consumes a `BoardAnalysis` object per player instead of static position counts. Two new outputs (`wait_analysis`, `next_round_board`) surface this reasoning to the frontend as "What Happens If I Wait?" and "Likely Available Next Pick" panels.

**Tech Stack:** Python 3.12, duckdb, FastAPI/Pydantic v2, React 18, TypeScript, Tailwind CSS, @tanstack/react-query, lucide-react

## Global Constraints

- All backend Python uses `from __future__ import annotations`
- `dataclasses.asdict()` is used to serialize backend response — keep all output types as plain dataclasses
- Existing `future_availability()` in `scoring.py` is kept as a utility; `positional_urgency()` is removed
- `pick_log` entries are `(gsis_id, team_number, position)` — position is included so board.py needs no extra DB query
- Survival probabilities are a list of 3 floats: `[P(next pick), P(+1 pick), P(+2 picks)]`
- Opponent pressure only applies to horizon 0 (next pick); horizons 1 and 2 use raw ADP z-score
- Frontend uses existing design system: `bg-bg-card`, `bg-bg-elevated`, `text-text-primary`, `text-text-muted`, `text-accent`, `border-border`, Tailwind
- Run `pytest tests/` from project root; run `npm run typecheck` from `ui/` to verify TypeScript
- Commit frequently — every task ends with a commit

---

## File Map

**New files:**
- `src/tay/draft/board.py` — `TierCliff`, `PositionBoardState`, `BoardAnalysis`, `build_board_analysis()`
- `tests/draft/test_board.py` — tests for board analysis (opponent rosters, run detection, survival probs, tier cliffs)
- `ui/src/components/draft/WaitAnalysisPanel.tsx` — "What Happens If I Wait?" UI panel
- `ui/src/components/draft/NextRoundBoardPanel.tsx` — "Likely Available Next Pick" grid

**Modified files:**
- `src/tay/draft/models.py` — add `WaitScenario`, `NextRoundPositionSummary`; update `Recommendation.explanation` to `list[dict[str, str]]`; add `pick_log` to `DraftState`; extend `RecommendationState`
- `src/tay/api/schemas.py` — add `PickEntry` (with `position`); replace `drafted_ids` with `pick_log` in `DraftStateIn`
- `src/tay/draft/scoring.py` — update `score_player()` to accept `BoardAnalysis`; remove `positional_urgency()`; new structured explanation format
- `src/tay/draft/engine.py` — import board module; add `_compute_next_user_picks()`, `build_wait_analysis()`, `build_next_round_board()`; update `recommend()`
- `src/tay/api/routers/draft.py` — derive `drafted_ids` and `pick_log` from `PickEntry` list
- `tests/draft/test_scoring.py` — update calls to `score_player`; replace `positional_urgency` tests with cliff/scarcity tests
- `tests/draft/test_engine.py` — add `pick_log` field to `_state()`; assert `wait_analysis` + `next_round_board` fields
- `tests/api/test_draft.py` — update `_STATE` fixture to use `pick_log`; add assertions for new response fields
- `ui/src/types/recommendation.ts` — add `WaitScenario`, `NextRoundPositionSummary`; update `RecommendationState`; remove `PositionalScarcity`
- `ui/src/api/draft.ts` — update `toDraftStateIn()` + `mapRecommendation()` + `fetchRecommendation()` response mapping
- `ui/src/components/draft/ScarcityBar.tsx` — accept `WaitScenario[]` instead of `PositionalScarcity[]`
- `ui/src/components/draft/RecommendationPanel.tsx` — insert `WaitAnalysisPanel` + `NextRoundBoardPanel`; update `ScarcityBar` props
- `ui/src/components/draft/index.ts` — export two new components

---

## Task 1: `board.py` — data structure scaffold

**Files:**
- Create: `src/tay/draft/board.py`

**Interfaces:**
- Produces: `TierCliff`, `PositionBoardState`, `BoardAnalysis` (imported by Tasks 3, 6, 7)

- [ ] **Step 1: Create `src/tay/draft/board.py` with dataclasses only**

```python
"""Board-level analysis — one-shot computation over all available players."""
from __future__ import annotations
from dataclasses import dataclass, field
from tay.draft.models import PlayerProjection


@dataclass
class TierCliff:
    before_player: PlayerProjection   # last player in current tier
    after_player: PlayerProjection    # first player in next (worse) tier
    vor_drop: float                   # before.vor - after.vor
    tier_jump: int                    # e.g. tier 2→3 means tier_jump=1
    rank_at_cliff: int                # 1-indexed position rank of before_player


@dataclass
class PositionBoardState:
    position: str
    available: list[PlayerProjection]             # sorted VOR desc
    tier_cliffs: list[TierCliff]
    survival_probs: dict[str, list[float]]        # gsis_id → [P(next), P(+1), P(+2)]
    run_in_progress: bool                         # 3+ of last 5 picks at this position


@dataclass
class BoardAnalysis:
    per_position: dict[str, PositionBoardState]
    opponent_rosters: dict[int, dict[str, int]]   # team_num → {position: count}
```

- [ ] **Step 2: Verify the module imports cleanly**

```bash
cd "/Users/theoauyeung/Documents/Projects/TAY Analytics FF" && python -c "from tay.draft.board import TierCliff, PositionBoardState, BoardAnalysis; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add src/tay/draft/board.py
git commit -m "feat: board.py data structures — TierCliff, PositionBoardState, BoardAnalysis"
```

---

## Task 2: `board.py` — opponent rosters, run detection, tier cliffs

**Files:**
- Modify: `src/tay/draft/board.py`
- Create: `tests/draft/test_board.py`

**Interfaces:**
- Consumes: `PlayerProjection` from `tay.draft.models`, `future_availability` from `tay.draft.scoring`
- Produces: `build_board_analysis(players, pick_log, current_pick, teams, user_pick_numbers) -> BoardAnalysis`
  - `players: list[PlayerProjection]` — available (undrafted) players
  - `pick_log: list[tuple[str, int, str]]` — `(gsis_id, team_number, position)` for every pick in draft order
  - `current_pick: int` — current overall pick number (1-indexed)
  - `teams: int` — league size
  - `user_pick_numbers: list[int]` — next 3 overall pick numbers for the user (len == 3, padded with `total_picks + 1` if fewer remain)

- [ ] **Step 1: Write failing tests**

Create `tests/draft/test_board.py`:

```python
from __future__ import annotations
import pytest
from tay.draft.models import PlayerProjection
from tay.draft.board import BoardAnalysis, build_board_analysis


def _player(gsis_id: str, position: str, vor: float, adp: float, tier: int):
    return PlayerProjection(
        gsis_id=gsis_id, name=gsis_id, position=position, team='T',
        vor=vor, vor_rank=1, sim_mean=200.0,
        sim_p10=140.0, sim_p90=260.0, adp=adp,
        tier=tier, sim_boom_prob=0.2, sim_bust_prob=0.1,
    )


# --- Opponent rosters ---

def test_opponent_rosters_empty_pick_log():
    players = [_player('R1', 'RB', 50.0, 2.0, 1)]
    board = build_board_analysis(
        players=players,
        pick_log=[],
        current_pick=1,
        teams=12,
        user_pick_numbers=[6, 19, 30],
    )
    assert board.opponent_rosters == {}


def test_opponent_rosters_reconstructed_from_pick_log():
    players = [_player('R1', 'RB', 50.0, 5.0, 1)]
    pick_log = [
        ('Q1', 1, 'QB'),
        ('R2', 2, 'RB'),
        ('W1', 3, 'WR'),
        ('R3', 1, 'RB'),  # team 1 gets second RB
    ]
    board = build_board_analysis(
        players=players,
        pick_log=pick_log,
        current_pick=5,
        teams=12,
        user_pick_numbers=[6, 19, 30],
    )
    assert board.opponent_rosters[1]['QB'] == 1
    assert board.opponent_rosters[1]['RB'] == 1
    assert board.opponent_rosters[2]['RB'] == 1
    assert board.opponent_rosters[3]['WR'] == 1


# --- Run detection ---

def test_no_run_with_mixed_positions():
    players = [_player('R1', 'RB', 50.0, 5.0, 1)]
    pick_log = [
        ('Q1', 1, 'QB'),
        ('R2', 2, 'RB'),
        ('W1', 3, 'WR'),
        ('Q2', 4, 'QB'),
        ('W2', 5, 'WR'),
    ]
    board = build_board_analysis(
        players=players,
        pick_log=pick_log,
        current_pick=6,
        teams=12,
        user_pick_numbers=[6, 19, 30],
    )
    assert not board.per_position['RB'].run_in_progress


def test_run_detected_when_3_of_last_5_same_position():
    players = [_player('R1', 'RB', 50.0, 5.0, 1)]
    pick_log = [
        ('W1', 1, 'WR'),
        ('R2', 2, 'RB'),
        ('R3', 3, 'RB'),
        ('R4', 4, 'RB'),
        ('W2', 5, 'WR'),
    ]
    board = build_board_analysis(
        players=players,
        pick_log=pick_log,
        current_pick=6,
        teams=12,
        user_pick_numbers=[6, 19, 30],
    )
    assert board.per_position['RB'].run_in_progress


# --- Tier cliffs ---

def test_no_cliff_when_single_player():
    players = [_player('R1', 'RB', 50.0, 2.0, 1)]
    board = build_board_analysis(
        players=players, pick_log=[], current_pick=1,
        teams=12, user_pick_numbers=[6, 19, 30],
    )
    assert board.per_position['RB'].tier_cliffs == []


def test_no_cliff_when_all_same_tier():
    players = [
        _player('R1', 'RB', 60.0, 2.0, 1),
        _player('R2', 'RB', 50.0, 4.0, 1),
        _player('R3', 'RB', 40.0, 6.0, 1),
    ]
    board = build_board_analysis(
        players=players, pick_log=[], current_pick=1,
        teams=12, user_pick_numbers=[6, 19, 30],
    )
    assert board.per_position['RB'].tier_cliffs == []


def test_cliff_detected_at_tier_boundary():
    players = [
        _player('R1', 'RB', 60.0, 2.0, 1),
        _player('R2', 'RB', 50.0, 4.0, 1),
        _player('R3', 'RB', 20.0, 8.0, 2),  # tier jumps 1→2 here
        _player('R4', 'RB', 10.0, 10.0, 2),
    ]
    board = build_board_analysis(
        players=players, pick_log=[], current_pick=1,
        teams=12, user_pick_numbers=[6, 19, 30],
    )
    cliffs = board.per_position['RB'].tier_cliffs
    assert len(cliffs) == 1
    assert cliffs[0].before_player.gsis_id == 'R2'
    assert cliffs[0].after_player.gsis_id == 'R3'
    assert cliffs[0].tier_jump == 1
    assert cliffs[0].rank_at_cliff == 2  # R2 is position rank 2
    assert abs(cliffs[0].vor_drop - 30.0) < 0.01


def test_available_list_sorted_by_vor_desc():
    players = [
        _player('R3', 'RB', 30.0, 6.0, 2),
        _player('R1', 'RB', 60.0, 2.0, 1),
        _player('R2', 'RB', 45.0, 4.0, 1),
    ]
    board = build_board_analysis(
        players=players, pick_log=[], current_pick=1,
        teams=12, user_pick_numbers=[6, 19, 30],
    )
    ids = [p.gsis_id for p in board.per_position['RB'].available]
    assert ids == ['R1', 'R2', 'R3']
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd "/Users/theoauyeung/Documents/Projects/TAY Analytics FF" && python -m pytest tests/draft/test_board.py -v 2>&1 | tail -15
```

Expected: all tests FAIL with `ImportError` or `AttributeError` (function not yet implemented)

- [ ] **Step 3: Implement opponent rosters, run detection, tier cliffs, and `build_board_analysis` scaffold in `board.py`**

Add to `src/tay/draft/board.py` (after the imports and dataclasses):

```python
from tay.draft.scoring import future_availability


def _picking_team(overall_pick: int, teams: int) -> int:
    """Team number (1-indexed) picking at overall_pick in a snake draft."""
    pick_in_round = ((overall_pick - 1) % teams) + 1
    round_num = (overall_pick - 1) // teams + 1
    return pick_in_round if round_num % 2 == 1 else teams - pick_in_round + 1


def _find_tier_cliffs(players: list[PlayerProjection]) -> list[TierCliff]:
    """Detect where tier number increases in a VOR-sorted player list."""
    cliffs = []
    for i in range(len(players) - 1):
        curr, nxt = players[i], players[i + 1]
        if curr.tier is None or nxt.tier is None:
            continue
        if nxt.tier > curr.tier:
            cliffs.append(TierCliff(
                before_player=curr,
                after_player=nxt,
                vor_drop=curr.vor - nxt.vor,
                tier_jump=nxt.tier - curr.tier,
                rank_at_cliff=i + 1,   # 1-indexed
            ))
    return cliffs


def build_board_analysis(
    players: list[PlayerProjection],
    pick_log: list[tuple[str, int, str]],   # (gsis_id, team_number, position)
    current_pick: int,
    teams: int,
    user_pick_numbers: list[int],           # next 3 user pick numbers, len == 3
) -> BoardAnalysis:
    # 1. Opponent rosters
    opponent_rosters: dict[int, dict[str, int]] = {}
    for _gsis_id, team_num, position in pick_log:
        team_roster = opponent_rosters.setdefault(team_num, {})
        team_roster[position] = team_roster.get(position, 0) + 1

    # 2. Run detection — last 5 picks
    last5 = pick_log[-5:]
    run_positions: set[str] = set()
    for pos in {entry[2] for entry in last5}:
        if sum(1 for e in last5 if e[2] == pos) >= 3:
            run_positions.add(pos)

    # 3. Group available players by position, sort VOR desc
    by_position: dict[str, list[PlayerProjection]] = {}
    for p in players:
        by_position.setdefault(p.position, []).append(p)
    for pos_players in by_position.values():
        pos_players.sort(key=lambda p: p.vor, reverse=True)

    # 4. Teams picking before user at horizon 0
    teams_before_h0 = [
        _picking_team(pk, teams)
        for pk in range(current_pick, user_pick_numbers[0])
    ] if user_pick_numbers else []

    # 5. Build per-position state (survival probs filled in Task 3)
    per_position: dict[str, PositionBoardState] = {}
    for pos, pos_players in by_position.items():
        per_position[pos] = PositionBoardState(
            position=pos,
            available=pos_players,
            tier_cliffs=_find_tier_cliffs(pos_players),
            survival_probs={},           # populated in Task 3
            run_in_progress=(pos in run_positions),
        )

    return BoardAnalysis(
        per_position=per_position,
        opponent_rosters=opponent_rosters,
    )
```

- [ ] **Step 4: Run tests — all should pass (survival_probs is `{}` so Task 3 tests don't exist yet)**

```bash
cd "/Users/theoauyeung/Documents/Projects/TAY Analytics FF" && python -m pytest tests/draft/test_board.py -v 2>&1 | tail -20
```

Expected: all tests in this file PASS (survival_prob tests are in Task 3)

- [ ] **Step 5: Commit**

```bash
git add src/tay/draft/board.py tests/draft/test_board.py
git commit -m "feat: board.py opponent rosters, run detection, tier cliff detection"
```

---

## Task 3: `board.py` — survival probabilities

**Files:**
- Modify: `src/tay/draft/board.py`
- Modify: `tests/draft/test_board.py`

**Interfaces:**
- Produces: `build_board_analysis()` fully implemented — `survival_probs` dict populated for every player

- [ ] **Step 1: Add survival probability tests to `tests/draft/test_board.py`**

Append to the existing file:

```python
# --- Survival probabilities ---

def test_survival_prob_has_three_horizons():
    players = [_player('R1', 'RB', 50.0, 10.0, 1)]
    board = build_board_analysis(
        players=players, pick_log=[], current_pick=1,
        teams=12, user_pick_numbers=[6, 19, 30],
    )
    probs = board.per_position['RB'].survival_probs['R1']
    assert len(probs) == 3
    assert all(0.0 <= p <= 1.0 for p in probs)


def test_survival_prob_decreases_with_horizon():
    # Player with ADP=10 — further horizons are worse (more picks have happened)
    players = [_player('R1', 'RB', 50.0, 10.0, 1)]
    board = build_board_analysis(
        players=players, pick_log=[], current_pick=1,
        teams=12, user_pick_numbers=[6, 19, 30],
    )
    probs = board.per_position['RB'].survival_probs['R1']
    # Each horizon is further out → lower survival
    assert probs[0] >= probs[1] >= probs[2]


def test_hungry_opponents_reduce_survival_at_horizon0():
    # Compare: 5 teams picking before user with 0 RBs (hungry) vs user picks immediately (no teams before).
    # More hungry opponents → lower survival probability.
    players = [_player('R1', 'RB', 50.0, 20.0, 1)]

    # High demand: 5 teams pick before user, all with 0 RBs
    board_high_demand = build_board_analysis(
        players=players,
        pick_log=[],
        current_pick=1,
        teams=12,
        user_pick_numbers=[6, 19, 30],
    )

    # Low demand: user picks immediately next, no teams between current_pick and user pick
    board_low_demand = build_board_analysis(
        players=players,
        pick_log=[],
        current_pick=6,
        teams=12,
        user_pick_numbers=[6, 19, 30],
    )

    prob_high = board_high_demand.per_position['RB'].survival_probs['R1'][0]
    prob_low = board_low_demand.per_position['RB'].survival_probs['R1'][0]
    assert prob_low >= prob_high  # fewer hungry teams → higher survival


def test_run_in_progress_reduces_survival_at_horizon0():
    players = [_player('R1', 'RB', 50.0, 20.0, 1)]
    # No run
    board_no_run = build_board_analysis(
        players=players, pick_log=[], current_pick=1,
        teams=12, user_pick_numbers=[6, 19, 30],
    )
    # RB run: last 5 picks are RB
    run_picks = [('X', i + 1, 'RB') for i in range(5)]
    board_run = build_board_analysis(
        players=players,
        pick_log=run_picks,
        current_pick=6,
        teams=12,
        user_pick_numbers=[12, 25, 36],
    )
    p_no_run = board_no_run.per_position['RB'].survival_probs['R1'][0]
    p_run = board_run.per_position['RB'].survival_probs['R1'][0]
    assert p_run <= p_no_run  # run increases demand → lower survival
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd "/Users/theoauyeung/Documents/Projects/TAY Analytics FF" && python -m pytest tests/draft/test_board.py::test_survival_prob_has_three_horizons -v 2>&1 | tail -10
```

Expected: FAIL (survival_probs is `{}`)

- [ ] **Step 3: Implement survival probability computation in `build_board_analysis`**

Replace the `# 5. Build per-position state` block in `build_board_analysis` with:

```python
    # 5. Build per-position state with survival probabilities
    per_position: dict[str, PositionBoardState] = {}
    for pos, pos_players in by_position.items():
        # Hungry teams: teams picking before user at horizon 0 with ≤ 1 player at this position
        hungry = sum(
            1 for t in teams_before_h0
            if opponent_rosters.get(t, {}).get(pos, 0) <= 1
        )
        run_active = pos in run_positions

        survival_probs: dict[str, list[float]] = {}
        for p in pos_players:
            probs: list[float] = []
            for h, horizon_pick in enumerate(user_pick_numbers[:3]):
                picks_until = max(0, horizon_pick - current_pick)
                base = future_availability(p, current_pick, picks_until)
                if h == 0:
                    demand = hungry * 0.05
                    if run_active:
                        demand += len(teams_before_h0) * 0.03
                    base = max(0.0, min(1.0, base - demand))
                probs.append(base)
            survival_probs[p.gsis_id] = probs

        per_position[pos] = PositionBoardState(
            position=pos,
            available=pos_players,
            tier_cliffs=_find_tier_cliffs(pos_players),
            survival_probs=survival_probs,
            run_in_progress=run_active,
        )
```

- [ ] **Step 4: Run all board tests**

```bash
cd "/Users/theoauyeung/Documents/Projects/TAY Analytics FF" && python -m pytest tests/draft/test_board.py -v 2>&1 | tail -20
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/tay/draft/board.py tests/draft/test_board.py
git commit -m "feat: board.py survival probabilities with opponent pressure and run detection"
```

---

## Task 4: `models.py` — new types, updated Recommendation, extended DraftState and RecommendationState

**Files:**
- Modify: `src/tay/draft/models.py`

**Interfaces:**
- Produces:
  - `WaitScenario(position, best_now_name, best_now_vor, expected_vor_at_next_pick, vor_cost_of_waiting, cliff_before_next_pick, survival_probability)`
  - `NextRoundPositionSummary(position, strong_options_remaining, next_cliff_rank, cliff_warning)`
  - `DraftState.pick_log: list[tuple[str, int, str]]` (default `[]`)
  - `Recommendation.explanation: list[dict[str, str]]` (was `list[str]`)
  - `RecommendationState.wait_analysis: list[WaitScenario]`
  - `RecommendationState.next_round_board: dict[str, NextRoundPositionSummary]`

- [ ] **Step 1: Update `src/tay/draft/models.py`**

Replace the full file contents:

```python
"""Pure dataclasses for draft engine inputs and outputs."""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class LeagueSettings:
    teams: int = 12
    scoring: str = 'ppr'
    roster_config: dict[str, int] = field(
        default_factory=lambda: {'QB': 1, 'RB': 2, 'WR': 2, 'TE': 1, 'FLEX': 1}
    )


@dataclass
class DraftState:
    season: int
    model_version: str
    league_settings: LeagueSettings
    current_pick: int          # 1-indexed overall pick number
    total_picks: int           # league_size * rounds (e.g. 12 * 15 = 180)
    user_pick_position: int    # 1-indexed draft slot (1 = first pick overall in round 1)
    drafted_ids: list[str]     # gsis_ids already taken (all teams)
    user_roster: dict[str, list[str]]  # position -> list of gsis_ids
    pick_log: list[tuple[str, int, str]] = field(default_factory=list)  # (gsis_id, team_num, position)

    @property
    def round(self) -> int:
        return (self.current_pick - 1) // self.league_settings.teams + 1

    @property
    def pick_in_round(self) -> int:
        return (self.current_pick - 1) % self.league_settings.teams + 1

    @property
    def picks_until_next(self) -> int:
        """Picks remaining until user's next turn (0 = it's their turn now)."""
        teams = self.league_settings.teams
        pick_in_round = self.pick_in_round
        current_round = self.round
        if current_round % 2 == 1:
            user_pick_in_round = self.user_pick_position
        else:
            user_pick_in_round = teams - self.user_pick_position + 1
        if user_pick_in_round >= pick_in_round:
            return user_pick_in_round - pick_in_round
        next_round = current_round + 1
        if next_round % 2 == 1:
            next_user_pick = self.user_pick_position
        else:
            next_user_pick = teams - self.user_pick_position + 1
        picks_to_end_of_round = teams - pick_in_round + 1
        return picks_to_end_of_round + next_user_pick - 1


@dataclass
class PlayerProjection:
    gsis_id: str
    name: str
    position: str
    team: str
    vor: float
    vor_rank: int
    sim_mean: float
    sim_p10: float
    sim_p90: float
    adp: float
    tier: int | None
    sim_boom_prob: float
    sim_bust_prob: float


@dataclass
class Recommendation:
    player: PlayerProjection
    draft_score: float
    roster_fit: float
    positional_urgency: float          # scarcity_premium value [0, 0.5]
    future_availability_pct: float     # P(still available at next pick)
    explanation: list[dict[str, str]]  # [{factor, detail, weight}, ...]


@dataclass
class WaitScenario:
    position: str
    best_now_name: str
    best_now_vor: float
    expected_vor_at_next_pick: float
    vor_cost_of_waiting: float         # best_now_vor - expected_vor_at_next_pick
    cliff_before_next_pick: bool
    survival_probability: float        # P(best_now still available at next pick)


@dataclass
class NextRoundPositionSummary:
    position: str
    strong_options_remaining: int      # tier ≤ 3 players with survival_prob > 0.3
    next_cliff_rank: int | None        # position rank of the next tier cliff
    cliff_warning: bool                # cliff within top 4 position ranks


@dataclass
class RecommendationState:
    top_pick: Recommendation
    alternatives: list[Recommendation]
    positional_needs: list[str]                             # positions by urgency
    may_not_make_it_back: list[PlayerProjection]
    wait_analysis: list[WaitScenario]
    next_round_board: dict[str, NextRoundPositionSummary]
    board_state: dict                                        # {current_pick, round, picks_until_next}
```

- [ ] **Step 2: Verify existing draft tests still import cleanly**

```bash
cd "/Users/theoauyeung/Documents/Projects/TAY Analytics FF" && python -m pytest tests/draft/test_models.py -v 2>&1 | tail -10
```

Expected: PASS (models tests only check dataclass structure)

- [ ] **Step 3: Commit**

```bash
git add src/tay/draft/models.py
git commit -m "feat: models.py — WaitScenario, NextRoundPositionSummary, pick_log on DraftState, structured Recommendation.explanation"
```

---

## Task 5: `schemas.py` + router — `PickEntry` and `pick_log` in API

**Files:**
- Modify: `src/tay/api/schemas.py`
- Modify: `src/tay/api/routers/draft.py`

**Interfaces:**
- Produces: `DraftStateIn.pick_log: list[PickEntry]` replaces `drafted_ids`; router derives both `drafted_ids` and `pick_log` for `DraftState`

- [ ] **Step 1: Update `src/tay/api/schemas.py`**

Replace only the `# ── Draft` section (lines 95 onward):

```python
# ── Draft ─────────────────────────────────────────────────────────────────────

class LeagueSettingsSchema(BaseModel):
    teams: int = 12
    scoring: str = 'ppr'
    roster_config: dict[str, int] = Field(
        default_factory=lambda: {'QB': 1, 'RB': 2, 'WR': 2, 'TE': 1, 'FLEX': 1}
    )


class PickEntry(BaseModel):
    gsis_id: str
    team_number: int
    position: str


class DraftStateIn(BaseModel):
    season: int = 2026
    model_version: str = 'neural-v1'
    league_settings: LeagueSettingsSchema = Field(default_factory=LeagueSettingsSchema)
    current_pick: int = 1
    total_picks: int = 180
    user_pick_position: int = 1
    pick_log: list[PickEntry] = Field(default_factory=list)
    user_roster: dict[str, list[str]] = Field(
        default_factory=lambda: {'QB': [], 'RB': [], 'WR': [], 'TE': [], 'FLEX': []}
    )


class SessionIn(BaseModel):
    session_id: str
    state: DraftStateIn


class SessionOut(BaseModel):
    session_id: str
    league_settings: dict | None
    picks: list[str] | None
    completed: bool
```

- [ ] **Step 2: Update `_to_draft_state` in `src/tay/api/routers/draft.py`**

Replace the `_to_draft_state` function:

```python
def _to_draft_state(body: DraftStateIn) -> DraftState:
    ls = DraftLeagueSettings(
        teams=body.league_settings.teams,
        scoring=body.league_settings.scoring,
        roster_config=body.league_settings.roster_config,
    )
    drafted_ids = [e.gsis_id for e in body.pick_log]
    pick_log = [(e.gsis_id, e.team_number, e.position) for e in body.pick_log]
    return DraftState(
        season=body.season,
        model_version=body.model_version,
        league_settings=ls,
        current_pick=body.current_pick,
        total_picks=body.total_picks,
        user_pick_position=body.user_pick_position,
        drafted_ids=drafted_ids,
        user_roster={k: list(v) for k, v in body.user_roster.items()},
        pick_log=pick_log,
    )
```

Also add the `PickEntry` import at the top of the router (it's used indirectly via `DraftStateIn`):

```python
from tay.api.schemas import DraftStateIn, SessionIn, SessionOut
```

(No change needed — `PickEntry` is not directly imported in the router.)

- [ ] **Step 3: Verify the API still imports cleanly**

```bash
cd "/Users/theoauyeung/Documents/Projects/TAY Analytics FF" && python -c "from tay.api.routers.draft import router; print('ok')"
```

Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add src/tay/api/schemas.py src/tay/api/routers/draft.py
git commit -m "feat: PickEntry schema, replace drafted_ids with pick_log in DraftStateIn"
```

---

## Task 6: `scoring.py` — update `score_player` to use `BoardAnalysis`

**Files:**
- Modify: `src/tay/draft/scoring.py`
- Modify: `tests/draft/test_scoring.py`

**Interfaces:**
- Consumes: `BoardAnalysis` from `tay.draft.board`
- Produces: `score_player(player, state, board) -> Recommendation` with structured explanation `[{factor, detail, weight}]`
- `positional_urgency()` is removed; `future_availability()` is kept (used by `board.py`)

- [ ] **Step 1: Update `tests/draft/test_scoring.py`**

Replace the full file:

```python
from __future__ import annotations
import pytest
from tay.draft.models import LeagueSettings, DraftState, PlayerProjection
from tay.draft.scoring import future_availability, score_player
from tay.draft.board import BoardAnalysis, PositionBoardState, TierCliff


def _player(
    gsis_id='X', position='RB', vor=50.0, vor_rank=10,
    adp=15.0, sim_boom_prob=0.2, tier=2,
):
    return PlayerProjection(
        gsis_id=gsis_id, name='Test', position=position, team='T',
        vor=vor, vor_rank=vor_rank, sim_mean=200.0,
        sim_p10=140.0, sim_p90=260.0, adp=adp, tier=tier,
        sim_boom_prob=sim_boom_prob, sim_bust_prob=0.1,
    )


def _state(current_pick=1, user_roster=None):
    ls = LeagueSettings()
    return DraftState(
        season=2026, model_version='neural-v1', league_settings=ls,
        current_pick=current_pick, total_picks=180, user_pick_position=1,
        drafted_ids=[],
        user_roster=user_roster or {'QB': [], 'RB': [], 'WR': [], 'TE': [], 'FLEX': []},
    )


def _board(
    player: PlayerProjection,
    survival_prob: float = 0.5,
    tier_cliffs: list[TierCliff] | None = None,
    extra_tier3_players: int = 8,   # top-tier count in position
) -> BoardAnalysis:
    """Minimal BoardAnalysis with one position group containing the test player."""
    tier3_players = [
        PlayerProjection(
            gsis_id=f'filler_{i}', name='F', position=player.position, team='T',
            vor=5.0, vor_rank=99, sim_mean=100.0, sim_p10=60.0, sim_p90=140.0,
            adp=50.0 + i, tier=2, sim_boom_prob=0.1, sim_bust_prob=0.1,
        )
        for i in range(extra_tier3_players)
    ]
    available = [player] + tier3_players
    pos_board = PositionBoardState(
        position=player.position,
        available=available,
        tier_cliffs=tier_cliffs or [],
        survival_probs={
            **{player.gsis_id: [survival_prob, survival_prob * 0.8, survival_prob * 0.6]},
            **{p.gsis_id: [0.5, 0.4, 0.3] for p in tier3_players},
        },
        run_in_progress=False,
    )
    return BoardAnalysis(per_position={player.position: pos_board}, opponent_rosters={})


# --- future_availability (kept as utility) ---

def test_future_availability_high_adp_relative_to_picks():
    p = _player(adp=100.0)
    fa = future_availability(p, current_pick=1, picks_until_next=2)
    assert fa > 0.9


def test_future_availability_low_adp_relative_to_picks():
    p = _player(adp=3.0)
    fa = future_availability(p, current_pick=1, picks_until_next=10)
    assert fa < 0.5


def test_future_availability_clamped_to_unit_interval():
    p = _player(adp=1.0)
    assert 0.0 <= future_availability(p, current_pick=1, picks_until_next=100) <= 1.0


# --- score_player ---

def test_score_player_returns_recommendation():
    p = _player(vor=80.0, adp=5.0, vor_rank=3)
    board = _board(p, survival_prob=0.4)
    rec = score_player(p, _state(), board)
    assert rec.player is p
    assert rec.draft_score > 0
    assert isinstance(rec.explanation, list)
    assert len(rec.explanation) >= 1


def test_score_player_explanation_is_structured():
    p = _player(vor=80.0, adp=5.0, vor_rank=3)
    board = _board(p)
    rec = score_player(p, _state(), board)
    for ex in rec.explanation:
        assert 'factor' in ex
        assert 'detail' in ex
        assert 'weight' in ex
        assert ex['weight'] in ('primary', 'secondary', 'risk')


def test_score_player_high_vor_produces_primary_explanation():
    p = _player(vor=80.0)
    board = _board(p)
    rec = score_player(p, _state(), board)
    assert any(e['weight'] == 'primary' for e in rec.explanation)


def test_cliff_premium_fires_when_player_is_last_in_tier():
    p = _player(gsis_id='CLIFF_PLAYER', vor=40.0, tier=1)
    next_p = _player(gsis_id='NEXT_PLAYER', vor=20.0, tier=2)
    cliff = TierCliff(
        before_player=p, after_player=next_p,
        vor_drop=20.0, tier_jump=1, rank_at_cliff=1,
    )
    board = _board(p, tier_cliffs=[cliff])
    rec = score_player(p, _state(), board)
    assert any('Cliff' in e['factor'] or 'cliff' in e['factor'].lower() for e in rec.explanation)


def test_no_cliff_premium_when_player_not_at_cliff():
    p = _player(gsis_id='MID_PLAYER', vor=50.0, tier=1)
    cliff_player = _player(gsis_id='CLIFF_PLAYER', vor=30.0, tier=1)
    next_p = _player(gsis_id='NEXT', vor=10.0, tier=2)
    cliff = TierCliff(
        before_player=cliff_player, after_player=next_p,
        vor_drop=20.0, tier_jump=1, rank_at_cliff=2,
    )
    board = _board(p, tier_cliffs=[cliff])
    rec_with_cliff = score_player(p, _state(), board)
    # Cliff premium should NOT be applied to MID_PLAYER (only CLIFF_PLAYER gets it)
    no_cliff_board = _board(p, tier_cliffs=[])
    rec_no_cliff = score_player(p, _state(), no_cliff_board)
    # Scores should be equal (no cliff premium)
    assert abs(rec_with_cliff.draft_score - rec_no_cliff.draft_score) < 0.01


def test_scarcity_premium_increases_when_tier3_pool_thin():
    p = _player(vor=40.0, tier=1)
    board_full = _board(p, extra_tier3_players=8)   # at threshold → premium=0
    board_thin = _board(p, extra_tier3_players=0)   # exhausted → premium=0.5
    rec_full = score_player(p, _state(), board_full)
    rec_thin = score_player(p, _state(), board_thin)
    assert rec_thin.draft_score > rec_full.draft_score


def test_low_survival_produces_risk_explanation():
    p = _player(vor=40.0, adp=5.0)
    board = _board(p, survival_prob=0.2)  # 20% → at risk
    rec = score_player(p, _state(), board)
    assert any(e['weight'] == 'risk' for e in rec.explanation)


def test_score_player_explanation_undervalued():
    # adp - vor_rank = 50 - 5 = 45 > 15 → undervalued explanation
    p = _player(vor=60.0, adp=50.0, vor_rank=5)
    board = _board(p)
    rec = score_player(p, _state(), board)
    assert any('Undervalued' in e['factor'] for e in rec.explanation)


def test_roster_fit_bonus_applied():
    p = _player(position='RB', vor=40.0)
    empty_roster = {'QB': [], 'RB': [], 'WR': [], 'TE': [], 'FLEX': []}
    full_roster = {'QB': ['q1'], 'RB': ['r1', 'r2', 'r3'], 'WR': ['w1', 'w2'], 'TE': ['t1'], 'FLEX': []}
    board = _board(p)
    rec_empty = score_player(p, _state(user_roster=empty_roster), board)
    rec_full = score_player(p, _state(user_roster=full_roster), board)
    assert rec_empty.draft_score > rec_full.draft_score
```

- [ ] **Step 2: Run tests — expect failures**

```bash
cd "/Users/theoauyeung/Documents/Projects/TAY Analytics FF" && python -m pytest tests/draft/test_scoring.py -v 2>&1 | tail -20
```

Expected: multiple FAIL (old `score_player` signature and `positional_urgency` still exist)

- [ ] **Step 3: Rewrite `src/tay/draft/scoring.py`**

```python
"""Draft Score formula — stateless scoring of available players."""
from __future__ import annotations
from tay.draft.models import DraftState, PlayerProjection, Recommendation

_FLEX_ELIGIBLE = {'RB', 'WR', 'TE'}
_STARTER_REQUIREMENTS = {'QB': 1, 'RB': 2, 'WR': 2, 'TE': 1}
_FLEX_SPOTS = 1
_SCARCITY_THRESHOLDS: dict[str, int] = {'QB': 4, 'TE': 4, 'RB': 8, 'WR': 8}


def future_availability(player: PlayerProjection, current_pick: int, picks_until_next: int) -> float:
    """P(player still available at user's next pick). High = can wait, Low = must take now."""
    next_pick = current_pick + picks_until_next
    adp = player.adp
    if adp <= 0 or adp >= 500:
        return 1.0
    adp_std = max(2.0, adp * 0.25)
    z = (next_pick - adp) / adp_std
    return max(0.0, min(1.0, 0.5 - 0.25 * z))


def roster_fit(
    player: PlayerProjection,
    user_roster: dict[str, list[str]],
    roster_config: dict[str, int] | None = None,
) -> float:
    """Multiplier [0.5, 1.2] for how well player fills user's roster needs."""
    pos = player.position
    requirements = roster_config if roster_config is not None else _STARTER_REQUIREMENTS
    filled = len(user_roster.get(pos, []))
    required = requirements.get(pos, 1)

    score = 1.0
    if filled == 0:
        score += 0.2
    elif pos in _FLEX_ELIGIBLE:
        total_skill_filled = sum(len(user_roster.get(p, [])) for p in _FLEX_ELIGIBLE)
        total_skill_required = sum(requirements.get(p, 0) for p in _FLEX_ELIGIBLE) + _FLEX_SPOTS
        if filled >= required and total_skill_filled >= total_skill_required:
            score -= 0.3
    else:
        if filled >= required:
            score -= 0.3

    return max(0.5, min(1.2, score))


def score_player(
    player: PlayerProjection,
    state: DraftState,
    board: 'BoardAnalysis',
) -> Recommendation:
    """Compute Draft Score and structured explanation for one player."""
    from tay.draft.board import BoardAnalysis  # local import avoids circular dependency

    pos_board = board.per_position.get(player.position)

    # Survival probability (next pick)
    if pos_board and player.gsis_id in pos_board.survival_probs:
        survival_prob = pos_board.survival_probs[player.gsis_id][0]
    else:
        survival_prob = future_availability(player, state.current_pick, state.picks_until_next)

    # Cliff premium: +0.3 if player is the last in their tier
    cliff_premium = 0.0
    cliff_ids: set[str] = set()
    if pos_board:
        cliff_ids = {cliff.before_player.gsis_id for cliff in pos_board.tier_cliffs}
        if player.gsis_id in cliff_ids:
            cliff_premium = 0.3

    # Scarcity premium: 0–0.5 based on remaining tier-1-through-3 players
    scarcity_premium = 0.0
    if pos_board:
        threshold = _SCARCITY_THRESHOLDS.get(player.position, 8)
        top_tier_count = sum(1 for p in pos_board.available if (p.tier or 5) <= 3)
        scarcity_premium = max(0.0, min(0.5, 0.5 * (1.0 - top_tier_count / threshold)))

    rf = roster_fit(player, state.user_roster, state.league_settings.roster_config)
    urgency_factor = 1.0 + cliff_premium + scarcity_premium
    now_vs_wait = 1.5 - 0.5 * survival_prob

    draft_score = player.vor * urgency_factor * rf * now_vs_wait

    # QB patience suppression
    if player.position == 'QB' and len(state.user_roster.get('QB', [])) == 0:
        user_skill_count = sum(
            len(state.user_roster.get(p, [])) for p in ('RB', 'WR', 'TE')
        )
        if user_skill_count < 4 and state.current_pick <= state.league_settings.teams * 7:
            draft_score *= 0.5

    # Structured explanation
    explanation: list[dict[str, str]] = []

    if player.vor > 20:
        explanation.append({
            'factor': 'High Value',
            'detail': f'{player.vor:.0f} VOR points above replacement',
            'weight': 'primary',
        })

    if cliff_premium > 0:
        explanation.append({
            'factor': 'Tier Cliff',
            'detail': f'Last available {player.position} in this tier — next group is significantly weaker',
            'weight': 'primary',
        })

    if survival_prob < 0.35:
        gone_pct = round((1 - survival_prob) * 100)
        explanation.append({
            'factor': 'At Risk',
            'detail': f'{gone_pct}% chance gone before your next pick',
            'weight': 'risk',
        })

    if scarcity_premium > 0.3 and pos_board:
        top_tier = sum(1 for p in pos_board.available if (p.tier or 5) <= 3)
        explanation.append({
            'factor': 'Positional Scarcity',
            'detail': f'Only {top_tier} quality {player.position}s remain',
            'weight': 'primary',
        })

    if player.adp - player.vor_rank > 15:
        explanation.append({
            'factor': 'Undervalued',
            'detail': f'ADP {player.adp:.0f} vs model rank #{player.vor_rank}',
            'weight': 'secondary',
        })

    if player.sim_boom_prob > 0.3:
        explanation.append({
            'factor': 'Upside',
            'detail': f'{player.sim_boom_prob:.0%} boom probability',
            'weight': 'secondary',
        })

    if not explanation:
        explanation.append({
            'factor': 'Solid Value',
            'detail': f'Good pick at position {state.current_pick}',
            'weight': 'secondary',
        })

    return Recommendation(
        player=player,
        draft_score=draft_score,
        roster_fit=rf,
        positional_urgency=scarcity_premium,
        future_availability_pct=survival_prob,
        explanation=explanation,
    )
```

- [ ] **Step 4: Run scoring tests**

```bash
cd "/Users/theoauyeung/Documents/Projects/TAY Analytics FF" && python -m pytest tests/draft/test_scoring.py -v 2>&1 | tail -25
```

Expected: all PASS

- [ ] **Step 5: Run full test suite — expect some engine/API failures (next task)**

```bash
cd "/Users/theoauyeung/Documents/Projects/TAY Analytics FF" && python -m pytest tests/ -v --tb=short 2>&1 | tail -30
```

Expected: `test_scoring.py` and `test_board.py` pass; `test_engine.py` and `test_draft.py` fail (old signature)

- [ ] **Step 6: Commit**

```bash
git add src/tay/draft/scoring.py tests/draft/test_scoring.py
git commit -m "feat: scoring.py — BoardAnalysis-based score_player, cliff/scarcity premium, structured explanations"
```

---

## Task 7: `engine.py` — wire board analysis, build wait analysis and next round board

**Files:**
- Modify: `src/tay/draft/engine.py`
- Modify: `tests/draft/test_engine.py`

**Interfaces:**
- Consumes: `build_board_analysis` from `tay.draft.board`, `score_player` from `tay.draft.scoring`
- Produces: `recommend(conn, state) -> RecommendationState` with `wait_analysis` and `next_round_board` populated

- [ ] **Step 1: Add new assertions to `tests/draft/test_engine.py`**

Update `_state()` helper to add `pick_log` default, then append new tests at the bottom of the existing file:

Replace `_state` function:
```python
def _state(drafted_ids=None, current_pick=1, user_roster=None, pick_log=None):
    ls = LeagueSettings()
    return DraftState(
        season=2026, model_version='test-v1', league_settings=ls,
        current_pick=current_pick, total_picks=180, user_pick_position=1,
        drafted_ids=drafted_ids or [],
        user_roster=user_roster or {'QB': [], 'RB': [], 'WR': [], 'TE': [], 'FLEX': []},
        pick_log=pick_log or [],
    )
```

Append to the file:
```python
def test_recommend_has_wait_analysis():
    conn = _make_db()
    state = _state()
    result = recommend(conn, state)
    assert hasattr(result, 'wait_analysis')
    assert isinstance(result.wait_analysis, list)
    conn.close()


def test_recommend_has_next_round_board():
    conn = _make_db()
    state = _state()
    result = recommend(conn, state)
    assert hasattr(result, 'next_round_board')
    assert isinstance(result.next_round_board, dict)
    conn.close()


def test_wait_analysis_positions_in_top_picks():
    conn = _make_db()
    state = _state()
    result = recommend(conn, state)
    # wait_analysis positions must be a subset of positions in top 5
    top5_positions = {r.player.position for r in [result.top_pick] + list(result.alternatives)}
    wait_positions = {w.position for w in result.wait_analysis}
    assert wait_positions.issubset(top5_positions)
    conn.close()


def test_next_round_board_has_all_positions():
    conn = _make_db()
    state = _state()
    result = recommend(conn, state)
    # Should have at least QB, RB, WR (3 positions in the test DB)
    assert len(result.next_round_board) >= 2
    conn.close()


def test_wait_analysis_vor_cost_non_negative():
    conn = _make_db()
    state = _state()
    result = recommend(conn, state)
    for scenario in result.wait_analysis:
        assert scenario.vor_cost_of_waiting >= -5.0  # allow small floating point
    conn.close()
```

- [ ] **Step 2: Run new tests — expect failures**

```bash
cd "/Users/theoauyeung/Documents/Projects/TAY Analytics FF" && python -m pytest tests/draft/test_engine.py::test_recommend_has_wait_analysis -v 2>&1 | tail -10
```

Expected: FAIL (`recommend()` doesn't return wait_analysis yet)

- [ ] **Step 3: Rewrite `src/tay/draft/engine.py`**

```python
"""Recommendation engine — loads projections and scores available players."""
from __future__ import annotations
import duckdb

from tay.draft.board import build_board_analysis
from tay.draft.models import (
    DraftState, PlayerProjection, RecommendationState,
    WaitScenario, NextRoundPositionSummary,
)
from tay.draft.scoring import score_player

_LOAD_SQL = """
    SELECT pr.gsis_id, p.name, p.position, p.team,
           COALESCE(pr.vor, 0.0),
           COALESCE(pr.vor_rank, 9999),
           COALESCE(pr.sim_mean, pr.mean_projection, 0.0),
           COALESCE(pr.sim_p10, pr.p10, 0.0),
           COALESCE(pr.sim_p90, pr.p90, 0.0),
           COALESCE(a.adp, 999.0),
           pr.tier,
           COALESCE(pr.sim_boom_prob, 0.0),
           COALESCE(pr.sim_bust_prob, 0.0)
    FROM projections pr
    JOIN players p ON p.gsis_id = pr.gsis_id
    LEFT JOIN adp a ON a.gsis_id = pr.gsis_id
                   AND a.season = pr.season
                   AND a.format = 'ppr'
                   AND a.platform = 'espn'
                   AND a.adp NOT IN (999, 9999999)
    WHERE pr.season = ? AND pr.model_version = ?
      AND p.position IN ('QB', 'RB', 'WR', 'TE')
    ORDER BY pr.vor DESC NULLS LAST
"""


def load_projections(
    conn: duckdb.DuckDBPyConnection,
    season: int,
    model_version: str,
    drafted_ids: list[str],
) -> list[PlayerProjection]:
    rows = conn.execute(_LOAD_SQL, [season, model_version]).fetchall()
    drafted_set = set(drafted_ids)
    return [
        PlayerProjection(
            gsis_id=r[0], name=r[1], position=r[2], team=r[3],
            vor=r[4], vor_rank=r[5], sim_mean=r[6],
            sim_p10=r[7], sim_p90=r[8], adp=r[9],
            tier=r[10], sim_boom_prob=r[11], sim_bust_prob=r[12],
        )
        for r in rows if r[0] not in drafted_set
    ]


def _compute_next_user_picks(state: DraftState, n: int = 3) -> list[int]:
    """Next n overall pick numbers for the user in a snake draft."""
    teams = state.league_settings.teams
    picks: list[int] = []
    pick = state.current_pick
    while len(picks) < n and pick <= state.total_picks:
        round_num = (pick - 1) // teams + 1
        pick_in_round = ((pick - 1) % teams) + 1
        user_pick_in_round = (
            state.user_pick_position if round_num % 2 == 1
            else teams - state.user_pick_position + 1
        )
        if pick_in_round == user_pick_in_round:
            picks.append(pick)
        pick += 1
    while len(picks) < n:
        picks.append(state.total_picks + 1)
    return picks


def _build_wait_analysis(board, scored: list) -> list[WaitScenario]:
    """One WaitScenario per unique position in the top 5 scored players."""
    from tay.draft.board import BoardAnalysis
    top5_positions = list(dict.fromkeys(r.player.position for r in scored[:5]))
    scenarios: list[WaitScenario] = []

    for pos in top5_positions:
        pos_board = board.per_position.get(pos)
        if not pos_board or not pos_board.available:
            continue
        best = pos_board.available[0]
        survivals = [
            pos_board.survival_probs.get(p.gsis_id, [0.5])[0]
            for p in pos_board.available
        ]
        total_survival = sum(survivals)
        if total_survival > 0:
            expected_vor = sum(
                p.vor * s for p, s in zip(pos_board.available, survivals)
            ) / total_survival
        else:
            expected_vor = 0.0

        cliff_ids = {cliff.before_player.gsis_id for cliff in pos_board.tier_cliffs}
        survival_prob = pos_board.survival_probs.get(best.gsis_id, [0.5])[0]

        scenarios.append(WaitScenario(
            position=pos,
            best_now_name=best.name,
            best_now_vor=round(best.vor, 1),
            expected_vor_at_next_pick=round(expected_vor, 1),
            vor_cost_of_waiting=round(best.vor - expected_vor, 1),
            cliff_before_next_pick=(best.gsis_id in cliff_ids),
            survival_probability=round(survival_prob, 3),
        ))
    return scenarios


def _build_next_round_board(board) -> dict[str, NextRoundPositionSummary]:
    """Summary of what each position's board will look like at the user's next pick."""
    result: dict[str, NextRoundPositionSummary] = {}
    for pos, pos_board in board.per_position.items():
        strong = sum(
            1 for p in pos_board.available
            if (p.tier or 5) <= 3
            and pos_board.survival_probs.get(p.gsis_id, [0.5])[0] > 0.3
        )
        next_cliff = pos_board.tier_cliffs[0] if pos_board.tier_cliffs else None
        result[pos] = NextRoundPositionSummary(
            position=pos,
            strong_options_remaining=strong,
            next_cliff_rank=next_cliff.rank_at_cliff if next_cliff else None,
            cliff_warning=(next_cliff is not None and next_cliff.rank_at_cliff <= 4),
        )
    return result


def recommend(
    conn: duckdb.DuckDBPyConnection,
    state: DraftState,
) -> RecommendationState:
    players = load_projections(conn, state.season, state.model_version, state.drafted_ids)

    user_pick_numbers = _compute_next_user_picks(state, n=3)

    board = build_board_analysis(
        players=players,
        pick_log=state.pick_log,
        current_pick=state.current_pick,
        teams=state.league_settings.teams,
        user_pick_numbers=user_pick_numbers,
    )

    scored = [score_player(p, state, board) for p in players]
    scored.sort(key=lambda r: r.draft_score, reverse=True)

    if not scored:
        raise ValueError(
            f'No available players for season={state.season} model={state.model_version}'
        )

    top_pick = scored[0]
    alternatives = scored[1:4]

    wait_analysis = _build_wait_analysis(board, scored)
    next_round_board = _build_next_round_board(board)

    # Sort positions by average scarcity premium (positional_urgency field)
    positional_needs = sorted(
        board.per_position.keys(),
        key=lambda pos: (
            sum(r.positional_urgency for r in scored if r.player.position == pos)
            / max(1, sum(1 for r in scored if r.player.position == pos))
        ),
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

- [ ] **Step 4: Run all draft tests**

```bash
cd "/Users/theoauyeung/Documents/Projects/TAY Analytics FF" && python -m pytest tests/draft/ -v 2>&1 | tail -30
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/tay/draft/engine.py tests/draft/test_engine.py
git commit -m "feat: engine.py — BoardAnalysis pipeline, build_wait_analysis, build_next_round_board"
```

---

## Task 8: API test — update fixture and assert new response fields

**Files:**
- Modify: `tests/api/test_draft.py`

- [ ] **Step 1: Update `tests/api/test_draft.py`**

Replace the `_STATE` fixture at the top, and add assertions for `wait_analysis` and `next_round_board`:

```python
"""Tests for draft endpoints: recommend, simulate, session save/load."""
from __future__ import annotations
import json
from tests.api.conftest import client


_STATE = {
    'season': 2026,
    'model_version': 'neural-v1',
    'league_settings': {
        'teams': 12,
        'scoring': 'ppr',
        'roster_config': {'QB': 1, 'RB': 2, 'WR': 2, 'TE': 1, 'FLEX': 1},
    },
    'current_pick': 1,
    'total_picks': 180,
    'user_pick_position': 1,
    'pick_log': [],
    'user_roster': {'QB': [], 'RB': [], 'WR': [], 'TE': [], 'FLEX': []},
}


def test_draft_recommend_returns_200():
    r = client.post('/draft/recommend', json=_STATE)
    assert r.status_code == 200


def test_draft_recommend_has_top_pick():
    r = client.post('/draft/recommend', json=_STATE)
    data = r.json()
    assert 'top_pick' in data
    assert 'player' in data['top_pick']
    assert 'draft_score' in data['top_pick']


def test_draft_recommend_has_alternatives():
    r = client.post('/draft/recommend', json=_STATE)
    data = r.json()
    assert 'alternatives' in data
    assert isinstance(data['alternatives'], list)


def test_draft_recommend_has_board_state():
    r = client.post('/draft/recommend', json=_STATE)
    data = r.json()
    assert 'board_state' in data
    bs = data['board_state']
    assert bs['current_pick'] == 1
    assert bs['round'] == 1


def test_draft_recommend_has_wait_analysis():
    r = client.post('/draft/recommend', json=_STATE)
    data = r.json()
    assert 'wait_analysis' in data
    assert isinstance(data['wait_analysis'], list)


def test_draft_recommend_has_next_round_board():
    r = client.post('/draft/recommend', json=_STATE)
    data = r.json()
    assert 'next_round_board' in data
    assert isinstance(data['next_round_board'], dict)


def test_draft_recommend_explanation_is_structured():
    r = client.post('/draft/recommend', json=_STATE)
    data = r.json()
    explanation = data['top_pick']['explanation']
    assert isinstance(explanation, list)
    if explanation:
        ex = explanation[0]
        assert 'factor' in ex
        assert 'detail' in ex
        assert 'weight' in ex


def test_draft_recommend_pick_log_accepted():
    state = {
        **_STATE,
        'pick_log': [
            {'gsis_id': 'nonexistent-1', 'team_number': 2, 'position': 'RB'},
        ],
    }
    r = client.post('/draft/recommend', json=state)
    assert r.status_code == 200


def test_draft_simulate_returns_501():
    r = client.post('/draft/simulate', json={})
    assert r.status_code == 501


def test_draft_session_save_and_retrieve():
    payload = {'session_id': 'test-sess-1', 'state': _STATE}
    r = client.post('/draft/session', json=payload)
    assert r.status_code == 200
    assert r.json()['ok'] is True

    r2 = client.get('/draft/session/test-sess-1')
    assert r2.status_code == 200
    data = r2.json()
    assert data['session_id'] == 'test-sess-1'


def test_draft_session_not_found():
    r = client.get('/draft/session/nonexistent')
    assert r.status_code == 404


def test_draft_recommend_empty_pool_returns_422():
    all_ids = [{'gsis_id': f'P{i}', 'team_number': 1, 'position': 'RB'} for i in range(4)]
    state = {**_STATE, 'pick_log': all_ids}
    r = client.post('/draft/recommend', json=state)
    assert r.status_code == 422
```

- [ ] **Step 2: Run API tests**

```bash
cd "/Users/theoauyeung/Documents/Projects/TAY Analytics FF" && python -m pytest tests/api/test_draft.py -v 2>&1 | tail -25
```

Expected: all PASS

- [ ] **Step 3: Run full test suite to confirm no regressions**

```bash
cd "/Users/theoauyeung/Documents/Projects/TAY Analytics FF" && python -m pytest tests/ -v --tb=short 2>&1 | tail -10
```

Expected: all PASS

- [ ] **Step 4: Commit**

```bash
git add tests/api/test_draft.py
git commit -m "test: update API draft fixture to pick_log, assert wait_analysis and next_round_board"
```

---

## Task 9: Frontend types — `recommendation.ts`

**Files:**
- Modify: `ui/src/types/recommendation.ts`

**Interfaces:**
- Produces: `WaitScenario`, `NextRoundPositionSummary` TypeScript interfaces; `RecommendationState` extended with `waitAnalysis` + `nextRoundBoard`; `PositionalScarcity` removed

- [ ] **Step 1: Replace `ui/src/types/recommendation.ts`**

```typescript
import type { Position, PlayerDetail } from './player'
import type { Ranking } from './ranking'

export interface FutureAvailability {
  playerId: string
  probability: number    // 0–1, probability player is GONE before user's next pick
  label: 'safe' | 'monitor' | 'urgent'
}

export interface RecommendationExplanation {
  factor: string
  detail: string
  weight: 'primary' | 'secondary' | 'risk'
}

export interface ScoredPlayer {
  player: PlayerDetail
  score: number
  explanation: RecommendationExplanation[]
}

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

export interface RecommendationState {
  topPick: Ranking & {
    draftScore: number
    rosterFit: number
    futureAvailability: FutureAvailability
    explanation: RecommendationExplanation[]
  }
  alternatives: Array<Ranking & {
    draftScore: number
    rosterFit: number
    futureAvailability: FutureAvailability
    explanation: RecommendationExplanation[]
  }>
  positionalNeeds: Record<Position, number>   // 0–1 urgency
  waitAnalysis: WaitScenario[]
  nextRoundBoard: Record<string, NextRoundPositionSummary>
  mayNotMakeItBack: FutureAvailability[]
}
```

- [ ] **Step 2: Run TypeScript check**

```bash
cd "/Users/theoauyeung/Documents/Projects/TAY Analytics FF/ui" && npm run typecheck 2>&1 | grep -E "error TS|Found [0-9]+" | head -20
```

Expected: errors only in `ScarcityBar.tsx` and `RecommendationPanel.tsx` (which reference the removed `PositionalScarcity` type — fixed in Task 13)

- [ ] **Step 3: Commit**

```bash
git add ui/src/types/recommendation.ts
git commit -m "feat: frontend types — WaitScenario, NextRoundPositionSummary, updated RecommendationState"
```

---

## Task 10: `api/draft.ts` — update request and response mapping

**Files:**
- Modify: `ui/src/api/draft.ts`

**Interfaces:**
- Consumes: `WaitScenario`, `NextRoundPositionSummary` from `../types`
- Produces: `fetchRecommendation()` returns `RecommendationState` with `waitAnalysis` and `nextRoundBoard`; `toDraftStateIn()` sends `pick_log` instead of `drafted_ids`

- [ ] **Step 1: Update `ui/src/api/draft.ts`**

Replace the full file:

```typescript
import type {
  Position, PlayerDetail, LiveDraftState,
  RecommendationState, FutureAvailability, Tier, TierLabel,
  WaitScenario, NextRoundPositionSummary,
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
}

interface BackendExplanation {
  factor: string
  detail: string
  weight: string
}

interface BackendRecommendation {
  player: BackendPlayerProjection
  draft_score: number
  roster_fit: number
  positional_urgency: number
  future_availability_pct: number
  explanation: BackendExplanation[]
}

interface BackendWaitScenario {
  position: string
  best_now_name: string
  best_now_vor: number
  expected_vor_at_next_pick: number
  vor_cost_of_waiting: number
  cliff_before_next_pick: boolean
  survival_probability: number
}

interface BackendNextRoundSummary {
  position: string
  strong_options_remaining: number
  next_cliff_rank: number | null
  cliff_warning: boolean
}

interface BackendRecommendationState {
  top_pick: BackendRecommendation
  alternatives: BackendRecommendation[]
  positional_needs: string[]
  may_not_make_it_back: BackendPlayerProjection[]
  wait_analysis: BackendWaitScenario[]
  next_round_board: Record<string, BackendNextRoundSummary>
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

function toPlayerDetailFromProjection(p: BackendPlayerProjection): PlayerDetail {
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
    projectedStats: {
      targets: null,
      receptions: null,
      recYards: null,
      recTds: null,
      rushAttempts: null,
      rushYards: null,
      rushTds: null,
      passAttempts: null,
      completions: null,
      passYards: null,
      passTds: null,
      interceptions: null,
    },
    rookieYear: false,
    collegeTeam: null,
    depthChartPosition: 1,
  }
}

function mapRecommendation(r: BackendRecommendation): RecommendationState['topPick'] {
  const p = r.player
  const tier = clampTier(p.tier)
  const prob = r.future_availability_pct
  const player = toPlayerDetailFromProjection(p)

  return {
    rank: p.vor_rank,
    positionRank: 0,
    player,
    tier: { number: tier, label: TIER_LABELS[tier] } as Tier,
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
    draftScore: r.draft_score,
    rosterFit: r.roster_fit,
    futureAvailability: {
      playerId: p.gsis_id,
      probability: prob,
      label: prob > 0.7 ? 'urgent' : prob > 0.3 ? 'monitor' : 'safe',
    } as FutureAvailability,
    explanation: r.explanation.map(e => ({
      factor: e.factor,
      detail: e.detail,
      weight: e.weight as 'primary' | 'secondary' | 'risk',
    })),
  }
}

function mapWaitScenario(w: BackendWaitScenario): WaitScenario {
  return {
    position: w.position,
    bestNowName: w.best_now_name,
    bestNowVor: w.best_now_vor,
    expectedVorAtNextPick: w.expected_vor_at_next_pick,
    vorCostOfWaiting: w.vor_cost_of_waiting,
    cliffBeforeNextPick: w.cliff_before_next_pick,
    survivalProbability: w.survival_probability,
  }
}

function mapNextRoundSummary(s: BackendNextRoundSummary): NextRoundPositionSummary {
  return {
    position: s.position,
    strongOptionsRemaining: s.strong_options_remaining,
    nextCliffRank: s.next_cliff_rank,
    cliffWarning: s.cliff_warning,
  }
}

function toDraftStateIn(state: LiveDraftState) {
  return {
    season: SEASON,
    model_version: MODEL_VERSION,
    league_settings: {
      teams: state.config.teams,
      scoring: 'full',
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
    pick_log: state.picks.map(p => ({
      gsis_id: p.player.id,
      team_number: p.teamNumber,
      position: p.player.position,
    })),
    user_roster: (() => {
      const roster: Record<string, string[]> = {}
      for (const pick of state.picks.filter(p => p.isUserPick)) {
        const pos = pick.player.position
        ;(roster[pos] ??= []).push(pick.player.id)
      }
      return roster
    })(),
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
      if (idx === -1) return [pos, 0]
      const urgency =
        idx === 0 ? 1.0
        : idx === 1 ? 0.75
        : idx === 2 ? 0.5
        : 0.25
      return [pos, urgency]
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
    waitAnalysis: data.wait_analysis.map(mapWaitScenario),
    nextRoundBoard: Object.fromEntries(
      Object.entries(data.next_round_board).map(([pos, s]) => [pos, mapNextRoundSummary(s)])
    ),
    mayNotMakeItBack,
  }
}

export async function saveSession(sessionId: string, state: LiveDraftState): Promise<void> {
  await apiFetch('/draft/session', {
    method: 'POST',
    body: JSON.stringify({
      session_id: sessionId,
      drafted_ids: state.picks.map(p => p.player.id),
      league_settings: toDraftStateIn(state).league_settings,
    }),
  })
}

export async function loadSession(_sessionId: string): Promise<LiveDraftState | null> {
  return null
}
```

- [ ] **Step 2: Run TypeScript check**

```bash
cd "/Users/theoauyeung/Documents/Projects/TAY Analytics FF/ui" && npm run typecheck 2>&1 | grep -E "error TS|Found [0-9]+" | head -20
```

Expected: errors only in components that still use the old `scarcity` prop (fixed in Task 13)

- [ ] **Step 3: Commit**

```bash
git add ui/src/api/draft.ts
git commit -m "feat: api/draft.ts — pick_log request, structured explanation mapping, waitAnalysis + nextRoundBoard response"
```

---

## Task 11: `WaitAnalysisPanel` component

**Files:**
- Create: `ui/src/components/draft/WaitAnalysisPanel.tsx`
- Modify: `ui/src/components/draft/index.ts`

**Interfaces:**
- Consumes: `WaitScenario[]` from `../../types`

- [ ] **Step 1: Create `ui/src/components/draft/WaitAnalysisPanel.tsx`**

```tsx
import clsx from 'clsx'
import type { WaitScenario } from '../../types'

interface Props {
  scenarios: WaitScenario[]
}

function CostLabel({ cost }: { cost: number }) {
  const colorClass =
    cost > 10 ? 'text-red-400' :
    cost > 5  ? 'text-yellow-400' :
    'text-text-muted'
  const sign = cost >= 0 ? '-' : '+'
  return (
    <span className={clsx('text-sm font-bold font-mono tabular-nums', colorClass)}>
      {sign}{Math.abs(cost).toFixed(1)} VOR
    </span>
  )
}

export function WaitAnalysisPanel({ scenarios }: Props) {
  // Hide panel if every position is the same (nothing to compare)
  const uniquePositions = new Set(scenarios.map(s => s.position))
  if (uniquePositions.size <= 1) return null

  return (
    <div>
      <div className="text-xs font-bold tracking-wide text-text-muted uppercase mb-3">
        What Happens If I Wait?
      </div>
      <div className="space-y-2">
        {scenarios.map(s => (
          <div
            key={s.position}
            className="bg-bg-elevated border border-border rounded-lg p-3"
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-bold text-text-secondary uppercase tracking-wide">
                If you wait on {s.position}
              </span>
              {s.cliffBeforeNextPick && (
                <span className="text-xs font-bold text-red-400 bg-red-900/20 px-1.5 py-0.5 rounded">
                  ⚠ CLIFF
                </span>
              )}
            </div>
            <div className="grid grid-cols-3 gap-2 text-xs">
              <div>
                <div className="text-text-muted mb-0.5">Best now</div>
                <div className="font-semibold text-text-primary truncate">{s.bestNowName}</div>
                <div className="text-text-secondary font-mono">+{s.bestNowVor.toFixed(1)} VOR</div>
              </div>
              <div>
                <div className="text-text-muted mb-0.5">Next pick</div>
                <div className="font-semibold text-text-secondary">~{s.expectedVorAtNextPick.toFixed(1)} expected</div>
                <div className="text-text-muted">
                  {Math.round((1 - s.survivalProbability) * 100)}% chance gone
                </div>
              </div>
              <div className="text-right">
                <div className="text-text-muted mb-0.5">Cost</div>
                <CostLabel cost={s.vorCostOfWaiting} />
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Export from `ui/src/components/draft/index.ts`**

Add to the existing exports:

```typescript
export { WaitAnalysisPanel } from './WaitAnalysisPanel'
```

- [ ] **Step 3: TypeScript check**

```bash
cd "/Users/theoauyeung/Documents/Projects/TAY Analytics FF/ui" && npm run typecheck 2>&1 | grep "WaitAnalysisPanel" | head -5
```

Expected: no errors referencing `WaitAnalysisPanel`

- [ ] **Step 4: Commit**

```bash
git add ui/src/components/draft/WaitAnalysisPanel.tsx ui/src/components/draft/index.ts
git commit -m "feat: WaitAnalysisPanel — position-by-position opportunity cost of waiting"
```

---

## Task 12: `NextRoundBoardPanel` component

**Files:**
- Create: `ui/src/components/draft/NextRoundBoardPanel.tsx`
- Modify: `ui/src/components/draft/index.ts`

**Interfaces:**
- Consumes: `Record<string, NextRoundPositionSummary>` from `../../types`

- [ ] **Step 1: Create `ui/src/components/draft/NextRoundBoardPanel.tsx`**

```tsx
import clsx from 'clsx'
import type { NextRoundPositionSummary } from '../../types'

interface Props {
  board: Record<string, NextRoundPositionSummary>
}

const POSITION_ORDER = ['QB', 'RB', 'WR', 'TE']

export function NextRoundBoardPanel({ board }: Props) {
  const positions = POSITION_ORDER.filter(pos => pos in board)
  if (positions.length === 0) return null

  return (
    <div>
      <div className="text-xs font-bold tracking-wide text-text-muted uppercase mb-3">
        Likely Available Next Pick
      </div>
      <div className="grid grid-cols-4 gap-2">
        {positions.map(pos => {
          const summary = board[pos]
          return (
            <div
              key={pos}
              className={clsx(
                'bg-bg-elevated border rounded-lg p-2.5 text-center',
                summary.cliffWarning ? 'border-red-400/30' : 'border-border'
              )}
            >
              <div className="text-xs font-bold text-text-secondary mb-1">{pos}</div>
              <div className={clsx(
                'text-lg font-bold',
                summary.strongOptionsRemaining <= 2 ? 'text-red-400' :
                summary.strongOptionsRemaining <= 4 ? 'text-yellow-400' :
                'text-text-primary'
              )}>
                {summary.strongOptionsRemaining}
              </div>
              <div className="text-xs text-text-muted leading-tight">
                {summary.strongOptionsRemaining === 1 ? 'option' : 'options'}
              </div>
              {summary.cliffWarning && (
                <div className="text-xs text-red-400 mt-1 font-semibold">⚠ cliff</div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Export from `ui/src/components/draft/index.ts`**

```typescript
export { NextRoundBoardPanel } from './NextRoundBoardPanel'
```

- [ ] **Step 3: TypeScript check**

```bash
cd "/Users/theoauyeung/Documents/Projects/TAY Analytics FF/ui" && npm run typecheck 2>&1 | grep "NextRoundBoardPanel" | head -5
```

Expected: no errors

- [ ] **Step 4: Commit**

```bash
git add ui/src/components/draft/NextRoundBoardPanel.tsx ui/src/components/draft/index.ts
git commit -m "feat: NextRoundBoardPanel — expected board state at user's next pick"
```

---

## Task 13: `ScarcityBar` + `RecommendationPanel` — wire new panels, fix type errors

**Files:**
- Modify: `ui/src/components/draft/ScarcityBar.tsx`
- Modify: `ui/src/components/draft/RecommendationPanel.tsx`

**Interfaces:**
- `ScarcityBar` now accepts `waitAnalysis: WaitScenario[]` instead of `scarcity: PositionalScarcity[]`
- `RecommendationPanel` renders `WaitAnalysisPanel` and `NextRoundBoardPanel` below the WHY section

- [ ] **Step 1: Update `ui/src/components/draft/ScarcityBar.tsx`**

```tsx
import clsx from 'clsx'
import type { WaitScenario } from '../../types'

interface Props {
  waitAnalysis: WaitScenario[]
}

export function ScarcityBar({ waitAnalysis }: Props) {
  if (waitAnalysis.length === 0) return null

  const maxCost = Math.max(...waitAnalysis.map(s => s.vorCostOfWaiting), 1)

  return (
    <div>
      <div className="text-xs font-bold tracking-wide text-text-muted uppercase mb-3">
        Positional Scarcity
      </div>
      <div className="space-y-2.5">
        {waitAnalysis.map(s => {
          const pct = Math.min(1, Math.max(0, s.vorCostOfWaiting / maxCost))
          const isHigh = s.vorCostOfWaiting > 10
          const isMed = s.vorCostOfWaiting > 5 && s.vorCostOfWaiting <= 10

          return (
            <div key={s.position}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-medium text-text-secondary">{s.position}</span>
                <span className={clsx(
                  'text-xs font-mono',
                  isHigh ? 'text-red-400' : isMed ? 'text-yellow-400' : 'text-text-muted'
                )}>
                  -{s.vorCostOfWaiting.toFixed(1)} VOR cost
                </span>
              </div>
              <div className="h-2 bg-bg-elevated rounded-full overflow-hidden">
                <div
                  className={clsx(
                    'h-full rounded-full transition-all',
                    isHigh ? 'bg-red-500' : isMed ? 'bg-yellow-500' : 'bg-accent'
                  )}
                  style={{ width: `${Math.round(pct * 100)}%` }}
                />
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Update `ui/src/components/draft/RecommendationPanel.tsx`**

Replace the import block and add the two new panels. The full updated file:

```tsx
import { useState } from 'react'
import { AlertTriangle } from 'lucide-react'
import clsx from 'clsx'
import { useDraftState } from '../../hooks/useDraftState'
import { useRecommendation } from '../../hooks/useRecommendation'
import { useRankings } from '../../hooks/useRankings'
import { ApiError } from '../../api/client'
import { PositionBadge } from '../ui/Badge'
import { AlternativeCard } from './AlternativeCard'
import { ScarcityBar } from './ScarcityBar'
import { MayNotMakeItBack } from './MayNotMakeItBack'
import { WaitAnalysisPanel } from './WaitAnalysisPanel'
import { NextRoundBoardPanel } from './NextRoundBoardPanel'

export function RecommendationPanel() {
  const { state, draftPlayer } = useDraftState()
  const { recommendation: reco, error: recoError } = useRecommendation()
  const { rankings } = useRankings({ position: 'ALL', search: '', format: 'ppr', draftType: 'redraft', year: 2026, tierFilter: null })
  const [selectedAltIdx, setSelectedAltIdx] = useState<number | null>(null)

  const totalPicks = state.config.teams * state.config.totalRounds
  const isDraftComplete = state.currentOverallPick > totalPicks

  if (isDraftComplete) {
    return (
      <div className="flex-1 flex items-center justify-center text-text-muted">
        <div className="text-center">
          <div className="text-2xl font-bold mb-2">Draft Complete</div>
          <div className="text-sm">All rounds filled. Check your roster in the right panel.</div>
        </div>
      </div>
    )
  }

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

  if (!reco) {
    return (
      <div className="flex-1 flex items-center justify-center text-text-muted text-sm">
        Loading recommendations...
      </div>
    )
  }

  const displayed = selectedAltIdx !== null ? reco.alternatives[selectedAltIdx] : reco.topPick
  const isShowingAlt = selectedAltIdx !== null

  return (
    <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5">

      {/* Header label */}
      <div className="flex items-center gap-2">
        <span className="text-xs font-bold tracking-wide text-accent uppercase">
          {isShowingAlt ? 'Alternative Pick' : 'Your Pick'}
        </span>
        {isShowingAlt && (
          <button
            onClick={() => setSelectedAltIdx(null)}
            className="ml-auto text-xs text-text-muted hover:text-text-primary"
          >
            Back to top pick
          </button>
        )}
      </div>

      {/* Main player card */}
      <div className="bg-bg-card border border-border rounded-lg p-5">
        <div className="flex items-start gap-4 mb-4">
          <div className="w-12 h-12 rounded-full overflow-hidden bg-bg-elevated flex-shrink-0">
            {displayed.player.imageUrl ? (
              <img
                src={displayed.player.imageUrl}
                alt={displayed.player.name}
                className="w-full h-full object-cover"
                onError={e => { (e.target as HTMLImageElement).style.display = 'none' }}
              />
            ) : (
              <div className="w-full h-full flex items-center justify-center text-xl font-bold text-text-muted">
                {displayed.player.name.charAt(0)}
              </div>
            )}
          </div>
          <div className="flex-1">
            <h2 className="text-2xl font-bold text-text-primary leading-tight">
              {displayed.player.name}
            </h2>
            <div className="flex items-center gap-2 mt-1">
              <PositionBadge position={displayed.player.position} />
              <span className="text-sm text-text-secondary">{displayed.player.team}</span>
              <span className="text-text-muted">·</span>
              <span className="text-sm text-text-muted">Bye {displayed.player.byeWeek}</span>
            </div>
          </div>
          <div className="text-right flex-shrink-0">
            <div className="text-xs text-text-muted mb-0.5">Draft Score</div>
            <div className="text-3xl font-bold text-accent">{displayed.draftScore}</div>
          </div>
        </div>

        <div className="grid grid-cols-4 gap-3 mb-4">
          {[
            { label: 'Proj', value: displayed.projection.toFixed(0), highlight: false },
            { label: 'VOR', value: `${displayed.vor >= 0 ? '+' : ''}${displayed.vor.toFixed(1)}`, highlight: displayed.vor >= 20 },
            { label: 'ADP', value: String(displayed.adp), highlight: false },
            { label: 'Avail', value: `${Math.round((1 - displayed.futureAvailability.probability) * 100)}%`, highlight: displayed.futureAvailability.probability < 0.4 },
          ].map(m => (
            <div key={m.label} className="bg-bg-elevated rounded-md p-2.5 text-center">
              <div className="text-xs text-text-muted mb-0.5">{m.label}</div>
              <div className={clsx('text-base font-bold', m.highlight ? 'text-accent' : 'text-text-primary')}>
                {m.value}
              </div>
            </div>
          ))}
        </div>

        <button
          onClick={() => draftPlayer(displayed.player, true)}
          className="w-full py-2.5 bg-accent text-bg-primary text-sm font-bold rounded-md hover:bg-accent-dim transition-colors"
        >
          Draft {displayed.player.name} (Mine)
        </button>
      </div>

      {/* WHY? */}
      {displayed.explanation.length > 0 && (
        <div>
          <div className="text-xs font-bold tracking-wide text-text-muted uppercase mb-2">Why?</div>
          <div className="space-y-1.5">
            {displayed.explanation.map((ex, i) => (
              <div
                key={i}
                className={clsx(
                  'flex items-start gap-2.5 p-2.5 rounded-lg text-xs',
                  ex.weight === 'primary' ? 'bg-accent-muted border border-accent/20' :
                  ex.weight === 'risk' ? 'bg-red-900/20 border border-red-400/20' :
                  'bg-bg-elevated border border-border'
                )}
              >
                {ex.weight === 'risk' && <AlertTriangle size={12} className="text-red-400 flex-shrink-0 mt-0.5" />}
                <div>
                  <span className={clsx(
                    'font-semibold',
                    ex.weight === 'primary' ? 'text-accent' :
                    ex.weight === 'risk' ? 'text-red-400' :
                    'text-text-primary'
                  )}>
                    {ex.factor}
                  </span>
                  <span className="text-text-secondary ml-1.5">{ex.detail}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* What Happens If I Wait? */}
      <WaitAnalysisPanel scenarios={reco.waitAnalysis} />

      {/* Likely Available Next Pick */}
      <NextRoundBoardPanel board={reco.nextRoundBoard} />

      {/* Alternatives */}
      {reco.alternatives.length > 0 && (
        <div>
          <div className="text-xs font-bold tracking-wide text-text-muted uppercase mb-2">
            Alternatives
          </div>
          <div className="space-y-2">
            {reco.alternatives.slice(0, 5).map((alt, i) => (
              <AlternativeCard
                key={alt.player.id}
                player={{ player: alt.player, score: alt.draftScore / 100, explanation: alt.explanation }}
                isSelected={selectedAltIdx === i}
                onClick={() => setSelectedAltIdx(selectedAltIdx === i ? null : i)}
              />
            ))}
          </div>
        </div>
      )}

      {/* Scarcity Bar */}
      {reco.waitAnalysis.length > 0 && (
        <div>
          <ScarcityBar waitAnalysis={reco.waitAnalysis} />
        </div>
      )}

      {/* May Not Make It Back */}
      {reco.mayNotMakeItBack.length > 0 && (
        <div>
          <MayNotMakeItBack items={reco.mayNotMakeItBack} allRankings={rankings} />
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 3: Run TypeScript check — expect zero errors**

```bash
cd "/Users/theoauyeung/Documents/Projects/TAY Analytics FF/ui" && npm run typecheck 2>&1 | grep -E "error TS|Found [0-9]+ error" | head -10
```

Expected: `Found 0 errors.`

- [ ] **Step 4: Run full backend test suite one final time**

```bash
cd "/Users/theoauyeung/Documents/Projects/TAY Analytics FF" && python -m pytest tests/ -v --tb=short 2>&1 | tail -10
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add ui/src/components/draft/ScarcityBar.tsx ui/src/components/draft/RecommendationPanel.tsx
git commit -m "feat: wire WaitAnalysisPanel + NextRoundBoardPanel into RecommendationPanel, update ScarcityBar to VOR cost"
```
