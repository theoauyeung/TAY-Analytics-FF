"""Orchestrate the full valuation pipeline."""
from __future__ import annotations
import duckdb

from tay.db import get_conn, init_schema
from tay.valuation.replacement import ReplacementConfig, compute_replacement_levels
from tay.valuation.vor import compute_vor
from tay.valuation.tiers import assign_tiers


def compute_adp_delta(
    conn: duckdb.DuckDBPyConnection,
    season: int,
    model_version: str,
) -> int:
    rows = conn.execute("""
        SELECT pr.gsis_id, pr.vor_rank, a.adp
        FROM projections pr
        JOIN adp a ON a.gsis_id = pr.gsis_id
                   AND a.season = pr.season
                   AND a.format = 'ppr'
        WHERE pr.season = ? AND pr.model_version = ?
          AND pr.vor_rank IS NOT NULL AND a.adp IS NOT NULL
    """, [season, model_version]).fetchall()

    updated = 0
    for gsis_id, vor_rank, adp in rows:
        conn.execute("""
            UPDATE projections SET adp_delta = ?
            WHERE gsis_id = ? AND season = ? AND model_version = ?
        """, [vor_rank - adp, gsis_id, season, model_version])
        updated += 1

    conn.commit()
    return updated


def run_valuation(
    season: int = 2026,
    model_version: str = 'neural-v1',
    gap_threshold: float = 15.0,
    config: ReplacementConfig | None = None,
    db_path=None,
) -> None:
    conn = get_conn(db_path) if db_path else get_conn()
    init_schema(conn)
    if config is None:
        config = ReplacementConfig()

    print(f'=== TAY Analytics FF — Valuation Engine (season {season}) ===')

    print('Step 1/4: Computing replacement levels...')
    levels = compute_replacement_levels(conn, season, model_version, config)
    for pos, lvl in levels.items():
        print(f'  {pos} replacement: {lvl:.1f} PPR pts')

    print('Step 2/4: Computing VOR...')
    n = compute_vor(conn, season, model_version, levels)
    print(f'  {n} players updated with VOR')

    print('Step 3/4: Assigning tiers...')
    n = assign_tiers(conn, season, model_version, gap_threshold=gap_threshold)
    print(f'  {n} players assigned tiers')

    print('Step 4/4: Computing ADP delta...')
    n = compute_adp_delta(conn, season, model_version)
    print(f'  {n} players updated with ADP delta')

    # Summary
    summary = conn.execute("""
        SELECT pl.position,
               COUNT(*) AS n,
               ROUND(MAX(pr.vor), 1) AS max_vor,
               COUNT(pr.tier) AS tiered,
               COUNT(pr.adp_delta) AS with_adp
        FROM projections pr
        JOIN players pl ON pl.gsis_id = pr.gsis_id
        WHERE pr.season = ? AND pr.model_version = ?
        GROUP BY pl.position ORDER BY max_vor DESC
    """, [season, model_version]).fetchall()

    print('\n=== Valuation Summary ===')
    for row in summary:
        print(f'  {row[0]}: n={row[1]}, max_vor={row[2]}, tiered={row[3]}, adp_delta={row[4]}')

    conn.close()
