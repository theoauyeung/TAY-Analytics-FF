"""Scrape Pro Football Reference for combine data (athleticism metrics)."""
from __future__ import annotations
import time
from pathlib import Path
import cloudscraper
from bs4 import BeautifulSoup
import pandas as pd
import duckdb

from tay.db import get_conn, init_schema
from tay.ingestion.player_ids import resolve_gsis_id

PFR_COMBINE_URL = "https://www.pro-football-reference.com/draft/{year}-combine.htm"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

_FLOAT = lambda v: float(v) if v and v != "--" else None
_INT   = lambda v: int(v) if v and v != "--" else None


def scrape_combine_year(year: int) -> list[dict]:
    """Scrape PFR combine page for one year. Returns list of player dicts."""
    url = PFR_COMBINE_URL.format(year=year)
    try:
        # Try with cloudscraper first (handles Cloudflare)
        scraper = cloudscraper.create_scraper()
        resp = scraper.get(url, timeout=30)
        if resp.status_code == 403:
            print(f"  PFR {year}: Blocked by Cloudflare (HTTP 403)")
            return []
        if resp.status_code != 200:
            print(f"  PFR {year}: HTTP {resp.status_code}")
            return []

        soup = BeautifulSoup(resp.text, "lxml")
        table = soup.find("table", id="combine")
        if not table:
            print(f"  PFR {year}: No combine table found")
            return []

        rows = []
        tbody = table.find("tbody")
        if not tbody:
            return []

        for tr in tbody.find_all("tr"):
            if tr.get("class") and "thead" in tr.get("class"):
                continue
            cells = {td.get("data-stat"): td.get_text(strip=True) for td in tr.find_all(["td", "th"])}
            if not cells.get("player"):
                continue

            # Extract pfr_id from player link
            pfr_id = None
            player_td = tr.find("td", {"data-stat": "player"})
            if player_td:
                link = player_td.find("a")
                if link and link.get("href"):
                    pfr_id = link["href"].split("/")[-1].replace(".htm", "")

            if not pfr_id:
                continue

            rows.append({
                "name":       cells.get("player", ""),
                "position":   cells.get("pos", ""),
                "pfr_id":     pfr_id,
                "season":     year,
                "forty_yard": _FLOAT(cells.get("forty_yd")),
                "vertical":   _FLOAT(cells.get("vertical")),
                "broad_jump": _FLOAT(cells.get("broad_jump")),
                "cone":       _FLOAT(cells.get("cone")),
                "shuttle":    _FLOAT(cells.get("shuttle")),
                "bench_reps": _INT(cells.get("bench_reps")),
                "height":     _INT(cells.get("ht")),
                "weight":     _INT(cells.get("wt")),
            })
        return rows
    except Exception as e:
        print(f"  PFR {year}: Error during scraping: {e}")
        return []


def ingest(
    start: int = 2005,
    end: int = 2025,
    db_path=None,
) -> None:
    conn = get_conn(db_path) if db_path else get_conn()
    init_schema(conn)
    total = 0

    for year in range(start, end + 1):
        print(f"  PFR combine {year}...")
        rows = scrape_combine_year(year)
        for r in rows:
            gsis_id = resolve_gsis_id(r["name"], r["position"], "", conn) if r["name"] else None
            pfr_id = r["pfr_id"]
            if not pfr_id:
                continue

            # Update pfr_id on players table if we resolved the gsis_id
            if gsis_id:
                conn.execute(
                    "UPDATE players SET pfr_id = ? WHERE gsis_id = ?",
                    [pfr_id, gsis_id]
                )

            conn.execute("""
                INSERT OR REPLACE INTO combine_data
                    (gsis_id, pfr_id, name, season, position,
                     forty_yard, vertical, broad_jump, cone, shuttle, bench_reps,
                     height, weight)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                gsis_id, pfr_id, r["name"], r["season"], r["position"],
                r["forty_yard"], r["vertical"], r["broad_jump"],
                r["cone"], r["shuttle"], r["bench_reps"],
                r["height"], r["weight"],
            ])
            total += 1

        conn.commit()
        time.sleep(1)  # PFR rate limit

    conn.close()
    print(f"PFR combine: {total:,} rows inserted")


if __name__ == "__main__":
    ingest()
