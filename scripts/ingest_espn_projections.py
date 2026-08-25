#!/usr/bin/env python3
"""Ingest ESPN Fantasy API consensus projections.

Usage:
    uv run python scripts/ingest_espn_projections.py --season 2026

Fetches ESPN projected stats, matches players via espn_id, and upserts
to consensus_projections with source='espn'. Run before ingest_fantasypros.py
so the blend step picks up both sources.
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from tay.db import get_conn, init_schema

_ESPN_URL = (
    'https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{season}'
    '/players?scoringPeriodId=0&view=kona_player_info'
)

_ESPN_HEADERS = {
    'X-Fantasy-Filter': json.dumps({
        'players': {
            'filterStatsForSourceIds': {'value': [1]},
            'filterStatsForSplitTypeIds': {'value': [0]},
        }
    }),
    'User-Agent': 'Mozilla/5.0',
}

# ESPN numeric stat IDs → our field names
_STAT_MAP = {
    '3':  'pass_yards',
    '4':  'pass_tds',
    '20': 'interceptions',
    '24': 'rush_yards',
    '25': 'rush_tds',
    '41': 'receptions',
    '42': 'rec_yards',
    '43': 'rec_tds',
}


def _ppr(row: dict) -> float:
    return (
        row.get('pass_yards', 0.0)      * 0.04
        + row.get('pass_tds', 0.0)      * 4.0
        + row.get('interceptions', 0.0) * -2.0
        + row.get('rush_yards', 0.0)    * 0.1
        + row.get('rush_tds', 0.0)      * 6.0
        + row.get('receptions', 0.0)    * 1.0
        + row.get('rec_yards', 0.0)     * 0.1
        + row.get('rec_tds', 0.0)       * 6.0
    )


def parse_espn_response(data: dict) -> list[dict]:
    """Extract projected stats from ESPN API JSON.

    Only includes players that have a statSourceId=1 (projected) entry.
    Returns list of dicts with espn_id (str) and stat fields.
    """
    rows = []
    for player_entry in data.get('players', []):
        espn_id = str(player_entry.get('id', ''))
        player = player_entry.get('playerPoolEntry', {}).get('player', {})
        stats_list = player.get('stats', [])
        # Find the projected full-season stat entry
        proj_stats = next(
            (s for s in stats_list
             if s.get('statSourceId') == 1 and s.get('scoringPeriodId') == 0),
            None,
        )
        if proj_stats is None:
            continue
        raw_stats = proj_stats.get('stats', {})
        row: dict = {'espn_id': espn_id}
        for stat_id, field in _STAT_MAP.items():
            row[field] = float(raw_stats.get(stat_id, 0.0))
        row['points'] = _ppr(row)
        rows.append(row)
    return rows


def ingest_espn(conn, season: int) -> dict:
    """Fetch ESPN projections and upsert to consensus_projections (source='espn')."""
    print('Fetching ESPN projections...', flush=True)
    url = _ESPN_URL.format(season=season)
    resp = requests.get(url, headers=_ESPN_HEADERS, timeout=60)
    resp.raise_for_status()
    data = resp.json()

    rows = parse_espn_response(data)
    print(f'  Parsed {len(rows)} players with projected stats.', flush=True)

    # Build espn_id → gsis_id map from players table
    espn_to_gsis = {
        str(espn_id): gsis_id
        for gsis_id, espn_id in conn.execute(
            "SELECT gsis_id, espn_id FROM players WHERE espn_id IS NOT NULL"
        ).fetchall()
    }

    matched = 0
    unmatched = 0
    rows_to_upsert = []
    for row in rows:
        gsis_id = espn_to_gsis.get(row['espn_id'])
        if gsis_id is None:
            print(f'UNMATCHED ESPN ID: {row["espn_id"]}', file=sys.stderr)
            unmatched += 1
            continue
        rows_to_upsert.append((
            gsis_id, season, 'espn',
            row.get('pass_yards'),
            row.get('pass_tds'),
            row.get('interceptions'),
            row.get('rush_yards'),
            row.get('rush_tds'),
            row.get('receptions'),
            row.get('rec_yards'),
            row.get('rec_tds'),
            row['points'],
        ))
        matched += 1

    conn.executemany("""
        INSERT INTO consensus_projections
            (gsis_id, season, source,
             pass_yards, pass_tds, interceptions,
             rush_yards, rush_tds,
             receptions, rec_yards, rec_tds,
             points)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (gsis_id, season, source) DO UPDATE SET
            pass_yards    = excluded.pass_yards,
            pass_tds      = excluded.pass_tds,
            interceptions = excluded.interceptions,
            rush_yards    = excluded.rush_yards,
            rush_tds      = excluded.rush_tds,
            receptions    = excluded.receptions,
            rec_yards     = excluded.rec_yards,
            rec_tds       = excluded.rec_tds,
            points        = excluded.points,
            scraped_at    = current_timestamp
    """, rows_to_upsert)
    conn.commit()
    print(f'  Upserted {matched} ESPN rows ({unmatched} unmatched).', flush=True)
    return {'matched': matched, 'unmatched': unmatched}


def main() -> None:
    p = argparse.ArgumentParser(description='Ingest ESPN consensus projections')
    p.add_argument('--season', type=int, default=2026)
    args = p.parse_args()

    conn = get_conn()
    init_schema(conn)
    result = ingest_espn(conn, args.season)
    conn.close()
    print(f"\nDone. matched={result['matched']}, unmatched={result['unmatched']}")


if __name__ == '__main__':
    main()
