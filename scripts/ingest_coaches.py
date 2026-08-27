#!/usr/bin/env python3
"""Ingest nflverse coaches data and compute OC historical features.

Usage:
    uv run python scripts/ingest_coaches.py --seasons 2016 2017 ... 2026
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from tay.db import get_conn, init_schema


def fetch_coaches_data() -> list[dict]:
    """Fetch coaches from nflverse via nfl_data_py."""
    import nfl_data_py as nfl
    df = nfl.import_coaches()
    rows = []
    for _, row in df.iterrows():
        season = int(row.get('season', 0))
        team = str(row.get('team', ''))
        for coach_type in ('head_coach', 'offensive_coordinator'):
            col = coach_type  # nflverse column name matches
            name = str(row.get(col, '') or '')
            if name and name != 'nan':
                rows.append({
                    'team': team,
                    'season': season,
                    'coach_type': coach_type,
                    'full_name': name,
                })
    return rows


def upsert_coaches(conn, rows: list[dict]) -> int:
    conn.executemany("""
        INSERT INTO coaches (team, season, coach_type, full_name)
        VALUES (?, ?, ?, ?)
        ON CONFLICT (team, season, coach_type) DO UPDATE SET
            full_name = excluded.full_name
    """, [(r['team'], r['season'], r['coach_type'], r['full_name']) for r in rows])
    conn.commit()
    return len(rows)


def compute_oc_features(conn, seasons: list[int]) -> int:
    """For each season in `seasons`, aggregate OC historical stats from prior seasons.

    Looks up who the OC was at each team in season S-1, then aggregates their
    stats across ALL seasons they coordinated prior to season S.
    """
    total = 0
    for season in seasons:
        # Find all OCs active in any season prior to this one
        ocs = conn.execute("""
            SELECT DISTINCT full_name
            FROM coaches
            WHERE coach_type = 'offensive_coordinator'
              AND season < ?
        """, [season]).fetchall()

        for (oc_name,) in ocs:
            # Seasons this OC coordinated (all prior to `season`)
            oc_seasons = conn.execute("""
                SELECT c.team, c.season
                FROM coaches c
                WHERE c.full_name = ?
                  AND c.coach_type = 'offensive_coordinator'
                  AND c.season < ?
            """, [oc_name, season]).fetchall()

            if not oc_seasons:
                continue

            # For each OC season, compute WR1 target share and air yards pct
            wr1_shares = []
            air_yds_pcts = []
            rb_shares = []

            for team, oc_season in oc_seasons:
                team_att = conn.execute("""
                    SELECT pass_attempts FROM team_season_stats
                    WHERE team = ? AND season = ?
                """, [team, oc_season]).fetchone()
                if not team_att or not team_att[0]:
                    continue
                team_pass_att = float(team_att[0])

                # WR1 target share: max single-WR target share on this team x season
                wr1 = conn.execute("""
                    SELECT MAX(s.targets::DOUBLE / ?) AS share
                    FROM player_season_stats s
                    JOIN players p ON p.gsis_id = s.gsis_id
                    WHERE s.team = ? AND s.season = ? AND p.position = 'WR'
                """, [team_pass_att, team, oc_season]).fetchone()
                if wr1 and wr1[0]:
                    wr1_shares.append(float(wr1[0]))

                # Air yards pct: total WR/TE air_yards / total rec_yards
                ay = conn.execute("""
                    SELECT SUM(s.air_yards), SUM(s.rec_yards)
                    FROM player_season_stats s
                    JOIN players p ON p.gsis_id = s.gsis_id
                    WHERE s.team = ? AND s.season = ?
                      AND p.position IN ('WR', 'TE')
                """, [team, oc_season]).fetchone()
                if ay and ay[1] and float(ay[1]) > 0:
                    air_yds_pcts.append(float(ay[0] or 0) / float(ay[1]))

                # RB receiving share: sum of RB targets / team pass attempts
                rb = conn.execute("""
                    SELECT SUM(s.targets)::DOUBLE / ?
                    FROM player_season_stats s
                    JOIN players p ON p.gsis_id = s.gsis_id
                    WHERE s.team = ? AND s.season = ? AND p.position = 'RB'
                """, [team_pass_att, team, oc_season]).fetchone()
                if rb and rb[0]:
                    rb_shares.append(float(rb[0]))

            # Current team tenure: count consecutive seasons going back from season-1
            tenure_rows = conn.execute("""
                SELECT season FROM coaches
                WHERE full_name = ? AND coach_type = 'offensive_coordinator' AND season < ?
                ORDER BY season DESC
            """, [oc_name, season]).fetchall()
            tenure = 0
            prev_season = None
            for (s,) in tenure_rows:
                if prev_season is None:
                    prev_season = s
                    tenure = 1
                elif prev_season - s == 1:
                    tenure += 1
                    prev_season = s
                else:
                    break

            # is_rookie_oc: True if the OC has no prior NFL OC seasons (tenure == 0).
            # Consistent with tenure — an OC with prior seasons is not a rookie even if
            # their stats rows happened to be missing from player_season_stats.
            is_rookie = tenure == 0

            conn.execute("""
                INSERT INTO oc_features
                    (oc_name, as_of_season, hist_wr1_target_share, hist_air_yards_pct,
                     hist_rb_target_share, tenure_at_team, is_rookie_oc)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (oc_name, as_of_season) DO UPDATE SET
                    hist_wr1_target_share = excluded.hist_wr1_target_share,
                    hist_air_yards_pct    = excluded.hist_air_yards_pct,
                    hist_rb_target_share  = excluded.hist_rb_target_share,
                    tenure_at_team        = excluded.tenure_at_team,
                    is_rookie_oc          = excluded.is_rookie_oc
            """, [
                oc_name, season,
                (sum(wr1_shares) / len(wr1_shares)) if wr1_shares else None,
                (sum(air_yds_pcts) / len(air_yds_pcts)) if air_yds_pcts else None,
                (sum(rb_shares) / len(rb_shares)) if rb_shares else None,
                tenure,
                is_rookie,
            ])
            total += 1

        # Write oc_features for OCs appearing for the first time in this season.
        # They have no prior history, so all stats are NULL and is_rookie_oc=True.
        new_ocs = conn.execute("""
            SELECT DISTINCT full_name FROM coaches
            WHERE coach_type = 'offensive_coordinator' AND season = ?
              AND full_name NOT IN (
                  SELECT DISTINCT full_name FROM coaches
                  WHERE coach_type = 'offensive_coordinator' AND season < ?
              )
        """, [season, season]).fetchall()
        for (oc_name,) in new_ocs:
            conn.execute("""
                INSERT INTO oc_features
                    (oc_name, as_of_season, hist_wr1_target_share, hist_air_yards_pct,
                     hist_rb_target_share, tenure_at_team, is_rookie_oc)
                VALUES (?, ?, NULL, NULL, NULL, 0, TRUE)
                ON CONFLICT (oc_name, as_of_season) DO UPDATE SET
                    hist_wr1_target_share = NULL,
                    hist_air_yards_pct    = NULL,
                    hist_rb_target_share  = NULL,
                    tenure_at_team        = 0,
                    is_rookie_oc          = TRUE
            """, [oc_name, season])
            total += 1

        conn.commit()
    return total


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument('--seasons', type=int, nargs='+',
                   default=list(range(2016, 2027)),
                   help='Seasons to compute OC features for (default 2016-2026)')
    args = p.parse_args()

    conn = get_conn()
    init_schema(conn)

    print('Fetching coaches data from nflverse...')
    rows = fetch_coaches_data()
    n = upsert_coaches(conn, rows)
    print(f'  Upserted {n} coach rows.')

    print(f'Computing OC features for seasons {args.seasons}...')
    n = compute_oc_features(conn, args.seasons)
    print(f'  Computed {n} OC feature rows.')
    conn.close()


if __name__ == '__main__':
    main()
