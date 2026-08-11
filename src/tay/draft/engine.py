"""Recommendation engine — loads projections and scores available players."""
from __future__ import annotations
import duckdb

from tay.draft.models import DraftState, PlayerProjection, RecommendationState
from tay.draft.scoring import positional_urgency, score_player

REPLACEMENT_SPOTS: dict[str, int] = {'QB': 12, 'RB': 30, 'WR': 30, 'TE': 12}

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
    rows = conn.execute(_LOAD_SQL, [season, model_version]).fetchall()
    drafted_set = set(drafted_ids)
    return [
        PlayerProjection(
            gsis_id=r[0], name=r[1], position=r[2], team=r[3],
            vor=r[4], vor_rank=r[5], sim_mean=r[6],
            sim_p10=r[7], sim_p90=r[8], adp=r[9],
            tier=r[10], sim_boom_prob=r[11], sim_bust_prob=r[12],
        )
        for r in rows if r[0] not in drafted_set
    ]


def recommend(
    conn: duckdb.DuckDBPyConnection,
    state: DraftState,
) -> RecommendationState:
    players = load_projections(
        conn, state.season, state.model_version, state.drafted_ids
    )

    available_by_position: dict[str, int] = {}
    for p in players:
        available_by_position[p.position] = available_by_position.get(p.position, 0) + 1

    scored = [
        score_player(p, state, available_by_position, REPLACEMENT_SPOTS)
        for p in players
    ]
    scored.sort(key=lambda r: r.draft_score, reverse=True)

    if not scored:
        raise ValueError(
            f"No available players for season={state.season} model={state.model_version}"
        )

    top_pick = scored[0]
    alternatives = scored[1:4]

    positional_needs = sorted(
        available_by_position.keys(),
        key=lambda pos: positional_urgency(pos, available_by_position[pos], REPLACEMENT_SPOTS),
        reverse=True,
    )

    top_id = top_pick.player.gsis_id
    may_not_make_it_back = [
        r.player for r in scored[1:]
        if r.future_availability_pct < 0.35 and r.player.gsis_id != top_id
    ]

    board_state = {
        'current_pick': state.current_pick,
        'round': state.round,
        'picks_until_next': state.picks_until_next,
    }

    return RecommendationState(
        top_pick=top_pick,
        alternatives=alternatives,
        positional_needs=positional_needs,
        may_not_make_it_back=may_not_make_it_back,
        board_state=board_state,
    )
