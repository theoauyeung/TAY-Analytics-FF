"""VOR computation and overall ranking."""
from __future__ import annotations
import duckdb

from tay.valuation.replacement import POSITIONS

# Single-QB PPR scarcity weights. QB is discounted because starter-quality QBs
# are available deep into drafts (late-round QB strategy). RB is 1.0 (scarcest).
_SCARCITY_WEIGHT: dict[str, float] = {
    'QB': 0.40,
    'RB': 1.0,
    'WR': 0.85,
    'TE': 0.75,
}


def compute_vor(
    conn: duckdb.DuckDBPyConnection,
    season: int,
    model_version: str,
    replacement_levels: dict[str, float],
) -> int:
    """Update vor and vor_rank in projections. Returns number of rows updated."""
    for pos in POSITIONS:
        repl = replacement_levels.get(pos, 0.0)
        weight = _SCARCITY_WEIGHT.get(pos, 1.0)
        conn.execute("""
            UPDATE projections
            SET vor = (mean_projection - ?) * ?
            WHERE season = ? AND model_version = ?
              AND gsis_id IN (SELECT gsis_id FROM players WHERE position = ?)
        """, [repl, weight, season, model_version, pos])

    updated = conn.execute("""
        SELECT COUNT(*) FROM projections
        WHERE season = ? AND model_version = ? AND vor IS NOT NULL
    """, [season, model_version]).fetchone()[0]

    ranked = conn.execute("""
        SELECT gsis_id,
               ROW_NUMBER() OVER (ORDER BY vor DESC NULLS LAST) AS rk
        FROM projections
        WHERE season = ? AND model_version = ? AND vor IS NOT NULL
    """, [season, model_version]).fetchall()

    for gsis_id, rk in ranked:
        conn.execute("""
            UPDATE projections SET vor_rank = ?
            WHERE gsis_id = ? AND season = ? AND model_version = ?
        """, [rk, gsis_id, season, model_version])

    conn.commit()
    return updated
