"""GET /rankings, GET /tiers/{position}, GET /scarcity"""
from __future__ import annotations
from collections import defaultdict
from typing import Literal
import duckdb
from fastapi import APIRouter, Depends, Query

from tay.api.deps import get_db
from tay.api.schemas import RankingOut, TierOut, TierPlayerOut, ScarcityPositionOut

router = APIRouter(tags=['rankings'])

_REPLACEMENT_SPOTS = {'QB': 12, 'RB': 30, 'WR': 30, 'TE': 12}

_RANKING_BASE = """
    SELECT pr.gsis_id, p.espn_id, p.name, p.position, p.team,
           pr.vor, pr.vor_rank, COALESCE(a.adp, 999.0) AS adp,
           pr.adp_delta, pr.tier, pr.mean_projection,
           pr.sim_mean, pr.sim_p10, pr.sim_p90,
           pr.sim_boom_prob, pr.sim_bust_prob, pr.avail_mean
    FROM projections pr
    JOIN players p ON p.gsis_id = pr.gsis_id
    LEFT JOIN adp a ON a.gsis_id = pr.gsis_id
                   AND a.season = pr.season
                   AND a.format = 'ppr'
                   AND a.platform = 'fantasycalc'
                   AND a.adp NOT IN (999, 9999999)
    WHERE pr.season = ? AND pr.model_version = ?
      AND p.position IN ('QB', 'RB', 'WR', 'TE')
"""

_RANKING_KEYS = [
    'gsis_id', 'espn_id', 'name', 'position', 'team', 'vor', 'vor_rank', 'adp',
    'adp_delta', 'tier', 'mean_projection', 'sim_mean', 'sim_p10', 'sim_p90',
    'sim_boom_prob', 'sim_bust_prob', 'avail_mean',
]

_SORT_COLS = {
    'vor_rank': 'pr.vor_rank ASC NULLS LAST',
    'adp': 'COALESCE(a.adp, 999.0) ASC NULLS LAST',
    'projection': 'pr.mean_projection DESC NULLS LAST',
}


_ADP_BLEND_WEIGHT = 0.3  # 70% VOR, 30% ADP consensus


def _blended_score(vor_rank: int | None, adp: float | None) -> float:
    """Combined score for default ranking: blends VOR with market ADP."""
    vr = vor_rank if vor_rank is not None else 9999
    if adp and adp < 900:
        return (1 - _ADP_BLEND_WEIGHT) * vr + _ADP_BLEND_WEIGHT * adp
    return float(vr)


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
    for row in rows:
        d = dict(zip(_RANKING_KEYS, row))
        result.append(d)

    # Default sort: blend VOR rank with ADP consensus so QBs aren't overvalued
    # relative to market. Pure VOR inflates QBs because scarcity weight is tuned
    # for ranking quality, not absolute draft position.
    if sort == 'vor_rank':
        result.sort(key=lambda d: _blended_score(d.get('vor_rank'), d.get('adp')))

    for i, d in enumerate(result, 1):
        d['rank'] = i
        result[i - 1] = RankingOut(**d)
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
                       AND a.platform = 'fantasycalc'
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
    # Fetch all players with their VOR and tier, sorted by vor_rank
    rows = conn.execute("""
        SELECT p.position, pr.vor, pr.tier
        FROM projections pr
        JOIN players p ON p.gsis_id = pr.gsis_id
        WHERE pr.season = ? AND pr.model_version = ?
          AND p.position IN ('QB', 'RB', 'WR', 'TE')
          AND pr.vor IS NOT NULL
        ORDER BY p.position, pr.vor_rank ASC NULLS LAST
    """, [season, model_version]).fetchall()

    # Group by position
    by_position: dict[str, list[tuple]] = defaultdict(list)
    for pos, vor, tier in rows:
        by_position[pos].append((vor, tier))

    result = []
    for pos in sorted(by_position.keys()):
        players = by_position[pos]
        total = len(players)
        top_tier_count = sum(1 for _, tier in players if tier == 1)
        max_vor = players[0][0] if players else None

        # VOR at replacement-level rank (0-indexed: rank N = index N-1)
        repl_idx = _REPLACEMENT_SPOTS.get(pos, 30) - 1
        repl_idx = min(repl_idx, total - 1)  # cap at available players
        repl_vor = players[repl_idx][0] if players else None

        vor_dropoff = (max_vor - repl_vor) if max_vor is not None and repl_vor is not None else None

        result.append(ScarcityPositionOut(
            position=pos,
            total_players=total,
            top_tier_count=top_tier_count,
            vor_dropoff=vor_dropoff,
        ))
    return result
