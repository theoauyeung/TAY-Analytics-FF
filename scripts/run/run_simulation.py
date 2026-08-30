#!/usr/bin/env python3
"""Run Monte Carlo simulation pipeline.

Usage:
    python scripts/run/run_simulation.py [--season 2026] [--model-version neural-v1]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from tay.db import get_conn, init_schema
from tay.simulation.pipeline import run_simulation_pipeline


def main():
    p = argparse.ArgumentParser(description='TAY Analytics FF — Monte Carlo simulation')
    p.add_argument('--season',        type=int, default=2026)
    p.add_argument('--model-version', default='neural-v1')
    args = p.parse_args()

    conn = get_conn()
    init_schema(conn)
    print(f'=== TAY Analytics FF — Monte Carlo Simulation ===')
    print(f'Season: {args.season}  Model: {args.model_version}')

    result = run_simulation_pipeline(conn, args.season, args.model_version)
    print(f"Simulated: {result['simulated_players']} players")
    conn.close()


if __name__ == '__main__':
    main()
