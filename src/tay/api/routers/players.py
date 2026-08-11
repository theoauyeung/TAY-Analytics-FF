"""GET /players, GET /players/{id}"""
from __future__ import annotations
import duckdb
from fastapi import APIRouter, Depends, HTTPException, Query

from tay.api.deps import get_db
from tay.api.schemas import PlayerOut

router = APIRouter(prefix='/players', tags=['players'])

_SELECT = """
    SELECT pr.gsis_id, p.name, p.position, p.team,
           pr.season, pr.model_version,
           pr.mean_projection, pr.vor, pr.vor_rank, pr.tier, pr.adp_delta,
           COALESCE(a.adp, 999.0) AS adp,
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

_KEYS = [
    'gsis_id', 'name', 'position', 'team', 'season', 'model_version',
    'mean_projection', 'vor', 'vor_rank', 'tier', 'adp_delta', 'adp',
    'sim_mean', 'sim_p10', 'sim_p90', 'sim_boom_prob', 'sim_bust_prob', 'avail_mean',
]


def _row_to_player(row: tuple) -> PlayerOut:
    return PlayerOut(**dict(zip(_KEYS, row)))


@router.get('', response_model=list[PlayerOut])
def list_players(
    season: int = Query(2026),
    model_version: str = Query('neural-v1'),
    position: str | None = Query(None),
    conn: duckdb.DuckDBPyConnection = Depends(get_db),
) -> list[PlayerOut]:
    sql = _SELECT
    params: list = [season, model_version]
    if position:
        sql += ' AND p.position = ?'
        params.append(position.upper())
    sql += ' ORDER BY pr.vor_rank ASC NULLS LAST'
    rows = conn.execute(sql, params).fetchall()
    return [_row_to_player(r) for r in rows]


@router.get('/{gsis_id}', response_model=PlayerOut)
def get_player(
    gsis_id: str,
    season: int = Query(2026),
    model_version: str = Query('neural-v1'),
    conn: duckdb.DuckDBPyConnection = Depends(get_db),
) -> PlayerOut:
    sql = _SELECT + ' AND pr.gsis_id = ?'
    params = [season, model_version, gsis_id]
    row = conn.execute(sql, params).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f'Player {gsis_id!r} not found')
    return _row_to_player(row)
