#!/usr/bin/env python3
"""Collect Sleeper public league draft + standings data for future model training.

Discovers leagues by fanning out from a seed username, then for each league
fetches draft picks and final standings. Data is stored in ff.duckdb for later
feature engineering.

Usage:
    python scripts/ingest/ingest_sleeper_leagues.py --username <sleeper_username> --season 2024
    python scripts/ingest/ingest_sleeper_leagues.py --season 2024 --max-leagues 5000
"""
from __future__ import annotations
import argparse
import sys
import time
from pathlib import Path

import requests
import duckdb

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))
from tay.db import get_conn, init_schema

BASE = 'https://api.sleeper.app/v1'
SESSION = requests.Session()
SESSION.headers['User-Agent'] = 'TAY-Analytics/1.0 (research)'


def _get(path: str, retries: int = 3) -> dict | list | None:
    for attempt in range(retries):
        try:
            r = SESSION.get(f'{BASE}{path}', timeout=15)
            if r.status_code == 429:
                time.sleep(2 ** attempt)
                continue
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.json()
        except requests.RequestException:
            time.sleep(1)
    return None


def init_league_tables(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sleeper_leagues (
            league_id       VARCHAR PRIMARY KEY,
            season          INTEGER,
            name            VARCHAR,
            scoring_settings VARCHAR,
            roster_positions VARCHAR,
            total_rosters   INTEGER,
            status          VARCHAR,
            fetched_at      TIMESTAMP DEFAULT current_timestamp
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sleeper_draft_picks (
            draft_id        VARCHAR,
            league_id       VARCHAR,
            season          INTEGER,
            pick_no         INTEGER,
            round           INTEGER,
            pick_in_round   INTEGER,
            roster_id       INTEGER,
            sleeper_player_id VARCHAR,
            position        VARCHAR,
            adp_at_draft    DOUBLE,
            PRIMARY KEY (draft_id, pick_no)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sleeper_rosters (
            league_id       VARCHAR,
            roster_id       INTEGER,
            season          INTEGER,
            wins            INTEGER,
            losses          INTEGER,
            points_for      DOUBLE,
            points_against  DOUBLE,
            playoff_finish  INTEGER,
            PRIMARY KEY (league_id, roster_id)
        )
    """)
    conn.commit()


def fetch_user_leagues(username: str, season: int) -> list[str]:
    user = _get(f'/user/{username}')
    if not user:
        return []
    uid = user.get('user_id')
    leagues = _get(f'/user/{uid}/leagues/nfl/{season}') or []
    return [lg['league_id'] for lg in leagues if lg.get('league_id')]


def ingest_league(conn: duckdb.DuckDBPyConnection, league_id: str, season: int) -> bool:
    # Skip if already collected
    exists = conn.execute(
        'SELECT 1 FROM sleeper_leagues WHERE league_id = ?', [league_id]
    ).fetchone()
    if exists:
        return False

    league = _get(f'/league/{league_id}')
    if not league or league.get('season') != str(season):
        return False

    scoring = str(league.get('scoring_settings', {}).get('rec', 0))
    positions = ','.join(league.get('roster_positions', []))
    total = league.get('total_rosters', 0)

    # Only standard-ish leagues (10-14 teams, skill positions present)
    if total < 8 or total > 16:
        return False
    if 'QB' not in positions or 'RB' not in positions:
        return False

    conn.execute("""
        INSERT OR IGNORE INTO sleeper_leagues
            (league_id, season, name, scoring_settings, roster_positions, total_rosters, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, [league_id, season, league.get('name', ''), scoring, positions,
          total, league.get('status', '')])

    # Rosters / standings
    rosters = _get(f'/league/{league_id}/rosters') or []
    for r in rosters:
        s = r.get('settings', {})
        conn.execute("""
            INSERT OR REPLACE INTO sleeper_rosters
                (league_id, roster_id, season, wins, losses, points_for, points_against, playoff_finish)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, [league_id, r['roster_id'], season,
              s.get('wins', 0), s.get('losses', 0),
              s.get('fpts', 0) + s.get('fpts_decimal', 0) / 100,
              s.get('fpts_against', 0) + s.get('fpts_against_decimal', 0) / 100,
              s.get('rank', 0)])

    # Drafts
    drafts = _get(f'/league/{league_id}/drafts') or []
    for draft in drafts:
        draft_id = draft.get('draft_id')
        if not draft_id:
            continue
        picks = _get(f'/draft/{draft_id}/picks') or []
        for pick in picks:
            md = pick.get('metadata', {})
            conn.execute("""
                INSERT OR IGNORE INTO sleeper_draft_picks
                    (draft_id, league_id, season, pick_no, round, pick_in_round,
                     roster_id, sleeper_player_id, position, adp_at_draft)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [draft_id, league_id, season,
                  pick.get('pick_no', 0), pick.get('round', 0),
                  pick.get('draft_slot', 0), pick.get('roster_id', 0),
                  pick.get('player_id', ''), md.get('position', ''),
                  float(pick.get('pick_no', 0))])  # pick_no as ADP proxy until we enrich

    conn.commit()
    return True


def discover_leagues(seed_username: str, season: int, max_leagues: int) -> list[str]:
    """Fan out from seed user's leaguemates to discover public leagues."""
    seen_users: set[str] = set()
    seen_leagues: set[str] = set()
    queue: list[str] = []

    # Start from seed user
    user = _get(f'/user/{seed_username}')
    if user:
        seed_uid = user.get('user_id', '')
        seen_users.add(seed_uid)
        leagues = _get(f'/user/{seed_uid}/leagues/nfl/{season}') or []
        for lg in leagues:
            lid = lg.get('league_id')
            if lid and lid not in seen_leagues:
                seen_leagues.add(lid)
                queue.append(lid)
                # Get other users in this league to fan out
                rosters = _get(f'/league/{lid}/rosters') or []
                users_in_league = _get(f'/league/{lid}/users') or []
                for u in users_in_league:
                    uid = u.get('user_id')
                    if uid and uid not in seen_users:
                        seen_users.add(uid)
                        user_leagues = _get(f'/user/{uid}/leagues/nfl/{season}') or []
                        for ulg in user_leagues:
                            ulid = ulg.get('league_id')
                            if ulid and ulid not in seen_leagues and len(seen_leagues) < max_leagues:
                                seen_leagues.add(ulid)
                                queue.append(ulid)
                        time.sleep(0.1)
        time.sleep(0.2)

    print(f'  Discovered {len(seen_leagues)} leagues from {len(seen_users)} users')
    return list(seen_leagues)[:max_leagues]


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--username', default='', help='Sleeper username to seed discovery')
    p.add_argument('--season', type=int, default=2024)
    p.add_argument('--max-leagues', type=int, default=2000)
    args = p.parse_args()

    conn = get_conn()
    init_schema(conn)
    init_league_tables(conn)

    if not args.username:
        print('No username provided — pass --username <sleeper_username> to seed discovery')
        conn.close()
        return

    print(f'Discovering leagues from @{args.username} for {args.season} season...')
    league_ids = discover_leagues(args.username, args.season, args.max_leagues)
    print(f'Processing {len(league_ids)} leagues...')

    ingested = 0
    skipped = 0
    for i, lid in enumerate(league_ids, 1):
        ok = ingest_league(conn, lid, args.season)
        if ok:
            ingested += 1
        else:
            skipped += 1
        if i % 100 == 0:
            already = conn.execute('SELECT COUNT(*) FROM sleeper_leagues').fetchone()[0]
            picks = conn.execute('SELECT COUNT(*) FROM sleeper_draft_picks').fetchone()[0]
            print(f'  [{i}/{len(league_ids)}] leagues={already:,}  picks={picks:,}')
        time.sleep(0.15)  # ~6-7 req/s — well within Sleeper's rate limit

    final_leagues = conn.execute('SELECT COUNT(*) FROM sleeper_leagues').fetchone()[0]
    final_picks = conn.execute('SELECT COUNT(*) FROM sleeper_draft_picks').fetchone()[0]
    final_rosters = conn.execute('SELECT COUNT(*) FROM sleeper_rosters').fetchone()[0]
    print(f'\nDone. leagues={final_leagues:,}  picks={final_picks:,}  rosters={final_rosters:,}')
    conn.close()


if __name__ == '__main__':
    main()
