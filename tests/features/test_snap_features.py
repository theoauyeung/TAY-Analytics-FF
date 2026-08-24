"""Tests for snap count feature computation."""
import pytest
from tay.db import get_conn, init_schema


@pytest.fixture
def snap_conn(tmp_path):
    from tay.db import get_conn, init_schema
    c = get_conn(tmp_path / 'snap_feat.duckdb')
    init_schema(c)
    # Player p1: snap_share 0.80 in 2024 (N-1), 0.70 in 2023 (N-2)
    c.execute("""
        INSERT INTO snap_counts (gsis_id, season, snap_share, total_snaps, games_played)
        VALUES ('p1', 2024, 0.80, 1000, 16),
               ('p1', 2023, 0.70, 950,  16)
    """)
    # player_features row for 2025 (predicts from 2024)
    c.execute("""
        INSERT INTO player_features (gsis_id, season, position)
        VALUES ('p1', 2025, 'WR')
    """)
    yield c
    c.close()


def test_snap_share_written(snap_conn):
    from tay.features.snap_features import _migrate_snap_features, compute_snap_features
    _migrate_snap_features(snap_conn)
    compute_snap_features(snap_conn, [2025])
    row = snap_conn.execute(
        "SELECT snap_share FROM player_features WHERE gsis_id = 'p1' AND season = 2025"
    ).fetchone()
    assert row is not None
    assert abs(row[0] - 0.80) < 0.001


def test_snap_share_trend(snap_conn):
    from tay.features.snap_features import _migrate_snap_features, compute_snap_features
    _migrate_snap_features(snap_conn)
    compute_snap_features(snap_conn, [2025])
    row = snap_conn.execute(
        "SELECT snap_share_trend FROM player_features WHERE gsis_id = 'p1' AND season = 2025"
    ).fetchone()
    # trend = snap_share(N-1) - snap_share(N-2) = 0.80 - 0.70 = 0.10
    assert row is not None
    assert abs(row[0] - 0.10) < 0.001


def test_snap_share_null_when_missing(tmp_path):
    """Players with no snap_counts row get NULL snap_share (not 0)."""
    from tay.db import get_conn, init_schema
    from tay.features.snap_features import _migrate_snap_features, compute_snap_features
    c = get_conn(tmp_path / 'null_snap.duckdb')
    init_schema(c)
    c.execute("INSERT INTO player_features (gsis_id, season, position) VALUES ('p_new', 2025, 'RB')")
    _migrate_snap_features(c)
    compute_snap_features(c, [2025])
    row = c.execute(
        "SELECT snap_share FROM player_features WHERE gsis_id = 'p_new' AND season = 2025"
    ).fetchone()
    assert row[0] is None
    c.close()


def test_snap_counts_table_created(tmp_path):
    conn = get_conn(tmp_path / 'test.duckdb')
    init_schema(conn)
    tables = {r[0] for r in conn.execute('SHOW TABLES').fetchall()}
    assert 'snap_counts' in tables
    conn.close()


def test_insert_snap_counts(tmp_path):
    """ingest_snap_season writes one row per player with correct snap_share."""
    from tay.db import get_conn, init_schema
    from scripts.ingest_snaps import ingest_snap_season

    conn = get_conn(tmp_path / 'test.duckdb')
    init_schema(conn)

    # Fake weekly rows: player p1, 3 weeks, offense_pct 0.8 / 0.9 / 0.7
    weekly_rows = [
        {'player_id': 'p1', 'season': 2024, 'week': 1, 'offense_snaps': 60, 'offense_pct': 0.80},
        {'player_id': 'p1', 'season': 2024, 'week': 2, 'offense_snaps': 65, 'offense_pct': 0.90},
        {'player_id': 'p1', 'season': 2024, 'week': 3, 'offense_snaps': 55, 'offense_pct': 0.70},
    ]
    ingest_snap_season(conn, weekly_rows, season=2024)

    row = conn.execute(
        "SELECT snap_share, total_snaps, games_played FROM snap_counts WHERE gsis_id = 'p1' AND season = 2024"
    ).fetchone()
    assert row is not None
    assert abs(row[0] - (0.8 + 0.9 + 0.7) / 3) < 0.01  # avg offense_pct
    assert row[1] == 180   # 60 + 65 + 55
    assert row[2] == 3
    conn.close()
