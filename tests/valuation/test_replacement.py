import duckdb
import pytest
from tay.valuation.replacement import ReplacementConfig, get_replacement_spots, compute_replacement_levels


def test_default_replacement_spots():
    config = ReplacementConfig()
    spots = get_replacement_spots(config)
    assert spots == {'QB': 12, 'RB': 30, 'WR': 30, 'TE': 12}


def test_custom_replacement_spots():
    config = ReplacementConfig(teams=10, roster_qb=1, roster_rb=2, roster_wr=2, roster_te=1, roster_flex=1)
    spots = get_replacement_spots(config)
    # QB: 10*1=10, RB: 10*2 + round(10*1*0.5)=25, WR: 10*2 + (10-5)=25, TE: 10*1=10
    assert spots['QB'] == 10
    assert spots['RB'] == 25
    assert spots['WR'] == 25
    assert spots['TE'] == 10


def _make_conn():
    conn = duckdb.connect(':memory:')
    conn.execute("""
        CREATE TABLE players (gsis_id VARCHAR PRIMARY KEY, position VARCHAR)
    """)
    conn.execute("""
        CREATE TABLE projections (
            gsis_id VARCHAR, season INTEGER, model_version VARCHAR,
            mean_projection DOUBLE,
            PRIMARY KEY (gsis_id, season, model_version)
        )
    """)
    # 5 QBs, projections 500, 400, 300, 200, 100
    for i, pts in enumerate([500, 400, 300, 200, 100]):
        conn.execute("INSERT INTO players VALUES (?, 'QB')", [f'qb{i}'])
        conn.execute("INSERT INTO projections VALUES (?, 2026, 'v1', ?)", [f'qb{i}', pts])
    # 4 RBs
    for i, pts in enumerate([250, 200, 150, 100]):
        conn.execute("INSERT INTO players VALUES (?, 'RB')", [f'rb{i}'])
        conn.execute("INSERT INTO projections VALUES (?, 2026, 'v1', ?)", [f'rb{i}', pts])
    return conn


def test_replacement_level_returns_nth_player():
    conn = _make_conn()
    # QB: 5 players, spots=2 → 2nd player (400)
    config = ReplacementConfig(teams=2, roster_qb=1, roster_rb=2, roster_wr=2, roster_te=1, roster_flex=0)
    levels = compute_replacement_levels(conn, 2026, 'v1', config)
    assert levels['QB'] == 400.0
    conn.close()


def test_replacement_level_beyond_roster_returns_zero():
    conn = _make_conn()
    # RB: 4 players, spots=10 → no 10th player → 0.0
    config = ReplacementConfig(teams=10, roster_qb=1, roster_rb=1, roster_wr=1, roster_te=1, roster_flex=0)
    levels = compute_replacement_levels(conn, 2026, 'v1', config)
    assert levels['RB'] == 0.0
    conn.close()
