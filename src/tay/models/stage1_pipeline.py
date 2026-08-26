"""Stage 1: XGBoost opportunity model — train, infer, team-normalize."""
from __future__ import annotations
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb

POSITIONS = ['QB', 'RB', 'WR', 'TE']

# Label column per position × output
_LABELS = {
    'WR': ['target_share'],
    'TE': ['target_share'],
    'RB': ['carry_share', 'rec_share'],
    'QB': ['pass_att_per_game'],
}

# Feature columns used for XGBoost (position-agnostic; missing → 0)
_FEATURE_COLS = [
    'ewma_yards_per_target', 'ewma_catch_rate', 'ewma_air_yards_per_target',
    'ewma_epa_per_play', 'ewma_yards_per_carry', 'ewma_cpoe',
    'ewma_completion_pct', 'ewma_target_share',
    'draft_pick_value', 'age', 'experience',
    'new_team_pass_rate', 'new_team_pass_epa',
    'vacated_wr_targets', 'vacated_rb_carries',
    'oc_hist_wr1_target_share', 'oc_hist_air_yards_pct',
    'oc_hist_rb_target_share', 'oc_tenure_at_team', 'is_rookie_oc',
    'scheme_cluster', 'depth_chart_rank',
]

_XGB_PARAMS = {
    'max_depth': 4,
    'learning_rate': 0.05,
    'n_estimators': 400,
    'subsample': 0.8,
    'colsample_bytree': 0.8,
    'min_child_weight': 5,
    'reg_alpha': 0.1,
    'reg_lambda': 1.0,
    'random_state': 42,
    'n_jobs': -1,
    'early_stopping_rounds': 30,
}


def _prep_X(df: pd.DataFrame) -> np.ndarray:
    X = df[[c for c in _FEATURE_COLS if c in df.columns]].copy()
    # Add any missing feature columns as zeros
    for col in _FEATURE_COLS:
        if col not in X.columns:
            X[col] = 0.0
    X = X[_FEATURE_COLS]
    X['is_rookie_oc'] = X['is_rookie_oc'].astype(float)
    return X.fillna(0.0).values.astype(np.float32)


def train_stage1_model(
    df_train: pd.DataFrame,
    df_val: pd.DataFrame,
    position: str,
    label: str,
) -> tuple[xgb.XGBRegressor, float]:
    """Train one XGBoost model for a single position x label."""
    mask_tr = df_train[label].notna()
    mask_val = df_val[label].notna()

    X_tr = _prep_X(df_train[mask_tr])
    y_tr = df_train[mask_tr][label].values.astype(np.float32)
    X_val = _prep_X(df_val[mask_val])
    y_val = df_val[mask_val][label].values.astype(np.float32)

    model = xgb.XGBRegressor(**_XGB_PARAMS, eval_metric='rmse')
    model.fit(X_tr, y_tr, eval_set=[(X_val, y_val)], verbose=False)

    preds = model.predict(X_val)
    rmse = float(np.sqrt(np.mean((preds - y_val) ** 2)))
    return model, rmse


def train_stage1_models(
    conn,
    train_end: int = 2023,
    val_start: int = 2024,
    models_dir: str | Path = 'models_stage1',
) -> dict[str, float]:
    """Train all Stage 1 models; save to models_dir; return {pos_label: val_rmse}."""
    from tay.features.stage1_features import build_stage1_features

    models_dir = Path(models_dir)
    models_dir.mkdir(parents=True, exist_ok=True)

    train_seasons = list(range(2016, train_end + 1))
    val_seasons = list(range(val_start, val_start + 1))

    df_train = build_stage1_features(conn, train_seasons)
    df_val = build_stage1_features(conn, val_seasons)

    results = {}
    for pos in POSITIONS:
        df_tr_pos = df_train[df_train['position'] == pos]
        df_val_pos = df_val[df_val['position'] == pos]

        for label in _LABELS[pos]:
            model, rmse = train_stage1_model(df_tr_pos, df_val_pos, pos, label)
            key = f'{pos}_{label}'
            results[key] = rmse
            ckpt = models_dir / f'{pos.lower()}_{label}_stage1.json'
            model.save_model(str(ckpt))
            print(f'  Stage1 {key}: val RMSE = {rmse:.4f} | saved {ckpt}')

    return results


def run_stage1_inference(
    conn,
    season: int,
    models_dir: str | Path = 'models_stage1',
) -> pd.DataFrame:
    """Load Stage 1 models, infer opportunity shares for `season`."""
    from tay.features.stage1_features import build_stage1_features

    models_dir = Path(models_dir)
    df = build_stage1_features(conn, [season])

    result_rows = []
    for pos in POSITIONS:
        df_pos = df[df['position'] == pos].copy()
        if df_pos.empty:
            continue

        X = _prep_X(df_pos)
        out = {
            'gsis_id': df_pos['gsis_id'].tolist(),
            'season': df_pos['season'].tolist(),
            'position': df_pos['position'].tolist(),
            'team': df_pos['team'].tolist(),
            'projected_target_share': [None] * len(df_pos),
            'projected_carry_share': [None] * len(df_pos),
            'projected_rec_share': [None] * len(df_pos),
            'projected_pass_att_per_game': [None] * len(df_pos),
        }

        for label in _LABELS[pos]:
            ckpt = models_dir / f'{pos.lower()}_{label}_stage1.json'
            if not ckpt.exists():
                print(f'  Warning: no Stage 1 checkpoint at {ckpt}')
                continue
            model = xgb.XGBRegressor()
            model.load_model(str(ckpt))
            preds = model.predict(X).tolist()
            out[f'projected_{label}'] = preds

        result_rows.append(pd.DataFrame(out))

    if not result_rows:
        return pd.DataFrame()
    return pd.concat(result_rows, ignore_index=True)


def normalize_team_shares(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize target_share, carry_share, rec_share to sum to 1.0 within each team.

    Stage 1 predicts per player independently; shares can sum > 1.
    Normalization: raw / sum(raw) so shares always sum to exactly 1.0.
    QB pass_att_per_game is absolute, not a share — not normalized.
    """
    df = df.copy()

    for share_col, pos_filter in [
        ('projected_target_share', ['WR', 'TE']),
        ('projected_carry_share', ['RB']),
        ('projected_rec_share', ['RB']),
    ]:
        mask = df['position'].isin(pos_filter) & df[share_col].notna()
        if not mask.any():
            continue
        team_totals = (
            df[mask].groupby(['team', 'season'])[share_col]
            .transform('sum')
        )
        df.loc[mask, share_col] = df.loc[mask, share_col] / team_totals

    return df
