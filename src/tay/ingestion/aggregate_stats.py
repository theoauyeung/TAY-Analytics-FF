"""Aggregate play-by-play data into per-player and per-team season stats."""
from __future__ import annotations
from pathlib import Path
import duckdb

from tay.db import get_conn, init_schema


def aggregate_player_stats(
    conn: duckdb.DuckDBPyConnection,
    seasons: list[int],
) -> None:
    """Aggregate PBP into player_season_stats. Overwrites existing rows for given seasons."""
    for season in seasons:
        conn.execute("DELETE FROM player_season_stats WHERE season = ?", [season])
        conn.execute("""
            INSERT INTO player_season_stats (
                gsis_id, season, team, games,
                attempts, completions, pass_yards, pass_tds, interceptions,
                carries, rush_yards, rush_tds,
                targets, receptions, rec_yards, rec_tds,
                air_yards, yards_after_catch, epa_per_play, cpoe,
                fantasy_points_ppr, fantasy_points_hppr, fantasy_points_std
            )
            WITH all_players AS (
                -- Passers
                SELECT passer_id AS gsis_id, posteam AS team, season, game_id,
                    SUM(pass_attempt)    AS attempts,
                    SUM(complete_pass)   AS completions,
                    SUM(CASE WHEN complete_pass=1 THEN yards_gained ELSE 0 END) AS pass_yards,
                    SUM(CASE WHEN play_type='pass' AND touchdown=1 THEN 1 ELSE 0 END) AS pass_tds,
                    SUM(interception)    AS interceptions,
                    0 AS carries, 0 AS rush_yards, 0 AS rush_tds,
                    0 AS targets, 0 AS receptions, 0 AS rec_yards, 0 AS rec_tds,
                    SUM(COALESCE(air_yards, 0)) AS air_yds,
                    0.0 AS yac,
                    AVG(epa) AS epa_pp,
                    AVG(cpoe) AS avg_cpoe
                FROM play_by_play
                WHERE season = ? AND season_type = 'REG'
                  AND passer_id IS NOT NULL AND play_type = 'pass'
                GROUP BY passer_id, posteam, season, game_id

                UNION ALL

                -- Rushers
                SELECT rusher_id, posteam, season, game_id,
                    0, 0, 0, 0, 0,
                    SUM(rush_attempt), SUM(yards_gained),
                    SUM(CASE WHEN play_type='run' AND touchdown=1 THEN 1 ELSE 0 END),
                    0, 0, 0, 0, 0.0, 0.0, AVG(epa), NULL
                FROM play_by_play
                WHERE season = ? AND season_type = 'REG'
                  AND rusher_id IS NOT NULL AND play_type = 'run'
                GROUP BY rusher_id, posteam, season, game_id

                UNION ALL

                -- Receivers
                SELECT receiver_id, posteam, season, game_id,
                    0, 0, 0, 0, 0, 0, 0, 0,
                    COUNT(*) AS targets,
                    SUM(complete_pass) AS receptions,
                    SUM(CASE WHEN complete_pass=1 THEN yards_gained ELSE 0 END),
                    SUM(CASE WHEN play_type='pass' AND touchdown=1 AND complete_pass=1 THEN 1 ELSE 0 END),
                    SUM(COALESCE(air_yards, 0)),
                    SUM(COALESCE(yards_after_catch, 0)),
                    AVG(epa), NULL
                FROM play_by_play
                WHERE season = ? AND season_type = 'REG'
                  AND receiver_id IS NOT NULL
                GROUP BY receiver_id, posteam, season, game_id
            ),
            agg_by_team AS (
                SELECT gsis_id, season, team,
                    COUNT(DISTINCT game_id) AS team_games,
                    SUM(attempts)     AS attempts,
                    SUM(completions)  AS completions,
                    SUM(pass_yards)   AS pass_yards,
                    SUM(pass_tds)     AS pass_tds,
                    SUM(interceptions) AS interceptions,
                    SUM(carries)      AS carries,
                    SUM(rush_yards)   AS rush_yards,
                    SUM(rush_tds)     AS rush_tds,
                    SUM(targets)      AS targets,
                    SUM(receptions)   AS receptions,
                    SUM(rec_yards)    AS rec_yards,
                    SUM(rec_tds)      AS rec_tds,
                    SUM(air_yds)      AS air_yards,
                    SUM(yac)          AS yards_after_catch,
                    AVG(epa_pp)       AS epa_per_play,
                    AVG(avg_cpoe)     AS cpoe
                FROM all_players
                WHERE gsis_id IS NOT NULL
                GROUP BY gsis_id, season, team
            ),
            -- Pick the team with the most games as the primary team
            primary_team AS (
                SELECT gsis_id, season,
                    FIRST(team ORDER BY team_games DESC) AS team
                FROM agg_by_team
                GROUP BY gsis_id, season
            ),
            agg AS (
                SELECT a.gsis_id, a.season, pt.team,
                    SUM(a.team_games)   AS games,
                    SUM(a.attempts)     AS attempts,
                    SUM(a.completions)  AS completions,
                    SUM(a.pass_yards)   AS pass_yards,
                    SUM(a.pass_tds)     AS pass_tds,
                    SUM(a.interceptions) AS interceptions,
                    SUM(a.carries)      AS carries,
                    SUM(a.rush_yards)   AS rush_yards,
                    SUM(a.rush_tds)     AS rush_tds,
                    SUM(a.targets)      AS targets,
                    SUM(a.receptions)   AS receptions,
                    SUM(a.rec_yards)    AS rec_yards,
                    SUM(a.rec_tds)      AS rec_tds,
                    SUM(a.air_yards)    AS air_yards,
                    SUM(a.yards_after_catch) AS yards_after_catch,
                    AVG(a.epa_per_play) AS epa_per_play,
                    AVG(a.cpoe)         AS cpoe
                FROM agg_by_team a
                JOIN primary_team pt ON a.gsis_id = pt.gsis_id AND a.season = pt.season
                GROUP BY a.gsis_id, a.season, pt.team
            )
            SELECT
                gsis_id, season, team, games,
                attempts, completions, pass_yards, pass_tds, interceptions,
                carries, rush_yards, rush_tds,
                targets, receptions, rec_yards, rec_tds,
                air_yards, yards_after_catch, epa_per_play, cpoe,
                -- PPR: 1pt/rec + 0.1pt/yard + 6pt/TD (pass: 0.04pt/yard, 6pt/TD, -2pt/INT)
                (pass_yards * 0.04 + pass_tds * 6 - interceptions * 2
                 + rush_yards * 0.1 + rush_tds * 6
                 + receptions * 1 + rec_yards * 0.1 + rec_tds * 6) AS fantasy_points_ppr,
                (pass_yards * 0.04 + pass_tds * 6 - interceptions * 2
                 + rush_yards * 0.1 + rush_tds * 6
                 + receptions * 0.5 + rec_yards * 0.1 + rec_tds * 6) AS fantasy_points_hppr,
                (pass_yards * 0.04 + pass_tds * 6 - interceptions * 2
                 + rush_yards * 0.1 + rush_tds * 6
                 + rec_yards * 0.1 + rec_tds * 6) AS fantasy_points_std
            FROM agg
        """, [season, season, season])

    conn.commit()


def aggregate_team_stats(
    conn: duckdb.DuckDBPyConnection,
    seasons: list[int],
) -> None:
    """Aggregate PBP into team_season_stats."""
    for season in seasons:
        conn.execute("DELETE FROM team_season_stats WHERE season = ?", [season])
        conn.execute("""
            INSERT INTO team_season_stats (
                team, season, games, total_plays, pass_attempts, rush_attempts,
                pass_rate, total_tds, pass_tds, rush_tds, points_scored,
                team_epa, pass_epa, rush_epa
            )
            SELECT
                posteam AS team,
                season,
                COUNT(DISTINCT game_id) AS games,
                COUNT(*) AS total_plays,
                SUM(pass_attempt) AS pass_attempts,
                SUM(rush_attempt) AS rush_attempts,
                AVG(pass_attempt) AS pass_rate,
                SUM(touchdown) AS total_tds,
                SUM(CASE WHEN play_type='pass' AND touchdown=1 THEN 1 ELSE 0 END) AS pass_tds,
                SUM(CASE WHEN play_type='run' AND touchdown=1 THEN 1 ELSE 0 END) AS rush_tds,
                SUM(touchdown) * 7.0 AS points_scored,
                AVG(epa) AS team_epa,
                AVG(CASE WHEN play_type='pass' THEN epa END) AS pass_epa,
                AVG(CASE WHEN play_type='run' THEN epa END) AS rush_epa
            FROM play_by_play
            WHERE season = ? AND season_type = 'REG' AND posteam IS NOT NULL
            GROUP BY posteam, season
        """, [season])

    conn.commit()


def ingest(
    start: int = 2005,
    end: int = 2025,
    db_path=None,
) -> None:
    """Run stat aggregation for all seasons."""
    conn = get_conn(db_path) if db_path else get_conn()
    seasons = list(range(start, end + 1))

    print("Aggregating player season stats...")
    aggregate_player_stats(conn, seasons)

    print("Aggregating team season stats...")
    aggregate_team_stats(conn, seasons)

    conn.close()
    print("Aggregation complete.")


if __name__ == "__main__":
    ingest()
