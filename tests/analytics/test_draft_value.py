"""Tests for draft value analytics."""
import pytest
from tay.db import get_conn, init_schema


def test_analytics_tables_created(tmp_path):
    conn = get_conn(tmp_path / 'test.duckdb')
    init_schema(conn)
    tables = {r[0] for r in conn.execute('SHOW TABLES').fetchall()}
    assert 'player_analytics' in tables
    conn.close()


@pytest.fixture
def analytics_conn(tmp_path):
    conn = get_conn(tmp_path / 'analytics.duckdb')
    init_schema(conn)
    # 3 players in bucket '1-5': projections 300, 250, 200 (mean=250, std≈50)
    conn.execute("""
        INSERT INTO players (gsis_id, name, position) VALUES
            ('p1', 'Player One', 'RB'),
            ('p2', 'Player Two', 'WR'),
            ('p3', 'Player Three', 'RB')
    """)
    conn.execute("""
        INSERT INTO adp (gsis_id, season, platform, format, adp, rank)
        VALUES ('p1', 2026, 'espn', 'ppr', 1.0, 1),
               ('p2', 2026, 'espn', 'ppr', 3.0, 3),
               ('p3', 2026, 'espn', 'ppr', 5.0, 5)
    """)
    conn.execute("""
        INSERT INTO projections (gsis_id, season, model_version, mean_projection, vor_rank)
        VALUES ('p1', 2026, 'neural-v1', 300.0, 1),
               ('p2', 2026, 'neural-v1', 250.0, 2),
               ('p3', 2026, 'neural-v1', 200.0, 3)
    """)
    yield conn
    conn.close()


def test_efficiency_factor_positive_for_overperformer(analytics_conn):
    from tay.analytics.draft_value import compute_draft_value
    compute_draft_value(analytics_conn, season=2026, model_version='neural-v1')
    row = analytics_conn.execute(
        "SELECT efficiency_factor FROM player_analytics WHERE gsis_id = 'p1' AND season = 2026"
    ).fetchone()
    assert row is not None
    assert row[0] > 0  # p1 projects 300, bucket mean 250 → positive z-score


def test_efficiency_factor_negative_for_underperformer(analytics_conn):
    from tay.analytics.draft_value import compute_draft_value
    compute_draft_value(analytics_conn, season=2026, model_version='neural-v1')
    row = analytics_conn.execute(
        "SELECT efficiency_factor FROM player_analytics WHERE gsis_id = 'p3' AND season = 2026"
    ).fetchone()
    assert row is not None
    assert row[0] < 0  # p3 projects 200, bucket mean 250 → negative z-score


def test_adp_bucket_assigned(analytics_conn):
    from tay.analytics.draft_value import _adp_bucket
    assert _adp_bucket(3)   == '1-5'
    assert _adp_bucket(10)  == '6-12'
    assert _adp_bucket(20)  == '13-24'
    assert _adp_bucket(120) == '109+'


def test_blended_score_with_analytics(tmp_path):
    from tay.api.routers.rankings import _blended_score
    # Player with analytics_rank=50 (historically overdrafted) should rank worse
    score_with    = _blended_score(vor_rank=10, adp=10.0, analytics_rank=50)
    score_without = _blended_score(vor_rank=10, adp=10.0, analytics_rank=None)
    assert score_with > score_without


def test_blended_score_neutral_when_no_analytics(tmp_path):
    from tay.api.routers.rankings import _blended_score
    score = _blended_score(vor_rank=5, adp=5.0, analytics_rank=None)
    # When analytics_rank=None, ar = vr = 5; blend = 0.65*5 + 0.25*5 + 0.10*5 = 5.0
    assert abs(score - 5.0) < 0.01
