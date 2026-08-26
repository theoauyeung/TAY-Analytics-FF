import pandas as pd
import numpy as np
import pytest


def _fake_s2_df(n=40, pos='WR'):
    rng = np.random.default_rng(1)
    return pd.DataFrame({
        'gsis_id': [f'p{i}' for i in range(n)],
        'season': [2022] * n,
        'position': [pos] * n,
        'team': ['KC'] * n,
        # labels
        'yards_per_target': rng.uniform(6, 12, n),
        'catch_rate': rng.uniform(0.5, 0.8, n),
        'td_rate_per_target': rng.uniform(0.04, 0.12, n),
        'yards_per_carry': [None] * n,
        'rush_td_rate': [None] * n,
        'rec_yards_per_target': [None] * n,
        'rec_catch_rate': [None] * n,
        'rec_td_rate': [None] * n,
        'yards_per_attempt': [None] * n,
        'td_rate': [None] * n,
        'int_rate': [None] * n,
        'rush_yards_per_game': [None] * n,
        'rush_tds_per_game': [None] * n,
        # features
        'ewma_yards_per_target': rng.uniform(6, 12, n),
        'ewma_catch_rate': rng.uniform(0.5, 0.8, n),
        'ewma_air_yards_per_target': rng.uniform(4, 10, n),
        'ewma_epa_per_play': rng.uniform(-0.1, 0.3, n),
        'ewma_yards_per_carry': [None] * n,
        'ewma_cpoe': [None] * n,
        'ewma_completion_pct': [None] * n,
        'age': rng.uniform(22, 32, n),
        'experience': rng.integers(1, 10, n).astype(float),
        'prev_games': rng.integers(8, 17, n).astype(float),
        'qb_ewma_epa_per_play': rng.uniform(-0.05, 0.25, n),
        'qb_ewma_cpoe': rng.uniform(-2, 5, n),
    })


def test_stage2_train_returns_rmse(tmp_path):
    from tay.models.stage2_pipeline import train_stage2_model
    df_tr = _fake_s2_df(60, 'WR')
    df_val = _fake_s2_df(20, 'WR')
    model, means, stds, features, rmse = train_stage2_model(df_tr, df_val, 'WR', 'yards_per_target')
    assert rmse >= 0
    assert len(features) > 0


def test_stage2_inference_keys(tmp_path):
    from tay.models.stage2_pipeline import train_stage2_model, infer_stage2_model
    df_tr = _fake_s2_df(60, 'WR')
    df_inf = _fake_s2_df(5, 'WR')
    model, means, stds, features, _ = train_stage2_model(df_tr, df_tr, 'WR', 'yards_per_target')
    preds = infer_stage2_model(model, means, stds, features, df_inf)
    assert len(preds) == 5
    assert all(v is not None for v in preds)
