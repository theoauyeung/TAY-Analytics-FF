"""Orchestrate the full valuation pipeline."""
from __future__ import annotations
import duckdb

from tay.valuation.replacement import ReplacementConfig, compute_replacement_levels
from tay.valuation.vor import compute_vor
from tay.valuation.tiers import assign_tiers


def compute_adp_delta(
    conn: duckdb.DuckDBPyConnection,
    season: int,
    model_version: str,
) -> int:
    # Two sentinel values appear in the adp table for effectively-undrafted players:
    #   9999999 — generic "not drafted" sentinel
    #   999     — Sleeper's search_rank placeholder for unranked players (483 rows)
    # Exclude both so adp_delta reflects only real consensus draft-position data.
    rows = conn.execute("""
        SELECT pr.gsis_id, CAST(pr.vor_rank AS DOUBLE) - a.adp AS adp_delta_val
        FROM projections pr
        JOIN adp a ON a.gsis_id = pr.gsis_id
                   AND a.season = pr.season
                   AND a.format = 'ppr'
        WHERE pr.season = ? AND pr.model_version = ?
          AND pr.vor_rank IS NOT NULL
          AND a.adp IS NOT NULL
          AND a.adp NOT IN (999, 9999999)
    """, [season, model_version]).fetchall()

    updated = 0
    for gsis_id, adp_delta_val in rows:
        conn.execute("""
            UPDATE projections SET adp_delta = ?
            WHERE gsis_id = ? AND season = ? AND model_version = ?
        """, [adp_delta_val, gsis_id, season, model_version])
        updated += 1

    conn.commit()
    return updated


def run_valuation(
    conn: duckdb.DuckDBPyConnection,
    season: int = 2026,
    model_version: str = 'neural-v1',
    config: ReplacementConfig | None = None,
) -> dict:
    if config is None:
        config = ReplacementConfig()

    print(f'=== TAY Analytics FF — Valuation Engine (season {season}) ===')

    print('Step 1/4: Computing replacement levels...')
    levels = compute_replacement_levels(conn, season, model_version, config)
    for pos, lvl in levels.items():
        print(f'  {pos} replacement: {lvl:.1f} PPR pts')

    print('Step 2/4: Computing VOR...')
    vor_rows = compute_vor(conn, season, model_version, levels)
    print(f'  {vor_rows} players updated with VOR')

    print('Step 3/4: Assigning tiers...')
    tier_rows = assign_tiers(conn, season, model_version, gap_threshold=15.0)
    print(f'  {tier_rows} players assigned tiers')

    print('Step 4/4: Computing ADP delta...')
    adp_delta_rows = compute_adp_delta(conn, season, model_version)
    print(f'  {adp_delta_rows} players updated with ADP delta')

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

    return {
        'season': season,
        'model_version': model_version,
        'replacement_levels': levels,
        'vor_rows': vor_rows,
        'tier_rows': tier_rows,
        'adp_delta_rows': adp_delta_rows,
    }
