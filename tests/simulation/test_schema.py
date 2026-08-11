import duckdb
from tay.db import init_schema

SIM_COLS = [
    'sim_mean', 'sim_std', 'sim_p10', 'sim_p25', 'sim_p50',
    'sim_p75', 'sim_p90', 'sim_boom_prob', 'sim_bust_prob',
    'avail_mean', 'avail_std',
]

def test_projections_has_sim_columns():
    conn = duckdb.connect(':memory:')
    init_schema(conn)
    cols = {r[0] for r in conn.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name='projections'"
    ).fetchall()}
    missing = [c for c in SIM_COLS if c not in cols]
    assert not missing, f"Missing columns: {missing}"
    conn.close()
