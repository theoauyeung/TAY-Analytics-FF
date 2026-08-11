from __future__ import annotations
import pytest
from tay.draft.models import LeagueSettings, DraftState, PlayerProjection
from tay.draft.scoring import future_availability, positional_urgency, roster_fit, score_player

REPLACEMENT_SPOTS = {'QB': 12, 'RB': 30, 'WR': 30, 'TE': 12}


def _player(position='RB', vor=50.0, vor_rank=10, adp=15.0, sim_boom_prob=0.2):
    return PlayerProjection(
        gsis_id='X', name='Test', position=position, team='T',
        vor=vor, vor_rank=vor_rank, sim_mean=200.0,
        sim_p10=140.0, sim_p90=260.0, adp=adp, tier=2,
        sim_boom_prob=sim_boom_prob, sim_bust_prob=0.1,
    )


def _state(picks_until_next=5, current_pick=1, user_roster=None):
    ls = LeagueSettings()
    return DraftState(
        season=2026, model_version='neural-v1', league_settings=ls,
        current_pick=current_pick, total_picks=180, user_pick_position=1,
        drafted_ids=[],
        user_roster=user_roster or {'QB': [], 'RB': [], 'WR': [], 'TE': [], 'FLEX': []},
    )


def test_future_availability_high_adp_relative_to_picks():
    # Player with ADP 100, only 2 picks away → very likely available
    p = _player(adp=100.0)
    fa = future_availability(p, picks_until_next=2)
    assert fa > 0.9


def test_future_availability_low_adp_relative_to_picks():
    # Player with ADP 3, 10 picks away → likely gone
    p = _player(adp=3.0)
    fa = future_availability(p, picks_until_next=10)
    assert fa < 0.5


def test_future_availability_clamped_to_unit_interval():
    p = _player(adp=1.0)
    assert 0.0 <= future_availability(p, picks_until_next=100) <= 1.0
    p2 = _player(adp=999.0)
    assert 0.0 <= future_availability(p2, picks_until_next=0) <= 1.0


def test_positional_urgency_scarce():
    # Only 3 RBs left, replacement = 30 → urgency near 1
    pu = positional_urgency('RB', available_at_position=3, replacement_spots=REPLACEMENT_SPOTS)
    assert pu > 0.85


def test_positional_urgency_plentiful():
    # 29 WRs left → low urgency
    pu = positional_urgency('WR', available_at_position=29, replacement_spots=REPLACEMENT_SPOTS)
    assert pu < 0.1


def test_roster_fit_empty_roster_bonus():
    state = _state(user_roster={'QB': [], 'RB': [], 'WR': [], 'TE': [], 'FLEX': []})
    p = _player(position='RB')
    rf = roster_fit(p, state.user_roster)
    assert rf > 1.0  # bonus for unfilled starter


def test_roster_fit_full_position_penalty():
    # RB slots full (2 RBs, 1 FLEX already filled)
    state = _state(user_roster={
        'QB': [], 'RB': ['a', 'b'], 'WR': [], 'TE': [], 'FLEX': ['c'],
    })
    p = _player(position='RB')
    rf = roster_fit(p, state.user_roster)
    assert rf < 1.0


def test_score_player_returns_recommendation():
    p = _player(vor=80.0, adp=5.0, vor_rank=3)
    state = _state()
    rec = score_player(p, state, available_by_position={'RB': 25}, replacement_spots=REPLACEMENT_SPOTS)
    assert rec.player is p
    assert rec.draft_score > 0
    assert isinstance(rec.explanation, list)
    assert len(rec.explanation) >= 1


def test_score_player_explanation_contains_vor_sentence():
    p = _player(vor=80.0, adp=5.0, vor_rank=3)
    state = _state()
    rec = score_player(p, state, available_by_position={'RB': 25}, replacement_spots=REPLACEMENT_SPOTS)
    assert any('VOR' in s for s in rec.explanation)


def test_score_player_explanation_undervalued():
    # adp - vor_rank = 50 - 5 = 45 > 15 → undervalued explanation
    p = _player(vor=60.0, adp=50.0, vor_rank=5)
    state = _state()
    rec = score_player(p, state, available_by_position={'RB': 25}, replacement_spots=REPLACEMENT_SPOTS)
    assert any('Undervalued' in s for s in rec.explanation)
