import json
import pytest
from pathlib import Path

FIXTURES = Path(__file__).parent / 'fixtures'


def _load():
    return json.loads((FIXTURES / 'espn_players.json').read_text())


def test_parse_espn_returns_two_players_with_stats():
    from scripts.ingest_espn_projections import parse_espn_response
    rows = parse_espn_response(_load())
    # 3rd player has no statSourceId=1 entry, should be excluded
    assert len(rows) == 2


def test_parse_espn_mahomes_espn_id():
    from scripts.ingest_espn_projections import parse_espn_response
    rows = parse_espn_response(_load())
    mahomes = next(r for r in rows if r['espn_id'] == '3054211')
    assert mahomes is not None


def test_parse_espn_mahomes_points():
    from scripts.ingest_espn_projections import parse_espn_response
    rows = parse_espn_response(_load())
    mahomes = next(r for r in rows if r['espn_id'] == '3054211')
    # 4800×0.04=192 + 36×4=144 + 10×(−2)=−20 + 280×0.1=28 + 3×6=18 = 362
    assert mahomes['points'] == pytest.approx(362.0)


def test_parse_espn_chase_points():
    from scripts.ingest_espn_projections import parse_espn_response
    rows = parse_espn_response(_load())
    chase = next(r for r in rows if r['espn_id'] == '3916387')
    # rec=90×1=90 + rec_yds=1350×0.1=135 + rec_tds=10×6=60
    # + rush_yds=25×0.1=2.5 = 287.5
    assert chase['points'] == pytest.approx(287.5)


def test_parse_espn_excludes_non_projected_stats():
    from scripts.ingest_espn_projections import parse_espn_response
    rows = parse_espn_response(_load())
    espn_ids = [r['espn_id'] for r in rows]
    assert '9999999' not in espn_ids
