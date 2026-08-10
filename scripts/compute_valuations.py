#!/usr/bin/env python3
"""Compute VOR, tiers, and ADP delta for projected players.

Usage:
    python scripts/compute_valuations.py [--season 2026] [--model-version neural-v1]
                                         [--teams 12] [--gap-threshold 15.0]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from tay.valuation.pipeline import run_valuation
from tay.valuation.replacement import ReplacementConfig


def main():
    p = argparse.ArgumentParser(description='TAY Analytics FF — valuation engine')
    p.add_argument('--season',         type=int,   default=2026)
    p.add_argument('--model-version',  default='neural-v1')
    p.add_argument('--teams',          type=int,   default=12)
    p.add_argument('--gap-threshold',  type=float, default=15.0)
    args = p.parse_args()

    config = ReplacementConfig(teams=args.teams)
    run_valuation(
        season=args.season,
        model_version=args.model_version,
        gap_threshold=args.gap_threshold,
        config=config,
    )


if __name__ == '__main__':
    main()
