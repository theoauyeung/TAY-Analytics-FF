"""Analytical composition of Stage 1 × Stage 2 outputs into PPR projections."""
from __future__ import annotations

import pandas as pd
import duckdb

MODEL_VERSION_DEFAULT = 'two-stage-v1'


def _team_volume(conn, team: str, season: int) -> tuple[float, float]:
    """Return (pass_att_per_game, rush_att_per_game) from team_features.

    team_features.pass_attempts is a season total; divide by 17 to get per-game.
    rush_att_per_game is derived from total_plays - pass_attempts.
    """
    row = conn.execute("""
        SELECT pass_attempts, total_plays
        FROM team_features
        WHERE team = ? AND season = ?
    """, [team, season]).fetchone()

    if row and row[0] is not None:
        pass_att_pg = float(row[0]) / 17.0
    else:
        pass_att_pg = 35.0

    if row and row[1] is not None and row[0] is not None:
        rush_att_pg = float(row[1] - row[0]) / 17.0
    else:
        rush_att_pg = 25.0

    return pass_att_pg, rush_att_pg


def _wr_te_ppr(target_share: float, team_pass_att_pg: float, eff: dict) -> float | None:
    """Compute PPR projection for WR/TE.

    ppr = targets × catch_rate × 1.0
        + targets × yards_per_target × 0.1
        + targets × td_rate_per_target × 6.0
    where targets = target_share × team_pass_att_per_game × 17
    """
    ypt = eff.get('yards_per_target')
    cr  = eff.get('catch_rate')
    tdr = eff.get('td_rate_per_target')
    if None in (ypt, cr, tdr):
        return None
    targets = target_share * team_pass_att_pg * 17
    return (
        targets * float(cr) * 1.0
        + targets * float(ypt) * 0.1
        + targets * float(tdr) * 6.0
    )


def _rb_ppr(
    carry_share: float,
    rec_share: float,
    pass_att_pg: float,
    rush_att_pg: float,
    eff: dict,
) -> float | None:
    """Compute PPR projection for RB.

    ppr = carries × yards_per_carry × 0.1
        + carries × rush_td_rate × 6.0
        + rb_tgts × rec_catch_rate × 1.0
        + rb_tgts × rec_yards_per_target × 0.1
        + rb_tgts × rec_td_rate × 6.0
    where carries = carry_share × team_rush_att_per_game × 17
          rb_tgts = rec_share × team_pass_att_per_game × 17
    """
    ypc     = eff.get('yards_per_carry')
    rtdr    = eff.get('rush_td_rate')
    rypt    = eff.get('rec_yards_per_target')
    rcr     = eff.get('rec_catch_rate')
    rec_tdr = eff.get('rec_td_rate')
    if None in (ypc, rtdr, rypt, rcr, rec_tdr):
        return None
    carries = carry_share * rush_att_pg * 17
    rb_tgts = rec_share * pass_att_pg * 17
    return (
        carries * float(ypc) * 0.1
        + carries * float(rtdr) * 6.0
        + rb_tgts * float(rcr) * 1.0
        + rb_tgts * float(rypt) * 0.1
        + rb_tgts * float(rec_tdr) * 6.0
    )


def _qb_ppr(pass_att_per_game: float, eff: dict) -> float | None:
    """Compute PPR projection for QB.

    ppr = pass_att × yards_per_attempt × 0.04
        + pass_att × td_rate × 4.0
        - pass_att × int_rate × 2.0
        + rush_yards_per_game × 17 × 0.1
        + rush_tds_per_game × 17 × 6.0
    where pass_att = pass_att_per_game × 17
    """
    ypa  = eff.get('yards_per_attempt')
    tdr  = eff.get('td_rate')
    intr = eff.get('int_rate')
    rypg = eff.get('rush_yards_per_game')
    rtpg = eff.get('rush_tds_per_game')
    if None in (ypa, tdr, intr):
        return None
    pass_att = pass_att_per_game * 17
    return (
        pass_att * float(ypa) * 0.04
        + pass_att * float(tdr) * 4.0
        - pass_att * float(intr) * 2.0
        + float(rypg or 0) * 17 * 0.1
        + float(rtpg or 0) * 17 * 6.0
    )


def compose_projections(
    conn: duckdb.DuckDBPyConnection,
    stage1_df: pd.DataFrame,
    stage2_dict: dict[str, dict],
    season: int,
    model_version: str = MODEL_VERSION_DEFAULT,
) -> int:
    """Compose Stage 1 × Stage 2 into PPR projections; upsert to projections table.

    Parameters
    ----------
    conn:
        DuckDB connection with projections and team_features tables.
    stage1_df:
        DataFrame from run_stage1_inference — columns include gsis_id, season,
        position, team, projected_target_share, projected_carry_share,
        projected_rec_share, projected_pass_att_per_game.
    stage2_dict:
        Dict keyed by gsis_id → efficiency metrics dict from run_stage2_inference.
    season:
        The season being projected.
    model_version:
        Model version string for the projections primary key.

    Returns
    -------
    int
        Number of rows successfully written to the projections table.
    """
    written = 0
    for _, row in stage1_df.iterrows():
        gsis_id  = row['gsis_id']
        position = row['position']
        team     = row['team']
        eff      = stage2_dict.get(gsis_id)

        # Skip players not present in Stage 2 output
        if not eff:
            continue

        pass_att_pg, rush_att_pg = _team_volume(conn, team, season)

        ppr = None
        if position in ('WR', 'TE'):
            ts = row.get('projected_target_share')
            if ts is not None and not pd.isna(ts):
                ppr = _wr_te_ppr(float(ts), pass_att_pg, eff)
        elif position == 'RB':
            cs = row.get('projected_carry_share')
            rs = row.get('projected_rec_share')
            if cs is not None and rs is not None and not pd.isna(cs) and not pd.isna(rs):
                ppr = _rb_ppr(float(cs), float(rs), pass_att_pg, rush_att_pg, eff)
        elif position == 'QB':
            papg = row.get('projected_pass_att_per_game')
            if papg is not None and not pd.isna(papg):
                ppr = _qb_ppr(float(papg), eff)

        if ppr is None:
            continue

        ppr = max(ppr, 0.0)

        def _nullable(val):
            if val is None:
                return None
            try:
                if pd.isna(val):
                    return None
            except (TypeError, ValueError):
                pass
            return float(val)

        conn.execute("""
            INSERT INTO projections
                (gsis_id, season, model_version, mean_projection,
                 projected_target_share, projected_carry_share,
                 projected_rec_share, projected_pass_att_per_game)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (gsis_id, season, model_version) DO UPDATE SET
                mean_projection             = excluded.mean_projection,
                projected_target_share      = excluded.projected_target_share,
                projected_carry_share       = excluded.projected_carry_share,
                projected_rec_share         = excluded.projected_rec_share,
                projected_pass_att_per_game = excluded.projected_pass_att_per_game
        """, [
            gsis_id, season, model_version, ppr,
            _nullable(row.get('projected_target_share')),
            _nullable(row.get('projected_carry_share')),
            _nullable(row.get('projected_rec_share')),
            _nullable(row.get('projected_pass_att_per_game')),
        ])
        written += 1

    conn.commit()
    return written
