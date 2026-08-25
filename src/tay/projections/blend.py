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
        )
        UPDATE projections
        SET consensus_projection = cp_agg.avg_pts,
            blended_projection   = ? * cp_agg.avg_pts + ? * mean_projection
        FROM cp_agg
        WHERE projections.gsis_id       = cp_agg.gsis_id
          AND projections.season        = ?
          AND projections.model_version = ?
    """, [season, CONSENSUS_WEIGHT, ML_WEIGHT, season, model_version])

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
