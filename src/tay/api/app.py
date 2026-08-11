"""FastAPI application factory."""
from __future__ import annotations
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from tay.db import get_conn, init_schema
from tay.api.routers import health, players, rankings, draft


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
    app.add_middleware(
        CORSMiddleware,
        allow_origins=['http://localhost:3000'],
        allow_methods=['*'],
        allow_headers=['*'],
    )
    app.include_router(health.router)
    app.include_router(players.router)
    app.include_router(rankings.router)
    app.include_router(draft.router)
    return app


app = create_app()
