"""Integration tests for the two-stage pipeline orchestration."""
import duckdb
import pytest
from tay.db import init_schema


def test_two_stage_pipeline_function_exists():
    from tay.models.pipeline import run_two_stage_pipeline
    assert callable(run_two_stage_pipeline)


def test_compose_projections_writes_mean_projection():
    """Smoke test: compose writes non-None mean_projection for a WR."""
    import pandas as pd
    import duckdb
    from tay.db import init_schema
    from tay.models.composition import compose_projections

    conn = duckdb.connect(':memory:')
    init_schema(conn)

    conn.execute("""
        INSERT INTO team_features
            (team, season, pass_rate, rush_rate, team_epa, pass_epa, rush_epa,
             total_plays, pass_attempts, total_tds)
        VALUES ('SF', 2026, 0.58, 0.42, 0.12, 0.16, 0.08, 1050, 578, 48)
    """)
    conn.execute("INSERT INTO players (gsis_id, name, position, team) VALUES ('w1', 'Deebo', 'WR', 'SF')")

    stage1_df = pd.DataFrame([{
        'gsis_id': 'w1', 'season': 2026, 'position': 'WR', 'team': 'SF',
        'projected_target_share': 0.18,
        'projected_carry_share': None, 'projected_rec_share': None,
        'projected_pass_att_per_game': None,
    }])
    stage2 = {'w1': {'yards_per_target': 8.5, 'catch_rate': 0.65, 'td_rate_per_target': 0.07}}

    n = compose_projections(conn, stage1_df, stage2, 2026, 'two-stage-v1')
    assert n == 1

    row = conn.execute("SELECT mean_projection FROM projections WHERE gsis_id = 'w1'").fetchone()
    assert row[0] is not None
    assert row[0] > 0
    conn.close()
