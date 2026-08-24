"""Tests for snap count feature computation."""
import pytest
from tay.db import get_conn, init_schema


def test_snap_counts_table_created(tmp_path):
    conn = get_conn(tmp_path / 'test.duckdb')
    init_schema(conn)
    tables = {r[0] for r in conn.execute('SHOW TABLES').fetchall()}
    assert 'snap_counts' in tables
    conn.close()
