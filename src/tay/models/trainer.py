"""Training loop for PositionMLP."""
from __future__ import annotations

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

from tay.models.network import PositionMLP


def train_model(
    X_train: torch.Tensor,
    y_train: torch.Tensor,
    X_val: torch.Tensor,
    y_val: torch.Tensor,
    epochs: int = 200,
    lr: float = 1e-3,
    batch_size: int = 64,
    patience: int = 20,
) -> tuple[PositionMLP, list[float], float]:
    """Train a PositionMLP; return (model, per-epoch train losses, val RMSE).

    Stops early when val RMSE has not improved for `patience` consecutive epochs
    and restores the best-val checkpoint before returning.
    """
    torch.set_num_threads(1)  # single-threaded matmul → deterministic across processes
    model = PositionMLP(input_size=X_train.shape[1])
    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=5e-4)
    criterion = nn.MSELoss()

    loader = DataLoader(
        TensorDataset(X_train, y_train),
        batch_size=batch_size,
        shuffle=True,
    )

    best_val_rmse = float('inf')
    best_state = {k: v.clone() for k, v in model.state_dict().items()}
    epochs_without_improvement = 0

    train_losses: list[float] = []
    for _ in range(epochs):
        model.train()
        epoch_loss = 0.0
        for xb, yb in loader:
            optimizer.zero_grad()
            loss = criterion(model(xb), yb)
            loss.backward()
            optimizer.step()
            epoch_loss += loss.item() * len(xb)
        train_losses.append(epoch_loss / len(X_train))

        model.eval()
        with torch.no_grad():
            val_rmse = float(criterion(model(X_val), y_val).item() ** 0.5)

        if val_rmse < best_val_rmse:
            best_val_rmse = val_rmse
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
            epochs_without_improvement = 0
        else:
            epochs_without_improvement += 1
            if epochs_without_improvement >= patience:
                break

    model.load_state_dict(best_state)
    model.eval()
    return model, train_losses, best_val_rmse
