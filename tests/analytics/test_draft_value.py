"""Tests for draft value analytics."""
from tay.db import get_conn, init_schema


def test_analytics_tables_created(tmp_path):
    conn = get_conn(tmp_path / 'test.duckdb')
    init_schema(conn)
    tables = {r[0] for r in conn.execute('SHOW TABLES').fetchall()}
    assert 'player_analytics' in tables
    conn.close()
