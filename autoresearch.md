# Autoresearch: QB Rankings (qb-rankings)

> The metric is the sole arbiter. "This looks better" never drives a keep/discard —
> only a measured improvement that clears the noise floor does.

## Objective

Improve the fantasy football QB neural network so that:
1. **Accuracy**: Lower val MAE without overfitting to training data
2. **Ranking quality**: Rushing QBs (Daniels, Dart) rank appropriately high; pocket-only QBs (Goff, Darnold) rank appropriately lower

**Workload profile from data analysis:**
- QB training data: 2006-2023, ~50-65 QBs per season
- Val set: 2024-2025 QB seasons
- QB target distribution: min=-7, mean=159, median=119, max=546, std=144 (very right-skewed — elite QBs pull mean up)
- Key issues found in baseline:
  - Jayden Daniels (2025 injury, 7 games after monster 2024): ranked QB12 overall when should be QB2-4
  - Jaxson Dart (rookie 2025, 14 games, huge rush stats): ranked QB17 when should be QB4-8  
  - Jared Goff (pocket passer): ranked QB6 when should be QB8-12
  - Drake Maye: ranked QB4 — may be slightly high
  - Experience penalty (0.75x for year-1 QBs) stacks multiplicatively with rush bonus (1.18x for elite rushers), netting only 0.885x — neutralizing the rush signal
  - Injury correction (blend toward anchor) not boosting Daniels enough

**Architecture**: 4-position MLPs (QB/RB/WR/TE), 100 epochs for experiments.
Post-hoc QB adjustments applied after inference in `pipeline.py:write_projections()`.

## Metrics
- **Primary**: `primary = qb_val_mae + rank_penalty / 20` (lower is better)
- **Secondary**: qb_mae, qb_rmse, rank_penalty, daniels_rank, dart_rank, goff_rank
- **Noise floor**: 1.0 (baseline stddev across 4 seeds: ~1.0-1.5)

## Budget
- maxRuns: 40 | maxSeconds: none | targetMetric: none
- Per-experiment cap: ~5-8 min (100 epoch training)

## How to Run
`./autoresearch.sh [SEED]` — outputs `METRIC name=value` lines. Default seed=42.

## Files in Scope
- `src/tay/models/pipeline.py` — QB post-hoc adjustments in `write_projections()` ← most impactful
- `src/tay/models/network.py` — MLP architecture (layers, dropout)
- `src/tay/models/trainer.py` — training loop (lr, weight_decay, batch_size)
- `src/tay/models/features.py` — QB feature column selection
- `src/tay/valuation/vor.py` — VOR scarcity weights per position

## Off Limits
- `experiments/eval_model.py` — locked eval harness
- `autoresearch.sh` — locked benchmark runner
- `src/tay/features/player_features.py` — feature computation (DB rebuild required)

## Constraints
- Do NOT retrain on val data or look at test labels when choosing experiments
- Do NOT increase epochs beyond 200 (overfitting risk)
- Changes should be motivated by understanding the problem, not random variation
- Never edit `autoresearch.sh` or `experiments/eval_model.py` to change metric computation

## What's Been Tried

### Baseline (Run 1)
- primary=80.44, qb_mae=75.3, rank_penalty=102.1
- Daniels rank=83, Dart rank=115, Goff rank=63
- Status: keep (baseline)

### Experiment ideas (in priority order)
1. **Stronger injury correction** — lower w_model for <8 games (0.20→0.10, 0.40→0.25): most direct Daniels fix
2. **Decouple exp penalty from rush bonus** — skip exp discount for QBs with rush_score>300: fixes Dart
3. **Stronger pocket-QB penalty** — rush_score<100: 0.93→0.88: fixes Goff
4. **Higher dropout** — 0.3→0.4, 0.2→0.3: might reduce val MAE
5. **Add ewma_rush_score QB feature** — multi-year rushing signal
6. **Modify EWMA weights** — try 0.6/0.3/0.1 in player_features.py
7. **QB scarcity weight** — try 0.45 from 0.35 to boost all QB overall ranks

### Meta-reviews
*(add after every ~10 runs)*
