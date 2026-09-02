#!/usr/bin/env python3
"""Load pre-exported consensus projections CSV into DuckDB.

Usage:
    python scripts/ingest/load_consensus_snapshot.py --season 2026

This is the fallback for environments (like Render) where live ESPN/FantasyPros
ingestion may not be available. The CSV is generated locally via:
    python scripts/ingest/ingest_espn_projections.py --season 2026
    then exported from DuckDB to data/consensus_projections_2026.csv
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from tay.db import get_conn, init_schema


def main() -> None:
    p = argparse.ArgumentParser(description='Load consensus snapshot into DuckDB')
    p.add_argument('--season', type=int, default=2026)
    args = p.parse_args()

    csv_path = Path(__file__).parent.parent.parent / 'data' / f'consensus_projections_{args.season}.csv'
    if not csv_path.exists():
        print(f'No snapshot found at {csv_path} — skipping.')
        return

    conn = get_conn()
    init_schema(conn)

    conn.execute(f"DELETE FROM consensus_projections WHERE season = {args.season}")
    conn.execute(f"""
        INSERT INTO consensus_projections
            (gsis_id, season, source, pass_yards, pass_tds, interceptions,
             rush_yards, rush_tds, receptions, rec_yards, rec_tds, points)
        SELECT gsis_id, season, source, pass_yards, pass_tds, interceptions,
               rush_yards, rush_tds, receptions, rec_yards, rec_tds, points
        FROM read_csv_auto('{csv_path}')
    """)
    count = conn.execute(
        f"SELECT COUNT(*) FROM consensus_projections WHERE season = {args.season}"
    ).fetchone()[0]
    conn.commit()
    conn.close()
    print(f'Loaded {count} consensus rows for season {args.season}.')


if __name__ == '__main__':
    main()
