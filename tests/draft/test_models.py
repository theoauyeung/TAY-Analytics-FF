from __future__ import annotations
from tay.draft.models import (
    LeagueSettings, DraftState, PlayerProjection,
    Recommendation, RecommendationState,
)


def test_league_settings_defaults():
    ls = LeagueSettings()
    assert ls.teams == 12
    assert ls.scoring == 'ppr'
    assert ls.roster_config == {'QB': 1, 'RB': 2, 'WR': 2, 'TE': 1, 'FLEX': 1}


def test_draft_state_construction():
    ls = LeagueSettings()
    ds = DraftState(
        season=2026,
        model_version='neural-v1',
        league_settings=ls,
        current_pick=1,
        total_picks=180,
        user_pick_position=1,
        drafted_ids=[],
        user_roster={'QB': [], 'RB': [], 'WR': [], 'TE': [], 'FLEX': []},
    )
    assert ds.picks_until_next == 0  # pick 1 is user's turn immediately (position 1)
    assert ds.round == 1


def test_player_projection_construction():
    pp = PlayerProjection(
        gsis_id='00-0000001',
        name='Josh Allen',
        position='QB',
        team='BUF',
        vor=120.0,
        vor_rank=1,
        sim_mean=381.0,
        sim_p10=304.0,
        sim_p90=458.0,
        adp=5.0,
        tier=1,
        sim_boom_prob=0.35,
        sim_bust_prob=0.08,
    )
    assert pp.gsis_id == '00-0000001'


def test_recommendation_state_has_top_pick():
    pp = PlayerProjection(
        gsis_id='X', name='A', position='RB', team='T',
        vor=50.0, vor_rank=5, sim_mean=200.0, sim_p10=140.0, sim_p90=260.0,
        adp=10.0, tier=2, sim_boom_prob=0.2, sim_bust_prob=0.1,
    )
    rec = Recommendation(
        player=pp, draft_score=75.0, roster_fit=1.0,
        positional_urgency=0.5, future_availability_pct=0.9,
        explanation=['High VOR relative to ADP'],
    )
    state = RecommendationState(
        top_pick=rec,
        alternatives=[],
        positional_needs=['RB', 'WR'],
        may_not_make_it_back=[],
        board_state={'current_pick': 1, 'round': 1, 'picks_until_next': 0},
    )
    assert state.top_pick.player.name == 'A'
    assert state.positional_needs[0] == 'RB'


def test_picks_until_next_odd_round_user_not_yet():
    # Round 1, 12 teams, user at slot 6. current_pick=3 (pick_in_round=3).
    # user_pick_in_round=6. 6 >= 3 → 6-3 = 3.
    ls = LeagueSettings()
    ds = DraftState(
        season=2026, model_version='neural-v1', league_settings=ls,
        current_pick=3, total_picks=180, user_pick_position=6,
        drafted_ids=[], user_roster={'QB': [], 'RB': [], 'WR': [], 'TE': [], 'FLEX': []},
    )
    assert ds.picks_until_next == 3


def test_picks_until_next_odd_round_user_already_picked():
    # Round 1, 12 teams, user at slot 6. current_pick=7 (pick_in_round=7).
    # User already picked at slot 6 in round 1.
    # next_round=2 (even). next_user_pick = 12-6+1 = 7. picks_to_end = 12-7+1 = 6.
    # result = 6 + 7 - 1 = 12. Overall pick: user next turns at round-2 slot 7 = pick 12+7 = 19. 19-7 = 12. ✓
    ls = LeagueSettings()
    ds = DraftState(
        season=2026, model_version='neural-v1', league_settings=ls,
        current_pick=7, total_picks=180, user_pick_position=6,
        drafted_ids=[], user_roster={'QB': [], 'RB': [], 'WR': [], 'TE': [], 'FLEX': []},
    )
    assert ds.picks_until_next == 12


def test_picks_until_next_even_round_user_picks_last():
    # Round 2 (even), 12 teams, user at slot 1. In even rounds user picks last (slot 12).
    # current_pick=13 (pick_in_round=1). user_pick_in_round = 12-1+1 = 12.
    # 12 >= 1 → 12-1 = 11. User picks at round-2 slot 12 = pick 24. 24-13=11. ✓
    ls = LeagueSettings()
    ds = DraftState(
        season=2026, model_version='neural-v1', league_settings=ls,
        current_pick=13, total_picks=180, user_pick_position=1,
        drafted_ids=[], user_roster={'QB': [], 'RB': [], 'WR': [], 'TE': [], 'FLEX': []},
    )
    assert ds.picks_until_next == 11
