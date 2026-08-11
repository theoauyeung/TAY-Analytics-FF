"""Monte Carlo simulation engine — injury-adjusted projection distributions."""
from __future__ import annotations
import numpy as np
import duckdb

from tay.simulation.availability import compute_availability

N_SIMS = 1000
SEASON_GAMES = 17

# Availability adjusts the projected mean by at most this fraction.
# Talent (mean_projection) is the primary signal; injury risk only applies
# a small discount so a chronically-injured player takes a ≤15% hit, not a 40%+ one.
AVAIL_ALPHA = 0.15

_RNG_SEED = 42


def run_simulation(
    conn: duckdb.DuckDBPyConnection,
    season: int,
    model_version: str,
    n_sims: int = N_SIMS,
) -> int:
    """Run Monte Carlo simulation for all players; write sim_* columns to projections.

    Returns total rows updated.
    """
    availability = compute_availability(conn, season, model_version)

    players = conn.execute("""
        SELECT gsis_id, mean_projection, std_dev
        FROM projections
        WHERE season = ? AND model_version = ?
          AND mean_projection IS NOT NULL AND std_dev IS NOT NULL
    """, [season, model_version]).fetchall()

    rng = np.random.default_rng(_RNG_SEED)
    updated = 0

    for gsis_id, mean_projection, std_dev in players:
        avail_mean, avail_std = availability.get(gsis_id, (13.0, 4.0))

        # Draw games from availability distribution, then convert to a small
        # scale factor: fully healthy (17 games) → 1.0, worst case → 1 - AVAIL_ALPHA.
        games = rng.normal(avail_mean, avail_std, n_sims).clip(0, SEASON_GAMES)
        avail_scale = 1.0 - AVAIL_ALPHA * (1.0 - games / SEASON_GAMES)

        # Season total: model mean (talent signal) × small availability adjustment
        # + model-level noise. std_dev drives distribution width, not games played.
        totals = rng.normal(mean_projection * avail_scale, std_dev, n_sims).clip(0, None)

        sim_mean = float(totals.mean())
        sim_std = float(totals.std())
        p10, p25, p50, p75, p90 = (float(np.percentile(totals, p)) for p in [10, 25, 50, 75, 90])
        boom_prob = float((totals > sim_mean * 1.5).mean()) if sim_mean > 0 else 0.0
        bust_prob = float((totals < sim_mean * 0.5).mean()) if sim_mean > 0 else 0.0

        conn.execute("""
            UPDATE projections SET
                sim_mean = ?, sim_std = ?,
                sim_p10 = ?, sim_p25 = ?, sim_p50 = ?, sim_p75 = ?, sim_p90 = ?,
                sim_boom_prob = ?, sim_bust_prob = ?,
                avail_mean = ?, avail_std = ?
            WHERE gsis_id = ? AND season = ? AND model_version = ?
        """, [
            sim_mean, sim_std,
            p10, p25, p50, p75, p90,
            boom_prob, bust_prob,
            float(avail_mean), float(avail_std),
            gsis_id, season, model_version,
        ])
        updated += 1

    conn.commit()
    return updated
