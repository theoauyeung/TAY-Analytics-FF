"""Backfill snap_share and snap_share_trend from snap_counts into player_features."""
from __future__ import annotations
import duckdb

_SNAP_COLUMNS = [
    ('snap_share',       'DOUBLE'),
    ('snap_share_trend', 'DOUBLE'),
]


def _migrate_snap_features(conn: duckdb.DuckDBPyConnection) -> None:
    for col, dtype in _SNAP_COLUMNS:
        conn.execute(f'ALTER TABLE player_features ADD COLUMN IF NOT EXISTS {col} {dtype}')


def compute_snap_features(
    conn: duckdb.DuckDBPyConnection,
    seasons: list[int],
) -> int:
    """Write snap_share and snap_share_trend into player_features for each target season.

    For target season N: reads snap_counts.season = N-1 (snap_share) and N-2 (trend).
    Returns number of rows updated.
    """
    _migrate_snap_features(conn)
    total = 0
    for season in seasons:
        prior  = season - 1
        prior2 = season - 2
        conn.execute("""
            WITH snap AS (
                SELECT s1.gsis_id,
                       s1.snap_share                            AS snap_share,
                       s1.snap_share - COALESCE(s2.snap_share, s1.snap_share) AS snap_share_trend
                FROM snap_counts s1
                LEFT JOIN snap_counts s2
                       ON s2.gsis_id = s1.gsis_id AND s2.season = ?
                WHERE s1.season = ?
            )
            UPDATE player_features
            SET snap_share       = snap.snap_share,
                snap_share_trend = snap.snap_share_trend
            FROM snap
            WHERE player_features.gsis_id = snap.gsis_id
              AND player_features.season  = ?
        """, [prior2, prior, season])
        n = conn.execute(
            'SELECT COUNT(*) FROM player_features WHERE season = ? AND snap_share IS NOT NULL',
            [season],
        ).fetchone()[0]
        total += n
    conn.commit()
    return total
