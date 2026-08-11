"""Session persistence — save/load draft state to draft_sessions table."""
from __future__ import annotations
import dataclasses
import json
import duckdb

from tay.draft.models import DraftState

_SELECT_SQL = """
    SELECT session_id, league_settings, picks, completed
    FROM draft_sessions WHERE session_id = ?
"""


def save_session(
    conn: duckdb.DuckDBPyConnection,
    session_id: str,
    state: DraftState,
) -> None:
    league_json = json.dumps(dataclasses.asdict(state.league_settings))
    picks_json = json.dumps(state.drafted_ids)
    # DuckDB does not support INSERT OR REPLACE; delete then insert instead
    conn.execute("DELETE FROM draft_sessions WHERE session_id = ?", [session_id])
    conn.execute(
        """
        INSERT INTO draft_sessions (session_id, league_settings, picks, completed)
        VALUES (?, ?, ?, FALSE)
        """,
        [session_id, league_json, picks_json],
    )
    conn.commit()


def load_session(
    conn: duckdb.DuckDBPyConnection,
    session_id: str,
) -> dict | None:
    row = conn.execute(_SELECT_SQL, [session_id]).fetchone()
    if row is None:
        return None
    return {
        'session_id': row[0],
        'league_settings': row[1],
        'picks': row[2],
        'completed': row[3],
    }
