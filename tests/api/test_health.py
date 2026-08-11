from __future__ import annotations
from tests.api.conftest import client


def test_health_ok():
    r = client.get('/health')
    assert r.status_code == 200
    assert r.json() == {'status': 'ok'}
