import duckdb
import pytest
from tay.db import init_schema

_FORBIDDEN = {
    'target_share', 'snap_share', 'ewma_targets', 'ewma_carries',
    'ewma_fantasy_ppr', 'targets', 'receptions', 'carries',
}


def _make_conn():
    conn = duckdb.connect(':memory:')
    init_schema(conn)
    return conn


def _seed_wr(conn):
    conn.execute("""
        INSERT INTO players (gsis_id, name, position, team, birth_date, draft_year, draft_round, draft_pick, college, height, weight, sleeper_id, espn_id, pfr_id, yahoo_id)
        VALUES ('w1', 'CeeDee Lamb', 'WR', 'DAL', '1999-04-08', 2020, 1, 17, NULL, NULL, NULL, NULL, NULL, NULL, NULL)
    """)
    for season, tgts, recs, yds, tds, ay, epa in [
        (2024, 140, 100, 1500, 12, 1100, 0.30),
        (2023, 130, 95, 1350, 9, 950, 0.25),
        (2022, 120, 85, 1200, 8, 850, 0.22),
    ]:
        conn.execute("""
            INSERT INTO player_season_stats
                (gsis_id, season, team, games, targets, receptions, rec_yards, rec_tds,
                 carries, rush_yards, rush_tds, attempts, completions, pass_yards,
                 air_yards, epa_per_play, cpoe)
            VALUES ('w1', ?, 'DAL', 17, ?, ?, ?, ?, 0, 0, 0, 0, 0, 0, ?, ?, NULL)
        """, [season, tgts, recs, yds, tds, ay, epa])


def test_no_volume_signals_in_columns():
    from tay.features.stage2_features import build_stage2_features
    conn = _make_conn()
    _seed_wr(conn)
    df = build_stage2_features(conn, [2025])
    forbidden_found = set(df.columns) & _FORBIDDEN
    assert forbidden_found == set(), f'Forbidden columns in Stage 2: {forbidden_found}'
    conn.close()


def test_wr_label_yards_per_target():
    from tay.features.stage2_features import build_stage2_features
    conn = _make_conn()
    _seed_wr(conn)
    df = build_stage2_features(conn, [2025])
    w1 = df[df['gsis_id'] == 'w1']
    assert len(w1) == 1
    # label for season 2025 requires season 2025 stats — not seeded, so label is NaN
    assert w1.iloc[0]['yards_per_target'] != w1.iloc[0]['yards_per_target']  # NaN check
    conn.close()


def test_wr_label_from_seeded_season():
    from tay.features.stage2_features import build_stage2_features
    conn = _make_conn()
    _seed_wr(conn)
    df = build_stage2_features(conn, [2024])
    w1 = df[df['gsis_id'] == 'w1']
    # 2024 label: 1500 / 140 ≈ 10.71
    assert w1.iloc[0]['yards_per_target'] == pytest.approx(1500 / 140, abs=0.01)
    conn.close()


def test_ewma_catch_rate_present():
    from tay.features.stage2_features import build_stage2_features
    conn = _make_conn()
    _seed_wr(conn)
    df = build_stage2_features(conn, [2025])
    w1 = df[df['gsis_id'] == 'w1'].iloc[0]
    # ewma uses seasons 2024, 2023, 2022 — no renormalization
    expected = (0.6 * (100/140) + 0.3 * (95/130) + 0.1 * (85/120))
    assert w1['ewma_catch_rate'] == pytest.approx(expected, abs=0.01)
    conn.close()
