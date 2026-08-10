"""Ingest player metadata and ADP from Sleeper API (free, no auth required)."""
from __future__ import annotations
import time
from pathlib import Path
import requests
import duckdb

from tay.db import get_conn, init_schema
from tay.ingestion.player_ids import map_sleeper_ids

SLEEPER_PLAYERS_URL = "https://api.sleeper.app/v1/players/nfl"


def fetch_all_players() -> list[dict]:
    """Fetch all NFL players from Sleeper. Returns list of player dicts."""
    print("Fetching Sleeper player registry...")
    resp = requests.get(SLEEPER_PLAYERS_URL, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return list(data.values())


def ingest_adp_from_sleeper_players(
    conn: duckdb.DuckDBPyConnection,
    players: list[dict],
    season: int,
    format_: str = "ppr",
) -> int:
    """Write Sleeper player ADP (search_rank) into the adp table."""
    inserted = 0
    for p in players:
        sleeper_id = p.get("player_id")
        adp_val = p.get("search_rank")
        if not sleeper_id or not adp_val:
            continue

        # Find gsis_id from sleeper_id we already mapped
        row = conn.execute(
            "SELECT gsis_id FROM players WHERE sleeper_id = ?", [sleeper_id]
        ).fetchone()
        if not row:
            continue
        gsis_id = row[0]

        conn.execute(
            """
            INSERT OR REPLACE INTO adp (gsis_id, season, platform, format, adp, rank)
            VALUES (?, ?, 'sleeper', ?, ?, ?)
            """,
            [gsis_id, season, format_, float(adp_val), int(adp_val)],
        )
        inserted += 1

    conn.commit()
    return inserted


def ingest(
    season: int = 2026,
    db_path=None,
) -> None:
    conn = get_conn(db_path) if db_path else get_conn()
    init_schema(conn)

    players = fetch_all_players()
    print(f"  Fetched {len(players):,} Sleeper players")

    mapped, unmatched = map_sleeper_ids(conn, players)
    print(f"  ID mapping: {mapped:,} matched, {unmatched:,} unmatched")

    n = ingest_adp_from_sleeper_players(conn, players, season)
    print(f"  ADP rows inserted: {n:,}")

    conn.close()
