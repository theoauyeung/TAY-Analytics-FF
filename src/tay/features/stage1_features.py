"""Build Stage 1 (opportunity) features: one row per player × projection season."""
from __future__ import annotations
import math
from datetime import date

import pandas as pd
import duckdb

_W1, _W2, _W3 = 0.6, 0.3, 0.1
SKILL_POSITIONS = ('QB', 'RB', 'WR', 'TE')


def _age(birth_date_str, season: int) -> float | None:
    if not birth_date_str:
        return None
    try:
        bd = date.fromisoformat(str(birth_date_str))
        return (date(season, 9, 1) - bd).days / 365.25
    except (ValueError, TypeError):
        return None


def _pick_value(draft_round, draft_pick) -> float:
    if draft_round and draft_pick:
        overall = (draft_round - 1) * 32 + int(draft_pick)
        return 1.0 / math.sqrt(max(overall, 1))
    return 0.0


def _ewma(v1, v2, v3) -> float | None:
    """Weighted EWMA: 0.6×v1 + 0.3×v2 + 0.1×v3.

    Weights are applied as-is (no re-normalization). Missing seasons contribute 0.
    Single-season value: 0.6 × v1 (not re-normalized to 1.0).
    """
    vals = [(v, w) for v, w in [(v1, _W1), (v2, _W2), (v3, _W3)] if v is not None]
    if not vals:
        return None
    return sum(v * w for v, w in vals)


def build_stage1_features(
    conn: duckdb.DuckDBPyConnection,
    seasons: list[int],
    positions: tuple[str, ...] = SKILL_POSITIONS,
) -> pd.DataFrame:
    """Return a DataFrame with Stage 1 features + labels for the given seasons.

    For training rows: season N features derived from season N-1 stats, label from season N stats.
    For inference rows: season N features only (label columns will be NaN).
    """
    rows = []
    for season in seasons:
        prior = season - 1
        prior2 = season - 2
        prior3 = season - 3

        # All players active in prior season on skill positions
        # Note: players table has no 'experience' column; compute from draft_year in Python
        players = conn.execute("""
            SELECT
                p.gsis_id, p.position, s.team,
                p.birth_date, p.draft_year, p.draft_round, p.draft_pick
            FROM player_season_stats s
            JOIN players p ON p.gsis_id = s.gsis_id
            WHERE s.season = ? AND p.position IN ('QB', 'RB', 'WR', 'TE')
        """, [prior]).fetchall()

        for (gsis_id, position, prior_team, birth_date, draft_year, draft_round,
             draft_pick) in players:

            # Compute experience from draft_year
            experience = (prior - draft_year) if draft_year else None

            # Current team (season N) from players table
            current_team_row = conn.execute(
                "SELECT team FROM players WHERE gsis_id = ?", [gsis_id]
            ).fetchone()
            team = current_team_row[0] if current_team_row else prior_team

            if not team:
                continue

            # --- Efficiency EWMAs (portable talent, from player_season_stats) ---
            def get_stats(s):
                return conn.execute("""
                    SELECT targets, receptions, rec_yards, rec_tds, air_yards,
                           carries, rush_yards, rush_tds,
                           attempts, completions, pass_yards,
                           epa_per_play, cpoe,
                           (SELECT pass_attempts FROM team_season_stats
                            WHERE team = ps.team AND season = ps.season) AS team_pa,
                           games
                    FROM player_season_stats ps
                    WHERE gsis_id = ? AND season = ?
                """, [gsis_id, s]).fetchone()

            s1 = get_stats(prior)
            s2 = get_stats(prior2)
            s3 = get_stats(prior3)

            def eff(row, num_col_idx, denom_col_idx, min_denom=1):
                if row is None:
                    return None
                n = row[num_col_idx]
                d = row[denom_col_idx]
                if n is None or d is None or float(d) < min_denom:
                    return None
                return float(n) / float(d)

            ypt1 = eff(s1, 2, 0)   # rec_yards / targets
            ypt2 = eff(s2, 2, 0)
            ypt3 = eff(s3, 2, 0)

            cr1 = eff(s1, 1, 0)    # receptions / targets
            cr2 = eff(s2, 1, 0)
            cr3 = eff(s3, 1, 0)

            ayt1 = eff(s1, 4, 0)   # air_yards / targets
            ayt2 = eff(s2, 4, 0)
            ayt3 = eff(s3, 4, 0)

            epa1 = s1[11] if s1 else None
            epa2 = s2[11] if s2 else None
            epa3 = s3[11] if s3 else None

            ypc1 = eff(s1, 6, 5)   # rush_yards / carries
            ypc2 = eff(s2, 6, 5)
            ypc3 = eff(s3, 6, 5)

            cpoe1 = s1[12] if s1 else None
            cpoe2 = s2[12] if s2 else None
            cpoe3 = s3[12] if s3 else None

            comppct1 = eff(s1, 9, 8)   # completions / attempts
            comppct2 = eff(s2, 9, 8)
            comppct3 = eff(s3, 9, 8)

            # ewma_target_share: targets / team_pass_attempts
            ts1 = eff(s1, 0, 13)
            ts2 = eff(s2, 0, 13)
            ts3 = eff(s3, 0, 13)

            # --- Labels (prior season actuals, used as training targets) ---
            # For training: labels = season N-1 actuals (what the player achieved last season).
            # For inference rows (no current season data), these still reflect prior performance.
            # If season N actuals exist, prefer those; otherwise fall back to prior.
            sN = get_stats(season)
            sLabel = sN if sN else s1  # prefer current season if available, else prior

            if sN:
                team_pa_label = conn.execute(
                    "SELECT pass_attempts FROM team_season_stats WHERE team = ? AND season = ?",
                    [team, season]
                ).fetchone()
                team_ra_label = conn.execute(
                    "SELECT rush_attempts FROM team_season_stats WHERE team = ? AND season = ?",
                    [team, season]
                ).fetchone()
                games_label = conn.execute(
                    "SELECT games FROM player_season_stats WHERE gsis_id = ? AND season = ?",
                    [gsis_id, season]
                ).fetchone()
            else:
                # Use prior season team stats as fallback for label denominators
                team_pa_label = conn.execute(
                    "SELECT pass_attempts FROM team_season_stats WHERE team = ? AND season = ?",
                    [prior_team, prior]
                ).fetchone()
                team_ra_label = conn.execute(
                    "SELECT rush_attempts FROM team_season_stats WHERE team = ? AND season = ?",
                    [prior_team, prior]
                ).fetchone()
                games_label = conn.execute(
                    "SELECT games FROM player_season_stats WHERE gsis_id = ? AND season = ?",
                    [gsis_id, prior]
                ).fetchone()

            target_share = None
            carry_share = None
            rec_share = None
            pass_att_per_game = None

            if sLabel:
                if team_pa_label and team_pa_label[0]:
                    tpa = float(team_pa_label[0])
                    if sLabel[0] is not None:
                        target_share = float(sLabel[0]) / tpa
                    if sLabel[0] is not None and position == 'RB':
                        rec_share = float(sLabel[0]) / tpa
                if team_ra_label and team_ra_label[0] and sLabel[5] is not None:
                    carry_share = float(sLabel[5]) / float(team_ra_label[0])
                if games_label and games_label[0] and sLabel[8] is not None:
                    pass_att_per_game = float(sLabel[8]) / float(games_label[0])

            # --- Team context (season N) ---
            tf = conn.execute("""
                SELECT pass_rate, pass_epa, vacated_wr_targets, vacated_rb_carries
                FROM team_features WHERE team = ? AND season = ?
            """, [team, season]).fetchone()

            # --- OC features ---
            oc_row = conn.execute("""
                SELECT full_name FROM coaches
                WHERE team = ? AND season = ? AND coach_type = 'offensive_coordinator'
            """, [team, prior]).fetchone()
            oc_name = oc_row[0] if oc_row else None

            oc_feat = None
            if oc_name:
                oc_feat = conn.execute("""
                    SELECT hist_wr1_target_share, hist_air_yards_pct, hist_rb_target_share,
                           tenure_at_team, is_rookie_oc
                    FROM oc_features WHERE oc_name = ? AND as_of_season = ?
                """, [oc_name, season]).fetchone()

            # --- Scheme cluster ---
            sc = conn.execute(
                "SELECT cluster_id FROM scheme_clusters WHERE team = ? AND season = ?",
                [team, season]  # use target season's cluster as best preseason prior
            ).fetchone()

            row = {
                'gsis_id': gsis_id,
                'season': season,
                'position': position,
                'team': team,
                # labels
                'target_share': target_share,
                'carry_share': carry_share,
                'rec_share': rec_share,
                'pass_att_per_game': pass_att_per_game,
                # talent EWMAs
                'ewma_yards_per_target': _ewma(ypt1, ypt2, ypt3),
                'ewma_catch_rate': _ewma(cr1, cr2, cr3),
                'ewma_air_yards_per_target': _ewma(ayt1, ayt2, ayt3),
                'ewma_epa_per_play': _ewma(epa1, epa2, epa3),
                'ewma_yards_per_carry': _ewma(ypc1, ypc2, ypc3),
                'ewma_cpoe': _ewma(cpoe1, cpoe2, cpoe3),
                'ewma_completion_pct': _ewma(comppct1, comppct2, comppct3),
                'ewma_target_share': _ewma(ts1, ts2, ts3),
                # player context
                'draft_pick_value': _pick_value(draft_round, draft_pick),
                'age': _age(birth_date, season),
                'experience': experience,
                # team context
                'new_team_pass_rate': tf[0] if tf else None,
                'new_team_pass_epa': tf[1] if tf else None,
                'vacated_wr_targets': tf[2] if tf else None,
                'vacated_rb_carries': tf[3] if tf else None,
                # OC/scheme
                'oc_hist_wr1_target_share': oc_feat[0] if oc_feat else None,
                'oc_hist_air_yards_pct': oc_feat[1] if oc_feat else None,
                'oc_hist_rb_target_share': oc_feat[2] if oc_feat else None,
                'oc_tenure_at_team': oc_feat[3] if oc_feat else None,
                'is_rookie_oc': bool(oc_feat[4]) if oc_feat else True,
                'scheme_cluster': sc[0] if sc else None,
                'depth_chart_rank': None,  # filled below
            }
            rows.append(row)

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # Compute implicit depth chart rank within team × season × position
    df['_ts_fill'] = df['ewma_target_share'].fillna(0.0)
    df['depth_chart_rank'] = (
        df.groupby(['team', 'season', 'position'])['_ts_fill']
        .rank(method='min', ascending=False)
        .astype(int)
    )
    df.drop(columns=['_ts_fill'], inplace=True)

    return df.reset_index(drop=True)
