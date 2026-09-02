"""GET /health"""
from __future__ import annotations
import os
from fastapi import APIRouter

router = APIRouter()

_BUILD_ID = os.environ.get('RENDER_GIT_COMMIT', 'local')[:8]


@router.get('/health')
def health() -> dict:
    return {'status': 'ok', 'build': _BUILD_ID}
