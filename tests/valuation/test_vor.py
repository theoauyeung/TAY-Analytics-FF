import duckdb
import pytest
from tay.valuation.vor import compute_vor


def _make_conn():
    conn = duckdb.connect(':memory:')
    conn.execute("CREATE TABLE players (gsis_id VARCHAR PRIMARY KEY, position VARCHAR)")
    conn.execute("""
        CREATE TABLE projections (
            gsis_id VARCHAR, season INTEGER, model_version VARCHAR,
            mean_projection DOUBLE,
            vor DOUBLE, vor_rank INTEGER,
            PRIMARY KEY (gsis_id, season, model_version)
        )
    """)
    data = [
        ('qb1', 'QB', 400.0),
        ('qb2', 'QB', 300.0),
        ('rb1', 'RB', 250.0),
        ('rb2', 'RB', 150.0),
        ('wr1', 'WR', 220.0),
        ('wr2', 'WR', 120.0),
        ('te1', 'TE', 180.0),
        ('te2', 'TE',  80.0),
    ]
    for gsis_id, pos, pts in data:
        conn.execute("INSERT INTO players VALUES (?, ?)", [gsis_id, pos])
        conn.execute("INSERT INTO projections (gsis_id, season, model_version, mean_projection) VALUES (?, 2026, 'v1', ?)", [gsis_id, pts])
    return conn


REPL = {'QB': 300.0, 'RB': 150.0, 'WR': 120.0, 'TE': 80.0}


def test_vor_values():
    conn = _make_conn()
    compute_vor(conn, 2026, 'v1', REPL)
    qb1_vor = conn.execute("SELECT vor FROM projections WHERE gsis_id='qb1'").fetchone()[0]
    qb2_vor = conn.execute("SELECT vor FROM projections WHERE gsis_id='qb2'").fetchone()[0]
    assert qb1_vor == pytest.approx(28.0)
    assert qb2_vor == pytest.approx(0.0)
    conn.close()


def test_vor_negative_below_replacement():
    conn = _make_conn()
    compute_vor(conn, 2026, 'v1', REPL)
    rb2_vor = conn.execute("SELECT vor FROM projections WHERE gsis_id='rb2'").fetchone()[0]
    assert rb2_vor == pytest.approx(0.0)
    conn.close()


def test_vor_rank_ordering():
    conn = _make_conn()
    compute_vor(conn, 2026, 'v1', REPL)
    rb1_rank = conn.execute("SELECT vor_rank FROM projections WHERE gsis_id='rb1'").fetchone()[0]
    assert rb1_rank == 1
    qb1_rank = conn.execute("SELECT vor_rank FROM projections WHERE gsis_id='qb1'").fetchone()[0]
    assert rb1_rank < qb1_rank  # RBs rank higher due to scarcity weighting
    conn.close()


def test_vor_rank_all_rows_ranked():
    conn = _make_conn()
    n = compute_vor(conn, 2026, 'v1', REPL)
    assert n == 8
    null_ranks = conn.execute(
        "SELECT COUNT(*) FROM projections WHERE season=2026 AND vor_rank IS NULL"
    ).fetchone()[0]
    assert null_ranks == 0
    conn.close()
