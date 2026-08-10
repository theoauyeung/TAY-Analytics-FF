"""Ingest ADP from ESPN unofficial Fantasy API."""
from __future__ import annotations
import requests
import duckdb

from tay.db import get_conn, init_schema

ESPN_ADP_URL = (
    "https://fantasy.espn.com/apis/v3/games/ffl/seasons/{season}"
    "/segments/0/leaguedefaults/3?view=kona_player_info"
)

ESPN_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://fantasy.espn.com/",
}


def fetch_espn_adp(season: int) -> list[dict]:
    """Fetch ESPN ADP data for a given season. Returns list of player entries."""
    url = ESPN_ADP_URL.format(season=season)
    try:
        resp = requests.get(url, headers=ESPN_HEADERS, timeout=30)
    except requests.RequestException as exc:
        print(f"  ESPN request failed: {exc} — skipping")
        return []

    if resp.status_code != 200:
        print(f"  ESPN API returned {resp.status_code} — skipping")
        return []

    try:
        data = resp.json()
    except ValueError:
        print("  ESPN response is not valid JSON — skipping")
        return []

    players = data.get("players", [])
    if not players:
        print("  ESPN response contained no 'players' key — skipping")
    return players


def ingest(season: int = 2026, format_: str = "ppr", db_path=None) -> None:
    conn = get_conn(db_path) if db_path else get_conn()
    init_schema(conn)

    print(f"Fetching ESPN ADP for {season}...")
    raw = fetch_espn_adp(season)
    if not raw:
        print("  No ESPN data returned.")
        conn.close()
        return

    inserted = 0
    for entry in raw:
        player_pool = entry.get("playerPoolEntry", {})
        # ESPN player id lives at playerPoolEntry.playerId
        espn_id = str(player_pool.get("playerId", ""))
        adp_val = player_pool.get("averageDraftPosition")
        if not espn_id or espn_id == "" or adp_val is None:
            continue

        # espn_id in players table is VARCHAR
        row = conn.execute(
            "SELECT gsis_id FROM players WHERE espn_id = ?", [espn_id]
        ).fetchone()
        if not row:
            continue

        conn.execute(
            """
            INSERT OR REPLACE INTO adp (gsis_id, season, platform, format, adp, rank)
            VALUES (?, ?, 'espn', ?, ?, ?)
            """,
            [row[0], season, format_, float(adp_val), round(adp_val)],
        )
        inserted += 1

    conn.commit()
    conn.close()
    print(f"ESPN ADP: {inserted:,} rows inserted")
