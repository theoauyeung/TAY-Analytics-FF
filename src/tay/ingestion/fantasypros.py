"""Ingest consensus ADP from FantasyPros.

Tries the XLS export endpoint first; falls back to scraping the HTML table
if openpyxl is unavailable or the export returns an unexpected content type.
"""
from __future__ import annotations
import io
import time
import warnings
import requests
import pandas as pd
import duckdb

from tay.db import get_conn, init_schema
from tay.ingestion.player_ids import resolve_gsis_id

FP_ADP_EXPORT_URL = "https://www.fantasypros.com/nfl/adp/{format_slug}.php?export=xls"
FP_ADP_HTML_URL = "https://www.fantasypros.com/nfl/adp/{format_slug}.php"

FORMAT_SLUGS = {
    "ppr": "ppr-overall",
}

FP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def _try_excel(resp: requests.Response) -> pd.DataFrame | None:
    """Attempt to parse response bytes as Excel. Returns None on failure."""
    content_type = resp.headers.get("Content-Type", "")
    # Reject if server returned HTML instead of a spreadsheet
    if "html" in content_type:
        return None
    try:
        import openpyxl  # noqa: F401 — presence check only
        df = pd.read_excel(io.BytesIO(resp.content))
        return df
    except (ImportError, Exception):
        return None


def _try_html(slug: str) -> pd.DataFrame | None:
    """Scrape the FantasyPros ADP HTML table as fallback."""
    url = FP_ADP_HTML_URL.format(format_slug=slug)
    try:
        resp = requests.get(url, headers=FP_HEADERS, timeout=30)
        if resp.status_code != 200:
            print(f"    HTML fallback returned {resp.status_code}")
            return None
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            tables = pd.read_html(io.StringIO(resp.text))
        if not tables:
            return None
        # Pick largest table (the ADP table)
        df = max(tables, key=len)
        return df
    except Exception as exc:
        print(f"    HTML fallback failed: {exc}")
        return None


def fetch_fp_adp(format_: str = "ppr") -> pd.DataFrame | None:
    """Fetch FantasyPros ADP for a given scoring format.

    Returns a DataFrame or None if all attempts fail.
    """
    slug = FORMAT_SLUGS.get(format_, "ppr-overall")
    url = FP_ADP_EXPORT_URL.format(format_slug=slug)

    df = None
    try:
        resp = requests.get(url, headers=FP_HEADERS, timeout=30)
        if resp.status_code == 200:
            df = _try_excel(resp)
    except requests.RequestException as exc:
        print(f"    FantasyPros export request failed: {exc}")

    if df is None:
        print(f"    Excel export unavailable for {format_}, trying HTML scrape...")
        df = _try_html(slug)

    return df


def _find_col(df: pd.DataFrame, *candidates: str) -> str | None:
    """Return the first candidate column name that exists in df (case-insensitive)."""
    lower_cols = {c.lower(): c for c in df.columns}
    for name in candidates:
        if name.lower() in lower_cols:
            return lower_cols[name.lower()]
    return None


def ingest(season: int = 2026, db_path=None) -> None:
    conn = get_conn(db_path) if db_path else get_conn()
    init_schema(conn)

    for format_ in ["ppr"]:
        print(f"Fetching FantasyPros ADP ({format_})...")
        try:
            df = fetch_fp_adp(format_)
        except Exception as exc:
            print(f"  Skipping {format_}: {exc}")
            continue

        if df is None:
            print(f"  No data for {format_}, skipping.")
            continue

        # Resolve column names flexibly
        name_col = _find_col(df, "Player Name", "Player", "Name")
        pos_col = _find_col(df, "POS", "Position", "Pos")
        team_col = _find_col(df, "Team", "TM")
        adp_col = _find_col(df, "AVG", "ADP", "Avg")
        rank_col = _find_col(df, "RK", "Rank", "Rk", "#")

        if name_col is None or adp_col is None:
            print(f"  Could not identify required columns in {format_} table. Skipping.")
            print(f"  Columns found: {list(df.columns)}")
            continue

        inserted = 0
        for _, row in df.iterrows():
            name = str(row[name_col]).strip()
            pos = str(row[pos_col]).strip()[:2].upper() if pos_col else ""
            team = str(row[team_col]).strip() if team_col else ""
            adp_val = row[adp_col]
            rank_val = row[rank_col] if rank_col else None

            if not name or name.lower() in ("nan", "player", "player name"):
                continue
            try:
                adp_float = float(adp_val)
            except (TypeError, ValueError):
                continue

            # Strip team suffix sometimes appended to name, e.g. "Patrick Mahomes KC"
            if team and name.endswith(f" {team}"):
                name = name[: -len(team) - 1].strip()

            gsis_id = resolve_gsis_id(name, pos, team, conn)
            if not gsis_id:
                continue

            rank_int = None
            if rank_val is not None:
                try:
                    rank_int = int(float(rank_val))
                except (TypeError, ValueError):
                    pass

            conn.execute(
                """
                INSERT OR REPLACE INTO adp (gsis_id, season, platform, format, adp, rank)
                VALUES (?, ?, 'fantasypros', ?, ?, ?)
                """,
                [gsis_id, season, format_, adp_float, rank_int],
            )
            inserted += 1

        conn.commit()
        print(f"  FantasyPros {format_}: {inserted:,} rows inserted")
        time.sleep(1)  # polite rate limiting

    conn.close()
