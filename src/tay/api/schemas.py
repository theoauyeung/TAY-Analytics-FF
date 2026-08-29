"""Pydantic v2 request/response models for the TAY API."""
from __future__ import annotations
from pydantic import BaseModel, Field


# ── Players ──────────────────────────────────────────────────────────────────

class PlayerOut(BaseModel):
    gsis_id: str
    name: str
    position: str
    team: str | None
    season: int
    model_version: str
    mean_projection: float | None
    vor: float | None
    vor_rank: int | None
    tier: int | None
    adp_delta: float | None
    adp: float | None
    sim_mean: float | None
    sim_p10: float | None
    sim_p90: float | None
    sim_boom_prob: float | None
    sim_bust_prob: float | None
    avail_mean: float | None
    # Position-specific projected statistics
    proj_targets: float | None = None
    proj_receptions: float | None = None
    proj_rec_yards: float | None = None
    proj_rec_tds: float | None = None
    proj_rush_attempts: float | None = None
    proj_rush_yards: float | None = None
    proj_rush_tds: float | None = None
    proj_pass_attempts: float | None = None
    proj_completions: float | None = None
    proj_pass_yards: float | None = None
    proj_pass_tds: float | None = None
    proj_interceptions: float | None = None


# ── Rankings ──────────────────────────────────────────────────────────────────

class RankingOut(BaseModel):
    rank: int
    gsis_id: str
    espn_id: str | None
    name: str
    position: str
    team: str | None
    vor: float | None
    vor_rank: int | None
    adp: float | None
    adp_delta: float | None
    tier: int | None
    mean_projection: float | None
    sim_mean: float | None
    sim_p10: float | None
    sim_p90: float | None
    sim_boom_prob: float | None
    sim_bust_prob: float | None
    avail_mean: float | None
    efficiency_factor: float = 0.0
    blended_score: float = 0.0


class TierPlayerOut(BaseModel):
    gsis_id: str
    name: str
    team: str | None
    vor: float | None
    vor_rank: int | None
    adp: float | None
    sim_mean: float | None


class TierOut(BaseModel):
    tier: int
    position: str
    players: list[TierPlayerOut]


class ScarcityPositionOut(BaseModel):
    position: str
    total_players: int
    top_tier_count: int
    vor_dropoff: float | None


# ── Draft ─────────────────────────────────────────────────────────────────────

class LeagueSettingsSchema(BaseModel):
    teams: int = 12
    scoring: str = 'ppr'
    roster_config: dict[str, int] = Field(
        default_factory=lambda: {'QB': 1, 'RB': 2, 'WR': 2, 'TE': 1, 'FLEX': 1}
    )


class DraftStateIn(BaseModel):
    season: int = 2026
    model_version: str = 'neural-v1'
    league_settings: LeagueSettingsSchema = Field(default_factory=LeagueSettingsSchema)
    current_pick: int = 1
    total_picks: int = 180
    user_pick_position: int = 1
    drafted_ids: list[str] = Field(default_factory=list)
    user_roster: dict[str, list[str]] = Field(
        default_factory=lambda: {'QB': [], 'RB': [], 'WR': [], 'TE': [], 'FLEX': []}
    )


class SessionIn(BaseModel):
    session_id: str
    state: DraftStateIn


class SessionOut(BaseModel):
    session_id: str
    league_settings: dict | None
    picks: list[str] | None
    completed: bool
