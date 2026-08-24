"""ADP-driven draft value analytics.

Computes efficiency_factor as a z-score of a player's projection relative to
peers in the same ADP bucket.  Results are written to the player_analytics table.
"""
from __future__ import annotations

import duckdb

_BUCKETS: list[tuple[int, int, str]] = [
    (1,   5,   '1-5'),
    (6,   12,  '6-12'),
    (13,  24,  '13-24'),
    (25,  36,  '25-36'),
    (37,  48,  '37-48'),
    (49,  72,  '49-72'),
    (73,  108, '73-108'),
    (109, 9999, '109+'),
]


def _adp_bucket(overall_pick: int) -> str:
    """Return the bucket label for an ADP value (1-based)."""
    for lo, hi, label in _BUCKETS:
        if lo <= overall_pick <= hi:
            return label
    return '109+'


def compute_draft_value(
    conn: duckdb.DuckDBPyConnection,
    season: int = 2026,
    model_version: str = 'neural-v1',
) -> int:
    """Compute efficiency_factor for each player with ESPN ADP and write to player_analytics.

    efficiency_factor is the z-score of a player's mean_projection relative to
    all players in the same ADP bucket.  Players in singleton/zero-std buckets
    receive efficiency_factor = 0.0.

    Returns the number of rows written.
    """
    # Pull ADP + projection data for the requested season/model
    rows = conn.execute(
        """
        SELECT
            a.gsis_id,
            a.adp,
            p.mean_projection
        FROM adp a
        JOIN projections p
            ON  a.gsis_id       = p.gsis_id
            AND a.season        = p.season
            AND p.model_version = ?
        WHERE a.season   = ?
          AND a.platform = 'espn'
          AND a.format   = 'ppr'
          AND p.mean_projection IS NOT NULL
        """,
        [model_version, season],
    ).fetchall()

    if not rows:
        return 0

    # Assign buckets and collect per-bucket projections
    bucket_projections: dict[str, list[float]] = {}
    player_data: list[tuple[str, str, float]] = []  # (gsis_id, bucket, projection)

    for gsis_id, adp, projection in rows:
        bucket = _adp_bucket(int(adp))
        bucket_projections.setdefault(bucket, []).append(projection)
        player_data.append((gsis_id, bucket, projection))

    # Compute per-bucket statistics
    bucket_stats: dict[str, tuple[float, float, int]] = {}  # bucket -> (mean, std, n)
    for bucket, projections in bucket_projections.items():
        n = len(projections)
        mean = sum(projections) / n
        if n > 1:
            variance = sum((x - mean) ** 2 for x in projections) / (n - 1)
            std = variance ** 0.5
        else:
            std = 0.0
        bucket_stats[bucket] = (mean, std, n)

    # Build output rows
    output_rows: list[tuple] = []
    for gsis_id, bucket, projection in player_data:
        mean, std, n = bucket_stats[bucket]
        pts_above = projection - mean
        if std > 0:
            efficiency_factor = pts_above / std
        else:
            efficiency_factor = 0.0
        output_rows.append((gsis_id, season, efficiency_factor, bucket, pts_above, n))

    # Upsert into player_analytics — ON CONFLICT preserves created_at
    conn.executemany(
        """
        INSERT INTO player_analytics
            (gsis_id, season, efficiency_factor, adp_bucket, avg_pts_above_expectation, sample_size)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT (gsis_id, season) DO UPDATE SET
            efficiency_factor         = excluded.efficiency_factor,
            adp_bucket                = excluded.adp_bucket,
            avg_pts_above_expectation = excluded.avg_pts_above_expectation,
            sample_size               = excluded.sample_size
        """,
        output_rows,
    )

    return len(output_rows)
