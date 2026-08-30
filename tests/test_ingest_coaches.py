import duckdb
import pytest
from tay.db import init_schema


def _make_conn():
    conn = duckdb.connect(':memory:')
    init_schema(conn)
    return conn


def test_upsert_coaches_rows():
    from scripts.ingest.ingest_coaches import upsert_coaches
    conn = _make_conn()
    raw = [
        {'team': 'KC', 'season': 2023, 'coach_type': 'offensive_coordinator', 'full_name': 'Matt Nagy'},
        {'team': 'KC', 'season': 2023, 'coach_type': 'head_coach', 'full_name': 'Andy Reid'},
    ]
    upsert_coaches(conn, raw)
    count = conn.execute("SELECT COUNT(*) FROM coaches").fetchone()[0]
    assert count == 2
    conn.close()


def test_upsert_coaches_idempotent():
    from scripts.ingest.ingest_coaches import upsert_coaches
    conn = _make_conn()
    raw = [{'team': 'KC', 'season': 2023, 'coach_type': 'head_coach', 'full_name': 'Andy Reid'}]
    upsert_coaches(conn, raw)
    upsert_coaches(conn, raw)
    count = conn.execute("SELECT COUNT(*) FROM coaches").fetchone()[0]
    assert count == 1
    conn.close()


def test_compute_oc_features_no_history():
    from scripts.ingest.ingest_coaches import compute_oc_features
    conn = _make_conn()
    # OC appearing for the first time (no prior seasons in coaches table) → is_rookie_oc = True
    conn.execute("INSERT INTO coaches VALUES ('DAL', 2024, 'offensive_coordinator', 'New Guy')")
    compute_oc_features(conn, seasons=[2024])
    row = conn.execute(
        "SELECT is_rookie_oc FROM oc_features WHERE oc_name = 'New Guy' AND as_of_season = 2024"
    ).fetchone()
    assert row is not None
    assert row[0] is True
    conn.close()


def test_compute_oc_features_with_history():
    from scripts.ingest.ingest_coaches import compute_oc_features
    conn = _make_conn()
    # Seed coaches + player stats to exercise the aggregation path
    conn.execute("INSERT INTO coaches VALUES ('KC', 2022, 'offensive_coordinator', 'Eric Bieniemy')")
    conn.execute("INSERT INTO coaches VALUES ('KC', 2023, 'offensive_coordinator', 'Eric Bieniemy')")
    # Player stats: WR1 with 120 targets out of 600 team attempts = 0.20 share
    conn.execute("INSERT INTO players (gsis_id, name, position, team, birth_date, draft_year, draft_round, draft_pick, college, height, weight, sleeper_id, espn_id, pfr_id, yahoo_id) VALUES ('p1', 'Tyreek Hill', 'WR', 'KC', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL)")
    conn.execute("""
        INSERT INTO player_season_stats
            (gsis_id, season, team, games, targets, attempts, air_yards)
        VALUES ('p1', 2022, 'KC', 17, 120, 0, 900)
    """)
    conn.execute("""
        INSERT INTO team_season_stats
            (team, season, games, pass_attempts)
        VALUES ('KC', 2022, 17, 600)
    """)
    compute_oc_features(conn, seasons=[2023])
    row = conn.execute(
        "SELECT hist_wr1_target_share, is_rookie_oc FROM oc_features WHERE oc_name = 'Eric Bieniemy' AND as_of_season = 2023"
    ).fetchone()
    assert row is not None
    assert row[0] == pytest.approx(0.20, abs=0.01)
    assert row[1] is False
    conn.close()
