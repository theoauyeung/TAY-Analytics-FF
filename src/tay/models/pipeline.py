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
_MC_SAMPLES = 200

# Typical PPR output for a round-1 pick starting rookie by position.
# Later rounds scale down by round tier (1.0 / 0.65 / 0.45 / 0.25).
_ROOKIE_R1_BASELINE = {'QB': 260, 'RB': 200, 'WR': 155, 'TE': 115}


def _build_adp_implied(conn, pos: str, season: int) -> dict[str, float]:
    """Return {gsis_id: implied_projection} for rookies by interpolating from
    veteran ADP → projection comps.

    Uses FantasyCalc ranks as the primary source (single platform for consistency).
    For each rookie, finds veteran comps within a ±20 pick window and takes the
    60th-percentile projection (skewed upward to avoid backup outliers dragging
    down the implied value for starters).
    """
    vet = conn.execute("""
        SELECT a.rank AS fc_rank, pr.mean_projection AS proj
        FROM adp a
        JOIN projections pr ON pr.gsis_id = a.gsis_id AND pr.season = ?
        JOIN players p      ON p.gsis_id  = a.gsis_id
        WHERE p.position = ? AND a.season = ? AND COALESCE(p.draft_year, 0) < 2026
          AND a.platform = 'fantasycalc' AND a.rank <= 250
    """, [season, pos, season]).fetchall()

    if len(vet) < 5:
        return {}

    vet_ranks = np.array([r[0] for r in vet], dtype=float)
    vet_projs = np.array([r[1] for r in vet], dtype=float)
    order = np.argsort(vet_ranks)
    vet_ranks, vet_projs = vet_ranks[order], vet_projs[order]

    rookies = conn.execute("""
        SELECT p.gsis_id,
               COALESCE(
                   (SELECT a2.rank FROM adp a2
                    WHERE a2.gsis_id = p.gsis_id AND a2.season = ? AND a2.platform = 'fantasycalc'
                    LIMIT 1),
                   (SELECT MIN(a3.rank) FROM adp a3
                    WHERE a3.gsis_id = p.gsis_id AND a3.season = ?)
               ) AS fc_rank
        FROM players p
        WHERE p.position = ? AND p.draft_year = 2026
          AND EXISTS (SELECT 1 FROM adp a WHERE a.gsis_id = p.gsis_id AND a.season = ?)
    """, [season, season, pos, season]).fetchall()

    result: dict[str, float] = {}
    for gsis_id, adp_rank in rookies:
        if adp_rank is None:
            continue
        mask = np.abs(vet_ranks - adp_rank) <= 20
        if mask.sum() >= 3:
            implied = float(np.percentile(vet_projs[mask], 60))
        else:
            idx = np.argsort(np.abs(vet_ranks - adp_rank))[:7]
            implied = float(np.percentile(vet_projs[idx], 60))
        result[gsis_id] = implied

    return result


def _apply_rookie_anchor(
    samples: np.ndarray,
    X_raw: np.ndarray,
    feature_names: list[str],
    pos: str,
    gsis_ids: list[str] | None = None,
    adp_implied: dict[str, float] | None = None,
) -> None:
    """Blend rookie projections toward an ADP-implied output level.

    Primary anchor: median veteran projection at the same ADP tier (self-calibrating).
    Fallback when no ADP data: position baseline scaled by draft round.
    """
    rookie_idx = feature_names.index('is_rookie')        if 'is_rookie'        in feature_names else -1
    pick_idx   = feature_names.index('draft_pick_value') if 'draft_pick_value' in feature_names else -1
    if rookie_idx < 0 or pick_idx < 0:
        return

    baseline   = _ROOKIE_R1_BASELINE.get(pos, 120)
    round_tier = {1: 1.0, 2: 0.65, 3: 0.45}

    for j in range(samples.shape[1]):
        if float(X_raw[j, rookie_idx]) < 0.5:
            continue

        pick_val = float(X_raw[j, pick_idx])
        if pick_val > 0:
            overall      = round(1.0 / (pick_val ** 2))
            draft_round  = max(1, (overall - 1) // 32 + 1)
        else:
            draft_round = 7

        tier = round_tier.get(draft_round, 0.25)

        gid = gsis_ids[j] if gsis_ids else None
        if adp_implied and gid and gid in adp_implied:
            anchor   = adp_implied[gid]
            w_anchor = 0.80
        else:
            anchor   = baseline * tier
            w_anchor = max(0.35, tier * 0.80)

        model_out = float(samples[:, j].mean())
        target    = (1.0 - w_anchor) * model_out + w_anchor * anchor
        if model_out > 0:
            samples[:, j] *= target / max(model_out, 10.0)


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
            ewma_idx      = feature_names.index('ewma_fantasy_ppr')  if 'ewma_fantasy_ppr'  in feature_names else -1

            for j in range(len(gsis_ids)):
                exp      = float(X_raw[j, exp_idx])  if exp_idx  >= 0 else 99.0
                pick_val = float(X_raw[j, pick_idx]) if pick_idx >= 0 else 0.0

                # 2. Rushing talent — compute first, used by step 1 and 3.
                rush_yds     = float(X_raw[j, rush_yds_idx]) if rush_yds_idx >= 0 else 0.0
                rush_tds     = float(X_raw[j, rush_tds_idx]) if rush_tds_idx >= 0 else 0.0
                games_played = float(X_raw[j, games_idx])    if games_idx    >= 0 else 17.0
                pace         = 17.0 / max(games_played, 5.0)
                rush_score   = (rush_yds * pace) + (rush_tds * pace) * 20

                # 1. Experience/potential discount: generic young QBs are discounted because
                #    the model sees many busts in the training data. Skip this discount for
                #    proven rushing QBs — their rushing ability is self-evident and the
                #    experience penalty would cancel the rush bonus unfairly.
                is_high_pick    = pick_val >= 0.15
                is_proven_rusher = rush_score >= 800
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

                # 3. Injury-season correction: when a QB played <15 games the model's
                #    raw-volume inputs under-represent talent. Blend toward anchor from
                #    lag2 PPR and EWMA projection.
                #    Note: ewma_fpts_proj17 is often unpopulated (=0); fall back to
                #    ewma_fantasy_ppr which is always available.
                if games_played < 15 and lag2_idx >= 0:
                    lag2     = float(X_raw[j, lag2_idx])
                    ep17     = float(X_raw[j, ep17_idx]) if ep17_idx >= 0 else 0.0
                    ewma_val = float(X_raw[j, ewma_idx]) if ewma_idx >= 0 else 0.0
                    ep17_eff = ep17 if ep17 > 0 else ewma_val  # prefer ep17; fall back to ewma

                    if rush_score >= 150:
                        anchor = 0.7 * lag2 + 0.3 * ep17_eff
                    elif games_played < 10:
                        # Severe injury: blend lag2 (true talent) with ewma (injury-adjusted recent form)
                        anchor = 0.40 * lag2 + 0.60 * ep17_eff
                    else:
                        # Moderate injury: weight ewma more than lag2
                        anchor = 0.30 * lag2 + 0.70 * ep17_eff
                    if anchor > 200:
                        model_out = float(samples[:, j].mean())
                        if rush_score >= 150:
                            w_model = 0.10 if games_played < 8 else 0.25
                            target  = w_model * model_out + (1.0 - w_model) * anchor
                        elif games_played < 10:
                            target  = min(0.10 * model_out + 0.90 * anchor, anchor * 1.05)
                        else:
                            target  = 0.25 * model_out + 0.75 * anchor
                        factor = min(target / max(model_out, 20.0), 2.5)
                        samples[:, j] *= factor

                # 4. Elite veteran underestimation: established dual-threat QBs (6+ years,
                #    strong rushing) whose output falls well below their long-run EWMA.
                #    The model over-discounts age for QBs who maintain elite rushing ability.
                #    Only apply when the rush bonus (step 3) didn't already boost this player,
                #    to prevent the two multipliers from stacking into top-10 QB territory.
                if (exp >= 6 and games_played >= 15 and ep17_idx >= 0 and rush_score >= 400
                        and rush_score < 600):
                    ep17 = float(X_raw[j, ep17_idx])
                    if ep17 >= 380:
                        model_out = float(samples[:, j].mean())
                        if model_out < ep17 * 0.97:
                            target = 0.30 * model_out + 0.70 * ep17
                            factor = min(target / max(model_out, 20.0), 1.2)
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

                # Injury correction: missed games → raw volume stats under-represent talent.
                # Skip for veterans (exp >= 8): missed games may reflect real decline,
                # not injury — blending toward historical highs would over-project aging backs.
                if games < 14 and ewma > 150 and exp < 8:
                    model_out = float(samples[:, j].mean())
                    anchor = 0.55 * lag2 + 0.45 * ewma if lag2 > 100 else ewma
                    if anchor > model_out:
                        w_model = 0.25 if games < 10 else 0.35
                        target  = w_model * model_out + (1.0 - w_model) * anchor
                        samples[:, j] *= min(target / max(model_out, 20.0), 1.8)

                # Bounce-back correction: large single-year drop due to injury (missed games)
                # for an established back — blend toward prior level.
                # Guard: games < 14 ensures this only fires for injury seasons, not
                # full-season underperformance that may reflect real decline or role change.
                elif games < 14 and ewma > 200 and exp < 9:
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

        adp_implied = _build_adp_implied(conn, pos, projection_season)
        _apply_rookie_anchor(samples, X_raw, feature_names, pos,
                             gsis_ids=gsis_ids, adp_implied=adp_implied)

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


def run_two_stage_pipeline(
    conn=None,
    train_end: int = 2023,
    val_start: int = 2024,
    projection_season: int = 2026,
    models_dir_s1: str | Path = 'models_stage1',
    models_dir_s2: str | Path = 'models_stage2',
    db_path=None,
) -> dict:
    """Train Stage 1 + Stage 2, compose, write projections. Returns summary dict."""
    from tay.models.stage1_pipeline import train_stage1_models, run_stage1_inference, normalize_team_shares
    from tay.models.stage2_pipeline import train_stage2_models, run_stage2_inference
    from tay.models.composition import compose_projections, MODEL_VERSION_DEFAULT

    _own_conn = conn is None
    if _own_conn:
        conn = get_conn(db_path) if db_path else get_conn()
        init_schema(conn)

    print('=== TAY Two-Stage Pipeline ===')

    print('\n--- Stage 1: Training opportunity models ---')
    s1_rmse = train_stage1_models(conn, train_end=train_end, val_start=val_start, models_dir=models_dir_s1)

    print('\n--- Stage 1: Inference ---')
    stage1_df = run_stage1_inference(conn, projection_season, models_dir=models_dir_s1)
    stage1_df = normalize_team_shares(stage1_df)
    print(f'  Stage 1: {len(stage1_df)} player-projections, shares normalized.')

    print('\n--- Stage 2: Training efficiency models ---')
    s2_rmse = train_stage2_models(conn, train_end=train_end, val_start=val_start, models_dir=models_dir_s2)

    print('\n--- Stage 2: Inference ---')
    stage2_dict = run_stage2_inference(conn, projection_season, models_dir=models_dir_s2)
    print(f'  Stage 2: {len(stage2_dict)} players with efficiency estimates.')

    print('\n--- Composition ---')
    rows_written = compose_projections(
        conn, stage1_df, stage2_dict, season=projection_season,
        model_version=MODEL_VERSION_DEFAULT,
    )
    print(f'  Composed {rows_written} PPR projections → projections table.')

    if _own_conn:
        conn.close()

    return {
        'stage1_rmse': s1_rmse,
        'stage2_rmse': s2_rmse,
        'rows_written': rows_written,
    }
