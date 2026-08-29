"""Analytical composition of Stage 1 × Stage 2 outputs into PPR projections."""
from __future__ import annotations

import pandas as pd
import duckdb

MODEL_VERSION_DEFAULT = 'two-stage-v1'


def _nullable(val):
    if val is None:
        return None
    try:
        if pd.isna(val):
            return None
    except (TypeError, ValueError):
        pass
    return float(val)


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


def _wr_te_ppr(target_share: float, team_pass_att_pg: float, eff: dict) -> dict | None:
    """Return PPR projection and component stats for WR/TE."""
    ypt = eff.get('yards_per_target')
    cr  = eff.get('catch_rate')
    tdr = eff.get('td_rate_per_target')
    if None in (ypt, cr, tdr):
        return None
    targets    = target_share * team_pass_att_pg * 17
    receptions = targets * float(cr)
    rec_yards  = targets * float(ypt)
    rec_tds    = targets * float(tdr)
    ppr = receptions * 1.0 + rec_yards * 0.1 + rec_tds * 6.0
    return {
        'ppr': ppr,
        'proj_targets':    targets,
        'proj_receptions': receptions,
        'proj_rec_yards':  rec_yards,
        'proj_rec_tds':    rec_tds,
    }


def _rb_ppr(
    carry_share: float,
    rec_share: float,
    pass_att_pg: float,
    rush_att_pg: float,
    eff: dict,
) -> dict | None:
    """Return PPR projection and component stats for RB."""
    ypc     = eff.get('yards_per_carry')
    rtdr    = eff.get('rush_td_rate')
    rypt    = eff.get('rec_yards_per_target')
    rcr     = eff.get('rec_catch_rate')
    rec_tdr = eff.get('rec_td_rate')
    if None in (ypc, rtdr, rypt, rcr, rec_tdr):
        return None
    carries    = carry_share * rush_att_pg * 17
    rb_tgts    = rec_share * pass_att_pg * 17
    rush_yards = carries * float(ypc)
    rush_tds   = carries * float(rtdr)
    receptions = rb_tgts * float(rcr)
    rec_yards  = rb_tgts * float(rypt)
    rec_tds    = rb_tgts * float(rec_tdr)
    ppr = (
        rush_yards * 0.1 + rush_tds * 6.0
        + receptions * 1.0 + rec_yards * 0.1 + rec_tds * 6.0
    )
    return {
        'ppr': ppr,
        'proj_rush_attempts': carries,
        'proj_rush_yards':    rush_yards,
        'proj_rush_tds':      rush_tds,
        'proj_targets':       rb_tgts,
        'proj_receptions':    receptions,
        'proj_rec_yards':     rec_yards,
        'proj_rec_tds':       rec_tds,
    }


def _qb_ppr(pass_att_per_game: float, eff: dict) -> dict | None:
    """Return PPR projection and component stats for QB."""
    ypa  = eff.get('yards_per_attempt')
    tdr  = eff.get('td_rate')
    intr = eff.get('int_rate')
    cpct = eff.get('completion_pct')
    rypg = eff.get('rush_yards_per_game')
    rtpg = eff.get('rush_tds_per_game')
    if None in (ypa, tdr, intr):
        return None
    pass_att    = pass_att_per_game * 17
    completions = pass_att * float(cpct or 0.63)
    pass_yards  = pass_att * float(ypa)
    pass_tds    = pass_att * float(tdr)
    ints        = pass_att * float(intr)
    rush_yards  = float(rypg or 0) * 17
    rush_tds    = float(rtpg or 0) * 17
    ppr = (
        pass_yards * 0.04 + pass_tds * 4.0 - ints * 2.0
        + rush_yards * 0.1 + rush_tds * 6.0
    )
    return {
        'ppr': ppr,
        'proj_pass_attempts': pass_att,
        'proj_completions':   completions,
        'proj_pass_yards':    pass_yards,
        'proj_pass_tds':      pass_tds,
        'proj_interceptions': ints,
        'proj_rush_attempts': float(rypg or 0) * 17 / max(float(ypa or 1), 1),
        'proj_rush_yards':    rush_yards,
        'proj_rush_tds':      rush_tds,
    }


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

        stats: dict | None = None
        if position in ('WR', 'TE'):
            ts = row.get('projected_target_share')
            if ts is not None and not pd.isna(ts):
                stats = _wr_te_ppr(float(ts), pass_att_pg, eff)
        elif position == 'RB':
            cs = row.get('projected_carry_share')
            rs = row.get('projected_rec_share')
            if cs is not None and rs is not None and not pd.isna(cs) and not pd.isna(rs):
                stats = _rb_ppr(float(cs), float(rs), pass_att_pg, rush_att_pg, eff)
        elif position == 'QB':
            papg = row.get('projected_pass_att_per_game')
            if papg is not None and not pd.isna(papg):
                stats = _qb_ppr(float(papg), eff)

        if stats is None:
            continue

        ppr = max(stats['ppr'], 0.0)

        conn.execute("""
            INSERT INTO projections
                (gsis_id, season, model_version, mean_projection,
                 projected_target_share, projected_carry_share,
                 projected_rec_share, projected_pass_att_per_game,
                 proj_targets, proj_receptions, proj_rec_yards, proj_rec_tds,
                 proj_rush_attempts, proj_rush_yards, proj_rush_tds,
                 proj_pass_attempts, proj_completions, proj_pass_yards,
                 proj_pass_tds, proj_interceptions)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (gsis_id, season, model_version) DO UPDATE SET
                mean_projection             = excluded.mean_projection,
                projected_target_share      = excluded.projected_target_share,
                projected_carry_share       = excluded.projected_carry_share,
                projected_rec_share         = excluded.projected_rec_share,
                projected_pass_att_per_game = excluded.projected_pass_att_per_game,
                proj_targets       = excluded.proj_targets,
                proj_receptions    = excluded.proj_receptions,
                proj_rec_yards     = excluded.proj_rec_yards,
                proj_rec_tds       = excluded.proj_rec_tds,
                proj_rush_attempts = excluded.proj_rush_attempts,
                proj_rush_yards    = excluded.proj_rush_yards,
                proj_rush_tds      = excluded.proj_rush_tds,
                proj_pass_attempts = excluded.proj_pass_attempts,
                proj_completions   = excluded.proj_completions,
                proj_pass_yards    = excluded.proj_pass_yards,
                proj_pass_tds      = excluded.proj_pass_tds,
                proj_interceptions = excluded.proj_interceptions
        """, [
            gsis_id, season, model_version, ppr,
            _nullable(row.get('projected_target_share')),
            _nullable(row.get('projected_carry_share')),
            _nullable(row.get('projected_rec_share')),
            _nullable(row.get('projected_pass_att_per_game')),
            _nullable(stats.get('proj_targets')),
            _nullable(stats.get('proj_receptions')),
            _nullable(stats.get('proj_rec_yards')),
            _nullable(stats.get('proj_rec_tds')),
            _nullable(stats.get('proj_rush_attempts')),
            _nullable(stats.get('proj_rush_yards')),
            _nullable(stats.get('proj_rush_tds')),
            _nullable(stats.get('proj_pass_attempts')),
            _nullable(stats.get('proj_completions')),
            _nullable(stats.get('proj_pass_yards')),
            _nullable(stats.get('proj_pass_tds')),
            _nullable(stats.get('proj_interceptions')),
        ])
        written += 1

    conn.commit()
    return written
