import duckdb
import pytest
from tay.db import init_schema


def _make_conn():
    conn = duckdb.connect(':memory:')
    init_schema(conn)
    return conn


def test_wr_composition_formula():
    from tay.models.composition import compose_projections
    conn = _make_conn()
    # Seed team: 595 pass attempts total (35/game × 17)
    conn.execute("""
        INSERT INTO team_features
            (team, season, pass_rate, rush_rate, team_epa, pass_epa, rush_epa,
             total_plays, pass_attempts, total_tds)
        VALUES ('KC', 2026, 0.60, 0.40, 0.10, 0.15, 0.05, 1000, 595, 45)
    """)
    conn.execute("""
        INSERT INTO players (gsis_id, name, position, team)
        VALUES ('w1', 'Test WR', 'WR', 'KC')
    """)

    import pandas as pd
    stage1_df = pd.DataFrame([{
        'gsis_id': 'w1', 'season': 2026, 'position': 'WR', 'team': 'KC',
        'projected_target_share': 0.20,
        'projected_carry_share': None,
        'projected_rec_share': None,
        'projected_pass_att_per_game': None,
    }])
    stage2 = {
        'w1': {
            'yards_per_target': 9.0,
            'catch_rate': 0.70,
            'td_rate_per_target': 0.08,
        }
    }

    count = compose_projections(conn, stage1_df, stage2, season=2026, model_version='two-stage-v1')
    assert count == 1

    row = conn.execute(
        "SELECT mean_projection FROM projections WHERE gsis_id = 'w1'"
    ).fetchone()
    assert row is not None

    # targets = 0.20 × 35.0 × 17 = 119
    targets = 0.20 * 35.0 * 17
    expected = targets * 0.70 * 1.0 + targets * 9.0 * 0.1 + targets * 0.08 * 6.0
    assert row[0] == pytest.approx(expected, abs=0.5)
    conn.close()


def test_qb_composition_formula():
    from tay.models.composition import compose_projections
    conn = _make_conn()
    conn.execute("""
        INSERT INTO team_features
            (team, season, pass_rate, rush_rate, team_epa, pass_epa, rush_epa,
             total_plays, pass_attempts, total_tds)
        VALUES ('KC', 2026, 0.60, 0.40, 0.10, 0.15, 0.05, 1000, 595, 45)
    """)
    conn.execute("""
        INSERT INTO players (gsis_id, name, position, team)
        VALUES ('qb1', 'Test QB', 'QB', 'KC')
    """)

    import pandas as pd
    stage1_df = pd.DataFrame([{
        'gsis_id': 'qb1', 'season': 2026, 'position': 'QB', 'team': 'KC',
        'projected_target_share': None,
        'projected_carry_share': None,
        'projected_rec_share': None,
        'projected_pass_att_per_game': 35.0,
    }])
    stage2 = {
        'qb1': {
            'yards_per_attempt': 7.5,
            'td_rate': 0.055,
            'int_rate': 0.020,
            'rush_yards_per_game': 30.0,
            'rush_tds_per_game': 0.30,
        }
    }

    count = compose_projections(conn, stage1_df, stage2, season=2026, model_version='two-stage-v1')
    assert count == 1

    row = conn.execute(
        "SELECT mean_projection FROM projections WHERE gsis_id = 'qb1'"
    ).fetchone()
    pass_att = 35.0 * 17
    expected = (
        pass_att * 7.5 * 0.04
        + pass_att * 0.055 * 4.0
        - pass_att * 0.020 * 2.0
        + 30.0 * 17 * 0.1
        + 0.30 * 17 * 6.0
    )
    assert row[0] == pytest.approx(expected, abs=0.5)
    conn.close()


def test_missing_stage2_player_skipped():
    from tay.models.composition import compose_projections
    conn = _make_conn()
    conn.execute("""
        INSERT INTO team_features
            (team, season, pass_rate, rush_rate, team_epa, pass_epa, rush_epa,
             total_plays, pass_attempts, total_tds)
        VALUES ('KC', 2026, 0.60, 0.40, 0.10, 0.15, 0.05, 1000, 595, 45)
    """)
    conn.execute("INSERT INTO players (gsis_id, name, position, team) VALUES ('w1', 'Test WR', 'WR', 'KC')")
    import pandas as pd
    stage1_df = pd.DataFrame([{
        'gsis_id': 'w1', 'season': 2026, 'position': 'WR', 'team': 'KC',
        'projected_target_share': 0.20,
        'projected_carry_share': None, 'projected_rec_share': None,
        'projected_pass_att_per_game': None,
    }])
    count = compose_projections(conn, stage1_df, {}, season=2026, model_version='two-stage-v1')
    assert count == 0
    conn.close()
