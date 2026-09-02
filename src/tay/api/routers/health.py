"""GET /health"""
from __future__ import annotations
import os
from fastapi import APIRouter, Depends
import duckdb
from tay.api.deps import get_db

router = APIRouter()

_BUILD_ID = os.environ.get('RENDER_GIT_COMMIT', 'local')[:8]


@router.get('/health')
def health() -> dict:
    return {'status': 'ok', 'build': _BUILD_ID}


@router.get('/debug/db')
def debug_db(conn: duckdb.DuckDBPyConnection = Depends(get_db)) -> dict:
    """Diagnostic endpoint: DB stats and Tuten's current VOR."""
    proj_count = conn.execute(
        "SELECT COUNT(*) FROM projections WHERE season = 2026 AND model_version = 'neural-v1'"
    ).fetchone()[0]
    consensus_count = conn.execute(
        "SELECT COUNT(*) FROM consensus_projections WHERE season = 2026"
    ).fetchone()[0]
    tuten = conn.execute("""
        SELECT pr.vor, pr.vor_rank, pr.mean_projection, pr.blended_projection
        FROM projections pr
        JOIN players pl ON pl.gsis_id = pr.gsis_id
        WHERE pl.name ILIKE '%tuten%' AND pr.season = 2026
    """).fetchone()
    rb_replacement = conn.execute("""
        SELECT COALESCE(blended_projection, mean_projection)
        FROM projections pr
        JOIN players pl ON pl.gsis_id = pr.gsis_id
        WHERE pl.position = 'RB' AND pr.season = 2026 AND pr.model_version = 'neural-v1'
        ORDER BY COALESCE(blended_projection, mean_projection) DESC
        LIMIT 1 OFFSET 35
    """).fetchone()
    return {
        'build': _BUILD_ID,
        'projections_2026': proj_count,
        'consensus_2026': consensus_count,
        'tuten': {
            'vor': tuten[0] if tuten else None,
            'vor_rank': tuten[1] if tuten else None,
            'mean_projection': tuten[2] if tuten else None,
            'blended_projection': tuten[3] if tuten else None,
        },
        'rb_replacement_approx': rb_replacement[0] if rb_replacement else None,
    }
