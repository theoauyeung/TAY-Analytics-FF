# Consensus Projection Blend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace ML-only projections with a 65/35 blend of expert consensus (FantasyPros + ESPN) and our ML model, fixing systematic failures for injury returnees, rookies, and opportunity-dependent players.

**Architecture:** New `consensus_projections` table stores FantasyPros and ESPN projected stats (one row per player/season/source); `src/tay/projections/blend.py` averages available sources then weights 65% consensus + 35% ML, writing `blended_projection` to the `projections` table; VOR uses `COALESCE(blended_projection, mean_projection)`; running `scripts/ingest_fantasypros.py --season 2026` orchestrates the full refresh end-to-end.

**Tech Stack:** Python/requests/BeautifulSoup4 (already in deps), rapidfuzz (add to deps), DuckDB, existing FastAPI/React stack.

## Global Constraints

- Blend weights: `CONSENSUS_WEIGHT = 0.65`, `ML_WEIGHT = 0.35` — module-level constants in `blend.py`, not runtime configurable.
- PPR scoring formula: `pass_yds×0.04 + pass_tds×4 + ints×(−2) + rush_yds×0.1 + rush_tds×6 + receptions×1.0 + rec_yds×0.1 + rec_tds×6`.
- Fuzzy match threshold: `rapidfuzz.fuzz.token_sort_ratio ≥ 85`.
- `consensus_projections` PRIMARY KEY: `(gsis_id, season, source)`.
- Fallback: when `consensus_projection IS NULL`, `blended_projection = mean_projection`.
- No HTTP calls in tests — scraping tested via local fixture files.
- ESPN stat IDs: `pass_yds=3, pass_tds=4, ints=20, rush_yds=24, rush_tds=25, receptions=41, rec_yds=42, rec_tds=43`.
- All scripts use `sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))` (existing pattern).
- Run all tests with: `uv run pytest tests/ -v`

---

## File Map

| Action | Path | Purpose |
|--------|------|---------|
| Modify | `src/tay/schemas/tables.py` | Add `CONSENSUS_PROJECTIONS` DDL; add 2 new cols to `PROJECTIONS` DDL; append to `ALL_TABLES` |
| Modify | `src/tay/db.py` | Add `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` migrations for existing DBs |
| Create | `src/tay/projections/__init__.py` | Empty package marker |
| Create | `src/tay/projections/blend.py` | `blend_projections(conn, season, model_version) -> int` |
| Modify | `src/tay/valuation/vor.py` | One-line: `COALESCE(blended_projection, mean_projection)` instead of `mean_projection` |
| Create | `src/tay/projections/name_match.py` | `normalize_name()` + `match_player()` for FantasyPros name fuzzy matching |
| Create | `scripts/ingest_fantasypros.py` | Scrape FP (4 positions), compute PPR, fuzzy match, upsert, call blend+VOR |
| Create | `scripts/ingest_espn_projections.py` | ESPN API fetch by espn_id, upsert to consensus_projections |
| Modify | `pyproject.toml` | Add `rapidfuzz>=1.9` to dependencies |
| Create | `tests/projections/__init__.py` | Empty package marker |
| Create | `tests/projections/test_blend.py` | Unit tests for blend_projections |
| Create | `tests/projections/test_name_match.py` | Unit tests for normalize_name + match_player |
| Create | `tests/projections/test_fantasypros_scrape.py` | Scrape tests via fixture HTML (no HTTP) |
| Create | `tests/projections/test_espn_scrape.py` | Scrape tests via fixture JSON (no HTTP) |
| Create | `tests/projections/fixtures/fp_qb.html` | Minimal FantasyPros QB page HTML fixture |
| Create | `tests/projections/fixtures/fp_wr.html` | Minimal FantasyPros WR page HTML fixture |
| Create | `tests/projections/fixtures/espn_players.json` | Minimal ESPN API response fixture |

---

## Task 1: Schema — consensus_projections table + projections new columns

**Files:**
- Modify: `src/tay/schemas/tables.py`
- Modify: `src/tay/db.py`
- Create: `tests/projections/__init__.py`
- Test: `tests/projections/test_blend.py` (schema assertions only in this task — blend logic added in Task 2)

**Interfaces:**
- Produces: `consensus_projections(gsis_id, season, source, pass_yards, pass_tds, interceptions, rush_yards, rush_tds, receptions, rec_yards, rec_tds, points, scraped_at)` with PRIMARY KEY `(gsis_id, season, source)`.
- Produces: `projections` table gains `consensus_projection DOUBLE` and `blended_projection DOUBLE`.

- [ ] **Step 1: Write failing schema test**

Create `tests/projections/__init__.py` (empty) and `tests/projections/test_blend.py`:

```python
import duckdb
import pytest
from tay.db import init_schema


def _make_conn():
    conn = duckdb.connect(':memory:')
    init_schema(conn)
    return conn


def test_consensus_projections_table_exists():
    conn = _make_conn()
    tables = [r[0] for r in conn.execute("SHOW TABLES").fetchall()]
    assert 'consensus_projections' in tables
    conn.close()


def test_consensus_projections_primary_key():
    conn = _make_conn()
    # Duplicate (gsis_id, season, source) must fail
    conn.execute("""
        INSERT INTO consensus_projections (gsis_id, season, source, points)
        VALUES ('p1', 2026, 'fantasypros', 100.0)
    """)
    with pytest.raises(Exception):
        conn.execute("""
            INSERT INTO consensus_projections (gsis_id, season, source, points)
            VALUES ('p1', 2026, 'fantasypros', 200.0)
        """)
    conn.close()


def test_projections_has_blend_columns():
    conn = _make_conn()
    cols = [r[1] for r in conn.execute("PRAGMA table_info('projections')").fetchall()]
    assert 'consensus_projection' in cols
    assert 'blended_projection' in cols
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

```
uv run pytest tests/projections/test_blend.py -v
```

Expected: FAIL — `consensus_projections` table does not exist.

- [ ] **Step 3: Add CONSENSUS_PROJECTIONS DDL to tables.py**

In `src/tay/schemas/tables.py`, add after the `PLAYER_ANALYTICS` block and before `ALL_TABLES`:

```python
CONSENSUS_PROJECTIONS = """
CREATE TABLE IF NOT EXISTS consensus_projections (
    gsis_id         VARCHAR NOT NULL,
    season          INTEGER NOT NULL,
    source          VARCHAR NOT NULL DEFAULT 'fantasypros',
    pass_yards      DOUBLE,
    pass_tds        DOUBLE,
    interceptions   DOUBLE,
    rush_yards      DOUBLE,
    rush_tds        DOUBLE,
    receptions      DOUBLE,
    rec_yards       DOUBLE,
    rec_tds         DOUBLE,
    points          DOUBLE,
    scraped_at      TIMESTAMP DEFAULT current_timestamp,
    PRIMARY KEY (gsis_id, season, source)
)
"""
```

- [ ] **Step 4: Add `consensus_projection` and `blended_projection` to the PROJECTIONS DDL**

In `src/tay/schemas/tables.py`, find the `PROJECTIONS` string. Add two columns after `avail_std DOUBLE,`:

```python
    avail_std           DOUBLE,   -- std dev of games played
    consensus_projection DOUBLE,
    blended_projection   DOUBLE,
    created_at          TIMESTAMP DEFAULT current_timestamp,
```

- [ ] **Step 5: Append CONSENSUS_PROJECTIONS to ALL_TABLES**

In `src/tay/schemas/tables.py`, update the `ALL_TABLES` list:

```python
ALL_TABLES = [
    PLAYERS, PLAY_BY_PLAY, PLAYER_SEASON_STATS, TEAM_SEASON_STATS,
    ROSTERS, DRAFT_PICKS, COMBINE_DATA, ADP, PROJECTIONS, DRAFT_SESSIONS,
    PLAYER_FEATURES, TEAM_FEATURES, SNAP_COUNTS, PLAYER_ANALYTICS,
    CONSENSUS_PROJECTIONS,
]
```

- [ ] **Step 6: Add ALTER TABLE migrations to db.py for existing databases**

In `src/tay/db.py`, update `init_schema`:

```python
def init_schema(conn: duckdb.DuckDBPyConnection) -> None:
    """Create all tables if they do not exist."""
    for ddl in ALL_TABLES:
        conn.execute(ddl)
    # Idempotent migrations for existing databases
    conn.execute("ALTER TABLE projections ADD COLUMN IF NOT EXISTS consensus_projection DOUBLE")
    conn.execute("ALTER TABLE projections ADD COLUMN IF NOT EXISTS blended_projection DOUBLE")
    conn.commit()
```

- [ ] **Step 7: Run tests to verify they pass**

```
uv run pytest tests/projections/test_blend.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 8: Run full suite to check for regressions**

```
uv run pytest tests/ -v
```

Expected: all previously passing tests still PASS.

- [ ] **Step 9: Commit**

```bash
git add src/tay/schemas/tables.py src/tay/db.py tests/projections/__init__.py tests/projections/test_blend.py
git commit -m "feat: add consensus_projections table and blend columns to projections"
```

---

## Task 2: blend.py — blend_projections function

**Files:**
- Create: `src/tay/projections/__init__.py`
- Create: `src/tay/projections/blend.py`
- Modify: `tests/projections/test_blend.py` (add blend logic tests)

**Interfaces:**
- Consumes: `consensus_projections(gsis_id, season, source, points)` and `projections(gsis_id, season, model_version, mean_projection, consensus_projection, blended_projection)`.
- Produces: `blend_projections(conn: duckdb.DuckDBPyConnection, season: int, model_version: str) -> int` — updates `consensus_projection` and `blended_projection` in `projections`; returns count of rows given a blended value (not fallback).

- [ ] **Step 1: Add blend logic tests to tests/projections/test_blend.py**

Append to `tests/projections/test_blend.py`:

```python
from tay.projections.blend import blend_projections, CONSENSUS_WEIGHT, ML_WEIGHT


def _make_blend_conn():
    """In-memory DB with projections + consensus_projections tables."""
    conn = duckdb.connect(':memory:')
    conn.execute("""
        CREATE TABLE projections (
            gsis_id VARCHAR, season INTEGER, model_version VARCHAR,
            mean_projection DOUBLE,
            consensus_projection DOUBLE,
            blended_projection DOUBLE,
            PRIMARY KEY (gsis_id, season, model_version)
        )
    """)
    conn.execute("""
        CREATE TABLE consensus_projections (
            gsis_id VARCHAR, season INTEGER, source VARCHAR,
            points DOUBLE,
            PRIMARY KEY (gsis_id, season, source)
        )
    """)
    return conn


def test_blend_weights_are_correct():
    assert CONSENSUS_WEIGHT == 0.65
    assert ML_WEIGHT == 0.35


def test_blend_single_source():
    conn = _make_blend_conn()
    conn.execute("INSERT INTO projections VALUES ('p1', 2026, 'v1', 300.0, NULL, NULL)")
    conn.execute("INSERT INTO consensus_projections VALUES ('p1', 2026, 'fantasypros', 350.0)")
    count = blend_projections(conn, 2026, 'v1')
    row = conn.execute(
        "SELECT consensus_projection, blended_projection FROM projections WHERE gsis_id='p1'"
    ).fetchone()
    assert row[0] == pytest.approx(350.0)
    assert row[1] == pytest.approx(0.65 * 350.0 + 0.35 * 300.0)
    assert count == 1
    conn.close()


def test_blend_two_sources_averaged():
    conn = _make_blend_conn()
    conn.execute("INSERT INTO projections VALUES ('p1', 2026, 'v1', 300.0, NULL, NULL)")
    conn.execute("INSERT INTO consensus_projections VALUES ('p1', 2026, 'fantasypros', 360.0)")
    conn.execute("INSERT INTO consensus_projections VALUES ('p1', 2026, 'espn', 340.0)")
    blend_projections(conn, 2026, 'v1')
    row = conn.execute(
        "SELECT consensus_projection, blended_projection FROM projections WHERE gsis_id='p1'"
    ).fetchone()
    avg_consensus = (360.0 + 340.0) / 2  # 350.0
    assert row[0] == pytest.approx(avg_consensus)
    assert row[1] == pytest.approx(0.65 * avg_consensus + 0.35 * 300.0)
    conn.close()


def test_blend_fallback_ml_only():
    """Players with no consensus row get blended_projection = mean_projection."""
    conn = _make_blend_conn()
    conn.execute("INSERT INTO projections VALUES ('p1', 2026, 'v1', 200.0, NULL, NULL)")
    # No row in consensus_projections
    count = blend_projections(conn, 2026, 'v1')
    row = conn.execute(
        "SELECT consensus_projection, blended_projection FROM projections WHERE gsis_id='p1'"
    ).fetchone()
    assert row[0] is None
    assert row[1] == pytest.approx(200.0)
    assert count == 0  # 0 blended, fallback not counted
    conn.close()


def test_blend_mixed_players():
    """Some players have consensus, some don't."""
    conn = _make_blend_conn()
    conn.execute("INSERT INTO projections VALUES ('p1', 2026, 'v1', 300.0, NULL, NULL)")
    conn.execute("INSERT INTO projections VALUES ('p2', 2026, 'v1', 180.0, NULL, NULL)")
    conn.execute("INSERT INTO consensus_projections VALUES ('p1', 2026, 'fantasypros', 350.0)")
    count = blend_projections(conn, 2026, 'v1')
    p1 = conn.execute("SELECT blended_projection FROM projections WHERE gsis_id='p1'").fetchone()[0]
    p2 = conn.execute("SELECT blended_projection FROM projections WHERE gsis_id='p2'").fetchone()[0]
    assert p1 == pytest.approx(0.65 * 350.0 + 0.35 * 300.0)
    assert p2 == pytest.approx(180.0)  # fallback to ML
    assert count == 1
    conn.close()
```

- [ ] **Step 2: Run tests to verify they fail**

```
uv run pytest tests/projections/test_blend.py -v -k "blend"
```

Expected: FAIL — `ModuleNotFoundError: No module named 'tay.projections'`.

- [ ] **Step 3: Create the projections package and blend.py**

Create `src/tay/projections/__init__.py` (empty file).

Create `src/tay/projections/blend.py`:

```python
"""Blend consensus projections with ML model projections."""
from __future__ import annotations
import duckdb

CONSENSUS_WEIGHT = 0.65
ML_WEIGHT = 0.35


def blend_projections(
    conn: duckdb.DuckDBPyConnection,
    season: int,
    model_version: str,
) -> int:
    """Write consensus_projection and blended_projection to projections table.

    Averages all consensus sources for a player, then blends 65% consensus
    + 35% ML. Returns count of rows given a true blended value (not fallback).
    Falls back to mean_projection when no consensus row exists for a player.
    """
    conn.execute("""
        UPDATE projections
        SET consensus_projection = cp_agg.avg_pts,
            blended_projection   = ? * cp_agg.avg_pts + ? * mean_projection
        FROM (
            SELECT gsis_id, AVG(points) AS avg_pts
            FROM consensus_projections
            WHERE season = ?
            GROUP BY gsis_id
        ) cp_agg
        WHERE projections.gsis_id       = cp_agg.gsis_id
          AND projections.season        = ?
          AND projections.model_version = ?
    """, [CONSENSUS_WEIGHT, ML_WEIGHT, season, season, model_version])

    blended_count = conn.execute("""
        SELECT COUNT(*) FROM projections
        WHERE season = ? AND model_version = ?
          AND blended_projection IS NOT NULL
    """, [season, model_version]).fetchone()[0]

    # Fallback: no consensus data → use ML projection directly
    conn.execute("""
        UPDATE projections
        SET blended_projection = mean_projection
        WHERE season = ? AND model_version = ?
          AND blended_projection IS NULL
          AND mean_projection IS NOT NULL
    """, [season, model_version])

    conn.commit()
    return blended_count
```

- [ ] **Step 4: Run tests to verify they pass**

```
uv run pytest tests/projections/test_blend.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Run full suite**

```
uv run pytest tests/ -v
```

Expected: all previously passing tests still PASS.

- [ ] **Step 6: Commit**

```bash
git add src/tay/projections/__init__.py src/tay/projections/blend.py tests/projections/test_blend.py
git commit -m "feat: add blend_projections — 65% consensus + 35% ML with ML fallback"
```

---

## Task 3: Update VOR to use blended_projection

**Files:**
- Modify: `src/tay/valuation/vor.py`
- Modify: `tests/valuation/test_vor.py`

**Interfaces:**
- Consumes: `projections.blended_projection DOUBLE` (from Task 1).
- Produces: VOR computed from `COALESCE(blended_projection, mean_projection)` instead of raw `mean_projection`.

- [ ] **Step 1: Add blended_projection tests to tests/valuation/test_vor.py**

Append to `tests/valuation/test_vor.py`:

```python
def test_vor_uses_blended_projection_when_present():
    """VOR should use blended_projection, not mean_projection, when available."""
    conn = duckdb.connect(':memory:')
    conn.execute("CREATE TABLE players (gsis_id VARCHAR PRIMARY KEY, position VARCHAR)")
    conn.execute("""
        CREATE TABLE projections (
            gsis_id VARCHAR, season INTEGER, model_version VARCHAR,
            mean_projection DOUBLE,
            blended_projection DOUBLE,
            vor DOUBLE, vor_rank INTEGER,
            PRIMARY KEY (gsis_id, season, model_version)
        )
    """)
    conn.execute("INSERT INTO players VALUES ('rb1', 'RB')")
    conn.execute("INSERT INTO players VALUES ('rb2', 'RB')")
    # rb1 has blended > mean; rb2 has no blended
    conn.execute("INSERT INTO projections (gsis_id, season, model_version, mean_projection, blended_projection) VALUES ('rb1', 2026, 'v1', 200.0, 250.0)")
    conn.execute("INSERT INTO projections (gsis_id, season, model_version, mean_projection, blended_projection) VALUES ('rb2', 2026, 'v1', 150.0, NULL)")
    repl = {'RB': 150.0}
    compute_vor(conn, 2026, 'v1', repl)
    rb1_vor = conn.execute("SELECT vor FROM projections WHERE gsis_id='rb1'").fetchone()[0]
    rb2_vor = conn.execute("SELECT vor FROM projections WHERE gsis_id='rb2'").fetchone()[0]
    # rb1: (250 - 150) * 1.0 = 100.0  (uses blended_projection)
    assert rb1_vor == pytest.approx(100.0)
    # rb2: (150 - 150) * 1.0 = 0.0  (falls back to mean_projection)
    assert rb2_vor == pytest.approx(0.0)
    conn.close()
```

- [ ] **Step 2: Run new test to verify it fails**

```
uv run pytest tests/valuation/test_vor.py::test_vor_uses_blended_projection_when_present -v
```

Expected: FAIL — VOR uses `mean_projection`, so rb1_vor = (200-150)*1.0 = 50.0, not 100.0.

- [ ] **Step 3: Update vor.py to use COALESCE**

In `src/tay/valuation/vor.py`, in the `compute_vor` function, change the UPDATE statement from:

```python
        conn.execute("""
            UPDATE projections
            SET vor = (mean_projection - ?) * ?
            WHERE season = ? AND model_version = ?
              AND gsis_id IN (SELECT gsis_id FROM players WHERE position = ?)
        """, [repl, weight, season, model_version, pos])
```

to:

```python
        conn.execute("""
            UPDATE projections
            SET vor = (COALESCE(blended_projection, mean_projection) - ?) * ?
            WHERE season = ? AND model_version = ?
              AND gsis_id IN (SELECT gsis_id FROM players WHERE position = ?)
        """, [repl, weight, season, model_version, pos])
```

Also update the existing `_make_conn()` helper in `tests/valuation/test_vor.py` to include `blended_projection DOUBLE` in the `projections` CREATE TABLE so existing tests keep working:

```python
def _make_conn():
    conn = duckdb.connect(':memory:')
    conn.execute("CREATE TABLE players (gsis_id VARCHAR PRIMARY KEY, position VARCHAR)")
    conn.execute("""
        CREATE TABLE projections (
            gsis_id VARCHAR, season INTEGER, model_version VARCHAR,
            mean_projection DOUBLE,
            blended_projection DOUBLE,
            vor DOUBLE, vor_rank INTEGER,
            PRIMARY KEY (gsis_id, season, model_version)
        )
    """)
    # ... rest of data inserts unchanged ...
```

- [ ] **Step 4: Run all VOR tests**

```
uv run pytest tests/valuation/test_vor.py -v
```

Expected: all 5 tests PASS (4 existing + 1 new).

- [ ] **Step 5: Run full suite**

```
uv run pytest tests/ -v
```

Expected: all previously passing tests still PASS.

- [ ] **Step 6: Commit**

```bash
git add src/tay/valuation/vor.py tests/valuation/test_vor.py
git commit -m "feat: VOR uses COALESCE(blended_projection, mean_projection)"
```

---

## Task 4: Player name normalization + fuzzy matching

**Files:**
- Create: `src/tay/projections/name_match.py`
- Modify: `pyproject.toml` (add rapidfuzz)
- Test: `tests/projections/test_name_match.py`

**Interfaces:**
- Produces: `normalize_name(name: str) -> str` — lowercase, strip punctuation/apostrophes/hyphens/periods, drop suffixes (Jr/Sr/II/III/IV/V), collapse whitespace.
- Produces: `match_player(fp_name: str, db_players: list[tuple[str, str]], threshold: int = 85) -> str | None` — returns `gsis_id` of best match above threshold, `None` if no match.
- `db_players` is a list of `(gsis_id, normalized_name)` tuples.

- [ ] **Step 1: Add rapidfuzz to pyproject.toml**

In `pyproject.toml`, add to the dependencies list:

```toml
    "rapidfuzz>=1.9",
```

Install it:

```
uv sync
```

- [ ] **Step 2: Write failing tests**

Create `tests/projections/test_name_match.py`:

```python
import pytest
from tay.projections.name_match import normalize_name, match_player


def test_normalize_lowercase():
    assert normalize_name("Patrick Mahomes") == "patrick mahomes"


def test_normalize_strips_suffix_jr():
    assert normalize_name("Travis Etienne Jr.") == "travis etienne"


def test_normalize_strips_suffix_sr():
    assert normalize_name("Michael Pittman Sr.") == "michael pittman"


def test_normalize_strips_suffix_ii():
    assert normalize_name("Odell Beckham II") == "odell beckham"


def test_normalize_strips_suffix_iii():
    assert normalize_name("Michael Thomas III") == "michael thomas"


def test_normalize_removes_apostrophe():
    assert normalize_name("Ja'Marr Chase") == "jamarr chase"


def test_normalize_removes_hyphen():
    assert normalize_name("De'Von Achane") == "devon achane"


def test_normalize_removes_period_in_initials():
    assert normalize_name("D.K. Metcalf") == "dk metcalf"


def test_normalize_collapses_whitespace():
    assert normalize_name("  Josh   Allen  ") == "josh allen"


def test_match_player_exact():
    db = [("id1", "patrick mahomes"), ("id2", "lamar jackson")]
    assert match_player("Patrick Mahomes", db) == "id1"


def test_match_player_fuzzy_suffix():
    db = [("id1", "travis etienne"), ("id2", "lamar jackson")]
    # "Travis Etienne Jr." normalizes to "travis etienne" — exact after norm
    assert match_player("Travis Etienne Jr.", db) == "id1"


def test_match_player_fuzzy_initials():
    db = [("id1", "dk metcalf"), ("id2", "lamar jackson")]
    # "D.K. Metcalf" normalizes to "dk metcalf" — exact after norm
    assert match_player("D.K. Metcalf", db) == "id1"


def test_match_player_below_threshold_returns_none():
    db = [("id1", "lamar jackson"), ("id2", "josh allen")]
    assert match_player("Totally Different Name", db) is None


def test_match_player_empty_db_returns_none():
    assert match_player("Patrick Mahomes", []) is None
```

- [ ] **Step 3: Run to verify they fail**

```
uv run pytest tests/projections/test_name_match.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'tay.projections.name_match'`.

- [ ] **Step 4: Create name_match.py**

Create `src/tay/projections/name_match.py`:

```python
"""Player name normalization and fuzzy matching for FantasyPros name resolution."""
from __future__ import annotations
import re
import unicodedata

from rapidfuzz import fuzz, process

_SUFFIX_RE = re.compile(r'\b(jr|sr|ii|iii|iv|v)\b\.?', re.IGNORECASE)
_PUNCT_RE  = re.compile(r"['\-\.]")
_SPACE_RE  = re.compile(r'\s+')


def normalize_name(name: str) -> str:
    """Lowercase, strip punctuation/suffixes, collapse whitespace."""
    name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode()
    name = name.lower()
    name = _SUFFIX_RE.sub('', name)
    name = _PUNCT_RE.sub('', name)
    name = _SPACE_RE.sub(' ', name).strip()
    return name


def match_player(
    fp_name: str,
    db_players: list[tuple[str, str]],
    threshold: int = 85,
) -> str | None:
    """Return gsis_id for the best fuzzy match of fp_name against db_players.

    db_players is a list of (gsis_id, normalized_name) tuples.
    Returns None if no match exceeds threshold.
    """
    if not db_players:
        return None
    norm = normalize_name(fp_name)
    names = [name for _, name in db_players]

    # Exact match first
    for gsis_id, db_name in db_players:
        if db_name == norm:
            return gsis_id

    # Fuzzy match
    result = process.extractOne(norm, names, scorer=fuzz.token_sort_ratio)
    if result is None or result[1] < threshold:
        return None
    return db_players[result[2]][0]
```

- [ ] **Step 5: Run tests to verify they pass**

```
uv run pytest tests/projections/test_name_match.py -v
```

Expected: all 14 tests PASS.

- [ ] **Step 6: Run full suite**

```
uv run pytest tests/ -v
```

Expected: all previously passing tests still PASS.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml src/tay/projections/name_match.py tests/projections/test_name_match.py
git commit -m "feat: add player name normalization and fuzzy matching for FantasyPros"
```

---

## Task 5: FantasyPros scraper + orchestrator

**Files:**
- Create: `scripts/ingest_fantasypros.py`
- Create: `tests/projections/fixtures/fp_qb.html`
- Create: `tests/projections/fixtures/fp_wr.html`
- Test: `tests/projections/test_fantasypros_scrape.py`

**Interfaces:**
- Consumes: `normalize_name`, `match_player` from `tay.projections.name_match`.
- Consumes: `blend_projections` from `tay.projections.blend`.
- Consumes: `compute_vor` from `tay.valuation.vor`.
- Produces: `scrape_position(html: str, position: str) -> list[dict]` — parses HTML, returns list of `{name, pass_yards, pass_tds, interceptions, rush_yards, rush_tds, receptions, rec_yards, rec_tds, points}` dicts (all numeric fields default 0.0).
- Produces: `ingest_fantasypros(conn, season) -> dict` — orchestrates scrape → match → upsert → blend → VOR; returns `{matched, unmatched, blended, vor_rows}`.

- [ ] **Step 1: Create fixture HTML files**

Create `tests/projections/fixtures/fp_qb.html` — minimal FantasyPros QB projections page:

```html
<html><body>
<table id="data">
<thead>
<tr>
<th class="player-label">Player</th>
<th>ATT</th><th>CMP</th><th>YDS</th><th>TDS</th><th>INTS</th>
<th>ATT</th><th>YDS</th><th>TDS</th>
<th>FL</th><th>FPTS</th>
</tr>
</thead>
<tbody>
<tr>
<td><a href="#">Patrick Mahomes</a><em>KC</em></td>
<td>575</td><td>387</td><td>4900</td><td>37</td><td>11</td>
<td>60</td><td>305</td><td>4</td>
<td>3</td><td>380</td>
</tr>
<tr>
<td><a href="#">Lamar Jackson</a><em>BAL</em></td>
<td>440</td><td>296</td><td>3600</td><td>26</td><td>7</td>
<td>130</td><td>920</td><td>5</td>
<td>2</td><td>360</td>
</tr>
</tbody>
</table>
</body></html>
```

Create `tests/projections/fixtures/fp_wr.html` — minimal FantasyPros WR projections page:

```html
<html><body>
<table id="data">
<thead>
<tr>
<th class="player-label">Player</th>
<th>REC</th><th>YDS</th><th>TDS</th>
<th>ATT</th><th>YDS</th><th>TDS</th>
<th>FL</th><th>FPTS</th>
</tr>
</thead>
<tbody>
<tr>
<td><a href="#">Ja'Marr Chase</a><em>CIN</em></td>
<td>95</td><td>1400</td><td>11</td>
<td>5</td><td>30</td><td>0</td>
<td>2</td><td>303</td>
</tr>
<tr>
<td><a href="#">Travis Etienne Jr.</a><em>JAC</em></td>
<td>50</td><td>450</td><td>3</td>
<td>180</td><td>1100</td><td>9</td>
<td>3</td><td>210</td>
</tr>
</tbody>
</table>
</body></html>
```

- [ ] **Step 2: Write failing scrape tests**

Create `tests/projections/test_fantasypros_scrape.py`:

```python
import pytest
from pathlib import Path

FIXTURES = Path(__file__).parent / 'fixtures'


def _read(fname):
    return (FIXTURES / fname).read_text()


def test_scrape_qb_player_count():
    from scripts.ingest_fantasypros import scrape_position
    rows = scrape_position(_read('fp_qb.html'), 'QB')
    assert len(rows) == 2


def test_scrape_qb_mahomes_name():
    from scripts.ingest_fantasypros import scrape_position
    rows = scrape_position(_read('fp_qb.html'), 'QB')
    assert rows[0]['name'] == 'Patrick Mahomes'


def test_scrape_qb_mahomes_ppr_points():
    from scripts.ingest_fantasypros import scrape_position
    rows = scrape_position(_read('fp_qb.html'), 'QB')
    mahomes = rows[0]
    # pass_yds=4900×0.04=196 + pass_tds=37×4=148 + ints=11×(−2)=−22
    # + rush_yds=305×0.1=30.5 + rush_tds=4×6=24 = 376.5
    assert mahomes['points'] == pytest.approx(376.5)


def test_scrape_qb_lamar_ppr_points():
    from scripts.ingest_fantasypros import scrape_position
    rows = scrape_position(_read('fp_qb.html'), 'QB')
    lamar = rows[1]
    # 3600×0.04=144 + 26×4=104 + 7×(−2)=−14 + 920×0.1=92 + 5×6=30 = 356
    assert lamar['points'] == pytest.approx(356.0)


def test_scrape_wr_chase_ppr_points():
    from scripts.ingest_fantasypros import scrape_position
    rows = scrape_position(_read('fp_wr.html'), 'WR')
    chase = rows[0]
    # rec=95×1=95 + rec_yds=1400×0.1=140 + rec_tds=11×6=66
    # + rush_yds=30×0.1=3 + rush_tds=0×6=0 = 304
    assert chase['points'] == pytest.approx(304.0)


def test_scrape_wr_etienne_name_preserved():
    from scripts.ingest_fantasypros import scrape_position
    rows = scrape_position(_read('fp_wr.html'), 'WR')
    assert rows[1]['name'] == "Travis Etienne Jr."
```

- [ ] **Step 3: Run to verify they fail**

```
uv run pytest tests/projections/test_fantasypros_scrape.py -v
```

Expected: FAIL — `ModuleNotFoundError` or `ImportError` for `scripts.ingest_fantasypros`.

- [ ] **Step 4: Create scripts/ingest_fantasypros.py**

```python
#!/usr/bin/env python3
"""Ingest FantasyPros consensus projections and refresh rankings.

Usage:
    uv run python scripts/ingest_fantasypros.py --season 2026

Orchestrates the full consensus refresh:
  1. Scrape FantasyPros (4 positions)
  2. Match player names to gsis_id via fuzzy matching
  3. Upsert to consensus_projections (source='fantasypros')
  4. Call blend_projections()
  5. Call compute_vor()
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from tay.db import get_conn, init_schema
from tay.projections.blend import blend_projections
from tay.projections.name_match import normalize_name, match_player
from tay.valuation.pipeline import run_valuation
from tay.valuation.replacement import ReplacementConfig

_FP_URLS = {
    'QB': 'https://www.fantasypros.com/nfl/projections/qb.php?week=draft&scoring=PPR',
    'RB': 'https://www.fantasypros.com/nfl/projections/rb.php?week=draft&scoring=PPR',
    'WR': 'https://www.fantasypros.com/nfl/projections/wr.php?week=draft&scoring=PPR',
    'TE': 'https://www.fantasypros.com/nfl/projections/te.php?week=draft&scoring=PPR',
}

# Stat column indices (0-based, after the Player column) per position
_COL_IDX = {
    'QB': {'pass_yards': 2, 'pass_tds': 3, 'interceptions': 4, 'rush_yards': 6, 'rush_tds': 7},
    'RB': {'rush_yards': 1, 'rush_tds': 2, 'receptions': 3, 'rec_yards': 4, 'rec_tds': 5},
    'WR': {'receptions': 0, 'rec_yards': 1, 'rec_tds': 2, 'rush_yards': 4, 'rush_tds': 5},
    'TE': {'receptions': 0, 'rec_yards': 1, 'rec_tds': 2},
}


def _ppr(row: dict) -> float:
    return (
        row.get('pass_yards', 0.0)    * 0.04
        + row.get('pass_tds', 0.0)   * 4.0
        + row.get('interceptions', 0.0) * -2.0
        + row.get('rush_yards', 0.0)  * 0.1
        + row.get('rush_tds', 0.0)   * 6.0
        + row.get('receptions', 0.0) * 1.0
        + row.get('rec_yards', 0.0)  * 0.1
        + row.get('rec_tds', 0.0)    * 6.0
    )


def scrape_position(html: str, position: str) -> list[dict]:
    """Parse FantasyPros projection HTML for one position.

    Returns list of dicts with 'name' and stat fields; 'points' is PPR total.
    """
    soup = BeautifulSoup(html, 'lxml')
    table = soup.find('table', id='data')
    if table is None:
        return []
    rows = []
    for tr in table.find('tbody').find_all('tr'):
        cells = tr.find_all('td')
        if not cells:
            continue
        # Player name is in an <a> tag in the first cell
        a_tag = cells[0].find('a')
        if a_tag is None:
            continue
        name = a_tag.get_text(strip=True)
        # Stat cells start at index 1
        stat_cells = cells[1:]
        col_map = _COL_IDX.get(position, {})
        stat: dict = {'name': name}
        for field, idx in col_map.items():
            if idx < len(stat_cells):
                raw = stat_cells[idx].get_text(strip=True).replace(',', '')
                try:
                    stat[field] = float(raw)
                except ValueError:
                    stat[field] = 0.0
            else:
                stat[field] = 0.0
        stat['points'] = _ppr(stat)
        rows.append(stat)
    return rows


def fetch_and_scrape(position: str) -> list[dict]:
    url = _FP_URLS[position]
    resp = requests.get(url, timeout=30, headers={'User-Agent': 'Mozilla/5.0'})
    resp.raise_for_status()
    return scrape_position(resp.text, position)


def ingest_fantasypros(conn, season: int) -> dict:
    """Scrape FP, match names, upsert consensus_projections, blend, run VOR."""
    # Load all players for name matching
    db_players_raw = conn.execute(
        "SELECT gsis_id, name FROM players WHERE position IN ('QB','RB','WR','TE')"
    ).fetchall()
    db_players = [(gsis_id, normalize_name(name)) for gsis_id, name in db_players_raw]

    matched = 0
    unmatched = 0
    rows_to_upsert = []

    for pos in ['QB', 'RB', 'WR', 'TE']:
        print(f'Scraping FantasyPros {pos}...', flush=True)
        try:
            fp_rows = fetch_and_scrape(pos)
        except Exception as e:
            print(f'  FAILED: {e}', file=sys.stderr)
            continue

        for row in fp_rows:
            gsis_id = match_player(row['name'], db_players)
            if gsis_id is None:
                print(f'UNMATCHED: {row["name"]}', file=sys.stderr)
                unmatched += 1
                continue
            rows_to_upsert.append((
                gsis_id, season, 'fantasypros',
                row.get('pass_yards', None),
                row.get('pass_tds', None),
                row.get('interceptions', None),
                row.get('rush_yards', None),
                row.get('rush_tds', None),
                row.get('receptions', None),
                row.get('rec_yards', None),
                row.get('rec_tds', None),
                row['points'],
            ))
            matched += 1
        print(f'  {pos}: {len(fp_rows)} players scraped', flush=True)

    conn.executemany("""
        INSERT INTO consensus_projections
            (gsis_id, season, source,
             pass_yards, pass_tds, interceptions,
             rush_yards, rush_tds,
             receptions, rec_yards, rec_tds,
             points)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (gsis_id, season, source) DO UPDATE SET
            pass_yards    = excluded.pass_yards,
            pass_tds      = excluded.pass_tds,
            interceptions = excluded.interceptions,
            rush_yards    = excluded.rush_yards,
            rush_tds      = excluded.rush_tds,
            receptions    = excluded.receptions,
            rec_yards     = excluded.rec_yards,
            rec_tds       = excluded.rec_tds,
            points        = excluded.points,
            scraped_at    = current_timestamp
    """, rows_to_upsert)
    conn.commit()
    print(f'Upserted {matched} consensus rows ({unmatched} unmatched).', flush=True)

    print('Blending projections...', flush=True)
    blended = blend_projections(conn, season, 'neural-v1')
    print(f'  {blended} players received a blended projection.', flush=True)

    print('Recomputing VOR...', flush=True)
    config = ReplacementConfig()
    result = run_valuation(conn, season=season, model_version='neural-v1', config=config)

    return {
        'matched': matched,
        'unmatched': unmatched,
        'blended': blended,
        'vor_rows': result['vor_rows'],
    }


def main() -> None:
    p = argparse.ArgumentParser(description='Ingest FantasyPros consensus projections')
    p.add_argument('--season', type=int, default=2026)
    args = p.parse_args()

    conn = get_conn()
    init_schema(conn)
    result = ingest_fantasypros(conn, args.season)
    conn.close()
    print(f"\nDone. matched={result['matched']}, unmatched={result['unmatched']}, "
          f"blended={result['blended']}, vor_rows={result['vor_rows']}")


if __name__ == '__main__':
    main()
```

- [ ] **Step 5: Run scrape tests to verify they pass**

```
uv run pytest tests/projections/test_fantasypros_scrape.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 6: Run full suite**

```
uv run pytest tests/ -v
```

Expected: all previously passing tests still PASS.

- [ ] **Step 7: Commit**

```bash
git add scripts/ingest_fantasypros.py \
        tests/projections/test_fantasypros_scrape.py \
        tests/projections/fixtures/fp_qb.html \
        tests/projections/fixtures/fp_wr.html
git commit -m "feat: FantasyPros scraper + full refresh orchestrator"
```

---

## Task 6: ESPN projections scraper

**Files:**
- Create: `scripts/ingest_espn_projections.py`
- Create: `tests/projections/fixtures/espn_players.json`
- Test: `tests/projections/test_espn_scrape.py`

**Interfaces:**
- Consumes: `players.espn_id VARCHAR` from the `players` table.
- Produces: `parse_espn_response(data: dict) -> list[dict]` — extracts projected stats from ESPN API JSON; returns list of `{espn_id (str), pass_yards, pass_tds, interceptions, rush_yards, rush_tds, receptions, rec_yards, rec_tds, points}`.
- Produces: `ingest_espn(conn, season) -> dict` — fetches ESPN API, matches via `espn_id`, upserts to `consensus_projections` with `source='espn'`; returns `{matched, unmatched}`.
- ESPN stat IDs to field names: `{'3': 'pass_yards', '4': 'pass_tds', '20': 'interceptions', '24': 'rush_yards', '25': 'rush_tds', '41': 'receptions', '42': 'rec_yards', '43': 'rec_tds'}`.

- [ ] **Step 1: Create ESPN fixture JSON**

Create `tests/projections/fixtures/espn_players.json`:

```json
{
  "players": [
    {
      "id": 3054211,
      "playerPoolEntry": {
        "player": {
          "fullName": "Patrick Mahomes",
          "stats": [
            {
              "statSourceId": 1,
              "scoringPeriodId": 0,
              "statSplitTypeId": 0,
              "stats": {
                "3": 4800.0,
                "4": 36.0,
                "20": 10.0,
                "24": 280.0,
                "25": 3.0,
                "41": 0.0,
                "42": 0.0,
                "43": 0.0
              }
            }
          ]
        }
      }
    },
    {
      "id": 3916387,
      "playerPoolEntry": {
        "player": {
          "fullName": "Ja'Marr Chase",
          "stats": [
            {
              "statSourceId": 1,
              "scoringPeriodId": 0,
              "statSplitTypeId": 0,
              "stats": {
                "3": 0.0,
                "4": 0.0,
                "20": 0.0,
                "24": 25.0,
                "25": 0.0,
                "41": 90.0,
                "42": 1350.0,
                "43": 10.0
              }
            }
          ]
        }
      }
    },
    {
      "id": 9999999,
      "playerPoolEntry": {
        "player": {
          "fullName": "No Stats Player",
          "stats": [
            {
              "statSourceId": 0,
              "scoringPeriodId": 0,
              "statSplitTypeId": 0,
              "stats": {"3": 1000.0}
            }
          ]
        }
      }
    }
  ]
}
```

- [ ] **Step 2: Write failing tests**

Create `tests/projections/test_espn_scrape.py`:

```python
import json
import pytest
from pathlib import Path

FIXTURES = Path(__file__).parent / 'fixtures'


def _load():
    return json.loads((FIXTURES / 'espn_players.json').read_text())


def test_parse_espn_returns_two_players_with_stats():
    from scripts.ingest_espn_projections import parse_espn_response
    rows = parse_espn_response(_load())
    # 3rd player has no statSourceId=1 entry, should be excluded
    assert len(rows) == 2


def test_parse_espn_mahomes_espn_id():
    from scripts.ingest_espn_projections import parse_espn_response
    rows = parse_espn_response(_load())
    mahomes = next(r for r in rows if r['espn_id'] == '3054211')
    assert mahomes is not None


def test_parse_espn_mahomes_points():
    from scripts.ingest_espn_projections import parse_espn_response
    rows = parse_espn_response(_load())
    mahomes = next(r for r in rows if r['espn_id'] == '3054211')
    # 4800×0.04=192 + 36×4=144 + 10×(−2)=−20 + 280×0.1=28 + 3×6=18 = 362
    assert mahomes['points'] == pytest.approx(362.0)


def test_parse_espn_chase_points():
    from scripts.ingest_espn_projections import parse_espn_response
    rows = parse_espn_response(_load())
    chase = next(r for r in rows if r['espn_id'] == '3916387')
    # rec=90×1=90 + rec_yds=1350×0.1=135 + rec_tds=10×6=60
    # + rush_yds=25×0.1=2.5 = 287.5
    assert chase['points'] == pytest.approx(287.5)


def test_parse_espn_excludes_non_projected_stats():
    from scripts.ingest_espn_projections import parse_espn_response
    rows = parse_espn_response(_load())
    espn_ids = [r['espn_id'] for r in rows]
    assert '9999999' not in espn_ids
```

- [ ] **Step 3: Run to verify they fail**

```
uv run pytest tests/projections/test_espn_scrape.py -v
```

Expected: FAIL — `ModuleNotFoundError` for `scripts.ingest_espn_projections`.

- [ ] **Step 4: Create scripts/ingest_espn_projections.py**

```python
#!/usr/bin/env python3
"""Ingest ESPN Fantasy API consensus projections.

Usage:
    uv run python scripts/ingest_espn_projections.py --season 2026

Fetches ESPN projected stats, matches players via espn_id, and upserts
to consensus_projections with source='espn'. Run before ingest_fantasypros.py
so the blend step picks up both sources.
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from tay.db import get_conn, init_schema

_ESPN_URL = (
    'https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{season}'
    '/players?scoringPeriodId=0&view=kona_player_info'
)

_ESPN_HEADERS = {
    'X-Fantasy-Filter': json.dumps({
        'players': {
            'filterStatsForSourceIds': {'value': [1]},
            'filterStatsForSplitTypeIds': {'value': [0]},
        }
    }),
    'User-Agent': 'Mozilla/5.0',
}

# ESPN numeric stat IDs → our field names
_STAT_MAP = {
    '3':  'pass_yards',
    '4':  'pass_tds',
    '20': 'interceptions',
    '24': 'rush_yards',
    '25': 'rush_tds',
    '41': 'receptions',
    '42': 'rec_yards',
    '43': 'rec_tds',
}


def _ppr(row: dict) -> float:
    return (
        row.get('pass_yards', 0.0)      * 0.04
        + row.get('pass_tds', 0.0)      * 4.0
        + row.get('interceptions', 0.0) * -2.0
        + row.get('rush_yards', 0.0)    * 0.1
        + row.get('rush_tds', 0.0)      * 6.0
        + row.get('receptions', 0.0)    * 1.0
        + row.get('rec_yards', 0.0)     * 0.1
        + row.get('rec_tds', 0.0)       * 6.0
    )


def parse_espn_response(data: dict) -> list[dict]:
    """Extract projected stats from ESPN API JSON.

    Only includes players that have a statSourceId=1 (projected) entry.
    Returns list of dicts with espn_id (str) and stat fields.
    """
    rows = []
    for player_entry in data.get('players', []):
        espn_id = str(player_entry.get('id', ''))
        player = player_entry.get('playerPoolEntry', {}).get('player', {})
        stats_list = player.get('stats', [])
        # Find the projected full-season stat entry
        proj_stats = next(
            (s for s in stats_list
             if s.get('statSourceId') == 1 and s.get('scoringPeriodId') == 0),
            None,
        )
        if proj_stats is None:
            continue
        raw_stats = proj_stats.get('stats', {})
        row: dict = {'espn_id': espn_id}
        for stat_id, field in _STAT_MAP.items():
            row[field] = float(raw_stats.get(stat_id, 0.0))
        row['points'] = _ppr(row)
        rows.append(row)
    return rows


def ingest_espn(conn, season: int) -> dict:
    """Fetch ESPN projections and upsert to consensus_projections (source='espn')."""
    print('Fetching ESPN projections...', flush=True)
    url = _ESPN_URL.format(season=season)
    resp = requests.get(url, headers=_ESPN_HEADERS, timeout=60)
    resp.raise_for_status()
    data = resp.json()

    rows = parse_espn_response(data)
    print(f'  Parsed {len(rows)} players with projected stats.', flush=True)

    # Build espn_id → gsis_id map from players table
    espn_to_gsis = {
        str(espn_id): gsis_id
        for gsis_id, espn_id in conn.execute(
            "SELECT gsis_id, espn_id FROM players WHERE espn_id IS NOT NULL"
        ).fetchall()
    }

    matched = 0
    unmatched = 0
    rows_to_upsert = []
    for row in rows:
        gsis_id = espn_to_gsis.get(row['espn_id'])
        if gsis_id is None:
            print(f'UNMATCHED ESPN ID: {row["espn_id"]}', file=sys.stderr)
            unmatched += 1
            continue
        rows_to_upsert.append((
            gsis_id, season, 'espn',
            row.get('pass_yards'),
            row.get('pass_tds'),
            row.get('interceptions'),
            row.get('rush_yards'),
            row.get('rush_tds'),
            row.get('receptions'),
            row.get('rec_yards'),
            row.get('rec_tds'),
            row['points'],
        ))
        matched += 1

    conn.executemany("""
        INSERT INTO consensus_projections
            (gsis_id, season, source,
             pass_yards, pass_tds, interceptions,
             rush_yards, rush_tds,
             receptions, rec_yards, rec_tds,
             points)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (gsis_id, season, source) DO UPDATE SET
            pass_yards    = excluded.pass_yards,
            pass_tds      = excluded.pass_tds,
            interceptions = excluded.interceptions,
            rush_yards    = excluded.rush_yards,
            rush_tds      = excluded.rush_tds,
            receptions    = excluded.receptions,
            rec_yards     = excluded.rec_yards,
            rec_tds       = excluded.rec_tds,
            points        = excluded.points,
            scraped_at    = current_timestamp
    """, rows_to_upsert)
    conn.commit()
    print(f'  Upserted {matched} ESPN rows ({unmatched} unmatched).', flush=True)
    return {'matched': matched, 'unmatched': unmatched}


def main() -> None:
    p = argparse.ArgumentParser(description='Ingest ESPN consensus projections')
    p.add_argument('--season', type=int, default=2026)
    args = p.parse_args()

    conn = get_conn()
    init_schema(conn)
    result = ingest_espn(conn, args.season)
    conn.close()
    print(f"\nDone. matched={result['matched']}, unmatched={result['unmatched']}")


if __name__ == '__main__':
    main()
```

- [ ] **Step 5: Run ESPN tests to verify they pass**

```
uv run pytest tests/projections/test_espn_scrape.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 6: Run full suite**

```
uv run pytest tests/ -v
```

Expected: all previously passing tests still PASS.

- [ ] **Step 7: Commit**

```bash
git add scripts/ingest_espn_projections.py \
        tests/projections/test_espn_scrape.py \
        tests/projections/fixtures/espn_players.json
git commit -m "feat: ESPN projections scraper using espn_id direct match"
```

---

## End-to-End Smoke Test (manual, no CI)

After all tasks complete, verify the full pipeline works against the live database:

```bash
# Run ESPN ingestion first (optional — only if espn_id populated in players table)
uv run python scripts/ingest_espn_projections.py --season 2026

# Full consensus refresh: scrape FP → match → blend → VOR
uv run python scripts/ingest_fantasypros.py --season 2026
```

Verify rankings improved:
```bash
# Check top-10 rankings via API
curl -s http://127.0.0.1:8000/api/rankings?season=2026&limit=10 | python -m json.tool
```

Expected: Rashee Rice, Omarion Hampton, Kyren Williams appear near their ADP rank (not 100+ places off).
