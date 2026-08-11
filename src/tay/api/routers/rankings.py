"""GET /rankings, GET /tiers/{position}, GET /scarcity"""
from __future__ import annotations
from typing import Literal
import duckdb
from fastapi import APIRouter, Depends, Query

from tay.api.deps import get_db
from tay.api.schemas import RankingOut, TierOut, TierPlayerOut, ScarcityPositionOut

router = APIRouter(tags=['rankings'])

_RANKING_BASE = """
    SELECT pr.gsis_id, p.name, p.position, p.team,
           pr.vor, pr.vor_rank, COALESCE(a.adp, 999.0) AS adp,
           pr.adp_delta, pr.tier, pr.mean_projection,
           pr.sim_mean, pr.sim_p10, pr.sim_p90,
           pr.sim_boom_prob, pr.sim_bust_prob, pr.avail_mean
    FROM projections pr
    JOIN players p ON p.gsis_id = pr.gsis_id
    LEFT JOIN adp a ON a.gsis_id = pr.gsis_id
                   AND a.season = pr.season
                   AND a.format = 'ppr'
                   AND a.adp NOT IN (999, 9999999)
    WHERE pr.season = ? AND pr.model_version = ?
      AND p.position IN ('QB', 'RB', 'WR', 'TE')
"""

_RANKING_KEYS = [
    'gsis_id', 'name', 'position', 'team', 'vor', 'vor_rank', 'adp',
    'adp_delta', 'tier', 'mean_projection', 'sim_mean', 'sim_p10', 'sim_p90',
    'sim_boom_prob', 'sim_bust_prob', 'avail_mean',
]

_SORT_COLS = {
    'vor_rank': 'pr.vor_rank ASC NULLS LAST',
    'adp': 'COALESCE(a.adp, 999.0) ASC NULLS LAST',
    'projection': 'pr.mean_projection DESC NULLS LAST',
}


@router.get('/rankings', response_model=list[RankingOut])
def get_rankings(
    season: int = Query(2026),
    model_version: str = Query('neural-v1'),
    position: str | None = Query(None),
    sort: Literal['vor_rank', 'adp', 'projection'] = Query('vor_rank'),
    conn: duckdb.DuckDBPyConnection = Depends(get_db),
) -> list[RankingOut]:
    order_col = _SORT_COLS[sort]
    sql = _RANKING_BASE
    params: list = [season, model_version]
    if position:
        sql += ' AND p.position = ?'
        params.append(position.upper())
    sql += f' ORDER BY {order_col}'
    rows = conn.execute(sql, params).fetchall()
    result = []
    for i, row in enumerate(rows, 1):
        d = dict(zip(_RANKING_KEYS, row))
        d['rank'] = i
        result.append(RankingOut(**d))
    return result


@router.get('/tiers/{position}', response_model=list[TierOut])
def get_tiers(
    position: Literal['QB', 'RB', 'WR', 'TE'],
    season: int = Query(2026),
    model_version: str = Query('neural-v1'),
    conn: duckdb.DuckDBPyConnection = Depends(get_db),
) -> list[TierOut]:
    rows = conn.execute("""
        SELECT pr.tier, pr.gsis_id, p.name, p.team,
               pr.vor, pr.vor_rank, COALESCE(a.adp, 999.0),
               pr.sim_mean
        FROM projections pr
        JOIN players p ON p.gsis_id = pr.gsis_id
        LEFT JOIN adp a ON a.gsis_id = pr.gsis_id
                       AND a.season = pr.season
                       AND a.format = 'ppr'
                       AND a.adp NOT IN (999, 9999999)
        WHERE pr.season = ? AND pr.model_version = ?
          AND p.position = ?
          AND pr.tier IS NOT NULL
        ORDER BY pr.tier ASC, pr.vor_rank ASC NULLS LAST
    """, [season, model_version, position]).fetchall()

    tiers: dict[int, list[TierPlayerOut]] = {}
    for row in rows:
        tier_num = row[0]
        player = TierPlayerOut(
            gsis_id=row[1], name=row[2], team=row[3],
            vor=row[4], vor_rank=row[5], adp=row[6], sim_mean=row[7],
        )
        tiers.setdefault(tier_num, []).append(player)

    return [
        TierOut(tier=t, position=position, players=players)
        for t, players in sorted(tiers.items())
    ]


@router.get('/scarcity', response_model=list[ScarcityPositionOut])
def get_scarcity(
    season: int = Query(2026),
    model_version: str = Query('neural-v1'),
    conn: duckdb.DuckDBPyConnection = Depends(get_db),
) -> list[ScarcityPositionOut]:
    rows = conn.execute("""
        SELECT p.position,
               COUNT(*) AS total,
               COUNT(CASE WHEN pr.tier = 1 THEN 1 END) AS tier1_count,
               MAX(pr.vor) AS max_vor,
               MIN(pr.vor) AS min_vor
        FROM projections pr
        JOIN players p ON p.gsis_id = pr.gsis_id
        WHERE pr.season = ? AND pr.model_version = ?
          AND p.position IN ('QB', 'RB', 'WR', 'TE')
        GROUP BY p.position
        ORDER BY p.position
    """, [season, model_version]).fetchall()

    result = []
    for pos, total, tier1, max_vor, min_vor in rows:
        vor_dropoff = (max_vor - min_vor) if max_vor is not None and min_vor is not None else None
        result.append(ScarcityPositionOut(
            position=pos,
            total_players=total,
            top_tier_count=tier1 or 0,
            vor_dropoff=vor_dropoff,
        ))
    return result
