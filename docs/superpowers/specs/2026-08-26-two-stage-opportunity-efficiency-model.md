# Two-Stage Opportunity + Efficiency Model Design

**Goal:** Replace the single-stage PPR-point neural net with a two-stage pipeline that separates *how much work a player gets* (Stage 1: opportunity) from *how efficiently they use it* (Stage 2: efficiency), composed analytically into a fantasy point projection.

**Core motivation:** The current model is sophisticated recency bias — last season's target share and carries feed forward directly. This is structurally wrong for team changers, new starters, and players entering new schemes. Separating opportunity from efficiency means a player's portable skill (yards per target, EPA, catch rate) travels with them across teams, while their opportunity gets a fresh estimate from their new context.

**Architecture:** XGBoost for Stage 1 (opportunity, interpretability matters on a small dataset), existing neural net architecture for Stage 2 (efficiency, more data, continuous features). Analytical composition. Consensus blend unchanged at PPR-points level.

**Tech Stack:** Python, XGBoost, PyTorch (existing), DuckDB, nfl_data_py (coaches dataset).

---

## Architecture Overview

```
Coaches dataset (nflverse)  ──┐
Scheme clusters (computed)    ├──► Stage 1: Opportunity Model (XGBoost × 4 positions)
Player talent signals         │    outputs: target_share (WR/TE)
Vacated opportunity           │             carry_share + rec_share (RB)
Implicit depth chart rank    ─┘             pass_att_per_game (QB)
                                                      │
                                        team normalization step
                                     (shares must sum ≤ 1 per team)
                                                      │
Player efficiency history ────► Stage 2: Efficiency Model (neural net × 4 positions)
QB quality context               outputs: yards_per_target, catch_rate, td_rate (WR/TE)
                                          ypc, rush_td_rate, rec_efficiency (RB)
                                          ypa, td_rate, int_rate, rush stats (QB)
                                                      │
                                        Analytical composition
                                      Stage1 × Stage2 = PPR points
                                                      │
                                          mean_projection (projections table)
                                                      │
                                   blend_projections() — unchanged
                                        compute_vor() — unchanged
```

**Key property:** Stage 1 uses the *new* team's scheme and OC context for team changers — it does not carry forward last season's target share. Stage 2 uses career efficiency history, which is portable. The VOR, consensus blend, and all API/UI layers are untouched.

---

## Stage 1: Opportunity Model

### Training Target

| Position | Label | Formula |
|----------|-------|---------|
| WR, TE | `target_share` | player_targets ÷ team_pass_attempts |
| RB | `carry_share`, `rec_share` | player_carries ÷ team_rush_attempts; rb_targets ÷ team_pass_attempts |
| QB | `pass_att_per_game` | player_pass_attempts ÷ games_played |

All labels derive from the existing `player_season_stats` table with a team-level totals join.

### Features

**Talent signals** — EWMAs of career efficiency, portable across teams:

| Feature | Positions | Source |
|---------|-----------|--------|
| `ewma_yards_per_target` | WR, TE | player_season_stats |
| `ewma_catch_rate` | WR, TE, RB | player_season_stats |
| `ewma_air_yards_per_target` | WR, TE | player_season_stats |
| `ewma_epa_per_play` | all | player_season_stats |
| `ewma_yards_per_carry` | RB | player_season_stats |
| `ewma_cpoe` | QB | player_season_stats |
| `ewma_completion_pct` | QB | player_season_stats |
| `ewma_target_share` | WR, TE, RB | player_season_stats — how well the player historically commanded targets regardless of team |
| `draft_pick_value` | all | players table |
| `age`, `experience` | all | players table |

**Team context** — attributes of the player's *new* team for season N:

| Feature | Description | Source |
|---------|-------------|--------|
| `new_team_pass_rate` | team historical pass rate | team_features |
| `new_team_pass_epa` | team historical pass EPA | team_features |
| `vacated_wr_targets` | targets vacated by departed WRs | team_features (vacated_opportunity.py) |
| `vacated_rb_carries` | carries vacated by departed RBs | team_features |
| `new_team_hist_wr1_share` | historical target concentration at WR1 slot | computed from player_season_stats |

**OC/scheme features** — new data:

| Feature | Description |
|---------|-------------|
| `oc_hist_wr1_target_share` | across all seasons this OC coordinated, avg share to their top receiver |
| `oc_hist_air_yards_pct` | air yards ÷ total receiving yards across their history — pass-heavy vs YAC tendency |
| `oc_hist_rb_target_share` | how much this OC historically involves RBs in the passing game |
| `oc_tenure_at_team` | consecutive seasons as OC at current team; 0 = new OC, regresses toward historical tendencies |
| `scheme_cluster` | integer cluster ID (0–7) derived from k-means on team play patterns |

**Implicit depth chart rank** — rather than depending on manually-curated depth charts, rank the player among their new team's roster at the same position by `ewma_target_share`. WR1 = highest talent signal, WR2 = second-highest, etc. Imperfect but avoids a fragile external data dependency.

### Rookie Handling

Players with fewer than 1 full NFL season have no efficiency history. `ewma_*` features are imputed from the historical mean for players drafted at the same pick value:
- Round 1 WR gets a first-round WR efficiency prior
- UDFA RB gets an undrafted RB efficiency prior

Draft capital (`draft_pick_value`) carries most of the predictive weight for rookies in Stage 1.

### Model

XGBoost, one model per position (4 total). Chosen over neural net for Stage 1 because:
- Dataset is small (~3,000–5,000 player-seasons across training history)
- Features are heterogeneous (categorical scheme cluster, sparse OC history, continuous EWMA metrics)
- Feature importance output lets us verify that OC history and scheme cluster actually drive predictions, not just historical target share

Training window: 2016–2023. Validation: 2024. Test: 2025.

### Team Normalization (post-Stage 1, pre-composition)

Stage 1 predicts each player independently, so target shares across a team can sum to more than 1. After projecting all players, normalize within each team:

```
normalized_target_share[player] = raw_target_share[player] / sum(raw_target_share[team])
```

Run this before composition. This is a required step, not optional — skipping it silently inflates all projections.

---

## Stage 2: Efficiency Model

### What It Predicts

How efficiently a player converts a touch into fantasy value — independent of touch volume. These are portable traits that travel with the player across teams.

| Position | Outputs |
|----------|---------|
| WR, TE | `yards_per_target`, `catch_rate`, `td_rate_per_target` |
| RB | `yards_per_carry`, `rush_td_rate`, `rec_yards_per_target`, `rec_catch_rate`, `rec_td_rate` |
| QB | `yards_per_attempt`, `td_rate`, `int_rate`, `rush_yards_per_game`, `rush_tds_per_game` |

**Stage 2 does not take Stage 1's output as a feature.** The two stages are independent; composition happens analytically. This is the strict boundary that prevents the old feedback loop from re-entering through Stage 2.

### Features

**Player efficiency history:**
- EWMA of the Stage 2 output metrics above (1-season, 2-season, 3-season lags)
- `ewma_epa_per_play`, `ewma_cpoe` (QB)
- `ewma_air_yards_per_target` as a conditioning variable — catches scheme-driven catch rate depression so Stage 2 separates player skill from air-yards scheme

**Context:**
- `age`, `experience`
- `prev_games` (last 2 seasons) — injury history proxy
- QB quality context for WR/TE/RB: receiving QB's `ewma_epa_per_play` and `ewma_cpoe`. Receiving efficiency is structurally depressed behind a bad QB. **QB must be projected first** (QB Stage 1+2 across all teams) before running WR/TE/RB Stage 2.

**Explicitly excluded from Stage 2:** `target_share`, `snap_share`, `ewma_targets`, `ewma_carries`, `incoming_vacated_targets`, `incoming_vacated_carries`, `depth_chart_pos`. All opportunity signals belong to Stage 1. Including them in Stage 2 would re-introduce the stale-situation feedback loop.

### Model

Existing neural net architecture (same as current `tay/models/network.py`), one per position (4 total). Stage 2 replaces the current single-stage models. Training data, loss function, and infrastructure are unchanged.

---

## Composition

Pure arithmetic, no model. Runs after Stage 1 normalization and Stage 2 inference.

**WR / TE:**
```
projected_targets    = target_share × team_pass_att_per_game × 17
projected_receptions = projected_targets × catch_rate
projected_rec_yards  = projected_targets × yards_per_target
projected_rec_tds    = projected_targets × td_rate_per_target

ppr = projected_receptions × 1.0
    + projected_rec_yards  × 0.1
    + projected_rec_tds    × 6.0
```

**RB:**
```
projected_carries     = carry_share × team_rush_att_per_game × 17
projected_rb_targets  = rec_share × team_pass_att_per_game × 17

ppr = (projected_carries × yards_per_carry × 0.1)
    + (projected_carries × rush_td_rate × 6.0)
    + (projected_rb_targets × rec_catch_rate × 1.0)
    + (projected_rb_targets × rec_yards_per_target × 0.1)
    + (projected_rb_targets × rec_td_rate × 6.0)
```

**QB:**
```
projected_pass_att = pass_att_per_game × 17

ppr = (projected_pass_att × yards_per_att × 0.04)
    + (projected_pass_att × td_rate × 4.0)
    - (projected_pass_att × int_rate × 2.0)
    + (rush_yards_per_game × 17 × 0.1)
    + (rush_tds_per_game × 17 × 6.0)
```

`team_pass_att_per_game` and `team_rush_att_per_game` come from the team's EWMA in `team_features` — already populated.

**Team volume limitation:** Team pass volume is uncertain, primarily because QB injuries change game script dramatically. Using the team's EWMA is a reasonable prior but will systematically miss seasons where the QB situation changes. This is a known limitation with no clean preseason fix.

---

## New Data Requirements

### Coaches Dataset

**Source:** nflverse `coaches` dataset via `nfl_data_py.import_coaches()`. Available back to 2006.

**New table: `coaches`**
```sql
CREATE TABLE coaches (
    team        VARCHAR NOT NULL,
    season      INTEGER NOT NULL,
    coach_type  VARCHAR NOT NULL,  -- 'head_coach', 'offensive_coordinator'
    full_name   VARCHAR NOT NULL,
    PRIMARY KEY (team, season, coach_type)
)
```

**Derived table: `oc_features`** — computed from `coaches` joined with `player_season_stats` and `team_features`:
```sql
CREATE TABLE oc_features (
    oc_name              VARCHAR NOT NULL,
    as_of_season         INTEGER NOT NULL,
    hist_wr1_target_share DOUBLE,   -- avg across all seasons coordinated
    hist_air_yards_pct    DOUBLE,
    hist_rb_target_share  DOUBLE,
    tenure_at_team        INTEGER,  -- consecutive seasons at current team
    is_rookie_oc          BOOLEAN,  -- True if no prior NFL OC history
    PRIMARY KEY (oc_name, as_of_season)
)
```

**Cold start:** A first-year NFL OC with no OC history gets `is_rookie_oc = True`. Their OC features fall back to the team's own historical averages rather than OC history.

**New script:** `scripts/ingest_coaches.py` — fetches via nfl_data_py, upserts to `coaches`, then computes and upserts to `oc_features`.

### Scheme Clustering

**No new ingestion** — derived from existing `team_features`.

K-means (k=6) on the following team-season features:
- `pass_rate`
- `team_pass_epa`
- WR1, WR2, TE, RB target share distribution (computed from `player_season_stats`)
- Air yards per attempt

**New table: `scheme_clusters`**
```sql
CREATE TABLE scheme_clusters (
    team        VARCHAR NOT NULL,
    season      INTEGER NOT NULL,
    cluster_id  INTEGER NOT NULL,  -- 0–5
    PRIMARY KEY (team, season)
)
```

**New script:** `scripts/compute_scheme_clusters.py` — fits k-means on historical team data, assigns cluster IDs, upserts to `scheme_clusters`. Re-run each offseason as new seasons are added.

**Cluster instability:** A new HC may shift a team's scheme cluster, but that isn't observable preseason. For preseason projections, carry forward the prior season's cluster assignment. This is a known limitation.

### New Columns on `projections` Table

Intermediate Stage 1 outputs stored for debugging and future UI use:
- `projected_target_share DOUBLE`
- `projected_carry_share DOUBLE`
- `projected_rec_share DOUBLE`
- `projected_pass_att_per_game DOUBLE`

Added via `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` in `init_schema()`.

---

## Pipeline Integration

### Execution Order

```
1. ingest_coaches.py            → coaches, oc_features tables
2. compute_scheme_clusters.py   → scheme_clusters table
3. build_stage1_features()      → src/tay/features/stage1_features.py
4. train_stage1_models()        → models_stage1/ (4 XGBoost models)
5. run_stage1_pipeline()        → populates projections.projected_target_share etc.
6. normalize_team_shares()      → in-place normalization within each team
7. [QB Stage2 runs first]
8. build_stage2_features()      → src/tay/features/stage2_features.py
9. train_stage2_models()        → models_stage2/ (4 neural nets, replaces models/)
10. run_stage2_pipeline()       → efficiency inference
11. compose_projections()       → analytical composition → projections.mean_projection
12. blend_projections()         → unchanged
13. compute_vor()               → unchanged
```

### New / Modified Files

| File | Change |
|------|--------|
| `scripts/ingest_coaches.py` | NEW — nfl_data_py coaches ingestion |
| `scripts/compute_scheme_clusters.py` | NEW — k-means scheme clustering |
| `src/tay/features/stage1_features.py` | NEW — Stage 1 feature builder |
| `src/tay/features/stage2_features.py` | NEW — Stage 2 feature builder (strips opportunity signals) |
| `src/tay/models/stage1_pipeline.py` | NEW — XGBoost train/infer for opportunity |
| `src/tay/models/stage2_pipeline.py` | NEW — neural net train/infer for efficiency (replaces pipeline.py) |
| `src/tay/models/composition.py` | NEW — analytical PPR composition |
| `src/tay/schemas/tables.py` | MOD — add coaches, oc_features, scheme_clusters, new projections columns |
| `src/tay/db.py` | MOD — migrations for new tables and columns |
| `src/tay/models/pipeline.py` | MOD — orchestrates Stage1 → normalize → Stage2 → compose |

Existing files untouched: `blend.py`, `vor.py`, `valuation/`, `api/`, `simulation/`.

### Migration Strategy

Run the two-stage system alongside the existing single-stage model for the 2025 holdout season. Compare RMSE. Once two-stage RMSE is equal or better, deprecate `models/` (single-stage) and make `models_stage2/` the canonical models. Do not delete the old model until validation passes.

---

## Known Pitfalls

1. **Target share sum >1** — Stage 1 predicts independently per player; shares across a team can exceed 100%. The team normalization step (step 6 above) is mandatory, not optional.

2. **Stage 2 must not see opportunity features** — `target_share`, `snap_share`, `ewma_targets`, `ewma_carries` must be excluded from Stage 2 inputs. Including them re-introduces last season's stale situation.

3. **QB runs first** — WR/TE/RB Stage 2 uses the new QB's projected efficiency as a context feature. QB projection must complete before skill positions run. This is an explicit ordering constraint, not a convention.

4. **Mid-season trades** — players with two team-seasons in one year are excluded from Stage 1 training data (their team context is ambiguous). For inference, use the team they entered the season with.

5. **New OC cold start** — first-year NFL OCs with no OC history fall back to team historical averages. Flag `is_rookie_oc = True` so this substitution is auditable.

6. **Scheme cluster instability** — new HC/OC may shift the team's cluster, not observable preseason. Carry forward prior season's cluster as the best available prior.

7. **Team volume uncertainty** — composition uses team EWMA pass/rush attempts. QB injuries change volume dramatically. No preseason fix; flag as a known source of systematic error.

8. **Depth chart ambiguity** — implicit depth chart rank from `ewma_target_share` relative to teammates is a proxy. It breaks when a low-`ewma` player is installed as the clear WR1 (trade acquisition, free agent signing mid-projections). The consensus blend partially corrects this.
