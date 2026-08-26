"""Blend consensus projections with ML model projections."""
from __future__ import annotations
import duckdb

CONSENSUS_WEIGHT = 0.65
ML_WEIGHT = 0.35

# Players who changed teams get more consensus weight: the ML model trained on
# last season's opportunity metrics, which no longer apply in the new situation.
TEAM_CHANGE_CONSENSUS_WEIGHT = 0.85
TEAM_CHANGE_ML_WEIGHT = 0.15


def blend_projections(
    conn: duckdb.DuckDBPyConnection,
    season: int,
    model_version: str,
) -> int:
    """Write consensus_projection and blended_projection to projections table.

    Averages all consensus sources for a player, then blends:
      - 65% consensus + 35% ML for players on the same team as last season
      - 85% consensus + 15% ML for team changers (ML opportunity metrics stale)
    Returns count of rows given a true blended value (not fallback).
    Falls back to mean_projection when no consensus row exists for a player.
    """
    conn.execute("""
        UPDATE projections
        SET consensus_projection = NULL,
            blended_projection   = NULL
        WHERE season = ? AND model_version = ?
    """, [season, model_version])

    conn.execute("""
        WITH cp_agg AS (
            SELECT gsis_id, AVG(points) AS avg_pts
            FROM consensus_projections
            WHERE season = ?
            GROUP BY gsis_id
        ),
        last_team AS (
            SELECT gsis_id, team,
                   ROW_NUMBER() OVER (PARTITION BY gsis_id ORDER BY season DESC) AS rn
            FROM player_season_stats
            WHERE season < ?
        ),
        team_changers AS (
            SELECT p.gsis_id
            FROM players p
            JOIN last_team lt ON lt.gsis_id = p.gsis_id AND lt.rn = 1
            WHERE p.team IS NOT NULL AND lt.team IS NOT NULL
              AND p.team != lt.team
        ),
        blended AS (
            SELECT
                cp.gsis_id,
                cp.avg_pts,
                CASE WHEN tc.gsis_id IS NOT NULL THEN ? ELSE ? END AS cw,
                CASE WHEN tc.gsis_id IS NOT NULL THEN ? ELSE ? END AS mw
            FROM cp_agg cp
            LEFT JOIN team_changers tc ON tc.gsis_id = cp.gsis_id
        )
        UPDATE projections
        SET consensus_projection = blended.avg_pts,
            blended_projection   = blended.cw * blended.avg_pts + blended.mw * mean_projection
        FROM blended
        WHERE projections.gsis_id       = blended.gsis_id
          AND projections.season        = ?
          AND projections.model_version = ?
    """, [season, season,
          TEAM_CHANGE_CONSENSUS_WEIGHT, CONSENSUS_WEIGHT,
          TEAM_CHANGE_ML_WEIGHT, ML_WEIGHT,
          season, model_version])

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
