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
