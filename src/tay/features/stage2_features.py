"""Build Stage 2 (efficiency) features — strictly no volume/opportunity signals."""
from __future__ import annotations
import math
from datetime import date

import pandas as pd
import duckdb

_W1, _W2, _W3 = 0.6, 0.3, 0.1
SKILL_POSITIONS = ('QB', 'RB', 'WR', 'TE')


def _ewma(v1, v2, v3) -> float | None:
    """Weighted EWMA: 0.6×v1 + 0.3×v2 + 0.1×v3.

    Weights are applied as-is (no re-normalization). Missing seasons contribute 0.
    Single-season value: 0.6 × v1 (not re-normalized to 1.0).
    """
    vals = [(v, w) for v, w in [(v1, _W1), (v2, _W2), (v3, _W3)] if v is not None]
    if not vals:
        return None
    return sum(v * w for v, w in vals)


def _age(birth_date_str, season: int) -> float | None:
    if not birth_date_str:
        return None
    try:
        bd = date.fromisoformat(str(birth_date_str))
        return (date(season, 9, 1) - bd).days / 365.25
    except (ValueError, TypeError):
        return None


def _safe_div(n, d, min_d=1) -> float | None:
    if n is None or d is None or float(d) < min_d:
        return None
    return float(n) / float(d)


def _nan_or(v) -> float:
    """Convert None to float NaN; leave other values as float."""
    if v is None:
        return math.nan
    return float(v)


def build_stage2_features(
    conn: duckdb.DuckDBPyConnection,
    seasons: list[int],
    qb_efficiency: dict[str, dict] | None = None,
) -> pd.DataFrame:
    """Return Stage 2 feature DataFrame. No volume signals.

    qb_efficiency: {gsis_id: {'ewma_epa': float, 'ewma_cpoe': float}}
    Used to inject QB context for WR/TE/RB rows. If None, those cols are NaN.
    """
    rows = []
    for season in seasons:
        prior, prior2, prior3 = season - 1, season - 2, season - 3

        # Fetch players who have stats in the prior season.
        # NOTE: p.experience does NOT exist on the players table.
        # Compute experience as (prior - p.draft_year) if draft_year is set.
        players = conn.execute("""
            SELECT p.gsis_id, p.position, s.team,
                   p.birth_date, p.draft_year, s.games AS prev_games
            FROM player_season_stats s
            JOIN players p ON p.gsis_id = s.gsis_id
            WHERE s.season = ? AND p.position IN ('QB', 'RB', 'WR', 'TE')
        """, [prior]).fetchall()

        for (gsis_id, position, team, birth_date, draft_year, prev_games) in players:
            # Compute experience from draft_year
            experience = (prior - draft_year) if draft_year else None

            def gs(s):
                return conn.execute("""
                    SELECT targets, receptions, rec_yards, rec_tds, air_yards,
                           carries, rush_yards, rush_tds,
                           attempts, completions, pass_yards, pass_tds, interceptions,
                           epa_per_play, cpoe, games
                    FROM player_season_stats
                    WHERE gsis_id = ? AND season = ?
                """, [gsis_id, s]).fetchone()

            s1 = gs(prior)
            s2 = gs(prior2)
            s3 = gs(prior3)
            sN = gs(season)

            # --- Efficiency metrics per season ---
            # yards per target
            ypt1 = _safe_div(s1[2], s1[0]) if s1 else None
            ypt2 = _safe_div(s2[2], s2[0]) if s2 else None
            ypt3 = _safe_div(s3[2], s3[0]) if s3 else None

            # catch rate
            cr1 = _safe_div(s1[1], s1[0]) if s1 else None
            cr2 = _safe_div(s2[1], s2[0]) if s2 else None
            cr3 = _safe_div(s3[1], s3[0]) if s3 else None

            # air yards per target
            ayt1 = _safe_div(s1[4], s1[0]) if s1 else None
            ayt2 = _safe_div(s2[4], s2[0]) if s2 else None
            ayt3 = _safe_div(s3[4], s3[0]) if s3 else None

            # EPA per play
            epa1 = s1[13] if s1 else None
            epa2 = s2[13] if s2 else None
            epa3 = s3[13] if s3 else None

            # yards per carry
            ypc1 = _safe_div(s1[6], s1[5]) if s1 else None
            ypc2 = _safe_div(s2[6], s2[5]) if s2 else None
            ypc3 = _safe_div(s3[6], s3[5]) if s3 else None

            # CPOE
            cpoe1 = s1[14] if s1 else None
            cpoe2 = s2[14] if s2 else None
            cpoe3 = s3[14] if s3 else None

            # completion pct
            comp1 = _safe_div(s1[9], s1[8]) if s1 else None
            comp2 = _safe_div(s2[9], s2[8]) if s2 else None
            comp3 = _safe_div(s3[9], s3[8]) if s3 else None

            # --- Labels (season N actuals, None when season N data absent) ---
            yards_per_target     = _safe_div(sN[2], sN[0]) if sN else None
            catch_rate           = _safe_div(sN[1], sN[0]) if sN else None
            td_rate_per_target   = _safe_div(sN[3], sN[0]) if sN else None
            yards_per_carry      = _safe_div(sN[6], sN[5]) if sN else None
            rush_td_rate         = _safe_div(sN[7], sN[5]) if sN else None
            rec_yards_per_target = _safe_div(sN[2], sN[0]) if sN else None
            rec_catch_rate       = _safe_div(sN[1], sN[0]) if sN else None
            rec_td_rate          = _safe_div(sN[3], sN[0]) if sN else None
            yards_per_attempt    = _safe_div(sN[10], sN[8]) if sN else None
            td_rate              = _safe_div(sN[11], sN[8]) if sN else None
            int_rate             = _safe_div(sN[12], sN[8]) if sN else None
            rush_yards_pg = (float(sN[6]) / float(sN[15])) if sN and sN[6] and sN[15] else None
            rush_tds_pg   = (float(sN[7]) / float(sN[15])) if sN and sN[7] and sN[15] else None

            # --- QB context for skill positions ---
            qb_epa = None
            qb_cpoe = None
            if position in ('WR', 'TE', 'RB') and qb_efficiency:
                qb_team_row = conn.execute(
                    "SELECT gsis_id FROM players WHERE team = ? AND position = 'QB'",
                    [team]
                ).fetchone()
                if qb_team_row:
                    q = qb_efficiency.get(qb_team_row[0], {})
                    qb_epa = q.get('ewma_epa')
                    qb_cpoe = q.get('ewma_cpoe')

            rows.append({
                'gsis_id': gsis_id,
                'season': season,
                'position': position,
                'team': team,
                # labels — NaN when season N data absent
                'yards_per_target': _nan_or(yards_per_target),
                'catch_rate': _nan_or(catch_rate),
                'td_rate_per_target': _nan_or(td_rate_per_target),
                'yards_per_carry': _nan_or(yards_per_carry),
                'rush_td_rate': _nan_or(rush_td_rate),
                'rec_yards_per_target': _nan_or(rec_yards_per_target),
                'rec_catch_rate': _nan_or(rec_catch_rate),
                'rec_td_rate': _nan_or(rec_td_rate),
                'yards_per_attempt': _nan_or(yards_per_attempt),
                'td_rate': _nan_or(td_rate),
                'int_rate': _nan_or(int_rate),
                'rush_yards_per_game': _nan_or(rush_yards_pg),
                'rush_tds_per_game': _nan_or(rush_tds_pg),
                # efficiency features (EWMA, no renormalization)
                'ewma_yards_per_target': _ewma(ypt1, ypt2, ypt3),
                'ewma_catch_rate': _ewma(cr1, cr2, cr3),
                'ewma_air_yards_per_target': _ewma(ayt1, ayt2, ayt3),
                'ewma_epa_per_play': _ewma(epa1, epa2, epa3),
                'ewma_yards_per_carry': _ewma(ypc1, ypc2, ypc3),
                'ewma_cpoe': _ewma(cpoe1, cpoe2, cpoe3),
                'ewma_completion_pct': _ewma(comp1, comp2, comp3),
                # player context
                'age': _age(birth_date, season),
                'experience': experience,
                'prev_games': prev_games,
                # QB context
                'qb_ewma_epa_per_play': qb_epa,
                'qb_ewma_cpoe': qb_cpoe,
            })

    return pd.DataFrame(rows).reset_index(drop=True)
