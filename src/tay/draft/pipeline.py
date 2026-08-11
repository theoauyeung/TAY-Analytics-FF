"""Draft pipeline orchestrator."""
from __future__ import annotations
import duckdb

from tay.draft.engine import recommend
from tay.draft.models import DraftState, RecommendationState


def run_draft_pipeline(
    conn: duckdb.DuckDBPyConnection,
    state: DraftState,
) -> RecommendationState:
    return recommend(conn, state)
