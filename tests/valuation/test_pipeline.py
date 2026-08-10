# tests/valuation/test_pipeline.py
"""Tests for the full valuation pipeline (run_valuation)."""
import duckdb
import pytest

from tay.db import init_schema
from tay.valuation.pipeline import run_valuation


def _make_conn():
    """Return an in-memory DuckDB connection with full schema and minimal seed data."""
    conn = duckdb.connect(':memory:')
    init_schema(conn)

    # Players: 2 QBs, 2 RBs, 2 WRs, 2 TEs
    players = [
        ('qb1', 'Starter QB', 'QB'),
        ('qb2', 'Backup QB',  'QB'),
        ('rb1', 'Lead RB',    'RB'),
        ('rb2', 'Backup RB',  'RB'),
        ('wr1', 'WR1',        'WR'),
        ('wr2', 'WR2',        'WR'),
        ('te1', 'TE1',        'TE'),
        ('te2', 'TE2',        'TE'),
    ]
    for gsis_id, name, pos in players:
        conn.execute(
            "INSERT INTO players (gsis_id, name, position) VALUES (?, ?, ?)",
            [gsis_id, name, pos],
        )

    # Projections: only mean_projection is required; pipeline fills vor/tier/adp_delta
    projections = [
        ('qb1', 400.0),
        ('qb2', 300.0),
        ('rb1', 250.0),
        ('rb2', 150.0),
        ('wr1', 220.0),
        ('wr2', 120.0),
        ('te1', 180.0),
        ('te2',  80.0),
    ]
    for gsis_id, pts in projections:
        conn.execute(
            "INSERT INTO projections (gsis_id, season, model_version, mean_projection)"
            " VALUES (?, 2026, 'v1', ?)",
            [gsis_id, pts],
        )

    # ADP for only some players (qb1 and rb1 have ADP; others do not)
    conn.execute(
        "INSERT INTO adp (gsis_id, season, platform, format, adp) VALUES (?, 2026, 'sleeper', 'ppr', ?)",
        ['qb1', 3.0],
    )
    conn.execute(
        "INSERT INTO adp (gsis_id, season, platform, format, adp) VALUES (?, 2026, 'sleeper', 'ppr', ?)",
        ['rb1', 1.0],
    )

    return conn


def test_run_valuation_returns_dict_with_expected_keys():
    """run_valuation should return a dict with the documented summary keys."""
    conn = _make_conn()
    result = run_valuation(conn, season=2026, model_version='v1')

    assert isinstance(result, dict), "run_valuation must return a dict"
    expected_keys = {'season', 'model_version', 'replacement_levels', 'vor_rows', 'tier_rows', 'adp_delta_rows'}
    assert expected_keys == set(result.keys()), f"Unexpected keys: {set(result.keys())}"

    conn.close()


def test_run_valuation_season_and_model_version_in_result():
    """Returned dict should echo back the season and model_version."""
    conn = _make_conn()
    result = run_valuation(conn, season=2026, model_version='v1')

    assert result['season'] == 2026
    assert result['model_version'] == 'v1'

    conn.close()


def test_run_valuation_vor_rows_count():
    """vor_rows should equal the number of projection rows processed (8 players)."""
    conn = _make_conn()
    result = run_valuation(conn, season=2026, model_version='v1')

    assert result['vor_rows'] == 8

    conn.close()


def test_run_valuation_replacement_levels_all_positions():
    """replacement_levels dict should contain all four positions."""
    conn = _make_conn()
    result = run_valuation(conn, season=2026, model_version='v1')

    levels = result['replacement_levels']
    assert set(levels.keys()) >= {'QB', 'RB', 'WR', 'TE'}

    conn.close()


def test_adp_delta_null_for_players_without_adp():
    """Players with no matching ADP entry should have adp_delta = NULL."""
    conn = _make_conn()
    run_valuation(conn, season=2026, model_version='v1')

    # qb2 has no ADP entry — adp_delta must remain NULL
    row = conn.execute(
        "SELECT adp_delta FROM projections WHERE gsis_id = 'qb2' AND season = 2026 AND model_version = 'v1'"
    ).fetchone()
    assert row is not None, "qb2 projection row not found"
    assert row[0] is None, f"Expected adp_delta=NULL for qb2, got {row[0]}"

    conn.close()


def test_adp_delta_set_for_players_with_adp():
    """Players that have an ADP entry should receive a non-NULL adp_delta."""
    conn = _make_conn()
    run_valuation(conn, season=2026, model_version='v1')

    # qb1 has ADP=3.0 and should get adp_delta = vor_rank - 3.0
    row = conn.execute(
        "SELECT adp_delta, vor_rank FROM projections WHERE gsis_id = 'qb1' AND season = 2026 AND model_version = 'v1'"
    ).fetchone()
    assert row is not None, "qb1 projection row not found"
    adp_delta, vor_rank = row
    assert adp_delta is not None, "adp_delta should not be NULL for qb1"
    assert adp_delta == pytest.approx(vor_rank - 3.0)

    conn.close()


def test_tier_rows_count():
    """tier_rows should equal the number of projection rows with tiers assigned (8 players)."""
    conn = _make_conn()
    result = run_valuation(conn, season=2026, model_version='v1')

    assert result['tier_rows'] == 8

    conn.close()
