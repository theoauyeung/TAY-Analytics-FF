"""Load and normalize player features for model training."""
from __future__ import annotations
from dataclasses import dataclass

import numpy as np
import torch
import duckdb

from tay.models.features import POSITION_FEATURES


@dataclass
class PositionDataset:
    X_train: torch.Tensor
    y_train: torch.Tensor
    X_val: torch.Tensor
    y_val: torch.Tensor
    means: np.ndarray
    stds: np.ndarray
    feature_names: list[str]


def load_position_data(
    conn: duckdb.DuckDBPyConnection,
    position: str,
    train_end: int = 2022,
    val_start: int = 2023,
    val_end: int = 2025,
) -> PositionDataset:
    features = POSITION_FEATURES[position]
    cols = ', '.join(f'COALESCE({f}, 0.0) AS {f}' for f in features)
    query = f"""
        SELECT {cols}, next_season_fantasy_ppr
        FROM player_features
        WHERE position = ?
          AND next_season_fantasy_ppr IS NOT NULL
          AND season BETWEEN ? AND ?
        ORDER BY season, gsis_id
    """
    train_df = conn.execute(query, [position, 2006, train_end]).df()
    val_df   = conn.execute(query, [position, val_start, val_end]).df()

    X_tr = train_df[features].values.astype(np.float32)
    y_tr = train_df['next_season_fantasy_ppr'].values.astype(np.float32)
    X_val = val_df[features].values.astype(np.float32)
    y_val = val_df['next_season_fantasy_ppr'].values.astype(np.float32)

    means = X_tr.mean(axis=0)
    stds  = X_tr.std(axis=0)
    stds[stds == 0] = 1.0  # constant column: skip normalization

    X_tr  = (X_tr  - means) / stds
    X_val = (X_val - means) / stds

    return PositionDataset(
        X_train=torch.tensor(X_tr),
        y_train=torch.tensor(y_tr),
        X_val=torch.tensor(X_val),
        y_val=torch.tensor(y_val),
        means=means,
        stds=stds,
        feature_names=features,
    )
