import pytest
import duckdb
from tay.db import get_conn, init_schema
from tay.features.player_features import build_player_features


def _seed_conn():
    """In-memory DB with minimal tables needed by build_player_features."""
    conn = duckdb.connect(':memory:')
    init_schema(conn)
    # Insert a player
    conn.execute("""
        INSERT INTO players (gsis_id, position, name)
        VALUES ('P001', 'RB', 'Test Runner')
    """)
    # Season N-3 stats (2021)
    conn.execute("""
        INSERT INTO player_season_stats
            (gsis_id, season, games, targets, receptions, rec_yards, rec_tds,
             air_yards, yards_after_catch, carries, rush_yards, rush_tds,
             attempts, completions, pass_yards, pass_tds, interceptions,
             fantasy_points_ppr, epa_per_play, cpoe, team)
        VALUES ('P001', 2021, 16, 20, 15, 180, 1, 200, 80, 180, 900, 8,
                0, 0, 0, 0, 0, 240.0, 0.05, NULL, 'KC')
    """)
    # Season N-2 stats (2022)
    conn.execute("""
        INSERT INTO player_season_stats
            (gsis_id, season, games, targets, receptions, rec_yards, rec_tds,
             air_yards, yards_after_catch, carries, rush_yards, rush_tds,
             attempts, completions, pass_yards, pass_tds, interceptions,
             fantasy_points_ppr, epa_per_play, cpoe, team)
        VALUES ('P001', 2022, 16, 30, 22, 260, 2, 310, 110, 200, 950, 9,
                0, 0, 0, 0, 0, 280.0, 0.06, NULL, 'KC')
    """)
    # Season N-1 stats (2023)
    conn.execute("""
        INSERT INTO player_season_stats
            (gsis_id, season, games, targets, receptions, rec_yards, rec_tds,
             air_yards, yards_after_catch, carries, rush_yards, rush_tds,
             attempts, completions, pass_yards, pass_tds, interceptions,
             fantasy_points_ppr, epa_per_play, cpoe, team)
        VALUES ('P001', 2023, 16, 40, 30, 340, 3, 420, 140, 220, 1100, 12,
                0, 0, 0, 0, 0, 320.0, 0.07, NULL, 'KC')
    """)
    # Target season stats (2024) — this is next_season_fantasy_ppr
    conn.execute("""
        INSERT INTO player_season_stats
            (gsis_id, season, games, targets, receptions, rec_yards, rec_tds,
             air_yards, yards_after_catch, carries, rush_yards, rush_tds,
             attempts, completions, pass_yards, pass_tds, interceptions,
             fantasy_points_ppr, epa_per_play, cpoe, team)
        VALUES ('P001', 2024, 16, 45, 34, 380, 4, 460, 160, 230, 1150, 13,
                0, 0, 0, 0, 0, 360.0, 0.08, NULL, 'KC')
    """)
    # Team features for target season (KC, 2024)
    conn.execute("""
        INSERT INTO team_features (team, season, pass_rate, pass_epa, total_plays)
        VALUES ('KC', 2024, 0.58, 0.12, 1050)
    """)
    conn.commit()
    return conn


def test_lag2_populated():
    conn = _seed_conn()
    build_player_features(conn, [2024])
    row = conn.execute(
        "SELECT lag2_fantasy_ppr, lag2_targets, lag2_carries FROM player_features WHERE gsis_id = 'P001' AND season = 2024"
    ).fetchone()
    assert row is not None
    assert abs(row[0] - 280.0) < 0.01, f"lag2_fantasy_ppr expected 280.0, got {row[0]}"
    assert row[1] == 30, f"lag2_targets expected 30, got {row[1]}"
    assert row[2] == 200, f"lag2_carries expected 200, got {row[2]}"
    conn.close()


def test_lag3_populated():
    conn = _seed_conn()
    build_player_features(conn, [2024])
    row = conn.execute(
        "SELECT lag3_fantasy_ppr, lag3_targets, lag3_carries FROM player_features WHERE gsis_id = 'P001' AND season = 2024"
    ).fetchone()
    assert row is not None
    assert abs(row[0] - 240.0) < 0.01, f"lag3_fantasy_ppr expected 240.0, got {row[0]}"
    assert row[1] == 20, f"lag3_targets expected 20, got {row[1]}"
    assert row[2] == 180, f"lag3_carries expected 180, got {row[2]}"
    conn.close()


def test_ewma_fantasy_ppr():
    """EWMA = 0.6×320 + 0.3×280 + 0.1×240 = 192 + 84 + 24 = 300.0"""
    conn = _seed_conn()
    build_player_features(conn, [2024])
    row = conn.execute(
        "SELECT ewma_fantasy_ppr, ewma_targets, ewma_carries FROM player_features WHERE gsis_id = 'P001' AND season = 2024"
    ).fetchone()
    assert row is not None
    assert abs(row[0] - 300.0) < 0.01, f"ewma_fantasy_ppr expected 300.0, got {row[0]}"
    # ewma_targets = 0.6×40 + 0.3×30 + 0.1×20 = 24 + 9 + 2 = 35.0
    assert abs(row[1] - 35.0) < 0.01, f"ewma_targets expected 35.0, got {row[1]}"
    # ewma_carries = 0.6×220 + 0.3×200 + 0.1×180 = 132 + 60 + 18 = 210.0
    assert abs(row[2] - 210.0) < 0.01, f"ewma_carries expected 210.0, got {row[2]}"
    conn.close()


def test_lag2_null_when_only_one_prior_season():
    """Player with only one prior season gets NULL lag2/lag3."""
    conn = duckdb.connect(':memory:')
    init_schema(conn)
    conn.execute("INSERT INTO players (gsis_id, position, name) VALUES ('P002', 'WR', 'Rookie Star')")
    # Only season N-1 exists (2023) — no 2022, no 2021
    conn.execute("""
        INSERT INTO player_season_stats
            (gsis_id, season, games, targets, receptions, rec_yards, rec_tds,
             air_yards, yards_after_catch, carries, rush_yards, rush_tds,
             attempts, completions, pass_yards, pass_tds, interceptions,
             fantasy_points_ppr, epa_per_play, cpoe, team)
        VALUES ('P002', 2023, 16, 80, 60, 900, 7, 1200, 300, 5, 30, 0,
                0, 0, 0, 0, 0, 250.0, 0.10, NULL, 'SF')
    """)
    conn.execute("""
        INSERT INTO player_season_stats
            (gsis_id, season, games, targets, receptions, rec_yards, rec_tds,
             air_yards, yards_after_catch, carries, rush_yards, rush_tds,
             attempts, completions, pass_yards, pass_tds, interceptions,
             fantasy_points_ppr, epa_per_play, cpoe, team)
        VALUES ('P002', 2024, 16, 85, 63, 950, 8, 1250, 320, 6, 35, 0,
                0, 0, 0, 0, 0, 270.0, 0.11, NULL, 'SF')
    """)
    conn.execute("INSERT INTO team_features (team, season, pass_rate, pass_epa, total_plays) VALUES ('SF', 2024, 0.56, 0.10, 1000)")
    conn.commit()
    build_player_features(conn, [2024])
    row = conn.execute(
        "SELECT lag2_fantasy_ppr, lag3_fantasy_ppr FROM player_features WHERE gsis_id = 'P002' AND season = 2024"
    ).fetchone()
    assert row is not None
    assert row[0] is None, f"lag2 should be NULL, got {row[0]}"
    assert row[1] is None, f"lag3 should be NULL, got {row[1]}"
    conn.close()

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
