#!/usr/bin/env python3
"""Compute VOR, tiers, and ADP delta for projected players.

Usage:
    python scripts/rankings/compute_valuations.py [--season 2026] [--model-version neural-v1]
                                         [--teams 12]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from tay.db import get_conn, init_schema
from tay.valuation.pipeline import run_valuation
from tay.valuation.replacement import ReplacementConfig


def main():
    p = argparse.ArgumentParser(description='TAY Analytics FF — valuation engine')
    p.add_argument('--season',         type=int,   default=2026)
    p.add_argument('--model-version',  default='neural-v1')
    p.add_argument('--teams',          type=int,   default=12)
    args = p.parse_args()

    conn = get_conn()
    init_schema(conn)
    config = ReplacementConfig(teams=args.teams)
    result = run_valuation(
        conn,
        season=args.season,
        model_version=args.model_version,
        config=config,
    )
    conn.close()
    return result


if __name__ == '__main__':
    main()
