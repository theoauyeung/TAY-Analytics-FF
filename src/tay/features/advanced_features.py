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
                   po.targets::DOUBLE          / NULLIF(tp.team_attempts,   0) AS target_share,
                   po.player_air_yards / NULLIF(tp.team_air_yards,  0) AS air_yards_share,
                   1.5 * po.targets::DOUBLE          / NULLIF(tp.team_attempts,  0)
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
    conn.execute("""
        WITH weekly_pts AS (
            SELECT receiver_id AS gsis_id,
                   week,
                   SUM(CASE WHEN complete_pass = 1 THEN 1.0              ELSE 0 END
                     + CASE WHEN complete_pass = 1 THEN yards_gained * 0.1 ELSE 0 END
                     + CASE WHEN complete_pass = 1 AND touchdown = 1 THEN 6.0 ELSE 0 END
                   ) AS fpts
            FROM play_by_play
            WHERE pass_attempt = 1 AND receiver_id IS NOT NULL
              AND season_type = 'REG' AND season = ?
            GROUP BY receiver_id, week
            UNION ALL
            SELECT rusher_id AS gsis_id,
                   week,
                   SUM(yards_gained * 0.1
                     + CASE WHEN touchdown = 1 THEN 6.0 ELSE 0 END
                   ) AS fpts
            FROM play_by_play
            WHERE rush_attempt = 1 AND rusher_id IS NOT NULL
              AND season_type = 'REG' AND season = ?
            GROUP BY rusher_id, week
        ),
        combined AS (
            SELECT gsis_id, week, SUM(fpts) AS total_fpts
            FROM weekly_pts
            GROUP BY gsis_id, week
        ),
        consistency AS (
            SELECT gsis_id,
                   STDDEV_SAMP(total_fpts)                                     AS weekly_fpts_std,
                   AVG(CASE WHEN total_fpts >= 20 THEN 1.0 ELSE 0.0 END)       AS boom_rate,
                   AVG(CASE WHEN total_fpts <   8 THEN 1.0 ELSE 0.0 END)       AS floor_rate
            FROM combined
            GROUP BY gsis_id
        )
        UPDATE player_features
        SET weekly_fpts_std = c.weekly_fpts_std,
            boom_rate       = c.boom_rate,
            floor_rate      = c.floor_rate
        FROM consistency c
        WHERE player_features.gsis_id = c.gsis_id
          AND player_features.season  = ?
    """, [prior_season, prior_season, target_season])


def _compute_sos(
    conn: duckdb.DuckDBPyConnection,
    prior_season: int,
    target_season: int,
) -> None:
    conn.execute("""
        WITH game_pts AS (
            SELECT receiver_id AS gsis_id,
                   defteam,
                   game_id,
                   SUM(CASE WHEN complete_pass = 1 THEN 1.0              ELSE 0 END
                     + CASE WHEN complete_pass = 1 THEN yards_gained * 0.1 ELSE 0 END
                     + CASE WHEN complete_pass = 1 AND touchdown = 1 THEN 6.0 ELSE 0 END
                   ) AS game_fpts
            FROM play_by_play
            WHERE pass_attempt = 1 AND receiver_id IS NOT NULL
              AND season_type = 'REG' AND season = ?
            GROUP BY receiver_id, defteam, game_id
            UNION ALL
            SELECT rusher_id,
                   defteam,
                   game_id,
                   SUM(yards_gained * 0.1 + CASE WHEN touchdown = 1 THEN 6.0 ELSE 0 END)
            FROM play_by_play
            WHERE rush_attempt = 1 AND rusher_id IS NOT NULL
              AND season_type = 'REG' AND season = ?
            GROUP BY rusher_id, defteam, game_id
        ),
        combined_game_pts AS (
            SELECT gsis_id, defteam, game_id, SUM(game_fpts) AS total_fpts
            FROM game_pts
            GROUP BY gsis_id, defteam, game_id
        ),
        def_vs_pos AS (
            SELECT gp.defteam,
                   pl.position,
                   AVG(gp.total_fpts) AS avg_pts_allowed
            FROM combined_game_pts gp
            JOIN players pl ON pl.gsis_id = gp.gsis_id
            GROUP BY gp.defteam, pl.position
        ),
        player_opponents AS (
            SELECT DISTINCT gsis_id, defteam FROM combined_game_pts
        ),
        player_sos AS (
            SELECT po.gsis_id,
                   AVG(dvp.avg_pts_allowed) AS sos_pts_allowed
            FROM player_opponents po
            JOIN players pl ON pl.gsis_id = po.gsis_id
            JOIN def_vs_pos dvp ON dvp.defteam = po.defteam AND dvp.position = pl.position
            GROUP BY po.gsis_id
        )
        UPDATE player_features
        SET sos_pts_allowed = ps.sos_pts_allowed
        FROM player_sos ps
        WHERE player_features.gsis_id = ps.gsis_id
          AND player_features.season  = ?
    """, [prior_season, prior_season, target_season])
