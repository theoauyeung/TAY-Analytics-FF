from __future__ import annotations
import pytest
from tay.draft.models import LeagueSettings, DraftState, PlayerProjection
from tay.draft.scoring import future_availability, score_player
from tay.draft.board import BoardAnalysis, PositionBoardState, TierCliff


def _player(
    gsis_id='X', position='RB', vor=50.0, vor_rank=10,
    adp=15.0, sim_boom_prob=0.2, tier=2,
):
    return PlayerProjection(
        gsis_id=gsis_id, name='Test', position=position, team='T',
        vor=vor, vor_rank=vor_rank, sim_mean=200.0,
        sim_p10=140.0, sim_p90=260.0, adp=adp, tier=tier,
        sim_boom_prob=sim_boom_prob, sim_bust_prob=0.1,
    )


def _state(current_pick=1, user_roster=None):
    ls = LeagueSettings()
    return DraftState(
        season=2026, model_version='neural-v1', league_settings=ls,
        current_pick=current_pick, total_picks=180, user_pick_position=1,
        drafted_ids=[],
        user_roster=user_roster or {'QB': [], 'RB': [], 'WR': [], 'TE': [], 'FLEX': []},
    )


def _board(
    player: PlayerProjection,
    survival_prob: float = 0.5,
    tier_cliffs: list[TierCliff] | None = None,
    extra_tier3_players: int = 8,   # top-tier count in position
) -> BoardAnalysis:
    """Minimal BoardAnalysis with one position group containing the test player."""
    tier3_players = [
        PlayerProjection(
            gsis_id=f'filler_{i}', name='F', position=player.position, team='T',
            vor=5.0, vor_rank=99, sim_mean=100.0, sim_p10=60.0, sim_p90=140.0,
            adp=50.0 + i, tier=2, sim_boom_prob=0.1, sim_bust_prob=0.1,
        )
        for i in range(extra_tier3_players)
    ]
    available = [player] + tier3_players
    pos_board = PositionBoardState(
        position=player.position,
        available=available,
        tier_cliffs=tier_cliffs or [],
        survival_probs={
            **{player.gsis_id: [survival_prob, survival_prob * 0.8, survival_prob * 0.6]},
            **{p.gsis_id: [0.5, 0.4, 0.3] for p in tier3_players},
        },
        run_in_progress=False,
    )
    return BoardAnalysis(per_position={player.position: pos_board}, opponent_rosters={})


# --- future_availability (kept as utility) ---

def test_future_availability_high_adp_relative_to_picks():
    p = _player(adp=100.0)
    fa = future_availability(p, current_pick=1, picks_until_next=2)
    assert fa > 0.9


def test_future_availability_low_adp_relative_to_picks():
    p = _player(adp=3.0)
    fa = future_availability(p, current_pick=1, picks_until_next=10)
    assert fa < 0.5


def test_future_availability_clamped_to_unit_interval():
    p = _player(adp=1.0)
    assert 0.0 <= future_availability(p, current_pick=1, picks_until_next=100) <= 1.0


# --- score_player ---

def test_score_player_returns_recommendation():
    p = _player(vor=80.0, adp=5.0, vor_rank=3)
    board = _board(p, survival_prob=0.4)
    rec = score_player(p, _state(), board)
    assert rec.player is p
    assert rec.draft_score > 0
    assert isinstance(rec.explanation, list)
    assert len(rec.explanation) >= 1


def test_score_player_explanation_is_structured():
    p = _player(vor=80.0, adp=5.0, vor_rank=3)
    board = _board(p)
    rec = score_player(p, _state(), board)
    for ex in rec.explanation:
        assert 'factor' in ex
        assert 'detail' in ex
        assert 'weight' in ex
        assert ex['weight'] in ('primary', 'secondary', 'risk')


def test_score_player_high_vor_produces_primary_explanation():
    p = _player(vor=80.0)
    board = _board(p)
    rec = score_player(p, _state(), board)
    assert any(e['weight'] == 'primary' for e in rec.explanation)


def test_cliff_premium_fires_when_player_is_last_in_tier():
    p = _player(gsis_id='CLIFF_PLAYER', vor=40.0, tier=1)
    next_p = _player(gsis_id='NEXT_PLAYER', vor=20.0, tier=2)
    cliff = TierCliff(
        before_player=p, after_player=next_p,
        vor_drop=20.0, tier_jump=1, rank_at_cliff=1,
    )
    board = _board(p, tier_cliffs=[cliff])
    rec = score_player(p, _state(), board)
    assert any('Cliff' in e['factor'] or 'cliff' in e['factor'].lower() for e in rec.explanation)


def test_no_cliff_premium_when_player_not_at_cliff():
    p = _player(gsis_id='MID_PLAYER', vor=50.0, tier=1)
    cliff_player = _player(gsis_id='CLIFF_PLAYER', vor=30.0, tier=1)
    next_p = _player(gsis_id='NEXT', vor=10.0, tier=2)
    cliff = TierCliff(
        before_player=cliff_player, after_player=next_p,
        vor_drop=20.0, tier_jump=1, rank_at_cliff=2,
    )
    board = _board(p, tier_cliffs=[cliff])
    rec_with_cliff = score_player(p, _state(), board)
    # Cliff premium should NOT be applied to MID_PLAYER (only CLIFF_PLAYER gets it)
    no_cliff_board = _board(p, tier_cliffs=[])
    rec_no_cliff = score_player(p, _state(), no_cliff_board)
    # Scores should be equal (no cliff premium)
    assert abs(rec_with_cliff.draft_score - rec_no_cliff.draft_score) < 0.01


def test_scarcity_premium_increases_when_tier3_pool_thin():
    p = _player(vor=40.0, tier=1)
    board_full = _board(p, extra_tier3_players=8)   # at threshold → premium=0
    board_thin = _board(p, extra_tier3_players=0)   # exhausted → premium=0.5
    rec_full = score_player(p, _state(), board_full)
    rec_thin = score_player(p, _state(), board_thin)
    assert rec_thin.draft_score > rec_full.draft_score


def test_low_survival_produces_risk_explanation():
    p = _player(vor=40.0, adp=5.0)
    board = _board(p, survival_prob=0.2)  # 20% → at risk
    rec = score_player(p, _state(), board)
    assert any(e['weight'] == 'risk' for e in rec.explanation)


def test_score_player_explanation_undervalued():
    # adp - vor_rank = 50 - 5 = 45 > 15 → undervalued explanation
    p = _player(vor=60.0, adp=50.0, vor_rank=5)
    board = _board(p)
    rec = score_player(p, _state(), board)
    assert any('Undervalued' in e['factor'] for e in rec.explanation)


def test_roster_fit_bonus_applied():
    p = _player(position='RB', vor=40.0)
    empty_roster = {'QB': [], 'RB': [], 'WR': [], 'TE': [], 'FLEX': []}
    full_roster = {'QB': ['q1'], 'RB': ['r1', 'r2', 'r3'], 'WR': ['w1', 'w2'], 'TE': ['t1'], 'FLEX': []}
    board = _board(p)
    rec_empty = score_player(p, _state(user_roster=empty_roster), board)
    rec_full = score_player(p, _state(user_roster=full_roster), board)
    assert rec_empty.draft_score > rec_full.draft_score
