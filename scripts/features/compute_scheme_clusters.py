#!/usr/bin/env python3
"""Compute scheme clusters from team_features via KMeans.

Usage:
    uv run python scripts/features/compute_scheme_clusters.py --seasons 2016 2017 ... 2026
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from tay.db import get_conn, init_schema

N_CLUSTERS = 6
CLUSTER_FEATURES = ['pass_rate', 'pass_epa', 'rush_epa']


def compute_and_store_clusters(
    conn,
    seasons: list[int],
    n_clusters: int = N_CLUSTERS,
    random_state: int = 42,
) -> int:
    """Fit KMeans on all available team_features, assign cluster_id, upsert."""
    # Load all historical team features (train on full history for stable clusters)
    rows = conn.execute("""
        SELECT team, season, pass_rate, pass_epa, rush_epa
        FROM team_features
        WHERE pass_rate IS NOT NULL AND pass_epa IS NOT NULL AND rush_epa IS NOT NULL
        ORDER BY season, team
    """).fetchall()

    if len(rows) < n_clusters:
        raise ValueError(f'Need at least {n_clusters} team-seasons to cluster, got {len(rows)}')

    teams = [(r[0], r[1]) for r in rows]
    X = np.array([[r[2], r[3], r[4]] for r in rows], dtype=np.float32)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    km = KMeans(n_clusters=n_clusters, random_state=random_state, n_init=10)
    labels = km.fit_predict(X_scaled)

    # Filter to requested seasons only
    to_upsert = [
        (team, season, int(label))
        for (team, season), label in zip(teams, labels)
        if season in seasons
    ]

    conn.executemany("""
        INSERT INTO scheme_clusters (team, season, cluster_id)
        VALUES (?, ?, ?)
        ON CONFLICT (team, season) DO UPDATE SET cluster_id = excluded.cluster_id
    """, to_upsert)
    conn.commit()
    return len(to_upsert)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument('--seasons', type=int, nargs='+', default=list(range(2016, 2027)))
    p.add_argument('--n-clusters', type=int, default=N_CLUSTERS)
    args = p.parse_args()

    conn = get_conn()
    init_schema(conn)
    n = compute_and_store_clusters(conn, args.seasons, args.n_clusters)
    print(f'Upserted {n} scheme cluster rows.')
    conn.close()


if __name__ == '__main__':
    main()
