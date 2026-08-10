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
        target_cols = ", ".join(f'"{RENAME.get(c, c)}"' for c in KEEP_COLS)
        # Delete existing rows for the season before re-inserting (idempotent)
        conn.execute("DELETE FROM play_by_play WHERE season = ?", [season])
        conn.execute(f"""
            INSERT INTO play_by_play ({target_cols})
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
