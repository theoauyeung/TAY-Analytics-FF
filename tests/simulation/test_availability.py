import duckdb
import pytest
from tay.db import init_schema
from tay.simulation.availability import compute_availability, POSITION_PRIORS


def _conn_with_player(gsis_id: str, position: str, games_by_season: dict[int, int]) -> duckdb.DuckDBPyConnection:
    conn = duckdb.connect(':memory:')
    init_schema(conn)
    conn.execute(f"INSERT INTO players (gsis_id, position, name) VALUES ('{gsis_id}', '{position}', 'Test Player')")
    # Insert a projection row so compute_availability knows this player exists
    conn.execute("""
        INSERT INTO projections (gsis_id, season, model_version, mean_projection, std_dev)
        VALUES (?, 2026, 'neural-v1', 200.0, 50.0)
    """, [gsis_id])
    for season, games in games_by_season.items():
        conn.execute("""
            INSERT INTO player_season_stats (gsis_id, season, games, fantasy_points_ppr, team)
            VALUES (?, ?, ?, 100.0, 'KC')
        """, [gsis_id, season, games])
    conn.commit()
    return conn


def test_returns_dict_keyed_by_gsis_id():
    conn = _conn_with_player('P001', 'RB', {2023: 14, 2024: 16, 2025: 12})
    result = compute_availability(conn, 2026, 'neural-v1')
    assert 'P001' in result
    mean, std = result['P001']
    assert isinstance(mean, float)
    assert isinstance(std, float)
    assert 0.0 <= mean <= 17.0
    assert std >= 0.0
    conn.close()


def test_falls_back_to_position_prior_with_no_history():
    conn = _conn_with_player('P002', 'WR', {})  # no prior season stats
    result = compute_availability(conn, 2026, 'neural-v1')
    mean, std = result['P002']
    prior_mean, prior_std = POSITION_PRIORS['WR']
    assert abs(mean - prior_mean) < 0.01, f"Expected prior mean {prior_mean}, got {mean}"
    assert abs(std - prior_std) < 0.01, f"Expected prior std {prior_std}, got {std}"
    conn.close()


def test_shrinks_toward_prior_with_one_season():
    """One season: weight=1/3, so blended_mean = 1/3*player + 2/3*prior."""
    conn = _conn_with_player('P003', 'QB', {2025: 17})  # 17 games in 2025
    result = compute_availability(conn, 2026, 'neural-v1')
    mean, std = result['P003']
    prior_mean, prior_std = POSITION_PRIORS['QB']
    expected_mean = (1/3) * 17.0 + (2/3) * prior_mean
    assert abs(mean - expected_mean) < 0.1, f"Expected ~{expected_mean:.1f}, got {mean:.1f}"
    conn.close()


def test_normalizes_pre_2021_games_to_17_game_scale():
    """2020 was a 16-game season; 16 games should normalize to 17."""
    conn = _conn_with_player('P004', 'RB', {2020: 16})  # 16-game season
    result = compute_availability(conn, 2026, 'neural-v1')
    mean, _ = result['P004']
    prior_mean, _ = POSITION_PRIORS['RB']
    # player games_17 = 16 * (17/16) = 17.0; weight = 1/3
    expected_mean = (1/3) * 17.0 + (2/3) * prior_mean
    assert abs(mean - expected_mean) < 0.1
    conn.close()
