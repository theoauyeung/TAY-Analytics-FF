import tempfile
from pathlib import Path
import numpy as np
import torch
import pytest
from tay.models.network import PositionMLP, save_checkpoint, load_checkpoint


def test_forward_shape():
    model = PositionMLP(input_size=24)
    x = torch.randn(32, 24)
    out = model(x)
    assert out.shape == (32,), f'Expected (32,), got {out.shape}'


def test_single_sample():
    model = PositionMLP(input_size=21)
    x = torch.randn(1, 21)
    out = model(x)
    assert out.shape == (1,)


def test_five_linear_layers():
    model = PositionMLP(input_size=10)
    linear_count = sum(1 for m in model.modules() if isinstance(m, torch.nn.Linear))
    assert linear_count == 5, f'Expected 5 Linear layers, got {linear_count}'


def test_save_and_load_roundtrip():
    model = PositionMLP(input_size=24)
    means = np.zeros(24, dtype=np.float32)
    stds  = np.ones(24, dtype=np.float32)
    feature_names = [f'f{i}' for i in range(24)]

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / 'rb_model.pt'
        save_checkpoint(path, model, 'RB', feature_names, means, stds, val_rmse=42.5)

        loaded_model, pos, feats, loaded_means, loaded_stds = load_checkpoint(path)

    assert pos == 'RB'
    assert feats == feature_names
    np.testing.assert_array_equal(loaded_means, means)
    np.testing.assert_array_equal(loaded_stds, stds)
    x = torch.randn(4, 24)
    loaded_model.eval()
    model.eval()
    with torch.no_grad():
        np.testing.assert_allclose(
            loaded_model(x).numpy(), model(x).numpy(), rtol=1e-5
        )


def test_loaded_model_is_eval_mode():
    model = PositionMLP(input_size=10)
    means = np.zeros(10, dtype=np.float32)
    stds  = np.ones(10, dtype=np.float32)
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / 'qb_model.pt'
        save_checkpoint(path, model, 'QB', [f'f{i}' for i in range(10)], means, stds, 55.0)
        loaded_model, *_ = load_checkpoint(path)
    assert not loaded_model.training
