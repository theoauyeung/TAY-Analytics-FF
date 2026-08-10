import pytest
from tay.db import get_conn, init_schema
from tay.features.vacated_opportunity import compute_vacated_opportunity, get_vacated_opportunity

@pytest.fixture
def conn(tmp_path):
    c = get_conn(tmp_path / "test.duckdb")
    init_schema(c)

    # Insert players so position JOIN works
    c.execute("""
        INSERT INTO players (gsis_id, name, position)
        VALUES ('player-a', 'Player A', 'WR'), ('player-b', 'Player B', 'WR')
    """)

    # Player A: was on KC in 2023 (100 targets), left for SF in 2024
    c.execute("""
        INSERT INTO player_season_stats (gsis_id, season, team, targets, carries, rec_yards, fantasy_points_ppr)
        VALUES ('player-a', 2023, 'KC', 100, 0, 1000.0, 200.0)
    """)
    # Player B: stayed on KC (80 targets in 2023)
    c.execute("""
        INSERT INTO player_season_stats (gsis_id, season, team, targets, carries, rec_yards, fantasy_points_ppr)
        VALUES ('player-b', 2023, 'KC', 80, 0, 800.0, 160.0)
    """)
    # Rosters: Player A is on SF in 2024 week 1, Player B is on KC
    c.execute("""
        INSERT INTO rosters (gsis_id, season, week, team, position)
        VALUES ('player-a', 2024, 1, 'SF', 'WR'), ('player-b', 2024, 1, 'KC', 'WR')
    """)
    yield c
    c.close()

def test_vacated_targets_for_departed_player(conn):
    compute_vacated_opportunity(conn, target_seasons=[2024])
    row = conn.execute(
        "SELECT vacated_wr_targets FROM team_features WHERE team='KC' AND season=2024"
    ).fetchone()
    assert row is not None
    assert row[0] == 100.0   # player-a's 2023 targets on KC

def test_staying_player_not_counted(conn):
    compute_vacated_opportunity(conn, target_seasons=[2024])
    row = conn.execute(
        "SELECT vacated_wr_targets FROM team_features WHERE team='KC' AND season=2024"
    ).fetchone()
    # player-b stayed → their 80 targets should NOT be in vacated
    assert row[0] == 100.0   # only player-a's 100
