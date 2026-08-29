"""Draft Score formula — stateless scoring of available players."""
from __future__ import annotations
from tay.draft.models import DraftState, PlayerProjection, Recommendation

_FLEX_ELIGIBLE = {'RB', 'WR', 'TE'}
_STARTER_REQUIREMENTS = {'QB': 1, 'RB': 2, 'WR': 2, 'TE': 1}
_FLEX_SPOTS = 1
_SCARCITY_THRESHOLDS: dict[str, int] = {'QB': 4, 'TE': 4, 'RB': 8, 'WR': 8}


def future_availability(player: PlayerProjection, current_pick: int, picks_until_next: int) -> float:
    """P(player still available at user's next pick). High = can wait, Low = must take now."""
    next_pick = current_pick + picks_until_next
    adp = player.adp
    if adp <= 0 or adp >= 500:
        return 1.0
    adp_std = max(2.0, adp * 0.25)
    z = (next_pick - adp) / adp_std
    return max(0.0, min(1.0, 0.5 - 0.25 * z))


def roster_fit(
    player: PlayerProjection,
    user_roster: dict[str, list[str]],
    roster_config: dict[str, int] | None = None,
) -> float:
    """Multiplier [0.5, 1.2] for how well player fills user's roster needs."""
    pos = player.position
    requirements = roster_config if roster_config is not None else _STARTER_REQUIREMENTS
    filled = len(user_roster.get(pos, []))
    required = requirements.get(pos, 1)

    score = 1.0
    if filled == 0:
        score += 0.2
    elif pos in _FLEX_ELIGIBLE:
        total_skill_filled = sum(len(user_roster.get(p, [])) for p in _FLEX_ELIGIBLE)
        total_skill_required = sum(requirements.get(p, 0) for p in _FLEX_ELIGIBLE) + _FLEX_SPOTS
        if filled >= required and total_skill_filled >= total_skill_required:
            score -= 0.3
    else:
        if filled >= required:
            score -= 0.3

    return max(0.5, min(1.2, score))


def score_player(
    player: PlayerProjection,
    state: DraftState,
    board: 'BoardAnalysis',
) -> Recommendation:
    """Compute Draft Score and structured explanation for one player."""
    from tay.draft.board import BoardAnalysis  # local import avoids circular dependency

    pos_board = board.per_position.get(player.position)

    # Survival probability (next pick)
    if pos_board and player.gsis_id in pos_board.survival_probs:
        survival_prob = pos_board.survival_probs[player.gsis_id][0]
    else:
        survival_prob = future_availability(player, state.current_pick, state.picks_until_next)

    # Cliff premium: +0.3 if player is the last in their tier
    cliff_premium = 0.0
    cliff_ids: set[str] = set()
    if pos_board:
        cliff_ids = {cliff.before_player.gsis_id for cliff in pos_board.tier_cliffs}
        if player.gsis_id in cliff_ids:
            cliff_premium = 0.3

    # Scarcity premium: 0–0.5 based on remaining tier-1-through-3 players
    scarcity_premium = 0.0
    if pos_board:
        threshold = _SCARCITY_THRESHOLDS.get(player.position, 8)
        top_tier_count = sum(1 for p in pos_board.available if (p.tier or 5) <= 3)
        scarcity_premium = max(0.0, min(0.5, 0.5 * (1.0 - top_tier_count / threshold)))

    rf = roster_fit(player, state.user_roster, state.league_settings.roster_config)
    urgency_factor = 1.0 + cliff_premium + scarcity_premium
    now_vs_wait = 1.5 - 0.5 * survival_prob

    draft_score = player.vor * urgency_factor * rf * now_vs_wait

    # QB patience suppression
    if player.position == 'QB' and len(state.user_roster.get('QB', [])) == 0:
        user_skill_count = sum(
            len(state.user_roster.get(p, [])) for p in ('RB', 'WR', 'TE')
        )
        if user_skill_count < 4 and state.current_pick <= state.league_settings.teams * 7:
            draft_score *= 0.5

    # Structured explanation
    explanation: list[dict[str, str]] = []

    if player.vor > 20:
        explanation.append({
            'factor': 'High Value',
            'detail': f'{player.vor:.0f} VOR points above replacement',
            'weight': 'primary',
        })

    if cliff_premium > 0:
        explanation.append({
            'factor': 'Tier Cliff',
            'detail': f'Last available {player.position} in this tier — next group is significantly weaker',
            'weight': 'primary',
        })

    if survival_prob < 0.35:
        gone_pct = round((1 - survival_prob) * 100)
        explanation.append({
            'factor': 'At Risk',
            'detail': f'{gone_pct}% chance gone before your next pick',
            'weight': 'risk',
        })

    if scarcity_premium > 0.3 and pos_board:
        top_tier = sum(1 for p in pos_board.available if (p.tier or 5) <= 3)
        explanation.append({
            'factor': 'Positional Scarcity',
            'detail': f'Only {top_tier} quality {player.position}s remain',
            'weight': 'primary',
        })

    if player.adp - player.vor_rank > 15:
        explanation.append({
            'factor': 'Undervalued',
            'detail': f'ADP {player.adp:.0f} vs model rank #{player.vor_rank}',
            'weight': 'secondary',
        })

    if player.sim_boom_prob > 0.3:
        explanation.append({
            'factor': 'Upside',
            'detail': f'{player.sim_boom_prob:.0%} boom probability',
            'weight': 'secondary',
        })

    if not explanation:
        explanation.append({
            'factor': 'Solid Value',
            'detail': f'Good pick at position {state.current_pick}',
            'weight': 'secondary',
        })

    return Recommendation(
        player=player,
        draft_score=draft_score,
        roster_fit=rf,
        positional_urgency=scarcity_premium,
        future_availability_pct=survival_prob,
        explanation=explanation,
    )
