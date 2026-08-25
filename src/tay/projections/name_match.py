"""Player name normalization and fuzzy matching for FantasyPros name resolution."""
from __future__ import annotations
import re
import unicodedata

from rapidfuzz import fuzz, process

_SUFFIX_RE = re.compile(r'\b(jr|sr|ii|iii|iv|v)\b\.?', re.IGNORECASE)
_PUNCT_RE  = re.compile(r"['\-\.]")
_SPACE_RE  = re.compile(r'\s+')


def normalize_name(name: str) -> str:
    """Lowercase, strip punctuation/suffixes, collapse whitespace."""
    name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode()
    name = name.lower()
    name = _SUFFIX_RE.sub('', name)
    name = _PUNCT_RE.sub('', name)
    name = _SPACE_RE.sub(' ', name).strip()
    return name


def match_player(
    fp_name: str,
    db_players: list[tuple[str, str]],
    threshold: int = 85,
) -> str | None:
    """Return gsis_id for the best fuzzy match of fp_name against db_players.

    db_players is a list of (gsis_id, normalized_name) tuples.
    Returns None if no match exceeds threshold.
    """
    if not db_players:
        return None
    norm = normalize_name(fp_name)
    names = [name for _, name in db_players]

    # Exact match first
    for gsis_id, db_name in db_players:
        if db_name == norm:
            return gsis_id

    # Fuzzy match
    result = process.extractOne(norm, names, scorer=fuzz.token_sort_ratio)
    if result is None or result[1] < threshold:
        return None
    return db_players[result[2]][0]
