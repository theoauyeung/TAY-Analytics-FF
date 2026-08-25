#!/usr/bin/env python3
"""Ingest FantasyPros consensus projections and refresh rankings.

Usage:
    uv run python scripts/ingest_fantasypros.py --season 2026

Orchestrates the full consensus refresh:
  1. Scrape FantasyPros (4 positions)
  2. Match player names to gsis_id via fuzzy matching
  3. Upsert to consensus_projections (source='fantasypros')
  4. Call blend_projections()
  5. Call compute_vor()
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from tay.db import get_conn, init_schema
from tay.projections.blend import blend_projections
from tay.projections.name_match import normalize_name, match_player
from tay.valuation.pipeline import run_valuation
from tay.valuation.replacement import ReplacementConfig

_FP_URLS = {
    'QB': 'https://www.fantasypros.com/nfl/projections/qb.php?week=draft&scoring=PPR',
    'RB': 'https://www.fantasypros.com/nfl/projections/rb.php?week=draft&scoring=PPR',
    'WR': 'https://www.fantasypros.com/nfl/projections/wr.php?week=draft&scoring=PPR',
    'TE': 'https://www.fantasypros.com/nfl/projections/te.php?week=draft&scoring=PPR',
}

# Stat column indices (0-based, after the Player column) per position
_COL_IDX = {
    'QB': {'pass_yards': 2, 'pass_tds': 3, 'interceptions': 4, 'rush_yards': 6, 'rush_tds': 7},
    'RB': {'rush_yards': 1, 'rush_tds': 2, 'receptions': 3, 'rec_yards': 4, 'rec_tds': 5},
    'WR': {'receptions': 0, 'rec_yards': 1, 'rec_tds': 2, 'rush_yards': 4, 'rush_tds': 5},
    'TE': {'receptions': 0, 'rec_yards': 1, 'rec_tds': 2},
}


def _ppr(row: dict) -> float:
    return (
        row.get('pass_yards', 0.0)    * 0.04
        + row.get('pass_tds', 0.0)   * 4.0
        + row.get('interceptions', 0.0) * -2.0
        + row.get('rush_yards', 0.0)  * 0.1
        + row.get('rush_tds', 0.0)   * 6.0
        + row.get('receptions', 0.0) * 1.0
        + row.get('rec_yards', 0.0)  * 0.1
        + row.get('rec_tds', 0.0)    * 6.0
    )


def scrape_position(html: str, position: str) -> list[dict]:
    """Parse FantasyPros projection HTML for one position.

    Returns list of dicts with 'name' and stat fields; 'points' is PPR total.
    """
    soup = BeautifulSoup(html, 'lxml')
    table = soup.find('table', id='data')
    if table is None:
        return []
    rows = []
    for tr in table.find('tbody').find_all('tr'):
        cells = tr.find_all('td')
        if not cells:
            continue
        # Player name is in an <a> tag in the first cell
        a_tag = cells[0].find('a')
        if a_tag is None:
            continue
        name = a_tag.get_text(strip=True)
        # Stat cells start at index 1
        stat_cells = cells[1:]
        col_map = _COL_IDX.get(position, {})
        stat: dict = {'name': name}
        for field, idx in col_map.items():
            if idx < len(stat_cells):
                raw = stat_cells[idx].get_text(strip=True).replace(',', '')
                try:
                    stat[field] = float(raw)
                except ValueError:
                    stat[field] = 0.0
            else:
                stat[field] = 0.0
        stat['points'] = _ppr(stat)
        rows.append(stat)
    return rows


def fetch_and_scrape(position: str) -> list[dict]:
    url = _FP_URLS[position]
    resp = requests.get(url, timeout=30, headers={'User-Agent': 'Mozilla/5.0'})
    resp.raise_for_status()
    return scrape_position(resp.text, position)


def ingest_fantasypros(conn, season: int, model_version: str = 'neural-v1') -> dict:
    """Scrape FP, match names, upsert consensus_projections, blend, run VOR."""
    # Load all players for name matching
    db_players_raw = conn.execute(
        "SELECT gsis_id, name FROM players WHERE position IN ('QB','RB','WR','TE')"
    ).fetchall()
    db_players = [(gsis_id, normalize_name(name)) for gsis_id, name in db_players_raw]

    matched = 0
    unmatched = 0
    rows_to_upsert = []

    for pos in ['QB', 'RB', 'WR', 'TE']:
        print(f'Scraping FantasyPros {pos}...', flush=True)
        try:
            fp_rows = fetch_and_scrape(pos)
        except Exception as e:
            print(f'  FAILED: {e}', file=sys.stderr)
            continue

        for row in fp_rows:
            gsis_id = match_player(row['name'], db_players)
            if gsis_id is None:
                print(f'UNMATCHED: {row["name"]}', file=sys.stderr)
                unmatched += 1
                continue
            rows_to_upsert.append((
                gsis_id, season, 'fantasypros',
                row.get('pass_yards', None),
                row.get('pass_tds', None),
                row.get('interceptions', None),
                row.get('rush_yards', None),
                row.get('rush_tds', None),
                row.get('receptions', None),
                row.get('rec_yards', None),
                row.get('rec_tds', None),
                row['points'],
            ))
            matched += 1
        print(f'  {pos}: {len(fp_rows)} players scraped', flush=True)

    conn.executemany("""
        INSERT INTO consensus_projections
            (gsis_id, season, source,
             pass_yards, pass_tds, interceptions,
             rush_yards, rush_tds,
             receptions, rec_yards, rec_tds,
             points)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (gsis_id, season, source) DO UPDATE SET
            pass_yards    = COALESCE(excluded.pass_yards,    consensus_projections.pass_yards),
            pass_tds      = COALESCE(excluded.pass_tds,      consensus_projections.pass_tds),
            interceptions = COALESCE(excluded.interceptions, consensus_projections.interceptions),
            rush_yards    = COALESCE(excluded.rush_yards,    consensus_projections.rush_yards),
            rush_tds      = COALESCE(excluded.rush_tds,      consensus_projections.rush_tds),
            receptions    = COALESCE(excluded.receptions,    consensus_projections.receptions),
            rec_yards     = COALESCE(excluded.rec_yards,     consensus_projections.rec_yards),
            rec_tds       = COALESCE(excluded.rec_tds,       consensus_projections.rec_tds),
            points        = excluded.points,
            scraped_at    = current_timestamp
    """, rows_to_upsert)
    conn.commit()
    print(f'Upserted {matched} consensus rows ({unmatched} unmatched).', flush=True)

    print('Blending projections...', flush=True)
    blended = blend_projections(conn, season, model_version)
    print(f'  {blended} players received a blended projection.', flush=True)

    print('Recomputing VOR...', flush=True)
    config = ReplacementConfig()
    result = run_valuation(conn, season=season, model_version=model_version, config=config)

    return {
        'matched': matched,
        'unmatched': unmatched,
        'blended': blended,
        'vor_rows': result['vor_rows'],
    }


def main() -> None:
    p = argparse.ArgumentParser(description='Ingest FantasyPros consensus projections')
    p.add_argument('--season', type=int, default=2026)
    p.add_argument('--model-version', type=str, default='neural-v1')
    args = p.parse_args()

    conn = get_conn()
    init_schema(conn)
    result = ingest_fantasypros(conn, args.season, args.model_version)
    conn.close()
    print(f"\nDone. matched={result['matched']}, unmatched={result['unmatched']}, "
          f"blended={result['blended']}, vor_rows={result['vor_rows']}")


if __name__ == '__main__':
    main()
