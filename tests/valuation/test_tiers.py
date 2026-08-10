# tests/valuation/test_tiers.py
import duckdb
from tay.valuation.tiers import assign_tiers


def _make_conn(vor_values: list[tuple[str, str, float]]):
    """vor_values: list of (gsis_id, position, vor)"""
    conn = duckdb.connect(':memory:')
    conn.execute("CREATE TABLE players (gsis_id VARCHAR PRIMARY KEY, position VARCHAR)")
    conn.execute("""
        CREATE TABLE projections (
            gsis_id VARCHAR, season INTEGER, model_version VARCHAR,
            vor DOUBLE, tier INTEGER,
            PRIMARY KEY (gsis_id, season, model_version)
        )
    """)
    for gsis_id, pos, vor in vor_values:
        conn.execute("INSERT INTO players VALUES (?, ?)", [gsis_id, pos])
        conn.execute(
            "INSERT INTO projections (gsis_id, season, model_version, vor) VALUES (?, 2026, 'v1', ?)",
            [gsis_id, vor],
        )
    return conn


def test_no_gap_all_same_tier():
    # VOR drops of 5 pts — below threshold of 15 → all tier 1
    data = [('wr1','WR',100.0), ('wr2','WR',95.0), ('wr3','WR',90.0)]
    conn = _make_conn(data)
    assign_tiers(conn, 2026, 'v1', gap_threshold=15.0)
    tiers = conn.execute("SELECT tier FROM projections ORDER BY vor DESC").fetchall()
    assert all(t[0] == 1 for t in tiers)
    conn.close()


def test_gap_creates_new_tier():
    # VOR: 100, 99, 60, 59 — gap of 39 between 99 and 60 → tier 1, tier 1, tier 2, tier 2
    data = [('a','WR',100.0), ('b','WR',99.0), ('c','WR',60.0), ('d','WR',59.0)]
    conn = _make_conn(data)
    assign_tiers(conn, 2026, 'v1', gap_threshold=15.0)
    row_a = conn.execute("SELECT tier FROM projections WHERE gsis_id='a'").fetchone()[0]
    row_b = conn.execute("SELECT tier FROM projections WHERE gsis_id='b'").fetchone()[0]
    row_c = conn.execute("SELECT tier FROM projections WHERE gsis_id='c'").fetchone()[0]
    assert row_a == 1
    assert row_b == 1
    assert row_c == 2
    conn.close()


def test_multiple_gaps():
    # Three tiers
    data = [('a','RB',100.0), ('b','RB',50.0), ('c','RB',10.0)]
    conn = _make_conn(data)
    assign_tiers(conn, 2026, 'v1', gap_threshold=15.0)
    tiers = [conn.execute("SELECT tier FROM projections WHERE gsis_id=?", [g]).fetchone()[0]
             for g in ['a','b','c']]
    assert tiers == [1, 2, 3]
    conn.close()


def test_positions_tiered_independently():
    # QB has gap, WR does not — QB gets 2 tiers, WR gets 1
    data = [('qb1','QB',100.0), ('qb2','QB',50.0), ('wr1','WR',90.0), ('wr2','WR',85.0)]
    conn = _make_conn(data)
    assign_tiers(conn, 2026, 'v1', gap_threshold=15.0)
    qb_tiers = sorted(conn.execute("SELECT tier FROM projections WHERE gsis_id LIKE 'qb%'").fetchall())
    wr_tiers = sorted(conn.execute("SELECT tier FROM projections WHERE gsis_id LIKE 'wr%'").fetchall())
    assert qb_tiers[0][0] == 1 and qb_tiers[1][0] == 2
    assert wr_tiers[0][0] == 1 and wr_tiers[1][0] == 1
    conn.close()


def test_returns_row_count():
    data = [('a','QB',50.0), ('b','QB',30.0)]
    conn = _make_conn(data)
    n = assign_tiers(conn, 2026, 'v1', gap_threshold=15.0)
    assert n == 2
    conn.close()


def test_default_gap_threshold():
    # Verify default gap_threshold=15.0 works without explicit parameter
    data = [('wr1','WR',100.0), ('wr2','WR',95.0), ('wr3','WR',60.0)]
    conn = _make_conn(data)
    # Call without gap_threshold to test default
    assign_tiers(conn, 2026, 'v1')
    # With default 15.0: 100→95 is 5 (same tier), 95→60 is 35 (new tier)
    row_wr1 = conn.execute("SELECT tier FROM projections WHERE gsis_id='wr1'").fetchone()[0]
    row_wr2 = conn.execute("SELECT tier FROM projections WHERE gsis_id='wr2'").fetchone()[0]
    row_wr3 = conn.execute("SELECT tier FROM projections WHERE gsis_id='wr3'").fetchone()[0]
    assert row_wr1 == 1
    assert row_wr2 == 1
    assert row_wr3 == 2
    conn.close()
