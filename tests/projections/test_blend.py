import duckdb
import pytest
from tay.db import init_schema


def _make_conn():
    conn = duckdb.connect(':memory:')
    init_schema(conn)
    return conn


def test_consensus_projections_table_exists():
    conn = _make_conn()
    tables = [r[0] for r in conn.execute("SHOW TABLES").fetchall()]
    assert 'consensus_projections' in tables
    conn.close()


def test_consensus_projections_primary_key():
    conn = _make_conn()
    # Duplicate (gsis_id, season, source) must fail
    conn.execute("""
        INSERT INTO consensus_projections (gsis_id, season, source, points)
        VALUES ('p1', 2026, 'fantasypros', 100.0)
    """)
    with pytest.raises(Exception):
        conn.execute("""
            INSERT INTO consensus_projections (gsis_id, season, source, points)
            VALUES ('p1', 2026, 'fantasypros', 200.0)
        """)
    conn.close()


def test_projections_has_blend_columns():
    conn = _make_conn()
    cols = [r[1] for r in conn.execute("PRAGMA table_info('projections')").fetchall()]
    assert 'consensus_projection' in cols
    assert 'blended_projection' in cols
    conn.close()


from tay.projections.blend import (
    blend_projections, CONSENSUS_WEIGHT, ML_WEIGHT,
    TEAM_CHANGE_CONSENSUS_WEIGHT, TEAM_CHANGE_ML_WEIGHT,
)


def _make_blend_conn():
    """In-memory DB with projections + consensus_projections tables."""
    conn = duckdb.connect(':memory:')
    conn.execute("""
        CREATE TABLE projections (
            gsis_id VARCHAR, season INTEGER, model_version VARCHAR,
            mean_projection DOUBLE,
            consensus_projection DOUBLE,
            blended_projection DOUBLE,
            PRIMARY KEY (gsis_id, season, model_version)
        )
    """)
    conn.execute("""
        CREATE TABLE consensus_projections (
            gsis_id VARCHAR, season INTEGER, source VARCHAR,
            points DOUBLE,
            PRIMARY KEY (gsis_id, season, source)
        )
    """)
    conn.execute("CREATE TABLE players (gsis_id VARCHAR PRIMARY KEY, team VARCHAR)")
    conn.execute("""
        CREATE TABLE player_season_stats (
            gsis_id VARCHAR, season INTEGER, team VARCHAR,
            PRIMARY KEY (gsis_id, season)
        )
    """)
    return conn


def test_blend_weights_are_correct():
    assert CONSENSUS_WEIGHT == 0.65
    assert ML_WEIGHT == 0.35


def test_blend_single_source():
    conn = _make_blend_conn()
    conn.execute("INSERT INTO projections VALUES ('p1', 2026, 'v1', 300.0, NULL, NULL)")
    conn.execute("INSERT INTO consensus_projections VALUES ('p1', 2026, 'fantasypros', 350.0)")
    count = blend_projections(conn, 2026, 'v1')
    row = conn.execute(
        "SELECT consensus_projection, blended_projection FROM projections WHERE gsis_id='p1'"
    ).fetchone()
    assert row[0] == pytest.approx(350.0)
    assert row[1] == pytest.approx(0.65 * 350.0 + 0.35 * 300.0)
    assert count == 1
    conn.close()


def test_blend_two_sources_averaged():
    conn = _make_blend_conn()
    conn.execute("INSERT INTO projections VALUES ('p1', 2026, 'v1', 300.0, NULL, NULL)")
    conn.execute("INSERT INTO consensus_projections VALUES ('p1', 2026, 'fantasypros', 360.0)")
    conn.execute("INSERT INTO consensus_projections VALUES ('p1', 2026, 'espn', 340.0)")
    blend_projections(conn, 2026, 'v1')
    row = conn.execute(
        "SELECT consensus_projection, blended_projection FROM projections WHERE gsis_id='p1'"
    ).fetchone()
    avg_consensus = (360.0 + 340.0) / 2  # 350.0
    assert row[0] == pytest.approx(avg_consensus)
    assert row[1] == pytest.approx(0.65 * avg_consensus + 0.35 * 300.0)
    conn.close()


def test_blend_fallback_ml_only():
    """Players with no consensus row get blended_projection = mean_projection."""
    conn = _make_blend_conn()
    conn.execute("INSERT INTO projections VALUES ('p1', 2026, 'v1', 200.0, NULL, NULL)")
    # No row in consensus_projections
    count = blend_projections(conn, 2026, 'v1')
    row = conn.execute(
        "SELECT consensus_projection, blended_projection FROM projections WHERE gsis_id='p1'"
    ).fetchone()
    assert row[0] is None
    assert row[1] == pytest.approx(200.0)
    assert count == 0  # 0 blended, fallback not counted
    conn.close()


def test_blend_mixed_players():
    """Some players have consensus, some don't."""
    conn = _make_blend_conn()
    conn.execute("INSERT INTO projections VALUES ('p1', 2026, 'v1', 300.0, NULL, NULL)")
    conn.execute("INSERT INTO projections VALUES ('p2', 2026, 'v1', 180.0, NULL, NULL)")
    conn.execute("INSERT INTO consensus_projections VALUES ('p1', 2026, 'fantasypros', 350.0)")
    count = blend_projections(conn, 2026, 'v1')
    p1 = conn.execute("SELECT blended_projection FROM projections WHERE gsis_id='p1'").fetchone()[0]
    p2 = conn.execute("SELECT blended_projection FROM projections WHERE gsis_id='p2'").fetchone()[0]
    assert p1 == pytest.approx(0.65 * 350.0 + 0.35 * 300.0)
    assert p2 == pytest.approx(180.0)  # fallback to ML
    assert count == 1
    conn.close()


def test_blend_team_changer_gets_higher_consensus_weight():
    """Players who switched teams get 85% consensus weight instead of 65%."""
    conn = _make_blend_conn()
    conn.execute("INSERT INTO players VALUES ('p1', 'TeamB')")
    conn.execute("INSERT INTO player_season_stats VALUES ('p1', 2025, 'TeamA')")
    conn.execute("INSERT INTO projections VALUES ('p1', 2026, 'v1', 200.0, NULL, NULL)")
    conn.execute("INSERT INTO consensus_projections VALUES ('p1', 2026, 'fantasypros', 150.0)")
    blend_projections(conn, 2026, 'v1')
    row = conn.execute(
        "SELECT blended_projection FROM projections WHERE gsis_id='p1'"
    ).fetchone()
    assert row[0] == pytest.approx(
        TEAM_CHANGE_CONSENSUS_WEIGHT * 150.0 + TEAM_CHANGE_ML_WEIGHT * 200.0
    )
    conn.close()


def test_blend_same_team_uses_normal_weights():
    """Players who stayed on the same team get the standard 65/35 blend."""
    conn = _make_blend_conn()
    conn.execute("INSERT INTO players VALUES ('p1', 'TeamA')")
    conn.execute("INSERT INTO player_season_stats VALUES ('p1', 2025, 'TeamA')")
    conn.execute("INSERT INTO projections VALUES ('p1', 2026, 'v1', 200.0, NULL, NULL)")
    conn.execute("INSERT INTO consensus_projections VALUES ('p1', 2026, 'fantasypros', 150.0)")
    blend_projections(conn, 2026, 'v1')
    row = conn.execute(
        "SELECT blended_projection FROM projections WHERE gsis_id='p1'"
    ).fetchone()
    assert row[0] == pytest.approx(CONSENSUS_WEIGHT * 150.0 + ML_WEIGHT * 200.0)
    conn.close()
