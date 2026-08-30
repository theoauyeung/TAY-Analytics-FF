"""Recommendation engine — loads projections and scores available players."""
from __future__ import annotations
import time
import logging
import duckdb

from tay.draft.board import build_board_analysis
from tay.draft.models import (
    DraftState, PlayerProjection, RecommendationState,
    WaitScenario, NextRoundPositionSummary,
)
from tay.draft.scoring import score_player

logger = logging.getLogger(__name__)

_projection_cache: dict[tuple[int, str], list[PlayerProjection]] = {}

_LOAD_SQL = """
    SELECT pr.gsis_id, p.name, p.position, p.team,
           COALESCE(pr.vor, 0.0),
           COALESCE(pr.vor_rank, 9999),
           COALESCE(pr.sim_mean, pr.mean_projection, 0.0),
           COALESCE(pr.sim_p10, pr.p10, 0.0),
           COALESCE(pr.sim_p90, pr.p90, 0.0),
           COALESCE(a.adp, 999.0),
           pr.tier,
           COALESCE(pr.sim_boom_prob, 0.0),
           COALESCE(pr.sim_bust_prob, 0.0)
    FROM projections pr
    JOIN players p ON p.gsis_id = pr.gsis_id
    LEFT JOIN adp a ON a.gsis_id = pr.gsis_id
                   AND a.season = pr.season
                   AND a.format = 'ppr'
                   AND a.platform = 'espn'
                   AND a.adp NOT IN (999, 9999999)
    WHERE pr.season = ? AND pr.model_version = ?
      AND p.position IN ('QB', 'RB', 'WR', 'TE')
    ORDER BY pr.vor DESC NULLS LAST
"""


def load_projections(
    conn: duckdb.DuckDBPyConnection,
    season: int,
    model_version: str,
    drafted_ids: list[str],
) -> list[PlayerProjection]:
    cache_key = (season, model_version)
    if cache_key not in _projection_cache:
        t0 = time.perf_counter()
        rows = conn.execute(_LOAD_SQL, [season, model_version]).fetchall()
        _projection_cache[cache_key] = [
            PlayerProjection(
                gsis_id=r[0], name=r[1], position=r[2], team=r[3],
                vor=r[4], vor_rank=r[5], sim_mean=r[6],
                sim_p10=r[7], sim_p90=r[8], adp=r[9],
                tier=r[10], sim_boom_prob=r[11], sim_bust_prob=r[12],
            )
            for r in rows
        ]
        logger.info("projection DB query: %.0fms", (time.perf_counter() - t0) * 1000)
    else:
        logger.info("projection cache hit for season=%s model=%s", season, model_version)

    drafted_set = set(drafted_ids)
    return [p for p in _projection_cache[cache_key] if p.gsis_id not in drafted_set]


def _compute_next_user_picks(
    current_pick: int,
    teams: int,
    user_pick_position: int,
    total_rounds: int,
) -> list[int]:
    """All upcoming snake-draft pick numbers for the user, starting from current_pick."""
    total_picks = teams * total_rounds
    all_pick_numbers: list[int] = []
    for round_num in range(1, total_rounds + 1):
        if round_num % 2 == 1:
            pick_in_round = user_pick_position
        else:
            pick_in_round = teams - user_pick_position + 1
        pick_number = (round_num - 1) * teams + pick_in_round
        all_pick_numbers.append(pick_number)
    return [p for p in all_pick_numbers if p >= current_pick]


def _build_wait_analysis(board, scored: list) -> list[WaitScenario]:
    """One WaitScenario per unique position in the top 5 scored players."""
    top5_positions = list(dict.fromkeys(r.player.position for r in scored[:5]))
    if len(set(top5_positions)) <= 1:
        return []
    scenarios: list[WaitScenario] = []

    for pos in top5_positions:
        pos_board = board.per_position.get(pos)
        if not pos_board or not pos_board.available:
            continue
        best = pos_board.available[0]
        survivals = [
            pos_board.survival_probs.get(p.gsis_id, [0.5])[0]
            for p in pos_board.available
        ]
        total_survival = sum(survivals)
        if total_survival > 0:
            expected_vor = sum(
                p.vor * s for p, s in zip(pos_board.available, survivals)
            ) / total_survival
        else:
            expected_vor = 0.0

        cliff_ids = {cliff.before_player.gsis_id for cliff in pos_board.tier_cliffs}
        survival_prob = pos_board.survival_probs.get(best.gsis_id, [0.5])[0]

        scenarios.append(WaitScenario(
            position=pos,
            best_now_name=best.name,
            best_now_vor=round(best.vor, 1),
            expected_vor_at_next_pick=round(expected_vor, 1),
            vor_cost_of_waiting=round(best.vor - expected_vor, 1),
            cliff_before_next_pick=(best.gsis_id in cliff_ids),
            survival_probability=round(survival_prob, 3),
        ))
    return scenarios


def _build_next_round_board(board) -> dict[str, NextRoundPositionSummary]:
    """Summary of what each position's board will look like at the user's next pick."""
    result: dict[str, NextRoundPositionSummary] = {}
    for pos, pos_board in board.per_position.items():
        strong = sum(
            1 for p in pos_board.available
            if (p.tier or 5) <= 3
            and pos_board.survival_probs.get(p.gsis_id, [0.5])[0] > 0.3
        )
        next_cliff = pos_board.tier_cliffs[0] if pos_board.tier_cliffs else None
        result[pos] = NextRoundPositionSummary(
            position=pos,
            strong_options_remaining=strong,
            next_cliff_rank=next_cliff.rank_at_cliff if next_cliff else None,
            cliff_warning=bool(pos_board.tier_cliffs),
        )
    return result


def recommend(
    conn: duckdb.DuckDBPyConnection,
    state: DraftState,
) -> RecommendationState:
    t_start = time.perf_counter()

    players = load_projections(conn, state.season, state.model_version, state.drafted_ids)
    t_proj = time.perf_counter()

    teams = state.league_settings.teams
    total_rounds = state.total_picks // teams
    user_pick_numbers = _compute_next_user_picks(
        current_pick=state.current_pick,
        teams=teams,
        user_pick_position=state.user_pick_position,
        total_rounds=total_rounds,
    )

    board = build_board_analysis(
        players=players,
        pick_log=state.pick_log,
        current_pick=state.current_pick,
        teams=state.league_settings.teams,
        user_pick_numbers=user_pick_numbers,
    )
    t_board = time.perf_counter()

    scored = [score_player(p, state, board) for p in players]
    scored.sort(key=lambda r: r.draft_score, reverse=True)
    t_score = time.perf_counter()

    logger.info(
        "recommend timings — projections: %.0fms, board: %.0fms, scoring: %.0fms, total: %.0fms",
        (t_proj - t_start) * 1000,
        (t_board - t_proj) * 1000,
        (t_score - t_board) * 1000,
        (t_score - t_start) * 1000,
    )

    if not scored:
        raise ValueError(
            f'No available players for season={state.season} model={state.model_version}'
        )

    top_pick = scored[0]
    alternatives = scored[1:4]

    wait_analysis = _build_wait_analysis(board, scored)
    next_round_board = _build_next_round_board(board)

    # Sort positions by average scarcity premium (positional_urgency field).
    # Include exhausted positions (not in board) at max urgency (1.0).
    all_positions = list(board.per_position.keys()) + [
        pos for pos in ('QB', 'RB', 'WR', 'TE') if pos not in board.per_position
    ]
    positional_needs = sorted(
        all_positions,
        key=lambda pos: (
            sum(r.positional_urgency for r in scored if r.player.position == pos)
            / max(1, sum(1 for r in scored if r.player.position == pos))
        ) if any(r.player.position == pos for r in scored) else 1.0,
        reverse=True,
    )

    top_id = top_pick.player.gsis_id
    may_not_make_it_back = [
        r.player for r in scored[1:]
        if r.future_availability_pct < 0.35 and r.player.gsis_id != top_id
    ]

    return RecommendationState(
        top_pick=top_pick,
        alternatives=alternatives,
        positional_needs=positional_needs,
        may_not_make_it_back=may_not_make_it_back,
        wait_analysis=wait_analysis,
        next_round_board=next_round_board,
        board_state={
            'current_pick': state.current_pick,
            'round': state.round,
            'picks_until_next': state.picks_until_next,
        },
    )
