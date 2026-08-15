"""Ingest ADP from ESPN Fantasy API."""
from __future__ import annotations
import json
import requests
import duckdb

from tay.db import get_conn, init_schema

# lm-api-reads subdomain is not behind Cloudflare and returns JSON directly
ESPN_ADP_URL = (
    "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl"
    "/seasons/{season}/segments/0/leaguedefaults/3?view=kona_player_info"
)

ESPN_HEADERS = {
    "User-Agent": "ESPN/7.0 CFNetwork/1490.0.4 Darwin/23.2.0",
    "Accept": "application/json",
}

# Request all skill positions (slotIds: 0=QB,2=RB,4=WR,6=TE)
_FANTASY_FILTER = json.dumps({
    "players": {
        "filterSlotIds": {"value": [0, 2, 4, 6]},
        "limit": 500,
        "sortDraftRanks": {"sortPriority": 1, "sortAsc": True, "value": "PPR"},
        "filterRanksForRankTypes": {"value": ["PPR"]},
    }
})


def fetch_espn_adp(season: int) -> list[dict]:
    """Fetch ESPN PPR draft rankings. Returns list of player entries."""
    url = ESPN_ADP_URL.format(season=season)
    headers = {**ESPN_HEADERS, "x-fantasy-filter": _FANTASY_FILTER}
    try:
        resp = requests.get(url, headers=headers, timeout=30)
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
    unmatched = 0
    for entry in raw:
        espn_id = str(entry.get("id", ""))
        if not espn_id or espn_id == "None":
            continue

        # PPR rank lives at player.draftRanksByRankType.PPR.rank
        player_info = entry.get("player", {})
        ppr_rank = (
            player_info
            .get("draftRanksByRankType", {})
            .get("PPR", {})
            .get("rank")
        )
        if ppr_rank is None or ppr_rank > 400:
            continue

        row = conn.execute(
            "SELECT gsis_id FROM players WHERE espn_id = ?", [espn_id]
        ).fetchone()
        if not row:
            unmatched += 1
            continue

        conn.execute(
            """
            INSERT OR REPLACE INTO adp (gsis_id, season, platform, format, adp, rank)
            VALUES (?, ?, 'espn', ?, ?, ?)
            """,
            [row[0], season, format_, float(ppr_rank), int(ppr_rank)],
        )
        inserted += 1

    conn.commit()
    conn.close()
    print(f"ESPN ADP: {inserted:,} rows inserted, {unmatched} unmatched")
