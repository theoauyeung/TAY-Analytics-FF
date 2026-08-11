"""Tests for session persistence (save_session, load_session)."""
from __future__ import annotations
import json
import duckdb
from tay.draft.models import LeagueSettings, DraftState
from tay.draft.session import save_session, load_session


def _conn():
    conn = duckdb.connect(':memory:')
    conn.execute("""
        CREATE TABLE draft_sessions (
            session_id VARCHAR PRIMARY KEY,
            created_at TIMESTAMP DEFAULT current_timestamp,
            league_settings JSON,
            picks JSON,
            completed BOOLEAN DEFAULT FALSE
        )
    """)
    return conn


def _state():
    ls = LeagueSettings()
    return DraftState(
        season=2026, model_version='neural-v1', league_settings=ls,
        current_pick=5, total_picks=180, user_pick_position=3,
        drafted_ids=['A', 'B', 'C', 'D'],
        user_roster={'QB': [], 'RB': ['A'], 'WR': [], 'TE': [], 'FLEX': []},
    )


def test_save_and_load_roundtrip():
    conn = _conn()
    state = _state()
    save_session(conn, 'sess-001', state)
    result = load_session(conn, 'sess-001')
    assert result is not None
    assert result['session_id'] == 'sess-001'
    picks = json.loads(result['picks']) if isinstance(result['picks'], str) else result['picks']
    assert picks == ['A', 'B', 'C', 'D']
    conn.close()


def test_load_session_missing_returns_none():
    conn = _conn()
    assert load_session(conn, 'nonexistent') is None
    conn.close()


def test_save_session_overwrites_existing():
    conn = _conn()
    state = _state()
    save_session(conn, 'sess-002', state)
    # Update picks and save again
    state.drafted_ids.append('E')
    save_session(conn, 'sess-002', state)
    result = load_session(conn, 'sess-002')
    picks = json.loads(result['picks']) if isinstance(result['picks'], str) else result['picks']
    assert 'E' in picks
    conn.close()
