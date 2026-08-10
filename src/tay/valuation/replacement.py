from __future__ import annotations
from dataclasses import dataclass
import duckdb

POSITIONS = ['QB', 'RB', 'WR', 'TE']


@dataclass
class ReplacementConfig:
    teams: int = 12
    roster_qb: int = 1
    roster_rb: int = 2
    roster_wr: int = 2
    roster_te: int = 1
    roster_flex: int = 1


def get_replacement_spots(config: ReplacementConfig) -> dict[str, int]:
    flex_rb = round(config.teams * config.roster_flex * 0.5)
    flex_wr = config.teams * config.roster_flex - flex_rb
    return {
        'QB': config.teams * config.roster_qb,
        'RB': config.teams * config.roster_rb + flex_rb,
        'WR': config.teams * config.roster_wr + flex_wr,
        'TE': config.teams * config.roster_te,
    }


def compute_replacement_levels(
    conn: duckdb.DuckDBPyConnection,
    season: int,
    model_version: str,
    config: ReplacementConfig,
) -> dict[str, float]:
    spots = get_replacement_spots(config)
    levels: dict[str, float] = {}
    for pos in POSITIONS:
        n = spots.get(pos, 0)
        if n <= 0:
            levels[pos] = 0.0
            continue
        row = conn.execute("""
            SELECT pr.mean_projection
            FROM projections pr
            JOIN players pl ON pl.gsis_id = pr.gsis_id
            WHERE pr.season = ? AND pr.model_version = ? AND pl.position = ?
            ORDER BY pr.mean_projection DESC
            LIMIT 1 OFFSET ?
        """, [season, model_version, pos, n - 1]).fetchone()
        levels[pos] = float(row[0]) if row else 0.0
    return levels
