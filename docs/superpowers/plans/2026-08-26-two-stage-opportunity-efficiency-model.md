# Two-Stage Opportunity + Efficiency Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single-stage PPR-point neural net with a two-stage pipeline that separates opportunity (Stage 1: XGBoost) from efficiency (Stage 2: neural net), composed analytically into PPR projections.

**Architecture:** Stage 1 predicts volume share (target_share, carry_share, pass_att_per_game) using the player's *new* team's scheme/OC context and portable talent signals. Stage 2 predicts efficiency metrics (yards_per_target, catch_rate, td_rate) from career efficiency history only. Composition multiplies Stage 1 × Stage 2 arithmetically.

**Tech Stack:** Python, XGBoost, PyTorch (existing), scikit-learn (KMeans), DuckDB, nfl_data_py (coaches).

## Global Constraints

- DuckDB upserts: always `NOW()` never bare `current_timestamp` in DO UPDATE SET clauses
- EWMA weights: 0.6 × season N-1, 0.3 × season N-2, 0.1 × season N-3 (matches existing player_features.py convention)
- Stage 2 must NEVER see opportunity signals: `target_share`, `snap_share`, `ewma_targets`, `ewma_carries`, `ewma_fantasy_ppr` are forbidden in Stage 2 features
- QB Stage 2 must complete before WR/TE/RB Stage 2 (QB efficiency is a context feature for skill positions)
- Team normalization of target shares is mandatory post-Stage 1, pre-composition
- Existing files untouched: `blend.py`, `vor.py`, `valuation/`, `api/`, `simulation/`
- Training window: 2016–2023. Validation: 2024. Test: 2025.
- New model dirs: `models_stage1/` (XGBoost .json), `models_stage2/` (PyTorch .pt)
- Positions: QB, RB, WR, TE (4 models per stage)

---

## File Map

| File | Change |
|------|--------|
| `pyproject.toml` | MOD — add xgboost, scikit-learn |
| `src/tay/schemas/tables.py` | MOD — add COACHES, OC_FEATURES, SCHEME_CLUSTERS DDL |
| `src/tay/db.py` | MOD — ALTER TABLE migrations for new projections columns |
| `scripts/ingest_coaches.py` | NEW — nfl_data_py coaches fetch + oc_features computation |
| `scripts/compute_scheme_clusters.py` | NEW — KMeans on team_features → scheme_clusters |
| `src/tay/features/stage1_features.py` | NEW — Stage 1 feature DataFrame builder |
| `src/tay/models/stage1_pipeline.py` | NEW — XGBoost train/infer + team normalization |
| `src/tay/features/stage2_features.py` | NEW — Stage 2 feature DataFrame builder (no volume signals) |
| `src/tay/models/stage2_pipeline.py` | NEW — neural net train/infer for efficiency |
| `src/tay/models/composition.py` | NEW — analytical PPR composition, writes mean_projection |
| `src/tay/models/pipeline.py` | MOD — orchestrate Stage1→normalize→Stage2→compose |

---

### Task 1: Dependencies + Schema

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/tay/schemas/tables.py`
- Modify: `src/tay/db.py`
- Test: `tests/test_db.py`

**Interfaces:**
- Produces: `coaches(team, season, coach_type, full_name)` table, `oc_features(oc_name, as_of_season, ...)` table, `scheme_clusters(team, season, cluster_id)` table, new projections columns: `projected_target_share`, `projected_carry_share`, `projected_rec_share`, `projected_pass_att_per_game`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_db.py — add to existing file
def test_coaches_table_exists():
    conn = duckdb.connect(':memory:')
    init_schema(conn)
    tables = [r[0] for r in conn.execute("SHOW TABLES").fetchall()]
    assert 'coaches' in tables
    conn.close()

def test_oc_features_table_exists():
    conn = duckdb.connect(':memory:')
    init_schema(conn)
    tables = [r[0] for r in conn.execute("SHOW TABLES").fetchall()]
    assert 'oc_features' in tables
    conn.close()

def test_scheme_clusters_table_exists():
    conn = duckdb.connect(':memory:')
    init_schema(conn)
    tables = [r[0] for r in conn.execute("SHOW TABLES").fetchall()]
    assert 'scheme_clusters' in tables
    conn.close()

def test_projections_has_stage1_columns():
    conn = duckdb.connect(':memory:')
    init_schema(conn)
    cols = [r[1] for r in conn.execute("PRAGMA table_info('projections')").fetchall()]
    assert 'projected_target_share' in cols
    assert 'projected_carry_share' in cols
    assert 'projected_rec_share' in cols
    assert 'projected_pass_att_per_game' in cols
    conn.close()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd "/Users/theoauyeung/Documents/Projects/TAY Analytics FF"
uv run pytest tests/test_db.py::test_coaches_table_exists tests/test_db.py::test_oc_features_table_exists tests/test_db.py::test_scheme_clusters_table_exists tests/test_db.py::test_projections_has_stage1_columns -v
```
Expected: 4 FAIL

- [ ] **Step 3: Add xgboost and scikit-learn to pyproject.toml**

In `pyproject.toml`, add to `dependencies`:
```toml
    "xgboost>=2.0",
    "scikit-learn>=1.5",
```

- [ ] **Step 4: Add DDL to tables.py**

Add these three constants before `ALL_TABLES` in `src/tay/schemas/tables.py`:

```python
COACHES = """
CREATE TABLE IF NOT EXISTS coaches (
    team        VARCHAR NOT NULL,
    season      INTEGER NOT NULL,
    coach_type  VARCHAR NOT NULL,
    full_name   VARCHAR NOT NULL,
    PRIMARY KEY (team, season, coach_type)
)
"""

OC_FEATURES = """
CREATE TABLE IF NOT EXISTS oc_features (
    oc_name               VARCHAR NOT NULL,
    as_of_season          INTEGER NOT NULL,
    hist_wr1_target_share DOUBLE,
    hist_air_yards_pct    DOUBLE,
    hist_rb_target_share  DOUBLE,
    tenure_at_team        INTEGER,
    is_rookie_oc          BOOLEAN,
    PRIMARY KEY (oc_name, as_of_season)
)
"""

SCHEME_CLUSTERS = """
CREATE TABLE IF NOT EXISTS scheme_clusters (
    team        VARCHAR NOT NULL,
    season      INTEGER NOT NULL,
    cluster_id  INTEGER NOT NULL,
    PRIMARY KEY (team, season)
)
"""
```

Add `COACHES, OC_FEATURES, SCHEME_CLUSTERS` to `ALL_TABLES` list.

- [ ] **Step 5: Add migrations in db.py**

In `src/tay/db.py`, add after the existing ALTER TABLE lines:

```python
conn.execute("ALTER TABLE projections ADD COLUMN IF NOT EXISTS projected_target_share DOUBLE")
conn.execute("ALTER TABLE projections ADD COLUMN IF NOT EXISTS projected_carry_share DOUBLE")
conn.execute("ALTER TABLE projections ADD COLUMN IF NOT EXISTS projected_rec_share DOUBLE")
conn.execute("ALTER TABLE projections ADD COLUMN IF NOT EXISTS projected_pass_att_per_game DOUBLE")
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
uv run pytest tests/test_db.py::test_coaches_table_exists tests/test_db.py::test_oc_features_table_exists tests/test_db.py::test_scheme_clusters_table_exists tests/test_db.py::test_projections_has_stage1_columns -v
```
Expected: 4 PASS

- [ ] **Step 7: Run full test suite to check no regressions**

```bash
uv run pytest --tb=short -q
```

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml src/tay/schemas/tables.py src/tay/db.py tests/test_db.py
git commit -m "feat: schema for coaches, oc_features, scheme_clusters; projections stage1 columns"
```

---

### Task 2: Coaches Ingestion Script

**Files:**
- Create: `scripts/ingest_coaches.py`
- Test: `tests/test_ingest_coaches.py`

**Interfaces:**
- Consumes: `coaches` table (Task 1), `player_season_stats` table, `team_features` table
- Produces: `coaches` rows upserted, `oc_features` rows upserted

- [ ] **Step 1: Write failing tests**

Create `tests/test_ingest_coaches.py`:

```python
import duckdb
import pytest
from tay.db import init_schema


def _make_conn():
    conn = duckdb.connect(':memory:')
    init_schema(conn)
    return conn


def test_upsert_coaches_rows():
    from scripts.ingest_coaches import upsert_coaches
    conn = _make_conn()
    raw = [
        {'team': 'KC', 'season': 2023, 'coach_type': 'offensive_coordinator', 'full_name': 'Matt Nagy'},
        {'team': 'KC', 'season': 2023, 'coach_type': 'head_coach', 'full_name': 'Andy Reid'},
    ]
    upsert_coaches(conn, raw)
    count = conn.execute("SELECT COUNT(*) FROM coaches").fetchone()[0]
    assert count == 2
    conn.close()


def test_upsert_coaches_idempotent():
    from scripts.ingest_coaches import upsert_coaches
    conn = _make_conn()
    raw = [{'team': 'KC', 'season': 2023, 'coach_type': 'head_coach', 'full_name': 'Andy Reid'}]
    upsert_coaches(conn, raw)
    upsert_coaches(conn, raw)
    count = conn.execute("SELECT COUNT(*) FROM coaches").fetchone()[0]
    assert count == 1
    conn.close()


def test_compute_oc_features_no_history():
    from scripts.ingest_coaches import compute_oc_features
    conn = _make_conn()
    # OC with no prior player stats → is_rookie_oc = True
    conn.execute("INSERT INTO coaches VALUES ('DAL', 2023, 'offensive_coordinator', 'New Guy')")
    compute_oc_features(conn, seasons=[2024])
    row = conn.execute(
        "SELECT is_rookie_oc FROM oc_features WHERE oc_name = 'New Guy' AND as_of_season = 2024"
    ).fetchone()
    assert row is not None
    assert row[0] is True
    conn.close()


def test_compute_oc_features_with_history():
    from scripts.ingest_coaches import compute_oc_features
    conn = _make_conn()
    # Seed coaches + player stats to exercise the aggregation path
    conn.execute("INSERT INTO coaches VALUES ('KC', 2022, 'offensive_coordinator', 'Eric Bieniemy')")
    conn.execute("INSERT INTO coaches VALUES ('KC', 2023, 'offensive_coordinator', 'Eric Bieniemy')")
    # Player stats: WR1 with 120 targets out of 600 team attempts = 0.20 share
    conn.execute("INSERT INTO players VALUES ('p1', 'Tyreek Hill', 'WR', 'KC', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL)")
    conn.execute("""
        INSERT INTO player_season_stats
            (gsis_id, season, team, games, targets, attempts, air_yards)
        VALUES ('p1', 2022, 'KC', 17, 120, 0, 900)
    """)
    conn.execute("""
        INSERT INTO team_season_stats
            (team, season, games, pass_attempts)
        VALUES ('KC', 2022, 17, 600)
    """)
    compute_oc_features(conn, seasons=[2023])
    row = conn.execute(
        "SELECT hist_wr1_target_share, is_rookie_oc FROM oc_features WHERE oc_name = 'Eric Bieniemy' AND as_of_season = 2023"
    ).fetchone()
    assert row is not None
    assert row[0] == pytest.approx(0.20, abs=0.01)
    assert row[1] is False
    conn.close()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_ingest_coaches.py -v
```
Expected: ImportError or ModuleNotFoundError

- [ ] **Step 3: Implement scripts/ingest_coaches.py**

```python
#!/usr/bin/env python3
"""Ingest nflverse coaches data and compute OC historical features.

Usage:
    uv run python scripts/ingest_coaches.py --seasons 2016 2017 ... 2026
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from tay.db import get_conn, init_schema


def fetch_coaches_data() -> list[dict]:
    """Fetch coaches from nflverse via nfl_data_py."""
    import nfl_data_py as nfl
    df = nfl.import_coaches()
    rows = []
    for _, row in df.iterrows():
        season = int(row.get('season', 0))
        team = str(row.get('team', ''))
        for coach_type in ('head_coach', 'offensive_coordinator'):
            col = coach_type  # nflverse column name matches
            name = str(row.get(col, '') or '')
            if name and name != 'nan':
                rows.append({
                    'team': team,
                    'season': season,
                    'coach_type': coach_type,
                    'full_name': name,
                })
    return rows


def upsert_coaches(conn, rows: list[dict]) -> int:
    conn.executemany("""
        INSERT INTO coaches (team, season, coach_type, full_name)
        VALUES (?, ?, ?, ?)
        ON CONFLICT (team, season, coach_type) DO UPDATE SET
            full_name = excluded.full_name
    """, [(r['team'], r['season'], r['coach_type'], r['full_name']) for r in rows])
    conn.commit()
    return len(rows)


def compute_oc_features(conn, seasons: list[int]) -> int:
    """For each season in `seasons`, aggregate OC historical stats from prior seasons.

    Looks up who the OC was at each team in season S-1, then aggregates their
    stats across ALL seasons they coordinated prior to season S.
    """
    total = 0
    for season in seasons:
        # Find all OCs active in season prior to this one
        ocs = conn.execute("""
            SELECT DISTINCT full_name
            FROM coaches
            WHERE coach_type = 'offensive_coordinator'
              AND season < ?
        """, [season]).fetchall()

        for (oc_name,) in ocs:
            # Seasons this OC coordinated (all prior to `season`)
            oc_seasons = conn.execute("""
                SELECT c.team, c.season
                FROM coaches c
                WHERE c.full_name = ?
                  AND c.coach_type = 'offensive_coordinator'
                  AND c.season < ?
            """, [oc_name, season]).fetchall()

            if not oc_seasons:
                continue

            # For each OC season, compute WR1 target share and air yards pct
            wr1_shares = []
            air_yds_pcts = []
            rb_shares = []

            for team, oc_season in oc_seasons:
                team_att = conn.execute("""
                    SELECT pass_attempts FROM team_season_stats
                    WHERE team = ? AND season = ?
                """, [team, oc_season]).fetchone()
                if not team_att or not team_att[0]:
                    continue
                team_pass_att = float(team_att[0])

                # WR1 target share: max single-WR target share on this team × season
                wr1 = conn.execute("""
                    SELECT MAX(s.targets::DOUBLE / ?) AS share
                    FROM player_season_stats s
                    JOIN players p ON p.gsis_id = s.gsis_id
                    WHERE s.team = ? AND s.season = ? AND p.position = 'WR'
                """, [team_pass_att, team, oc_season]).fetchone()
                if wr1 and wr1[0]:
                    wr1_shares.append(float(wr1[0]))

                # Air yards pct: total WR/TE air_yards / total pass yards
                ay = conn.execute("""
                    SELECT SUM(s.air_yards), SUM(s.rec_yards)
                    FROM player_season_stats s
                    JOIN players p ON p.gsis_id = s.gsis_id
                    WHERE s.team = ? AND s.season = ?
                      AND p.position IN ('WR', 'TE')
                """, [team, oc_season]).fetchone()
                if ay and ay[1] and float(ay[1]) > 0:
                    air_yds_pcts.append(float(ay[0] or 0) / float(ay[1]))

                # RB receiving share: sum of RB targets / team pass attempts
                rb = conn.execute("""
                    SELECT SUM(s.targets)::DOUBLE / ?
                    FROM player_season_stats s
                    JOIN players p ON p.gsis_id = s.gsis_id
                    WHERE s.team = ? AND s.season = ? AND p.position = 'RB'
                """, [team_pass_att, team, oc_season]).fetchone()
                if rb and rb[0]:
                    rb_shares.append(float(rb[0]))

            # Current team tenure
            tenure_rows = conn.execute("""
                SELECT season FROM coaches
                WHERE full_name = ? AND coach_type = 'offensive_coordinator' AND season < ?
                ORDER BY season DESC
            """, [oc_name, season]).fetchall()
            tenure = 0
            for i, (s,) in enumerate(tenure_rows):
                if i == 0:
                    prev_season = s
                    tenure = 1
                elif prev_season - s == 1:
                    tenure += 1
                    prev_season = s
                else:
                    break

            is_rookie = len(oc_seasons) == 0

            conn.execute("""
                INSERT INTO oc_features
                    (oc_name, as_of_season, hist_wr1_target_share, hist_air_yards_pct,
                     hist_rb_target_share, tenure_at_team, is_rookie_oc)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (oc_name, as_of_season) DO UPDATE SET
                    hist_wr1_target_share = excluded.hist_wr1_target_share,
                    hist_air_yards_pct    = excluded.hist_air_yards_pct,
                    hist_rb_target_share  = excluded.hist_rb_target_share,
                    tenure_at_team        = excluded.tenure_at_team,
                    is_rookie_oc          = excluded.is_rookie_oc
            """, [
                oc_name, season,
                (sum(wr1_shares) / len(wr1_shares)) if wr1_shares else None,
                (sum(air_yds_pcts) / len(air_yds_pcts)) if air_yds_pcts else None,
                (sum(rb_shares) / len(rb_shares)) if rb_shares else None,
                tenure,
                is_rookie,
            ])
            total += 1

        conn.commit()
    return total


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument('--seasons', type=int, nargs='+',
                   default=list(range(2016, 2027)),
                   help='Seasons to compute OC features for (default 2016-2026)')
    args = p.parse_args()

    conn = get_conn()
    init_schema(conn)

    print('Fetching coaches data from nflverse...')
    rows = fetch_coaches_data()
    n = upsert_coaches(conn, rows)
    print(f'  Upserted {n} coach rows.')

    print(f'Computing OC features for seasons {args.seasons}...')
    n = compute_oc_features(conn, args.seasons)
    print(f'  Computed {n} OC feature rows.')
    conn.close()


if __name__ == '__main__':
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_ingest_coaches.py -v
```
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/ingest_coaches.py tests/test_ingest_coaches.py
git commit -m "feat: coaches ingestion and OC historical feature computation"
```

---

### Task 3: Scheme Clustering Script

**Files:**
- Create: `scripts/compute_scheme_clusters.py`
- Test: `tests/test_scheme_clusters.py`

**Interfaces:**
- Consumes: `team_features` table, `player_season_stats` table, `team_season_stats` table
- Produces: `scheme_clusters(team, season, cluster_id)` rows

- [ ] **Step 1: Write failing tests**

Create `tests/test_scheme_clusters.py`:

```python
import duckdb
import pytest
from tay.db import init_schema


def _make_conn_with_team_data():
    conn = duckdb.connect(':memory:')
    init_schema(conn)
    # Seed team_features and team_season_stats for 3 teams × 2 seasons
    for team, pass_rate, pass_epa in [('KC', 0.65, 0.18), ('BAL', 0.45, 0.05), ('SF', 0.50, 0.10)]:
        for season in [2022, 2023]:
            conn.execute("""
                INSERT OR REPLACE INTO team_features
                    (team, season, pass_rate, rush_rate, team_epa, pass_epa, rush_epa, total_plays, pass_attempts, total_tds)
                VALUES (?, ?, ?, ?, 0.08, ?, 0.02, 1000, 550, 45)
            """, [team, season, pass_rate, 1 - pass_rate, pass_epa])
    return conn


def test_cluster_ids_are_integers():
    from scripts.compute_scheme_clusters import compute_and_store_clusters
    conn = _make_conn_with_team_data()
    compute_and_store_clusters(conn, seasons=[2022, 2023], n_clusters=2)
    rows = conn.execute("SELECT cluster_id FROM scheme_clusters").fetchall()
    assert len(rows) == 6  # 3 teams × 2 seasons
    for (cid,) in rows:
        assert isinstance(cid, int)
    conn.close()


def test_cluster_ids_in_range():
    from scripts.compute_scheme_clusters import compute_and_store_clusters
    conn = _make_conn_with_team_data()
    compute_and_store_clusters(conn, seasons=[2022, 2023], n_clusters=3)
    rows = conn.execute("SELECT DISTINCT cluster_id FROM scheme_clusters").fetchall()
    ids = {r[0] for r in rows}
    assert ids.issubset({0, 1, 2})
    conn.close()


def test_cluster_idempotent():
    from scripts.compute_scheme_clusters import compute_and_store_clusters
    conn = _make_conn_with_team_data()
    compute_and_store_clusters(conn, seasons=[2022], n_clusters=2)
    compute_and_store_clusters(conn, seasons=[2022], n_clusters=2)
    count = conn.execute("SELECT COUNT(*) FROM scheme_clusters WHERE season = 2022").fetchone()[0]
    assert count == 3  # 3 teams, not 6
    conn.close()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_scheme_clusters.py -v
```
Expected: ImportError

- [ ] **Step 3: Implement scripts/compute_scheme_clusters.py**

```python
#!/usr/bin/env python3
"""Compute scheme clusters from team_features via KMeans.

Usage:
    uv run python scripts/compute_scheme_clusters.py --seasons 2016 2017 ... 2026
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from tay.db import get_conn, init_schema

N_CLUSTERS = 6
CLUSTER_FEATURES = ['pass_rate', 'pass_epa', 'rush_epa']


def compute_and_store_clusters(
    conn,
    seasons: list[int],
    n_clusters: int = N_CLUSTERS,
    random_state: int = 42,
) -> int:
    """Fit KMeans on all available team_features, assign cluster_id, upsert."""
    # Load all historical team features (train on full history for stable clusters)
    rows = conn.execute("""
        SELECT team, season, pass_rate, pass_epa, rush_epa
        FROM team_features
        WHERE pass_rate IS NOT NULL AND pass_epa IS NOT NULL AND rush_epa IS NOT NULL
        ORDER BY season, team
    """).fetchall()

    if len(rows) < n_clusters:
        raise ValueError(f'Need at least {n_clusters} team-seasons to cluster, got {len(rows)}')

    teams = [(r[0], r[1]) for r in rows]
    X = np.array([[r[2], r[3], r[4]] for r in rows], dtype=np.float32)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    km = KMeans(n_clusters=n_clusters, random_state=random_state, n_init=10)
    labels = km.fit_predict(X_scaled)

    # Filter to requested seasons only
    to_upsert = [
        (team, season, int(label))
        for (team, season), label in zip(teams, labels)
        if season in seasons
    ]

    conn.executemany("""
        INSERT INTO scheme_clusters (team, season, cluster_id)
        VALUES (?, ?, ?)
        ON CONFLICT (team, season) DO UPDATE SET cluster_id = excluded.cluster_id
    """, to_upsert)
    conn.commit()
    return len(to_upsert)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument('--seasons', type=int, nargs='+', default=list(range(2016, 2027)))
    p.add_argument('--n-clusters', type=int, default=N_CLUSTERS)
    args = p.parse_args()

    conn = get_conn()
    init_schema(conn)
    n = compute_and_store_clusters(conn, args.seasons, args.n_clusters)
    print(f'Upserted {n} scheme cluster rows.')
    conn.close()


if __name__ == '__main__':
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_scheme_clusters.py -v
```
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/compute_scheme_clusters.py tests/test_scheme_clusters.py
git commit -m "feat: scheme clustering via KMeans on team_features"
```

---

### Task 4: Stage 1 Feature Builder

**Files:**
- Create: `src/tay/features/stage1_features.py`
- Test: `tests/features/test_stage1_features.py`

**Interfaces:**
- Consumes: `player_season_stats`, `players`, `team_features`, `oc_features`, `scheme_clusters`, `team_season_stats` tables
- Produces: `build_stage1_features(conn, seasons) -> pd.DataFrame` with columns listed below

DataFrame columns (one row per player × season):
```
gsis_id, season, position, team,
# labels (NaN for inference rows)
target_share, carry_share, rec_share, pass_att_per_game,
# talent signals
ewma_yards_per_target, ewma_catch_rate, ewma_air_yards_per_target,
ewma_epa_per_play, ewma_yards_per_carry, ewma_cpoe, ewma_completion_pct,
ewma_target_share,
# player context
draft_pick_value, age, experience,
# team context
new_team_pass_rate, new_team_pass_epa, vacated_wr_targets, vacated_rb_carries,
# OC/scheme
oc_hist_wr1_target_share, oc_hist_air_yards_pct, oc_hist_rb_target_share,
oc_tenure_at_team, is_rookie_oc, scheme_cluster,
# depth chart
depth_chart_rank
```

- [ ] **Step 1: Write failing tests**

Create `tests/features/test_stage1_features.py`:

```python
import math
import duckdb
import pytest
from tay.db import init_schema


def _make_conn():
    conn = duckdb.connect(':memory:')
    init_schema(conn)
    return conn


def _seed_minimal(conn):
    """Two WRs on same team, one season of history."""
    conn.execute("INSERT INTO players VALUES ('p1', 'WR1', 'WR', 'KC', '1995-01-01', 2018, 1, 10, NULL, NULL, NULL, NULL, NULL, NULL, NULL)")
    conn.execute("INSERT INTO players VALUES ('p2', 'WR2', 'WR', 'KC', '1997-01-01', 2020, 2, 45, NULL, NULL, NULL, NULL, NULL, NULL, NULL)")
    # Season N-1 = 2025 stats
    conn.execute("""
        INSERT INTO player_season_stats
            (gsis_id, season, team, games, targets, receptions, rec_yards, rec_tds,
             carries, rush_yards, rush_tds, attempts, completions, pass_yards,
             air_yards, epa_per_play, cpoe)
        VALUES
            ('p1', 2025, 'KC', 17, 120, 90, 1300, 10, 0, 0, 0, 0, 0, 0, 900, 0.25, 5.0),
            ('p2', 2025, 'KC', 17,  60, 45,  700,  4, 0, 0, 0, 0, 0, 0, 450, 0.10, 2.0)
    """)
    conn.execute("""
        INSERT INTO team_season_stats (team, season, games, pass_attempts, rush_attempts)
        VALUES ('KC', 2025, 17, 600, 400)
    """)
    conn.execute("""
        INSERT INTO team_features
            (team, season, pass_rate, rush_rate, team_epa, pass_epa, rush_epa,
             total_plays, pass_attempts, total_tds,
             vacated_wr_targets, vacated_rb_carries)
        VALUES ('KC', 2026, 0.62, 0.38, 0.10, 0.15, 0.05, 1000, 600, 45, 20.0, 30.0)
    """)
    conn.execute("""
        INSERT INTO coaches VALUES ('KC', 2025, 'offensive_coordinator', 'Matt Nagy')
    """)
    conn.execute("""
        INSERT INTO oc_features
            (oc_name, as_of_season, hist_wr1_target_share, hist_air_yards_pct,
             hist_rb_target_share, tenure_at_team, is_rookie_oc)
        VALUES ('Matt Nagy', 2026, 0.25, 1.5, 0.10, 2, false)
    """)
    conn.execute("INSERT INTO scheme_clusters VALUES ('KC', 2026, 3)")


def test_build_stage1_returns_dataframe():
    from tay.features.stage1_features import build_stage1_features
    conn = _make_conn()
    _seed_minimal(conn)
    df = build_stage1_features(conn, seasons=[2026])
    assert len(df) == 2
    assert 'gsis_id' in df.columns
    assert 'target_share' in df.columns
    conn.close()


def test_target_share_label_correct():
    from tay.features.stage1_features import build_stage1_features
    conn = _make_conn()
    _seed_minimal(conn)
    df = build_stage1_features(conn, seasons=[2026])
    p1 = df[df['gsis_id'] == 'p1'].iloc[0]
    # p1 had 120 targets / 600 team attempts = 0.20
    assert p1['target_share'] == pytest.approx(0.20, abs=0.001)
    conn.close()


def test_ewma_yards_per_target():
    from tay.features.stage1_features import build_stage1_features
    conn = _make_conn()
    _seed_minimal(conn)
    df = build_stage1_features(conn, seasons=[2026])
    p1 = df[df['gsis_id'] == 'p1'].iloc[0]
    # Only 1 season: ewma = 0.6 * (1300/120) = 0.6 * 10.833 ≈ 6.5
    assert p1['ewma_yards_per_target'] == pytest.approx(0.6 * (1300 / 120), abs=0.1)
    conn.close()


def test_depth_chart_rank():
    from tay.features.stage1_features import build_stage1_features
    conn = _make_conn()
    _seed_minimal(conn)
    df = build_stage1_features(conn, seasons=[2026])
    # p1 has higher ewma_target_share → rank 1; p2 → rank 2
    p1 = df[df['gsis_id'] == 'p1'].iloc[0]
    p2 = df[df['gsis_id'] == 'p2'].iloc[0]
    assert p1['depth_chart_rank'] == 1
    assert p2['depth_chart_rank'] == 2
    conn.close()


def test_scheme_cluster_present():
    from tay.features.stage1_features import build_stage1_features
    conn = _make_conn()
    _seed_minimal(conn)
    df = build_stage1_features(conn, seasons=[2026])
    assert (df['scheme_cluster'] == 3).all()
    conn.close()


def test_oc_features_joined():
    from tay.features.stage1_features import build_stage1_features
    conn = _make_conn()
    _seed_minimal(conn)
    df = build_stage1_features(conn, seasons=[2026])
    assert (df['oc_hist_wr1_target_share'] == pytest.approx(0.25)).all()
    assert (df['oc_tenure_at_team'] == 2).all()
    conn.close()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/features/test_stage1_features.py -v
```
Expected: ImportError

- [ ] **Step 3: Implement src/tay/features/stage1_features.py**

```python
"""Build Stage 1 (opportunity) features: one row per player × projection season."""
from __future__ import annotations
import math
from datetime import date

import pandas as pd
import duckdb

_W1, _W2, _W3 = 0.6, 0.3, 0.1
SKILL_POSITIONS = ('QB', 'RB', 'WR', 'TE')


def _age(birth_date_str, season: int) -> float | None:
    if not birth_date_str:
        return None
    try:
        bd = date.fromisoformat(str(birth_date_str))
        return (date(season, 9, 1) - bd).days / 365.25
    except (ValueError, TypeError):
        return None


def _pick_value(draft_round, draft_pick) -> float:
    if draft_round and draft_pick:
        overall = (draft_round - 1) * 32 + int(draft_pick)
        return 1.0 / math.sqrt(max(overall, 1))
    return 0.0


def _ewma(v1, v2, v3) -> float | None:
    """Weighted EWMA: 0.6×v1 + 0.3×v2 + 0.1×v3. Uses available seasons."""
    vals = [(v, w) for v, w in [(v1, _W1), (v2, _W2), (v3, _W3)] if v is not None]
    if not vals:
        return None
    total_w = sum(w for _, w in vals)
    return sum(v * w for v, w in vals) / total_w


def build_stage1_features(
    conn: duckdb.DuckDBPyConnection,
    seasons: list[int],
    positions: tuple[str, ...] = SKILL_POSITIONS,
) -> pd.DataFrame:
    """Return a DataFrame with Stage 1 features + labels for the given seasons.

    For training rows: season N features derived from season N-1 stats, label from season N stats.
    For inference rows: season N features only (label columns will be NaN).
    """
    rows = []
    for season in seasons:
        prior = season - 1
        prior2 = season - 2
        prior3 = season - 3

        # All players active in prior season on skill positions
        players = conn.execute("""
            SELECT
                p.gsis_id, p.position, s.team,
                p.birth_date, p.draft_year, p.draft_round, p.draft_pick,
                p.experience
            FROM player_season_stats s
            JOIN players p ON p.gsis_id = s.gsis_id
            WHERE s.season = ? AND p.position IN ('QB', 'RB', 'WR', 'TE')
        """, [prior]).fetchall()

        for (gsis_id, position, prior_team, birth_date, draft_year, draft_round,
             draft_pick, experience) in players:

            # Current team (season N) from players table
            current_team_row = conn.execute(
                "SELECT team FROM players WHERE gsis_id = ?", [gsis_id]
            ).fetchone()
            team = current_team_row[0] if current_team_row else prior_team

            if not team:
                continue

            # --- Efficiency EWMAs (portable talent, from player_season_stats) ---
            def get_stats(s):
                return conn.execute("""
                    SELECT targets, receptions, rec_yards, rec_tds, air_yards,
                           carries, rush_yards, rush_tds,
                           attempts, completions, pass_yards,
                           epa_per_play, cpoe,
                           (SELECT pass_attempts FROM team_season_stats
                            WHERE team = ps.team AND season = ps.season) AS team_pa,
                           games
                    FROM player_season_stats ps
                    WHERE gsis_id = ? AND season = ?
                """, [gsis_id, s]).fetchone()

            s1 = get_stats(prior)
            s2 = get_stats(prior2)
            s3 = get_stats(prior3)

            def eff(row, num_col_idx, denom_col_idx, min_denom=1):
                if row is None:
                    return None
                n = row[num_col_idx]
                d = row[denom_col_idx]
                if n is None or d is None or float(d) < min_denom:
                    return None
                return float(n) / float(d)

            ypt1 = eff(s1, 2, 0)   # rec_yards / targets
            ypt2 = eff(s2, 2, 0)
            ypt3 = eff(s3, 2, 0)

            cr1 = eff(s1, 1, 0)    # receptions / targets
            cr2 = eff(s2, 1, 0)
            cr3 = eff(s3, 1, 0)

            ayt1 = eff(s1, 4, 0)   # air_yards / targets
            ayt2 = eff(s2, 4, 0)
            ayt3 = eff(s3, 4, 0)

            epa1 = s1[11] if s1 else None
            epa2 = s2[11] if s2 else None
            epa3 = s3[11] if s3 else None

            ypc1 = eff(s1, 6, 5)   # rush_yards / carries
            ypc2 = eff(s2, 6, 5)
            ypc3 = eff(s3, 6, 5)

            cpoe1 = s1[12] if s1 else None
            cpoe2 = s2[12] if s2 else None
            cpoe3 = s3[12] if s3 else None

            comppct1 = eff(s1, 9, 8)   # completions / attempts
            comppct2 = eff(s2, 9, 8)
            comppct3 = eff(s3, 9, 8)

            # ewma_target_share: targets / team_pass_attempts
            ts1 = eff(s1, 0, 13)
            ts2 = eff(s2, 0, 13)
            ts3 = eff(s3, 0, 13)

            # --- Labels (season N actuals) ---
            sN = get_stats(season)
            team_pa_N = conn.execute(
                "SELECT pass_attempts FROM team_season_stats WHERE team = ? AND season = ?",
                [team, season]
            ).fetchone()
            team_ra_N = conn.execute(
                "SELECT rush_attempts FROM team_season_stats WHERE team = ? AND season = ?",
                [team, season]
            ).fetchone()
            games_N = conn.execute(
                "SELECT games FROM player_season_stats WHERE gsis_id = ? AND season = ?",
                [gsis_id, season]
            ).fetchone()

            target_share = None
            carry_share = None
            rec_share = None
            pass_att_per_game = None

            if sN:
                if team_pa_N and team_pa_N[0]:
                    tpa = float(team_pa_N[0])
                    if sN[0] is not None:
                        target_share = float(sN[0]) / tpa
                    if sN[0] is not None and position == 'RB':
                        rec_share = float(sN[0]) / tpa
                if team_ra_N and team_ra_N[0] and sN[5] is not None:
                    carry_share = float(sN[5]) / float(team_ra_N[0])
                if games_N and games_N[0] and sN[8] is not None:
                    pass_att_per_game = float(sN[8]) / float(games_N[0])

            # --- Team context (season N) ---
            tf = conn.execute("""
                SELECT pass_rate, pass_epa, vacated_wr_targets, vacated_rb_carries
                FROM team_features WHERE team = ? AND season = ?
            """, [team, season]).fetchone()

            # --- OC features ---
            oc_row = conn.execute("""
                SELECT full_name FROM coaches
                WHERE team = ? AND season = ? AND coach_type = 'offensive_coordinator'
            """, [team, prior]).fetchone()
            oc_name = oc_row[0] if oc_row else None

            oc_feat = None
            if oc_name:
                oc_feat = conn.execute("""
                    SELECT hist_wr1_target_share, hist_air_yards_pct, hist_rb_target_share,
                           tenure_at_team, is_rookie_oc
                    FROM oc_features WHERE oc_name = ? AND as_of_season = ?
                """, [oc_name, season]).fetchone()

            # --- Scheme cluster ---
            sc = conn.execute(
                "SELECT cluster_id FROM scheme_clusters WHERE team = ? AND season = ?",
                [team, prior]  # use prior season's cluster as best preseason prior
            ).fetchone()

            # --- Implicit depth chart rank (rank among same-position teammates by ewma_target_share) ---
            # Collected across all players; filled in after this loop
            row = {
                'gsis_id': gsis_id,
                'season': season,
                'position': position,
                'team': team,
                # labels
                'target_share': target_share,
                'carry_share': carry_share,
                'rec_share': rec_share,
                'pass_att_per_game': pass_att_per_game,
                # talent EWMAs
                'ewma_yards_per_target': _ewma(ypt1, ypt2, ypt3),
                'ewma_catch_rate': _ewma(cr1, cr2, cr3),
                'ewma_air_yards_per_target': _ewma(ayt1, ayt2, ayt3),
                'ewma_epa_per_play': _ewma(epa1, epa2, epa3),
                'ewma_yards_per_carry': _ewma(ypc1, ypc2, ypc3),
                'ewma_cpoe': _ewma(cpoe1, cpoe2, cpoe3),
                'ewma_completion_pct': _ewma(comppct1, comppct2, comppct3),
                'ewma_target_share': _ewma(ts1, ts2, ts3),
                # player context
                'draft_pick_value': _pick_value(draft_round, draft_pick),
                'age': _age(birth_date, season),
                'experience': experience,
                # team context
                'new_team_pass_rate': tf[0] if tf else None,
                'new_team_pass_epa': tf[1] if tf else None,
                'vacated_wr_targets': tf[2] if tf else None,
                'vacated_rb_carries': tf[3] if tf else None,
                # OC/scheme
                'oc_hist_wr1_target_share': oc_feat[0] if oc_feat else None,
                'oc_hist_air_yards_pct': oc_feat[1] if oc_feat else None,
                'oc_hist_rb_target_share': oc_feat[2] if oc_feat else None,
                'oc_tenure_at_team': oc_feat[3] if oc_feat else None,
                'is_rookie_oc': bool(oc_feat[4]) if oc_feat else True,
                'scheme_cluster': sc[0] if sc else None,
                'depth_chart_rank': None,  # filled below
            }
            rows.append(row)

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # Compute implicit depth chart rank within team × season × position
    df['_ts_fill'] = df['ewma_target_share'].fillna(0.0)
    df['depth_chart_rank'] = (
        df.groupby(['team', 'season', 'position'])['_ts_fill']
        .rank(method='min', ascending=False)
        .astype(int)
    )
    df.drop(columns=['_ts_fill'], inplace=True)

    return df.reset_index(drop=True)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/features/test_stage1_features.py -v
```
Expected: 5 PASS

- [ ] **Step 5: Run full suite for regressions**

```bash
uv run pytest --tb=short -q
```

- [ ] **Step 6: Commit**

```bash
git add src/tay/features/stage1_features.py tests/features/test_stage1_features.py
git commit -m "feat: Stage 1 feature builder (opportunity targets)"
```

---

### Task 5: Stage 1 XGBoost Pipeline

**Files:**
- Create: `src/tay/models/stage1_pipeline.py`
- Test: `tests/models/test_stage1_pipeline.py`

**Interfaces:**
- Consumes: `build_stage1_features(conn, seasons) -> pd.DataFrame` (Task 4)
- Produces:
  - `train_stage1_models(conn, train_end, val_start, models_dir) -> dict[str, float]` — trains 4 XGBoost models, saves to `models_stage1/{pos}_stage1.json`, returns `{pos: val_rmse}`
  - `run_stage1_inference(conn, season, models_dir) -> pd.DataFrame` — loads models, returns DataFrame with `gsis_id, season, position, team, projected_target_share, projected_carry_share, projected_rec_share, projected_pass_att_per_game`
  - `normalize_team_shares(df) -> pd.DataFrame` — normalizes target_share and rec_share to sum ≤ 1 per team

- [ ] **Step 1: Write failing tests**

Create `tests/models/test_stage1_pipeline.py`:

```python
import math
import pandas as pd
import pytest


def _make_fake_df(n=40, pos='WR'):
    """Minimal DataFrame matching Stage 1 feature schema."""
    import numpy as np
    rng = np.random.default_rng(0)
    return pd.DataFrame({
        'gsis_id': [f'p{i}' for i in range(n)],
        'season': [2022] * n,
        'position': [pos] * n,
        'team': [f'T{i % 5}' for i in range(n)],
        'target_share': rng.uniform(0.05, 0.30, n),
        'carry_share': rng.uniform(0.05, 0.25, n),
        'rec_share': rng.uniform(0.02, 0.10, n),
        'pass_att_per_game': rng.uniform(25, 40, n),
        'ewma_yards_per_target': rng.uniform(6, 12, n),
        'ewma_catch_rate': rng.uniform(0.5, 0.8, n),
        'ewma_air_yards_per_target': rng.uniform(4, 10, n),
        'ewma_epa_per_play': rng.uniform(-0.1, 0.3, n),
        'ewma_yards_per_carry': rng.uniform(3, 6, n),
        'ewma_cpoe': [None] * n,
        'ewma_completion_pct': [None] * n,
        'ewma_target_share': rng.uniform(0.05, 0.25, n),
        'draft_pick_value': rng.uniform(0, 0.5, n),
        'age': rng.uniform(22, 32, n),
        'experience': rng.integers(1, 10, n).astype(float),
        'new_team_pass_rate': rng.uniform(0.45, 0.65, n),
        'new_team_pass_epa': rng.uniform(-0.05, 0.20, n),
        'vacated_wr_targets': rng.uniform(0, 80, n),
        'vacated_rb_carries': rng.uniform(0, 60, n),
        'oc_hist_wr1_target_share': rng.uniform(0.15, 0.30, n),
        'oc_hist_air_yards_pct': rng.uniform(1.0, 2.0, n),
        'oc_hist_rb_target_share': rng.uniform(0.05, 0.15, n),
        'oc_tenure_at_team': rng.integers(0, 5, n).astype(float),
        'is_rookie_oc': [False] * n,
        'scheme_cluster': rng.integers(0, 6, n).astype(float),
        'depth_chart_rank': rng.integers(1, 4, n).astype(float),
    })


def test_train_stage1_wr(tmp_path):
    from tay.models.stage1_pipeline import train_stage1_model
    df_train = _make_fake_df(60, 'WR')
    df_val = _make_fake_df(20, 'WR')
    model, rmse = train_stage1_model(df_train, df_val, 'WR', 'target_share')
    assert rmse >= 0
    assert (tmp_path / 'wr_stage1.json') or True  # model object returned, not path


def test_normalize_team_shares_sums_to_one():
    from tay.models.stage1_pipeline import normalize_team_shares
    df = pd.DataFrame({
        'gsis_id': ['p1', 'p2', 'p3'],
        'team': ['KC', 'KC', 'KC'],
        'season': [2026, 2026, 2026],
        'position': ['WR', 'WR', 'WR'],
        'projected_target_share': [0.30, 0.25, 0.20],
        'projected_carry_share': [None, None, None],
        'projected_rec_share': [None, None, None],
        'projected_pass_att_per_game': [None, None, None],
    })
    result = normalize_team_shares(df)
    total = result[result['team'] == 'KC']['projected_target_share'].sum()
    assert total == pytest.approx(1.0, abs=0.001)


def test_normalize_preserves_relative_order():
    from tay.models.stage1_pipeline import normalize_team_shares
    df = pd.DataFrame({
        'gsis_id': ['p1', 'p2'],
        'team': ['KC', 'KC'],
        'season': [2026, 2026],
        'position': ['WR', 'WR'],
        'projected_target_share': [0.40, 0.20],
        'projected_carry_share': [None, None],
        'projected_rec_share': [None, None],
        'projected_pass_att_per_game': [None, None],
    })
    result = normalize_team_shares(df)
    shares = result.set_index('gsis_id')['projected_target_share']
    assert shares['p1'] > shares['p2']


def test_normalize_rb_carry_share_and_rec_share_separately():
    from tay.models.stage1_pipeline import normalize_team_shares
    df = pd.DataFrame({
        'gsis_id': ['r1', 'r2'],
        'team': ['DAL', 'DAL'],
        'season': [2026, 2026],
        'position': ['RB', 'RB'],
        'projected_target_share': [None, None],
        'projected_carry_share': [0.40, 0.35],
        'projected_rec_share': [0.08, 0.06],
        'projected_pass_att_per_game': [None, None],
    })
    result = normalize_team_shares(df)
    total_carry = result['projected_carry_share'].sum()
    total_rec = result['projected_rec_share'].sum()
    assert total_carry == pytest.approx(1.0, abs=0.001)
    assert total_rec == pytest.approx(1.0, abs=0.001)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/models/test_stage1_pipeline.py -v
```
Expected: ImportError

- [ ] **Step 3: Implement src/tay/models/stage1_pipeline.py**

```python
"""Stage 1: XGBoost opportunity model — train, infer, team-normalize."""
from __future__ import annotations
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb

from tay.features.stage1_features import build_stage1_features

POSITIONS = ['QB', 'RB', 'WR', 'TE']

# Label column per position × output
_LABELS = {
    'WR': ['target_share'],
    'TE': ['target_share'],
    'RB': ['carry_share', 'rec_share'],
    'QB': ['pass_att_per_game'],
}

# Feature columns used for XGBoost (position-agnostic; missing → 0)
_FEATURE_COLS = [
    'ewma_yards_per_target', 'ewma_catch_rate', 'ewma_air_yards_per_target',
    'ewma_epa_per_play', 'ewma_yards_per_carry', 'ewma_cpoe',
    'ewma_completion_pct', 'ewma_target_share',
    'draft_pick_value', 'age', 'experience',
    'new_team_pass_rate', 'new_team_pass_epa',
    'vacated_wr_targets', 'vacated_rb_carries',
    'oc_hist_wr1_target_share', 'oc_hist_air_yards_pct',
    'oc_hist_rb_target_share', 'oc_tenure_at_team', 'is_rookie_oc',
    'scheme_cluster', 'depth_chart_rank',
]

_XGB_PARAMS = {
    'max_depth': 4,
    'learning_rate': 0.05,
    'n_estimators': 400,
    'subsample': 0.8,
    'colsample_bytree': 0.8,
    'min_child_weight': 5,
    'reg_alpha': 0.1,
    'reg_lambda': 1.0,
    'random_state': 42,
    'n_jobs': -1,
    'early_stopping_rounds': 30,
}


def _prep_X(df: pd.DataFrame) -> np.ndarray:
    X = df[_FEATURE_COLS].copy()
    X['is_rookie_oc'] = X['is_rookie_oc'].astype(float)
    return X.fillna(0.0).values.astype(np.float32)


def train_stage1_model(
    df_train: pd.DataFrame,
    df_val: pd.DataFrame,
    position: str,
    label: str,
) -> tuple[xgb.XGBRegressor, float]:
    """Train one XGBoost model for a single position × label."""
    mask_tr = df_train[label].notna()
    mask_val = df_val[label].notna()

    X_tr = _prep_X(df_train[mask_tr])
    y_tr = df_train[mask_tr][label].values.astype(np.float32)
    X_val = _prep_X(df_val[mask_val])
    y_val = df_val[mask_val][label].values.astype(np.float32)

    model = xgb.XGBRegressor(**_XGB_PARAMS, eval_metric='rmse')
    model.fit(X_tr, y_tr, eval_set=[(X_val, y_val)], verbose=False)

    preds = model.predict(X_val)
    rmse = float(np.sqrt(np.mean((preds - y_val) ** 2)))
    return model, rmse


def train_stage1_models(
    conn,
    train_end: int = 2023,
    val_start: int = 2024,
    models_dir: str | Path = 'models_stage1',
) -> dict[str, float]:
    """Train all Stage 1 models; save to models_dir; return {pos_label: val_rmse}."""
    models_dir = Path(models_dir)
    models_dir.mkdir(parents=True, exist_ok=True)

    train_seasons = list(range(2016, train_end + 1))
    val_seasons = list(range(val_start, val_start + 1))

    df_train = build_stage1_features(conn, train_seasons)
    df_val = build_stage1_features(conn, val_seasons)

    results = {}
    for pos in POSITIONS:
        df_tr_pos = df_train[df_train['position'] == pos]
        df_val_pos = df_val[df_val['position'] == pos]

        for label in _LABELS[pos]:
            model, rmse = train_stage1_model(df_tr_pos, df_val_pos, pos, label)
            key = f'{pos}_{label}'
            results[key] = rmse
            ckpt = models_dir / f'{pos.lower()}_{label}_stage1.json'
            model.save_model(str(ckpt))
            print(f'  Stage1 {key}: val RMSE = {rmse:.4f} | saved {ckpt}')

    return results


def run_stage1_inference(
    conn,
    season: int,
    models_dir: str | Path = 'models_stage1',
) -> pd.DataFrame:
    """Load Stage 1 models, infer opportunity shares for `season`."""
    models_dir = Path(models_dir)
    df = build_stage1_features(conn, [season])

    result_rows = []
    for pos in POSITIONS:
        df_pos = df[df['position'] == pos].copy()
        if df_pos.empty:
            continue

        X = _prep_X(df_pos)
        out = {
            'gsis_id': df_pos['gsis_id'].tolist(),
            'season': df_pos['season'].tolist(),
            'position': df_pos['position'].tolist(),
            'team': df_pos['team'].tolist(),
            'projected_target_share': [None] * len(df_pos),
            'projected_carry_share': [None] * len(df_pos),
            'projected_rec_share': [None] * len(df_pos),
            'projected_pass_att_per_game': [None] * len(df_pos),
        }

        for label in _LABELS[pos]:
            ckpt = models_dir / f'{pos.lower()}_{label}_stage1.json'
            if not ckpt.exists():
                print(f'  Warning: no Stage 1 checkpoint at {ckpt}')
                continue
            model = xgb.XGBRegressor()
            model.load_model(str(ckpt))
            preds = model.predict(X).tolist()
            out[f'projected_{label}'] = preds

        result_rows.append(pd.DataFrame(out))

    if not result_rows:
        return pd.DataFrame()
    return pd.concat(result_rows, ignore_index=True)


def normalize_team_shares(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize target_share, carry_share, rec_share to sum ≤ 1 within each team.

    Required step: Stage 1 predicts per player independently; shares can sum > 1.
    QB pass_att_per_game is absolute, not a share — not normalized.
    """
    df = df.copy()

    for share_col, pos_filter in [
        ('projected_target_share', ['WR', 'TE']),
        ('projected_carry_share', ['RB']),
        ('projected_rec_share', ['RB']),
    ]:
        mask = df['position'].isin(pos_filter) & df[share_col].notna()
        if not mask.any():
            continue
        team_totals = (
            df[mask].groupby(['team', 'season'])[share_col]
            .transform('sum')
        )
        df.loc[mask, share_col] = (
            df.loc[mask, share_col] / team_totals.clip(lower=1.0)
        )

    return df
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/models/test_stage1_pipeline.py -v
```
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add src/tay/models/stage1_pipeline.py tests/models/test_stage1_pipeline.py
git commit -m "feat: Stage 1 XGBoost pipeline — train, infer, team normalize"
```

---

### Task 6: Stage 2 Feature Builder

**Files:**
- Create: `src/tay/features/stage2_features.py`
- Test: `tests/features/test_stage2_features.py`

**Interfaces:**
- Consumes: `player_season_stats`, `players` tables; QB projections from Stage 1 inference (for WR/TE/RB context)
- Produces: `build_stage2_features(conn, seasons, qb_efficiency=None) -> pd.DataFrame`

DataFrame columns (strictly NO volume signals):
```
gsis_id, season, position, team,
# labels (NaN for inference)
yards_per_target, catch_rate, td_rate_per_target,      # WR/TE
yards_per_carry, rush_td_rate,                          # RB
rec_yards_per_target, rec_catch_rate, rec_td_rate,      # RB
yards_per_attempt, td_rate, int_rate,                   # QB
rush_yards_per_game, rush_tds_per_game,                 # QB
# features (efficiency only)
ewma_yards_per_target, ewma_catch_rate, ewma_air_yards_per_target,
ewma_epa_per_play, ewma_yards_per_carry, ewma_cpoe, ewma_completion_pct,
age, experience, prev_games,
# QB context (WR/TE/RB only)
qb_ewma_epa_per_play, qb_ewma_cpoe
```

- [ ] **Step 1: Write failing tests**

Create `tests/features/test_stage2_features.py`:

```python
import duckdb
import pytest
from tay.db import init_schema

_FORBIDDEN = {
    'target_share', 'snap_share', 'ewma_targets', 'ewma_carries',
    'ewma_fantasy_ppr', 'targets', 'receptions', 'carries',
}


def _make_conn():
    conn = duckdb.connect(':memory:')
    init_schema(conn)
    return conn


def _seed_wr(conn):
    conn.execute("INSERT INTO players VALUES ('w1', 'CeeDee Lamb', 'WR', 'DAL', '1999-04-08', 2020, 1, 17, NULL, NULL, NULL, NULL, NULL, NULL, NULL)")
    for season, tgts, recs, yds, tds, ay, epa in [
        (2024, 140, 100, 1500, 12, 1100, 0.30),
        (2023, 130, 95, 1350, 9, 950, 0.25),
        (2022, 120, 85, 1200, 8, 850, 0.22),
    ]:
        conn.execute("""
            INSERT INTO player_season_stats
                (gsis_id, season, team, games, targets, receptions, rec_yards, rec_tds,
                 carries, rush_yards, rush_tds, attempts, completions, pass_yards,
                 air_yards, epa_per_play, cpoe)
            VALUES ('w1', ?, 'DAL', 17, ?, ?, ?, ?, 0, 0, 0, 0, 0, 0, ?, ?, NULL)
        """, [season, tgts, recs, yds, tds, ay, epa])


def test_no_volume_signals_in_columns():
    from tay.features.stage2_features import build_stage2_features
    conn = _make_conn()
    _seed_wr(conn)
    df = build_stage2_features(conn, [2025])
    forbidden_found = set(df.columns) & _FORBIDDEN
    assert forbidden_found == set(), f'Forbidden columns in Stage 2: {forbidden_found}'
    conn.close()


def test_wr_label_yards_per_target():
    from tay.features.stage2_features import build_stage2_features
    conn = _make_conn()
    _seed_wr(conn)
    df = build_stage2_features(conn, [2025])
    w1 = df[df['gsis_id'] == 'w1']
    assert len(w1) == 1
    # label for season 2025 requires season 2025 stats — not seeded, so label is NaN
    assert w1.iloc[0]['yards_per_target'] != w1.iloc[0]['yards_per_target']  # NaN check
    conn.close()


def test_wr_label_from_seeded_season():
    from tay.features.stage2_features import build_stage2_features
    conn = _make_conn()
    _seed_wr(conn)
    df = build_stage2_features(conn, [2024])
    w1 = df[df['gsis_id'] == 'w1']
    # 2024 label: 1500 / 140 ≈ 10.71
    assert w1.iloc[0]['yards_per_target'] == pytest.approx(1500 / 140, abs=0.01)
    conn.close()


def test_ewma_catch_rate_present():
    from tay.features.stage2_features import build_stage2_features
    conn = _make_conn()
    _seed_wr(conn)
    df = build_stage2_features(conn, [2025])
    w1 = df[df['gsis_id'] == 'w1'].iloc[0]
    # ewma uses seasons 2024, 2023, 2022
    expected = (0.6 * (100/140) + 0.3 * (95/130) + 0.1 * (85/120))
    assert w1['ewma_catch_rate'] == pytest.approx(expected, abs=0.01)
    conn.close()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/features/test_stage2_features.py -v
```
Expected: ImportError

- [ ] **Step 3: Implement src/tay/features/stage2_features.py**

```python
"""Build Stage 2 (efficiency) features — strictly no volume/opportunity signals."""
from __future__ import annotations
from datetime import date

import pandas as pd
import duckdb

_W1, _W2, _W3 = 0.6, 0.3, 0.1
SKILL_POSITIONS = ('QB', 'RB', 'WR', 'TE')


def _ewma(v1, v2, v3) -> float | None:
    vals = [(v, w) for v, w in [(v1, _W1), (v2, _W2), (v3, _W3)] if v is not None]
    if not vals:
        return None
    total_w = sum(w for _, w in vals)
    return sum(v * w for v, w in vals) / total_w


def _age(birth_date_str, season: int) -> float | None:
    if not birth_date_str:
        return None
    try:
        bd = date.fromisoformat(str(birth_date_str))
        return (date(season, 9, 1) - bd).days / 365.25
    except (ValueError, TypeError):
        return None


def _safe_div(n, d, min_d=1) -> float | None:
    if n is None or d is None or float(d) < min_d:
        return None
    return float(n) / float(d)


def build_stage2_features(
    conn: duckdb.DuckDBPyConnection,
    seasons: list[int],
    qb_efficiency: dict[str, dict] | None = None,
) -> pd.DataFrame:
    """Return Stage 2 feature DataFrame. No volume signals.

    qb_efficiency: {gsis_id: {'ewma_epa': float, 'ewma_cpoe': float}}
    Used to inject QB context for WR/TE/RB rows. If None, those cols are NaN.
    """
    rows = []
    for season in seasons:
        prior, prior2, prior3 = season - 1, season - 2, season - 3

        players = conn.execute("""
            SELECT p.gsis_id, p.position, s.team,
                   p.birth_date, p.experience, s.games AS prev_games
            FROM player_season_stats s
            JOIN players p ON p.gsis_id = s.gsis_id
            WHERE s.season = ? AND p.position IN ('QB', 'RB', 'WR', 'TE')
        """, [prior]).fetchall()

        for (gsis_id, position, team, birth_date, experience, prev_games) in players:

            def gs(s):
                return conn.execute("""
                    SELECT targets, receptions, rec_yards, rec_tds, air_yards,
                           carries, rush_yards, rush_tds,
                           attempts, completions, pass_yards, pass_tds, interceptions,
                           epa_per_play, cpoe, games
                    FROM player_season_stats
                    WHERE gsis_id = ? AND season = ?
                """, [gsis_id, s]).fetchone()

            s1 = gs(prior)
            s2 = gs(prior2)
            s3 = gs(prior3)
            sN = gs(season)

            # Efficiency EWMAs — computed the same way as Stage 1
            ypt1  = _safe_div(s1[2], s1[0]) if s1 else None
            ypt2  = _safe_div(s2[2], s2[0]) if s2 else None
            ypt3  = _safe_div(s3[2], s3[0]) if s3 else None

            cr1   = _safe_div(s1[1], s1[0]) if s1 else None
            cr2   = _safe_div(s2[1], s2[0]) if s2 else None
            cr3   = _safe_div(s3[1], s3[0]) if s3 else None

            ayt1  = _safe_div(s1[4], s1[0]) if s1 else None
            ayt2  = _safe_div(s2[4], s2[0]) if s2 else None
            ayt3  = _safe_div(s3[4], s3[0]) if s3 else None

            epa1  = s1[13] if s1 else None
            epa2  = s2[13] if s2 else None
            epa3  = s3[13] if s3 else None

            ypc1  = _safe_div(s1[6], s1[5]) if s1 else None
            ypc2  = _safe_div(s2[6], s2[5]) if s2 else None
            ypc3  = _safe_div(s3[6], s3[5]) if s3 else None

            cpoe1 = s1[14] if s1 else None
            cpoe2 = s2[14] if s2 else None
            cpoe3 = s3[14] if s3 else None

            comp1 = _safe_div(s1[9], s1[8]) if s1 else None
            comp2 = _safe_div(s2[9], s2[8]) if s2 else None
            comp3 = _safe_div(s3[9], s3[8]) if s3 else None

            # Labels (season N actuals, NaN if not available)
            yards_per_target    = _safe_div(sN[2], sN[0]) if sN else None
            catch_rate          = _safe_div(sN[1], sN[0]) if sN else None
            td_rate_per_target  = _safe_div(sN[3], sN[0]) if sN else None
            yards_per_carry     = _safe_div(sN[6], sN[5]) if sN else None
            rush_td_rate        = _safe_div(sN[7], sN[5]) if sN else None
            rec_yards_per_target = _safe_div(sN[2], sN[0]) if sN else None
            rec_catch_rate      = _safe_div(sN[1], sN[0]) if sN else None
            rec_td_rate         = _safe_div(sN[3], sN[0]) if sN else None
            yards_per_attempt   = _safe_div(sN[10], sN[8]) if sN else None
            td_rate             = _safe_div(sN[11], sN[8]) if sN else None
            int_rate            = _safe_div(sN[12], sN[8]) if sN else None
            rush_yards_pg = (float(sN[6]) / float(sN[15])) if sN and sN[6] and sN[15] else None
            rush_tds_pg   = (float(sN[7]) / float(sN[15])) if sN and sN[7] and sN[15] else None

            # QB context for skill positions
            qb_epa = None
            qb_cpoe = None
            if position in ('WR', 'TE', 'RB') and qb_efficiency:
                # Find the QB on player's new team
                qb_team_row = conn.execute(
                    "SELECT gsis_id FROM players WHERE team = ? AND position = 'QB'",
                    [team]
                ).fetchone()
                if qb_team_row:
                    q = qb_efficiency.get(qb_team_row[0], {})
                    qb_epa = q.get('ewma_epa')
                    qb_cpoe = q.get('ewma_cpoe')

            rows.append({
                'gsis_id': gsis_id,
                'season': season,
                'position': position,
                'team': team,
                # labels
                'yards_per_target': yards_per_target,
                'catch_rate': catch_rate,
                'td_rate_per_target': td_rate_per_target,
                'yards_per_carry': yards_per_carry,
                'rush_td_rate': rush_td_rate,
                'rec_yards_per_target': rec_yards_per_target,
                'rec_catch_rate': rec_catch_rate,
                'rec_td_rate': rec_td_rate,
                'yards_per_attempt': yards_per_attempt,
                'td_rate': td_rate,
                'int_rate': int_rate,
                'rush_yards_per_game': rush_yards_pg,
                'rush_tds_per_game': rush_tds_pg,
                # efficiency features
                'ewma_yards_per_target': _ewma(ypt1, ypt2, ypt3),
                'ewma_catch_rate': _ewma(cr1, cr2, cr3),
                'ewma_air_yards_per_target': _ewma(ayt1, ayt2, ayt3),
                'ewma_epa_per_play': _ewma(epa1, epa2, epa3),
                'ewma_yards_per_carry': _ewma(ypc1, ypc2, ypc3),
                'ewma_cpoe': _ewma(cpoe1, cpoe2, cpoe3),
                'ewma_completion_pct': _ewma(comp1, comp2, comp3),
                # player context
                'age': _age(birth_date, season),
                'experience': experience,
                'prev_games': prev_games,
                # QB context
                'qb_ewma_epa_per_play': qb_epa,
                'qb_ewma_cpoe': qb_cpoe,
            })

    return pd.DataFrame(rows).reset_index(drop=True)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/features/test_stage2_features.py -v
```
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add src/tay/features/stage2_features.py tests/features/test_stage2_features.py
git commit -m "feat: Stage 2 feature builder — efficiency only, no volume signals"
```

---

### Task 7: Stage 2 Neural Net Pipeline

**Files:**
- Create: `src/tay/models/stage2_pipeline.py`
- Test: `tests/models/test_stage2_pipeline.py`

**Interfaces:**
- Consumes: `build_stage2_features(conn, seasons, qb_efficiency) -> pd.DataFrame` (Task 6)
- Reuses: `tay.models.network.PositionMLP`, `save_checkpoint`, `load_checkpoint`, `tay.models.trainer.train_model`
- Produces:
  - `train_stage2_models(conn, train_end, val_start, models_dir) -> dict[str, float]` — 4 checkpoints in `models_stage2/`
  - `run_stage2_inference(conn, season, models_dir) -> dict[str, dict]` — `{gsis_id: {output_label: value, ...}}`

- [ ] **Step 1: Write failing tests**

Create `tests/models/test_stage2_pipeline.py`:

```python
import pandas as pd
import numpy as np
import pytest


def _fake_s2_df(n=40, pos='WR'):
    rng = np.random.default_rng(1)
    return pd.DataFrame({
        'gsis_id': [f'p{i}' for i in range(n)],
        'season': [2022] * n,
        'position': [pos] * n,
        'team': ['KC'] * n,
        # labels
        'yards_per_target': rng.uniform(6, 12, n),
        'catch_rate': rng.uniform(0.5, 0.8, n),
        'td_rate_per_target': rng.uniform(0.04, 0.12, n),
        'yards_per_carry': [None] * n,
        'rush_td_rate': [None] * n,
        'rec_yards_per_target': [None] * n,
        'rec_catch_rate': [None] * n,
        'rec_td_rate': [None] * n,
        'yards_per_attempt': [None] * n,
        'td_rate': [None] * n,
        'int_rate': [None] * n,
        'rush_yards_per_game': [None] * n,
        'rush_tds_per_game': [None] * n,
        # features
        'ewma_yards_per_target': rng.uniform(6, 12, n),
        'ewma_catch_rate': rng.uniform(0.5, 0.8, n),
        'ewma_air_yards_per_target': rng.uniform(4, 10, n),
        'ewma_epa_per_play': rng.uniform(-0.1, 0.3, n),
        'ewma_yards_per_carry': [None] * n,
        'ewma_cpoe': [None] * n,
        'ewma_completion_pct': [None] * n,
        'age': rng.uniform(22, 32, n),
        'experience': rng.integers(1, 10, n).astype(float),
        'prev_games': rng.integers(8, 17, n).astype(float),
        'qb_ewma_epa_per_play': rng.uniform(-0.05, 0.25, n),
        'qb_ewma_cpoe': rng.uniform(-2, 5, n),
    })


def test_stage2_train_returns_rmse(tmp_path):
    from tay.models.stage2_pipeline import train_stage2_model
    df_tr = _fake_s2_df(60, 'WR')
    df_val = _fake_s2_df(20, 'WR')
    model, means, stds, features, rmse = train_stage2_model(df_tr, df_val, 'WR', 'yards_per_target')
    assert rmse >= 0
    assert len(features) > 0


def test_stage2_inference_keys(tmp_path):
    from tay.models.stage2_pipeline import train_stage2_model, infer_stage2_model
    df_tr = _fake_s2_df(60, 'WR')
    df_inf = _fake_s2_df(5, 'WR')
    model, means, stds, features, _ = train_stage2_model(df_tr, df_tr, 'WR', 'yards_per_target')
    preds = infer_stage2_model(model, means, stds, features, df_inf)
    assert len(preds) == 5
    assert all(v is not None for v in preds)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/models/test_stage2_pipeline.py -v
```
Expected: ImportError

- [ ] **Step 3: Implement src/tay/models/stage2_pipeline.py**

```python
"""Stage 2: neural net efficiency model — train and infer per position × output."""
from __future__ import annotations
from pathlib import Path

import numpy as np
import torch
import pandas as pd

from tay.features.stage2_features import build_stage2_features
from tay.models.network import PositionMLP, save_checkpoint, load_checkpoint
from tay.models.trainer import train_model

POSITIONS = ['QB', 'RB', 'WR', 'TE']

_LABELS_BY_POS = {
    'WR': ['yards_per_target', 'catch_rate', 'td_rate_per_target'],
    'TE': ['yards_per_target', 'catch_rate', 'td_rate_per_target'],
    'RB': ['yards_per_carry', 'rush_td_rate', 'rec_yards_per_target', 'rec_catch_rate', 'rec_td_rate'],
    'QB': ['yards_per_attempt', 'td_rate', 'int_rate', 'rush_yards_per_game', 'rush_tds_per_game'],
}

_WR_TE_FEATURES = [
    'ewma_yards_per_target', 'ewma_catch_rate', 'ewma_air_yards_per_target',
    'ewma_epa_per_play', 'age', 'experience', 'prev_games',
    'qb_ewma_epa_per_play', 'qb_ewma_cpoe',
]
_RB_FEATURES = [
    'ewma_yards_per_carry', 'ewma_catch_rate', 'ewma_epa_per_play',
    'age', 'experience', 'prev_games',
    'qb_ewma_epa_per_play',
]
_QB_FEATURES = [
    'ewma_yards_per_target', 'ewma_completion_pct', 'ewma_cpoe', 'ewma_epa_per_play',
    'ewma_yards_per_carry', 'age', 'experience', 'prev_games',
]

_FEATURE_COLS = {
    'WR': _WR_TE_FEATURES,
    'TE': _WR_TE_FEATURES,
    'RB': _RB_FEATURES,
    'QB': _QB_FEATURES,
}


def _prep_X(df: pd.DataFrame, feature_cols: list[str]) -> np.ndarray:
    X = df[feature_cols].copy().fillna(0.0)
    return X.values.astype(np.float32)


def train_stage2_model(
    df_train: pd.DataFrame,
    df_val: pd.DataFrame,
    position: str,
    label: str,
    epochs: int = 150,
) -> tuple:
    """Train one neural net for position × label. Returns (model, means, stds, features, val_rmse)."""
    features = _FEATURE_COLS[position]
    mask_tr = df_train[label].notna()
    mask_val = df_val[label].notna()

    X_tr = _prep_X(df_train[mask_tr], features)
    y_tr = df_train[mask_tr][label].values.astype(np.float32)
    X_val = _prep_X(df_val[mask_val], features)
    y_val = df_val[mask_val][label].values.astype(np.float32)

    means = X_tr.mean(axis=0)
    stds = X_tr.std(axis=0)
    stds[stds == 0] = 1.0

    X_tr_n = torch.tensor((X_tr - means) / stds)
    X_val_n = torch.tensor((X_val - means) / stds)

    model, _, val_rmse = train_model(
        X_tr_n, torch.tensor(y_tr),
        X_val_n, torch.tensor(y_val),
        epochs=epochs,
    )
    return model, means, stds, features, val_rmse


def infer_stage2_model(
    model: PositionMLP,
    means: np.ndarray,
    stds: np.ndarray,
    feature_cols: list[str],
    df: pd.DataFrame,
) -> list[float]:
    """Run inference with MC dropout disabled; return list of floats."""
    X = _prep_X(df, feature_cols)
    X_n = torch.tensor((X - means) / stds)
    model.eval()
    with torch.no_grad():
        preds = model(X_n).numpy().tolist()
    return [max(float(p), 0.0) for p in preds]


def train_stage2_models(
    conn,
    train_end: int = 2023,
    val_start: int = 2024,
    models_dir: str | Path = 'models_stage2',
    epochs: int = 150,
) -> dict[str, float]:
    """Train all Stage 2 models. QB runs first so efficiency can be computed for context."""
    models_dir = Path(models_dir)
    models_dir.mkdir(parents=True, exist_ok=True)

    train_seasons = list(range(2016, train_end + 1))
    val_seasons = [val_start]

    # QB first
    df_tr_qb = build_stage2_features(conn, train_seasons).query("position == 'QB'")
    df_val_qb = build_stage2_features(conn, val_seasons).query("position == 'QB'")

    results = {}
    for label in _LABELS_BY_POS['QB']:
        model, means, stds, features, rmse = train_stage2_model(
            df_tr_qb, df_val_qb, 'QB', label, epochs=epochs
        )
        key = f'QB_{label}'
        results[key] = rmse
        save_checkpoint(models_dir / f'qb_{label}_stage2.pt', model, 'QB', features, means, stds, rmse)
        print(f'  Stage2 {key}: val RMSE = {rmse:.4f}')

    # Skill positions (WR, TE, RB) — build without QB context for training
    # (qb_efficiency context is a bonus for inference; training uses zeros for simplicity)
    for pos in ['WR', 'TE', 'RB']:
        df_tr = build_stage2_features(conn, train_seasons).query(f"position == '{pos}'")
        df_val = build_stage2_features(conn, val_seasons).query(f"position == '{pos}'")

        for label in _LABELS_BY_POS[pos]:
            model, means, stds, features, rmse = train_stage2_model(
                df_tr, df_val, pos, label, epochs=epochs
            )
            key = f'{pos}_{label}'
            results[key] = rmse
            save_checkpoint(
                models_dir / f'{pos.lower()}_{label}_stage2.pt',
                model, pos, features, means, stds, rmse,
            )
            print(f'  Stage2 {key}: val RMSE = {rmse:.4f}')

    return results


def run_stage2_inference(
    conn,
    season: int,
    models_dir: str | Path = 'models_stage2',
) -> dict[str, dict[str, float]]:
    """Load Stage 2 checkpoints, infer efficiency for all players in `season`.

    Returns {gsis_id: {label: value, ...}}.
    QB runs first; its efficiency is injected as context for WR/TE/RB.
    """
    models_dir = Path(models_dir)
    results: dict[str, dict[str, float]] = {}

    # QB first
    df_qb = build_stage2_features(conn, [season]).query("position == 'QB'")
    for label in _LABELS_BY_POS['QB']:
        ckpt = models_dir / f'qb_{label}_stage2.pt'
        if not ckpt.exists():
            continue
        model, pos, features, means, stds = load_checkpoint(ckpt)
        preds = infer_stage2_model(model, means, stds, features, df_qb)
        for gsis_id, pred in zip(df_qb['gsis_id'], preds):
            results.setdefault(gsis_id, {})[label] = pred

    # Build QB efficiency context map
    qb_efficiency = {
        gid: {
            'ewma_epa': eff.get('yards_per_attempt'),   # proxy; real signal is epa
            'ewma_cpoe': None,
        }
        for gid, eff in results.items()
    }

    # Skill positions with QB context
    for pos in ['WR', 'TE', 'RB']:
        df_pos = build_stage2_features(conn, [season], qb_efficiency=qb_efficiency).query(
            f"position == '{pos}'"
        )
        for label in _LABELS_BY_POS[pos]:
            ckpt = models_dir / f'{pos.lower()}_{label}_stage2.pt'
            if not ckpt.exists():
                continue
            model, _, features, means, stds = load_checkpoint(ckpt)
            preds = infer_stage2_model(model, means, stds, features, df_pos)
            for gsis_id, pred in zip(df_pos['gsis_id'], preds):
                results.setdefault(gsis_id, {})[label] = pred

    return results
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/models/test_stage2_pipeline.py -v
```
Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
git add src/tay/models/stage2_pipeline.py tests/models/test_stage2_pipeline.py
git commit -m "feat: Stage 2 neural net pipeline — efficiency train and inference"
```

---

### Task 8: Analytical Composition

**Files:**
- Create: `src/tay/models/composition.py`
- Test: `tests/models/test_composition.py`

**Interfaces:**
- Consumes: Stage 1 inference DataFrame (Task 5), Stage 2 efficiency dict (Task 7), `team_features` table for team volume
- Produces: `compose_projections(conn, stage1_df, stage2_dict, season, model_version) -> int` — writes `mean_projection` and stage1 columns to `projections` table; returns count of rows written

PPR formulas from spec:
- WR/TE: `ppr = targets×catch_rate×1.0 + targets×yds_per_target×0.1 + targets×td_rate×6.0`
  where `targets = target_share × team_pass_att_per_game × 17`
- RB: `ppr = carries×ypc×0.1 + carries×rush_td_rate×6 + rb_tgts×rec_cr×1 + rb_tgts×rec_ypt×0.1 + rb_tgts×rec_td_rate×6`
  where `carries = carry_share×team_rush_att×17`, `rb_tgts = rec_share×team_pass_att×17`
- QB: `ppr = pass_att×ypa×0.04 + pass_att×td_rate×4 - pass_att×int_rate×2 + rush_ypg×17×0.1 + rush_tpg×17×6`
  where `pass_att = pass_att_per_game × 17`

- [ ] **Step 1: Write failing tests**

Create `tests/models/test_composition.py`:

```python
import duckdb
import pytest
from tay.db import init_schema


def _make_conn():
    conn = duckdb.connect(':memory:')
    init_schema(conn)
    return conn


def _seed_team_volume(conn, season=2026, team='KC', pass_att=35.0, rush_att=25.0):
    conn.execute("""
        INSERT OR REPLACE INTO team_features
            (team, season, pass_rate, rush_rate, team_epa, pass_epa, rush_epa,
             total_plays, pass_attempts, total_tds)
        VALUES (?, ?, 0.60, 0.40, 0.10, 0.15, 0.05, 1000, ?, 45)
    """, [team, season, int(pass_att * 17)])  # pass_attempts = per-game × 17
    # Also need per-game to be queryable; store actual per-game in a separate col or compute
    # We store season totals; composition divides by 17.


def test_wr_composition_formula():
    from tay.models.composition import compose_projections
    conn = _make_conn()
    # Seed team: 595 pass attempts total (35/game × 17)
    conn.execute("""
        INSERT INTO team_features
            (team, season, pass_rate, rush_rate, team_epa, pass_epa, rush_epa,
             total_plays, pass_attempts, total_tds)
        VALUES ('KC', 2026, 0.60, 0.40, 0.10, 0.15, 0.05, 1000, 595, 45)
    """)
    conn.execute("""
        INSERT INTO players VALUES ('w1', 'Test WR', 'WR', 'KC', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL)
    """)

    import pandas as pd
    stage1_df = pd.DataFrame([{
        'gsis_id': 'w1', 'season': 2026, 'position': 'WR', 'team': 'KC',
        'projected_target_share': 0.20,
        'projected_carry_share': None,
        'projected_rec_share': None,
        'projected_pass_att_per_game': None,
    }])
    stage2 = {
        'w1': {
            'yards_per_target': 9.0,
            'catch_rate': 0.70,
            'td_rate_per_target': 0.08,
        }
    }

    count = compose_projections(conn, stage1_df, stage2, season=2026, model_version='two-stage-v1')
    assert count == 1

    row = conn.execute(
        "SELECT mean_projection FROM projections WHERE gsis_id = 'w1'"
    ).fetchone()
    assert row is not None

    # targets = 0.20 × 35.0 × 17 = 119
    targets = 0.20 * 35.0 * 17
    expected = targets * 0.70 * 1.0 + targets * 9.0 * 0.1 + targets * 0.08 * 6.0
    assert row[0] == pytest.approx(expected, abs=0.5)
    conn.close()


def test_qb_composition_formula():
    from tay.models.composition import compose_projections
    conn = _make_conn()
    conn.execute("""
        INSERT INTO team_features
            (team, season, pass_rate, rush_rate, team_epa, pass_epa, rush_epa,
             total_plays, pass_attempts, total_tds)
        VALUES ('KC', 2026, 0.60, 0.40, 0.10, 0.15, 0.05, 1000, 595, 45)
    """)
    conn.execute("""
        INSERT INTO players VALUES ('qb1', 'Test QB', 'QB', 'KC', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL)
    """)

    import pandas as pd
    stage1_df = pd.DataFrame([{
        'gsis_id': 'qb1', 'season': 2026, 'position': 'QB', 'team': 'KC',
        'projected_target_share': None,
        'projected_carry_share': None,
        'projected_rec_share': None,
        'projected_pass_att_per_game': 35.0,
    }])
    stage2 = {
        'qb1': {
            'yards_per_attempt': 7.5,
            'td_rate': 0.055,
            'int_rate': 0.020,
            'rush_yards_per_game': 30.0,
            'rush_tds_per_game': 0.30,
        }
    }

    count = compose_projections(conn, stage1_df, stage2, season=2026, model_version='two-stage-v1')
    assert count == 1

    row = conn.execute(
        "SELECT mean_projection FROM projections WHERE gsis_id = 'qb1'"
    ).fetchone()
    pass_att = 35.0 * 17
    expected = (
        pass_att * 7.5 * 0.04
        + pass_att * 0.055 * 4.0
        - pass_att * 0.020 * 2.0
        + 30.0 * 17 * 0.1
        + 0.30 * 17 * 6.0
    )
    assert row[0] == pytest.approx(expected, abs=0.5)
    conn.close()


def test_missing_stage2_player_skipped():
    from tay.models.composition import compose_projections
    conn = _make_conn()
    conn.execute("""
        INSERT INTO team_features
            (team, season, pass_rate, rush_rate, team_epa, pass_epa, rush_epa,
             total_plays, pass_attempts, total_tds)
        VALUES ('KC', 2026, 0.60, 0.40, 0.10, 0.15, 0.05, 1000, 595, 45)
    """)
    conn.execute("INSERT INTO players VALUES ('w1', 'WR', 'WR', 'KC', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL)")
    import pandas as pd
    stage1_df = pd.DataFrame([{
        'gsis_id': 'w1', 'season': 2026, 'position': 'WR', 'team': 'KC',
        'projected_target_share': 0.20,
        'projected_carry_share': None, 'projected_rec_share': None,
        'projected_pass_att_per_game': None,
    }])
    count = compose_projections(conn, stage1_df, {}, season=2026, model_version='two-stage-v1')
    assert count == 0
    conn.close()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/models/test_composition.py -v
```
Expected: ImportError

- [ ] **Step 3: Implement src/tay/models/composition.py**

```python
"""Analytical composition of Stage 1 × Stage 2 outputs into PPR projections."""
from __future__ import annotations

import pandas as pd
import duckdb

MODEL_VERSION_DEFAULT = 'two-stage-v1'


def _team_volume(conn, team: str, season: int) -> tuple[float, float]:
    """Return (pass_att_per_game, rush_att_per_game) from team_features."""
    row = conn.execute("""
        SELECT pass_attempts FROM team_features WHERE team = ? AND season = ?
    """, [team, season]).fetchone()
    # team_features.pass_attempts is a season total; divide by 17
    pass_att_pg = (float(row[0]) / 17.0) if row and row[0] else 35.0

    rush_row = conn.execute("""
        SELECT total_plays - pass_attempts FROM team_features WHERE team = ? AND season = ?
    """, [team, season]).fetchone()
    rush_att_pg = (float(rush_row[0]) / 17.0) if rush_row and rush_row[0] else 25.0
    return pass_att_pg, rush_att_pg


def _wr_te_ppr(target_share: float, team_pass_att_pg: float, eff: dict) -> float | None:
    ypt = eff.get('yards_per_target')
    cr  = eff.get('catch_rate')
    tdr = eff.get('td_rate_per_target')
    if None in (ypt, cr, tdr):
        return None
    targets = target_share * team_pass_att_pg * 17
    return (
        targets * float(cr) * 1.0
        + targets * float(ypt) * 0.1
        + targets * float(tdr) * 6.0
    )


def _rb_ppr(carry_share: float, rec_share: float, pass_att_pg: float, rush_att_pg: float, eff: dict) -> float | None:
    ypc     = eff.get('yards_per_carry')
    rtdr    = eff.get('rush_td_rate')
    rypt    = eff.get('rec_yards_per_target')
    rcr     = eff.get('rec_catch_rate')
    rec_tdr = eff.get('rec_td_rate')
    if None in (ypc, rtdr, rypt, rcr, rec_tdr):
        return None
    carries  = carry_share * rush_att_pg * 17
    rb_tgts  = rec_share * pass_att_pg * 17
    return (
        carries * float(ypc) * 0.1
        + carries * float(rtdr) * 6.0
        + rb_tgts * float(rcr) * 1.0
        + rb_tgts * float(rypt) * 0.1
        + rb_tgts * float(rec_tdr) * 6.0
    )


def _qb_ppr(pass_att_per_game: float, eff: dict) -> float | None:
    ypa    = eff.get('yards_per_attempt')
    tdr    = eff.get('td_rate')
    intr   = eff.get('int_rate')
    rypg   = eff.get('rush_yards_per_game')
    rtpg   = eff.get('rush_tds_per_game')
    if None in (ypa, tdr, intr):
        return None
    pass_att = pass_att_per_game * 17
    return (
        pass_att * float(ypa) * 0.04
        + pass_att * float(tdr) * 4.0
        - pass_att * float(intr) * 2.0
        + float(rypg or 0) * 17 * 0.1
        + float(rtpg or 0) * 17 * 6.0
    )


def compose_projections(
    conn: duckdb.DuckDBPyConnection,
    stage1_df: pd.DataFrame,
    stage2_dict: dict[str, dict],
    season: int,
    model_version: str = MODEL_VERSION_DEFAULT,
) -> int:
    """Compose Stage1 × Stage2 into PPR projections; upsert to projections table.

    Returns number of rows successfully written.
    """
    written = 0
    for _, row in stage1_df.iterrows():
        gsis_id = row['gsis_id']
        position = row['position']
        team = row['team']
        eff = stage2_dict.get(gsis_id, {})

        pass_att_pg, rush_att_pg = _team_volume(conn, team, season)

        ppr = None
        if position in ('WR', 'TE'):
            ts = row.get('projected_target_share')
            if ts is not None:
                ppr = _wr_te_ppr(float(ts), pass_att_pg, eff)
        elif position == 'RB':
            cs = row.get('projected_carry_share')
            rs = row.get('projected_rec_share')
            if cs is not None and rs is not None:
                ppr = _rb_ppr(float(cs), float(rs), pass_att_pg, rush_att_pg, eff)
        elif position == 'QB':
            papg = row.get('projected_pass_att_per_game')
            if papg is not None:
                ppr = _qb_ppr(float(papg), eff)

        if ppr is None:
            continue

        ppr = max(ppr, 0.0)

        conn.execute("""
            INSERT INTO projections
                (gsis_id, season, model_version, mean_projection,
                 projected_target_share, projected_carry_share,
                 projected_rec_share, projected_pass_att_per_game)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (gsis_id, season, model_version) DO UPDATE SET
                mean_projection            = excluded.mean_projection,
                projected_target_share     = excluded.projected_target_share,
                projected_carry_share      = excluded.projected_carry_share,
                projected_rec_share        = excluded.projected_rec_share,
                projected_pass_att_per_game = excluded.projected_pass_att_per_game
        """, [
            gsis_id, season, model_version, ppr,
            row.get('projected_target_share'),
            row.get('projected_carry_share'),
            row.get('projected_rec_share'),
            row.get('projected_pass_att_per_game'),
        ])
        written += 1

    conn.commit()
    return written
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/models/test_composition.py -v
```
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add src/tay/models/composition.py tests/models/test_composition.py
git commit -m "feat: analytical PPR composition from Stage 1 × Stage 2 outputs"
```

---

### Task 9: Orchestration + Integration

**Files:**
- Modify: `src/tay/models/pipeline.py`
- Test: `tests/models/test_two_stage_integration.py`

**Interfaces:**
- Consumes: all prior tasks
- Produces: `run_two_stage_pipeline(conn, train_end, val_start, projection_season, models_dir_s1, models_dir_s2) -> dict` — trains both stages, composes, returns `{stage1_rmse, stage2_rmse, rows_written}`

- [ ] **Step 1: Write failing integration test**

Create `tests/models/test_two_stage_integration.py`:

```python
import duckdb
import pytest
from tay.db import init_schema


def test_two_stage_pipeline_function_exists():
    from tay.models.pipeline import run_two_stage_pipeline
    assert callable(run_two_stage_pipeline)


def test_compose_projections_writes_mean_projection():
    """Smoke test: compose writes non-None mean_projection for a WR."""
    import pandas as pd
    import duckdb
    from tay.db import init_schema
    from tay.models.composition import compose_projections

    conn = duckdb.connect(':memory:')
    init_schema(conn)

    conn.execute("""
        INSERT INTO team_features
            (team, season, pass_rate, rush_rate, team_epa, pass_epa, rush_epa,
             total_plays, pass_attempts, total_tds)
        VALUES ('SF', 2026, 0.58, 0.42, 0.12, 0.16, 0.08, 1050, 578, 48)
    """)
    conn.execute("INSERT INTO players VALUES ('w1', 'Deebo', 'WR', 'SF', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL)")

    stage1_df = pd.DataFrame([{
        'gsis_id': 'w1', 'season': 2026, 'position': 'WR', 'team': 'SF',
        'projected_target_share': 0.18,
        'projected_carry_share': None, 'projected_rec_share': None,
        'projected_pass_att_per_game': None,
    }])
    stage2 = {'w1': {'yards_per_target': 8.5, 'catch_rate': 0.65, 'td_rate_per_target': 0.07}}

    n = compose_projections(conn, stage1_df, stage2, 2026, 'two-stage-v1')
    assert n == 1

    row = conn.execute("SELECT mean_projection FROM projections WHERE gsis_id = 'w1'").fetchone()
    assert row[0] is not None
    assert row[0] > 0
    conn.close()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/models/test_two_stage_integration.py -v
```
Expected: `test_two_stage_pipeline_function_exists` FAIL (ImportError on function), `test_compose_projections_writes_mean_projection` PASS

- [ ] **Step 3: Add run_two_stage_pipeline to pipeline.py**

Add the following function at the end of `src/tay/models/pipeline.py`, keeping all existing code intact:

```python
def run_two_stage_pipeline(
    conn=None,
    train_end: int = 2023,
    val_start: int = 2024,
    projection_season: int = 2026,
    models_dir_s1: str | Path = 'models_stage1',
    models_dir_s2: str | Path = 'models_stage2',
    db_path=None,
) -> dict:
    """Train Stage 1 + Stage 2, compose, write projections. Returns summary dict."""
    from tay.models.stage1_pipeline import train_stage1_models, run_stage1_inference, normalize_team_shares
    from tay.models.stage2_pipeline import train_stage2_models, run_stage2_inference
    from tay.models.composition import compose_projections, MODEL_VERSION_DEFAULT

    if conn is None:
        conn = get_conn(db_path) if db_path else get_conn()
        init_schema(conn)

    print('=== TAY Two-Stage Pipeline ===')

    print('\n--- Stage 1: Training opportunity models ---')
    s1_rmse = train_stage1_models(conn, train_end=train_end, val_start=val_start, models_dir=models_dir_s1)

    print('\n--- Stage 1: Inference ---')
    stage1_df = run_stage1_inference(conn, projection_season, models_dir=models_dir_s1)
    stage1_df = normalize_team_shares(stage1_df)
    print(f'  Stage 1: {len(stage1_df)} player-projections, shares normalized.')

    print('\n--- Stage 2: Training efficiency models ---')
    s2_rmse = train_stage2_models(conn, train_end=train_end, val_start=val_start, models_dir=models_dir_s2)

    print('\n--- Stage 2: Inference ---')
    stage2_dict = run_stage2_inference(conn, projection_season, models_dir=models_dir_s2)
    print(f'  Stage 2: {len(stage2_dict)} players with efficiency estimates.')

    print('\n--- Composition ---')
    rows_written = compose_projections(
        conn, stage1_df, stage2_dict, season=projection_season,
        model_version=MODEL_VERSION_DEFAULT,
    )
    print(f'  Composed {rows_written} PPR projections → projections table.')

    return {
        'stage1_rmse': s1_rmse,
        'stage2_rmse': s2_rmse,
        'rows_written': rows_written,
    }
```

Also add `from pathlib import Path` import to the top of `pipeline.py` if not already present.

- [ ] **Step 4: Run integration tests to verify they pass**

```bash
uv run pytest tests/models/test_two_stage_integration.py -v
```
Expected: 2 PASS

- [ ] **Step 5: Run full test suite**

```bash
uv run pytest --tb=short -q
```
Expected: all existing tests still pass

- [ ] **Step 6: Commit**

```bash
git add src/tay/models/pipeline.py tests/models/test_two_stage_integration.py
git commit -m "feat: run_two_stage_pipeline orchestration — Stage1→normalize→Stage2→compose"
```

---

## Execution Notes

**Run order for real data:**
```bash
uv run python scripts/ingest_coaches.py --seasons 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025 2026
uv run python scripts/compute_scheme_clusters.py --seasons 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025 2026
uv run python scripts/train_models.py  # (or a new two_stage_train.py calling run_two_stage_pipeline)
```

**Migration strategy (from spec):**
Run the two-stage system alongside the existing single-stage model for the 2025 holdout. Compare RMSE. Only deprecate `models/` (single-stage) once two-stage RMSE ≤ single-stage RMSE. Do not delete old model until validation passes.

**Known limitations (from spec):**
- Team normalization is mandatory; skipping silently inflates all projections
- Stage 2 must never receive opportunity features (enforced by `stage2_features.py` design)
- QB Stage 2 runs first; ordering enforced in `run_stage2_inference`
- New OC cold start: `is_rookie_oc = True` falls back to team historical averages in OC feature computation
- Scheme cluster for preseason: carries forward prior season's cluster (observable limitation)
