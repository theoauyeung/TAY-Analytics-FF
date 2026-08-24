import numpy as np
import torch
import duckdb
import pytest
from tay.models.dataset import load_position_data, PositionDataset


def _make_conn():
    """In-memory DuckDB with minimal player_features rows."""
    conn = duckdb.connect(':memory:')
    conn.execute("""
        CREATE TABLE player_features (
            gsis_id VARCHAR, season INTEGER, position VARCHAR,
            age DOUBLE, experience INTEGER, is_rookie INTEGER,
            prev_games INTEGER,
            prev_carries INTEGER, prev_rush_yards DOUBLE, prev_rush_tds INTEGER,
            prev_targets INTEGER, prev_receptions INTEGER, prev_rec_yards DOUBLE,
            prev_rec_tds INTEGER, prev_air_yards DOUBLE, prev_yac DOUBLE,
            prev_fantasy_ppr DOUBLE, prev_epa_per_play DOUBLE,
            prev_attempts INTEGER, prev_completions INTEGER, prev_pass_yards DOUBLE,
            prev_pass_tds INTEGER, prev_interceptions INTEGER,
            prev_rush_yards_qb DOUBLE, prev_rush_tds_qb INTEGER,
            prev_cpoe DOUBLE,
            pass_completion_pct DOUBLE, pass_yards_per_attempt DOUBLE,
            carries_per_game DOUBLE, rush_yards_per_game DOUBLE, yards_per_carry DOUBLE,
            catch_rate DOUBLE, td_rate_rushing DOUBLE, td_rate_receiving DOUBLE,
            targets_per_game DOUBLE, rec_yards_per_game DOUBLE,
            yards_per_target DOUBLE, air_yards_per_target DOUBLE, yac_per_reception DOUBLE,
            roll2_fantasy_ppr DOUBLE, roll2_targets DOUBLE, roll2_carries DOUBLE,
            lag2_fantasy_ppr DOUBLE, lag2_targets DOUBLE, lag2_carries DOUBLE,
            lag2_pass_yards DOUBLE,
            lag3_fantasy_ppr DOUBLE, lag3_targets DOUBLE, lag3_carries DOUBLE,
            lag3_pass_yards DOUBLE,
            ewma_fantasy_ppr DOUBLE, ewma_targets DOUBLE, ewma_carries DOUBLE,
            ewma_pass_yards DOUBLE,
            team_pass_rate DOUBLE, team_pass_epa DOUBLE, team_total_plays INTEGER,
            incoming_vacated_targets DOUBLE, incoming_vacated_carries DOUBLE,
            depth_chart_pos INTEGER, draft_pick_value DOUBLE,
            target_share DOUBLE,
            air_yards_share DOUBLE,
            wopr DOUBLE,
            weekly_fpts_std DOUBLE,
            boom_rate DOUBLE,
            floor_rate DOUBLE,
            sos_pts_allowed DOUBLE,
            snap_share DOUBLE,
            snap_share_trend DOUBLE,
            next_season_fantasy_ppr DOUBLE
        )
    """)
    # 5 train rows + 2 val rows, all RB
    for i in range(7):
        season = 2018 + i   # 2018-2022 train, 2023-2024 val
        conn.execute("""
            INSERT INTO player_features
            (gsis_id, season, position, age, experience, is_rookie,
             prev_games, prev_carries, prev_rush_yards, prev_rush_tds,
             prev_targets, prev_receptions, prev_rec_yards,
             prev_rec_tds, prev_air_yards, prev_yac,
             prev_fantasy_ppr, prev_epa_per_play,
             prev_attempts, prev_completions, prev_pass_yards, prev_pass_tds,
             prev_interceptions, prev_cpoe,
             pass_completion_pct, pass_yards_per_attempt,
             carries_per_game, rush_yards_per_game, yards_per_carry,
             catch_rate, td_rate_rushing, td_rate_receiving,
             targets_per_game, rec_yards_per_game,
             yards_per_target, air_yards_per_target, yac_per_reception,
             roll2_fantasy_ppr, roll2_targets, roll2_carries,
             team_pass_rate, team_pass_epa, team_total_plays,
             incoming_vacated_targets, incoming_vacated_carries,
             depth_chart_pos, draft_pick_value,
             next_season_fantasy_ppr)
            VALUES (?, ?, 'RB', 25.0+?, ?, 0,
                    16, 200+?, 800.0+?, 8,
                    40, 30, 250.0,
                    2, 300.0, 180.0,
                    200.0+?, 0.05,
                    0, 0, 0.0, 0, 0, 0.0,
                    0.0, 0.0,
                    12.5, 50.0, 4.0,
                    0.75, 0.05, 0.02,
                    2.5, 15.6,
                    6.25, 7.5, 6.0,
                    210.0+?, 45.0, 200.0+?,
                    0.55, 0.12, 950,
                    20.0, 15.0,
                    1, 0.08,
                    220.0+?)
        """, [f'rb{i:03d}', season, i, i, i, i, i, i, i, i])
    return conn


def test_returns_position_dataset():
    conn = _make_conn()
    ds = load_position_data(conn, 'RB', train_end=2022, val_start=2023, val_end=2024)
    assert isinstance(ds, PositionDataset)
    conn.close()


def test_train_val_shapes():
    conn = _make_conn()
    ds = load_position_data(conn, 'RB', train_end=2022, val_start=2023, val_end=2024)
    # 5 train rows (2018-2022), 2 val rows (2023-2024)
    assert ds.X_train.shape[0] == 5
    assert ds.X_val.shape[0] == 2
    assert ds.X_train.shape[1] == ds.X_val.shape[1]
    assert ds.y_train.shape == (5,)
    assert ds.y_val.shape == (2,)
    conn.close()


def test_tensors_are_float32():
    conn = _make_conn()
    ds = load_position_data(conn, 'RB', train_end=2022, val_start=2023, val_end=2024)
    assert ds.X_train.dtype == torch.float32
    assert ds.y_train.dtype == torch.float32
    conn.close()


def test_train_features_normalized():
    conn = _make_conn()
    ds = load_position_data(conn, 'RB', train_end=2022, val_start=2023, val_end=2024)
    # After z-score normalization, train mean ≈ 0
    import torch
    means = ds.X_train.mean(dim=0)
    assert torch.all(means.abs() < 1e-5), f'Train not zero-mean: max={means.abs().max()}'
    conn.close()


def test_null_features_filled_with_zero():
    conn = duckdb.connect(':memory:')
    conn.execute("""
        CREATE TABLE player_features (
            gsis_id VARCHAR, season INTEGER, position VARCHAR,
            age DOUBLE, experience INTEGER, is_rookie INTEGER,
            prev_games INTEGER,
            prev_carries INTEGER, prev_rush_yards DOUBLE, prev_rush_tds INTEGER,
            prev_targets INTEGER, prev_receptions INTEGER, prev_rec_yards DOUBLE,
            prev_rec_tds INTEGER, prev_air_yards DOUBLE, prev_yac DOUBLE,
            prev_fantasy_ppr DOUBLE, prev_epa_per_play DOUBLE,
            prev_attempts INTEGER, prev_completions INTEGER, prev_pass_yards DOUBLE,
            prev_pass_tds INTEGER, prev_interceptions INTEGER, prev_cpoe DOUBLE,
            pass_completion_pct DOUBLE, pass_yards_per_attempt DOUBLE,
            carries_per_game DOUBLE, rush_yards_per_game DOUBLE, yards_per_carry DOUBLE,
            catch_rate DOUBLE, td_rate_rushing DOUBLE, td_rate_receiving DOUBLE,
            targets_per_game DOUBLE, rec_yards_per_game DOUBLE,
            yards_per_target DOUBLE, air_yards_per_target DOUBLE, yac_per_reception DOUBLE,
            roll2_fantasy_ppr DOUBLE, roll2_targets DOUBLE, roll2_carries DOUBLE,
            lag2_fantasy_ppr DOUBLE, lag2_targets DOUBLE, lag2_carries DOUBLE,
            lag2_pass_yards DOUBLE,
            lag3_fantasy_ppr DOUBLE, lag3_targets DOUBLE, lag3_carries DOUBLE,
            lag3_pass_yards DOUBLE,
            ewma_fantasy_ppr DOUBLE, ewma_targets DOUBLE, ewma_carries DOUBLE,
            ewma_pass_yards DOUBLE,
            team_pass_rate DOUBLE, team_pass_epa DOUBLE, team_total_plays INTEGER,
            incoming_vacated_targets DOUBLE, incoming_vacated_carries DOUBLE,
            depth_chart_pos INTEGER, draft_pick_value DOUBLE,
            target_share DOUBLE,
            air_yards_share DOUBLE,
            wopr DOUBLE,
            weekly_fpts_std DOUBLE,
            boom_rate DOUBLE,
            floor_rate DOUBLE,
            sos_pts_allowed DOUBLE,
            snap_share DOUBLE,
            snap_share_trend DOUBLE,
            next_season_fantasy_ppr DOUBLE
        )
    """)
    # Row with NULLs in all feature cols except next_season_fantasy_ppr
    conn.execute("""
        INSERT INTO player_features (gsis_id, season, position, next_season_fantasy_ppr)
        VALUES ('x', 2020, 'RB', 100.0)
    """)
    ds = load_position_data(conn, 'RB', train_end=2022, val_start=2023, val_end=2024)
    # NULL features become 0 → after normalization, constant column stays 0
    assert not ds.X_train.isnan().any()
    conn.close()
