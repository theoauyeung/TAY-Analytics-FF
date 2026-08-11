"""Tests for GET /rankings, GET /tiers/{position}, GET /scarcity."""
from __future__ import annotations
from tests.api.conftest import client


def test_get_rankings_returns_list():
    r = client.get('/rankings')
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) == 4


def test_get_rankings_sorted_by_vor_rank():
    r = client.get('/rankings?sort=vor_rank')
    data = r.json()
    ranks = [p['vor_rank'] for p in data if p['vor_rank'] is not None]
    assert ranks == sorted(ranks)


def test_get_rankings_filter_position():
    r = client.get('/rankings?position=QB')
    data = r.json()
    assert len(data) == 1
    assert data[0]['position'] == 'QB'


def test_get_rankings_sort_adp():
    r = client.get('/rankings?sort=adp')
    data = r.json()
    adps = [p['adp'] for p in data if p['adp'] is not None]
    assert adps == sorted(adps)


def test_get_rankings_invalid_sort():
    r = client.get('/rankings?sort=invalid')
    assert r.status_code == 422


def test_get_tiers_for_position():
    r = client.get('/tiers/RB')
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]['position'] == 'RB'
    assert 'players' in data[0]


def test_get_tiers_invalid_position():
    r = client.get('/tiers/K')
    assert r.status_code == 422


def test_get_scarcity():
    r = client.get('/scarcity')
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    positions = {item['position'] for item in data}
    assert {'QB', 'RB', 'WR', 'TE'}.issubset(positions)


def test_get_scarcity_fields():
    r = client.get('/scarcity')
    item = r.json()[0]
    assert 'total_players' in item
    assert 'top_tier_count' in item
    assert 'vor_dropoff' in item
