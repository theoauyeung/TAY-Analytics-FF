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


def ingest_players(conn: duckdb.DuckDBPyConnection) -> int:
    """Load player data into the players table using import_players().

    Uses the full player registry (not season-specific) to populate the
    players table with gsis_id as primary key. Columns mapped:
      display_name -> name, college_name -> college, latest_team -> team,
      draft_team -> draft info source, espn_id, pfr_id.
    """
    print("Fetching player data from import_players()...")
    df = nfl.import_players()
    df = df.dropna(subset=["gsis_id"])
    df = df.drop_duplicates(subset=["gsis_id"])

    inserted = 0
    for _, row in df.iterrows():
        conn.execute(
            """
            INSERT OR REPLACE INTO players
                (gsis_id, name, position, team, birth_date, draft_year,
                 draft_round, draft_pick, college, height, weight,
                 espn_id, pfr_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                _safe_str(row.get("gsis_id")),
                _safe_str(row.get("display_name")),
                _safe_str(row.get("position")),
                _safe_str(row.get("latest_team")),
                _safe_str(row.get("birth_date")),
                _safe_int(row.get("draft_year")),
                _safe_int(row.get("draft_round")),
                _safe_int(row.get("draft_pick")),
                _safe_str(row.get("college_name")),
                _safe_int(row.get("height")),
                _safe_int(row.get("weight")),
                _safe_str(row.get("espn_id")),
                _safe_str(row.get("pfr_id")),
            ],
        )
        inserted += 1

    conn.commit()
    return inserted


def ingest_rosters(conn: duckdb.DuckDBPyConnection, seasons: list[int]) -> int:
    """Load weekly roster data into the rosters table.

    Fetches one season at a time to avoid a pandas duplicate-label bug in
    import_weekly_rosters() when called with many seasons at once.
    """
    print(f"Fetching weekly rosters for {len(seasons)} season(s)...")
    import pandas as pd
    frames = []
    for season in seasons:
        try:
            frames.append(nfl.import_weekly_rosters(years=[season]))
        except Exception as e:
            print(f"  Season {season} rosters skipped: {e}")
    if not frames:
        return 0
    df = pd.concat(frames, ignore_index=True)

    inserted = 0
    for _, row in df.iterrows():
        gsis_id = _safe_str(row.get("player_id"))
        season = _safe_int(row.get("season"))
        week = _safe_int(row.get("week"))
        if not all([gsis_id, season, week]):
            continue
        conn.execute(
            """
            INSERT OR REPLACE INTO rosters
                (gsis_id, season, week, team, position, depth_chart_pos, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                gsis_id,
                season,
                week,
                _safe_str(row.get("team")),
                _safe_str(row.get("position")),
                _safe_int(row.get("depth_chart_position")),
                _safe_str(row.get("status")),
            ],
        )
        inserted += 1

    conn.commit()
    return inserted


def ingest_draft_picks(conn: duckdb.DuckDBPyConnection, seasons: list[int]) -> int:
    """Load NFL draft pick data into the draft_picks table.

    Uses import_draft_picks(). The 'pick' column is the overall pick number;
    there is no separate within-round pick field in this dataset so both
    overall_pick and pick are set from 'pick'.
    """
    print(f"Fetching draft picks for {len(seasons)} season(s)...")
    df = nfl.import_draft_picks(years=seasons)

    inserted = 0
    for _, row in df.iterrows():
        season = _safe_int(row.get("season"))
        overall = _safe_int(row.get("pick"))
        if not season or not overall:
            continue
        conn.execute(
            """
            INSERT OR REPLACE INTO draft_picks
                (gsis_id, season, round, pick, overall_pick, team, position, college)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                _safe_str(row.get("gsis_id")),
                season,
                _safe_int(row.get("round")),
                overall,   # within-round pick not available; use overall
                overall,
                _safe_str(row.get("team")),
                _safe_str(row.get("position")),
                _safe_str(row.get("college")),
            ],
        )
        inserted += 1

    conn.commit()
    return inserted


def ingest(
    start: int = 2005,
    end: int = 2025,
    db_path: str | Path | None = None,
) -> None:
    """Run all nfl-data-py ingestion steps.

    Populates players (full registry), rosters (weekly, start–end),
    and draft_picks (start–end).
    """
    conn = get_conn(db_path) if db_path else get_conn()
    init_schema(conn)
    seasons = list(range(start, end + 1))

    n = ingest_players(conn)
    print(f"  Players: {n:,} rows")

    n = ingest_rosters(conn, seasons)
    print(f"  Rosters: {n:,} rows")

    n = ingest_draft_picks(conn, seasons)
    print(f"  Draft picks: {n:,} rows")

    conn.close()
    print("nfl-data-py ingestion complete.")


if __name__ == "__main__":
    ingest()
