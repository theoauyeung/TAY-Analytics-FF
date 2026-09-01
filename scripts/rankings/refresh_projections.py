#!/usr/bin/env python3
"""Refresh ADP data and recompute projections + valuations.

Runs in ~30 seconds. Use this whenever you want to pull the latest
consensus ADP from FantasyCalc and regenerate the full rankings.

Usage:
    python scripts/rankings/refresh_projections.py [--season 2026] [--epochs 150] [--teams 12]
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from tay.db import get_conn, init_schema
from tay.ingestion import espn, fantasycalc
from tay.models.pipeline import write_projections
from tay.valuation.pipeline import run_valuation
from tay.valuation.replacement import ReplacementConfig


def main():
    p = argparse.ArgumentParser(description="Refresh ADP + projections")
    p.add_argument("--season",        type=int, default=2026)
    p.add_argument("--model-version", default="neural-v1")
    p.add_argument("--teams",         type=int, default=12)
    p.add_argument("--retrain",       action="store_true",
                   help="Re-train models before writing projections (slow, ~30s extra)")
    p.add_argument("--epochs",        type=int, default=150,
                   help="Epochs if --retrain is set (default 150)")
    args = p.parse_args()

    start = time.time()
    conn = get_conn()
    init_schema(conn)

    print(f"=== TAY Analytics FF — Projection Refresh (season {args.season}) ===\n")

    # Step 1: fresh ADP
    print("Step 1/3: Fetching ADP (FantasyCalc + ESPN)...")
    conn.execute("DELETE FROM adp WHERE season = ? AND platform = 'fantasycalc'", [args.season])
    conn.execute("DELETE FROM adp WHERE season = ? AND platform = 'espn'", [args.season])
    conn.commit()
    conn.close()
    fantasycalc.ingest(season=args.season)
    espn.ingest(season=args.season)
    conn = get_conn()

    # Step 2: optionally retrain, then write projections
    if args.retrain:
        print("\nStep 2/3: Re-training models and writing projections...")
        conn.close()
        from tay.models.pipeline import run_training_pipeline
        run_training_pipeline(
            epochs=args.epochs,
            projection_season=args.season,
            models_dir="models",
        )
        conn = get_conn()
    else:
        print("\nStep 2/3: Writing projections from existing checkpoints...")
        n = write_projections(conn, models_dir="models", projection_season=args.season)
        print(f"  {n} projections written")

    # Step 3: VOR + tiers + ADP delta
    print("\nStep 3/3: Computing VOR, tiers, ADP delta...")
    config = ReplacementConfig(teams=args.teams)
    run_valuation(conn, season=args.season, model_version=args.model_version, config=config)

    conn.close()
    elapsed = time.time() - start
    print(f"\nDone in {elapsed:.1f}s — restart the API to serve updated rankings.")


if __name__ == "__main__":
    main()
