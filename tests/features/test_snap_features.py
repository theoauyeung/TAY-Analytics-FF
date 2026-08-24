"""Tests for snap count feature computation."""
import pytest
from tay.db import get_conn, init_schema


def test_snap_counts_table_created(tmp_path):
    conn = get_conn(tmp_path / 'test.duckdb')
    init_schema(conn)
    tables = {r[0] for r in conn.execute('SHOW TABLES').fetchall()}
    assert 'snap_counts' in tables
    conn.close()


def test_insert_snap_counts(tmp_path):
    """ingest_snap_season writes one row per player with correct snap_share."""
    import sys, os
    sys.path.insert(0, str(tmp_path.parent.parent / 'src'))
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
