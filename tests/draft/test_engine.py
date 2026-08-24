# tests/draft/test_engine.py
from __future__ import annotations
import pytest
import duckdb
from tay.draft.models import LeagueSettings, DraftState
from tay.draft.engine import recommend, load_projections


def _make_db():
    conn = duckdb.connect(':memory:')
    conn.execute("""
        CREATE TABLE players (
            gsis_id VARCHAR PRIMARY KEY, name VARCHAR, position VARCHAR, team VARCHAR
        )
    """)
    conn.execute("""
        CREATE TABLE projections (
            gsis_id VARCHAR, season INTEGER, model_version VARCHAR,
            mean_projection DOUBLE, std_dev DOUBLE,
            vor DOUBLE, vor_rank INTEGER,
            sim_mean DOUBLE, sim_p10 DOUBLE, sim_p90 DOUBLE,
            sim_boom_prob DOUBLE, sim_bust_prob DOUBLE,
            tier INTEGER, p10 DOUBLE, p90 DOUBLE,
            PRIMARY KEY (gsis_id, season, model_version)
        )
    """)
    conn.execute("""
        CREATE TABLE adp (
            gsis_id VARCHAR, season INTEGER, platform VARCHAR,
            format VARCHAR, adp DOUBLE, rank INTEGER,
            PRIMARY KEY (season, platform, format, gsis_id)
        )
    """)
    # Insert 6 players: 2 QB, 2 RB, 2 WR
    players = [
        ('Q1', 'QB One', 'QB', 'BUF'),
        ('Q2', 'QB Two', 'QB', 'KC'),
        ('R1', 'RB One', 'RB', 'SF'),
        ('R2', 'RB Two', 'RB', 'DAL'),
        ('W1', 'WR One', 'WR', 'CIN'),
        ('W2', 'WR Two', 'WR', 'PHI'),
    ]
    conn.executemany("INSERT INTO players VALUES (?, ?, ?, ?)", players)

    projs = [
        # (gsis_id, season, mv, mean_proj, std_dev, vor, vor_rank, sim_mean, sim_p10, sim_p90, boom, bust, tier, p10, p90)
        ('Q1', 2026, 'test-v1', 380.0, 40.0, 100.0, 1, 375.0, 290.0, 460.0, 0.3, 0.1, 1, 290.0, 460.0),
        ('Q2', 2026, 'test-v1', 300.0, 35.0,  50.0, 2, 295.0, 225.0, 365.0, 0.2, 0.1, 2, 225.0, 365.0),
        ('R1', 2026, 'test-v1', 260.0, 30.0,  90.0, 3, 255.0, 195.0, 315.0, 0.25, 0.1, 1, 195.0, 315.0),
        ('R2', 2026, 'test-v1', 200.0, 28.0,  40.0, 4, 195.0, 145.0, 245.0, 0.2, 0.12, 2, 145.0, 245.0),
        ('W1', 2026, 'test-v1', 280.0, 32.0,  80.0, 5, 275.0, 210.0, 340.0, 0.28, 0.09, 1, 210.0, 340.0),
        ('W2', 2026, 'test-v1', 220.0, 29.0,  30.0, 6, 215.0, 162.0, 268.0, 0.18, 0.11, 2, 162.0, 268.0),
    ]
    conn.executemany("INSERT INTO projections VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", projs)

    adp_rows = [
        ('Q1', 2026, 'espn', 'ppr', 5.0, 5),
        ('R1', 2026, 'espn', 'ppr', 2.0, 2),
        ('W1', 2026, 'espn', 'ppr', 4.0, 4),
    ]
    conn.executemany("INSERT INTO adp VALUES (?, ?, ?, ?, ?, ?)", adp_rows)
    return conn


def _state(drafted_ids=None, current_pick=1, user_roster=None):
    ls = LeagueSettings()
    return DraftState(
        season=2026, model_version='test-v1', league_settings=ls,
        current_pick=current_pick, total_picks=180, user_pick_position=1,
        drafted_ids=drafted_ids or [],
        user_roster=user_roster or {'QB': [], 'RB': [], 'WR': [], 'TE': [], 'FLEX': []},
    )


def test_load_projections_returns_all_available():
    conn = _make_db()
    players = load_projections(conn, 2026, 'test-v1', drafted_ids=[])
    assert len(players) == 6
    conn.close()


def test_load_projections_excludes_drafted():
    conn = _make_db()
    players = load_projections(conn, 2026, 'test-v1', drafted_ids=['Q1', 'R1'])
    ids = [p.gsis_id for p in players]
    assert 'Q1' not in ids
    assert 'R1' not in ids
    assert len(players) == 4
    conn.close()


def test_recommend_returns_recommendation_state():
    conn = _make_db()
    state = _state()
    result = recommend(conn, state)
    assert result.top_pick is not None
    assert len(result.alternatives) <= 3
    assert isinstance(result.positional_needs, list)
    conn.close()


def test_recommend_top_pick_not_drafted():
    conn = _make_db()
    # Draft the highest VOR player (Q1, vor=100) and confirm it's excluded
    state = _state(drafted_ids=['Q1'])
    result = recommend(conn, state)
    assert result.top_pick.player.gsis_id != 'Q1'
    conn.close()


def test_recommend_board_state_fields():
    conn = _make_db()
    state = _state(current_pick=5)
    result = recommend(conn, state)
    assert result.board_state['current_pick'] == 5
    assert result.board_state['round'] == 1
    assert 'picks_until_next' in result.board_state
    conn.close()


def test_recommend_exhausted_position_appears_in_needs():
    conn = _make_db()
    # Draft all QBs — Q1 and Q2 both taken
    state = _state(drafted_ids=['Q1', 'Q2'])
    result = recommend(conn, state)
    # QB exhausted → should appear in positional_needs (likely first)
    assert 'QB' in result.positional_needs
    conn.close()


def test_recommend_may_not_make_it_back_list():
    conn = _make_db()
    # R1 has ADP=2 and becomes the top pick (highest VOR after QB suppression)
    # W1 (ADP=4) and Q1 (ADP=5, QB-suppressed) end up in may_not_make_it_back
    state = DraftState(
        season=2026, model_version='test-v1',
        league_settings=LeagueSettings(),
        current_pick=1, total_picks=180, user_pick_position=12,  # user picks last
        drafted_ids=[], user_roster={'QB': [], 'RB': [], 'WR': [], 'TE': [], 'FLEX': []},
    )
    result = recommend(conn, state)
    # W1 has ADP=4, user picks ~12th — should appear in may_not_make_it_back
    mnmib_ids = [p.gsis_id for p in result.may_not_make_it_back]
    assert 'W1' in mnmib_ids  # ADP=4, likely gone by user's turn at pick 12
    conn.close()
