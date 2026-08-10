import pytest
from tay.ingestion.player_ids import normalize_name, resolve_gsis_id
from tay.db import get_conn, init_schema

def test_normalize_name():
    assert normalize_name("Patrick Mahomes II") == "patrick mahomes"
    assert normalize_name("Travis Kelce Jr.") == "travis kelce"
    assert normalize_name("Tyreek Hill") == "tyreek hill"

@pytest.fixture
def conn(tmp_path):
    c = get_conn(tmp_path / "test.duckdb")
    init_schema(c)
    c.execute("""
        INSERT INTO players (gsis_id, name, position, team)
        VALUES ('00-0033873', 'Patrick Mahomes', 'QB', 'KC')
    """)
    yield c
    c.close()

def test_resolve_exact_match(conn):
    gsis = resolve_gsis_id("Patrick Mahomes", "QB", "KC", conn)
    assert gsis == "00-0033873"

def test_resolve_normalized_match(conn):
    gsis = resolve_gsis_id("Patrick Mahomes II", "QB", "KC", conn)
    assert gsis == "00-0033873"

def test_resolve_no_match(conn):
    gsis = resolve_gsis_id("Unknown Player", "WR", "SF", conn)
    assert gsis is None
