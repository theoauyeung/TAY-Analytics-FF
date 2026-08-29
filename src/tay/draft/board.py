"""Board-level analysis — one-shot computation over all available players."""
from __future__ import annotations
from dataclasses import dataclass, field
from tay.draft.models import PlayerProjection


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
