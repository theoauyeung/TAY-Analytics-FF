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
