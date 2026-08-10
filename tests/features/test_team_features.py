import pytest
from tay.db import get_conn, init_schema
from tay.features.team_features import build_team_features

@pytest.fixture
def conn(tmp_path):
    c = get_conn(tmp_path / "test.duckdb")
    init_schema(c)
    # Season 2023 team stats
    c.execute("""
        INSERT INTO team_season_stats
            (team, season, games, total_plays, pass_attempts, rush_attempts,
             pass_rate, total_tds, pass_tds, rush_tds,
             team_epa, pass_epa, rush_epa)
        VALUES ('KC', 2023, 17, 1100, 600, 500, 0.545, 60, 40, 20, 0.12, 0.25, -0.05)
    """)
    yield c
    c.close()

def test_build_team_features_creates_row(conn):
    build_team_features(conn, target_seasons=[2024])
    row = conn.execute(
        "SELECT team, season, pass_rate, total_plays FROM team_features WHERE team='KC' AND season=2024"
    ).fetchone()
    assert row is not None
    assert row[0] == 'KC'
    assert row[1] == 2024
    assert abs(row[2] - 0.545) < 0.01   # prior year's pass rate

def test_first_season_gets_nulls(conn):
    build_team_features(conn, target_seasons=[2005])
    # No prior data for 2005 → either no row or a row with NULL features
    # We choose: insert a row with NULLs so the model can still reference the team
    row = conn.execute(
        "SELECT pass_rate FROM team_features WHERE season=2005"
    ).fetchone()
    # Either no row (skip) or NULL — both are acceptable
    assert row is None or row[0] is None
