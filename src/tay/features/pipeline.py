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
    # Use current team from players table (reflects upcoming season assignment),
    # falling back to pf.team (prior season) when not found.
    # For RBs, weight vacated carries by 1/depth_chart_pos so starters get
    # more credit than backups — prevents all RBs on a team from receiving the
    # same inflated opportunity signal.
    conn.execute("""
        UPDATE player_features pf
        SET incoming_vacated_targets = (
            SELECT CASE
                WHEN pf.position = 'WR' THEN tf.vacated_wr_targets
                WHEN pf.position = 'TE' THEN tf.vacated_te_targets
                WHEN pf.position = 'QB' THEN tf.vacated_qb_attempts
                ELSE 0
            END
            FROM team_features tf
            LEFT JOIN players pl ON pl.gsis_id = pf.gsis_id
            WHERE tf.team = COALESCE(pl.team, pf.team)
              AND tf.season = pf.season
        ),
        incoming_vacated_carries = (
            SELECT CASE
                WHEN pf.position = 'RB' THEN
                    COALESCE(tf.vacated_rb_carries, 0)
                    / COALESCE(pf.depth_chart_pos, 2)
                ELSE 0
            END
            FROM team_features tf
            LEFT JOIN players pl ON pl.gsis_id = pf.gsis_id
            WHERE tf.team = COALESCE(pl.team, pf.team)
              AND tf.season = pf.season
        )
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
