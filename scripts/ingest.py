#!/usr/bin/env python3
"""
Full ingestion pipeline — populates data/ff.duckdb.

Usage:
    python scripts/ingest.py [--seasons 2005-2025] [--skip-pbp] [--season-only 2024]

Steps:
    1. Initialize DuckDB schema
    2. Pull NFLFastR play-by-play (R script)
    3. Load PBP into DuckDB
    4. Ingest nfl-data-py (players, rosters, draft picks)
    5. Aggregate player + team season stats
    6. Ingest Sleeper API (player IDs only)
    7. Ingest FantasyCalc consensus ADP (all positions, no auth required)
    8. Scrape PFR combine data
"""
import argparse
import sys
import time
from pathlib import Path

# Ensure src/ is on the path when running as script
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tay.db import get_conn, init_schema
from tay.ingestion import (
    nflfastr,
    nfl_data_py_ingest,
    aggregate_stats,
    sleeper,
    pfr,
)
from tay.ingestion import fantasycalc, espn as espn_ingest


def parse_args():
    p = argparse.ArgumentParser(description="TAY Analytics FF — data ingestion pipeline")
    p.add_argument("--start", type=int, default=2005, help="First season (default 2005)")
    p.add_argument("--end", type=int, default=2025, help="Last season (default 2025)")
    p.add_argument("--skip-pbp", action="store_true", help="Skip NFLFastR download (use cached parquet)")
    p.add_argument("--skip-pfr", action="store_true", help="Skip PFR scraping")
    p.add_argument("--adp-season", type=int, default=2026, help="Season for ADP data (default 2026)")
    return p.parse_args()


def step(name: str):
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")


def main():
    args = parse_args()
    start = time.time()

    step("1. Initializing DuckDB schema")
    conn = get_conn()
    init_schema(conn)
    conn.close()
    print("  Schema ready.")

    step("2-3. NFLFastR play-by-play")
    nflfastr.ingest(
        start=args.start,
        end=args.end,
        skip_download=args.skip_pbp,
    )

    step("4. nfl-data-py (players, rosters, draft picks)")
    nfl_data_py_ingest.ingest(start=args.start, end=args.end)

    step("5. Aggregate player + team season stats")
    aggregate_stats.ingest(start=args.start, end=args.end)

    step("6. Sleeper API (player ID mapping)")
    sleeper.ingest(season=args.adp_season)

    step("7. FantasyCalc consensus ADP (all positions)")
    fantasycalc.ingest(season=args.adp_season)

    step("7b. ESPN ADP (PPR)")
    espn_ingest.ingest(season=args.adp_season, format_='ppr')

    if not args.skip_pfr:
        step("8. PFR combine data")
        pfr.ingest(start=args.start, end=args.end)

    elapsed = time.time() - start
    print(f"\n{'='*60}")
    print(f"  Ingestion complete in {elapsed/60:.1f} minutes")
    print(f"  Database: data/ff.duckdb")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
