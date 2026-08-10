"""Tier assignment via gap analysis on VOR within each position."""
from __future__ import annotations
import duckdb

from tay.valuation.replacement import POSITIONS


def assign_tiers(
    conn: duckdb.DuckDBPyConnection,
    season: int,
    model_version: str,
    gap_threshold: float = 15.0,
) -> int:
    """Assign tiers within each position using VOR gap analysis. Returns rows updated."""
    total = 0
    for pos in POSITIONS:
        rows = conn.execute("""
            SELECT pr.gsis_id, pr.vor
            FROM projections pr
            JOIN players pl ON pl.gsis_id = pr.gsis_id
            WHERE pr.season = ? AND pr.model_version = ? AND pl.position = ?
              AND pr.vor IS NOT NULL
            ORDER BY pr.vor DESC
        """, [season, model_version, pos]).fetchall()

        if not rows:
            continue

        tier = 1
        for i, (gsis_id, vor) in enumerate(rows):
            if i > 0 and (rows[i - 1][1] - vor) > gap_threshold:
                tier += 1
            conn.execute("""
                UPDATE projections SET tier = ?
                WHERE gsis_id = ? AND season = ? AND model_version = ?
            """, [tier, gsis_id, season, model_version])
            total += 1

    conn.commit()
    return total
