import pytest
from tay.db import get_conn, init_schema


def test_roster_columns_present(tmp_path):
    """Verify we can insert a mock roster row into the rosters table."""
    conn = get_conn(tmp_path / "test.duckdb")
    init_schema(conn)
    conn.execute("""
        INSERT INTO rosters (gsis_id, season, week, team, position, depth_chart_pos, status)
        VALUES ('test-id-1', 2024, 1, 'KC', 'QB', 1, 'Active')
    """)
    row = conn.execute("SELECT gsis_id FROM rosters WHERE season=2024").fetchone()
    assert row[0] == 'test-id-1'
    conn.close()


def test_players_columns_present(tmp_path):
    """Verify we can insert a mock player row into the players table."""
    conn = get_conn(tmp_path / "test.duckdb")
    init_schema(conn)
    conn.execute("""
        INSERT INTO players (gsis_id, name, position, team)
        VALUES ('00-0000001', 'Test Player', 'QB', 'KC')
    """)
    row = conn.execute("SELECT name FROM players WHERE gsis_id='00-0000001'").fetchone()
    assert row[0] == 'Test Player'
    conn.close()


def test_draft_picks_columns_present(tmp_path):
    """Verify we can insert a mock draft pick row into the draft_picks table."""
    conn = get_conn(tmp_path / "test.duckdb")
    init_schema(conn)
    conn.execute("""
        INSERT INTO draft_picks (gsis_id, season, round, pick, overall_pick, team, position, college)
        VALUES ('00-0000001', 2024, 1, 1, 1, 'CHI', 'QB', 'USC')
    """)
    row = conn.execute("SELECT gsis_id FROM draft_picks WHERE season=2024").fetchone()
    assert row[0] == '00-0000001'
    conn.close()
