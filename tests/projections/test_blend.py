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
