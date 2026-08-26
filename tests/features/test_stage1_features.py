import math
import duckdb
import pytest
from tay.db import init_schema


def _make_conn():
    conn = duckdb.connect(':memory:')
    init_schema(conn)
    return conn


def _seed_minimal(conn):
    """Two WRs on same team, one season of history."""
    conn.execute("""
        INSERT INTO players (gsis_id, name, position, team, birth_date, draft_year, draft_round, draft_pick, college, height, weight, sleeper_id, espn_id, pfr_id, yahoo_id)
        VALUES ('p1', 'WR1', 'WR', 'KC', '1995-01-01', 2018, 1, 10, NULL, NULL, NULL, NULL, NULL, NULL, NULL)
    """)
    conn.execute("""
        INSERT INTO players (gsis_id, name, position, team, birth_date, draft_year, draft_round, draft_pick, college, height, weight, sleeper_id, espn_id, pfr_id, yahoo_id)
        VALUES ('p2', 'WR2', 'WR', 'KC', '1997-01-01', 2020, 2, 45, NULL, NULL, NULL, NULL, NULL, NULL, NULL)
    """)
    # Season N-1 = 2025 stats
    conn.execute("""
        INSERT INTO player_season_stats
            (gsis_id, season, team, games, targets, receptions, rec_yards, rec_tds,
             carries, rush_yards, rush_tds, attempts, completions, pass_yards,
             air_yards, epa_per_play, cpoe)
        VALUES
            ('p1', 2025, 'KC', 17, 120, 90, 1300, 10, 0, 0, 0, 0, 0, 0, 900, 0.25, 5.0),
            ('p2', 2025, 'KC', 17,  60, 45,  700,  4, 0, 0, 0, 0, 0, 0, 450, 0.10, 2.0)
    """)
    conn.execute("""
        INSERT INTO team_season_stats (team, season, games, pass_attempts, rush_attempts)
        VALUES ('KC', 2025, 17, 600, 400)
    """)
    conn.execute("""
        INSERT INTO team_features
            (team, season, pass_rate, rush_rate, team_epa, pass_epa, rush_epa,
             total_plays, pass_attempts, total_tds,
             vacated_wr_targets, vacated_rb_carries)
        VALUES ('KC', 2026, 0.62, 0.38, 0.10, 0.15, 0.05, 1000, 600, 45, 20.0, 30.0)
    """)
    conn.execute("""
        INSERT INTO coaches VALUES ('KC', 2025, 'offensive_coordinator', 'Matt Nagy')
    """)
    conn.execute("""
        INSERT INTO oc_features
            (oc_name, as_of_season, hist_wr1_target_share, hist_air_yards_pct,
             hist_rb_target_share, tenure_at_team, is_rookie_oc)
        VALUES ('Matt Nagy', 2026, 0.25, 1.5, 0.10, 2, false)
    """)
    conn.execute("INSERT INTO scheme_clusters VALUES ('KC', 2026, 3)")


def test_build_stage1_returns_dataframe():
    from tay.features.stage1_features import build_stage1_features
    conn = _make_conn()
    _seed_minimal(conn)
    df = build_stage1_features(conn, seasons=[2026])
    assert len(df) == 2
    assert 'gsis_id' in df.columns
    assert 'target_share' in df.columns
    conn.close()


def test_target_share_label_correct():
    from tay.features.stage1_features import build_stage1_features
    conn = _make_conn()
    _seed_minimal(conn)
    df = build_stage1_features(conn, seasons=[2026])
    p1 = df[df['gsis_id'] == 'p1'].iloc[0]
    # p1 had 120 targets / 600 team attempts = 0.20
    assert p1['target_share'] == pytest.approx(0.20, abs=0.001)
    conn.close()


def test_ewma_yards_per_target():
    from tay.features.stage1_features import build_stage1_features
    conn = _make_conn()
    _seed_minimal(conn)
    df = build_stage1_features(conn, seasons=[2026])
    p1 = df[df['gsis_id'] == 'p1'].iloc[0]
    # Only 1 season: ewma = 0.6 * (1300/120) = 0.6 * 10.833 ≈ 6.5
    assert p1['ewma_yards_per_target'] == pytest.approx(0.6 * (1300 / 120), abs=0.1)
    conn.close()


def test_depth_chart_rank():
    from tay.features.stage1_features import build_stage1_features
    conn = _make_conn()
    _seed_minimal(conn)
    df = build_stage1_features(conn, seasons=[2026])
    # p1 has higher ewma_target_share → rank 1; p2 → rank 2
    p1 = df[df['gsis_id'] == 'p1'].iloc[0]
    p2 = df[df['gsis_id'] == 'p2'].iloc[0]
    assert p1['depth_chart_rank'] == 1
    assert p2['depth_chart_rank'] == 2
    conn.close()


def test_scheme_cluster_present():
    from tay.features.stage1_features import build_stage1_features
    conn = _make_conn()
    _seed_minimal(conn)
    df = build_stage1_features(conn, seasons=[2026])
    assert (df['scheme_cluster'] == 3).all()
    conn.close()


def test_oc_features_joined():
    from tay.features.stage1_features import build_stage1_features
    conn = _make_conn()
    _seed_minimal(conn)
    df = build_stage1_features(conn, seasons=[2026])
    for val in df['oc_hist_wr1_target_share']:
        assert val == pytest.approx(0.25)
    assert (df['oc_tenure_at_team'] == 2).all()
    conn.close()
