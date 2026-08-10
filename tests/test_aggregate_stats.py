import pytest
import duckdb
from tay.db import get_conn, init_schema
from tay.ingestion.aggregate_stats import aggregate_player_stats, aggregate_team_stats

@pytest.fixture
def conn_with_pbp(tmp_path):
    conn = get_conn(tmp_path / "test.duckdb")
    init_schema(conn)
    # Insert minimal PBP rows
    conn.execute("""
        INSERT INTO play_by_play
            (play_id, game_id, season, week, season_type, posteam, defteam,
             play_type, yards_gained, passer_id, rusher_id, receiver_id,
             air_yards, yards_after_catch, pass_attempt, rush_attempt,
             complete_pass, touchdown, interception, fumble, epa, cpoe, wpa)
        VALUES
            ('p1', 'g1', 2024, 1, 'REG', 'KC', 'LV', 'pass', 15.0,
             'player-1', NULL, 'player-2', 10.0, 5.0,
             1, 0, 1, 1, 0, 0, 0.8, 5.0, 0.1),
            ('p2', 'g1', 2024, 1, 'REG', 'KC', 'LV', 'run', 5.0,
             NULL, 'player-3', NULL, NULL, NULL,
             0, 1, 0, 0, 0, 0, 0.2, NULL, 0.05)
    """)
    yield conn
    conn.close()

def test_aggregate_player_stats(conn_with_pbp):
    aggregate_player_stats(conn_with_pbp, seasons=[2024])
    rows = conn_with_pbp.execute(
        "SELECT gsis_id, season FROM player_season_stats WHERE season=2024"
    ).fetchall()
    gsis_ids = {r[0] for r in rows}
    assert 'player-1' in gsis_ids  # passer
    assert 'player-3' in gsis_ids  # rusher

def test_aggregate_team_stats(conn_with_pbp):
    aggregate_team_stats(conn_with_pbp, seasons=[2024])
    row = conn_with_pbp.execute(
        "SELECT total_plays FROM team_season_stats WHERE team='KC' AND season=2024"
    ).fetchone()
    assert row is not None
    assert row[0] == 2
