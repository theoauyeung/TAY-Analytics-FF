"""Tests for advanced_features module."""
import pytest
import duckdb
from tay.db import get_conn, init_schema


@pytest.fixture
def conn(tmp_path):
    c = get_conn(tmp_path / 'test.duckdb')
    init_schema(c)
    # Minimal player_features row so migration has a table to alter
    c.execute("""
        INSERT INTO player_features (gsis_id, season, position)
        VALUES ('p1', 2026, 'WR')
    """)
    yield c
    c.close()


def test_migrate_adds_columns(conn):
    from tay.features.advanced_features import _migrate_advanced_features
    _migrate_advanced_features(conn)
    cols = {r[1] for r in conn.execute('PRAGMA table_info(player_features)').fetchall()}
    for col in ('target_share', 'air_yards_share', 'wopr',
                'weekly_fpts_std', 'boom_rate', 'floor_rate', 'sos_pts_allowed'):
        assert col in cols, f'Missing column: {col}'


def test_migrate_is_idempotent(conn):
    from tay.features.advanced_features import _migrate_advanced_features
    _migrate_advanced_features(conn)
    _migrate_advanced_features(conn)  # must not raise
