import pytest
from pathlib import Path

FIXTURES = Path(__file__).parent / 'fixtures'


def _read(fname):
    return (FIXTURES / fname).read_text()


def test_scrape_qb_player_count():
    from scripts.ingest.ingest_fantasypros import scrape_position
    rows = scrape_position(_read('fp_qb.html'), 'QB')
    assert len(rows) == 2


def test_scrape_qb_mahomes_name():
    from scripts.ingest.ingest_fantasypros import scrape_position
    rows = scrape_position(_read('fp_qb.html'), 'QB')
    assert rows[0]['name'] == 'Patrick Mahomes'


def test_scrape_qb_mahomes_ppr_points():
    from scripts.ingest.ingest_fantasypros import scrape_position
    rows = scrape_position(_read('fp_qb.html'), 'QB')
    mahomes = rows[0]
    # pass_yds=4900×0.04=196 + pass_tds=37×4=148 + ints=11×(−2)=−22
    # + rush_yds=305×0.1=30.5 + rush_tds=4×6=24 = 376.5
    assert mahomes['points'] == pytest.approx(376.5)


def test_scrape_qb_lamar_ppr_points():
    from scripts.ingest.ingest_fantasypros import scrape_position
    rows = scrape_position(_read('fp_qb.html'), 'QB')
    lamar = rows[1]
    # 3600×0.04=144 + 26×4=104 + 7×(−2)=−14 + 920×0.1=92 + 5×6=30 = 356
    assert lamar['points'] == pytest.approx(356.0)


def test_scrape_wr_chase_ppr_points():
    from scripts.ingest.ingest_fantasypros import scrape_position
    rows = scrape_position(_read('fp_wr.html'), 'WR')
    chase = rows[0]
    # rec=95×1=95 + rec_yds=1400×0.1=140 + rec_tds=11×6=66
    # + rush_yds=30×0.1=3 + rush_tds=0×6=0 = 304
    assert chase['points'] == pytest.approx(304.0)


def test_scrape_wr_etienne_name_preserved():
    from scripts.ingest.ingest_fantasypros import scrape_position
    rows = scrape_position(_read('fp_wr.html'), 'WR')
    assert rows[1]['name'] == "Travis Etienne Jr."
