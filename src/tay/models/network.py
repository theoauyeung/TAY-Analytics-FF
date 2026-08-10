from __future__ import annotations
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn


class PositionMLP(nn.Module):
    def __init__(self, input_size: int):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_size, 64), nn.ReLU(), nn.Dropout(0.3),
            nn.Linear(64, 32),         nn.ReLU(), nn.Dropout(0.2),
            nn.Linear(32, 16),         nn.ReLU(), nn.Dropout(0.2),
            nn.Linear(16, 8),          nn.ReLU(),
            nn.Linear(8, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x).squeeze(-1)


def save_checkpoint(
    path: str | Path,
    model: PositionMLP,
    position: str,
    feature_names: list[str],
    means: np.ndarray,
    stds: np.ndarray,
    val_rmse: float,
) -> None:
    torch.save({
        'model_state':   model.state_dict(),
        'input_size':    len(feature_names),
        'position':      position,
        'feature_names': feature_names,
        'means':         means,
        'stds':          stds,
        'val_rmse':      val_rmse,
    }, path)


def load_checkpoint(
    path: str | Path,
) -> tuple[PositionMLP, str, list[str], np.ndarray, np.ndarray]:
    data = torch.load(path, weights_only=False)
    model = PositionMLP(input_size=data['input_size'])
    model.load_state_dict(data['model_state'])
    model.eval()
    return model, data['position'], data['feature_names'], data['means'], data['stds']
