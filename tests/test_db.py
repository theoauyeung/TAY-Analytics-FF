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
