"""Ingest consensus redraft rankings from FantasyCalc (free, no auth required).

FantasyCalc aggregates trade values and consensus rankings across the fantasy
community. The `overallRank` field is a strong proxy for PPR ADP.
"""
from __future__ import annotations
import requests
import duckdb

from tay.db import get_conn, init_schema

FC_URL = (
    "https://api.fantasycalc.com/values/current"
    "?isDynasty=false&numQbs=1&numTeams=12&ppr=1&isRookie=false"
)

FC_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
}


def fetch_fc_rankings() -> list[dict]:
    resp = requests.get(FC_URL, headers=FC_HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json()


def ingest(season: int = 2026, db_path=None) -> None:
    conn = get_conn(db_path) if db_path else get_conn()
    init_schema(conn)

    print("Fetching FantasyCalc consensus rankings...")
    data = fetch_fc_rankings()
    print(f"  {len(data)} players returned")

    inserted = 0
    unmatched = 0
    for entry in data:
        player = entry.get("player", {})
        espn_id = player.get("espnId")
        overall_rank = entry.get("overallRank")
        if not espn_id or not overall_rank:
            continue

        row = conn.execute(
            "SELECT gsis_id FROM players WHERE espn_id = ?", [str(espn_id)]
        ).fetchone()
        if not row:
            unmatched += 1
            continue

        conn.execute(
            """
            INSERT OR REPLACE INTO adp (gsis_id, season, platform, format, adp, rank)
            VALUES (?, ?, 'fantasycalc', 'ppr', ?, ?)
            """,
            [row[0], season, float(overall_rank), int(overall_rank)],
        )
        inserted += 1

    conn.commit()
    conn.close()
    print(f"  FantasyCalc: {inserted} rows inserted, {unmatched} unmatched")
