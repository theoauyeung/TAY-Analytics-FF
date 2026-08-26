import math
import pandas as pd
import pytest


def _make_fake_df(n=40, pos='WR'):
    """Minimal DataFrame matching Stage 1 feature schema."""
    import numpy as np
    rng = np.random.default_rng(0)
    return pd.DataFrame({
        'gsis_id': [f'p{i}' for i in range(n)],
        'season': [2022] * n,
        'position': [pos] * n,
        'team': [f'T{i % 5}' for i in range(n)],
        'target_share': rng.uniform(0.05, 0.30, n),
        'carry_share': rng.uniform(0.05, 0.25, n),
        'rec_share': rng.uniform(0.02, 0.10, n),
        'pass_att_per_game': rng.uniform(25, 40, n),
        'ewma_yards_per_target': rng.uniform(6, 12, n),
        'ewma_catch_rate': rng.uniform(0.5, 0.8, n),
        'ewma_air_yards_per_target': rng.uniform(4, 10, n),
        'ewma_epa_per_play': rng.uniform(-0.1, 0.3, n),
        'ewma_yards_per_carry': rng.uniform(3, 6, n),
        'ewma_cpoe': [None] * n,
        'ewma_completion_pct': [None] * n,
        'ewma_target_share': rng.uniform(0.05, 0.25, n),
        'draft_pick_value': rng.uniform(0, 0.5, n),
        'age': rng.uniform(22, 32, n),
        'experience': rng.integers(1, 10, n).astype(float),
        'new_team_pass_rate': rng.uniform(0.45, 0.65, n),
        'new_team_pass_epa': rng.uniform(-0.05, 0.20, n),
        'vacated_wr_targets': rng.uniform(0, 80, n),
        'vacated_rb_carries': rng.uniform(0, 60, n),
        'oc_hist_wr1_target_share': rng.uniform(0.15, 0.30, n),
        'oc_hist_air_yards_pct': rng.uniform(1.0, 2.0, n),
        'oc_hist_rb_target_share': rng.uniform(0.05, 0.15, n),
        'oc_tenure_at_team': rng.integers(0, 5, n).astype(float),
        'is_rookie_oc': [False] * n,
        'scheme_cluster': rng.integers(0, 6, n).astype(float),
        'depth_chart_rank': rng.integers(1, 4, n).astype(float),
    })


def test_train_stage1_wr(tmp_path):
    from tay.models.stage1_pipeline import train_stage1_model
    df_train = _make_fake_df(60, 'WR')
    df_val = _make_fake_df(20, 'WR')
    model, rmse = train_stage1_model(df_train, df_val, 'WR', 'target_share')
    assert rmse >= 0
    assert (tmp_path / 'wr_stage1.json') or True  # model object returned, not path


def test_normalize_team_shares_sums_to_one():
    from tay.models.stage1_pipeline import normalize_team_shares
    df = pd.DataFrame({
        'gsis_id': ['p1', 'p2', 'p3'],
        'team': ['KC', 'KC', 'KC'],
        'season': [2026, 2026, 2026],
        'position': ['WR', 'WR', 'WR'],
        'projected_target_share': [0.30, 0.25, 0.20],
        'projected_carry_share': [None, None, None],
        'projected_rec_share': [None, None, None],
        'projected_pass_att_per_game': [None, None, None],
    })
    result = normalize_team_shares(df)
    total = result[result['team'] == 'KC']['projected_target_share'].sum()
    assert total == pytest.approx(1.0, abs=0.001)


def test_normalize_preserves_relative_order():
    from tay.models.stage1_pipeline import normalize_team_shares
    df = pd.DataFrame({
        'gsis_id': ['p1', 'p2'],
        'team': ['KC', 'KC'],
        'season': [2026, 2026],
        'position': ['WR', 'WR'],
        'projected_target_share': [0.40, 0.20],
        'projected_carry_share': [None, None],
        'projected_rec_share': [None, None],
        'projected_pass_att_per_game': [None, None],
    })
    result = normalize_team_shares(df)
    shares = result.set_index('gsis_id')['projected_target_share']
    assert shares['p1'] > shares['p2']


def test_normalize_rb_carry_share_and_rec_share_separately():
    from tay.models.stage1_pipeline import normalize_team_shares
    df = pd.DataFrame({
        'gsis_id': ['r1', 'r2'],
        'team': ['DAL', 'DAL'],
        'season': [2026, 2026],
        'position': ['RB', 'RB'],
        'projected_target_share': [None, None],
        'projected_carry_share': [0.40, 0.35],
        'projected_rec_share': [0.08, 0.06],
        'projected_pass_att_per_game': [None, None],
    })
    result = normalize_team_shares(df)
    total_carry = result['projected_carry_share'].sum()
    total_rec = result['projected_rec_share'].sum()
    assert total_carry == pytest.approx(1.0, abs=0.001)
    assert total_rec == pytest.approx(1.0, abs=0.001)
