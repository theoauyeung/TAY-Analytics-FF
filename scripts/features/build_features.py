#!/usr/bin/env python3
"""Build feature tables from ingested DuckDB data.

Usage:
    python scripts/features/build_features.py [--start 2006] [--end 2026]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from tay.features.pipeline import run_pipeline


def main():
    p = argparse.ArgumentParser(description="TAY Analytics FF — feature engineering pipeline")
    p.add_argument("--start", type=int, default=2006, help="First target season (default 2006)")
    p.add_argument("--end", type=int, default=2026, help="Last target season (default 2026)")
    args = p.parse_args()
    run_pipeline(start=args.start, end=args.end)


if __name__ == "__main__":
    main()
