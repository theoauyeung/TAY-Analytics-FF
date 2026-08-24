#!/usr/bin/env python3
"""Ingest nflverse weekly snap count CSVs into snap_counts table.

Usage:
    uv run python scripts/ingest_snaps.py --start 2016 --end 2025
"""
from __future__ import annotations
import argparse
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


def fetch_snap_csv(season: int) -> list[dict]:
    """Download nflverse snap count CSV for a season; return list of row dicts."""
    url = _SNAP_CSV_URL.format(season=season)
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    import csv
    reader = csv.DictReader(io.StringIO(resp.text))
    rows = []
    for row in reader:
        if not row.get('player_id') or not row.get('offense_pct'):
            continue
        try:
            rows.append({
                'player_id':     row['player_id'],
                'season':        int(row['season']),
                'week':          int(row['week']),
                'offense_snaps': int(float(row.get('offense_snaps') or 0)),
                'offense_pct':   float(row['offense_pct']),
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

    for season in range(args.start, args.end + 1):
        print(f'Fetching snap counts for {season}...', end=' ', flush=True)
        try:
            rows = fetch_snap_csv(season)
            n = ingest_snap_season(conn, rows, season)
            print(f'{n} players')
        except Exception as e:
            print(f'FAILED: {e}')

    conn.close()


if __name__ == '__main__':
    main()
