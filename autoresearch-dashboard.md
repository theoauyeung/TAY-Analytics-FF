# Autoresearch Dashboard: QB Rankings (qb-rankings)

**Runs:** 40 / 40 (BUDGET EXHAUSTED) | **Kept:** 13 | **Discarded:** 27 | **Crashed:** 0
**Baseline:** primary=80.44 (#1)
**Best (cross-seed):** primary=76.63/74.25, mean=75.44 (#34, commit b05718b)
**Improvement from baseline:** 80.44→76.63 seed42 (-4.7%), rank_penalty 102.1→8.9 (-91%)
**Noise floor:** ±0.93 per seed (reliable threshold: >0.93 cross-seed mean improvement)

| # | commit | primary (s42) | s99 | rank_penalty | status | description |
|---|--------|--------------|-----|--------------|--------|-------------|
| 1 | baseline | 80.44 | — | 102.1 | keep | baseline: 100 epochs |
| 2 | — | 80.08 | — | 94.9 | keep | rush-aware injury correction w_model 0.10/0.25 |
| 3 | — | 78.89 | — | 71.1 | keep | skip exp discount for proven rushers (rush>=300) |
| 4 | — | 78.25 | — | 58.2 | keep | pocket QB penalty 0.93→0.87 |
| 5 | — | 77.95 | — | 52.2 | keep | QB scarcity 0.35→0.42 |
| 6 | — | 77.25 | — | 38.2 | keep | lag2-weighted injury anchor 0.7/0.3 for rushers |
| 7 | — | 80.80 | — | — | discard | experience penalty young QBs 0.75x (too aggressive) |
| 8 | — | 79.24 | — | — | discard | rush bonus tiers without other fixes |
| 9 | — | 76.47 | — | 27.2 | keep | 150 epochs (pre-determinism, best stochastic) |
| 10-15 | — | various | — | various | discard | see worklog |
| 16 | 15fa786 | 78.28 | — | 41.6 | keep | set_num_threads=1 + ewma_fpts_proj17 feature |
| 17-19 | various | worse | — | — | discard | scarcity/pocket bundles below noise floor or wrong threshold |
| **20** | cfe238e | **77.06** | 75.20 | 17.2 | **keep** | scarcity 0.52 + pocket 0.82 + injury threshold <15 |
| 21-30 | various | — | — | — | discard | feature experiments, lag3 removal, MC samples |
| **31** | 9c1d159 | 76.80 | 74.90 | 12.2 | **keep** | scarcity 0.58 + weight_decay 5e-4 |
| **32** | 80d41e4 | 76.75 | 74.79 | 11.2 | **keep** | scarcity 0.65 |
| **33** | 264140d | 76.65 | 74.37 | 9.2 | **keep** | scarcity 0.75 |
| **34** | b05718b | **76.63** | **74.25** | **8.9** | **keep** | **scarcity 0.85 ← BEST** |
| 35 | b05718b | 76.63 | 74.25 | 8.9 | discard | scarcity 0.95: plateau at 0.85 |
| 36 | b05718b | 76.63 | 74.15 | 8.9 | discard | Daniels anchor w_lag2=0.85: +0.05 below noise |
| 37 | b05718b | 76.64 | 74.22 | 9.1 | discard | ultra-elite rush tier >=900: 1.23x — no net gain |
| 38 | b05718b | 77.38 | — | 23.8 | discard | veteran rush bonus 1.22x (exp>=5): Dart #87→109 CATASTROPHIC |
| 39 | b05718b | 76.63 | 74.25 | 8.9 | discard | pocket penalty 0.82→0.77: no effect (pocket QBs already below threshold) |
| 40 | b05718b | 79.31 | — | 48.9 | discard | cosine annealing LR: Dart #147 CATASTROPHIC |

## Final QB Rankings vs Targets (Exp 34 / Run 34, seed 42)
| QB | Rank | Target | Delta | Status |
|----|------|--------|-------|--------|
| Jayden Daniels | #42 | #50 | -8 | ✓ (above target) |
| Jaxson Dart | #87 | #80 | +7 | minor penalty |
| Josh Allen | #18 | #10 | +8 | main remaining penalty |
| Lamar Jackson | ~#13 | #30 | -17 | (too high, no penalty) |
| Patrick Mahomes | #50 | #60 | -10 | ✓ (above target) |
| Jared Goff | ~#153 | #110 | +43 | ✓ (below target, no penalty) |
| Sam Darnold | ~#170 | #120 | +50 | ✓ (below target, no penalty) |

## Remaining rank_penalty: 8.9 (91% reduction from baseline 102.1)
- Allen: ~4.0 (8 ranks too low at #18 vs target #10, weight 0.5) — STRUCTURAL LIMIT
- Dart: ~4.9 (7 ranks too low at #87 vs target #80, weight 0.7)
- Allen gap is structural: model projects Allen ~383 pts vs Maye/Lamar 460+; closing requires 20% boost which causes cross-position displacement

## Key Insights (final)
- **Post-hoc adjustments dominate** all wins — 11/13 keeps were pipeline.py or vor.py changes
- **Training changes hurt**: Huber loss, higher dropout, cosine annealing, lr=5e-4 all discarded
- **Displacement is the ceiling**: Any targeted QB boost proportionally changes cross-position ranks; only UNIFORM changes (pocket penalty) are safe, and pocket QBs are already ranked low enough
- **Scarcity plateau**: QB scarcity saturates at 0.85 — further increases give identical results
- **Allen gap is structural**: The model underestimates Allen due to many veteran QBs regressing in training data; no post-hoc adjustment closes a 20% gap without catastrophic displacement
