#!/usr/bin/env python3
"""Train position-specific neural network projection models.

Usage:
    python scripts/models/train_models.py [--epochs 200] [--train-end 2023]
                                   [--val-start 2024] [--val-end 2025]
                                   [--projection-season 2026]
                                   [--models-dir models]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from tay.models.pipeline import run_training_pipeline


def main():
    p = argparse.ArgumentParser(description='TAY Analytics FF — train projection models')
    p.add_argument('--epochs',             type=int, default=200)
    p.add_argument('--train-end',          type=int, default=2023)
    p.add_argument('--val-start',          type=int, default=2024)
    p.add_argument('--val-end',            type=int, default=2025)
    p.add_argument('--projection-season',  type=int, default=2026)
    p.add_argument('--models-dir',         default='models')
    args = p.parse_args()

    run_training_pipeline(
        epochs=args.epochs,
        train_end=args.train_end,
        val_start=args.val_start,
        val_end=args.val_end,
        projection_season=args.projection_season,
        models_dir=args.models_dir,
    )


if __name__ == '__main__':
    main()
