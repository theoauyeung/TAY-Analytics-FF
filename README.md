# TAY Analytics FF

A fantasy football projection and draft tool. Neural nets trained per position on historical PPR stats, ranked by value over replacement, served through a FastAPI backend and React UI.

## How it works

Data flows in one direction: ingest → features → model → valuation → API.

**Ingest.** Historical NFL play-by-play comes from `nfl-data-py` and `nflfastr`. ADP comes from two sources: FantasyCalc (used for veteran comps during rookie projection) and ESPN (used in the final ranking blend). Both are refreshed every time you run `refresh_projections.py`.

**Features.** Player features are EWMA-smoothed over recent seasons — targets, carries, snap share, efficiency metrics. Team features (scheme cluster, pass rate, target distribution) are computed separately and joined at inference time. See `src/tay/features/` for the full pipeline.

**Model.** Four separate neural nets — one per position (QB, RB, WR, TE). Each predicts seasonal PPR fantasy points. Trained on 2015–2024 seasons, 150 epochs, with Monte Carlo dropout for confidence intervals. Checkpoints live in `models/`.

**Rookie cold-start.** Rookies have all-zero historical features, so the model is nearly blind to them. The fix: for each rookie, find veterans within ±20 picks on FantasyCalc, take the 60th percentile of their projections as an "ADP-implied anchor," and blend 80% anchor / 20% model. If fewer than 3 comps exist in that window, it falls back to the 7 nearest.

**VOR.** Value over replacement is `(mean_projection - replacement_level) × positional_scarcity_weight`. Replacement level is the projected score of the last rostered player at each position (QB12, RB30, WR30, TE12 in a 12-team league). Scarcity weights reflect draft strategy, not just market rates — QB is discounted at 0.30 because good QBs are available deep into drafts:

```python
{'QB': 0.30, 'RB': 1.0, 'WR': 0.85, 'TE': 0.50}
```

**Injury discounts.** `data/player_flags.json` applies a multiplier to `mean_projection` before VOR runs. Edit this file to reflect current news, then re-run the refresh script:

```json
{
  "injury_discounts": {
    "Ashton Jeanty": 0.65,
    "Josh Jacobs": 0.82
  }
}
```

**Final ranking blend.** The API blends three signals: 55% VOR rank, 35% ESPN ADP, 10% historical draft efficiency (how often players at this ADP have outperformed expectations in past seasons). This is in `src/tay/api/routers/rankings.py` as `_blended_score`.

## Quickstart

```bash
pip install -e ".[dev]"
```

The main DB is `data/ff.duckdb`. The API reads from `tay.db` (a slim export of the 5 tables the API needs). Both are DuckDB files.

To pull fresh ADP and recompute rankings from existing model checkpoints (~8 seconds):

```bash
python scripts/rankings/refresh_projections.py
```

To retrain models from scratch (~4 minutes):

```bash
python scripts/rankings/refresh_projections.py --retrain --epochs 150
```

After either command, rebuild the slim API DB and restart the server:

```bash
# rebuild tay.db from data/ff.duckdb
TAY_DB_PATH=tay.db python -c "
import sys; sys.path.insert(0, 'src')
from tay.db import get_conn, init_schema
# ... or run the export snippet in scripts/build_slim_db.py
"

uvicorn tay.api.app:app --reload
```

The API runs on port 8000. The UI dev server (`ui/`) proxies to it.

## Tuning

**Scarcity weights** are in `src/tay/valuation/vor.py`. Lower a position's weight if its top players rank too high overall. QB at 0.30 is deliberately below market (empirical regression gave 0.82) because the tool assumes late-round QB strategy.

**ADP blend weight** is `_ADP_BLEND_WEIGHT` in `src/tay/api/routers/rankings.py`. Currently 0.35. Raise it if you want rankings to track ADP more closely; lower it if you trust the model over the market.

**Injury flags** live in `data/player_flags.json`. Add any player by their exact name as it appears in the DB (`SELECT name FROM players WHERE name ILIKE '%lastname%'`). The multiplier applies to the raw projection before VOR, so it affects both the player's rank and their tier placement.

## Deployment

API: Render web service. Set `TAY_DB_PATH=tay.db` in the environment. The `tay.db` file is committed to the repo — it's ~5 MB and gets rebuilt whenever rankings change.

UI: Vercel. `ui/vercel.json` has the SPA rewrite rule so direct routes like `/rankings` work.

After any change to rankings logic, the workflow is:
1. Run `refresh_projections.py`
2. Rebuild `tay.db`
3. Commit and push — Render redeploys automatically

## Project layout

```
src/tay/
  ingestion/     # nfl-data-py, FantasyCalc, ESPN, Sleeper ADP pulls
  features/      # EWMA player features, team scheme clusters, snap share
  models/        # neural net architecture, trainer, per-position pipelines
  valuation/     # replacement levels, VOR, tier assignment, ADP delta
  api/           # FastAPI app, routers, schemas
  draft/         # live draft session engine
  simulation/    # Monte Carlo availability simulation

scripts/rankings/
  refresh_projections.py   # main entry point — ADP + projections + valuation

data/
  ff.duckdb          # full local DB
  player_flags.json  # injury/suspension multipliers
  league_settings.json

models/            # trained checkpoint files (one per position)
tay.db             # slim production DB (players, projections, adp, analytics)
ui/                # React frontend
```
