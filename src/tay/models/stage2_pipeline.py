"""Stage 2: neural net efficiency model — train and infer per position × output."""
from __future__ import annotations
from pathlib import Path

import numpy as np
import torch
import pandas as pd

from tay.features.stage2_features import build_stage2_features
from tay.models.network import PositionMLP, save_checkpoint, load_checkpoint
from tay.models.trainer import train_model

POSITIONS = ['QB', 'RB', 'WR', 'TE']

_LABELS_BY_POS = {
    'WR': ['yards_per_target', 'catch_rate', 'td_rate_per_target'],
    'TE': ['yards_per_target', 'catch_rate', 'td_rate_per_target'],
    'RB': ['yards_per_carry', 'rush_td_rate', 'rec_yards_per_target', 'rec_catch_rate', 'rec_td_rate'],
    'QB': ['yards_per_attempt', 'td_rate', 'int_rate', 'rush_yards_per_game', 'rush_tds_per_game'],
}

_WR_TE_FEATURES = [
    'ewma_yards_per_target', 'ewma_catch_rate', 'ewma_air_yards_per_target',
    'ewma_epa_per_play', 'age', 'experience', 'prev_games',
    'qb_ewma_epa_per_play', 'qb_ewma_cpoe',
]
_RB_FEATURES = [
    'ewma_yards_per_carry', 'ewma_catch_rate', 'ewma_epa_per_play',
    'age', 'experience', 'prev_games',
    'qb_ewma_epa_per_play',
]
_QB_FEATURES = [
    'ewma_yards_per_target', 'ewma_completion_pct', 'ewma_cpoe', 'ewma_epa_per_play',
    'ewma_yards_per_carry', 'age', 'experience', 'prev_games',
]

_FEATURE_COLS = {
    'WR': _WR_TE_FEATURES,
    'TE': _WR_TE_FEATURES,
    'RB': _RB_FEATURES,
    'QB': _QB_FEATURES,
}


def _prep_X(df: pd.DataFrame, feature_cols: list[str]) -> np.ndarray:
    X = df[feature_cols].copy().fillna(0.0)
    return X.values.astype(np.float32)


def train_stage2_model(
    df_train: pd.DataFrame,
    df_val: pd.DataFrame,
    position: str,
    label: str,
    epochs: int = 150,
) -> tuple:
    """Train one neural net for position × label. Returns (model, means, stds, features, val_rmse)."""
    features = _FEATURE_COLS[position]
    mask_tr = df_train[label].notna()
    mask_val = df_val[label].notna()

    X_tr = _prep_X(df_train[mask_tr], features)
    y_tr = df_train[mask_tr][label].values.astype(np.float32)
    X_val = _prep_X(df_val[mask_val], features)
    y_val = df_val[mask_val][label].values.astype(np.float32)

    means = X_tr.mean(axis=0)
    stds = X_tr.std(axis=0)
    stds[stds == 0] = 1.0

    X_tr_n = torch.tensor((X_tr - means) / stds)
    X_val_n = torch.tensor((X_val - means) / stds)

    model, _, val_rmse = train_model(
        X_tr_n, torch.tensor(y_tr),
        X_val_n, torch.tensor(y_val),
        epochs=epochs,
    )
    return model, means, stds, features, val_rmse


def infer_stage2_model(
    model: PositionMLP,
    means: np.ndarray,
    stds: np.ndarray,
    feature_cols: list[str],
    df: pd.DataFrame,
) -> list[float]:
    """Run inference with MC dropout disabled; return list of floats."""
    X = _prep_X(df, feature_cols)
    X_n = torch.tensor((X - means) / stds)
    model.eval()
    with torch.no_grad():
        preds = model(X_n).numpy().tolist()
    return [max(float(p), 0.0) for p in preds]


def train_stage2_models(
    conn,
    train_end: int = 2023,
    val_start: int = 2024,
    models_dir: str | Path = 'models_stage2',
    epochs: int = 150,
) -> dict[str, float]:
    """Train all Stage 2 models. QB runs first so efficiency can be computed for context."""
    models_dir = Path(models_dir)
    models_dir.mkdir(parents=True, exist_ok=True)

    train_seasons = list(range(2016, train_end + 1))
    val_seasons = [val_start]

    # QB first — build all features for train/val seasons to extract EWMA context
    df_tr_all = build_stage2_features(conn, train_seasons)
    df_val_all = build_stage2_features(conn, val_seasons)

    df_tr_qb = df_tr_all[df_tr_all['position'] == 'QB'].copy()
    df_val_qb = df_val_all[df_val_all['position'] == 'QB'].copy()

    results = {}
    for label in _LABELS_BY_POS['QB']:
        model, means, stds, features, rmse = train_stage2_model(
            df_tr_qb, df_val_qb, 'QB', label, epochs=epochs
        )
        key = f'QB_{label}'
        results[key] = rmse
        save_checkpoint(models_dir / f'qb_{label}_stage2.pt', model, 'QB', features, means, stds, rmse)
        print(f'  Stage2 {key}: val RMSE = {rmse:.4f}')

    # Build QB efficiency context from historical EWMA features (not predicted outputs)
    qb_eff_tr = {
        row['gsis_id']: {'ewma_epa': row.get('ewma_epa_per_play'), 'ewma_cpoe': row.get('ewma_cpoe')}
        for _, row in df_tr_qb.iterrows()
    }
    qb_eff_val = {
        row['gsis_id']: {'ewma_epa': row.get('ewma_epa_per_play'), 'ewma_cpoe': row.get('ewma_cpoe')}
        for _, row in df_val_qb.iterrows()
    }

    # Skill positions (WR, TE, RB) — build WITH QB context for train/val consistency
    df_tr_skill = build_stage2_features(conn, train_seasons, qb_efficiency=qb_eff_tr)
    df_val_skill = build_stage2_features(conn, val_seasons, qb_efficiency=qb_eff_val)
    for pos in ['WR', 'TE', 'RB']:
        df_tr = df_tr_skill[df_tr_skill['position'] == pos]
        df_val = df_val_skill[df_val_skill['position'] == pos]

        for label in _LABELS_BY_POS[pos]:
            model, means, stds, features, rmse = train_stage2_model(
                df_tr, df_val, pos, label, epochs=epochs
            )
            key = f'{pos}_{label}'
            results[key] = rmse
            save_checkpoint(
                models_dir / f'{pos.lower()}_{label}_stage2.pt',
                model, pos, features, means, stds, rmse,
            )
            print(f'  Stage2 {key}: val RMSE = {rmse:.4f}')

    return results


def run_stage2_inference(
    conn,
    season: int,
    models_dir: str | Path = 'models_stage2',
) -> dict[str, dict[str, float]]:
    """Load Stage 2 checkpoints, infer efficiency for all players in `season`.

    Returns {gsis_id: {label: value, ...}}.
    QB runs first; its efficiency is injected as context for WR/TE/RB.
    """
    models_dir = Path(models_dir)
    results: dict[str, dict[str, float]] = {}

    # QB first
    df_qb = build_stage2_features(conn, [season]).query("position == 'QB'")
    for label in _LABELS_BY_POS['QB']:
        ckpt = models_dir / f'qb_{label}_stage2.pt'
        if not ckpt.exists():
            continue
        model, pos, features, means, stds = load_checkpoint(ckpt)
        preds = infer_stage2_model(model, means, stds, features, df_qb)
        for gsis_id, pred in zip(df_qb['gsis_id'], preds):
            results.setdefault(gsis_id, {})[label] = pred

    # Build QB efficiency context from historical EWMA features (not predicted outputs)
    qb_efficiency = {
        row['gsis_id']: {
            'ewma_epa': row.get('ewma_epa_per_play'),
            'ewma_cpoe': row.get('ewma_cpoe'),
        }
        for _, row in df_qb.iterrows()
    }

    # Skill positions with QB context
    for pos in ['WR', 'TE', 'RB']:
        df_pos = build_stage2_features(conn, [season], qb_efficiency=qb_efficiency).query(
            f"position == '{pos}'"
        )
        for label in _LABELS_BY_POS[pos]:
            ckpt = models_dir / f'{pos.lower()}_{label}_stage2.pt'
            if not ckpt.exists():
                continue
            model, _, features, means, stds = load_checkpoint(ckpt)
            preds = infer_stage2_model(model, means, stds, features, df_pos)
            for gsis_id, pred in zip(df_pos['gsis_id'], preds):
                results.setdefault(gsis_id, {})[label] = pred

    return results
