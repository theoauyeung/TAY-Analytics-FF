import torch
import pytest
from tay.models.trainer import train_model
from tay.models.network import PositionMLP


def _dummy_data(n_train=200, n_val=50, n_features=24):
    torch.manual_seed(42)
    X_tr  = torch.randn(n_train, n_features)
    y_tr  = torch.randn(n_train).abs() * 100     # always positive, realistic scale
    X_val = torch.randn(n_val, n_features)
    y_val = torch.randn(n_val).abs() * 100
    return X_tr, y_tr, X_val, y_val


def test_returns_model_losses_rmse():
    X_tr, y_tr, X_val, y_val = _dummy_data()
    model, losses, val_rmse = train_model(X_tr, y_tr, X_val, y_val, epochs=5)
    assert isinstance(model, PositionMLP)
    assert len(losses) == 5
    assert isinstance(val_rmse, float)
    assert val_rmse >= 0


def test_train_losses_are_positive():
    X_tr, y_tr, X_val, y_val = _dummy_data()
    _, losses, _ = train_model(X_tr, y_tr, X_val, y_val, epochs=5)
    assert all(l > 0 for l in losses)


def test_loss_decreases_over_training():
    """Loss at epoch 50 should be lower than epoch 1 on synthetic data."""
    X_tr, y_tr, X_val, y_val = _dummy_data(n_train=500)
    _, losses, _ = train_model(X_tr, y_tr, X_val, y_val, epochs=50, lr=1e-2)
    assert losses[-1] < losses[0], f'Loss did not decrease: {losses[0]:.1f} → {losses[-1]:.1f}'


def test_model_in_eval_mode_after_training():
    X_tr, y_tr, X_val, y_val = _dummy_data()
    model, _, _ = train_model(X_tr, y_tr, X_val, y_val, epochs=3)
    assert not model.training
