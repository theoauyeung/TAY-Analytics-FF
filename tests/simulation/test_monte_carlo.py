import duckdb
import pytest
from tay.db import init_schema
from tay.simulation.monte_carlo import run_simulation, N_SIMS, SEASON_GAMES


def _make_conn(mean_proj: float = 300.0, std_dev: float = 60.0, position: str = 'RB') -> duckdb.DuckDBPyConnection:
    conn = duckdb.connect(':memory:')
    init_schema(conn)
    conn.execute(f"INSERT INTO players (gsis_id, position, name) VALUES ('P001', '{position}', 'Test Back')")
    conn.execute("""
        INSERT INTO projections (gsis_id, season, model_version, mean_projection, std_dev)
        VALUES ('P001', 2026, 'neural-v1', ?, ?)
    """, [mean_proj, std_dev])
    # Give player 3 seasons of history (healthy starter)
    for s, g in [(2023, 15), (2024, 16), (2025, 14)]:
        conn.execute("""
            INSERT INTO player_season_stats (gsis_id, season, games, fantasy_points_ppr, team)
            VALUES ('P001', ?, ?, 100.0, 'KC')
        """, [s, g])
    conn.commit()
    return conn


def test_returns_row_count():
    conn = _make_conn()
    n = run_simulation(conn, 2026, 'neural-v1')
    assert n == 1
    conn.close()


def test_sim_columns_populated():
    conn = _make_conn(mean_proj=300.0, std_dev=60.0)
    run_simulation(conn, 2026, 'neural-v1')
    row = conn.execute("""
        SELECT sim_mean, sim_std, sim_p10, sim_p25, sim_p50, sim_p75, sim_p90,
               sim_boom_prob, sim_bust_prob, avail_mean, avail_std
        FROM projections WHERE gsis_id = 'P001' AND season = 2026
    """).fetchone()
    assert row is not None
    assert all(v is not None for v in row), f"NULL values: {row}"
    sim_mean = row[0]
    assert 50 < sim_mean < 350, f"sim_mean out of range: {sim_mean}"
    conn.close()


def test_sim_percentiles_ordered():
    conn = _make_conn(mean_proj=250.0, std_dev=50.0)
    run_simulation(conn, 2026, 'neural-v1')
    row = conn.execute(
        "SELECT sim_p10, sim_p25, sim_p50, sim_p75, sim_p90 FROM projections WHERE gsis_id='P001'"
    ).fetchone()
    p10, p25, p50, p75, p90 = row
    assert p10 <= p25 <= p50 <= p75 <= p90, f"Percentiles not ordered: {row}"
    conn.close()


def test_sim_probabilities_between_0_and_1():
    conn = _make_conn()
    run_simulation(conn, 2026, 'neural-v1')
    row = conn.execute(
        "SELECT sim_boom_prob, sim_bust_prob FROM projections WHERE gsis_id='P001'"
    ).fetchone()
    boom, bust = row
    assert 0.0 <= boom <= 1.0
    assert 0.0 <= bust <= 1.0
    conn.close()


def test_injured_player_lower_sim_mean():
    """Player with 5-game history should project lower than player with 15-game history."""
    conn_healthy = _make_conn()
    run_simulation(conn_healthy, 2026, 'neural-v1')
    healthy_mean = conn_healthy.execute(
        "SELECT sim_mean FROM projections WHERE gsis_id='P001'"
    ).fetchone()[0]

    conn_injured = duckdb.connect(':memory:')
    init_schema(conn_injured)
    conn_injured.execute("INSERT INTO players (gsis_id, position, name) VALUES ('P001', 'RB', 'Injury Risk')")
    conn_injured.execute("""
        INSERT INTO projections (gsis_id, season, model_version, mean_projection, std_dev)
        VALUES ('P001', 2026, 'neural-v1', 300.0, 60.0)
    """)
    for s in [2023, 2024, 2025]:
        conn_injured.execute("""
            INSERT INTO player_season_stats (gsis_id, season, games, fantasy_points_ppr, team)
            VALUES ('P001', ?, 5, 60.0, 'KC')
        """, [s])
    conn_injured.commit()
    run_simulation(conn_injured, 2026, 'neural-v1')
    injured_mean = conn_injured.execute(
        "SELECT sim_mean FROM projections WHERE gsis_id='P001'"
    ).fetchone()[0]

    assert injured_mean < healthy_mean, (
        f"Injured player ({injured_mean:.1f}) should be lower than healthy ({healthy_mean:.1f})"
    )
