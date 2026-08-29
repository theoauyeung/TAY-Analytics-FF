"""Board-level analysis — one-shot computation over all available players."""
from __future__ import annotations
from dataclasses import dataclass, field
from tay.draft.models import PlayerProjection
from tay.draft.scoring import future_availability


@dataclass
class TierCliff:
    before_player: PlayerProjection   # last player in current tier
    after_player: PlayerProjection    # first player in next (worse) tier
    vor_drop: float                   # before.vor - after.vor
    tier_jump: int                    # e.g. tier 2→3 means tier_jump=1
    rank_at_cliff: int                # 1-indexed position rank of before_player


@dataclass
class PositionBoardState:
    position: str
    available: list[PlayerProjection]             # sorted VOR desc
    tier_cliffs: list[TierCliff]
    survival_probs: dict[str, list[float]]        # gsis_id → [P(next), P(+1), P(+2)]
    run_in_progress: bool                         # 3+ of last 5 picks at this position


@dataclass
class BoardAnalysis:
    per_position: dict[str, PositionBoardState]
    opponent_rosters: dict[int, dict[str, int]]   # team_num → {position: count}


def _picking_team(overall_pick: int, teams: int) -> int:
    """Team number (1-indexed) picking at overall_pick in a snake draft."""
    pick_in_round = ((overall_pick - 1) % teams) + 1
    round_num = (overall_pick - 1) // teams + 1
    return pick_in_round if round_num % 2 == 1 else teams - pick_in_round + 1


def _find_tier_cliffs(players: list[PlayerProjection]) -> list[TierCliff]:
    """Detect where tier number increases in a VOR-sorted player list."""
    cliffs = []
    for i in range(len(players) - 1):
        curr, nxt = players[i], players[i + 1]
        if curr.tier is None or nxt.tier is None:
            continue
        if nxt.tier > curr.tier:
            cliffs.append(TierCliff(
                before_player=curr,
                after_player=nxt,
                vor_drop=curr.vor - nxt.vor,
                tier_jump=nxt.tier - curr.tier,
                rank_at_cliff=i + 1,   # 1-indexed
            ))
    return cliffs


def build_board_analysis(
    players: list[PlayerProjection],
    pick_log: list[tuple[str, int, str]],   # (gsis_id, team_number, position)
    current_pick: int,
    teams: int,
    user_pick_numbers: list[int],           # next 3 user pick numbers, len == 3
) -> BoardAnalysis:
    # 1. Opponent rosters
    opponent_rosters: dict[int, dict[str, int]] = {}
    for _gsis_id, team_num, position in pick_log:
        team_roster = opponent_rosters.setdefault(team_num, {})
        team_roster[position] = team_roster.get(position, 0) + 1

    # 2. Run detection — last 5 picks
    last5 = pick_log[-5:]
    run_positions: set[str] = set()
    for pos in {entry[2] for entry in last5}:
        if sum(1 for e in last5 if e[2] == pos) >= 3:
            run_positions.add(pos)

    # 3. Group available players by position, sort VOR desc
    by_position: dict[str, list[PlayerProjection]] = {}
    for p in players:
        by_position.setdefault(p.position, []).append(p)
    for pos_players in by_position.values():
        pos_players.sort(key=lambda p: p.vor, reverse=True)

    # 4. Teams picking before user at horizon 0
    teams_before_h0 = [
        _picking_team(pk, teams)
        for pk in range(current_pick, user_pick_numbers[0])
    ] if user_pick_numbers else []

    # 5. Build per-position state with survival probabilities
    per_position: dict[str, PositionBoardState] = {}
    for pos, pos_players in by_position.items():
        # Hungry teams: teams picking before user at horizon 0 with ≤ 1 player at this position
        hungry = sum(
            1 for t in teams_before_h0
            if opponent_rosters.get(t, {}).get(pos, 0) <= 1
        )
        run_active = pos in run_positions

        survival_probs: dict[str, list[float]] = {}
        for p in pos_players:
            probs: list[float] = []
            for h, horizon_pick in enumerate(user_pick_numbers[:3]):
                picks_until = max(0, horizon_pick - current_pick)
                base = future_availability(p, current_pick, picks_until)
                if h == 0:
                    demand = hungry * 0.05
                    if run_active:
                        demand += len(teams_before_h0) * 0.03
                    base = max(0.0, min(1.0, base - demand))
                probs.append(base)
            survival_probs[p.gsis_id] = probs

        per_position[pos] = PositionBoardState(
            position=pos,
            available=pos_players,
            tier_cliffs=_find_tier_cliffs(pos_players),
            survival_probs=survival_probs,
            run_in_progress=run_active,
        )

    return BoardAnalysis(
        per_position=per_position,
        opponent_rosters=opponent_rosters,
    )
