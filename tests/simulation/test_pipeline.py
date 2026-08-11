import duckdb
from tay.db import init_schema
from tay.simulation.pipeline import run_simulation_pipeline


def _make_conn() -> duckdb.DuckDBPyConnection:
    conn = duckdb.connect(':memory:')
    init_schema(conn)
    conn.execute("INSERT INTO players (gsis_id, position, name) VALUES ('P001', 'WR', 'Test Receiver')")
    conn.execute("""
        INSERT INTO projections (gsis_id, season, model_version, mean_projection, std_dev)
        VALUES ('P001', 2026, 'neural-v1', 220.0, 55.0)
    """)
    conn.commit()
    return conn


def test_returns_summary_dict():
    conn = _make_conn()
    result = run_simulation_pipeline(conn, 2026, 'neural-v1')
    assert result['season'] == 2026
    assert result['model_version'] == 'neural-v1'
    assert result['simulated_players'] == 1
    conn.close()


def test_sim_columns_written():
    conn = _make_conn()
    run_simulation_pipeline(conn, 2026, 'neural-v1')
    row = conn.execute(
        "SELECT sim_mean, avail_mean FROM projections WHERE gsis_id='P001'"
    ).fetchone()
    assert row[0] is not None
    assert row[1] is not None
    conn.close()
