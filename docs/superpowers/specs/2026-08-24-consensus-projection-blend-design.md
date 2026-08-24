# Consensus Projection Blend Design

**Goal:** Replace pure ML projections with a weighted blend of FantasyPros expert consensus (65%) and our ML model (35%), fixing systematic failures for injury returnees, rookies, and opportunity-dependent players.

**Architecture:** Scrape FantasyPros → store in `consensus_projections` table → blend step writes `blended_projection` to `projections` → VOR uses `blended_projection` → rankings unchanged.

**Tech Stack:** Python/requests/BeautifulSoup, rapidfuzz, DuckDB, existing FastAPI/React stack.

---

## Problem Being Solved

The ML model has three structural blind spots:
1. **Injury returnees** — sees bad stats from injured season, projects low (Rashee Rice: ADP=16, model rank=129)
2. **Rookies and new starters** — no NFL history → low projection (Omarion Hampton: ADP=23, model rank=73)
3. **Opportunity-dependent players** — projects based on raw stats without knowing situation changes (Kyren Williams: ADP=38, model rank=10; Rico Dowdle: ADP=119, model rank=31)

Expert consensus projections (FantasyPros aggregates ~50 analysts) already account for all three. The ML model adds signal where it genuinely has an edge: WOPR trends, snap share changes, consistency patterns, schedule strength.

---

## Data Source

**FantasyPros consensus projections** — public, no auth required.

URLs (one per position):
- `https://www.fantasypros.com/nfl/projections/qb.php?week=draft&scoring=PPR`
- `https://www.fantasypros.com/nfl/projections/rb.php?week=draft&scoring=PPR`
- `https://www.fantasypros.com/nfl/projections/wr.php?week=draft&scoring=PPR`
- `https://www.fantasypros.com/nfl/projections/te.php?week=draft&scoring=PPR`

Stat columns scraped per position and PPR points computed from them (not taken from FantasyPros FPTS column, which may use different scoring settings):

| Position | Columns |
|----------|---------|
| QB | pass_yds, pass_tds, ints, rush_yds, rush_tds |
| RB | rush_yds, rush_tds, receptions, rec_yds, rec_tds |
| WR/TE | receptions, rec_yds, rec_tds, rush_yds, rush_tds |

PPR scoring applied: pass_yds×0.04 + pass_tds×4 + ints×(−2) + rush_yds×0.1 + rush_tds×6 + receptions×1.0 + rec_yds×0.1 + rec_tds×6.

---

## Schema

### New table: `consensus_projections`

```sql
CREATE TABLE consensus_projections (
    gsis_id     VARCHAR NOT NULL,
    season      INTEGER NOT NULL,
    source      VARCHAR NOT NULL DEFAULT 'fantasypros',
    pass_yards  DOUBLE,
    pass_tds    DOUBLE,
    interceptions DOUBLE,
    rush_yards  DOUBLE,
    rush_tds    DOUBLE,
    receptions  DOUBLE,
    rec_yards   DOUBLE,
    rec_tds     DOUBLE,
    points      DOUBLE,  -- computed PPR total
    scraped_at  TIMESTAMP DEFAULT current_timestamp,
    PRIMARY KEY (gsis_id, season, source)
)
```

### Modified table: `projections`

Two new columns added via `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`:
- `consensus_projection DOUBLE` — raw FantasyPros PPR points
- `blended_projection DOUBLE` — 0.65×consensus + 0.35×mean_projection

---

## Components

### `scripts/ingest_fantasypros.py`

Single script that does three things in sequence:

1. **Scrape** — fetches all four position pages, parses stat columns, computes PPR points per player.

2. **Match names to GSIS IDs** — normalizes names (lowercase, strip punctuation, drop suffixes like Jr./Sr.), then:
   - Exact match against `players.name`
   - Fuzzy match via `rapidfuzz.fuzz.token_sort_ratio` ≥ 85
   - Below threshold: skip + log to stderr as `UNMATCHED: <fp_name>`
   
3. **Upsert** — writes matched rows to `consensus_projections` via `ON CONFLICT DO UPDATE`.

### `src/tay/projections/blend.py`

```python
CONSENSUS_WEIGHT = 0.65
ML_WEIGHT        = 0.35

def blend_projections(conn, season, model_version) -> int:
    """Write consensus_projection and blended_projection to projections table.
    
    Falls back to ML-only (blended_projection = mean_projection) when no
    consensus row exists for a player.
    """
```

Runs a single UPDATE FROM joining `projections` with `consensus_projections`. Returns rows updated.

### Updated `src/tay/valuation/vor.py`

`compute_vor` switches from `mean_projection` to `COALESCE(blended_projection, mean_projection)` — one-line change. No interface change.

### `scripts/ingest_fantasypros.py` orchestrates the full refresh

After scraping and upserting consensus data, the script calls `blend_projections()` and `compute_vor()` in sequence so one command fully refreshes rankings:

```
scrape FP → match names → upsert consensus_projections →
blend_projections() → compute_vor() → done
```

Running `uv run python scripts/ingest_fantasypros.py --season 2026` is the only command needed to go from fresh FantasyPros data to updated rankings.

---

## Blend Formula

```
blended_projection = 0.65 × consensus_projection + 0.35 × mean_projection
```

**Fallback:** When `consensus_projection IS NULL` (player not on FantasyPros — depth chart players, obscure backups), `blended_projection = mean_projection`. These players stay in the rankings but are ML-only.

**Constants** live in `blend.py` as module-level values. Not configurable at runtime — change requires a code edit and is intentional (not a knob operators should twirl casually).

---

## Player Name Matching

FantasyPros display names differ from nflverse names in predictable ways:
- Suffixes: "Ja'Marr Chase" vs "Ja'Marr Chase" (usually fine), "D.K. Metcalf" vs "DK Metcalf"
- Apostrophes, hyphens: normalized away before matching
- Same-name conflicts (e.g., two players named "Mike Williams"): fuzzy match picks the one with higher score; if tied, skip both and log

Unmatched players are printed to stderr during ingestion. Operators review the log after each scrape run.

---

## Testing

- `tests/projections/test_blend.py`: unit tests for `blend_projections` — verifies weighted math, fallback to ML-only, and that `vor.py` uses `blended_projection`.
- `tests/test_name_match.py`: unit tests for the name normalization + fuzzy matching logic with known tricky names (D.K. Metcalf, Ja'Marr Chase, Travis Etienne Jr.).
- No HTTP calls in tests — scraping is tested via fixture HTML files (saved snapshots of FantasyPros pages).

---

## Operational Notes

- **Re-scrape cadence:** Run once before draft season, then whenever FantasyPros updates (weekly during preseason). Single command: `uv run python scripts/ingest_fantasypros.py --season 2026`.
- **Idempotent:** Re-running overwrites existing consensus rows via ON CONFLICT — safe to run multiple times.
- **No UI changes needed** — the rankings API already serves `mean_projection` (which will now reflect the blended value via `blended_projection`). A future enhancement could surface the consensus vs ML divergence in the UI.
