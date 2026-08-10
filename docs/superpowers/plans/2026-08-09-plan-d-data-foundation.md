# Data Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the complete data foundation — Python project structure, DuckDB schema, all ingestion scripts (NFLFastR, nfl-data-py, Sleeper, ESPN, FantasyPros), player ID unification, and a CLI pipeline script that populates `data/ff.duckdb` with 2005–2025 NFL data.

**Architecture:** Modular Python package (`src/tay/`) with strict schema boundaries. Each ingestion module writes to DuckDB exclusively through typed schemas. NFLFastR data is pulled via R script and loaded into DuckDB via pyarrow. Player IDs are unified across sources before any downstream use.

**Tech Stack:** Python 3.12 (miniforge), DuckDB 1.x, R 4.4 + nflfastR + nflreadr + arrow, nfl-data-py, pandas, pyarrow, requests, beautifulsoup4

## Global Constraints

- Python interpreter: `/Users/theoauyeung/miniforge3/bin/python3.12`
- R interpreter: `/usr/local/bin/Rscript` (or wherever `which Rscript` resolves)
- All data stored in `data/ff.duckdb` (single DuckDB file)
- Raw downloaded files cached in `data/raw/` — never re-downloaded if already present
- All tables include a `created_at TIMESTAMP DEFAULT current_timestamp` column
- No future information ever enters a training row — every table has a `season` column for filtering
- `players.gsis_id` is the canonical player ID used by all downstream modules
- Free data sources only: NFLFastR, nfl-data-py, Sleeper API (free), ESPN unofficial API, FantasyPros (free tier scrape)
- Scraping: respect rate limits — 1-second delay between PFR requests
- TDD: tests go in `tests/`, run with `pytest`
- Commits after each task

---

## File Map

```
TAY Analytics FF/
├── src/
│   └── tay/
│       ├── __init__.py
│       ├── db.py                          — DuckDB connection manager
│       ├── schemas/
│       │   ├── __init__.py
│       │   └── tables.py                  — SQL CREATE TABLE statements as constants
│       └── ingestion/
│           ├── __init__.py
│           ├── nflfastr.py                — calls R script, loads parquet → DuckDB
│           ├── nfl_data_py_ingest.py      — rosters, schedules, injuries, draft picks
│           ├── player_ids.py              — cross-source ID unification
│           ├── aggregate_stats.py         — PBP → player_season_stats, team_season_stats
│           ├── sleeper.py                 — Sleeper API: player metadata + ADP
│           ├── espn.py                    — ESPN unofficial API: ADP
│           └── fantasypros.py             — FantasyPros: consensus rankings + ADP
├── scripts/
│   ├── pull_pbp.R                         — NFLFastR R script
│   └── ingest.py                          — CLI: runs full ingestion pipeline
├── data/
│   ├── raw/                               — cached downloaded files (git-ignored)
│   └── ff.duckdb                          — single DuckDB file (git-ignored)
├── tests/
│   ├── test_db.py
│   ├── test_player_ids.py
│   └── test_aggregate_stats.py
├── pyproject.toml
├── requirements.txt
└── Makefile
```

---

### Task 1: Python project setup

**Files:**
- Create: `pyproject.toml`
- Create: `requirements.txt`
- Create: `src/tay/__init__.py`
- Create: `src/tay/ingestion/__init__.py`
- Create: `src/tay/schemas/__init__.py`
- Create: `Makefile`
- Create: `.gitignore` additions
- Create: `data/raw/.gitkeep`

**Interfaces:**
- Produces: installable `tay` package, `python -m tay` entry point available

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "tay"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "duckdb>=1.1",
    "pandas>=2.2",
    "pyarrow>=17",
    "nfl-data-py>=0.3",
    "requests>=2.32",
    "beautifulsoup4>=4.12",
    "lxml>=5.2",
    "tqdm>=4.66",
    "rich>=13",
    "python-dotenv>=1.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8",
    "pytest-cov>=5",
]

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Create `requirements.txt`** (pip-freeze friendly reference)

```
duckdb>=1.1
pandas>=2.2
pyarrow>=17
nfl-data-py>=0.3
requests>=2.32
beautifulsoup4>=4.12
lxml>=5.2
tqdm>=4.66
rich>=13
python-dotenv>=1.0
pytest>=8
pytest-cov>=5
```

- [ ] **Step 3: Install the package**

```bash
cd "/Users/theoauyeung/Documents/Projects/TAY Analytics FF"
/Users/theoauyeung/miniforge3/bin/pip install -e ".[dev]"
```

Expected: successful install, `tay` package importable.

- [ ] **Step 4: Create `src/tay/__init__.py`**

```python
"""TAY Analytics FF — fantasy football analytics engine."""
__version__ = "0.1.0"
```

- [ ] **Step 5: Create `src/tay/ingestion/__init__.py` and `src/tay/schemas/__init__.py`**

Both empty files.

- [ ] **Step 6: Create `data/raw/.gitkeep`**

```bash
mkdir -p "/Users/theoauyeung/Documents/Projects/TAY Analytics FF/data/raw"
touch "/Users/theoauyeung/Documents/Projects/TAY Analytics FF/data/raw/.gitkeep"
```

- [ ] **Step 7: Create `Makefile`**

```makefile
PYTHON := /Users/theoauyeung/miniforge3/bin/python3.12
RSCRIPT := $(shell which Rscript)

.PHONY: install ingest test clean

install:
	$(PYTHON) -m pip install -e ".[dev]"

ingest:
	$(PYTHON) scripts/ingest.py

test:
	$(PYTHON) -m pytest tests/ -v

clean:
	rm -f data/ff.duckdb
```

- [ ] **Step 8: Add to `.gitignore`**

Append to root `.gitignore` (create if absent):
```
data/raw/
data/ff.duckdb
data/*.parquet
__pycache__/
*.pyc
.pytest_cache/
*.egg-info/
dist/
.env
```

- [ ] **Step 9: Write a smoke test**

Create `tests/test_import.py`:
```python
def test_package_importable():
    import tay
    assert tay.__version__ == "0.1.0"
```

- [ ] **Step 10: Run the test**

```bash
cd "/Users/theoauyeung/Documents/Projects/TAY Analytics FF"
/Users/theoauyeung/miniforge3/bin/python3.12 -m pytest tests/test_import.py -v
```

Expected: `PASSED`

- [ ] **Step 11: Commit**

```bash
git add pyproject.toml requirements.txt src/ tests/test_import.py Makefile data/raw/.gitkeep .gitignore
git commit -m "feat: bootstrap Python project structure for backend"
```

---

### Task 2: DuckDB schema

**Files:**
- Create: `src/tay/schemas/tables.py`
- Create: `src/tay/db.py`
- Create: `tests/test_db.py`

**Interfaces:**
- Produces (consumed by all ingestion tasks):
  - `get_conn(db_path: str = "data/ff.duckdb") -> duckdb.DuckDBPyConnection`
  - `init_schema(conn) -> None` — creates all tables if not exist

- [ ] **Step 1: Create `src/tay/schemas/tables.py`**

```python
"""SQL CREATE TABLE statements — single source of truth for the DuckDB schema."""

PLAYERS = """
CREATE TABLE IF NOT EXISTS players (
    gsis_id         VARCHAR PRIMARY KEY,
    name            VARCHAR NOT NULL,
    position        VARCHAR,
    team            VARCHAR,
    birth_date      DATE,
    draft_year      INTEGER,
    draft_round     INTEGER,
    draft_pick      INTEGER,
    college         VARCHAR,
    height          INTEGER,
    weight          INTEGER,
    -- Cross-source IDs
    sleeper_id      VARCHAR,
    espn_id         VARCHAR,
    pfr_id          VARCHAR,
    yahoo_id        VARCHAR,
    created_at      TIMESTAMP DEFAULT current_timestamp
)
"""

PLAY_BY_PLAY = """
CREATE TABLE IF NOT EXISTS play_by_play (
    play_id         VARCHAR,
    game_id         VARCHAR,
    season          INTEGER NOT NULL,
    week            INTEGER,
    season_type     VARCHAR,
    posteam         VARCHAR,
    defteam         VARCHAR,
    play_type       VARCHAR,
    yards_gained    DOUBLE,
    passer_id       VARCHAR,
    rusher_id       VARCHAR,
    receiver_id     VARCHAR,
    air_yards       DOUBLE,
    yards_after_catch DOUBLE,
    pass_attempt    INTEGER,
    rush_attempt    INTEGER,
    complete_pass   INTEGER,
    touchdown       INTEGER,
    interception    INTEGER,
    fumble          INTEGER,
    epa             DOUBLE,
    cpoe            DOUBLE,
    wpa             DOUBLE,
    created_at      TIMESTAMP DEFAULT current_timestamp,
    PRIMARY KEY (play_id, season)
)
"""

PLAYER_SEASON_STATS = """
CREATE TABLE IF NOT EXISTS player_season_stats (
    gsis_id             VARCHAR NOT NULL,
    season              INTEGER NOT NULL,
    team                VARCHAR,
    games               INTEGER,
    -- Passing
    attempts            INTEGER DEFAULT 0,
    completions         INTEGER DEFAULT 0,
    pass_yards          DOUBLE DEFAULT 0,
    pass_tds            INTEGER DEFAULT 0,
    interceptions       INTEGER DEFAULT 0,
    -- Rushing
    carries             INTEGER DEFAULT 0,
    rush_yards          DOUBLE DEFAULT 0,
    rush_tds            INTEGER DEFAULT 0,
    -- Receiving
    targets             INTEGER DEFAULT 0,
    receptions          INTEGER DEFAULT 0,
    rec_yards           DOUBLE DEFAULT 0,
    rec_tds             INTEGER DEFAULT 0,
    -- Advanced
    air_yards           DOUBLE DEFAULT 0,
    yards_after_catch   DOUBLE DEFAULT 0,
    epa_per_play        DOUBLE,
    cpoe                DOUBLE,
    -- Fantasy points
    fantasy_points_ppr  DOUBLE DEFAULT 0,
    fantasy_points_hppr DOUBLE DEFAULT 0,
    fantasy_points_std  DOUBLE DEFAULT 0,
    created_at          TIMESTAMP DEFAULT current_timestamp,
    PRIMARY KEY (gsis_id, season)
)
"""

TEAM_SEASON_STATS = """
CREATE TABLE IF NOT EXISTS team_season_stats (
    team                VARCHAR NOT NULL,
    season              INTEGER NOT NULL,
    games               INTEGER,
    -- Volume
    total_plays         INTEGER DEFAULT 0,
    pass_attempts       INTEGER DEFAULT 0,
    rush_attempts       INTEGER DEFAULT 0,
    pass_rate           DOUBLE,
    -- Scoring
    total_tds           INTEGER DEFAULT 0,
    pass_tds            INTEGER DEFAULT 0,
    rush_tds            INTEGER DEFAULT 0,
    points_scored       DOUBLE DEFAULT 0,
    -- Efficiency
    team_epa            DOUBLE,
    pass_epa            DOUBLE,
    rush_epa            DOUBLE,
    created_at          TIMESTAMP DEFAULT current_timestamp,
    PRIMARY KEY (team, season)
)
"""

ROSTERS = """
CREATE TABLE IF NOT EXISTS rosters (
    gsis_id         VARCHAR NOT NULL,
    season          INTEGER NOT NULL,
    week            INTEGER NOT NULL,
    team            VARCHAR,
    position        VARCHAR,
    depth_chart_pos INTEGER,
    status          VARCHAR,
    created_at      TIMESTAMP DEFAULT current_timestamp,
    PRIMARY KEY (gsis_id, season, week)
)
"""

DRAFT_PICKS = """
CREATE TABLE IF NOT EXISTS draft_picks (
    gsis_id         VARCHAR,
    season          INTEGER NOT NULL,
    round           INTEGER,
    pick            INTEGER,
    overall_pick    INTEGER,
    team            VARCHAR,
    position        VARCHAR,
    college         VARCHAR,
    created_at      TIMESTAMP DEFAULT current_timestamp,
    PRIMARY KEY (season, overall_pick)
)
"""

COMBINE_DATA = """
CREATE TABLE IF NOT EXISTS combine_data (
    gsis_id         VARCHAR,
    pfr_id          VARCHAR,
    name            VARCHAR,
    season          INTEGER NOT NULL,
    position        VARCHAR,
    forty_yard      DOUBLE,
    vertical        DOUBLE,
    broad_jump      DOUBLE,
    cone            DOUBLE,
    shuttle         DOUBLE,
    bench_reps      INTEGER,
    height          INTEGER,
    weight          INTEGER,
    created_at      TIMESTAMP DEFAULT current_timestamp,
    PRIMARY KEY (season, pfr_id)
)
"""

ADP = """
CREATE TABLE IF NOT EXISTS adp (
    gsis_id         VARCHAR,
    season          INTEGER NOT NULL,
    platform        VARCHAR NOT NULL,
    format          VARCHAR NOT NULL,
    adp             DOUBLE,
    rank            INTEGER,
    fetched_at      TIMESTAMP,
    created_at      TIMESTAMP DEFAULT current_timestamp,
    PRIMARY KEY (season, platform, format, gsis_id)
)
"""

PROJECTIONS = """
CREATE TABLE IF NOT EXISTS projections (
    gsis_id             VARCHAR NOT NULL,
    season              INTEGER NOT NULL,
    model_version       VARCHAR,
    mean_projection     DOUBLE,
    median_projection   DOUBLE,
    floor               DOUBLE,
    ceiling             DOUBLE,
    std_dev             DOUBLE,
    p10                 DOUBLE,
    p25                 DOUBLE,
    p50                 DOUBLE,
    p75                 DOUBLE,
    p90                 DOUBLE,
    boom_probability    DOUBLE,
    bust_probability    DOUBLE,
    vor                 DOUBLE,
    vor_rank            INTEGER,
    adp_delta           DOUBLE,
    tier                INTEGER,
    created_at          TIMESTAMP DEFAULT current_timestamp,
    PRIMARY KEY (gsis_id, season, model_version)
)
"""

DRAFT_SESSIONS = """
CREATE TABLE IF NOT EXISTS draft_sessions (
    session_id      VARCHAR PRIMARY KEY,
    created_at      TIMESTAMP DEFAULT current_timestamp,
    league_settings JSON,
    picks           JSON,
    completed       BOOLEAN DEFAULT FALSE
)
"""

ALL_TABLES = [
    PLAYERS, PLAY_BY_PLAY, PLAYER_SEASON_STATS, TEAM_SEASON_STATS,
    ROSTERS, DRAFT_PICKS, COMBINE_DATA, ADP, PROJECTIONS, DRAFT_SESSIONS,
]
```

- [ ] **Step 2: Create `src/tay/db.py`**

```python
"""DuckDB connection manager."""
from pathlib import Path
import duckdb
from tay.schemas.tables import ALL_TABLES

DB_PATH = Path(__file__).parent.parent.parent / "data" / "ff.duckdb"


def get_conn(db_path: str | Path = DB_PATH) -> duckdb.DuckDBPyConnection:
    """Return a DuckDB connection. Creates the file if absent."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(path))


def init_schema(conn: duckdb.DuckDBPyConnection) -> None:
    """Create all tables if they do not exist."""
    for ddl in ALL_TABLES:
        conn.execute(ddl)
    conn.commit()
```

- [ ] **Step 3: Write failing test**

Create `tests/test_db.py`:
```python
import duckdb
import pytest
from pathlib import Path
from tay.db import get_conn, init_schema

@pytest.fixture
def conn(tmp_path):
    c = get_conn(tmp_path / "test.duckdb")
    yield c
    c.close()

def test_init_schema_creates_all_tables(conn):
    init_schema(conn)
    tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
    expected = {
        "players", "play_by_play", "player_season_stats", "team_season_stats",
        "rosters", "draft_picks", "combine_data", "adp", "projections", "draft_sessions",
    }
    assert expected.issubset(tables)

def test_init_schema_is_idempotent(conn):
    init_schema(conn)
    init_schema(conn)  # second call must not raise
    tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
    assert "players" in tables
```

- [ ] **Step 4: Run test — expect FAIL**

```bash
cd "/Users/theoauyeung/Documents/Projects/TAY Analytics FF"
/Users/theoauyeung/miniforge3/bin/python3.12 -m pytest tests/test_db.py -v
```

Expected: FAIL (tay.db not yet implemented with correct content, or PASSED if Step 2 already done).

- [ ] **Step 5: Run test — expect PASS after implementation**

```bash
/Users/theoauyeung/miniforge3/bin/python3.12 -m pytest tests/test_db.py -v
```

Expected: 2 PASSED

- [ ] **Step 6: Commit**

```bash
git add src/tay/schemas/tables.py src/tay/db.py tests/test_db.py
git commit -m "feat: DuckDB schema — 10 tables with typed columns and primary keys"
```

---

### Task 3: NFLFastR play-by-play ingestion

**Files:**
- Create: `scripts/pull_pbp.R`
- Create: `src/tay/ingestion/nflfastr.py`

**Interfaces:**
- Produces: `play_by_play` table in DuckDB, `data/raw/pbp_{season}.parquet` cached files
- Consumes: `get_conn`, `init_schema` from `tay.db`

**Note:** nflfastR PBP for 2005–2025 is ~8GB of data. The R script downloads from the nflfastR CDN (S3 bucket) which is fast. The parquet files are cached locally so re-runs skip already-downloaded seasons.

- [ ] **Step 1: Create `scripts/pull_pbp.R`**

```r
#!/usr/bin/env Rscript
# Pull NFLFastR play-by-play data and write per-season parquet files
# Usage: Rscript scripts/pull_pbp.R [start_season] [end_season]
# Default: 2005 to 2025

library(nflfastR)
library(nflreadr)
library(arrow)

args <- commandArgs(trailingOnly = TRUE)
start_season <- if (length(args) >= 1) as.integer(args[1]) else 2005
end_season   <- if (length(args) >= 2) as.integer(args[2]) else 2025

raw_dir <- file.path(dirname(dirname(sys.frame(1)$ofile)), "data", "raw")
if (!dir.exists(raw_dir)) dir.create(raw_dir, recursive = TRUE)

cat(sprintf("Pulling NFLFastR PBP %d-%d\n", start_season, end_season))

for (season in start_season:end_season) {
  out_path <- file.path(raw_dir, sprintf("pbp_%d.parquet", season))
  if (file.exists(out_path)) {
    cat(sprintf("  Season %d: already cached, skipping\n", season))
    next
  }
  cat(sprintf("  Season %d: downloading...\n", season))
  pbp <- tryCatch(
    load_pbp(seasons = season),
    error = function(e) { cat(sprintf("  ERROR: %s\n", e$message)); NULL }
  )
  if (!is.null(pbp)) {
    write_parquet(pbp, out_path)
    cat(sprintf("  Season %d: written to %s\n", season, out_path))
  }
}

cat("Done.\n")
```

- [ ] **Step 2: Create `src/tay/ingestion/nflfastr.py`**

```python
"""Load NFLFastR play-by-play parquet files into DuckDB."""
from __future__ import annotations
import subprocess
import sys
from pathlib import Path
import duckdb

from tay.db import get_conn, init_schema

RAW_DIR = Path(__file__).parent.parent.parent.parent / "data" / "raw"
SCRIPTS_DIR = Path(__file__).parent.parent.parent.parent / "scripts"

# Columns we care about — PBP is ~400 columns; we keep only what models need
KEEP_COLS = [
    "play_id", "game_id", "season", "week", "season_type",
    "posteam", "defteam", "play_type",
    "yards_gained", "passer_player_id", "rusher_player_id", "receiver_player_id",
    "air_yards", "yards_after_catch", "pass_attempt", "rush_attempt",
    "complete_pass", "touchdown", "interception", "fumble",
    "epa", "cpoe", "wpa",
]

# Rename nflfastR column names → our schema names
RENAME = {
    "passer_player_id": "passer_id",
    "rusher_player_id": "rusher_id",
    "receiver_player_id": "receiver_id",
}


def pull_pbp(start: int = 2005, end: int = 2025, rscript: str = "Rscript") -> None:
    """Run the R script to download PBP parquet files."""
    script = SCRIPTS_DIR / "pull_pbp.R"
    result = subprocess.run(
        [rscript, str(script), str(start), str(end)],
        capture_output=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"R script failed with code {result.returncode}")


def load_pbp_to_duckdb(
    conn: duckdb.DuckDBPyConnection,
    start: int = 2005,
    end: int = 2025,
) -> int:
    """Load cached PBP parquet files into play_by_play table. Returns rows inserted."""
    total = 0
    for season in range(start, end + 1):
        path = RAW_DIR / f"pbp_{season}.parquet"
        if not path.exists():
            print(f"  Season {season}: parquet not found, skipping")
            continue

        col_list = ", ".join(
            f'"{c}" AS "{RENAME.get(c, c)}"' for c in KEEP_COLS
        )
        conn.execute(f"""
            INSERT OR REPLACE INTO play_by_play
            SELECT {col_list}
            FROM read_parquet('{path}')
            WHERE play_type IS NOT NULL
        """)
        rows = conn.execute(
            "SELECT COUNT(*) FROM play_by_play WHERE season = ?", [season]
        ).fetchone()[0]
        print(f"  Season {season}: {rows:,} plays loaded")
        total += rows

    conn.commit()
    return total


def ingest(
    start: int = 2005,
    end: int = 2025,
    skip_download: bool = False,
    db_path: str | Path | None = None,
) -> None:
    """Full NFLFastR ingestion: download (unless skip_download) then load to DuckDB."""
    conn = get_conn(db_path) if db_path else get_conn()
    init_schema(conn)

    if not skip_download:
        print("Pulling NFLFastR PBP via R...")
        pull_pbp(start, end)

    print("Loading PBP parquet files into DuckDB...")
    total = load_pbp_to_duckdb(conn, start, end)
    print(f"NFLFastR ingestion complete: {total:,} total plays")
    conn.close()


if __name__ == "__main__":
    ingest()
```

- [ ] **Step 3: Smoke test (manual — requires download)**

Because the PBP download takes ~15 minutes, we test only with a single recent season and the `skip_download` path:

```bash
# First pull just 2024 to verify the R script works
Rscript scripts/pull_pbp.R 2024 2024

# Verify parquet created
ls data/raw/pbp_2024.parquet

# Load it into DuckDB
/Users/theoauyeung/miniforge3/bin/python3.12 -c "
from tay.ingestion.nflfastr import ingest
ingest(start=2024, end=2024, skip_download=True)
"
```

Expected: parquet file exists, `play_by_play` table has ~50,000+ rows for 2024.

- [ ] **Step 4: Commit**

```bash
git add scripts/pull_pbp.R src/tay/ingestion/nflfastr.py
git commit -m "feat: NFLFastR PBP ingestion — R download script and DuckDB loader"
```

---

### Task 4: nfl-data-py ingestion (rosters, schedules, injuries, draft picks)

**Files:**
- Create: `src/tay/ingestion/nfl_data_py_ingest.py`

**Interfaces:**
- Produces: `players` table (initial population), `rosters` table, `draft_picks` table
- Consumes: `get_conn`, `init_schema`

- [ ] **Step 1: Write failing test**

Create `tests/test_nfl_data_py.py`:
```python
import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
from tay.db import get_conn, init_schema

def test_roster_columns_present(tmp_path):
    """Verify we can insert a mock roster row into the rosters table."""
    conn = get_conn(tmp_path / "test.duckdb")
    init_schema(conn)
    conn.execute("""
        INSERT INTO rosters (gsis_id, season, week, team, position, depth_chart_pos, status)
        VALUES ('test-id-1', 2024, 1, 'KC', 'QB', 1, 'Active')
    """)
    row = conn.execute("SELECT gsis_id FROM rosters WHERE season=2024").fetchone()
    assert row[0] == 'test-id-1'
    conn.close()
```

Run: expected PASS (just tests schema, not the ingest function).

- [ ] **Step 2: Create `src/tay/ingestion/nfl_data_py_ingest.py`**

```python
"""Ingest NFL data using nfl-data-py: players, rosters, draft picks."""
from __future__ import annotations
from pathlib import Path
import duckdb
import nfl_data_py as nfl
import pandas as pd

from tay.db import get_conn, init_schema


def _safe_str(val) -> str | None:
    return str(val) if pd.notna(val) else None


def _safe_int(val) -> int | None:
    try:
        return int(val) if pd.notna(val) else None
    except (ValueError, TypeError):
        return None


def ingest_players(conn: duckdb.DuckDBPyConnection, seasons: list[int]) -> int:
    """Load player roster data into the players table."""
    print("Fetching player roster data...")
    df = nfl.import_rosters(years=seasons, columns=[
        "player_id", "player_name", "position", "team",
        "birth_date", "draft_year", "draft_round", "draft_pick",
        "college", "height", "weight", "espn_id",
    ])
    df = df.drop_duplicates(subset=["player_id"]).dropna(subset=["player_id"])

    inserted = 0
    for _, row in df.iterrows():
        conn.execute("""
            INSERT OR REPLACE INTO players
                (gsis_id, name, position, team, birth_date, draft_year,
                 draft_round, draft_pick, college, height, weight, espn_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            _safe_str(row.get("player_id")),
            _safe_str(row.get("player_name")),
            _safe_str(row.get("position")),
            _safe_str(row.get("team")),
            _safe_str(row.get("birth_date")),
            _safe_int(row.get("draft_year")),
            _safe_int(row.get("draft_round")),
            _safe_int(row.get("draft_pick")),
            _safe_str(row.get("college")),
            _safe_int(row.get("height")),
            _safe_int(row.get("weight")),
            _safe_str(row.get("espn_id")),
        ])
        inserted += 1

    conn.commit()
    return inserted


def ingest_rosters(conn: duckdb.DuckDBPyConnection, seasons: list[int]) -> int:
    """Load weekly depth chart / roster data."""
    print("Fetching weekly rosters...")
    df = nfl.import_weekly_rosters(years=seasons)

    inserted = 0
    for _, row in df.iterrows():
        gsis_id = _safe_str(row.get("player_id"))
        season = _safe_int(row.get("season"))
        week = _safe_int(row.get("week"))
        if not all([gsis_id, season, week]):
            continue
        conn.execute("""
            INSERT OR REPLACE INTO rosters (gsis_id, season, week, team, position, depth_chart_pos, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, [
            gsis_id, season, week,
            _safe_str(row.get("team")),
            _safe_str(row.get("position")),
            _safe_int(row.get("depth_chart_position")),
            _safe_str(row.get("status")),
        ])
        inserted += 1

    conn.commit()
    return inserted


def ingest_draft_picks(conn: duckdb.DuckDBPyConnection, seasons: list[int]) -> int:
    """Load NFL draft pick data."""
    print("Fetching draft picks...")
    df = nfl.import_draft_picks(years=seasons)

    inserted = 0
    for _, row in df.iterrows():
        season = _safe_int(row.get("season"))
        overall = _safe_int(row.get("pick"))
        if not season or not overall:
            continue
        conn.execute("""
            INSERT OR REPLACE INTO draft_picks
                (gsis_id, season, round, pick, overall_pick, team, position, college)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            _safe_str(row.get("gsis_id")),
            season,
            _safe_int(row.get("round")),
            _safe_int(row.get("pick_no")),
            overall,
            _safe_str(row.get("team")),
            _safe_str(row.get("position")),
            _safe_str(row.get("pfr_player_name")),
        ])
        inserted += 1

    conn.commit()
    return inserted


def ingest(
    start: int = 2005,
    end: int = 2025,
    db_path: str | Path | None = None,
) -> None:
    """Run all nfl-data-py ingestion steps."""
    conn = get_conn(db_path) if db_path else get_conn()
    init_schema(conn)
    seasons = list(range(start, end + 1))

    n = ingest_players(conn, seasons)
    print(f"  Players: {n:,} rows")

    n = ingest_rosters(conn, seasons)
    print(f"  Rosters: {n:,} rows")

    n = ingest_draft_picks(conn, seasons)
    print(f"  Draft picks: {n:,} rows")

    conn.close()
    print("nfl-data-py ingestion complete.")


if __name__ == "__main__":
    ingest()
```

- [ ] **Step 3: Run tests**

```bash
cd "/Users/theoauyeung/Documents/Projects/TAY Analytics FF"
/Users/theoauyeung/miniforge3/bin/python3.12 -m pytest tests/test_nfl_data_py.py -v
```

Expected: PASSED

- [ ] **Step 4: Smoke test (live)**

```bash
/Users/theoauyeung/miniforge3/bin/python3.12 -c "
from tay.ingestion.nfl_data_py_ingest import ingest
ingest(start=2024, end=2024)
"
```

Expected: players, rosters, draft_picks tables populated with 2024 data.

- [ ] **Step 5: Commit**

```bash
git add src/tay/ingestion/nfl_data_py_ingest.py tests/test_nfl_data_py.py
git commit -m "feat: nfl-data-py ingestion — players, rosters, draft picks"
```

---

### Task 5: Player season stats aggregation

**Files:**
- Create: `src/tay/ingestion/aggregate_stats.py`
- Create: `tests/test_aggregate_stats.py`

**Interfaces:**
- Consumes: `play_by_play` table (must be populated first)
- Produces: `player_season_stats` table, `team_season_stats` table

- [ ] **Step 1: Write failing tests**

Create `tests/test_aggregate_stats.py`:
```python
import pytest
import duckdb
from tay.db import get_conn, init_schema
from tay.ingestion.aggregate_stats import aggregate_player_stats, aggregate_team_stats

@pytest.fixture
def conn_with_pbp(tmp_path):
    conn = get_conn(tmp_path / "test.duckdb")
    init_schema(conn)
    # Insert minimal PBP rows
    conn.execute("""
        INSERT INTO play_by_play
            (play_id, game_id, season, week, season_type, posteam, defteam,
             play_type, yards_gained, passer_id, rusher_id, receiver_id,
             air_yards, yards_after_catch, pass_attempt, rush_attempt,
             complete_pass, touchdown, interception, fumble, epa, cpoe, wpa)
        VALUES
            ('p1', 'g1', 2024, 1, 'REG', 'KC', 'LV', 'pass', 15.0,
             'player-1', NULL, 'player-2', 10.0, 5.0,
             1, 0, 1, 1, 0, 0, 0.8, 5.0, 0.1),
            ('p2', 'g1', 2024, 1, 'REG', 'KC', 'LV', 'run', 5.0,
             NULL, 'player-3', NULL, NULL, NULL,
             0, 1, 0, 0, 0, 0, 0.2, NULL, 0.05)
    """)
    yield conn
    conn.close()

def test_aggregate_player_stats(conn_with_pbp):
    aggregate_player_stats(conn_with_pbp, seasons=[2024])
    rows = conn_with_pbp.execute(
        "SELECT gsis_id, season FROM player_season_stats WHERE season=2024"
    ).fetchall()
    gsis_ids = {r[0] for r in rows}
    assert 'player-1' in gsis_ids  # passer
    assert 'player-3' in gsis_ids  # rusher

def test_aggregate_team_stats(conn_with_pbp):
    aggregate_team_stats(conn_with_pbp, seasons=[2024])
    row = conn_with_pbp.execute(
        "SELECT total_plays FROM team_season_stats WHERE team='KC' AND season=2024"
    ).fetchone()
    assert row is not None
    assert row[0] == 2
```

- [ ] **Step 2: Run — expect FAIL**

```bash
/Users/theoauyeung/miniforge3/bin/python3.12 -m pytest tests/test_aggregate_stats.py -v
```

Expected: FAIL (ImportError — module not yet created)

- [ ] **Step 3: Create `src/tay/ingestion/aggregate_stats.py`**

```python
"""Aggregate play-by-play data into per-player and per-team season stats."""
from __future__ import annotations
from pathlib import Path
import duckdb

from tay.db import get_conn, init_schema


def aggregate_player_stats(
    conn: duckdb.DuckDBPyConnection,
    seasons: list[int],
) -> None:
    """Aggregate PBP into player_season_stats. Overwrites existing rows for given seasons."""
    for season in seasons:
        conn.execute("DELETE FROM player_season_stats WHERE season = ?", [season])
        conn.execute("""
            INSERT INTO player_season_stats (
                gsis_id, season, team, games,
                attempts, completions, pass_yards, pass_tds, interceptions,
                carries, rush_yards, rush_tds,
                targets, receptions, rec_yards, rec_tds,
                air_yards, yards_after_catch, epa_per_play, cpoe,
                fantasy_points_ppr, fantasy_points_hppr, fantasy_points_std
            )
            WITH all_players AS (
                -- Passers
                SELECT passer_id AS gsis_id, posteam AS team, season,
                    SUM(pass_attempt)    AS attempts,
                    SUM(complete_pass)   AS completions,
                    SUM(CASE WHEN complete_pass=1 THEN yards_gained ELSE 0 END) AS pass_yards,
                    SUM(CASE WHEN play_type='pass' AND touchdown=1 THEN 1 ELSE 0 END) AS pass_tds,
                    SUM(interception)    AS interceptions,
                    0 AS carries, 0 AS rush_yards, 0 AS rush_tds,
                    0 AS targets, 0 AS receptions, 0 AS rec_yards, 0 AS rec_tds,
                    SUM(COALESCE(air_yards, 0)) AS air_yds,
                    0 AS yac,
                    AVG(epa) AS epa_pp,
                    AVG(cpoe) AS avg_cpoe
                FROM play_by_play
                WHERE season = ? AND season_type = 'REG'
                  AND passer_id IS NOT NULL AND play_type = 'pass'
                GROUP BY passer_id, posteam, season

                UNION ALL

                -- Rushers
                SELECT rusher_id, posteam, season,
                    0, 0, 0, 0, 0,
                    SUM(rush_attempt), SUM(yards_gained),
                    SUM(CASE WHEN play_type='run' AND touchdown=1 THEN 1 ELSE 0 END),
                    0, 0, 0, 0, 0, 0, AVG(epa), NULL
                FROM play_by_play
                WHERE season = ? AND season_type = 'REG'
                  AND rusher_id IS NOT NULL AND play_type = 'run'
                GROUP BY rusher_id, posteam, season

                UNION ALL

                -- Receivers
                SELECT receiver_id, posteam, season,
                    0, 0, 0, 0, 0, 0, 0, 0,
                    COUNT(*) AS targets,
                    SUM(complete_pass) AS receptions,
                    SUM(CASE WHEN complete_pass=1 THEN yards_gained ELSE 0 END),
                    SUM(CASE WHEN play_type='pass' AND touchdown=1 AND complete_pass=1 THEN 1 ELSE 0 END),
                    SUM(COALESCE(air_yards, 0)),
                    SUM(COALESCE(yards_after_catch, 0)),
                    AVG(epa), NULL
                FROM play_by_play
                WHERE season = ? AND season_type = 'REG'
                  AND receiver_id IS NOT NULL
                GROUP BY receiver_id, posteam, season
            ),
            agg AS (
                SELECT gsis_id, season, team,
                    COUNT(DISTINCT team) AS games,  -- approximation; real game count needs join
                    SUM(attempts)     AS attempts,
                    SUM(completions)  AS completions,
                    SUM(pass_yards)   AS pass_yards,
                    SUM(pass_tds)     AS pass_tds,
                    SUM(interceptions) AS interceptions,
                    SUM(carries)      AS carries,
                    SUM(rush_yards)   AS rush_yards,
                    SUM(rush_tds)     AS rush_tds,
                    SUM(targets)      AS targets,
                    SUM(receptions)   AS receptions,
                    SUM(rec_yards)    AS rec_yards,
                    SUM(rec_tds)      AS rec_tds,
                    SUM(air_yds)      AS air_yards,
                    SUM(yac)          AS yards_after_catch,
                    AVG(epa_pp)       AS epa_per_play,
                    AVG(avg_cpoe)     AS cpoe
                FROM all_players
                WHERE gsis_id IS NOT NULL
                GROUP BY gsis_id, season, team
            )
            SELECT
                gsis_id, season, team, 17 AS games,
                attempts, completions, pass_yards, pass_tds, interceptions,
                carries, rush_yards, rush_tds,
                targets, receptions, rec_yards, rec_tds,
                air_yards, yards_after_catch, epa_per_play, cpoe,
                -- PPR: 1pt/rec + 0.1pt/yard + 6pt/TD (pass: 0.04pt/yard, 6pt/TD, -2pt/INT)
                (pass_yards * 0.04 + pass_tds * 6 - interceptions * 2
                 + rush_yards * 0.1 + rush_tds * 6
                 + receptions * 1 + rec_yards * 0.1 + rec_tds * 6) AS fantasy_points_ppr,
                (pass_yards * 0.04 + pass_tds * 6 - interceptions * 2
                 + rush_yards * 0.1 + rush_tds * 6
                 + receptions * 0.5 + rec_yards * 0.1 + rec_tds * 6) AS fantasy_points_hppr,
                (pass_yards * 0.04 + pass_tds * 6 - interceptions * 2
                 + rush_yards * 0.1 + rush_tds * 6
                 + rec_yards * 0.1 + rec_tds * 6) AS fantasy_points_std
            FROM agg
        """, [season, season, season])

    conn.commit()


def aggregate_team_stats(
    conn: duckdb.DuckDBPyConnection,
    seasons: list[int],
) -> None:
    """Aggregate PBP into team_season_stats."""
    for season in seasons:
        conn.execute("DELETE FROM team_season_stats WHERE season = ?", [season])
        conn.execute("""
            INSERT INTO team_season_stats (
                team, season, games, total_plays, pass_attempts, rush_attempts,
                pass_rate, total_tds, pass_tds, rush_tds, points_scored,
                team_epa, pass_epa, rush_epa
            )
            SELECT
                posteam AS team,
                season,
                COUNT(DISTINCT game_id) AS games,
                COUNT(*) AS total_plays,
                SUM(pass_attempt) AS pass_attempts,
                SUM(rush_attempt) AS rush_attempts,
                AVG(pass_attempt) AS pass_rate,
                SUM(touchdown) AS total_tds,
                SUM(CASE WHEN play_type='pass' AND touchdown=1 THEN 1 ELSE 0 END) AS pass_tds,
                SUM(CASE WHEN play_type='run' AND touchdown=1 THEN 1 ELSE 0 END) AS rush_tds,
                SUM(touchdown) * 7.0 AS points_scored,
                AVG(epa) AS team_epa,
                AVG(CASE WHEN play_type='pass' THEN epa END) AS pass_epa,
                AVG(CASE WHEN play_type='run' THEN epa END) AS rush_epa
            FROM play_by_play
            WHERE season = ? AND season_type = 'REG' AND posteam IS NOT NULL
            GROUP BY posteam, season
        """, [season])

    conn.commit()


def ingest(
    start: int = 2005,
    end: int = 2025,
    db_path=None,
) -> None:
    """Run stat aggregation for all seasons."""
    conn = get_conn(db_path) if db_path else get_conn()
    seasons = list(range(start, end + 1))

    print("Aggregating player season stats...")
    aggregate_player_stats(conn, seasons)

    print("Aggregating team season stats...")
    aggregate_team_stats(conn, seasons)

    conn.close()
    print("Aggregation complete.")


if __name__ == "__main__":
    ingest()
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
/Users/theoauyeung/miniforge3/bin/python3.12 -m pytest tests/test_aggregate_stats.py -v
```

Expected: 2 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/tay/ingestion/aggregate_stats.py tests/test_aggregate_stats.py
git commit -m "feat: aggregate PBP → player_season_stats and team_season_stats"
```

---

### Task 6: Player ID unification layer

**Files:**
- Create: `src/tay/ingestion/player_ids.py`
- Create: `tests/test_player_ids.py`

**Interfaces:**
- Consumes: `players` table (gsis_id + name), external IDs from Sleeper/ESPN
- Produces: updates `players.sleeper_id`, `players.espn_id`, `players.pfr_id` columns
- Exports: `resolve_gsis_id(name: str, position: str, team: str, conn) -> str | None`

The canonical ID is `gsis_id` from nfl-data-py. All other sources must map to it. Strategy:
1. Exact match on `(name, position, team)` — covers ~85% of players
2. Normalized name match (lowercase, remove suffixes Jr/Sr/III) — covers another ~10%
3. Remaining unmapped players logged to `data/raw/unmatched_players.csv` for manual review

- [ ] **Step 1: Write failing tests**

Create `tests/test_player_ids.py`:
```python
import pytest
from tay.ingestion.player_ids import normalize_name, resolve_gsis_id
from tay.db import get_conn, init_schema

def test_normalize_name():
    assert normalize_name("Patrick Mahomes II") == "patrick mahomes"
    assert normalize_name("Travis Kelce Jr.") == "travis kelce"
    assert normalize_name("Tyreek Hill") == "tyreek hill"

@pytest.fixture
def conn(tmp_path):
    c = get_conn(tmp_path / "test.duckdb")
    init_schema(c)
    c.execute("""
        INSERT INTO players (gsis_id, name, position, team)
        VALUES ('00-0033873', 'Patrick Mahomes', 'QB', 'KC')
    """)
    yield c
    c.close()

def test_resolve_exact_match(conn):
    gsis = resolve_gsis_id("Patrick Mahomes", "QB", "KC", conn)
    assert gsis == "00-0033873"

def test_resolve_normalized_match(conn):
    gsis = resolve_gsis_id("Patrick Mahomes II", "QB", "KC", conn)
    assert gsis == "00-0033873"

def test_resolve_no_match(conn):
    gsis = resolve_gsis_id("Unknown Player", "WR", "SF", conn)
    assert gsis is None
```

- [ ] **Step 2: Run — expect FAIL**

```bash
/Users/theoauyeung/miniforge3/bin/python3.12 -m pytest tests/test_player_ids.py -v
```

Expected: FAIL (module not found)

- [ ] **Step 3: Create `src/tay/ingestion/player_ids.py`**

```python
"""Cross-source player ID unification."""
from __future__ import annotations
import re
import csv
from pathlib import Path
import duckdb

from tay.db import get_conn

RAW_DIR = Path(__file__).parent.parent.parent.parent / "data" / "raw"

_SUFFIX_RE = re.compile(
    r"\s+(jr\.?|sr\.?|ii|iii|iv|v)$", re.IGNORECASE
)


def normalize_name(name: str) -> str:
    """Lowercase, strip name suffixes (Jr, Sr, II, III)."""
    return _SUFFIX_RE.sub("", name.strip()).lower()


def resolve_gsis_id(
    name: str,
    position: str,
    team: str,
    conn: duckdb.DuckDBPyConnection,
) -> str | None:
    """Attempt to find a gsis_id for (name, position, team).

    Tries:
    1. Exact name + position + team match
    2. Normalized name + position match (ignores team — players change teams)
    """
    # 1. Exact match
    row = conn.execute(
        "SELECT gsis_id FROM players WHERE name = ? AND position = ? AND team = ?",
        [name, position, team],
    ).fetchone()
    if row:
        return row[0]

    # 2. Normalized name + position
    normed = normalize_name(name)
    rows = conn.execute(
        "SELECT gsis_id, name FROM players WHERE position = ?", [position]
    ).fetchall()
    for gsis_id, db_name in rows:
        if normalize_name(db_name) == normed:
            return gsis_id

    return None


def map_sleeper_ids(
    conn: duckdb.DuckDBPyConnection,
    sleeper_players: list[dict],
) -> tuple[int, int]:
    """Map Sleeper player IDs to gsis_ids. Returns (mapped, unmatched) counts."""
    mapped = 0
    unmatched = []

    for p in sleeper_players:
        name = p.get("full_name", "")
        pos = p.get("position", "")
        team = p.get("team", "")
        sleeper_id = p.get("player_id", "")
        gsis_id = p.get("gsis_id")  # Sleeper sometimes provides gsis_id directly

        if not gsis_id:
            gsis_id = resolve_gsis_id(name, pos, team, conn)

        if gsis_id:
            conn.execute(
                "UPDATE players SET sleeper_id = ? WHERE gsis_id = ?",
                [sleeper_id, gsis_id],
            )
            mapped += 1
        else:
            unmatched.append({"name": name, "position": pos, "team": team, "sleeper_id": sleeper_id})

    conn.commit()

    if unmatched:
        out = RAW_DIR / "unmatched_sleeper.csv"
        with open(out, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["name", "position", "team", "sleeper_id"])
            writer.writeheader()
            writer.writerows(unmatched)
        print(f"  {len(unmatched)} unmatched players written to {out}")

    return mapped, len(unmatched)
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
/Users/theoauyeung/miniforge3/bin/python3.12 -m pytest tests/test_player_ids.py -v
```

Expected: 4 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/tay/ingestion/player_ids.py tests/test_player_ids.py
git commit -m "feat: player ID unification — normalize names, resolve gsis_id cross-source"
```

---

### Task 7: ADP ingestion (Sleeper + ESPN + FantasyPros)

**Files:**
- Create: `src/tay/ingestion/sleeper.py`
- Create: `src/tay/ingestion/espn.py`
- Create: `src/tay/ingestion/fantasypros.py`

**Interfaces:**
- Consumes: `players` table (for ID resolution), `player_ids.map_sleeper_ids`
- Produces: `adp` table rows with `platform` ∈ `{'sleeper', 'espn', 'fantasypros'}`

- [ ] **Step 1: Create `src/tay/ingestion/sleeper.py`**

```python
"""Ingest player metadata and ADP from Sleeper API (free, no auth required)."""
from __future__ import annotations
import time
from pathlib import Path
import requests
import duckdb

from tay.db import get_conn, init_schema
from tay.ingestion.player_ids import map_sleeper_ids

SLEEPER_PLAYERS_URL = "https://api.sleeper.app/v1/players/nfl"


def fetch_all_players() -> list[dict]:
    """Fetch all NFL players from Sleeper. Returns list of player dicts."""
    print("Fetching Sleeper player registry...")
    resp = requests.get(SLEEPER_PLAYERS_URL, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return list(data.values())


def ingest_adp_from_sleeper_players(
    conn: duckdb.DuckDBPyConnection,
    players: list[dict],
    season: int,
    format_: str = "ppr",
) -> int:
    """Write Sleeper player ADP (fantasy_positions, adp) into the adp table."""
    inserted = 0
    for p in players:
        sleeper_id = p.get("player_id")
        adp_val = p.get("search_rank")
        if not sleeper_id or not adp_val:
            continue

        # Find gsis_id from sleeper_id we already mapped
        row = conn.execute(
            "SELECT gsis_id FROM players WHERE sleeper_id = ?", [sleeper_id]
        ).fetchone()
        if not row:
            continue
        gsis_id = row[0]

        conn.execute("""
            INSERT OR REPLACE INTO adp (gsis_id, season, platform, format, adp, rank)
            VALUES (?, ?, 'sleeper', ?, ?, ?)
        """, [gsis_id, season, format_, float(adp_val), int(adp_val)])
        inserted += 1

    conn.commit()
    return inserted


def ingest(
    season: int = 2026,
    db_path=None,
) -> None:
    conn = get_conn(db_path) if db_path else get_conn()
    init_schema(conn)

    players = fetch_all_players()
    print(f"  Fetched {len(players):,} Sleeper players")

    mapped, unmatched = map_sleeper_ids(conn, players)
    print(f"  ID mapping: {mapped:,} matched, {unmatched:,} unmatched")

    n = ingest_adp_from_sleeper_players(conn, players, season)
    print(f"  ADP rows inserted: {n:,}")

    conn.close()
```

- [ ] **Step 2: Create `src/tay/ingestion/espn.py`**

```python
"""Ingest ADP from ESPN unofficial Fantasy API."""
from __future__ import annotations
import requests
import duckdb

from tay.db import get_conn, init_schema

ESPN_ADP_URL = (
    "https://fantasy.espn.com/apis/v3/games/ffl/seasons/{season}"
    "/segments/0/leaguedefaults/3?view=kona_player_info"
)

ESPN_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://fantasy.espn.com/",
}


def fetch_espn_adp(season: int) -> list[dict]:
    """Fetch ESPN ADP data for a given season."""
    url = ESPN_ADP_URL.format(season=season)
    resp = requests.get(url, headers=ESPN_HEADERS, timeout=30)
    if resp.status_code != 200:
        print(f"  ESPN API returned {resp.status_code} — skipping")
        return []
    data = resp.json()
    players = data.get("players", [])
    return players


def ingest(season: int = 2026, format_: str = "ppr", db_path=None) -> None:
    conn = get_conn(db_path) if db_path else get_conn()
    init_schema(conn)

    print(f"Fetching ESPN ADP for {season}...")
    raw = fetch_espn_adp(season)
    if not raw:
        print("  No ESPN data returned.")
        conn.close()
        return

    inserted = 0
    for entry in raw:
        player_info = entry.get("playerPoolEntry", {})
        espn_id = str(player_info.get("playerId", ""))
        adp_val = player_info.get("averageDraftPosition")
        if not espn_id or not adp_val:
            continue

        row = conn.execute(
            "SELECT gsis_id FROM players WHERE espn_id = ?", [espn_id]
        ).fetchone()
        if not row:
            continue

        conn.execute("""
            INSERT OR REPLACE INTO adp (gsis_id, season, platform, format, adp, rank)
            VALUES (?, ?, 'espn', ?, ?, ?)
        """, [row[0], season, format_, float(adp_val), round(adp_val)])
        inserted += 1

    conn.commit()
    conn.close()
    print(f"ESPN ADP: {inserted:,} rows inserted")
```

- [ ] **Step 3: Create `src/tay/ingestion/fantasypros.py`**

```python
"""Ingest consensus ADP from FantasyPros (CSV export endpoint, free tier)."""
from __future__ import annotations
import time
import io
import requests
import pandas as pd
import duckdb

from tay.db import get_conn, init_schema
from tay.ingestion.player_ids import resolve_gsis_id

FP_ADP_URL = "https://www.fantasypros.com/nfl/adp/{format_slug}.php?export=xls"
FORMAT_SLUGS = {
    "ppr": "ppr-overall",
    "half_ppr": "half-point-ppr-overall",
    "standard": "overall",
}

FP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
}


def fetch_fp_adp(format_: str = "ppr") -> pd.DataFrame | None:
    """Fetch FantasyPros ADP CSV for a given format."""
    slug = FORMAT_SLUGS.get(format_, "ppr-overall")
    url = FP_ADP_URL.format(format_slug=slug)
    resp = requests.get(url, headers=FP_HEADERS, timeout=30)
    if resp.status_code != 200:
        print(f"  FantasyPros returned {resp.status_code} for {format_}")
        return None
    df = pd.read_excel(io.BytesIO(resp.content))
    return df


def ingest(season: int = 2026, db_path=None) -> None:
    conn = get_conn(db_path) if db_path else get_conn()
    init_schema(conn)

    for format_ in ["ppr", "half_ppr", "standard"]:
        print(f"Fetching FantasyPros ADP ({format_})...")
        df = fetch_fp_adp(format_)
        if df is None:
            continue

        inserted = 0
        for _, row in df.iterrows():
            name = str(row.get("Player Name", row.get("Player", "")))
            pos = str(row.get("POS", row.get("Position", "")))[:2].upper()
            team = str(row.get("Team", ""))
            adp_val = row.get("AVG", row.get("ADP"))
            rank = row.get("RK", row.get("Rank"))
            if not name or pd.isna(adp_val):
                continue

            gsis_id = resolve_gsis_id(name, pos, team, conn)
            if not gsis_id:
                continue

            conn.execute("""
                INSERT OR REPLACE INTO adp (gsis_id, season, platform, format, adp, rank)
                VALUES (?, ?, 'fantasypros', ?, ?, ?)
            """, [gsis_id, season, format_, float(adp_val),
                  int(rank) if pd.notna(rank) else None])
            inserted += 1

        conn.commit()
        print(f"  FantasyPros {format_}: {inserted:,} rows")
        time.sleep(1)  # rate limit

    conn.close()
```

- [ ] **Step 4: Smoke test Sleeper (live API)**

```bash
/Users/theoauyeung/miniforge3/bin/python3.12 -c "
from tay.ingestion.sleeper import fetch_all_players
players = fetch_all_players()
print(f'Fetched {len(players)} players from Sleeper')
active = [p for p in players if p.get('active')]
print(f'Active players: {len(active)}')
"
```

Expected: ~2000+ total players, ~1800+ active.

- [ ] **Step 5: Commit**

```bash
git add src/tay/ingestion/sleeper.py src/tay/ingestion/espn.py src/tay/ingestion/fantasypros.py
git commit -m "feat: ADP ingestion — Sleeper API, ESPN unofficial API, FantasyPros CSV"
```

---

### Task 8: PFR combine data scraper

**Files:**
- Create: `src/tay/ingestion/pfr.py`

**Interfaces:**
- Produces: `combine_data` table rows
- Rate limit: 1-second delay between requests

- [ ] **Step 1: Create `src/tay/ingestion/pfr.py`**

```python
"""Scrape Pro Football Reference for combine data (athleticism metrics)."""
from __future__ import annotations
import time
from pathlib import Path
import requests
from bs4 import BeautifulSoup
import pandas as pd
import duckdb

from tay.db import get_conn, init_schema
from tay.ingestion.player_ids import resolve_gsis_id

PFR_COMBINE_URL = "https://www.pro-football-reference.com/draft/{year}-combine.htm"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

_FLOAT = lambda v: float(v) if v and v != "--" else None
_INT   = lambda v: int(v) if v and v != "--" else None


def scrape_combine_year(year: int) -> list[dict]:
    """Scrape PFR combine page for one year. Returns list of player dicts."""
    url = PFR_COMBINE_URL.format(year=year)
    resp = requests.get(url, headers=HEADERS, timeout=30)
    if resp.status_code != 200:
        print(f"  PFR {year}: HTTP {resp.status_code}")
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    table = soup.find("table", id="combine")
    if not table:
        return []

    rows = []
    for tr in table.find("tbody").find_all("tr"):
        if tr.get("class") and "thead" in tr.get("class"):
            continue
        cells = {td.get("data-stat"): td.get_text(strip=True) for td in tr.find_all(["td", "th"])}
        if not cells.get("player"):
            continue
        rows.append({
            "name":       cells.get("player", ""),
            "position":   cells.get("pos", ""),
            "pfr_id":     tr.find("td", {"data-stat": "player"}).find("a")["href"].split("/")[-1].replace(".htm", "")
                          if tr.find("td", {"data-stat": "player"}) and tr.find("td", {"data-stat": "player"}).find("a") else None,
            "season":     year,
            "forty_yard": _FLOAT(cells.get("forty_yd")),
            "vertical":   _FLOAT(cells.get("vertical")),
            "broad_jump": _FLOAT(cells.get("broad_jump")),
            "cone":       _FLOAT(cells.get("cone")),
            "shuttle":    _FLOAT(cells.get("shuttle")),
            "bench_reps": _INT(cells.get("bench_reps")),
            "height":     _INT(cells.get("ht")),
            "weight":     _INT(cells.get("wt")),
        })
    return rows


def ingest(
    start: int = 2005,
    end: int = 2025,
    db_path=None,
) -> None:
    conn = get_conn(db_path) if db_path else get_conn()
    init_schema(conn)
    total = 0

    for year in range(start, end + 1):
        print(f"  PFR combine {year}...")
        rows = scrape_combine_year(year)
        for r in rows:
            gsis_id = resolve_gsis_id(r["name"], r["position"], "", conn) if r["name"] else None
            pfr_id = r["pfr_id"]
            if not pfr_id:
                continue

            # Update pfr_id on players table if we resolved the gsis_id
            if gsis_id:
                conn.execute(
                    "UPDATE players SET pfr_id = ? WHERE gsis_id = ?",
                    [pfr_id, gsis_id]
                )

            conn.execute("""
                INSERT OR REPLACE INTO combine_data
                    (gsis_id, pfr_id, name, season, position,
                     forty_yard, vertical, broad_jump, cone, shuttle, bench_reps,
                     height, weight)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                gsis_id, pfr_id, r["name"], r["season"], r["position"],
                r["forty_yard"], r["vertical"], r["broad_jump"],
                r["cone"], r["shuttle"], r["bench_reps"],
                r["height"], r["weight"],
            ])
            total += 1

        conn.commit()
        time.sleep(1)  # PFR rate limit

    conn.close()
    print(f"PFR combine: {total:,} rows inserted")


if __name__ == "__main__":
    ingest()
```

- [ ] **Step 2: Smoke test one year**

```bash
/Users/theoauyeung/miniforge3/bin/python3.12 -c "
from tay.ingestion.pfr import scrape_combine_year
rows = scrape_combine_year(2024)
print(f'Scraped {len(rows)} combine entries for 2024')
if rows:
    print(rows[0])
"
```

Expected: 300+ rows, first row shows name/position/40 time.

- [ ] **Step 3: Commit**

```bash
git add src/tay/ingestion/pfr.py
git commit -m "feat: PFR combine data scraper (40 time, vertical, cone, shuttle, bench)"
```

---

### Task 9: CLI pipeline script

**Files:**
- Create: `scripts/ingest.py`

**Interfaces:**
- Consumes: all ingestion modules
- Produces: fully populated `data/ff.duckdb`

- [ ] **Step 1: Create `scripts/ingest.py`**

```python
#!/usr/bin/env python3
"""
Full ingestion pipeline — populates data/ff.duckdb.

Usage:
    python scripts/ingest.py [--seasons 2005-2025] [--skip-pbp] [--season-only 2024]

Steps:
    1. Initialize DuckDB schema
    2. Pull NFLFastR play-by-play (R script)
    3. Load PBP into DuckDB
    4. Ingest nfl-data-py (players, rosters, draft picks)
    5. Aggregate player/team season stats
    6. Ingest Sleeper API (player IDs + ADP)
    7. Ingest ESPN ADP
    8. Ingest FantasyPros ADP
    9. Scrape PFR combine data
"""
import argparse
import sys
import time
from pathlib import Path

# Ensure src/ is on the path when running as script
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tay.db import get_conn, init_schema
from tay.ingestion import (
    nflfastr,
    nfl_data_py_ingest,
    aggregate_stats,
    sleeper,
    espn,
    fantasypros,
    pfr,
)


def parse_args():
    p = argparse.ArgumentParser(description="TAY Analytics FF — data ingestion pipeline")
    p.add_argument("--start", type=int, default=2005, help="First season (default 2005)")
    p.add_argument("--end", type=int, default=2025, help="Last season (default 2025)")
    p.add_argument("--skip-pbp", action="store_true", help="Skip NFLFastR download (use cached parquet)")
    p.add_argument("--skip-pfr", action="store_true", help="Skip PFR scraping")
    p.add_argument("--adp-season", type=int, default=2026, help="Season for ADP data (default 2026)")
    return p.parse_args()


def step(name: str):
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")


def main():
    args = parse_args()
    start = time.time()

    step("1. Initializing DuckDB schema")
    conn = get_conn()
    init_schema(conn)
    conn.close()
    print("  Schema ready.")

    step("2-3. NFLFastR play-by-play")
    nflfastr.ingest(
        start=args.start,
        end=args.end,
        skip_download=args.skip_pbp,
    )

    step("4. nfl-data-py (players, rosters, draft picks)")
    nfl_data_py_ingest.ingest(start=args.start, end=args.end)

    step("5. Aggregate player + team season stats")
    aggregate_stats.ingest(start=args.start, end=args.end)

    step("6. Sleeper API (player IDs + ADP)")
    sleeper.ingest(season=args.adp_season)

    step("7. ESPN ADP")
    espn.ingest(season=args.adp_season)

    step("8. FantasyPros ADP")
    fantasypros.ingest(season=args.adp_season)

    if not args.skip_pfr:
        step("9. PFR combine data")
        pfr.ingest(start=args.start, end=args.end)

    elapsed = time.time() - start
    print(f"\n{'='*60}")
    print(f"  Ingestion complete in {elapsed/60:.1f} minutes")
    print(f"  Database: data/ff.duckdb")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Make executable**

```bash
chmod +x scripts/ingest.py
```

- [ ] **Step 3: Verify --help works**

```bash
/Users/theoauyeung/miniforge3/bin/python3.12 scripts/ingest.py --help
```

Expected: usage message with all flags listed.

- [ ] **Step 4: Run full test suite**

```bash
/Users/theoauyeung/miniforge3/bin/python3.12 -m pytest tests/ -v
```

Expected: all tests PASS (test_import.py, test_db.py, test_nfl_data_py.py, test_aggregate_stats.py, test_player_ids.py)

- [ ] **Step 5: Commit**

```bash
git add scripts/ingest.py
git commit -m "feat: CLI ingestion pipeline — runs all 9 ingestion steps in order"
```

---

### Task 10: End-to-end ingestion run + verification

**Files:**
- No new files — runs the pipeline and validates output

**Goal:** Run the full pipeline (or at least 2024 season) and verify data quality.

- [ ] **Step 1: Run ingestion for 2024 only (fast smoke test)**

```bash
/Users/theoauyeung/miniforge3/bin/python3.12 scripts/ingest.py \
    --start 2024 --end 2024 \
    --adp-season 2026
```

Expected: completes without error. `data/ff.duckdb` created.

- [ ] **Step 2: Verify table counts**

```bash
/Users/theoauyeung/miniforge3/bin/python3.12 -c "
from tay.db import get_conn
conn = get_conn()
tables = ['players', 'play_by_play', 'player_season_stats',
          'team_season_stats', 'rosters', 'draft_picks', 'adp']
for t in tables:
    n = conn.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
    print(f'  {t}: {n:,} rows')
conn.close()
"
```

Expected minimums (2024 only):
- `players`: 1,000+
- `play_by_play`: 40,000+
- `player_season_stats`: 500+
- `team_season_stats`: 32
- `rosters`: 5,000+
- `draft_picks`: 250+
- `adp`: 200+

- [ ] **Step 3: Spot-check data quality**

```bash
/Users/theoauyeung/miniforge3/bin/python3.12 -c "
from tay.db import get_conn
conn = get_conn()

# Check a known player
row = conn.execute(\"\"\"
    SELECT p.gsis_id, p.name, p.position, p.team,
           s.fantasy_points_ppr, s.targets, s.receptions, s.rec_yards
    FROM players p
    JOIN player_season_stats s ON p.gsis_id = s.gsis_id
    WHERE p.name ILIKE '%kelce%' AND s.season = 2024
    LIMIT 3
\"\"\").fetchall()
for r in row:
    print(r)
conn.close()
"
```

Expected: Travis Kelce row with realistic 2024 stats (100+ targets, 90+ receptions, 1000+ yards).

- [ ] **Step 4: Run full 2005–2025 ingestion (background — takes ~30-60 min)**

```bash
# Run with skip-pfr for speed first; add PFR in a follow-up run
/Users/theoauyeung/miniforge3/bin/python3.12 scripts/ingest.py \
    --start 2005 --end 2025 \
    --adp-season 2026 \
    --skip-pfr
```

- [ ] **Step 5: Commit any fixes found during the run**

If any issues arise during the full run, fix and commit:
```bash
git add -p  # stage only the fix
git commit -m "fix: <description of what was wrong>"
```

- [ ] **Step 6: Final commit**

```bash
git add .
git commit -m "feat: Plan D complete — full data foundation with 2005-2025 NFL data in DuckDB"
```

---
