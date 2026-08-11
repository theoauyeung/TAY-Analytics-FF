from __future__ import annotations
import json
import pytest
from pathlib import Path
from tests.api.conftest import client
import tay.api.routers.league as league_module


@pytest.fixture(autouse=True)
def patch_settings_path(tmp_path, monkeypatch):
    """Redirect league settings file to tmp dir so tests don't touch data/."""
    monkeypatch.setattr(league_module, 'SETTINGS_PATH', tmp_path / 'league_settings.json')


def test_get_league_settings_default():
    r = client.get('/league/settings')
    assert r.status_code == 200
    data = r.json()
    assert data['teams'] == 12
    assert data['scoring'] == 'ppr'
    assert 'roster_config' in data


def test_post_league_settings_saves():
    payload = {
        'teams': 10,
        'scoring': 'half',
        'roster_config': {'QB': 1, 'RB': 2, 'WR': 3, 'TE': 1, 'FLEX': 1},
    }
    r = client.post('/league/settings', json=payload)
    assert r.status_code == 200
    assert r.json()['ok'] is True


def test_get_league_settings_after_save():
    payload = {
        'teams': 10,
        'scoring': 'half',
        'roster_config': {'QB': 1, 'RB': 2, 'WR': 3, 'TE': 1, 'FLEX': 1},
    }
    client.post('/league/settings', json=payload)
    r = client.get('/league/settings')
    data = r.json()
    assert data['teams'] == 10
    assert data['scoring'] == 'half'
