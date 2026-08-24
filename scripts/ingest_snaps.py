#!/usr/bin/env python3
"""Ingest nflverse weekly snap count CSVs into snap_counts table.

Usage:
    uv run python scripts/ingest_snaps.py --start 2016 --end 2025

The nflverse snap_counts CSV uses pfr_player_id (PFR format, e.g. BrowSp00).
We download the nflverse players crosswalk to map pfr_id -> gsis_id.
"""
from __future__ import annotations
import argparse
import csv
import io
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from tay.db import get_conn, init_schema

_SNAP_CSV_URL = (
    'https://github.com/nflverse/nflverse-data/releases/download/'
    'snap_counts/snap_counts_{season}.csv'
)

_PLAYERS_CSV_URL = (
    'https://github.com/nflverse/nflverse-data/releases/download/'
    'players/players.csv'
)


def fetch_pfr_to_gsis_map() -> dict[str, str]:
    """Download nflverse players CSV and return {pfr_id: gsis_id} mapping."""
    resp = requests.get(_PLAYERS_CSV_URL, timeout=60)
    resp.raise_for_status()
    reader = csv.DictReader(io.StringIO(resp.text))
    mapping: dict[str, str] = {}
    for row in reader:
        pfr_id = row.get('pfr_id', '').strip()
        gsis_id = row.get('gsis_id', '').strip()
        if pfr_id and gsis_id:
            mapping[pfr_id] = gsis_id
    return mapping


def fetch_snap_csv(season: int, pfr_to_gsis: dict[str, str]) -> list[dict]:
    """Download nflverse snap count CSV for a season; return list of row dicts.

    Rows are keyed by gsis_id (mapped from pfr_player_id).
    Rows where no gsis_id mapping exists are skipped.
    """
    url = _SNAP_CSV_URL.format(season=season)
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    reader = csv.DictReader(io.StringIO(resp.text))
    rows = []
    skipped = 0
    for row in reader:
        pfr_id = row.get('pfr_player_id', '').strip()
        offense_pct_raw = row.get('offense_pct', '').strip()
        # Only keep offensive skill players with actual snap data
        if not pfr_id or not offense_pct_raw:
            continue
        try:
            offense_pct = float(offense_pct_raw)
        except ValueError:
            continue
        # Map to gsis_id; skip if not found
        gsis_id = pfr_to_gsis.get(pfr_id)
        if not gsis_id:
            skipped += 1
            continue
        try:
            rows.append({
                'player_id':     gsis_id,
                'season':        int(row['season']),
                'week':          int(row['week']),
                'offense_snaps': int(float(row.get('offense_snaps') or 0)),
                'offense_pct':   offense_pct,
            })
        except (ValueError, KeyError):
            continue
    return rows


def ingest_snap_season(conn, weekly_rows: list[dict], season: int) -> int:
    """Aggregate weekly snap rows to season level and upsert into snap_counts.

    Returns number of players inserted/updated.
    """
    from collections import defaultdict

    by_player: dict[str, dict] = defaultdict(lambda: {
        'total_snaps': 0, 'pct_sum': 0.0, 'games': 0
    })
    for row in weekly_rows:
        gsis_id = row['player_id']
        by_player[gsis_id]['total_snaps'] += row['offense_snaps']
        by_player[gsis_id]['pct_sum']     += row['offense_pct']
        by_player[gsis_id]['games']       += 1

    for gsis_id, agg in by_player.items():
        snap_share = agg['pct_sum'] / agg['games'] if agg['games'] > 0 else None
        conn.execute("""
            INSERT INTO snap_counts (gsis_id, season, snap_share, total_snaps, games_played)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (gsis_id, season) DO UPDATE SET
                snap_share   = excluded.snap_share,
                total_snaps  = excluded.total_snaps,
                games_played = excluded.games_played
        """, [gsis_id, season, snap_share, agg['total_snaps'], agg['games']])

    conn.commit()
    return len(by_player)


def main() -> None:
    p = argparse.ArgumentParser(description='Ingest nflverse snap count data')
    p.add_argument('--start', type=int, default=2016)
    p.add_argument('--end',   type=int, default=2025)
    args = p.parse_args()

    conn = get_conn()
    init_schema(conn)

    print('Downloading player ID crosswalk (pfr_id -> gsis_id)...', flush=True)
    try:
        pfr_to_gsis = fetch_pfr_to_gsis_map()
        print(f'  {len(pfr_to_gsis)} mappings loaded.')
    except Exception as e:
        print(f'FAILED to load player crosswalk: {e}')
        conn.close()
        return

    for season in range(args.start, args.end + 1):
        print(f'Fetching snap counts for {season}...', end=' ', flush=True)
        try:
            rows = fetch_snap_csv(season, pfr_to_gsis)
            n = ingest_snap_season(conn, rows, season)
            print(f'{n} players')
        except Exception as e:
            print(f'FAILED: {e}')

    conn.close()


if __name__ == '__main__':
    main()
