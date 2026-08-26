import duckdb
import pytest
from pathlib import Path
from tay.db import get_conn, init_schema

@pytest.fixture
def conn(tmp_path):
    c = get_conn(tmp_path / "test.duckdb")
    yield c
    c.close()

def test_init_schema_creates_all_tables(conn):
    init_schema(conn)
    tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
    expected = {
        "players", "play_by_play", "player_season_stats", "team_season_stats",
        "rosters", "draft_picks", "combine_data", "adp", "projections", "draft_sessions",
    }
    assert expected.issubset(tables)

def test_init_schema_is_idempotent(conn):
    init_schema(conn)
    init_schema(conn)  # second call must not raise
    tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
    assert "players" in tables

def test_coaches_table_exists():
    conn = duckdb.connect(':memory:')
    init_schema(conn)
    tables = [r[0] for r in conn.execute("SHOW TABLES").fetchall()]
    assert 'coaches' in tables
    conn.close()

def test_oc_features_table_exists():
    conn = duckdb.connect(':memory:')
    init_schema(conn)
    tables = [r[0] for r in conn.execute("SHOW TABLES").fetchall()]
    assert 'oc_features' in tables
    conn.close()

def test_scheme_clusters_table_exists():
    conn = duckdb.connect(':memory:')
    init_schema(conn)
    tables = [r[0] for r in conn.execute("SHOW TABLES").fetchall()]
    assert 'scheme_clusters' in tables
    conn.close()

def test_projections_has_stage1_columns():
    conn = duckdb.connect(':memory:')
    init_schema(conn)
    cols = [r[1] for r in conn.execute("PRAGMA table_info('projections')").fetchall()]
    assert 'projected_target_share' in cols
    assert 'projected_carry_share' in cols
    assert 'projected_rec_share' in cols
    assert 'projected_pass_att_per_game' in cols
    conn.close()
