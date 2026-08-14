# Worklog: QB Rankings Autoresearch

**Goal**: Improve QB projection rankings so rushing QBs are properly valued and accuracy improves.

**Session start**: 2026-08-14
**Branch**: autoresearch/qb-rankings-2026-08-14

---

## Data Summary
- QB training data: 2006-2023 (~50-65 QBs/season, total ~950 rows)
- Val data: 2024-2025 (good temporal split — avoids leakage)
- Target: next_season_fantasy_ppr (PPR scoring)
- Distribution: mean=159, std=144, median=119 (right-skewed, elite QBs at 400-550)
- Key injured players in 2026 projection window:
  - Jayden Daniels: 7 games in 2025 (injury) after 401 pts in 2024
  - Jaxson Dart: 14 games in 2025 (debut), 492 rush yards, 9 rush TDs

## Key Insights
- Experience penalty (exp ≤ 1: 0.75x) and rush bonus (rush_score ≥ 600: 1.18x) are applied sequentially → net effect 0.885x for elite rookie rushers — the rush bonus is nearly cancelled
- Injury correction anchor = (lag2_fpts + ewma_fpts_proj17) / 2, w_model=0.20 for <8 games → Daniels anchor ≈ 343, but model output is low post-injury → final projection not high enough
- Goff has 0 rush yards → rush_score < 100 → only 7% penalty (0.93x) — not enough to drop him

## Next Ideas
1. Stronger injury correction (w_model: 0.20→0.10 for <8 games, 0.40→0.25 for 8-11 games)
2. Decouple exp penalty from rush bonus — skip exp discount when rush_score ≥ 300
3. Stronger pocket-QB penalty (rush_score < 100 → 0.93 → 0.88)

---

### Run 1: Baseline — primary=80.44 (KEEP)
- Timestamp: 2026-08-14 09:35
- What changed: baseline — current production code with 100 epochs
- Result: primary=80.44, qb_mae=75.3, rank_penalty=102.1
- daniels_rank=83, dart_rank=115, goff_rank=63, mahomes_rank=72
- Insight: Daniels 33 ranks too low (injury year), Dart 35 ranks too low (exp penalty neutralizes rush bonus), Goff 47 ranks too high (pocket QB penalty too weak)
- Next: Try stronger injury correction (w_model 0.10 for <8 games)
