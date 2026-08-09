# TAY Analytics FF — Fantasy Football Analytics & Draft Assistant
**Design Spec · 2026-08-08**

---

## 1. Project Overview

A production-quality fantasy football analytics application combining:
- A multi-layer NFL player projection engine (PyTorch neural networks)
- A live draft decision engine with contextual recommendations
- A clean, information-dense React UI

**Live target season:** 2026  
**Training data:** 2005–2025 NFL seasons  
**Deployment:** Local (FastAPI + React, localhost)

---

## 2. Core Objectives

The application must answer three questions exceptionally well:

1. **"How good will this player be?"** — Projection engine
2. **"How valuable is this player in my league?"** — VOR + positional scarcity + scoring settings
3. **"Should I draft this player right now?"** — Roster construction + remaining player pool + scarcity + future availability + opportunity cost

The third question is the ultimate goal. This is a draft decision engine with a fantasy football UI, not a rankings website.

---

## 3. Tech Stack

| Layer | Technology |
|-------|-----------|
| ML framework | PyTorch (neural networks) |
| Data pipeline | Python + R (NFLFastR) |
| Database | DuckDB (file-based, analytical) |
| Backend API | FastAPI + Pydantic v2 |
| Frontend | React 18 + TypeScript + Vite |
| Data fetching | TanStack Query |
| Charts | Recharts |
| Styling | Tailwind CSS |

---

## 4. Project Structure

```
TAY Analytics FF/
├── data/
│   ├── raw/              # downloaded source files (NFLFastR parquet, PFR CSVs, etc.)
│   ├── processed/        # cleaned, merged, feature-engineered tables
│   └── ff.duckdb         # single DuckDB file — all persistent storage
│
├── src/
│   ├── ingestion/        # data pull scripts (R + Python per source)
│   ├── features/         # feature engineering pipeline
│   ├── models/           # PyTorch model definitions + training scripts
│   │   ├── team/         # team environment model
│   │   ├── opportunity/  # position-specific opportunity model
│   │   ├── efficiency/   # position-specific efficiency model
│   │   ├── touchdown/    # TD regression model
│   │   ├── injury/       # availability model
│   │   └── rookie/       # rookie projection module
│   ├── valuation/        # VOR, replacement level, scarcity, tiers
│   ├── simulation/       # Monte Carlo engine
│   ├── draft/            # live draft decision engine
│   ├── api/              # FastAPI app + route definitions
│   └── schemas/          # shared Pydantic contracts (single source of truth)
│
├── ui/                   # React frontend
│   ├── src/
│   │   ├── components/   # shared UI components
│   │   ├── pages/        # page-level components
│   │   ├── state/        # application state (draft state, roster state)
│   │   ├── data/         # mock data + data interfaces
│   │   ├── hooks/        # TanStack Query hooks
│   │   └── types/        # TypeScript interfaces mirroring backend schemas
│   └── ...
│
├── scripts/              # CLI: pull data, train models, run backtest
├── tests/
├── docs/
└── notebooks/            # exploratory analysis only, never production code
```

**Key principle:** All Python modules communicate exclusively through schemas defined in `src/schemas/`. No module imports another module's internals. DuckDB is shared state. This makes every component independently replaceable.

---

## 5. Architecture Pattern: Modular Monolith with Typed Contracts

One Python package with strict module boundaries enforced by Pydantic schemas. The projection engine, valuation engine, and draft engine are all independently replaceable without touching each other — they only share data contracts. Single process to run locally, but interfaces are already clean for future service extraction.

```
Data Sources
    ↓
Ingestion (per-source modules)
    ↓
DuckDB (raw + processed tables)
    ↓
Feature Engineering
    ↓
[Team Model] → [Opportunity Model] → [Efficiency Model] → [TD Model] → [Injury Model]
    ↓
Fantasy Projection (mean, median, floor, ceiling, percentiles)
    ↓
Valuation Engine (VOR, replacement level, scarcity, tiers, ADP delta)
    ↓
Monte Carlo Simulation
    ↓
DuckDB (projections table — precomputed)
    ↓
Draft Decision Engine (stateless, reads precomputed outputs + draft state)
    ↓
FastAPI
    ↓
React UI
```

---

## 6. Data Sources

| Source | Method | Data |
|--------|--------|------|
| NFLFastR | R script → parquet | Play-by-play, EPA, CPOE, pressure, air yards (2005–2025) |
| nfl-data-py | Python package | Rosters, schedules, injuries, draft picks, depth charts |
| Pro Football Reference | Python scraper | Historical stats, combine data, OL grades, coaching history |
| Sleeper API | Python REST | Player metadata, ADP, injury status |
| ESPN API (unofficial) | Python REST | ESPN ADP (primary baseline), league settings |
| FantasyPros | Python scraper | Consensus rankings, multi-platform ADP comparison |

**Player ID unification:** A dedicated cross-source ID mapping layer normalizes player identities across all sources before any downstream use. This is built first and maintained as new sources are added.

**Core DuckDB tables:**
- `players` — master registry with cross-source ID mapping
- `play_by_play` — NFLFastR data partitioned by season
- `player_season_stats` — aggregated per-player per-season stats
- `team_season_stats` — team-level environment metrics per season
- `rosters` — weekly depth charts and snap counts
- `draft_picks` — historical NFL draft capital
- `combine_data` — athleticism metrics
- `adp` — ADP snapshots by platform and date
- `projections` — precomputed model outputs
- `draft_sessions` — saved draft history

**Leakage prevention:** Every training row includes a `season` column. Feature engineering always filters to `season < target_season`. No future information ever enters a training example.

---

## 7. Projection Engine

A sequential pipeline of five position-specific PyTorch models. Training target is always the *following* season's stats given current-season inputs.

### Layer 1 — Team Environment Model
- **Input:** historical pace, pass rate, OC/HC tendencies, OL metrics, Vegas implied totals, offseason changes
- **Output:** projected team plays, pass/rush attempts, red-zone possessions, team TDs, pace, pass rate over expectation

### Layer 2 — Opportunity Model (position-specific)
- **Input:** team environment outputs + player snap share history, depth chart position, vacated opportunity from departing players, coaching tendencies
- **Output per player:** targets, carries, routes run, red-zone/goal-line touches — separate from efficiency

### Layer 3 — Efficiency Model (position-specific)
- **Input:** opportunity outputs + player historical efficiency, athleticism, CPOE, YAC, separation, EPA/play
- **Output per player:** yards/target, catch rate, yards/carry, TD rate, completion %, INT rate

### Layer 4 — Touchdown Model
- **Input:** team TD opportunities + player red-zone/goal-line share + historical TD rate
- **Output:** expected TDs with regression toward the mean (prevents outlier TD seasons from dominating)

### Layer 5 — Availability Model
- **Input:** age, injury history, injury type, games missed last 3 seasons
- **Output:** expected games played, P(miss 4+ games)
- **Weight:** minor influence — injuries are too volatile to heavily penalize

### Rookie Module (parallel path, merges at Layer 2)
Dedicated model using college production, draft capital, athleticism, RAS, landing spot. Produces a prior distribution using historical rookie comps. Bayesian shrinkage pulls rookie projections toward position-specific historical priors and gradually incorporates NFL information as data accumulates.

### Aging Curves
Position-specific multiplicative adjustment applied before the opportunity model. A 30-year-old RB's inputs are discounted relative to a 25-year-old with identical prior stats.

### Final Projection Output (per player)
```
mean_projection, median_projection, floor, ceiling, std_dev
p10, p25, p50, p75, p90
boom_probability, bust_probability, weekly_consistency
```
Applied against league scoring settings to convert statistical projections to fantasy points.

---

## 8. Valuation Engine

Separate module consuming projection outputs. Never touches model internals — only reads from the `projections` table via the shared schema.

### Step 1 — Replacement Level
Calculated dynamically from league settings. League size, starting slots, flex eligibility, and bench depth all affect replacement level per position. Every league configuration produces different replacement levels.

### Step 2 — Value Over Replacement (VOR)
`VOR = player projected points − replacement level at their position`
Primary ranking metric. Replaces raw projected points for all valuation and draft decisions.

### Step 3 — Positional Scarcity Score
Slope of the VOR curve from picks 1–N at each position. Steep dropoff = high scarcity = earlier positional urgency. Recalculated live during draft as players are taken.

### Step 4 — Tier Construction
Gap analysis on the VOR curve. Large VOR gaps = tier breaks. Tiers are position-specific and drive the draft UI visualization.

### Step 5 — Market Value Comparison
`Model Value vs Market Value = VOR rank − ADP rank`
ESPN ADP is the primary baseline. FantasyPros consensus is the secondary comparison. Surfaces undervalued and overvalued players.

### Step 6 — Uncertainty Adjustment
Players with identical VOR but different standard deviations have different draft values depending on roster context. Late-draft picks favor ceiling. Early picks favor floor. The valuation engine tags each player with a volatility score.

---

## 9. Draft Decision Engine

The core of the application. Stateless — receives precomputed projection/valuation outputs + current draft state, returns a ranked recommendation list. Never retrains models. All recommendation logic operates on precomputed outputs in DuckDB.

### Input Schema (Draft State)
```
league_settings, scoring_format, roster_config
current_round, current_pick, user_draft_position
picks_until_next_turn
all_drafted_players
available_players
user_current_roster
```

### Draft Score Components (per available player)
1. **Base Value** — VOR adjusted for positional scarcity at current board state
2. **Roster Fit Score** — marginal value added to this specific user roster; accounts for starter slots filled, flex eligibility, bye conflicts, bench depth
3. **Future Availability Probability** — P(player still available at user's next pick); modeled from ADP distribution + picks remaining + positional run likelihood; powers "May Not Make It Back" feature
4. **Opportunity Cost** — expected VOR of the best alternative player, weighted by their future availability
5. **Positional Urgency** — live scarcity score at that position given current board
6. **Risk Adjustment** — volatility score applied by roster context (early = floor, late = ceiling)

### Draft Score Formula
```
Draft Score = BaseValue × RosterFit × (1 + PositionalUrgency)
              − OpportunityCost × FutureAvailability
              ± RiskAdjustment
```
Weights are configurable and tuned via the backtesting framework.

### QB Scoring Note
In a standard 1-QB league, the engine explicitly recognizes that QBs have lower marginal draft value because only one starter is required and replacement-level QB production is relatively strong. In Superflex/2-QB formats, QB scarcity fundamentally changes their Draft Score. The engine is format-aware and applies the correct replacement level per format.

### Output Schema (Recommendation State)
```
top_pick: {
  player, draft_score, projection, vor, scarcity,
  roster_fit, future_availability_pct, explanation[]
}
alternatives: [ 2–4 players with same fields ]
positional_needs: { QB, RB, WR, TE, FLEX — ranked by urgency }
positional_scarcity: { per-position scarcity score + tiers remaining }
may_not_make_it_back: [ players with >70% draft probability before next pick ]
board_state_summary: { picks_until_next, rounds_remaining }
```

### Explanation Generation
`explanation[]` is constructed from actual factor values driving the score — not template text. The dominant factor leads the explanation. Each factor above a significance threshold contributes one sentence.

---

## 10. Monte Carlo Simulation

Runs thousands of simulated seasons per player. For each simulation draws:
- Games played (from availability distribution)
- Opportunities (from opportunity model distribution)
- Efficiency (from efficiency model distribution)
- TDs (from TD model distribution)

Aggregates to produce the full projection distribution (p10–p90, boom/bust probabilities). Also powers draft simulation — runs thousands of simulated drafts to estimate:
- Expected roster value at each draft position
- Strategy comparison (Zero RB, Hero RB, WR-heavy, Balanced, etc.)
- Championship probability estimate

---

## 11. FastAPI Layer

```
GET  /players                    — full player list with projections + VOR + ADP
GET  /players/{id}               — player detail (distribution, comps, risk factors)
GET  /rankings                   — ranked list, sortable by projection/VOR/ADP/model rank
GET  /tiers/{position}           — tier breakdown for a position

POST /draft/recommend            — hot path: accepts DraftState, returns RecommendationState
POST /draft/simulate             — mock draft simulation with strategy selection
POST /draft/session              — saves draft session to DuckDB
GET  /draft/session/{id}         — retrieves saved session

GET  /scarcity                   — live positional scarcity scores
GET  /league/settings            — saved league config
POST /league/settings            — saves league config

GET  /health
```

**Performance requirement:** `/draft/recommend` must return in under 500ms. All projection outputs are precomputed — no model inference at request time. The endpoint does only in-memory computation on precomputed DuckDB reads.

**CORS:** Configured for `localhost:3000` (React dev server).  
**Docs:** FastAPI's automatic OpenAPI spec at `/docs` serves as the living API contract.

---

## 12. React UI

### Visual Direction
- Dark, premium, analytical, information-dense
- Color palette: near-black background, dark charcoal cards, baby blue accent
- Baby blue used for: active nav, selected tabs, buttons, player highlights, positive signals, hover states
- Typography: strong display font for player names and headings
- Inspiration: flockfantasy.com (information density, ranking tables) with distinct black/blue identity
- Personality: premium fantasy football platform + modern sports media + analytics — not Bloomberg terminal clone

### Tech
- React 18 + TypeScript + Vite
- TanStack Query (data fetching + caching)
- Recharts (projection distributions, scarcity curves)
- Tailwind CSS

### Data Architecture
Mock data is isolated in `ui/src/data/`. UI components consume typed interfaces — they do not care whether data comes from mock JSON, the API, or the live models. Replacing mock data with real API calls requires only updating the TanStack Query hooks, not touching any component.

### TypeScript Interfaces (mirroring backend schemas)
```typescript
Player, Projection, Ranking, DraftState, Roster,
Recommendation, PositionalScarcity, FutureAvailability
```

### Application State
- **Draft State** — maintained in React state/context; updated after every pick; drives all draft-related components simultaneously
- **League Settings** — persisted to localStorage; applied to all valuation calculations
- **Roster State** — derived from Draft State; drives positional need assessment

### Build Order
1. **Rankings + data foundation** — player table, filters, tiers, player detail drawer, shared data types
2. **Draft Assistant** — three-panel layout, live draft state, recommendations, scarcity, May Not Make It Back
3. **Dashboard** — summary cards, movers, values, scarcity overview
4. **Player Explorer** — detailed player view, projection distribution, comps
5. **Remaining pages** — Mock Draft, Roster Analyzer, Settings, Projections

### Pages

**Dashboard** — team summary, model movers, best values, draft trends, scarcity overview, model status

**Rankings** — primary data page
- Controls: Redraft/Best Ball/Dynasty, PPR/Half/Standard, position filter, year
- Dense sortable/filterable table: Rank, Player, Team, Bye, Projection, VOR, ADP, Model Rank, Tier
- Toggleable columns: Floor, Ceiling, Target Share, Rush Share, Snap%, Route%, Red Zone, TD Proj, Games Played, Confidence, ADP Delta
- Tier separators with labels (TIER 1 — ELITE, etc.)
- Player detail drawer (right-side) on row click — projection breakdown, opportunity metrics, efficiency metrics, model assessment with ADP delta explanation

**Draft Assistant** — three-panel desktop layout
- Left: available players table (undrafted only), search, filters, click to draft
- Center: recommendation panel — Draft Score, VOR, ADP, future availability, "WHY?" explanation, 2–4 alternatives with comparison
- Right: my roster by position, positional strength assessment, priority needs
- Top bar: Round/Pick, picks until next selection, player count
- May Not Make It Back component (probability > 64% flagged)
- Positional Scarcity bar chart (viable players remaining)
- Optional draft timer

**Mock Draft** — configured simulation; realistic draft board; user picks + simulated auto-picks for other teams; same Draft State architecture as Draft Assistant

**Roster Analyzer** — post-draft analysis; overall/starting/bench projections; floor/ceiling; positional strength bars; "What should I target next?"

**Player Explorer** — searchable player database; projection distribution chart; historical performance; comparable players; risk factors

**Settings** — league scoring sliders, roster configuration, data source status

### Interaction Philosophy
- Information density first
- Fast scanning and readability
- Interactive numbers (clicking VOR, Target Share, ADP opens contextual detail)
- User path: Recommendation → Explanation → Underlying Data without leaving page
- Avoid: excessive gradients, giant hero sections, heavy animations, generic SaaS aesthetics

---

## 13. Backtesting & Model Evaluation

Run after models are trained. Uses historical seasons where we recreate the pre-season information environment (no leakage).

**Projection metrics:** MAE, RMSE, correlation, rank correlation, calibration, bias  
**Ranking metrics:** Spearman correlation, NDCG, top-10/top-20 hit rate  
**Draft metrics:** expected vs actual roster value, VOR captured, optimality gap

Compare against: ADP baseline, expert consensus rankings, position-adjusted simple model.

**Autoresearch integration:** Once models are operational, use the autoresearch skill to run iterative optimization loops on historical data. Heavy emphasis on preventing overfitting — the goal is generalization, not fitting past seasons.

---

## 14. Sub-Project Build Order

Each sub-project is designed, planned, and built before the next begins.

| Phase | Sub-project | Deliverable |
|-------|-------------|-------------|
| 1 | Data foundation | Directory structure, DuckDB schema, all ingestion scripts, player ID unification |
| 2 | Feature engineering | Cleaned tables, vacated opportunity, coaching tendencies, OL metrics |
| 3 | Projection engine | Five-layer neural network pipeline, rookie module, aging curves |
| 4 | Valuation engine | VOR, replacement level, scarcity, tiers, ADP delta |
| 5 | Monte Carlo | Simulation engine, boom/bust probabilities |
| 6 | Draft decision engine | Draft Score, recommendation state, explanation generation |
| 7 | FastAPI layer | All endpoints, Pydantic schemas, OpenAPI docs |
| 8 | React UI — Rankings | Data foundation, shared types, rankings table, player drawer |
| 9 | React UI — Draft Assistant | Three-panel layout, live draft state, all draft components |
| 10 | React UI — remaining | Dashboard, Player Explorer, Mock Draft, Roster Analyzer, Settings |
| 11 | Backtesting | Evaluation framework, autoresearch optimization loop |

The UI build (Phases 8–10) can begin in parallel with Phases 6–7 using mock data, since the UI data interfaces are defined by the TypeScript types mirroring the backend schemas.

---

## 15. Key Design Principles

- **Projection ≠ Valuation ≠ Recommendation** — three separate problems, three separate modules
- **No leakage** — every training example recreates the pre-season information environment
- **No overfitting** — backtesting emphasis is generalization, not historical fit
- **Stateless draft engine** — receives full draft state each call, returns recommendation state; no session held in the engine
- **Precomputed projections** — models run offline; the API and draft engine only serve precomputed outputs
- **Typed contracts** — Pydantic schemas (backend) and TypeScript interfaces (frontend) are the single source of truth for all data shapes
- **Mock-to-real swap** — UI data layer is isolated so replacing mock data with real API calls touches only TanStack Query hooks
