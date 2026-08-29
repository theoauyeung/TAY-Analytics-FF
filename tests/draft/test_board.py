from __future__ import annotations
import pytest
from tay.draft.models import PlayerProjection
from tay.draft.board import BoardAnalysis, build_board_analysis


def _player(gsis_id: str, position: str, vor: float, adp: float, tier: int):
    return PlayerProjection(
        gsis_id=gsis_id, name=gsis_id, position=position, team='T',
        vor=vor, vor_rank=1, sim_mean=200.0,
        sim_p10=140.0, sim_p90=260.0, adp=adp,
        tier=tier, sim_boom_prob=0.2, sim_bust_prob=0.1,
    )


# --- Opponent rosters ---

def test_opponent_rosters_empty_pick_log():
    players = [_player('R1', 'RB', 50.0, 2.0, 1)]
    board = build_board_analysis(
        players=players,
        pick_log=[],
        current_pick=1,
        teams=12,
        user_pick_numbers=[6, 19, 30],
    )
    assert board.opponent_rosters == {}


def test_opponent_rosters_reconstructed_from_pick_log():
    players = [_player('R1', 'RB', 50.0, 5.0, 1)]
    pick_log = [
        ('Q1', 1, 'QB'),
        ('R2', 2, 'RB'),
        ('W1', 3, 'WR'),
        ('R3', 1, 'RB'),  # team 1 gets second RB
    ]
    board = build_board_analysis(
        players=players,
        pick_log=pick_log,
        current_pick=5,
        teams=12,
        user_pick_numbers=[6, 19, 30],
    )
    assert board.opponent_rosters[1]['QB'] == 1
    assert board.opponent_rosters[1]['RB'] == 1
    assert board.opponent_rosters[2]['RB'] == 1
    assert board.opponent_rosters[3]['WR'] == 1


# --- Run detection ---

def test_no_run_with_mixed_positions():
    players = [_player('R1', 'RB', 50.0, 5.0, 1)]
    pick_log = [
        ('Q1', 1, 'QB'),
        ('R2', 2, 'RB'),
        ('W1', 3, 'WR'),
        ('Q2', 4, 'QB'),
        ('W2', 5, 'WR'),
    ]
    board = build_board_analysis(
        players=players,
        pick_log=pick_log,
        current_pick=6,
        teams=12,
        user_pick_numbers=[6, 19, 30],
    )
    assert not board.per_position['RB'].run_in_progress


def test_run_detected_when_3_of_last_5_same_position():
    players = [_player('R1', 'RB', 50.0, 5.0, 1)]
    pick_log = [
        ('W1', 1, 'WR'),
        ('R2', 2, 'RB'),
        ('R3', 3, 'RB'),
        ('R4', 4, 'RB'),
        ('W2', 5, 'WR'),
    ]
    board = build_board_analysis(
        players=players,
        pick_log=pick_log,
        current_pick=6,
        teams=12,
        user_pick_numbers=[6, 19, 30],
    )
    assert board.per_position['RB'].run_in_progress


# --- Tier cliffs ---

def test_no_cliff_when_single_player():
    players = [_player('R1', 'RB', 50.0, 2.0, 1)]
    board = build_board_analysis(
        players=players, pick_log=[], current_pick=1,
        teams=12, user_pick_numbers=[6, 19, 30],
    )
    assert board.per_position['RB'].tier_cliffs == []


def test_no_cliff_when_all_same_tier():
    players = [
        _player('R1', 'RB', 60.0, 2.0, 1),
        _player('R2', 'RB', 50.0, 4.0, 1),
        _player('R3', 'RB', 40.0, 6.0, 1),
    ]
    board = build_board_analysis(
        players=players, pick_log=[], current_pick=1,
        teams=12, user_pick_numbers=[6, 19, 30],
    )
    assert board.per_position['RB'].tier_cliffs == []


def test_cliff_detected_at_tier_boundary():
    players = [
        _player('R1', 'RB', 60.0, 2.0, 1),
        _player('R2', 'RB', 50.0, 4.0, 1),
        _player('R3', 'RB', 20.0, 8.0, 2),  # tier jumps 1→2 here
        _player('R4', 'RB', 10.0, 10.0, 2),
    ]
    board = build_board_analysis(
        players=players, pick_log=[], current_pick=1,
        teams=12, user_pick_numbers=[6, 19, 30],
    )
    cliffs = board.per_position['RB'].tier_cliffs
    assert len(cliffs) == 1
    assert cliffs[0].before_player.gsis_id == 'R2'
    assert cliffs[0].after_player.gsis_id == 'R3'
    assert cliffs[0].tier_jump == 1
    assert cliffs[0].rank_at_cliff == 2  # R2 is position rank 2
    assert abs(cliffs[0].vor_drop - 30.0) < 0.01


def test_available_list_sorted_by_vor_desc():
    players = [
        _player('R3', 'RB', 30.0, 6.0, 2),
        _player('R1', 'RB', 60.0, 2.0, 1),
        _player('R2', 'RB', 45.0, 4.0, 1),
    ]
    board = build_board_analysis(
        players=players, pick_log=[], current_pick=1,
        teams=12, user_pick_numbers=[6, 19, 30],
    )
    ids = [p.gsis_id for p in board.per_position['RB'].available]
    assert ids == ['R1', 'R2', 'R3']


# --- Survival probabilities ---

def test_survival_prob_has_three_horizons():
    players = [_player('R1', 'RB', 50.0, 10.0, 1)]
    board = build_board_analysis(
        players=players, pick_log=[], current_pick=1,
        teams=12, user_pick_numbers=[6, 19, 30],
    )
    probs = board.per_position['RB'].survival_probs['R1']
    assert len(probs) == 3
    assert all(0.0 <= p <= 1.0 for p in probs)


def test_survival_prob_decreases_with_horizon():
    # Player with ADP=10 — further horizons are worse (more picks have happened)
    players = [_player('R1', 'RB', 50.0, 10.0, 1)]
    board = build_board_analysis(
        players=players, pick_log=[], current_pick=1,
        teams=12, user_pick_numbers=[6, 19, 30],
    )
    probs = board.per_position['RB'].survival_probs['R1']
    # Each horizon is further out → lower survival
    assert probs[0] >= probs[1] >= probs[2]


def test_hungry_opponents_reduce_survival_at_horizon0():
    # Compare: 5 teams picking before user with 0 RBs (hungry) vs user picks immediately (no teams before).
    # More hungry opponents → lower survival probability.
    players = [_player('R1', 'RB', 50.0, 20.0, 1)]

    # High demand: 5 teams pick before user, all with 0 RBs
    board_high_demand = build_board_analysis(
        players=players,
        pick_log=[],
        current_pick=1,
        teams=12,
        user_pick_numbers=[6, 19, 30],
    )

    # Low demand: user picks immediately next, no teams between current_pick and user pick
    board_low_demand = build_board_analysis(
        players=players,
        pick_log=[],
        current_pick=6,
        teams=12,
        user_pick_numbers=[6, 19, 30],
    )

    prob_high = board_high_demand.per_position['RB'].survival_probs['R1'][0]
    prob_low = board_low_demand.per_position['RB'].survival_probs['R1'][0]
    assert prob_low >= prob_high  # fewer hungry teams → higher survival


def test_run_in_progress_reduces_survival_at_horizon0():
    players = [_player('R1', 'RB', 50.0, 20.0, 1)]
    # No run
    board_no_run = build_board_analysis(
        players=players, pick_log=[], current_pick=1,
        teams=12, user_pick_numbers=[6, 19, 30],
    )
    # RB run: last 5 picks are RB
    run_picks = [('X', i + 1, 'RB') for i in range(5)]
    board_run = build_board_analysis(
        players=players,
        pick_log=run_picks,
        current_pick=6,
        teams=12,
        user_pick_numbers=[12, 25, 36],
    )
    p_no_run = board_no_run.per_position['RB'].survival_probs['R1'][0]
    p_run = board_run.per_position['RB'].survival_probs['R1'][0]
    assert p_run <= p_no_run  # run increases demand → lower survival
