import duckdb
import pytest
from tay.db import init_schema


def _make_conn_with_team_data():
    conn = duckdb.connect(':memory:')
    init_schema(conn)
    # Seed team_features and team_season_stats for 3 teams × 2 seasons
    for team, pass_rate, pass_epa in [('KC', 0.65, 0.18), ('BAL', 0.45, 0.05), ('SF', 0.50, 0.10)]:
        for season in [2022, 2023]:
            conn.execute("""
                INSERT OR REPLACE INTO team_features
                    (team, season, pass_rate, rush_rate, team_epa, pass_epa, rush_epa, total_plays, pass_attempts, total_tds)
                VALUES (?, ?, ?, ?, 0.08, ?, 0.02, 1000, 550, 45)
            """, [team, season, pass_rate, 1 - pass_rate, pass_epa])
    return conn


def test_cluster_ids_are_integers():
    from scripts.compute_scheme_clusters import compute_and_store_clusters
    conn = _make_conn_with_team_data()
    compute_and_store_clusters(conn, seasons=[2022, 2023], n_clusters=2)
    rows = conn.execute("SELECT cluster_id FROM scheme_clusters").fetchall()
    assert len(rows) == 6  # 3 teams × 2 seasons
    for (cid,) in rows:
        assert isinstance(cid, int)
    conn.close()


def test_cluster_ids_in_range():
    from scripts.compute_scheme_clusters import compute_and_store_clusters
    conn = _make_conn_with_team_data()
    compute_and_store_clusters(conn, seasons=[2022, 2023], n_clusters=3)
    rows = conn.execute("SELECT DISTINCT cluster_id FROM scheme_clusters").fetchall()
    ids = {r[0] for r in rows}
    assert ids.issubset({0, 1, 2})
    conn.close()


def test_cluster_idempotent():
    from scripts.compute_scheme_clusters import compute_and_store_clusters
    conn = _make_conn_with_team_data()
    compute_and_store_clusters(conn, seasons=[2022], n_clusters=2)
    compute_and_store_clusters(conn, seasons=[2022], n_clusters=2)
    count = conn.execute("SELECT COUNT(*) FROM scheme_clusters WHERE season = 2022").fetchone()[0]
    assert count == 3  # 3 teams, not 6
    conn.close()
