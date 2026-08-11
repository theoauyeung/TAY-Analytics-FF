"""Draft Score formula — stateless scoring of available players."""
from __future__ import annotations
from tay.draft.models import DraftState, PlayerProjection, Recommendation

_FLEX_ELIGIBLE = {'RB', 'WR', 'TE'}
_STARTER_REQUIREMENTS = {'QB': 1, 'RB': 2, 'WR': 2, 'TE': 1}


def future_availability(player: PlayerProjection, picks_until_next: int) -> float:
    """P(player still available at next pick) based on ADP vs picks remaining."""
    adp_std = max(1.0, player.adp * 0.3)
    adp_z = picks_until_next / adp_std
    return max(0.0, min(1.0, 1.0 - adp_z))


def positional_urgency(
    position: str,
    available_at_position: int,
    replacement_spots: dict[str, int],
) -> float:
    """Scarcity score [0, 1] — 1 means position is nearly exhausted."""
    cap = replacement_spots.get(position, 30)
    return max(0.0, min(1.0, 1.0 - available_at_position / cap))


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
    flex_filled = len(user_roster.get('FLEX', []))

    score = 1.0
    if filled == 0:
        score += 0.2   # bonus: unfilled starter slot at this position
    elif filled >= required:
        score -= 0.3   # penalty: position already covered

    if pos in _FLEX_ELIGIBLE and flex_filled == 0:
        score += 0.1   # flex slot still open

    return max(0.5, min(1.2, score))


def score_player(
    player: PlayerProjection,
    state: DraftState,
    available_by_position: dict[str, int],
    replacement_spots: dict[str, int],
) -> Recommendation:
    """Compute Draft Score and build explanation for one player."""
    fa = future_availability(player, state.picks_until_next)
    pu = positional_urgency(
        player.position,
        available_by_position.get(player.position, 30),
        replacement_spots,
    )
    rf = roster_fit(player, state.user_roster, state.league_settings.roster_config)

    base_value = player.vor
    draft_score = (base_value * rf * (1.0 + pu)) * (0.5 + 0.5 * fa)

    explanation: list[str] = []
    if player.vor > 20:
        explanation.append(f"High value: {player.vor:.0f} VOR points above replacement")
    if player.adp - player.vor_rank > 15:
        explanation.append(
            f"Undervalued: ADP {player.adp:.0f} vs model rank #{player.vor_rank}"
        )
    avail_at_pos = available_by_position.get(player.position, 30)
    if pu > 0.6:
        explanation.append(
            f"Positional scarcity: only {avail_at_pos} {player.position}s remain"
        )
    next_pick = state.current_pick + state.picks_until_next
    if fa < 0.5:
        explanation.append(f"May not be available at pick {next_pick}")
    if player.sim_boom_prob > 0.3:
        explanation.append(f"High upside: {player.sim_boom_prob:.0%} boom probability")
    if not explanation:
        explanation.append(f"Solid value at pick {state.current_pick}")

    return Recommendation(
        player=player,
        draft_score=draft_score,
        roster_fit=rf,
        positional_urgency=pu,
        future_availability_pct=fa,
        explanation=explanation,
    )
