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
           pr.sim_boom_prob, pr.sim_bust_prob, pr.avail_mean,
           COALESCE(pa.efficiency_factor, 0.0) AS efficiency_factor
    FROM projections pr
    JOIN players p ON p.gsis_id = pr.gsis_id
    LEFT JOIN adp a ON a.gsis_id = pr.gsis_id
                   AND a.season = pr.season
                   AND a.format = 'ppr'
                   AND a.platform = 'espn'
                   AND a.adp NOT IN (999, 9999999)
    LEFT JOIN player_analytics pa ON pa.gsis_id = pr.gsis_id
                                  AND pa.season = pr.season
    WHERE pr.season = ? AND pr.model_version = ?
      AND p.position IN ('QB', 'RB', 'WR', 'TE')
"""

_RANKING_KEYS = [
    'gsis_id', 'espn_id', 'name', 'position', 'team', 'vor', 'vor_rank', 'adp',
    'adp_delta', 'tier', 'mean_projection', 'sim_mean', 'sim_p10', 'sim_p90',
    'sim_boom_prob', 'sim_bust_prob', 'avail_mean', 'efficiency_factor',
]

_SORT_COLS = {
    'vor_rank': 'pr.vor_rank ASC NULLS LAST',
    'adp': 'COALESCE(a.adp, 999.0) ASC NULLS LAST',
    'projection': 'pr.mean_projection DESC NULLS LAST',
}


_ADP_BLEND_WEIGHT       = 0.35
_ANALYTICS_BLEND_WEIGHT = 0.10


_ANALYTICS_MAX_SHIFT = 15  # analytics_rank can nudge at most this many spots from vor_rank


def _blended_score(
    vor_rank: int | None,
    adp: float | None,
    analytics_rank: int | None = None,
) -> float:
    """Blended ranking score: 65% VOR, 25% ADP, 10% historical draft efficiency.

    analytics_rank is clamped to within _ANALYTICS_MAX_SHIFT of vor_rank so that
    efficiency history nudges but never overrides the model projection.
    """
    vr = vor_rank if vor_rank is not None else 9999
    if analytics_rank is not None:
        ar = max(vr - _ANALYTICS_MAX_SHIFT, min(vr + _ANALYTICS_MAX_SHIFT, analytics_rank))
    else:
        ar = vr
    if adp and adp < 900:
        return (
            (1 - _ADP_BLEND_WEIGHT - _ANALYTICS_BLEND_WEIGHT) * vr
            + _ADP_BLEND_WEIGHT       * adp
            + _ANALYTICS_BLEND_WEIGHT * ar
        )
    return (1 - _ANALYTICS_BLEND_WEIGHT) * vr + _ANALYTICS_BLEND_WEIGHT * ar


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

    # Compute analytics_rank: sort result by efficiency_factor desc, assign 1-based rank
    sorted_by_ef = sorted(
        enumerate(result),
        key=lambda x: x[1].get('efficiency_factor', 0.0),
        reverse=True,
    )
    analytics_rank_map = {
        orig_idx: ar_rank + 1
        for ar_rank, (orig_idx, _) in enumerate(sorted_by_ef)
    }

    result_out = []
    for i, d in enumerate(result, 1):
        d['rank'] = i
        ar = analytics_rank_map.get(i - 1)
        d['blended_score'] = _blended_score(d.get('vor_rank'), d.get('adp'), ar)
        result_out.append(RankingOut(**d))

    if sort == 'vor_rank':
        result_out.sort(key=lambda r: r.blended_score)
        for i, r in enumerate(result_out, 1):
            r.rank = i
    return result_out


@router.get('/analytics/draft-value')
def get_draft_value(
    season: int = Query(2026),
    conn: duckdb.DuckDBPyConnection = Depends(get_db),
) -> dict:
    """Return top undervalued players and bucket efficiency stats."""
    undervalued = conn.execute("""
        SELECT p.name, p.position, p.team,
               pa.efficiency_factor, pa.adp_bucket,
               pa.avg_pts_above_expectation, pa.sample_size,
               COALESCE(a.adp, 999) AS adp
        FROM player_analytics pa
        JOIN players p ON p.gsis_id = pa.gsis_id
        LEFT JOIN adp a ON a.gsis_id = pa.gsis_id
                       AND a.season = ? AND a.format = 'ppr' AND a.platform = 'espn'
        WHERE pa.season = ? AND pa.sample_size >= 3
        ORDER BY pa.efficiency_factor DESC
        LIMIT 20
    """, [season, season]).fetchall()

    bucket_stats = conn.execute("""
        SELECT pa.adp_bucket,
               p.position,
               AVG(pa.efficiency_factor)  AS avg_factor,
               COUNT(*)                   AS sample_size
        FROM player_analytics pa
        JOIN players p ON p.gsis_id = pa.gsis_id
        WHERE pa.season = ?
        GROUP BY pa.adp_bucket, p.position
        ORDER BY pa.adp_bucket, p.position
    """, [season]).fetchall()

    return {
        'undervalued': [
            {'name': r[0], 'position': r[1], 'team': r[2],
             'efficiency_factor': r[3], 'adp_bucket': r[4],
             'avg_pts_above': r[5], 'sample_size': r[6], 'adp': r[7]}
            for r in undervalued
        ],
        'bucket_stats': [
            {'bucket': r[0], 'position': r[1], 'avg_factor': r[2], 'sample_size': r[3]}
            for r in bucket_stats
        ],
    }


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
                       AND a.platform = 'espn'
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
