"""Position-specific feature column lists for the projection models."""
from __future__ import annotations

QB_FEATURES: list[str] = [
    'age', 'experience', 'is_rookie',
    'prev_games',
    'prev_attempts', 'prev_completions', 'prev_pass_yards',
    'prev_pass_tds', 'prev_interceptions',
    'prev_rush_yards', 'prev_rush_tds',
    'prev_fantasy_ppr', 'prev_epa_per_play', 'prev_cpoe',
    'pass_completion_pct', 'pass_yards_per_attempt',
    'roll2_fantasy_ppr',
    'lag2_fantasy_ppr', 'lag3_fantasy_ppr',
    'ewma_fantasy_ppr', 'ewma_pass_yards',
    'team_pass_rate', 'team_pass_epa', 'team_total_plays',
    'draft_pick_value',
]

RB_FEATURES: list[str] = [
    'age', 'experience', 'is_rookie',
    'prev_games',
    'prev_carries', 'prev_rush_yards', 'prev_rush_tds',
    'prev_targets', 'prev_receptions', 'prev_rec_yards',
    'prev_fantasy_ppr', 'prev_epa_per_play',
    'carries_per_game', 'rush_yards_per_game', 'yards_per_carry',
    'catch_rate', 'td_rate_rushing',
    'roll2_fantasy_ppr', 'roll2_carries',
    'lag2_fantasy_ppr', 'lag2_carries',
    'lag3_fantasy_ppr', 'lag3_carries',
    'ewma_fantasy_ppr', 'ewma_carries',
    'team_pass_rate', 'team_total_plays',
    'incoming_vacated_carries',
    'depth_chart_pos', 'draft_pick_value',
]

WR_FEATURES: list[str] = [
    'age', 'experience', 'is_rookie',
    'prev_games',
    'prev_targets', 'prev_receptions', 'prev_rec_yards', 'prev_rec_tds',
    'prev_air_yards', 'prev_yac',
    'prev_fantasy_ppr', 'prev_epa_per_play',
    'targets_per_game', 'rec_yards_per_game', 'catch_rate',
    'yards_per_target', 'air_yards_per_target', 'yac_per_reception',
    'td_rate_receiving',
    'roll2_fantasy_ppr', 'roll2_targets',
    'lag2_fantasy_ppr', 'lag2_targets',
    'lag3_fantasy_ppr', 'lag3_targets',
    'ewma_fantasy_ppr', 'ewma_targets',
    'team_pass_rate', 'team_pass_epa', 'team_total_plays',
    'incoming_vacated_targets',
    'depth_chart_pos', 'draft_pick_value',
]

TE_FEATURES: list[str] = [
    'age', 'experience', 'is_rookie',
    'prev_games',
    'prev_targets', 'prev_receptions', 'prev_rec_yards', 'prev_rec_tds',
    'prev_air_yards', 'prev_yac',
    'prev_fantasy_ppr', 'prev_epa_per_play',
    'targets_per_game', 'rec_yards_per_game', 'catch_rate',
    'yards_per_target', 'td_rate_receiving',
    'roll2_fantasy_ppr', 'roll2_targets',
    'lag2_fantasy_ppr', 'lag2_targets',
    'lag3_fantasy_ppr', 'lag3_targets',
    'ewma_fantasy_ppr', 'ewma_targets',
    'team_pass_rate', 'team_pass_epa', 'team_total_plays',
    'incoming_vacated_targets',
    'depth_chart_pos', 'draft_pick_value',
]

POSITION_FEATURES: dict[str, list[str]] = {
    'QB': QB_FEATURES,
    'RB': RB_FEATURES,
    'WR': WR_FEATURES,
    'TE': TE_FEATURES,
}
