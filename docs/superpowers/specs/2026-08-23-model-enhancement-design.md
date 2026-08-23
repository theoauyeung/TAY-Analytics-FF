# Model Enhancement Design
_2026-08-23_

## Goal

Improve projection accuracy and ranking quality through three phases:

1. **Phase 1** — New ML features derived from existing `play_by_play` data (no new ingestion)
2. **Phase 2** — Snap count ingestion from nflverse public CSVs
3. **Phase 3** — Sleeper historical league analytics feeding back into the rankings score

All phases are independently shippable. PPR is the only supported scoring format going forward; half PPR and standard are removed throughout.

---

## Scoring Format Cleanup (precondition)

Before any new feature work, remove half PPR and standard scoring everywhere:

| Location | Change |
|---|---|
| `src/tay/schemas/tables.py` | Drop `fantasy_points_hppr`, `fantasy_points_std` columns from `player_season_stats` DDL |
| `src/tay/ingestion/aggregate_stats.py` | Remove `fantasy_points_hppr` and `fantasy_points_std` from SELECT and INSERT |
| `src/tay/ingestion/fantasypros.py` | Remove `half_ppr` and `standard` from format loop; PPR only |
| `ui/src/types/player.ts` | `ScoringFormat = 'ppr'` (literal, not union) |
| `ui/src/types/settings.ts` | `format: 'ppr'` (hardcoded) |
| `ui/src/components/rankings/RankingsControls.tsx` | Remove half PPR option from format selector |
| `ui/src/pages/Settings.tsx` | Remove half PPR and standard from scoring options |
| `ui/src/api/draft.ts` | Remove `half_ppr` mapping |
| `ui/src/api/league.ts` | Simplify format mapping to PPR only |

---

## Phase 1 — New ML Features from play_by_play

### New columns on `player_features`

All features are computed from prior season N-1 data (no leakage into season N).

| Column | Type | Positions | Description |
|---|---|---|---|
| `target_share` | DOUBLE | RB, WR, TE | Player targets / team pass attempts |
| `air_yards_share` | DOUBLE | WR, TE | Player air yards / team total air yards |
| `wopr` | DOUBLE | WR, TE | 1.5 × target_share + 0.7 × air_yards_share |
| `weekly_fpts_std` | DOUBLE | All | Std dev of weekly PPR points across games |
| `boom_rate` | DOUBLE | All | Fraction of games with ≥ 20 PPR points |
| `floor_rate` | DOUBLE | RB, WR, TE | Fraction of games with < 8 PPR points |
| `sos_pts_allowed` | DOUBLE | All | Avg PPR pts allowed by opponents faced last season |

### Feature computation

**Opportunity share** (single SQL pass over `play_by_play`):
- Team pass attempts per season: `COUNT(*) WHERE pass_attempt = 1 GROUP BY posteam, season`
- Player targets per season: `COUNT(*) WHERE pass_attempt = 1 AND receiver_id IS NOT NULL GROUP BY receiver_id, season`
- Player/team air yards: `SUM(air_yards)` on same groups
- `target_share = player_targets / team_pass_attempts`
- `air_yards_share = player_air_yards / team_air_yards`
- `wopr = 1.5 * target_share + 0.7 * air_yards_share`

**Consistency** (aggregate play_by_play to weekly fantasy points, then reduce to season stats):
- Weekly PPR points from play_by_play:
  - Receiving: `complete_pass × 1 + yards_gained × 0.1 + touchdown × 6` (where receiver_id matches)
  - Rushing: `yards_gained × 0.1 + touchdown × 6` (where rusher_id matches)
- Per player per season: `STDDEV(weekly_fpts)`, `AVG(weekly_fpts >= 20)`, `AVG(weekly_fpts < 8)`
- Regular season only (`season_type = 'REG'`)

**Defensive SOS**:
- For each player, collect the set of defteams they faced last season (games where they appear in play_by_play on posteam side)
- For each defteam, compute average PPR points allowed to that position (from player_season_stats joined to rosters for team assignment)
- `sos_pts_allowed` = average across all opponents faced

### New file: `src/tay/features/advanced_features.py`

Single public function: `compute_advanced_features(conn, seasons)`. Called at the end of `build_player_features` in `player_features.py`. Uses `_migrate_player_features` pattern to add columns if missing.

### POSITION_FEATURES additions (`src/tay/models/features.py`)

| Position | New features added |
|---|---|
| QB | `weekly_fpts_std`, `boom_rate`, `sos_pts_allowed` |
| RB | `target_share`, `weekly_fpts_std`, `boom_rate`, `floor_rate`, `sos_pts_allowed` |
| WR | `target_share`, `air_yards_share`, `wopr`, `weekly_fpts_std`, `boom_rate`, `floor_rate`, `sos_pts_allowed` |
| TE | `target_share`, `air_yards_share`, `wopr`, `weekly_fpts_std`, `boom_rate`, `floor_rate`, `sos_pts_allowed` |

### After Phase 1

Rebuild `player_features` for all seasons, then retrain all four position models. Early stopping will select the best checkpoint per position.

---

## Phase 2 — Snap Count Ingestion

### Data source

nflverse publishes weekly snap count data as public CSVs (no auth). One file per season. Key fields: `player_id` (gsis_id), `team`, `season`, `week`, `offense_snaps`, `offense_pct`.

### New table: `snap_counts`

```sql
CREATE TABLE snap_counts (
    gsis_id       VARCHAR NOT NULL,
    season        INTEGER NOT NULL,
    snap_share    DOUBLE,   -- avg weekly offense_pct across games played
    snap_share_trend DOUBLE, -- snap_share(N-1) minus snap_share(N-2)
    total_snaps   INTEGER,
    games_played  INTEGER,
    PRIMARY KEY (gsis_id, season)
)
```

### New columns on `player_features`

| Column | Positions | Description |
|---|---|---|
| `snap_share` | All | Avg offensive snap % last season |
| `snap_share_trend` | All | Change in snap_share vs. prior season (N-2) |

`snap_share` captures role floor independently of volume stats — a player can have a quiet target week but still play 90% of snaps, indicating volume will normalize. `snap_share_trend` signals role growth or erosion within a season.

### New ingestion script: `scripts/ingest_snaps.py`

Downloads nflverse snap CSVs for a configurable season range, inserts into `snap_counts`, computes `snap_share_trend` against prior season, then triggers `compute_advanced_features` to backfill the new columns.

### POSITION_FEATURES additions

All four positions gain `snap_share` and `snap_share_trend`.

---

## Phase 3 — Sleeper Draft Analytics

### Data source

Sleeper public API (no authentication required). Given a list of league IDs, we can fetch:
- League settings (teams, scoring format, roster config)
- Draft results (pick slot, player, overall pick number)
- Weekly matchup scores
- Final standings (wins, losses, points for, playoff finish)

User supplies league IDs via config or CLI argument.

### New tables

**`sl_leagues`**
```sql
league_id, season, teams, scoring_format, roster_config, created_at
PRIMARY KEY (league_id, season)
```

**`sl_draft_picks`**
```sql
league_id, season, team_id, overall_pick, pick_slot, gsis_id, adp_at_draft
PRIMARY KEY (league_id, season, overall_pick)
```

**`sl_team_results`**
```sql
league_id, season, team_id, wins, losses, points_for, made_playoffs, finish
PRIMARY KEY (league_id, season, team_id)
```

### Analytics layer: `src/tay/analytics/draft_value.py`

Three outputs:

**1. Points above expectation by ADP slot**
For each ADP bucket (1–5, 6–12, 13–24, 25–36, 37–48, 49–72, 73–108, 109+):
- Expected PPR output = average actual points for all players ever drafted in that slot
- Per-player delta = actual points − bucket expectation
- Aggregated across all ingested leagues and seasons

**2. Position allocation by playoff outcome**
For each round × position combination, what fraction of playoff teams vs. non-playoff teams used that slot on each position? Surfaces tendencies like "playoff teams drafted RB in rounds 1–2 at 2× the rate of non-playoff teams."

**3. Per-player historical efficiency factor**
`efficiency_factor = player_avg_points_above_expectation / bucket_std_dev`

Normalized z-score: positive = historically undervalued at their ADP, negative = historically overvalued. This feeds directly into the rankings score.

### Analytics → Rankings integration

The blended ranking score in `src/tay/api/routers/rankings.py` currently mixes VOR rank and ADP:

```python
_ADP_BLEND_WEIGHT = 0.3
score = 0.7 * vor_rank + 0.3 * adp
```

Phase 3 adds a third term:

```python
_ADP_BLEND_WEIGHT = 0.25
_ANALYTICS_WEIGHT = 0.10
score = 0.65 * vor_rank + 0.25 * adp + 0.10 * analytics_rank
```

Where `analytics_rank` is derived from `efficiency_factor` (players with higher efficiency_factor get lower/better analytics_rank). The weight is conservative (10%) since the signal is noisy across different league types and sample sizes.

`efficiency_factor` is stored in a new `player_analytics` table and joined in the rankings query. Players with no historical draft data get `efficiency_factor = 0` (neutral).

**`player_analytics`**
```sql
gsis_id, season, efficiency_factor DOUBLE, adp_bucket VARCHAR,
avg_pts_above_expectation DOUBLE, sample_size INTEGER, created_at
PRIMARY KEY (gsis_id, season)
```

### New ingestion script: `scripts/ingest_sleeper.py`

CLI: `python scripts/ingest_sleeper.py --league-ids L1 L2 L3 --seasons 2020 2025`

Fetches, validates (PPR only, skip non-skill-position picks), and inserts into the three tables. Then runs `draft_value.py` to compute and store `efficiency_factor`.

### UI surface

New `/analytics` tab with:
- Draft value curve by position and round (line chart)
- Top 10 historically undervalued players vs. current ADP
- Position allocation heatmap by playoff outcome (round × position × win rate)

Rankings table gains a subtle indicator (e.g. ↑↓ badge) when a player's `efficiency_factor` meaningfully adjusts their rank vs. pure VOR.

---

## Retrain Schedule

| After | Action |
|---|---|
| Phase 1 complete | Rebuild player_features 2006–2025, retrain all 4 models |
| Phase 2 complete | Rebuild player_features 2006–2025 (snap cols backfilled), retrain all 4 models |
| Phase 3 complete | No retrain — analytics feeds rankings blending logic only |

---

## File Map

```
src/tay/
├── features/
│   ├── player_features.py      — add _migrate call + compute_advanced_features call
│   └── advanced_features.py    — NEW: target share, consistency, SOS computation
├── models/
│   └── features.py             — add new columns to POSITION_FEATURES
├── analytics/
│   ├── __init__.py             — NEW
│   └── draft_value.py          — NEW: ADP efficiency, position allocation, efficiency_factor
├── ingestion/
│   ├── aggregate_stats.py      — remove hppr/std
│   └── fantasypros.py          — remove half_ppr/standard format loop
├── schemas/
│   └── tables.py               — drop hppr/std cols; add snap_counts, sl_* tables, player_analytics
└── api/
    └── routers/
        └── rankings.py         — add analytics_rank to blended score

scripts/
├── ingest_snaps.py             — NEW: nflverse snap count CSV ingestion
└── ingest_sleeper.py           — NEW: Sleeper API league ingestion

ui/src/
├── types/
│   ├── player.ts               — ScoringFormat = 'ppr' only
│   └── settings.ts             — format: 'ppr' hardcoded
├── components/rankings/
│   └── RankingsControls.tsx    — remove half PPR option
├── pages/
│   ├── Settings.tsx            — remove half PPR / standard options
│   └── Analytics.tsx           — NEW: draft analytics dashboard
└── api/
    ├── draft.ts                — remove half_ppr mapping
    └── league.ts               — simplify to PPR only
```
