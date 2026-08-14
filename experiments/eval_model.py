"""Eval harness for autoresearch. DO NOT EDIT during loop — this is the locked benchmark.

Trains all position models with fixed seed, writes projections via the real pipeline
(so experiments can modify pipeline.py / network.py / trainer.py / features.py),
then reports MAE/RMSE on val set + key QB ranking positions.

FILES UNDER TEST (may be modified by experiments):
  src/tay/models/features.py   - feature column lists
  src/tay/models/network.py    - MLP architecture
  src/tay/models/trainer.py    - training loop
  src/tay/models/pipeline.py   - QB post-hoc adjustments in write_projections()
  src/tay/valuation/vor.py     - VOR scarcity weights

OFF LIMITS (locked — do not edit):
  experiments/eval_model.py    - this file
  autoresearch.sh              - benchmark runner
"""
from __future__ import annotations
import argparse
import random
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np
import torch

# ── reproducibility ──────────────────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument('--seed', type=int, default=42)
parser.add_argument('--models-dir', type=str, default='models_ar')
parser.add_argument('--epochs', type=int, default=100)
args = parser.parse_args()

SEED = args.seed
torch.manual_seed(SEED)
np.random.seed(SEED)
random.seed(SEED)

# ── project root ─────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'src'))

from tay.db import get_conn
from tay.models.dataset import load_position_data
from tay.models.network import PositionMLP, save_checkpoint
from tay.models.trainer import train_model
from tay.models.pipeline import write_projections
from tay.valuation.replacement import compute_replacement_levels, ReplacementConfig
from tay.valuation.vor import compute_vor

POSITIONS    = ['QB', 'RB', 'WR', 'TE']
TRAIN_END    = 2023
VAL_START    = 2024
VAL_END      = 2025
PROJ_SEASON  = 2026
MODEL_VER    = 'ar-eval'

MODELS_DIR = Path(args.models_dir)
MODELS_DIR.mkdir(parents=True, exist_ok=True)

# ── copy DB to temp so we don't corrupt production data ──────────────────────
PROD_DB = ROOT / 'data' / 'ff.duckdb'
tmp_db  = tempfile.NamedTemporaryFile(suffix='.duckdb', delete=False)
tmp_db.close()
shutil.copy2(PROD_DB, tmp_db.name)
import duckdb as _duckdb
conn = _duckdb.connect(tmp_db.name)
# NOTE: do NOT call init_schema on the temp copy — DuckDB 1.5.5 conflicts with
# ALTER TABLE-added columns when the base CREATE TABLE DDL doesn't include them.

# ── train all positions (locked harness) ─────────────────────────────────────
val_maes  = {}
val_rmses = {}

for pos in POSITIONS:
    ds = load_position_data(conn, pos, train_end=TRAIN_END,
                            val_start=VAL_START, val_end=VAL_END)
    model, _, val_rmse = train_model(
        ds.X_train, ds.y_train, ds.X_val, ds.y_val, epochs=args.epochs
    )

    # Compute MAE on val set
    model.eval()
    with torch.no_grad():
        preds = model(ds.X_val).numpy()
    val_mae = float(np.abs(preds - ds.y_val.numpy()).mean())
    val_maes[pos]  = val_mae
    val_rmses[pos] = val_rmse

    ckpt = MODELS_DIR / f'{pos.lower()}_model.pt'
    save_checkpoint(ckpt, model, pos, ds.feature_names, ds.means, ds.stds, val_rmse)

# ── write projections via pipeline (experiments modify this) ──────────────────
# Patch model version so we don't overwrite production projections
import tay.models.pipeline as _pipe
_orig_ver = _pipe.MODEL_VERSION
_pipe.MODEL_VERSION = MODEL_VER
write_projections(conn, models_dir=MODELS_DIR, projection_season=PROJ_SEASON)
_pipe.MODEL_VERSION = _orig_ver

# ── compute VOR + rankings (locked) ──────────────────────────────────────────
repl = compute_replacement_levels(conn, PROJ_SEASON, MODEL_VER, ReplacementConfig())
compute_vor(conn, PROJ_SEASON, MODEL_VER, repl)

# ── overall val metrics ───────────────────────────────────────────────────────
overall_mae  = np.mean(list(val_maes.values()))
overall_rmse = np.mean(list(val_rmses.values()))

# ── QB ranking quality (locked) ───────────────────────────────────────────────
# Full QB ranking for inspection
qb_ranking = conn.execute("""
    SELECT p.name, ROUND(pr.mean_projection,1), pr.vor_rank
    FROM projections pr
    JOIN players p ON pr.gsis_id = p.gsis_id
    WHERE pr.season = ? AND pr.model_version = ?
      AND p.position = 'QB'
    ORDER BY pr.vor_rank
    LIMIT 20
""", [PROJ_SEASON, MODEL_VER]).fetchall()

print('\n=== QB Rankings ===')
for i, (name, proj, overall_rank) in enumerate(qb_ranking, 1):
    print(f'  QB{i:2d} (overall #{overall_rank:3d}): {name} — {proj:.1f} pts')

# Lookup specific QBs by full-name match
key_qbs = {
    'daniels_rank': ('Jayden', 'Daniels'),
    'dart_rank':    ('Jaxson', 'Dart'),
    'allen_rank':   ('Josh',   'Allen'),
    'lamar_rank':   ('Lamar',  'Jackson'),
    'mahomes_rank': ('Patrick','Mahomes'),
    'hurts_rank':   ('Jalen',  'Hurts'),
    'goff_rank':    ('Jared',  'Goff'),
    'darnold_rank': ('Sam',    'Darnold'),
    'maye_rank':    ('Drake',  'Maye'),
    'burrow_rank':  ('Joe',    'Burrow'),
}
qb_ranks = {}
for key, (first, last) in key_qbs.items():
    row = conn.execute("""
        SELECT pr.vor_rank
        FROM projections pr
        JOIN players p ON pr.gsis_id = p.gsis_id
        WHERE pr.season = ? AND pr.model_version = ?
          AND p.name ILIKE ? AND p.name ILIKE ?
        LIMIT 1
    """, [PROJ_SEASON, MODEL_VER, f'%{first}%', f'%{last}%']).fetchone()
    qb_ranks[key] = row[0] if row else 999

# ── ranking quality score (locked formula) ───────────────────────────────────
# Penalty for key misranks. Lower = better.
# Targets are rough consensus 2026 expert ADP.
expected = {
    'daniels_rank': 50,   # QB2 in most rankings
    'dart_rank':    80,   # QB4-6 — rushing upside, limited data
    'allen_rank':   10,   # QB1 overall top pick
    'lamar_rank':   30,   # QB2 rushing monster
    'mahomes_rank': 60,   # QB4-6 elite veteran
    'hurts_rank':   55,   # QB4-6 dual-threat
    'goff_rank':    110,  # pocket QB, late QB2 territory
    'darnold_rank': 120,  # career journeyman
    'maye_rank':    75,   # young rushing QB year 2
    'burrow_rank':  65,   # elite passer, injury history
}
rank_penalty = 0.0
rank_penalty += max(0, qb_ranks['daniels_rank'] - expected['daniels_rank'])
rank_penalty += max(0, qb_ranks['dart_rank']    - expected['dart_rank'])    * 0.7
rank_penalty += max(0, qb_ranks['allen_rank']   - expected['allen_rank'])   * 0.5
rank_penalty += max(0, qb_ranks['mahomes_rank'] - expected['mahomes_rank']) * 0.3
rank_penalty += max(0, expected['goff_rank']    - qb_ranks['goff_rank'])    * 0.5
rank_penalty += max(0, expected['darnold_rank'] - qb_ranks['darnold_rank']) * 0.3

print(f'\n=== Key QB Ranks ===')
for key, rank in qb_ranks.items():
    exp = expected[key]
    delta = rank - exp
    flag = '✓' if abs(delta) < 20 else ('↓ TOO LOW' if delta > 0 else '↑ TOO HIGH')
    print(f'  {key:15s}: #{rank:3d} (target ~#{exp}, delta={delta:+d}) {flag}')
print(f'  rank_penalty: {rank_penalty:.1f}')

# ── combined primary metric (lower is better) ─────────────────────────────────
# QB val MAE + rank_penalty scaled so both terms are comparable
primary_metric = val_maes['QB'] + rank_penalty / 20.0

print(f'\n=== Validation Metrics ===')
for pos in POSITIONS:
    print(f'  {pos} MAE={val_maes[pos]:.1f}  RMSE={val_rmses[pos]:.1f}')
print(f'  Overall MAE={overall_mae:.1f}')
print(f'  Rank penalty={rank_penalty:.1f}')
print(f'  Primary metric={primary_metric:.2f}')

# ── METRIC output lines ───────────────────────────────────────────────────────
print(f'METRIC primary={primary_metric:.4f}')
print(f'METRIC qb_mae={val_maes["QB"]:.4f}')
print(f'METRIC qb_rmse={val_rmses["QB"]:.4f}')
print(f'METRIC rank_penalty={rank_penalty:.1f}')
print(f'METRIC overall_mae={overall_mae:.4f}')
print(f'METRIC daniels_rank={qb_ranks["daniels_rank"]}')
print(f'METRIC dart_rank={qb_ranks["dart_rank"]}')
print(f'METRIC goff_rank={qb_ranks["goff_rank"]}')
print(f'METRIC mahomes_rank={qb_ranks["mahomes_rank"]}')

# cleanup
conn.close()
import os; os.unlink(tmp_db.name)
