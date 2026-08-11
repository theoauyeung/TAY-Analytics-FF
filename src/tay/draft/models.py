"""Pure dataclasses for draft engine inputs and outputs."""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class LeagueSettings:
    teams: int = 12
    scoring: str = 'ppr'
    roster_config: dict[str, int] = field(
        default_factory=lambda: {'QB': 1, 'RB': 2, 'WR': 2, 'TE': 1, 'FLEX': 1}
    )


@dataclass
class DraftState:
    season: int
    model_version: str
    league_settings: LeagueSettings
    current_pick: int          # 1-indexed overall pick number
    total_picks: int           # league_size * rounds (e.g. 12 * 15 = 180)
    user_pick_position: int    # 1-indexed draft slot (1 = first pick overall in round 1)
    drafted_ids: list[str]     # gsis_ids already taken (all teams)
    user_roster: dict[str, list[str]]  # position -> list of gsis_ids

    @property
    def round(self) -> int:
        return (self.current_pick - 1) // self.league_settings.teams + 1

    @property
    def pick_in_round(self) -> int:
        return (self.current_pick - 1) % self.league_settings.teams + 1

    @property
    def picks_until_next(self) -> int:
        """Picks remaining until user's next turn (0 = it's their turn now)."""
        teams = self.league_settings.teams
        pick_in_round = self.pick_in_round
        # Snake draft: odd rounds pick ascending, even rounds descending
        current_round = self.round
        if current_round % 2 == 1:
            user_pick_in_round = self.user_pick_position
        else:
            user_pick_in_round = teams - self.user_pick_position + 1
        if user_pick_in_round >= pick_in_round:
            return user_pick_in_round - pick_in_round
        # User already picked this round; next pick is in the next round
        next_round = current_round + 1
        if next_round % 2 == 1:
            next_user_pick = self.user_pick_position
        else:
            next_user_pick = teams - self.user_pick_position + 1
        picks_to_end_of_round = teams - pick_in_round + 1
        return picks_to_end_of_round + next_user_pick - 1


@dataclass
class PlayerProjection:
    gsis_id: str
    name: str
    position: str
    team: str
    vor: float
    vor_rank: int
    sim_mean: float
    sim_p10: float
    sim_p90: float
    adp: float
    tier: int | None
    sim_boom_prob: float
    sim_bust_prob: float


@dataclass
class Recommendation:
    player: PlayerProjection
    draft_score: float
    roster_fit: float
    positional_urgency: float
    future_availability_pct: float
    explanation: list[str]


@dataclass
class RecommendationState:
    top_pick: Recommendation
    alternatives: list[Recommendation]
    positional_needs: list[str]           # positions ordered by urgency
    may_not_make_it_back: list[PlayerProjection]  # ADP suggests drafted before next turn
    board_state: dict                     # {current_pick, round, picks_until_next}
