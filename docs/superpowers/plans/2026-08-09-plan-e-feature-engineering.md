# Feature Engineering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform raw ingested data into a model-ready feature matrix. Produce two DuckDB tables — `player_features` and `team_features` — covering all 2005–2025 seasons, that can be directly consumed by the PyTorch projection models in Plan F.

**Architecture:** Pure SQL + Python transformations. All features computed from data already in DuckDB. No model code. The `features/` module reads from `player_season_stats`, `team_season_stats`, `rosters`, `draft_picks`, `combine_data` and writes to `player_features` and `team_features`. A CLI script (`scripts/build_features.py`) runs the full pipeline.

**Tech Stack:** Python 3.12, DuckDB 1.x, pandas (for any complex transformations not easily expressed in SQL)

## Global Constraints

- Python interpreter: `/Users/theoauyeung/miniforge3/bin/python3.12`
- **No leakage:** features for predicting season N use only data from seasons ≤ N-1. The target column (`next_season_fantasy_ppr`) is season N itself. Season indices are explicit in every query.
- All features stored in `data/ff.duckdb` (same database as ingestion)
- Skill positions only: QB, RB, WR, TE — filter out ST, K, P, etc.
- Minimum history requirement: players with no prior season stats get NULL for lag features (handled, not dropped)
- `gsis_id` + `season` is the primary key for all feature rows
- TDD: tests in `tests/features/`, run with `pytest`
- Commits after each task

---

## File Map

```
src/tay/
├── features/
│   ├── __init__.py
│   ├── schema.py          — DDL for player_features and team_features tables
│   ├── player_features.py — player-level feature computation
│   ├── team_features.py   — team-level feature computation
│   ├── vacated_opportunity.py — departed player opportunity calculation
│   └── pipeline.py        — orchestrates full feature build
scripts/
└── build_features.py      — CLI: runs feature pipeline
tests/features/
├── __init__.py
├── test_player_features.py
├── test_team_features.py
└── test_vacated_opportunity.py
```

---

### Task 1: Feature table schema

**Files:**
- Create: `src/tay/features/__init__.py`
- Create: `src/tay/features/schema.py`
- Modify: `src/tay/schemas/tables.py` — add `PLAYER_FEATURES` and `TEAM_FEATURES` DDL to `ALL_TABLES`
- Modify: `src/tay/db.py` — `init_schema` already iterates `ALL_TABLES`, so adding there auto-creates the new tables

**Interfaces:**
- Produces: `player_features` and `team_features` tables in DuckDB (created by `init_schema`)

- [ ] **Step 1: Create `src/tay/features/__init__.py`**

Empty file.

- [ ] **Step 2: Add DDL to `src/tay/schemas/tables.py`**

Add these two constants and include them in `ALL_TABLES`:

```python
PLAYER_FEATURES = """
CREATE TABLE IF NOT EXISTS player_features (
    gsis_id                 VARCHAR NOT NULL,
    season                  INTEGER NOT NULL,
    position                VARCHAR,
    age                     DOUBLE,
    experience              INTEGER,

    -- Prior season raw stats (season N-1)
    prev_games              INTEGER,
    prev_targets            INTEGER,
    prev_receptions         INTEGER,
    prev_rec_yards          DOUBLE,
    prev_rec_tds            INTEGER,
    prev_air_yards          DOUBLE,
    prev_yac                DOUBLE,
    prev_carries            INTEGER,
    prev_rush_yards         DOUBLE,
    prev_rush_tds           INTEGER,
    prev_attempts           INTEGER,
    prev_completions        INTEGER,
    prev_pass_yards         DOUBLE,
    prev_pass_tds           INTEGER,
    prev_interceptions      INTEGER,
    prev_fantasy_ppr        DOUBLE,

    -- Per-game efficiency (season N-1, only when games > 0)
    targets_per_game        DOUBLE,
    catches_per_game        DOUBLE,
    rec_yards_per_game      DOUBLE,
    rec_tds_per_game        DOUBLE,
    carries_per_game        DOUBLE,
    rush_yards_per_game     DOUBLE,

    -- Rate stats (season N-1)
    catch_rate              DOUBLE,   -- receptions / targets
    yards_per_target        DOUBLE,   -- rec_yards / targets
    yards_per_carry         DOUBLE,   -- rush_yards / carries
    air_yards_per_target    DOUBLE,   -- air_yards / targets
    yac_per_reception       DOUBLE,   -- yac / receptions
    pass_completion_pct     DOUBLE,   -- completions / attempts
    pass_yards_per_attempt  DOUBLE,   -- pass_yards / attempts
    td_rate_receiving       DOUBLE,   -- rec_tds / targets
    td_rate_rushing         DOUBLE,   -- rush_tds / carries

    -- Advanced (season N-1)
    prev_epa_per_play       DOUBLE,
    prev_cpoe               DOUBLE,

    -- 2-year rolling averages (seasons N-2 and N-1)
    roll2_fantasy_ppr       DOUBLE,
    roll2_targets           DOUBLE,
    roll2_carries           DOUBLE,

    -- Team context (season N-1 team environment)
    team                    VARCHAR,
    team_pass_rate          DOUBLE,
    team_pass_epa           DOUBLE,
    team_total_plays        INTEGER,

    -- Vacated opportunity coming into season N
    -- (opportunity from players who left this team after season N-1)
    incoming_vacated_targets   DOUBLE,
    incoming_vacated_carries   DOUBLE,

    -- Roster depth (from weekly rosters, season N-1 week 1)
    depth_chart_pos         INTEGER,

    -- Rookie / draft context (NULL for veterans)
    is_rookie               INTEGER,   -- 1 if first NFL season
    draft_round             INTEGER,
    draft_pick              INTEGER,
    draft_pick_value        DOUBLE,    -- 1/(overall_pick^0.5), 0 for undrafted
    combine_forty           DOUBLE,
    combine_vertical        DOUBLE,

    -- Target variable (what we're predicting — season N)
    next_season_fantasy_ppr DOUBLE,
    next_season_games       INTEGER,

    created_at              TIMESTAMP DEFAULT current_timestamp,
    PRIMARY KEY (gsis_id, season)
)
"""

TEAM_FEATURES = """
CREATE TABLE IF NOT EXISTS team_features (
    team                    VARCHAR NOT NULL,
    season                  INTEGER NOT NULL,

    -- Season N-1 environment
    pass_rate               DOUBLE,
    rush_rate               DOUBLE,
    team_epa                DOUBLE,
    pass_epa                DOUBLE,
    rush_epa                DOUBLE,
    total_plays             INTEGER,
    pass_attempts           INTEGER,
    total_tds               INTEGER,

    -- Vacated opportunity (after season N-1, before season N)
    vacated_qb_attempts     DOUBLE,
    vacated_rb_carries      DOUBLE,
    vacated_wr_targets      DOUBLE,
    vacated_te_targets      DOUBLE,

    created_at              TIMESTAMP DEFAULT current_timestamp,
    PRIMARY KEY (team, season)
)
"""
```

In `ALL_TABLES`, add `PLAYER_FEATURES` and `TEAM_FEATURES` to the list.

- [ ] **Step 3: Create `src/tay/features/schema.py`**

```python
"""Re-export feature DDL for direct import."""
from tay.schemas.tables import PLAYER_FEATURES, TEAM_FEATURES

__all__ = ["PLAYER_FEATURES", "TEAM_FEATURES"]
```

- [ ] **Step 4: Write failing test**

Create `tests/features/__init__.py` (empty) and `tests/features/test_schema.py`:

```python
from tay.db import get_conn, init_schema

def test_feature_tables_created(tmp_path):
    conn = get_conn(tmp_path / "test.duckdb")
    init_schema(conn)
    tables = {r[0] for r in conn.execute("SHOW TABLES").fetchall()}
    assert "player_features" in tables
    assert "team_features" in tables
    conn.close()
```

- [ ] **Step 5: Run test**

```bash
cd "/Users/theoauyeung/Documents/Projects/TAY Analytics FF"
/Users/theoauyeung/miniforge3/bin/python3.12 -m pytest tests/features/test_schema.py -v
```

Expected: PASSED

- [ ] **Step 6: Commit**

```bash
git add src/tay/features/__init__.py src/tay/features/schema.py \
        src/tay/schemas/tables.py tests/features/__init__.py tests/features/test_schema.py
git commit -m "feat: player_features and team_features table schema"
```

---

### Task 2: Team environment features

**Files:**
- Create: `src/tay/features/team_features.py`
- Create: `tests/features/test_team_features.py`

**Interfaces:**
- Consumes: `team_season_stats` table
- Produces: `team_features` rows (one per team per season); the `season` column here means "features derived from season N-1 for use in predicting season N"

**Design:** `team_features.season = N` contains the team's N-1 environment stats. So `team_features` rows for season 2007 contain 2006 stats — what a model would know going into 2007. First season (2005) gets NULLs for prior-year features.

- [ ] **Step 1: Write failing test**

Create `tests/features/test_team_features.py`:

```python
import pytest
from tay.db import get_conn, init_schema
from tay.features.team_features import build_team_features

@pytest.fixture
def conn(tmp_path):
    c = get_conn(tmp_path / "test.duckdb")
    init_schema(c)
    # Season 2023 team stats
    c.execute("""
        INSERT INTO team_season_stats
            (team, season, games, total_plays, pass_attempts, rush_attempts,
             pass_rate, total_tds, pass_tds, rush_tds,
             team_epa, pass_epa, rush_epa)
        VALUES ('KC', 2023, 17, 1100, 600, 500, 0.545, 60, 40, 20, 0.12, 0.25, -0.05)
    """)
    yield c
    c.close()

def test_build_team_features_creates_row(conn):
    build_team_features(conn, target_seasons=[2024])
    row = conn.execute(
        "SELECT team, season, pass_rate, total_plays FROM team_features WHERE team='KC' AND season=2024"
    ).fetchone()
    assert row is not None
    assert row[0] == 'KC'
    assert row[1] == 2024
    assert abs(row[2] - 0.545) < 0.01   # prior year's pass rate

def test_first_season_gets_nulls(conn):
    build_team_features(conn, target_seasons=[2005])
    # No prior data for 2005 → either no row or a row with NULL features
    # We choose: insert a row with NULLs so the model can still reference the team
    row = conn.execute(
        "SELECT pass_rate FROM team_features WHERE season=2005"
    ).fetchone()
    # Either no row (skip) or NULL — both are acceptable
    assert row is None or row[0] is None
```

- [ ] **Step 2: Run — expect FAIL**

```bash
/Users/theoauyeung/miniforge3/bin/python3.12 -m pytest tests/features/test_team_features.py -v
```

Expected: FAIL (ImportError)

- [ ] **Step 3: Create `src/tay/features/team_features.py`**

```python
"""Build team environment features (season N-1 stats → season N features)."""
from __future__ import annotations
import duckdb
from tay.db import get_conn, init_schema


def build_team_features(
    conn: duckdb.DuckDBPyConnection,
    target_seasons: list[int],
) -> int:
    """Populate team_features for the given target seasons.

    team_features.season = N contains environment data from season N-1.
    Skip season if no prior-year data exists (e.g., 2005).
    Returns number of rows inserted.
    """
    total = 0
    for season in target_seasons:
        prior = season - 1
        conn.execute("DELETE FROM team_features WHERE season = ?", [season])

        rows = conn.execute("""
            SELECT
                team,
                ? AS season,
                pass_rate,
                (1.0 - pass_rate) AS rush_rate,
                team_epa,
                pass_epa,
                rush_epa,
                total_plays,
                pass_attempts,
                total_tds
            FROM team_season_stats
            WHERE season = ?
        """, [season, prior]).fetchall()

        if not rows:
            continue

        conn.executemany("""
            INSERT OR REPLACE INTO team_features
                (team, season, pass_rate, rush_rate, team_epa, pass_epa, rush_epa,
                 total_plays, pass_attempts, total_tds)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, rows)

        total += len(rows)

    conn.commit()
    return total


def ingest(start: int = 2006, end: int = 2025, db_path=None) -> None:
    conn = get_conn(db_path) if db_path else get_conn()
    init_schema(conn)
    seasons = list(range(start, end + 1))
    n = build_team_features(conn, seasons)
    print(f"team_features: {n:,} rows built")
    conn.close()


if __name__ == "__main__":
    ingest()
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
/Users/theoauyeung/miniforge3/bin/python3.12 -m pytest tests/features/test_team_features.py -v
```

Expected: 2 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/tay/features/team_features.py tests/features/test_team_features.py
git commit -m "feat: team environment features (prior-season team stats → season N features)"
```

---

### Task 3: Vacated opportunity

**Files:**
- Create: `src/tay/features/vacated_opportunity.py`
- Create: `tests/features/test_vacated_opportunity.py`

**Interfaces:**
- Consumes: `player_season_stats`, `rosters` (to detect team changes between seasons)
- Produces: `team_features.vacated_*` columns populated; a standalone `get_vacated_opportunity(team, season, conn)` function

**Design:** For each team going into season N, find all players who had stats on that team in season N-1 but are NOT on that team's roster for season N. Sum their N-1 targets/carries. This is the "vacated opportunity" the new season must redistribute.

**Leakage check:** We use N-1 stats (already known) and compare to roster status (also known before season N starts). No future information.

- [ ] **Step 1: Write failing test**

Create `tests/features/test_vacated_opportunity.py`:

```python
import pytest
from tay.db import get_conn, init_schema
from tay.features.vacated_opportunity import compute_vacated_opportunity, get_vacated_opportunity

@pytest.fixture
def conn(tmp_path):
    c = get_conn(tmp_path / "test.duckdb")
    init_schema(c)

    # Player A: was on KC in 2023 (100 targets), left for SF in 2024
    c.execute("""
        INSERT INTO player_season_stats (gsis_id, season, team, targets, carries, rec_yards, fantasy_points_ppr)
        VALUES ('player-a', 2023, 'KC', 100, 0, 1000.0, 200.0)
    """)
    # Player B: stayed on KC (80 targets in 2023)
    c.execute("""
        INSERT INTO player_season_stats (gsis_id, season, team, targets, carries, rec_yards, fantasy_points_ppr)
        VALUES ('player-b', 2023, 'KC', 80, 0, 800.0, 160.0)
    """)
    # Rosters: Player A is on SF in 2024 week 1, Player B is on KC
    c.execute("""
        INSERT INTO rosters (gsis_id, season, week, team, position)
        VALUES ('player-a', 2024, 1, 'SF', 'WR'), ('player-b', 2024, 1, 'KC', 'WR')
    """)
    yield c
    c.close()

def test_vacated_targets_for_departed_player(conn):
    compute_vacated_opportunity(conn, target_seasons=[2024])
    row = conn.execute(
        "SELECT vacated_wr_targets FROM team_features WHERE team='KC' AND season=2024"
    ).fetchone()
    assert row is not None
    assert row[0] == 100.0   # player-a's 2023 targets on KC

def test_staying_player_not_counted(conn):
    compute_vacated_opportunity(conn, target_seasons=[2024])
    row = conn.execute(
        "SELECT vacated_wr_targets FROM team_features WHERE team='KC' AND season=2024"
    ).fetchone()
    # player-b stayed → their 80 targets should NOT be in vacated
    assert row[0] == 100.0   # only player-a's 100
```

- [ ] **Step 2: Run — expect FAIL**

```bash
/Users/theoauyeung/miniforge3/bin/python3.12 -m pytest tests/features/test_vacated_opportunity.py -v
```

Expected: FAIL

- [ ] **Step 3: Create `src/tay/features/vacated_opportunity.py`**

```python
"""Compute vacated opportunity: targets/carries left by players who changed teams."""
from __future__ import annotations
import duckdb
from tay.db import get_conn, init_schema


def compute_vacated_opportunity(
    conn: duckdb.DuckDBPyConnection,
    target_seasons: list[int],
) -> int:
    """For each team × season, sum stats of players who departed after season N-1.

    A player is 'departed' if they had stats on team T in season N-1 but their
    earliest week-1 roster entry in season N is a different team (or absent).

    Updates team_features.vacated_* columns. Inserts team_features rows if missing.
    Returns number of team-season rows updated.
    """
    total = 0
    for season in target_seasons:
        prior = season - 1

        # Build: for each player, their team in season N (from week-1 roster)
        # If not in rosters for season N, treat as departed (retired/cut)
        conn.execute(f"""
            CREATE OR REPLACE TEMP TABLE _season_{season}_teams AS
            SELECT gsis_id, team AS new_team
            FROM rosters
            WHERE season = {season} AND week = 1
            QUALIFY ROW_NUMBER() OVER (PARTITION BY gsis_id ORDER BY week) = 1
        """)

        # Players who were on each team in season N-1 but NOT on same team in season N
        departed = conn.execute(f"""
            SELECT
                s.team AS old_team,
                p.position,
                SUM(s.targets)  AS dep_targets,
                SUM(s.carries)  AS dep_carries
            FROM player_season_stats s
            JOIN players p ON s.gsis_id = p.gsis_id
            LEFT JOIN _season_{season}_teams t ON s.gsis_id = t.gsis_id
            WHERE s.season = {prior}
              AND p.position IN ('QB', 'RB', 'WR', 'TE')
              AND (t.new_team IS NULL OR t.new_team != s.team)
            GROUP BY s.team, p.position
        """).fetchall()

        # Pivot into per-team vacated columns
        vacated: dict[str, dict] = {}
        for old_team, pos, dep_targets, dep_carries in departed:
            if old_team not in vacated:
                vacated[old_team] = {
                    "vacated_qb_attempts": 0.0,
                    "vacated_rb_carries": 0.0,
                    "vacated_wr_targets": 0.0,
                    "vacated_te_targets": 0.0,
                }
            if pos == "QB":
                vacated[old_team]["vacated_qb_attempts"] += dep_targets or 0
            elif pos == "RB":
                vacated[old_team]["vacated_rb_carries"] += dep_carries or 0
            elif pos == "WR":
                vacated[old_team]["vacated_wr_targets"] += dep_targets or 0
            elif pos == "TE":
                vacated[old_team]["vacated_te_targets"] += dep_targets or 0

        for team, v in vacated.items():
            # Upsert into team_features (insert if missing, then update)
            conn.execute("""
                INSERT INTO team_features (team, season)
                VALUES (?, ?)
                ON CONFLICT (team, season) DO NOTHING
            """, [team, season])
            conn.execute("""
                UPDATE team_features
                SET vacated_qb_attempts = ?,
                    vacated_rb_carries  = ?,
                    vacated_wr_targets  = ?,
                    vacated_te_targets  = ?
                WHERE team = ? AND season = ?
            """, [
                v["vacated_qb_attempts"],
                v["vacated_rb_carries"],
                v["vacated_wr_targets"],
                v["vacated_te_targets"],
                team, season,
            ])
            total += 1

        conn.commit()

    return total


def get_vacated_opportunity(
    team: str,
    season: int,
    conn: duckdb.DuckDBPyConnection,
) -> dict:
    """Convenience function — returns vacated opportunity dict for a team/season."""
    row = conn.execute("""
        SELECT vacated_qb_attempts, vacated_rb_carries, vacated_wr_targets, vacated_te_targets
        FROM team_features WHERE team = ? AND season = ?
    """, [team, season]).fetchone()
    if not row:
        return {"vacated_qb_attempts": 0, "vacated_rb_carries": 0,
                "vacated_wr_targets": 0, "vacated_te_targets": 0}
    return {
        "vacated_qb_attempts": row[0] or 0,
        "vacated_rb_carries": row[1] or 0,
        "vacated_wr_targets": row[2] or 0,
        "vacated_te_targets": row[3] or 0,
    }
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
/Users/theoauyeung/miniforge3/bin/python3.12 -m pytest tests/features/test_vacated_opportunity.py -v
```

Expected: 2 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/tay/features/vacated_opportunity.py tests/features/test_vacated_opportunity.py
git commit -m "feat: vacated opportunity — departed player targets/carries per team per season"
```

---

### Task 4: Player efficiency features

**Files:**
- Create: `src/tay/features/player_features.py`
- Create: `tests/features/test_player_features.py`

**Interfaces:**
- Consumes: `player_season_stats`, `players`, `team_features`, `rosters`, `draft_picks`, `combine_data`
- Produces: `player_features` table fully populated (except `incoming_vacated_*` columns — those are set in Task 5)

**Design:** For each player and target season N, look up their season N-1 stats (lag features), season N-2 and N-1 for rolling averages, their N-1 team environment, their draft data, and their combine data. Also set `next_season_fantasy_ppr` (season N actual points) as the target variable.

Draft pick value formula: `1 / sqrt(overall_pick)` where overall_pick is 1-based. Undrafted = 0.

- [ ] **Step 1: Write failing test**

Create `tests/features/test_player_features.py`:

```python
import pytest
from tay.db import get_conn, init_schema
from tay.features.player_features import build_player_features

@pytest.fixture
def conn(tmp_path):
    c = get_conn(tmp_path / "test.duckdb")
    init_schema(c)

    # Player setup: WR, born 2000-01-01, on KC
    c.execute("""
        INSERT INTO players (gsis_id, name, position, team, birth_date, draft_year, draft_round, draft_pick)
        VALUES ('wr-1', 'Test WR', 'WR', 'KC', '2000-01-01', 2022, 1, 10)
    """)
    # Season 2022 stats
    c.execute("""
        INSERT INTO player_season_stats
            (gsis_id, season, team, games, targets, receptions, rec_yards, rec_tds,
             air_yards, yards_after_catch, fantasy_points_ppr)
        VALUES ('wr-1', 2022, 'KC', 17, 120, 90, 1200.0, 8, 800.0, 400.0, 252.0)
    """)
    # Season 2023 stats (what we're predicting FROM)
    c.execute("""
        INSERT INTO player_season_stats
            (gsis_id, season, team, games, targets, receptions, rec_yards, rec_tds,
             air_yards, yards_after_catch, fantasy_points_ppr)
        VALUES ('wr-1', 2023, 'KC', 16, 140, 100, 1400.0, 10, 900.0, 500.0, 300.0)
    """)
    # Season 2024 stats (the target variable)
    c.execute("""
        INSERT INTO player_season_stats
            (gsis_id, season, team, games, targets, receptions, rec_yards, rec_tds,
             air_yards, yards_after_catch, fantasy_points_ppr)
        VALUES ('wr-1', 2024, 'KC', 17, 130, 95, 1300.0, 9, 850.0, 450.0, 278.0)
    """)
    # Team features for KC 2024 (from Task 2)
    c.execute("""
        INSERT INTO team_features (team, season, pass_rate, team_epa, total_plays)
        VALUES ('KC', 2024, 0.55, 0.12, 1100)
    """)
    yield c
    c.close()

def test_build_player_features_creates_row(conn):
    build_player_features(conn, target_seasons=[2024])
    row = conn.execute(
        "SELECT gsis_id, season, prev_targets, next_season_fantasy_ppr FROM player_features WHERE gsis_id='wr-1' AND season=2024"
    ).fetchone()
    assert row is not None
    assert row[0] == 'wr-1'
    assert row[1] == 2024
    assert row[2] == 140   # 2023 targets
    assert abs(row[3] - 278.0) < 1.0   # 2024 actual

def test_rate_stats_computed(conn):
    build_player_features(conn, target_seasons=[2024])
    row = conn.execute(
        "SELECT catch_rate, yards_per_target FROM player_features WHERE gsis_id='wr-1' AND season=2024"
    ).fetchone()
    assert row is not None
    # catch_rate = 100/140 ≈ 0.714
    assert abs(row[0] - 100/140) < 0.01
    # yards_per_target = 1400/140 = 10.0
    assert abs(row[1] - 10.0) < 0.01

def test_rolling_average(conn):
    build_player_features(conn, target_seasons=[2024])
    row = conn.execute(
        "SELECT roll2_fantasy_ppr FROM player_features WHERE gsis_id='wr-1' AND season=2024"
    ).fetchone()
    assert row is not None
    # roll2 = (252 + 300) / 2 = 276
    assert abs(row[0] - 276.0) < 1.0

def test_skill_positions_only(conn):
    """Non-skill position players (K, P) should not get feature rows."""
    conn.execute("""
        INSERT INTO players (gsis_id, name, position, team)
        VALUES ('k-1', 'Test Kicker', 'K', 'KC')
    """)
    conn.execute("""
        INSERT INTO player_season_stats (gsis_id, season, team, fantasy_points_ppr)
        VALUES ('k-1', 2023, 'KC', 150.0)
    """)
    build_player_features(conn, target_seasons=[2024])
    row = conn.execute(
        "SELECT gsis_id FROM player_features WHERE gsis_id='k-1'"
    ).fetchone()
    assert row is None
```

- [ ] **Step 2: Run — expect FAIL**

```bash
/Users/theoauyeung/miniforge3/bin/python3.12 -m pytest tests/features/test_player_features.py -v
```

- [ ] **Step 3: Create `src/tay/features/player_features.py`**

```python
"""Build player-level features for the projection model."""
from __future__ import annotations
import math
from datetime import date
import duckdb
from tay.db import get_conn, init_schema

SKILL_POSITIONS = ("'QB'", "'RB'", "'WR'", "'TE'")
SKILL_POS_SQL = f"({', '.join(SKILL_POSITIONS)})"


def _draft_pick_value(overall_pick: int | None) -> float:
    """Non-linear pick value: 1/sqrt(pick). 0 for undrafted."""
    if overall_pick and overall_pick > 0:
        return 1.0 / math.sqrt(overall_pick)
    return 0.0


def _age_on_sept_1(birth_date_str: str | None, season: int) -> float | None:
    """Age in years as of September 1 of the target season."""
    if not birth_date_str:
        return None
    try:
        bd = date.fromisoformat(str(birth_date_str))
        sep1 = date(season, 9, 1)
        return (sep1 - bd).days / 365.25
    except (ValueError, TypeError):
        return None


def build_player_features(
    conn: duckdb.DuckDBPyConnection,
    target_seasons: list[int],
) -> int:
    """Build player_features rows for each target season.

    For season N: uses N-1 as lag, N-2 and N-1 for rolling avg, N as target.
    """
    total = 0
    for season in target_seasons:
        prior = season - 1
        prior2 = season - 2
        conn.execute("DELETE FROM player_features WHERE season = ?", [season])

        # Get all skill-position players who have prior season stats
        players = conn.execute(f"""
            SELECT DISTINCT s.gsis_id, p.position, p.birth_date,
                p.draft_round, p.draft_pick, p.draft_year
            FROM player_season_stats s
            JOIN players p ON s.gsis_id = p.gsis_id
            WHERE s.season = ? AND p.position IN {SKILL_POS_SQL}
        """, [prior]).fetchall()

        for gsis_id, position, birth_date, draft_round, draft_pick, draft_year in players:
            # Prior season (N-1) stats
            s1 = conn.execute("""
                SELECT games, targets, receptions, rec_yards, rec_tds, air_yards,
                       yards_after_catch, carries, rush_yards, rush_tds,
                       attempts, completions, pass_yards, pass_tds, interceptions,
                       fantasy_points_ppr, epa_per_play, cpoe, team
                FROM player_season_stats WHERE gsis_id = ? AND season = ?
            """, [gsis_id, prior]).fetchone()
            if not s1:
                continue

            (games, targets, recs, rec_yards, rec_tds, air_yards, yac,
             carries, rush_yards, rush_tds, attempts, comps, pass_yards,
             pass_tds, ints, fpts, epa, cpoe, team) = s1

            # Two-seasons-ago (N-2) stats for rolling average
            s2 = conn.execute("""
                SELECT fantasy_points_ppr, targets, carries
                FROM player_season_stats WHERE gsis_id = ? AND season = ?
            """, [gsis_id, prior2]).fetchone()

            # Target: season N actual
            target_row = conn.execute("""
                SELECT fantasy_points_ppr, games
                FROM player_season_stats WHERE gsis_id = ? AND season = ?
            """, [gsis_id, season]).fetchone()

            # Rate stats (guard div by zero)
            g = max(games or 1, 1)
            t = max(targets or 0, 0)
            c = max(carries or 0, 0)
            r = max(recs or 0, 0)
            a = max(attempts or 0, 0)

            catch_rate = recs / t if t > 0 else None
            ypt = rec_yards / t if t > 0 else None
            ypc = rush_yards / c if c > 0 else None
            ayp = air_yards / t if t > 0 else None
            yac_pr = yac / r if r > 0 else None
            comp_pct = comps / a if a > 0 else None
            ypa = pass_yards / a if a > 0 else None
            td_rate_rec = rec_tds / t if t > 0 else None
            td_rate_rush = rush_tds / c if c > 0 else None

            # Rolling 2-year averages
            if s2:
                roll2_fpts = (fpts + s2[0]) / 2
                roll2_targets = (t + s2[1]) / 2
                roll2_carries = (c + s2[2]) / 2
            else:
                roll2_fpts = fpts
                roll2_targets = float(t)
                roll2_carries = float(c)

            # Team environment
            tf = conn.execute("""
                SELECT pass_rate, pass_epa, total_plays
                FROM team_features WHERE team = ? AND season = ?
            """, [team, season]).fetchone()
            team_pass_rate = tf[0] if tf else None
            team_pass_epa = tf[1] if tf else None
            team_plays = tf[2] if tf else None

            # Depth chart
            dc = conn.execute("""
                SELECT depth_chart_pos FROM rosters
                WHERE gsis_id = ? AND season = ? AND week = 1
                ORDER BY week LIMIT 1
            """, [gsis_id, prior]).fetchone()
            depth = dc[0] if dc else None

            # Rookie flag: first NFL season
            is_rookie = 1 if draft_year == season else 0

            # Draft pick value (compute overall_pick from round + pick)
            overall = None
            if draft_round and draft_pick:
                overall = (draft_round - 1) * 32 + draft_pick
            pick_value = _draft_pick_value(overall)

            # Combine data
            comb = conn.execute("""
                SELECT combine_forty, combine_vertical FROM combine_data
                WHERE gsis_id = ? ORDER BY season LIMIT 1
            """, [gsis_id]).fetchone()
            # combine_data table doesn't have those col names — use actual cols
            comb2 = conn.execute("""
                SELECT forty_yard, vertical FROM combine_data
                WHERE gsis_id = ? ORDER BY season LIMIT 1
            """, [gsis_id]).fetchone()
            forty = comb2[0] if comb2 else None
            vertical = comb2[1] if comb2 else None

            age = _age_on_sept_1(birth_date, season)
            experience = (season - draft_year) if draft_year else None

            conn.execute("""
                INSERT OR REPLACE INTO player_features (
                    gsis_id, season, position, age, experience,
                    prev_games, prev_targets, prev_receptions, prev_rec_yards, prev_rec_tds,
                    prev_air_yards, prev_yac, prev_carries, prev_rush_yards, prev_rush_tds,
                    prev_attempts, prev_completions, prev_pass_yards, prev_pass_tds,
                    prev_interceptions, prev_fantasy_ppr,
                    targets_per_game, catches_per_game, rec_yards_per_game, rec_tds_per_game,
                    carries_per_game, rush_yards_per_game,
                    catch_rate, yards_per_target, yards_per_carry,
                    air_yards_per_target, yac_per_reception,
                    pass_completion_pct, pass_yards_per_attempt,
                    td_rate_receiving, td_rate_rushing,
                    prev_epa_per_play, prev_cpoe,
                    roll2_fantasy_ppr, roll2_targets, roll2_carries,
                    team, team_pass_rate, team_pass_epa, team_total_plays,
                    depth_chart_pos, is_rookie, draft_round, draft_pick, draft_pick_value,
                    combine_forty, combine_vertical,
                    next_season_fantasy_ppr, next_season_games
                ) VALUES (
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?
                )
            """, [
                gsis_id, season, position, age, experience,
                games, targets, recs, rec_yards, rec_tds,
                air_yards, yac, carries, rush_yards, rush_tds,
                attempts, comps, pass_yards, pass_tds, ints,
                fpts,
                t/g, recs/g, (rec_yards or 0)/g, (rec_tds or 0)/g,
                c/g, (rush_yards or 0)/g,
                catch_rate, ypt, ypc, ayp, yac_pr,
                comp_pct, ypa, td_rate_rec, td_rate_rush,
                epa, cpoe,
                roll2_fpts, roll2_targets, roll2_carries,
                team, team_pass_rate, team_pass_epa, team_plays,
                depth, is_rookie, draft_round, draft_pick, pick_value,
                forty, vertical,
                target_row[0] if target_row else None,
                target_row[1] if target_row else None,
            ])
            total += 1

        conn.commit()
        print(f"  Season {season}: {total} player-feature rows built so far")

    return total


def ingest(start: int = 2006, end: int = 2025, db_path=None) -> None:
    conn = get_conn(db_path) if db_path else get_conn()
    init_schema(conn)
    n = build_player_features(conn, list(range(start, end + 1)))
    print(f"player_features: {n:,} rows built")
    conn.close()


if __name__ == "__main__":
    ingest()
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
/Users/theoauyeung/miniforge3/bin/python3.12 -m pytest tests/features/test_player_features.py -v
```

Expected: 4 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/tay/features/player_features.py tests/features/test_player_features.py
git commit -m "feat: player efficiency features — lag stats, rate stats, rolling averages, draft context"
```

---

### Task 5: Wire vacated opportunity into player features + pipeline

**Files:**
- Create: `src/tay/features/pipeline.py`
- Create: `scripts/build_features.py`

**Interfaces:**
- Consumes: all feature modules built in Tasks 1–4
- Produces: fully populated `player_features` (including `incoming_vacated_*`) and `team_features` tables

**Design:** After `player_features` rows are built, for each player look up their team's vacated opportunity for the target season and write it to `player_features.incoming_vacated_targets` / `incoming_vacated_carries`.

- [ ] **Step 1: Create `src/tay/features/pipeline.py`**

```python
"""Orchestrate the full feature engineering pipeline."""
from __future__ import annotations
import duckdb
from tay.db import get_conn, init_schema
from tay.features.team_features import build_team_features
from tay.features.vacated_opportunity import compute_vacated_opportunity
from tay.features.player_features import build_player_features


def run_pipeline(
    start: int = 2006,
    end: int = 2025,
    db_path=None,
) -> None:
    """Run all feature engineering steps in order."""
    conn = get_conn(db_path) if db_path else get_conn()
    init_schema(conn)
    seasons = list(range(start, end + 1))

    print("Step 1/3: Building team environment features...")
    n = build_team_features(conn, seasons)
    print(f"  {n:,} team-feature rows")

    print("Step 2/3: Computing vacated opportunity...")
    n = compute_vacated_opportunity(conn, seasons)
    print(f"  {n:,} team-seasons updated with vacated opportunity")

    print("Step 3/3: Building player features...")
    n = build_player_features(conn, seasons)
    print(f"  {n:,} player-feature rows")

    # Step 3b: Backfill incoming_vacated_* onto player_features
    print("Step 3b: Backfilling vacated opportunity into player features...")
    conn.execute("""
        UPDATE player_features pf
        SET incoming_vacated_targets = (
            SELECT CASE
                WHEN pf.position = 'WR' THEN tf.vacated_wr_targets
                WHEN pf.position = 'TE' THEN tf.vacated_te_targets
                WHEN pf.position = 'QB' THEN tf.vacated_qb_attempts
                ELSE 0
            END
            FROM team_features tf
            WHERE tf.team = pf.team AND tf.season = pf.season
        ),
        incoming_vacated_carries = (
            SELECT CASE
                WHEN pf.position = 'RB' THEN tf.vacated_rb_carries
                ELSE 0
            END
            FROM team_features tf
            WHERE tf.team = pf.team AND tf.season = pf.season
        )
    """)
    conn.commit()

    # Summary
    n_pf = conn.execute("SELECT COUNT(*) FROM player_features").fetchone()[0]
    n_tf = conn.execute("SELECT COUNT(*) FROM team_features").fetchone()[0]
    seasons_covered = conn.execute(
        "SELECT COUNT(DISTINCT season) FROM player_features"
    ).fetchone()[0]
    print(f"\nFeature pipeline complete:")
    print(f"  player_features: {n_pf:,} rows ({seasons_covered} seasons)")
    print(f"  team_features:   {n_tf:,} rows")
    conn.close()
```

- [ ] **Step 2: Create `scripts/build_features.py`**

```python
#!/usr/bin/env python3
"""Build feature tables from ingested DuckDB data.

Usage:
    python scripts/build_features.py [--start 2006] [--end 2025]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tay.features.pipeline import run_pipeline


def main():
    p = argparse.ArgumentParser(description="TAY Analytics FF — feature engineering pipeline")
    p.add_argument("--start", type=int, default=2006, help="First target season (default 2006)")
    p.add_argument("--end", type=int, default=2025, help="Last target season (default 2025)")
    args = p.parse_args()
    run_pipeline(start=args.start, end=args.end)


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Make executable and test --help**

```bash
chmod +x scripts/build_features.py
/Users/theoauyeung/miniforge3/bin/python3.12 scripts/build_features.py --help
```

- [ ] **Step 4: Run full feature pipeline on real data**

```bash
/Users/theoauyeung/miniforge3/bin/python3.12 scripts/build_features.py --start 2006 --end 2025
```

Expected output (approximate):
```
Step 1/3: Building team environment features...
  640 team-feature rows
Step 2/3: Computing vacated opportunity...
  640 team-seasons updated with vacated opportunity
Step 3/3: Building player features...
  Season 2006: ...
  ...
  10,000+ player-feature rows
Step 3b: Backfilling vacated opportunity into player features...
Feature pipeline complete:
  player_features: 10,000+ rows (20 seasons)
  team_features:   640 rows
```

- [ ] **Step 5: Spot-check data quality**

```python
from tay.db import get_conn
conn = get_conn()

# Antonio Brown 2015 features (predicting from 2014 stats)
row = conn.execute("""
    SELECT gsis_id, season, prev_targets, prev_rec_yards, catch_rate,
           yards_per_target, roll2_fantasy_ppr, next_season_fantasy_ppr
    FROM player_features
    WHERE gsis_id IN (
        SELECT gsis_id FROM players WHERE name ILIKE '%antonio brown%'
    )
    AND season = 2015
""").fetchone()
print("Antonio Brown 2015 features:", row)

# Verify leakage: prev_targets for 2015 should be 2014's 182 targets
# next_season_fantasy_ppr for 2015 should be 2015's ~380 PPR points
assert row[2] == 182   # 2014 targets

# Check vacated opportunity backfilled
conn.execute("SELECT AVG(incoming_vacated_targets) FROM player_features WHERE position='WR'").fetchone()
conn.close()
```

- [ ] **Step 6: Run full test suite**

```bash
/Users/theoauyeung/miniforge3/bin/python3.12 -m pytest tests/ -v 2>&1 | tail -10
```

Expected: all tests PASS

- [ ] **Step 7: Commit**

```bash
git add src/tay/features/pipeline.py scripts/build_features.py
git commit -m "feat: feature pipeline — team env, vacated opportunity, player features assembled"
```

---

### Task 6: Final verification and data quality report

**Files:**
- No new files — validation and cleanup

- [ ] **Step 1: Check coverage across all seasons**

```python
from tay.db import get_conn
conn = get_conn()

print("player_features by season:")
rows = conn.execute("""
    SELECT season, COUNT(*) AS players,
           ROUND(AVG(prev_targets), 1) AS avg_targets,
           ROUND(AVG(next_season_fantasy_ppr), 1) AS avg_next_fpts
    FROM player_features
    GROUP BY season ORDER BY season
""").fetchall()
for r in rows:
    print(f"  {r[0]}: {r[1]} players, avg targets={r[2]}, avg next fpts={r[3]}")
conn.close()
```

Expected: 20 seasons (2006–2025), 400–700 player rows per season.

- [ ] **Step 2: Check NULL rates**

```python
from tay.db import get_conn
conn = get_conn()

cols = ['catch_rate', 'yards_per_target', 'roll2_fantasy_ppr',
        'team_pass_rate', 'next_season_fantasy_ppr']
for col in cols:
    null_pct = conn.execute(f"""
        SELECT ROUND(100.0 * COUNT(*) FILTER (WHERE {col} IS NULL) / COUNT(*), 1)
        FROM player_features
    """).fetchone()[0]
    print(f"  {col}: {null_pct}% NULL")
conn.close()
```

Expected:
- `catch_rate`: <30% NULL (receivers only; QBs will be NULL which is fine)
- `yards_per_target`: <30% NULL
- `roll2_fantasy_ppr`: <10% NULL (only 2006 first year will have partial)
- `team_pass_rate`: <5% NULL
- `next_season_fantasy_ppr`: ~10% NULL (players who retired or have no N+1 season)

- [ ] **Step 3: Update Makefile**

Add a `features` target to the Makefile:
```makefile
features:
	$(PYTHON) scripts/build_features.py
```

- [ ] **Step 4: Final commit**

```bash
git add Makefile
git commit -m "feat: Plan E complete — feature engineering pipeline with 10k+ training rows"
```

---
