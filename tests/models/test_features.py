from tay.models.features import POSITION_FEATURES, QB_FEATURES, RB_FEATURES, WR_FEATURES, TE_FEATURES


def test_all_positions_present():
    assert set(POSITION_FEATURES.keys()) == {'QB', 'RB', 'WR', 'TE'}


def test_no_duplicates():
    for pos, feats in POSITION_FEATURES.items():
        assert len(feats) == len(set(feats)), f'{pos} has duplicate feature names'


def test_all_strings():
    for pos, feats in POSITION_FEATURES.items():
        assert all(isinstance(f, str) for f in feats), f'{pos} has non-string feature'


def test_non_empty():
    for pos, feats in POSITION_FEATURES.items():
        assert len(feats) >= 10, f'{pos} has too few features: {len(feats)}'


def test_dict_matches_lists():
    assert POSITION_FEATURES['QB'] is QB_FEATURES
    assert POSITION_FEATURES['RB'] is RB_FEATURES
    assert POSITION_FEATURES['WR'] is WR_FEATURES
    assert POSITION_FEATURES['TE'] is TE_FEATURES


def test_qb_has_multi_year_features():
    for col in ['lag2_fantasy_ppr', 'lag3_fantasy_ppr', 'ewma_fantasy_ppr', 'ewma_pass_yards']:
        assert col in QB_FEATURES, f"QB missing {col}"


def test_rb_has_multi_year_features():
    for col in ['lag2_fantasy_ppr', 'lag3_fantasy_ppr', 'ewma_fantasy_ppr',
                'lag2_carries', 'lag3_carries', 'ewma_carries']:
        assert col in RB_FEATURES, f"RB missing {col}"


def test_wr_has_multi_year_features():
    for col in ['lag2_fantasy_ppr', 'lag3_fantasy_ppr', 'ewma_fantasy_ppr',
                'lag2_targets', 'lag3_targets', 'ewma_targets']:
        assert col in WR_FEATURES, f"WR missing {col}"


def test_te_has_multi_year_features():
    for col in ['lag2_fantasy_ppr', 'lag3_fantasy_ppr', 'ewma_fantasy_ppr',
                'lag2_targets', 'lag3_targets', 'ewma_targets']:
        assert col in TE_FEATURES, f"TE missing {col}"


def test_no_duplicate_features():
    for name, lst in [('QB', QB_FEATURES), ('RB', RB_FEATURES),
                      ('WR', WR_FEATURES), ('TE', TE_FEATURES)]:
        assert len(lst) == len(set(lst)), f"{name} has duplicate features: {[f for f in lst if lst.count(f) > 1]}"
