#!/usr/bin/env bash
# Autoresearch benchmark: train QB model, report MAE + ranking metrics.
# Usage: ./autoresearch.sh [SEED]
# Outputs: METRIC name=value lines (lower MAE = better)
set -euo pipefail

SEED=${1:-42}
PROJ_DIR="$(cd "$(dirname "$0")" && pwd)"
export PYTHONPATH="$PROJ_DIR/src"
MODELS_DIR="$PROJ_DIR/models_ar"
EVAL_SCRIPT="$PROJ_DIR/experiments/eval_model.py"
PYTHON=/Users/theoauyeung/miniforge3/bin/python3

# Run evaluation (macOS lacks GNU timeout; rely on Python's own timeout guards)
"$PYTHON" "$EVAL_SCRIPT" --seed "$SEED" --models-dir "$MODELS_DIR" --epochs 100
