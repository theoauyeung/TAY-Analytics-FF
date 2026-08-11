"""Draft endpoints — recommend, simulate (stub), session save/load."""
from __future__ import annotations
import dataclasses
import json
import duckdb
from fastapi import APIRouter, Depends, HTTPException, Response

from tay.api.deps import get_db
from tay.api.schemas import DraftStateIn, SessionIn, SessionOut
from tay.draft.engine import recommend
from tay.draft.models import LeagueSettings as DraftLeagueSettings, DraftState
from tay.draft.session import save_session, load_session

router = APIRouter(prefix='/draft', tags=['draft'])


def _to_draft_state(body: DraftStateIn) -> DraftState:
    ls = DraftLeagueSettings(
        teams=body.league_settings.teams,
        scoring=body.league_settings.scoring,
        roster_config=body.league_settings.roster_config,
    )
    return DraftState(
        season=body.season,
        model_version=body.model_version,
        league_settings=ls,
        current_pick=body.current_pick,
        total_picks=body.total_picks,
        user_pick_position=body.user_pick_position,
        drafted_ids=list(body.drafted_ids),
        user_roster={k: list(v) for k, v in body.user_roster.items()},
    )


@router.post('/recommend')
def draft_recommend(
    body: DraftStateIn,
    conn: duckdb.DuckDBPyConnection = Depends(get_db),
) -> dict:
    state = _to_draft_state(body)
    result = recommend(conn, state)
    return dataclasses.asdict(result)


@router.post('/simulate')
def draft_simulate(response: Response) -> dict:
    response.status_code = 501
    return {'detail': 'Draft simulation not yet implemented'}


@router.post('/session')
def save_draft_session(
    body: SessionIn,
    conn: duckdb.DuckDBPyConnection = Depends(get_db),
) -> dict:
    state = _to_draft_state(body.state)
    save_session(conn, body.session_id, state)
    return {'ok': True}


@router.get('/session/{session_id}', response_model=SessionOut)
def get_draft_session(
    session_id: str,
    conn: duckdb.DuckDBPyConnection = Depends(get_db),
) -> SessionOut:
    row = load_session(conn, session_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f'Session {session_id!r} not found')

    # DuckDB JSON columns may come back as str or already-parsed
    league_settings = row['league_settings']
    if isinstance(league_settings, str):
        league_settings = json.loads(league_settings)

    picks_raw = row['picks']
    if isinstance(picks_raw, str):
        picks_raw = json.loads(picks_raw)

    return SessionOut(
        session_id=row['session_id'],
        league_settings=league_settings,
        picks=picks_raw,
        completed=bool(row['completed']),
    )
