"""Train all position models and write projections to DuckDB."""
from __future__ import annotations
from pathlib import Path

import numpy as np
import torch

from tay.db import get_conn, init_schema
from tay.models.dataset import load_position_data
from tay.models.network import PositionMLP, save_checkpoint, load_checkpoint
from tay.models.trainer import train_model
from tay.models.features import POSITION_FEATURES

POSITIONS = ['QB', 'RB', 'WR', 'TE']
MODEL_VERSION = 'neural-v1'
_MC_SAMPLES = 50


def _mc_predict(model: PositionMLP, X: torch.Tensor) -> np.ndarray:
    """Run MC Dropout inference; returns array of shape (mc_samples, n_players)."""
    model.train()  # keep dropout active
    with torch.no_grad():
        samples = torch.stack([model(X) for _ in range(_MC_SAMPLES)], dim=0)
    return samples.numpy()  # (50, n_players)


def train_all_positions(
    conn,
    epochs: int = 200,
    train_end: int = 2022,
    val_start: int = 2023,
    val_end: int = 2025,
    models_dir: str | Path = 'models',
) -> dict[str, float]:
    """Train one MLP per position; save checkpoints; return {position: val_rmse}."""
    models_dir = Path(models_dir)
    models_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, float] = {}

    for pos in POSITIONS:
        print(f'\nTraining {pos}...')
        ds = load_position_data(conn, pos, train_end=train_end, val_start=val_start, val_end=val_end)
        print(f'  Train: {len(ds.X_train)} rows | Val: {len(ds.X_val)} rows')

        model, losses, val_rmse = train_model(
            ds.X_train, ds.y_train, ds.X_val, ds.y_val, epochs=epochs
        )
        results[pos] = val_rmse
        print(f'  Val RMSE: {val_rmse:.1f} PPR pts')

        ckpt = models_dir / f'{pos.lower()}_model.pt'
        save_checkpoint(ckpt, model, pos, ds.feature_names, ds.means, ds.stds, val_rmse)
        print(f'  Saved: {ckpt}')

    return results


def write_projections(
    conn,
    models_dir: str | Path = 'models',
    projection_season: int = 2025,
) -> int:
    """Load trained checkpoints, run MC Dropout inference, upsert to projections table."""
    models_dir = Path(models_dir)
    total = 0

    for pos in POSITIONS:
        ckpt = models_dir / f'{pos.lower()}_model.pt'
        if not ckpt.exists():
            print(f'  Skipping {pos}: no checkpoint at {ckpt}')
            continue

        model, position, feature_names, means, stds = load_checkpoint(ckpt)

        cols_sql = ', '.join(f'COALESCE({f}, 0.0) AS {f}' for f in feature_names)
        rows = conn.execute(
            f'SELECT gsis_id, {cols_sql} FROM player_features WHERE position = ? AND season = ? ORDER BY gsis_id',
            [pos, projection_season],
        ).fetchall()

        if not rows:
            print(f'  No {pos} rows for season {projection_season}')
            continue

        gsis_ids = [r[0] for r in rows]
        X_raw = np.array([[r[i + 1] for i in range(len(feature_names))] for r in rows], dtype=np.float32)
        X_norm = torch.tensor((X_raw - means) / stds)

        samples = _mc_predict(model, X_norm)  # (50, n_players)

        for j, gsis_id in enumerate(gsis_ids):
            s = np.maximum(samples[:, j], 0.0)
            mean_proj = float(s.mean())
            std_proj  = float(s.std())
            p10, p25, p50, p75, p90 = (float(np.percentile(s, p)) for p in [10, 25, 50, 75, 90])
            boom_prob = float((s > mean_proj * 1.5).mean())
            bust_prob = float((s < mean_proj * 0.5).mean())

            conn.execute("""
                INSERT OR REPLACE INTO projections
                    (gsis_id, season, model_version,
                     mean_projection, median_projection, floor, ceiling, std_dev,
                     p10, p25, p50, p75, p90,
                     boom_probability, bust_probability)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                gsis_id, projection_season, MODEL_VERSION,
                mean_proj, p50, p10, p90, std_proj,
                p10, p25, p50, p75, p90,
                boom_prob, bust_prob,
            ])
            total += 1

        conn.commit()
        print(f'  {pos}: {len(gsis_ids)} projections written for season {projection_season}')

    return total


def run_training_pipeline(
    epochs: int = 200,
    train_end: int = 2022,
    val_start: int = 2023,
    val_end: int = 2025,
    projection_season: int = 2025,
    models_dir: str | Path = 'models',
    db_path=None,
) -> None:
    conn = get_conn(db_path) if db_path else get_conn()
    init_schema(conn)

    print('=== TAY Analytics FF — Model Training ===')
    rmse = train_all_positions(
        conn, epochs=epochs,
        train_end=train_end, val_start=val_start, val_end=val_end,
        models_dir=models_dir,
    )

    print('\n=== Validation RMSE Summary ===')
    for pos, r in rmse.items():
        print(f'  {pos}: {r:.1f} PPR pts')

    print(f'\n=== Writing projections for season {projection_season} ===')
    n = write_projections(conn, models_dir=models_dir, projection_season=projection_season)
    print(f'  {n} total projections written')

    conn.close()
