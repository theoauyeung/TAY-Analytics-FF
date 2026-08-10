"""Build player-level features for the projection model."""
from __future__ import annotations
import math
from datetime import date
import duckdb
from tay.db import get_conn, init_schema

SKILL_POSITIONS = ("'QB'", "'RB'", "'WR'", "'TE'")
SKILL_POS_SQL = f"({', '.join(SKILL_POSITIONS)})"

_LAG_COLUMNS = [
    ('lag2_fantasy_ppr', 'DOUBLE'),
    ('lag2_targets',     'INTEGER'),
    ('lag2_carries',     'INTEGER'),
    ('lag2_pass_yards',  'DOUBLE'),
    ('lag3_fantasy_ppr', 'DOUBLE'),
    ('lag3_targets',     'INTEGER'),
    ('lag3_carries',     'INTEGER'),
    ('lag3_pass_yards',  'DOUBLE'),
    ('ewma_fantasy_ppr', 'DOUBLE'),
    ('ewma_targets',     'DOUBLE'),
    ('ewma_carries',     'DOUBLE'),
    ('ewma_pass_yards',  'DOUBLE'),
]


def _migrate_player_features(conn: duckdb.DuckDBPyConnection) -> None:
    """Add new lag/EWMA columns to an existing player_features table."""
    for col, dtype in _LAG_COLUMNS:
        conn.execute(
            f'ALTER TABLE player_features ADD COLUMN IF NOT EXISTS {col} {dtype}'
        )


def _draft_pick_value(overall_pick: int | None) -> float:
    """Non-linear pick value: 1/sqrt(pick). 0 for undrafted."""
    if overall_pick and overall_pick > 0:
        return 1.0 / math.sqrt(overall_pick)
    return 0.0


def _age_on_sept_1(birth_date_str: str | None, season: int) -> float | None:
    """Age in years as of September 1 of the target season."""
    if not birth_date_str:
        return None
    try:
        bd = date.fromisoformat(str(birth_date_str))
        sep1 = date(season, 9, 1)
        return (sep1 - bd).days / 365.25
    except (ValueError, TypeError):
        return None


def build_player_features(
    conn: duckdb.DuckDBPyConnection,
    target_seasons: list[int],
) -> int:
    """Build player_features rows for each target season.

    For season N: uses N-1 as lag, N-2 and N-1 for rolling avg, N as target.
    Returns total number of rows inserted.
    """
    _migrate_player_features(conn)
    total = 0
    for season in target_seasons:
        prior = season - 1
        prior2 = season - 2
        conn.execute("DELETE FROM player_features WHERE season = ?", [season])

        # Get all skill-position players who have prior season stats
        players = conn.execute(f"""
            SELECT DISTINCT s.gsis_id, p.position, p.birth_date,
                p.draft_round, p.draft_pick, p.draft_year
            FROM player_season_stats s
            JOIN players p ON s.gsis_id = p.gsis_id
            WHERE s.season = ? AND p.position IN {SKILL_POS_SQL}
        """, [prior]).fetchall()

        for gsis_id, position, birth_date, draft_round, draft_pick, draft_year in players:
            # Prior season (N-1) stats
            s1 = conn.execute("""
                SELECT games, targets, receptions, rec_yards, rec_tds, air_yards,
                       yards_after_catch, carries, rush_yards, rush_tds,
                       attempts, completions, pass_yards, pass_tds, interceptions,
                       fantasy_points_ppr, epa_per_play, cpoe, team
                FROM player_season_stats WHERE gsis_id = ? AND season = ?
            """, [gsis_id, prior]).fetchone()
            if not s1:
                continue

            (games, targets, recs, rec_yards, rec_tds, air_yards, yac,
             carries, rush_yards, rush_tds, attempts, comps, pass_yards,
             pass_tds, ints, fpts, epa, cpoe, team) = s1

            # Two-seasons-ago (N-2) stats for rolling average
            s2 = conn.execute("""
                SELECT fantasy_points_ppr, targets, carries
                FROM player_season_stats WHERE gsis_id = ? AND season = ?
            """, [gsis_id, prior2]).fetchone()

            # Target: season N actual
            target_row = conn.execute("""
                SELECT fantasy_points_ppr, games
                FROM player_season_stats WHERE gsis_id = ? AND season = ?
            """, [gsis_id, season]).fetchone()

            # Rate stats (guard div by zero)
            g = max(games or 1, 1)
            t = targets or 0
            c = carries or 0
            r = recs or 0
            a = attempts or 0

            catch_rate = recs / t if t > 0 else None
            ypt = rec_yards / t if t > 0 else None
            ypc = rush_yards / c if c > 0 else None
            ayp = air_yards / t if t > 0 else None
            yac_pr = yac / r if r > 0 else None
            comp_pct = comps / a if a > 0 else None
            ypa = pass_yards / a if a > 0 else None
            td_rate_rec = rec_tds / t if t > 0 else None
            td_rate_rush = rush_tds / c if c > 0 else None

            # Rolling 2-year averages
            if s2:
                roll2_fpts = ((fpts or 0) + (s2[0] or 0)) / 2.0
                roll2_targets = (t + (s2[1] or 0)) / 2.0
                roll2_carries = (c + (s2[2] or 0)) / 2.0
            else:
                roll2_fpts = float(fpts or 0)
                roll2_targets = float(t)
                roll2_carries = float(c)

            # Team environment (use season N team features — the prior-year env for next season)
            tf = conn.execute("""
                SELECT pass_rate, pass_epa, total_plays
                FROM team_features WHERE team = ? AND season = ?
            """, [team, season]).fetchone()
            team_pass_rate = tf[0] if tf else None
            team_pass_epa = tf[1] if tf else None
            team_plays = tf[2] if tf else None

            # Depth chart position from rosters (prior season, week 1)
            dc = conn.execute("""
                SELECT depth_chart_pos FROM rosters
                WHERE gsis_id = ? AND season = ? AND week = 1
                ORDER BY week LIMIT 1
            """, [gsis_id, prior]).fetchone()
            depth = dc[0] if dc else None

            # Rookie flag: drafted in target season means first NFL season
            is_rookie = 1 if draft_year == season else 0

            # Draft pick value (compute overall_pick from round + pick)
            overall = None
            if draft_round and draft_pick:
                overall = (draft_round - 1) * 32 + draft_pick
            pick_value = _draft_pick_value(overall)

            # Combine data (gracefully handle empty table)
            try:
                comb = conn.execute("""
                    SELECT forty_yard, vertical FROM combine_data
                    WHERE gsis_id = ? ORDER BY season LIMIT 1
                """, [gsis_id]).fetchone()
                forty = comb[0] if comb else None
                vertical = comb[1] if comb else None
            except Exception:
                forty = None
                vertical = None

            age = _age_on_sept_1(birth_date, season)
            experience = (season - draft_year) if draft_year else None

            conn.execute("""
                INSERT OR REPLACE INTO player_features (
                    gsis_id, season, position, age, experience,
                    prev_games, prev_targets, prev_receptions, prev_rec_yards, prev_rec_tds,
                    prev_air_yards, prev_yac, prev_carries, prev_rush_yards, prev_rush_tds,
                    prev_attempts, prev_completions, prev_pass_yards, prev_pass_tds,
                    prev_interceptions, prev_fantasy_ppr,
                    targets_per_game, catches_per_game, rec_yards_per_game, rec_tds_per_game,
                    carries_per_game, rush_yards_per_game,
                    catch_rate, yards_per_target, yards_per_carry,
                    air_yards_per_target, yac_per_reception,
                    pass_completion_pct, pass_yards_per_attempt,
                    td_rate_receiving, td_rate_rushing,
                    prev_epa_per_play, prev_cpoe,
                    roll2_fantasy_ppr, roll2_targets, roll2_carries,
                    team, team_pass_rate, team_pass_epa, team_total_plays,
                    depth_chart_pos, is_rookie, draft_round, draft_pick, draft_pick_value,
                    combine_forty, combine_vertical,
                    next_season_fantasy_ppr, next_season_games
                ) VALUES (
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?
                )
            """, [
                gsis_id, season, position, age, experience,
                games, targets, recs, rec_yards, rec_tds,
                air_yards, yac, carries, rush_yards, rush_tds,
                attempts, comps, pass_yards, pass_tds, ints,
                fpts,
                t / g, r / g, (rec_yards or 0) / g, (rec_tds or 0) / g,
                c / g, (rush_yards or 0) / g,
                catch_rate, ypt, ypc, ayp, yac_pr,
                comp_pct, ypa, td_rate_rec, td_rate_rush,
                epa, cpoe,
                roll2_fpts, roll2_targets, roll2_carries,
                team, team_pass_rate, team_pass_epa, team_plays,
                depth, is_rookie, draft_round, draft_pick, pick_value,
                forty, vertical,
                target_row[0] if target_row else None,
                target_row[1] if target_row else None,
            ])
            total += 1

        conn.commit()
        print(f"  Season {season}: {total} player-feature rows built so far")

    return total


def ingest(start: int = 2006, end: int = 2025, db_path=None) -> None:
    conn = get_conn(db_path) if db_path else get_conn()
    init_schema(conn)
    n = build_player_features(conn, list(range(start, end + 1)))
    print(f"player_features: {n:,} rows built")
    conn.close()


if __name__ == "__main__":
    ingest()
