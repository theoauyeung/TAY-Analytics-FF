import pytest
from tay.projections.name_match import normalize_name, match_player


def test_normalize_lowercase():
    assert normalize_name("Patrick Mahomes") == "patrick mahomes"


def test_normalize_strips_suffix_jr():
    assert normalize_name("Travis Etienne Jr.") == "travis etienne"


def test_normalize_strips_suffix_sr():
    assert normalize_name("Michael Pittman Sr.") == "michael pittman"


def test_normalize_strips_suffix_ii():
    assert normalize_name("Odell Beckham II") == "odell beckham"


def test_normalize_strips_suffix_iii():
    assert normalize_name("Michael Thomas III") == "michael thomas"


def test_normalize_removes_apostrophe():
    assert normalize_name("Ja'Marr Chase") == "jamarr chase"


def test_normalize_removes_hyphen():
    assert normalize_name("De'Von Achane") == "devon achane"


def test_normalize_removes_period_in_initials():
    assert normalize_name("D.K. Metcalf") == "dk metcalf"


def test_normalize_collapses_whitespace():
    assert normalize_name("  Josh   Allen  ") == "josh allen"


def test_match_player_exact():
    db = [("id1", "patrick mahomes"), ("id2", "lamar jackson")]
    assert match_player("Patrick Mahomes", db) == "id1"


def test_match_player_fuzzy_suffix():
    db = [("id1", "travis etienne"), ("id2", "lamar jackson")]
    # "Travis Etienne Jr." normalizes to "travis etienne" — exact after norm
    assert match_player("Travis Etienne Jr.", db) == "id1"


def test_match_player_fuzzy_initials():
    db = [("id1", "dk metcalf"), ("id2", "lamar jackson")]
    # "D.K. Metcalf" normalizes to "dk metcalf" — exact after norm
    assert match_player("D.K. Metcalf", db) == "id1"


def test_match_player_below_threshold_returns_none():
    db = [("id1", "lamar jackson"), ("id2", "josh allen")]
    assert match_player("Totally Different Name", db) is None


def test_match_player_empty_db_returns_none():
    assert match_player("Patrick Mahomes", []) is None
