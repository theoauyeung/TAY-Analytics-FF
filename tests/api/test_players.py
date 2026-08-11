"""Tests for player endpoints."""
from __future__ import annotations
from tests.api.conftest import client


def test_get_players_returns_list():
    r = client.get('/players')
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) == 4


def test_get_players_filter_by_position():
    r = client.get('/players?position=RB')
    assert r.status_code == 200
    data = r.json()
    assert all(p['position'] == 'RB' for p in data)
    assert len(data) == 1


def test_get_players_fields():
    r = client.get('/players')
    p = r.json()[0]
    assert 'gsis_id' in p
    assert 'name' in p
    assert 'vor' in p
    assert 'sim_mean' in p
    assert 'adp' in p


def test_get_player_by_id():
    r = client.get('/players/P1')
    assert r.status_code == 200
    data = r.json()
    assert data['gsis_id'] == 'P1'
    assert data['name'] == 'Bijan Robinson'


def test_get_player_by_id_not_found():
    r = client.get('/players/NOTEXIST')
    assert r.status_code == 404
