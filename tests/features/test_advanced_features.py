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


@pytest.fixture
def opp_conn(tmp_path):
    """Fixture with play_by_play and player_features for opportunity share tests."""
    c = get_conn(tmp_path / 'opp_test.duckdb')
    init_schema(c)

    # Season 2025 play_by_play: KC offense, WR1 gets 8 of 20 team targets
    # Team total: 20 pass attempts, 200 air yards
    # WR1: 8 targets, 100 air yards
    # RB1: 2 targets (receiving), 20 air yards
    plays = []
    # 8 WR1 targets
    for i in range(8):
        plays.append((f'p{len(plays)}', 'g1', 2025, 1, 'REG', 'KC', 'DEN', 'pass',
                      1, 'wr1', None, 12.5, 1, 0, 0))
    # 2 RB1 targets
    for i in range(2):
        plays.append((f'p{len(plays)}', 'g1', 2025, 1, 'REG', 'KC', 'DEN', 'pass',
                      1, 'rb1', None, 10.0, 1, 0, 0))
    # 10 other targets (no receiver_id tracked = other players)
    for i in range(10):
        plays.append((f'p{len(plays)}', 'g1', 2025, 1, 'REG', 'KC', 'DEN', 'pass',
                      1, 'oth', None, 7.5, 1, 0, 0))

    c.executemany("""
        INSERT INTO play_by_play
            (play_id, game_id, season, week, season_type, posteam, defteam, play_type,
             pass_attempt, receiver_id, rusher_id, air_yards, complete_pass,
             touchdown, rush_attempt)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, plays)

    # player_features for 2026 (predicting from 2025): WR1 on KC
    c.execute("""
        INSERT INTO player_features (gsis_id, season, position, team)
        VALUES ('wr1', 2026, 'WR', 'KC'),
               ('rb1', 2026, 'RB', 'KC')
    """)
    # Also add players table rows (needed for SOS tests later)
    c.execute("""
        INSERT INTO players (gsis_id, name, position) VALUES
            ('wr1', 'WR One', 'WR'),
            ('rb1', 'RB One', 'RB'),
            ('oth', 'Other', 'WR')
    """)
    yield c
    c.close()


def test_target_share(opp_conn):
    from tay.features.advanced_features import _migrate_advanced_features, _compute_opportunity_share
    _migrate_advanced_features(opp_conn)
    _compute_opportunity_share(opp_conn, prior_season=2025, target_season=2026)

    row = opp_conn.execute(
        "SELECT target_share FROM player_features WHERE gsis_id = 'wr1' AND season = 2026"
    ).fetchone()
    assert row is not None
    # WR1: 8 targets / 20 team pass attempts = 0.40
    assert abs(row[0] - 0.40) < 0.01


def test_air_yards_share(opp_conn):
    from tay.features.advanced_features import _migrate_advanced_features, _compute_opportunity_share
    _migrate_advanced_features(opp_conn)
    _compute_opportunity_share(opp_conn, prior_season=2025, target_season=2026)

    row = opp_conn.execute(
        "SELECT air_yards_share FROM player_features WHERE gsis_id = 'wr1' AND season = 2026"
    ).fetchone()
    # WR1 air_yards: 8 * 12.5 = 100; team total: 8*12.5 + 2*10 + 10*7.5 = 100+20+75 = 195
    assert row is not None
    assert abs(row[0] - 100 / 195) < 0.01


def test_wopr(opp_conn):
    from tay.features.advanced_features import _migrate_advanced_features, _compute_opportunity_share
    _migrate_advanced_features(opp_conn)
    _compute_opportunity_share(opp_conn, prior_season=2025, target_season=2026)

    row = opp_conn.execute(
        "SELECT target_share, air_yards_share, wopr FROM player_features WHERE gsis_id = 'wr1' AND season = 2026"
    ).fetchone()
    expected_wopr = 1.5 * row[0] + 0.7 * row[1]
    assert abs(row[2] - expected_wopr) < 0.001


def test_rb_gets_target_share(opp_conn):
    from tay.features.advanced_features import _migrate_advanced_features, _compute_opportunity_share
    _migrate_advanced_features(opp_conn)
    _compute_opportunity_share(opp_conn, prior_season=2025, target_season=2026)

    row = opp_conn.execute(
        "SELECT target_share FROM player_features WHERE gsis_id = 'rb1' AND season = 2026"
    ).fetchone()
    # RB1: 2 / 20 = 0.10
    assert row is not None
    assert abs(row[0] - 0.10) < 0.01


@pytest.fixture
def consist_conn(tmp_path):
    """3 weeks of plays for WR1: [10.0, 21.0, 2.0] weekly PPR pts."""
    c = get_conn(tmp_path / 'consist.duckdb')
    init_schema(c)

    plays = []
    # Week 1: 4 completions, 15 yards each → 4*1 + 60*0.1 + 0 = 10.0
    for i in range(4):
        plays.append((f'w1_c{i}', 'g1', 2025, 1, 'REG', 'KC', 'DEN', 'pass',
                      1, 'wr1', None, 10.0, 15.0, 1, 0, 0))
    for i in range(2):  # incompletions
        plays.append((f'w1_i{i}', 'g1', 2025, 1, 'REG', 'KC', 'DEN', 'pass',
                      1, 'wr1', None, 10.0, 0.0, 0, 0, 0))

    # Week 2: 4 completions 20 yards + 1 TD completion 20 yards → 5*1 + 100*0.1 + 6 = 21.0 (boom)
    for i in range(4):
        plays.append((f'w2_c{i}', 'g2', 2025, 2, 'REG', 'KC', 'LV', 'pass',
                      1, 'wr1', None, 15.0, 20.0, 1, 0, 0))
    plays.append(('w2_td', 'g2', 2025, 2, 'REG', 'KC', 'LV', 'pass',
                  1, 'wr1', None, 15.0, 20.0, 1, 1, 0))
    for i in range(2):  # incompletions
        plays.append((f'w2_i{i}', 'g2', 2025, 2, 'REG', 'KC', 'LV', 'pass',
                      1, 'wr1', None, 15.0, 0.0, 0, 0, 0))

    # Week 3: 1 completion, 10 yards → 1*1 + 10*0.1 = 2.0 (floor)
    plays.append(('w3_c0', 'g3', 2025, 3, 'REG', 'KC', 'LAC', 'pass',
                  1, 'wr1', None, 10.0, 10.0, 1, 0, 0))
    for i in range(5):  # incompletions
        plays.append((f'w3_i{i}', 'g3', 2025, 3, 'REG', 'KC', 'LAC', 'pass',
                      1, 'wr1', None, 10.0, 0.0, 0, 0, 0))

    c.executemany("""
        INSERT INTO play_by_play
            (play_id, game_id, season, week, season_type, posteam, defteam, play_type,
             pass_attempt, receiver_id, rusher_id, air_yards, yards_gained,
             complete_pass, touchdown, rush_attempt)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, plays)

    c.execute("""
        INSERT INTO player_features (gsis_id, season, position, team)
        VALUES ('wr1', 2026, 'WR', 'KC')
    """)
    yield c
    c.close()


def test_boom_rate(consist_conn):
    from tay.features.advanced_features import _migrate_advanced_features, _compute_consistency
    _migrate_advanced_features(consist_conn)
    _compute_consistency(consist_conn, prior_season=2025, target_season=2026)

    row = consist_conn.execute(
        "SELECT boom_rate FROM player_features WHERE gsis_id = 'wr1' AND season = 2026"
    ).fetchone()
    # Week 2 (21 pts) is the only boom week out of 3 → 1/3
    assert row is not None
    assert abs(row[0] - 1 / 3) < 0.01


def test_floor_rate(consist_conn):
    from tay.features.advanced_features import _migrate_advanced_features, _compute_consistency
    _migrate_advanced_features(consist_conn)
    _compute_consistency(consist_conn, prior_season=2025, target_season=2026)

    row = consist_conn.execute(
        "SELECT floor_rate FROM player_features WHERE gsis_id = 'wr1' AND season = 2026"
    ).fetchone()
    # Week 3 (2 pts) is the only floor week → 1/3
    assert row is not None
    assert abs(row[0] - 1 / 3) < 0.01


def test_weekly_fpts_std(consist_conn):
    from tay.features.advanced_features import _migrate_advanced_features, _compute_consistency
    _migrate_advanced_features(consist_conn)
    _compute_consistency(consist_conn, prior_season=2025, target_season=2026)

    row = consist_conn.execute(
        "SELECT weekly_fpts_std FROM player_features WHERE gsis_id = 'wr1' AND season = 2026"
    ).fetchone()
    # Weekly pts: wk1=10.0, wk2=21.0, wk3=2.0; std_samp > 0
    assert row is not None
    assert row[0] > 0


def test_postseason_excluded(tmp_path):
    """Playoff plays (season_type != REG) must not count toward target share."""
    c = get_conn(tmp_path / 'post_test.duckdb')
    init_schema(c)
    c.execute("""
        INSERT INTO play_by_play
            (play_id, game_id, season, week, season_type, posteam, defteam, play_type,
             pass_attempt, receiver_id, rusher_id, air_yards, complete_pass,
             touchdown, rush_attempt)
        VALUES ('p1', 'g1', 2025, 19, 'POST', 'KC', 'DEN', 'pass', 1, 'wr1', NULL, 10.0, 1, 0, 0)
    """)
    c.execute("INSERT INTO player_features (gsis_id, season, position, team) VALUES ('wr1', 2026, 'WR', 'KC')")
    from tay.features.advanced_features import _migrate_advanced_features, _compute_opportunity_share
    _migrate_advanced_features(c)
    _compute_opportunity_share(c, prior_season=2025, target_season=2026)
    row = c.execute("SELECT target_share FROM player_features WHERE gsis_id = 'wr1' AND season = 2026").fetchone()
    # No REG plays → target_share should be NULL (no update)
    assert row[0] is None
    c.close()
