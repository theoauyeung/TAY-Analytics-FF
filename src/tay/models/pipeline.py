"""Train all position models and write projections to DuckDB."""
from __future__ import annotations
from pathlib import Path

import numpy as np
import torch

from tay.db import get_conn, init_schema
from tay.models.dataset import load_position_data
from tay.models.network import PositionMLP, save_checkpoint, load_checkpoint
from tay.models.trainer import train_model

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
    train_end: int = 2023,
    val_start: int = 2024,
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
    projection_season: int = 2026,
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

        # Position-specific post-hoc inference adjustments:
        if pos == 'QB':
            exp_idx       = feature_names.index('experience')        if 'experience'        in feature_names else -1
            games_idx     = feature_names.index('prev_games')        if 'prev_games'        in feature_names else -1
            rush_yds_idx  = feature_names.index('prev_rush_yards')   if 'prev_rush_yards'   in feature_names else -1
            rush_tds_idx  = feature_names.index('prev_rush_tds')     if 'prev_rush_tds'     in feature_names else -1
            pick_idx      = feature_names.index('draft_pick_value')  if 'draft_pick_value'  in feature_names else -1
            lag2_idx      = feature_names.index('lag2_fantasy_ppr')  if 'lag2_fantasy_ppr'  in feature_names else -1
            ep17_idx      = feature_names.index('ewma_fpts_proj17')  if 'ewma_fpts_proj17'  in feature_names else -1

            for j in range(len(gsis_ids)):
                exp      = float(X_raw[j, exp_idx])  if exp_idx  >= 0 else 99.0
                pick_val = float(X_raw[j, pick_idx]) if pick_idx >= 0 else 0.0

                # 2. Rushing talent — compute first, used by step 1 and 3.
                rush_yds     = float(X_raw[j, rush_yds_idx]) if rush_yds_idx >= 0 else 0.0
                rush_tds     = float(X_raw[j, rush_tds_idx]) if rush_tds_idx >= 0 else 0.0
                games_played = float(X_raw[j, games_idx])    if games_idx    >= 0 else 17.0
                pace         = 17.0 / max(games_played, 5.0)
                rush_score   = (rush_yds * pace) + (rush_tds * pace) * 80

                # 1. Experience/potential discount: generic young QBs are discounted because
                #    the model sees many busts in the training data. Skip this discount for
                #    proven rushing QBs — their rushing ability is self-evident and the
                #    experience penalty would cancel the rush bonus unfairly.
                is_high_pick    = pick_val >= 0.15
                is_proven_rusher = rush_score >= 300
                if not is_proven_rusher:
                    if exp <= 1:
                        samples[:, j] *= 0.83 if is_high_pick else 0.75
                    elif exp <= 3:
                        samples[:, j] *= 0.88 if is_high_pick else 0.82
                    elif exp <= 5:
                        samples[:, j] *= 0.94

                if rush_score < 100:
                    samples[:, j] *= 0.82   # no rushing upside: stronger penalty
                elif rush_score >= 600:
                    samples[:, j] *= 1.18   # elite dual-threat
                elif rush_score >= 400:
                    samples[:, j] *= 1.10   # solid rusher
                elif rush_score >= 200:
                    samples[:, j] *= 1.05   # occasional rusher

                # 3. Injury-season correction: when a QB played <11 games the model's
                #    raw-volume inputs under-represent talent. Blend toward anchor from
                #    lag2 PPR and per-game EWMA projection.
                if games_played < 15 and lag2_idx >= 0 and ep17_idx >= 0:
                    lag2   = float(X_raw[j, lag2_idx])
                    ep17   = float(X_raw[j, ep17_idx])
                    # For rushing QBs: weight lag2 (last healthy season) more heavily
                    # since their rushing ability is the persistent talent signal.
                    # For pocket QBs: equal weight between lag2 and per-game EWMA.
                    if rush_score >= 150:
                        anchor = 0.7 * lag2 + 0.3 * ep17
                    else:
                        anchor = (lag2 + ep17) / 2.0
                    if anchor > 200:
                        model_out = float(samples[:, j].mean())
                        # Rushing QBs: trust the anchor more (injury obscures true talent)
                        # Pocket QBs: injury correction is also talent signal, blend lightly
                        if rush_score >= 150:
                            w_model = 0.10 if games_played < 8 else 0.25
                        else:
                            w_model = 0.20 if games_played < 8 else 0.40
                        target    = w_model * model_out + (1.0 - w_model) * anchor
                        factor    = min(target / max(model_out, 20.0), 2.5)
                        samples[:, j] *= factor

        if pos == 'RB':
            games_idx = feature_names.index('prev_games')       if 'prev_games'       in feature_names else -1
            ewma_idx  = feature_names.index('ewma_fantasy_ppr') if 'ewma_fantasy_ppr' in feature_names else -1
            lag2_idx  = feature_names.index('lag2_fantasy_ppr') if 'lag2_fantasy_ppr' in feature_names else -1
            exp_idx   = feature_names.index('experience')       if 'experience'       in feature_names else -1

            for j in range(len(gsis_ids)):
                games = float(X_raw[j, games_idx]) if games_idx >= 0 else 17.0
                ewma  = float(X_raw[j, ewma_idx])  if ewma_idx  >= 0 else 0.0
                lag2  = float(X_raw[j, lag2_idx])  if lag2_idx  >= 0 else 0.0
                exp   = float(X_raw[j, exp_idx])   if exp_idx   >= 0 else 99.0

                # Injury correction: missed games → raw volume stats under-represent talent
                if games < 14 and ewma > 150:
                    model_out = float(samples[:, j].mean())
                    anchor = 0.55 * lag2 + 0.45 * ewma if lag2 > 100 else ewma
                    if anchor > model_out:
                        w_model = 0.25 if games < 10 else 0.35
                        target  = w_model * model_out + (1.0 - w_model) * anchor
                        samples[:, j] *= min(target / max(model_out, 20.0), 1.8)

                # Bounce-back correction: large single-year drop for an established back
                # (coaching change, early injury, role change) — blend toward prior level.
                # Guard: exp < 9 avoids boosting aging backs in genuine decline.
                elif ewma > 200 and exp < 9:
                    model_out = float(samples[:, j].mean())
                    if model_out < ewma * 0.82:
                        anchor = 0.40 * lag2 + 0.60 * ewma if lag2 > 100 else ewma
                        if anchor > model_out:
                            w_model = 0.50 if exp < 4 else 0.40
                            target  = w_model * model_out + (1.0 - w_model) * anchor
                            samples[:, j] *= min(target / max(model_out, 20.0), 1.4)

        if pos == 'WR':
            games_idx = feature_names.index('prev_games')       if 'prev_games'       in feature_names else -1
            ewma_idx  = feature_names.index('ewma_fantasy_ppr') if 'ewma_fantasy_ppr' in feature_names else -1
            lag2_idx  = feature_names.index('lag2_fantasy_ppr') if 'lag2_fantasy_ppr' in feature_names else -1
            prev_idx  = feature_names.index('prev_fantasy_ppr') if 'prev_fantasy_ppr' in feature_names else -1
            exp_idx   = feature_names.index('experience')       if 'experience'       in feature_names else -1

            for j in range(len(gsis_ids)):
                games = float(X_raw[j, games_idx]) if games_idx >= 0 else 17.0
                ewma  = float(X_raw[j, ewma_idx])  if ewma_idx  >= 0 else 0.0
                lag2  = float(X_raw[j, lag2_idx])  if lag2_idx  >= 0 else 0.0
                prev  = float(X_raw[j, prev_idx])  if prev_idx  >= 0 else 0.0
                exp   = float(X_raw[j, exp_idx])   if exp_idx   >= 0 else 99.0

                # Injury correction: fewer than 14 games → volume under-represents talent
                if games < 14 and ewma > 150:
                    model_out = float(samples[:, j].mean())
                    anchor = 0.50 * ewma + 0.50 * lag2 if lag2 > 100 else ewma
                    if anchor > model_out:
                        w_model = 0.25 if games < 10 else 0.35
                        target  = w_model * model_out + (1.0 - w_model) * anchor
                        samples[:, j] *= min(target / max(model_out, 20.0), 1.8)

                # Down-year correction for proven veterans: prev year significantly below
                # their established level signals transient causes, not true decline.
                elif prev < lag2 * 0.72 and lag2 > 250 and ewma < lag2 * 0.90 and exp >= 4:
                    model_out = float(samples[:, j].mean())
                    anchor    = 0.55 * lag2 + 0.45 * ewma
                    if anchor > model_out:
                        target = 0.35 * model_out + 0.65 * anchor
                        samples[:, j] *= min(target / max(model_out, 20.0), 1.5)

                # Recency dampener: young WR with a large single-year breakout from a
                # low base has elevated regression risk. lag2 < 250 guards against
                # penalising players with a solid multi-year foundation (e.g. JSN).
                if exp <= 3 and lag2 > 50 and lag2 < 250 and prev > 0 and prev / lag2 > 1.7:
                    samples[:, j] *= 0.86

        if pos == 'TE':
            games_idx = feature_names.index('prev_games')       if 'prev_games'       in feature_names else -1
            ewma_idx  = feature_names.index('ewma_fantasy_ppr') if 'ewma_fantasy_ppr' in feature_names else -1
            lag2_idx  = feature_names.index('lag2_fantasy_ppr') if 'lag2_fantasy_ppr' in feature_names else -1
            prev_idx  = feature_names.index('prev_fantasy_ppr') if 'prev_fantasy_ppr' in feature_names else -1

            for j in range(len(gsis_ids)):
                games = float(X_raw[j, games_idx]) if games_idx >= 0 else 17.0
                ewma  = float(X_raw[j, ewma_idx])  if ewma_idx  >= 0 else 0.0
                lag2  = float(X_raw[j, lag2_idx])  if lag2_idx  >= 0 else 0.0
                prev  = float(X_raw[j, prev_idx])  if prev_idx  >= 0 else 0.0

                # Injury correction with pace adjustment: a TE who missed significant
                # games has much higher per-game production than raw totals show.
                if games < 14 and ewma > 80:
                    pace      = 17.0 / max(games, 4.0)
                    adj_prev  = min(prev * pace, prev * 1.6)
                    anchor    = 0.55 * adj_prev + 0.45 * ewma if lag2 > 50 \
                                else 0.50 * adj_prev + 0.50 * ewma
                    model_out = float(samples[:, j].mean())
                    if anchor > model_out:
                        w_model = 0.25 if games < 10 else 0.40
                        target  = w_model * model_out + (1.0 - w_model) * anchor
                        samples[:, j] *= min(target / max(model_out, 20.0), 1.8)

        for j, gsis_id in enumerate(gsis_ids):
            s = np.maximum(samples[:, j], 0.0)
            mean_proj = float(s.mean())
            std_proj  = float(s.std())
            p10, p25, p50, p75, p90 = (float(np.percentile(s, p)) for p in [10, 25, 50, 75, 90])
            boom_prob = float((s > mean_proj * 1.2).mean())
            bust_prob = float((s < mean_proj * 0.8).mean())

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
    train_end: int = 2023,
    val_start: int = 2024,
    val_end: int = 2025,
    projection_season: int = 2026,
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
