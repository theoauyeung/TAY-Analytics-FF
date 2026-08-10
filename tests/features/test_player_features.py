import pytest
import duckdb
from tay.db import get_conn, init_schema
from tay.features.player_features import build_player_features

@pytest.fixture
def conn(tmp_path):
    c = get_conn(tmp_path / "test.duckdb")
    init_schema(c)

    # Player setup: WR, born 2000-01-01, on KC
    c.execute("""
        INSERT INTO players (gsis_id, name, position, team, birth_date, draft_year, draft_round, draft_pick)
        VALUES ('wr-1', 'Test WR', 'WR', 'KC', '2000-01-01', 2022, 1, 10)
    """)
    # Season 2022 stats
    c.execute("""
        INSERT INTO player_season_stats
            (gsis_id, season, team, games, targets, receptions, rec_yards, rec_tds,
             air_yards, yards_after_catch, fantasy_points_ppr)
        VALUES ('wr-1', 2022, 'KC', 17, 120, 90, 1200.0, 8, 800.0, 400.0, 252.0)
    """)
    # Season 2023 stats (what we're predicting FROM)
    c.execute("""
        INSERT INTO player_season_stats
            (gsis_id, season, team, games, targets, receptions, rec_yards, rec_tds,
             air_yards, yards_after_catch, fantasy_points_ppr)
        VALUES ('wr-1', 2023, 'KC', 16, 140, 100, 1400.0, 10, 900.0, 500.0, 300.0)
    """)
    # Season 2024 stats (the target variable)
    c.execute("""
        INSERT INTO player_season_stats
            (gsis_id, season, team, games, targets, receptions, rec_yards, rec_tds,
             air_yards, yards_after_catch, fantasy_points_ppr)
        VALUES ('wr-1', 2024, 'KC', 17, 130, 95, 1300.0, 9, 850.0, 450.0, 278.0)
    """)
    # Team features for KC 2024 (from Task 2)
    c.execute("""
        INSERT INTO team_features (team, season, pass_rate, team_epa, total_plays)
        VALUES ('KC', 2024, 0.55, 0.12, 1100)
    """)
    yield c
    c.close()

def test_build_player_features_creates_row(conn):
    build_player_features(conn, target_seasons=[2024])
    row = conn.execute(
        "SELECT gsis_id, season, prev_targets, next_season_fantasy_ppr FROM player_features WHERE gsis_id='wr-1' AND season=2024"
    ).fetchone()
    assert row is not None
    assert row[0] == 'wr-1'
    assert row[1] == 2024
    assert row[2] == 140   # 2023 targets
    assert abs(row[3] - 278.0) < 1.0   # 2024 actual

def test_rate_stats_computed(conn):
    build_player_features(conn, target_seasons=[2024])
    row = conn.execute(
        "SELECT catch_rate, yards_per_target FROM player_features WHERE gsis_id='wr-1' AND season=2024"
    ).fetchone()
    assert row is not None
    # catch_rate = 100/140 ≈ 0.714
    assert abs(row[0] - 100/140) < 0.01
    # yards_per_target = 1400/140 = 10.0
    assert abs(row[1] - 10.0) < 0.01

def test_rolling_average(conn):
    build_player_features(conn, target_seasons=[2024])
    row = conn.execute(
        "SELECT roll2_fantasy_ppr FROM player_features WHERE gsis_id='wr-1' AND season=2024"
    ).fetchone()
    assert row is not None
    # roll2 = (252 + 300) / 2 = 276
    assert abs(row[0] - 276.0) < 1.0

def test_skill_positions_only(conn):
    """Non-skill position players (K, P) should not get feature rows."""
    conn.execute("""
        INSERT INTO players (gsis_id, name, position, team)
        VALUES ('k-1', 'Test Kicker', 'K', 'KC')
    """)
    conn.execute("""
        INSERT INTO player_season_stats (gsis_id, season, team, fantasy_points_ppr)
        VALUES ('k-1', 2023, 'KC', 150.0)
    """)
    build_player_features(conn, target_seasons=[2024])
    row = conn.execute(
        "SELECT gsis_id FROM player_features WHERE gsis_id='k-1'"
    ).fetchone()
    assert row is None

def test_player_features_has_lag_columns():
    """Verify all 12 new lag/EWMA columns exist in the schema."""
    conn = duckdb.connect(':memory:')
    init_schema(conn)
    cols = {row[0] for row in conn.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'player_features'"
    ).fetchall()}
    expected = {
        'lag2_fantasy_ppr', 'lag2_targets', 'lag2_carries', 'lag2_pass_yards',
        'lag3_fantasy_ppr', 'lag3_targets', 'lag3_carries', 'lag3_pass_yards',
        'ewma_fantasy_ppr', 'ewma_targets', 'ewma_carries', 'ewma_pass_yards',
    }
    assert expected.issubset(cols), f"Missing columns: {expected - cols}"
    conn.close()

def test_migrate_adds_missing_columns():
    """Simulate an old DB that lacks the new columns, then migrate."""
    conn = duckdb.connect(':memory:')
    # Create table without new columns (old schema)
    conn.execute("""
        CREATE TABLE player_features (
            gsis_id VARCHAR NOT NULL,
            season INTEGER NOT NULL,
            prev_fantasy_ppr DOUBLE,
            PRIMARY KEY (gsis_id, season)
        )
    """)
    # Migration must not error and must add the columns
    from tay.features.player_features import _migrate_player_features
    _migrate_player_features(conn)
    cols = {row[0] for row in conn.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'player_features'"
    ).fetchall()}
    assert 'lag2_fantasy_ppr' in cols
    assert 'ewma_fantasy_ppr' in cols
    conn.close()
