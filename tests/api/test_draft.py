"""Tests for draft endpoints: recommend, simulate, session save/load."""
from __future__ import annotations
import json
from tests.api.conftest import client


_STATE = {
    'season': 2026,
    'model_version': 'neural-v1',
    'league_settings': {
        'teams': 12,
        'scoring': 'ppr',
        'roster_config': {'QB': 1, 'RB': 2, 'WR': 2, 'TE': 1, 'FLEX': 1},
    },
    'current_pick': 1,
    'total_picks': 180,
    'user_pick_position': 1,
    'pick_log': [],
    'user_roster': {'QB': [], 'RB': [], 'WR': [], 'TE': [], 'FLEX': []},
}


def test_draft_recommend_returns_200():
    r = client.post('/draft/recommend', json=_STATE)
    assert r.status_code == 200


def test_draft_recommend_has_top_pick():
    r = client.post('/draft/recommend', json=_STATE)
    data = r.json()
    assert 'top_pick' in data
    assert 'player' in data['top_pick']
    assert 'draft_score' in data['top_pick']


def test_draft_recommend_has_alternatives():
    r = client.post('/draft/recommend', json=_STATE)
    data = r.json()
    assert 'alternatives' in data
    assert isinstance(data['alternatives'], list)


def test_draft_recommend_has_board_state():
    r = client.post('/draft/recommend', json=_STATE)
    data = r.json()
    assert 'board_state' in data
    bs = data['board_state']
    assert bs['current_pick'] == 1
    assert bs['round'] == 1


def test_draft_recommend_has_wait_analysis():
    r = client.post('/draft/recommend', json=_STATE)
    data = r.json()
    assert 'wait_analysis' in data
    assert isinstance(data['wait_analysis'], list)


def test_draft_recommend_has_next_round_board():
    r = client.post('/draft/recommend', json=_STATE)
    data = r.json()
    assert 'next_round_board' in data
    assert isinstance(data['next_round_board'], dict)


def test_draft_recommend_explanation_is_structured():
    r = client.post('/draft/recommend', json=_STATE)
    data = r.json()
    explanation = data['top_pick']['explanation']
    assert isinstance(explanation, list)
    if explanation:
        ex = explanation[0]
        assert 'factor' in ex
        assert 'detail' in ex
        assert 'weight' in ex


def test_draft_recommend_pick_log_accepted():
    state = {
        **_STATE,
        'pick_log': [
            {'gsis_id': 'nonexistent-1', 'team_number': 2, 'position': 'RB'},
        ],
    }
    r = client.post('/draft/recommend', json=state)
    assert r.status_code == 200


def test_draft_simulate_returns_501():
    r = client.post('/draft/simulate', json={})
    assert r.status_code == 501


def test_draft_session_save_and_retrieve():
    payload = {'session_id': 'test-sess-1', 'state': _STATE}
    r = client.post('/draft/session', json=payload)
    assert r.status_code == 200
    assert r.json()['ok'] is True

    r2 = client.get('/draft/session/test-sess-1')
    assert r2.status_code == 200
    data = r2.json()
    assert data['session_id'] == 'test-sess-1'


def test_draft_session_not_found():
    r = client.get('/draft/session/nonexistent')
    assert r.status_code == 404


def test_draft_recommend_empty_pool_returns_422():
    all_ids = [{'gsis_id': f'P{i}', 'team_number': 1, 'position': 'RB'} for i in range(1, 5)]
    state = {**_STATE, 'pick_log': all_ids}
    r = client.post('/draft/recommend', json=state)
    assert r.status_code == 422
