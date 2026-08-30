"""Orchestrate the full feature engineering pipeline."""
from __future__ import annotations
from tay.db import get_conn, init_schema
from tay.features.team_features import build_team_features
from tay.features.vacated_opportunity import compute_vacated_opportunity
from tay.features.player_features import build_player_features


def run_pipeline(
    start: int = 2006,
    end: int = 2025,
    db_path=None,
) -> None:
    """Run all feature engineering steps in order."""
    conn = get_conn(db_path) if db_path else get_conn()
    init_schema(conn)
    seasons = list(range(start, end + 1))

    print("Step 1/3: Building team environment features...")
    n = build_team_features(conn, seasons)
    print(f"  {n:,} team-feature rows")

    print("Step 2/3: Computing vacated opportunity...")
    n = compute_vacated_opportunity(conn, seasons)
    print(f"  {n:,} team-seasons updated with vacated opportunity")

    print("Step 3/3: Building player features...")
    n = build_player_features(conn, seasons)
    print(f"  {n:,} player-feature rows")

    print("Step 3b: Backfilling vacated opportunity into player features...")
    # Build a temp map of gsis_id → current team (from players table, which
    # reflects upcoming season assignment). Fall back to pf.team when absent.
    conn.execute("""
        CREATE OR REPLACE TEMP TABLE _current_teams AS
        SELECT pf.gsis_id, pf.season,
               COALESCE(pl.team, pf.team) AS current_team
        FROM player_features pf
        LEFT JOIN players pl ON pl.gsis_id = pf.gsis_id
    """)
    # Pre-compute vacated values for all rows, then apply via UPDATE FROM to
    # avoid DuckDB correlated-subquery limitations.
    conn.execute("""
        CREATE OR REPLACE TEMP TABLE _vacated_updates AS
        SELECT
            ct.gsis_id,
            ct.season,
            CASE
                WHEN pf.position = 'WR' THEN tf.vacated_wr_targets
                WHEN pf.position = 'TE' THEN tf.vacated_te_targets
                WHEN pf.position = 'QB' THEN tf.vacated_qb_attempts
                ELSE 0
            END AS incoming_vacated_targets,
            CASE
                WHEN pf.position = 'RB' THEN
                    COALESCE(tf.vacated_rb_carries, 0)
                    / COALESCE(pf.depth_chart_pos, 2)
                ELSE 0
            END AS incoming_vacated_carries
        FROM _current_teams ct
        JOIN team_features tf ON tf.team = ct.current_team AND tf.season = ct.season
        JOIN player_features pf ON pf.gsis_id = ct.gsis_id AND pf.season = ct.season
    """)
    conn.execute("""
        UPDATE player_features
        SET incoming_vacated_targets = u.incoming_vacated_targets,
            incoming_vacated_carries = u.incoming_vacated_carries
        FROM _vacated_updates u
        WHERE player_features.gsis_id = u.gsis_id
          AND player_features.season = u.season
    """)
    conn.commit()

    n_pf = conn.execute("SELECT COUNT(*) FROM player_features").fetchone()[0]
    n_tf = conn.execute("SELECT COUNT(*) FROM team_features").fetchone()[0]
    seasons_covered = conn.execute(
        "SELECT COUNT(DISTINCT season) FROM player_features"
    ).fetchone()[0]
    print(f"\nFeature pipeline complete:")
    print(f"  player_features: {n_pf:,} rows ({seasons_covered} seasons)")
    print(f"  team_features:   {n_tf:,} rows")
    conn.close()
