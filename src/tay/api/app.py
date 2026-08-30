"""FastAPI application factory."""
from __future__ import annotations
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from tay.db import get_conn, init_schema
from tay.api.routers import health, players, rankings, draft, league

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
    app.state.conn = conn
    yield
    conn.close()


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
