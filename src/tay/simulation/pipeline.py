"""Orchestrate the simulation pipeline."""
from __future__ import annotations
import duckdb

from tay.simulation.monte_carlo import run_simulation


def run_simulation_pipeline(
    conn: duckdb.DuckDBPyConnection,
    season: int,
    model_version: str,
) -> dict:
    """Run Monte Carlo simulation and return summary dict."""
    n = run_simulation(conn, season, model_version)
    return {'season': season, 'model_version': model_version, 'simulated_players': n}
