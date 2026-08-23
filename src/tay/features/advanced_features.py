"""Compute advanced player features from play_by_play (opportunity share, consistency, SOS)."""
from __future__ import annotations
import duckdb

_ADVANCED_COLUMNS = [
    ('target_share',    'DOUBLE'),
    ('air_yards_share', 'DOUBLE'),
    ('wopr',            'DOUBLE'),
    ('weekly_fpts_std', 'DOUBLE'),
    ('boom_rate',       'DOUBLE'),
    ('floor_rate',      'DOUBLE'),
    ('sos_pts_allowed', 'DOUBLE'),
]


def _migrate_advanced_features(conn: duckdb.DuckDBPyConnection) -> None:
    for col, dtype in _ADVANCED_COLUMNS:
        conn.execute(f'ALTER TABLE player_features ADD COLUMN IF NOT EXISTS {col} {dtype}')


def compute_advanced_features(
    conn: duckdb.DuckDBPyConnection,
    seasons: list[int],
) -> int:
    """Compute and write advanced features for the given target seasons.

    For target season N, reads play_by_play rows where season = N-1.
    Updates existing player_features rows in place.
    Returns total number of player_features rows updated.
    """
    _migrate_advanced_features(conn)
    total = 0
    for season in seasons:
        prior = season - 1
        _compute_opportunity_share(conn, prior, season)
        _compute_consistency(conn, prior, season)
        _compute_sos(conn, prior, season)
        n = conn.execute(
            'SELECT COUNT(*) FROM player_features WHERE season = ? AND target_share IS NOT NULL',
            [season],
        ).fetchone()[0]
        total += n
    conn.commit()
    return total


def _compute_opportunity_share(
    conn: duckdb.DuckDBPyConnection,
    prior_season: int,
    target_season: int,
) -> None:
    conn.execute("""
        WITH team_pass AS (
            SELECT posteam                          AS team,
                   COUNT(*)                         AS team_attempts,
                   SUM(COALESCE(air_yards, 0.0))    AS team_air_yards
            FROM play_by_play
            WHERE pass_attempt = 1 AND season_type = 'REG' AND season = ?
            GROUP BY posteam
        ),
        player_opps AS (
            SELECT receiver_id                       AS gsis_id,
                   COUNT(*)                          AS targets,
                   SUM(COALESCE(air_yards, 0.0))     AS player_air_yards
            FROM play_by_play
            WHERE pass_attempt = 1 AND receiver_id IS NOT NULL
              AND season_type = 'REG' AND season = ?
            GROUP BY receiver_id
        ),
        computed AS (
            SELECT pf.gsis_id,
                   po.targets          / NULLIF(tp.team_attempts,   0) AS target_share,
                   po.player_air_yards / NULLIF(tp.team_air_yards,  0) AS air_yards_share,
                   1.5 * po.targets          / NULLIF(tp.team_attempts,  0)
                 + 0.7 * po.player_air_yards / NULLIF(tp.team_air_yards, 0) AS wopr
            FROM player_features pf
            JOIN player_opps po ON po.gsis_id = pf.gsis_id
            JOIN team_pass   tp ON tp.team    = pf.team
            WHERE pf.season = ?
        )
        UPDATE player_features
        SET target_share    = c.target_share,
            air_yards_share = c.air_yards_share,
            wopr            = c.wopr
        FROM computed c
        WHERE player_features.gsis_id = c.gsis_id
          AND player_features.season  = ?
    """, [prior_season, prior_season, target_season, target_season])


def _compute_consistency(
    conn: duckdb.DuckDBPyConnection,
    prior_season: int,
    target_season: int,
) -> None:
    pass  # implemented in Task 3


def _compute_sos(
    conn: duckdb.DuckDBPyConnection,
    prior_season: int,
    target_season: int,
) -> None:
    pass  # implemented in Task 4
