"""Cross-source player ID unification."""
from __future__ import annotations
import re
import csv
from pathlib import Path
import duckdb

from tay.db import get_conn

RAW_DIR = Path(__file__).parent.parent.parent.parent / "data" / "raw"

_SUFFIX_RE = re.compile(
    r"\s+(jr\.?|sr\.?|ii|iii|iv|v)$", re.IGNORECASE
)


def normalize_name(name: str) -> str:
    """Lowercase, strip name suffixes (Jr, Sr, II, III)."""
    return _SUFFIX_RE.sub("", name.strip()).lower()


def resolve_gsis_id(
    name: str,
    position: str,
    team: str,
    conn: duckdb.DuckDBPyConnection,
) -> str | None:
    """Attempt to find a gsis_id for (name, position, team).

    Tries:
    1. Exact name + position + team match
    2. Normalized name + position match (ignores team — players change teams)
    """
    # 1. Exact match
    row = conn.execute(
        "SELECT gsis_id FROM players WHERE name = ? AND position = ? AND team = ?",
        [name, position, team],
    ).fetchone()
    if row:
        return row[0]

    # 2. Normalized name + position
    normed = normalize_name(name)
    rows = conn.execute(
        "SELECT gsis_id, name FROM players WHERE position = ?", [position]
    ).fetchall()
    for gsis_id, db_name in rows:
        if normalize_name(db_name) == normed:
            return gsis_id

    return None


def map_sleeper_ids(
    conn: duckdb.DuckDBPyConnection,
    sleeper_players: list[dict],
) -> tuple[int, int]:
    """Map Sleeper player IDs to gsis_ids. Returns (mapped, unmatched) counts."""
    mapped = 0
    unmatched = []

    for p in sleeper_players:
        name = p.get("full_name", "")
        pos = p.get("position", "")
        team = p.get("team", "")
        sleeper_id = p.get("player_id", "")
        gsis_id = p.get("gsis_id")  # Sleeper sometimes provides gsis_id directly

        if not gsis_id:
            gsis_id = resolve_gsis_id(name, pos, team, conn)

        if gsis_id:
            conn.execute(
                "UPDATE players SET sleeper_id = ? WHERE gsis_id = ?",
                [sleeper_id, gsis_id],
            )
            mapped += 1
        else:
            unmatched.append({"name": name, "position": pos, "team": team, "sleeper_id": sleeper_id})

    conn.commit()

    if unmatched:
        out = RAW_DIR / "unmatched_sleeper.csv"
        with open(out, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["name", "position", "team", "sleeper_id"])
            writer.writeheader()
            writer.writerows(unmatched)
        print(f"  {len(unmatched)} unmatched players written to {out}")

    return mapped, len(unmatched)
