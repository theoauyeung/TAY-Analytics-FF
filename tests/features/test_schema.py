from tay.db import get_conn, init_schema

def test_feature_tables_created(tmp_path):
    conn = get_conn(tmp_path / "test.duckdb")
    init_schema(conn)
    tables = {r[0] for r in conn.execute("SHOW TABLES").fetchall()}
    assert "player_features" in tables
    assert "team_features" in tables
    conn.close()
