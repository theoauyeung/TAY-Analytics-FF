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
            # DuckDB supports INSERT OR IGNORE via WHERE NOT EXISTS
            conn.execute("""
                INSERT INTO team_features (team, season)
                SELECT ?, ?
                WHERE NOT EXISTS (
                    SELECT 1 FROM team_features WHERE team = ? AND season = ?
                )
            """, [team, season, team, season])
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
