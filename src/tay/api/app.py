"""FastAPI application factory."""
from __future__ import annotations
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from tay.db import get_conn, init_schema
from tay.api.routers import health, players, rankings, draft, league
from tay.valuation.pipeline import run_valuation
from tay.valuation.replacement import ReplacementConfig

_LOCAL_ORIGINS = [
    'http://localhost:3000',
    'http://localhost:5173',
    'http://localhost:5174',
    'http://localhost:5175',
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    conn = get_conn()
    init_schema(conn)
    # On Render, recompute VOR/tiers at startup so the persistent disk DB stays
    # in sync with the latest pipeline (blended projections, replacement levels, etc.)
    if os.environ.get('RENDER'):
        _refresh_on_render(conn)
    app.state.conn = conn
    yield
    conn.close()


def _refresh_on_render(conn) -> None:
    from pathlib import Path
    print('[startup] Render env detected — loading consensus snapshot and recomputing VOR...')
    snapshot = Path(__file__).parent.parent.parent.parent / 'data' / 'consensus_projections_2026.csv'
    if snapshot.exists():
        try:
            conn.execute("DELETE FROM consensus_projections WHERE season = 2026")
            conn.execute(f"""
                INSERT INTO consensus_projections
                    (gsis_id, season, source, pass_yards, pass_tds, interceptions,
                     rush_yards, rush_tds, receptions, rec_yards, rec_tds, points)
                SELECT gsis_id, season, source, pass_yards, pass_tds, interceptions,
                       rush_yards, rush_tds, receptions, rec_yards, rec_tds, points
                FROM read_csv_auto('{snapshot}')
            """)
            count = conn.execute(
                "SELECT COUNT(*) FROM consensus_projections WHERE season = 2026"
            ).fetchone()[0]
            conn.commit()
            print(f'[startup] Loaded {count} consensus rows from snapshot.')
        except Exception as exc:
            print(f'[startup] Snapshot load failed: {exc}')
    run_valuation(conn, season=2026, model_version='neural-v1',
                  config=ReplacementConfig(teams=12))


def create_app() -> FastAPI:
    app = FastAPI(
        title='TAY Analytics FF',
        description='Fantasy football analytics API',
        version='0.1.0',
        lifespan=lifespan,
    )
    extra = [o for o in os.environ.get('ALLOWED_ORIGINS', '').split(',') if o]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_LOCAL_ORIGINS + extra,
        allow_methods=['*'],
        allow_headers=['*'],
    )
    app.include_router(health.router)
    app.include_router(players.router)
    app.include_router(rankings.router)
    app.include_router(draft.router)
    app.include_router(league.router)
    return app


app = create_app()
