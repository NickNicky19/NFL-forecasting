# Top-player cached comparison — 2026 Weeks 1–6

Completed October 28, 2026 (America/Chicago). **This analysis regrades retained predictions; it trains no specialized model.** It does not establish a new gain against the website. The ranked groups use one shared prior-opportunity ordering per position/category/week.

## Full original population: products stay separate

MAE is the average miss in yards, counts or chart points. MSE selects the mean product; RMSE returns it to original units. ATD uses Brier loss. These are the lowest recorded losses among this saved candidate set, on the same stated population.

| Category | Scored / query rows | Median-product leader: MAE (ATD: Brier) | Mean-product leader: MSE / RMSE |
|---|---:|---|---|
| Passing yards | 211/515 | CDF-m 62.280 | CDF-e 6362.064610 / 79.763 |
| Passing TDs | 211/515 | CDF-m 0.825 | RCDF-e 1.157146 / 1.076 |
| Completions | 211/515 | CDF-m 5.118 | CDF-e 44.178448 / 6.647 |
| Passing attempts | 211/515 | CDF-m 7.773 | RCDF-e 104.055610 / 10.201 |
| Interceptions | 211/515 | CDF-m 0.602 | CDF-e 0.526397 / 0.726 |
| Rushing yards | 526/668 | CDF-m 18.426 | CDF-e 696.278439 / 26.387 |
| Carries | 526/668 | CDF-m 3.662 | CountA-e 24.216499 / 4.921 |
| Receptions | 1849/2458 | CDF-m 1.253 | CountA-e 3.331184 / 1.825 |
| Receiving yards | 1849/2458 | CDF-m 16.055 | CDF-e 591.892661 / 24.329 |
| Rush + rec yards | 1849/2458 | CDF-m 19.926 | CDF-e 803.718978 / 28.350 |
| Chart PPR (new contract) | 1954/2117 | Leaf-m 4.679 | Leaf-e 41.610163 / 6.451 |
| Anytime rush/rec TD | 1849/2458 | CAT 0.136 | — |

**Chart PPR is `nick-chart-ppr-v1`, not the old exact website-PPR target.** The latter is not validated by these labels. Median products and means answer different questions. A count-median MAE lead does not qualify replacement of a mean or probability component.

## Shared top-10 / 15 / 20 groups by position

Each cell gives the lowest observed **point MAE** (ATD: Brier), method, and **scored/planned** rows. Unlike the full typed table, this diagnostic permits all saved point recipes to compete on MAE; product labels are retained in the summary. Top N means players in each weekly position/category pool, not N independent games. Membership is identical across methods.

| Category / position | Full | Top 10 | Top 15 | Top 20 |
|---|---|---|---|---|
| pass_yd / QB | CDF-m 62.280 (211/515) | CAT 68.041 (57/60) | CAT 65.847 (78/90) | CAT 61.591 (101/120) |
| pass_td / QB | CDF-m 0.825 (211/515) | CDF-e 0.964 (57/60) | CDF-m 0.897 (78/90) | CDF-m 0.911 (101/120) |
| pass_cmp / QB | CDF-m 5.118 (211/515) | CDF-e 5.094 (57/60) | CDF-e 5.309 (78/90) | CDF-e 4.989 (101/120) |
| pass_att / QB | CDF-m 7.773 (211/515) | CDF-e 7.237 (57/60) | CDF-m 7.667 (78/90) | CDF-e 7.316 (101/120) |
| pass_int / QB | CDF-m 0.602 (211/515) | RCDF-e 0.658 (57/60) | CDF-m 0.615 (78/90) | CDF-m 0.594 (101/120) |
| rush_yd / RB | CDF-m 18.426 (526/668) | CDF-e 27.343 (56/60) | CDF-e 28.648 (84/90) | CDF-m 26.631 (111/120) |
| rush_att / RB | CDF-m 3.662 (526/668) | CDF-e 4.435 (56/60) | CDF-m 4.690 (84/90) | CountA-e 4.663 (111/120) |
| rec / RB | CDF-m 1.057 (526/668) | CDF-m 1.660 (53/60) | CDF-m 1.506 (81/90) | CDF-m 1.485 (103/120) |
| rec / WR | CDF-m 1.378 (871/1082) | CountA-e 2.341 (56/60) | CountA-e 2.482 (86/90) | CDF-m 2.342 (111/120) |
| rec / TE | CDF-m 1.239 (452/708) | CDF-e 2.284 (57/60) | CDF-m 2.106 (85/90) | CDF-m 2.037 (109/120) |
| rec_yd / RB | CDF-m 9.213 (526/668) | CDF-m 17.887 (53/60) | CDF-m 15.963 (81/90) | CDF-m 15.515 (103/120) |
| rec_yd / WR | CDF-m 20.700 (871/1082) | CDF-e 33.680 (56/60) | CDF-e 35.976 (86/90) | CDF-e 35.128 (111/120) |
| rec_yd / TE | CAT 15.019 (452/708) | CDF-e 27.819 (57/60) | CDF-e 26.443 (85/90) | CDF-e 25.415 (109/120) |
| rush_rec_yd / RB | CDF-m 22.477 (526/668) | CDF-m 33.068 (59/60) | CDF-m 32.917 (84/90) | CDF-m 30.676 (111/120) |
| rush_rec_yd / WR | CDF-m 20.921 (871/1082) | CDF-e 33.761 (56/60) | CDF-m 35.791 (86/90) | CDF-m 34.857 (112/120) |
| rush_rec_yd / TE | CDF-m 15.040 (452/708) | CDF-e 27.730 (57/60) | CDF-e 26.282 (85/90) | CDF-e 25.069 (110/120) |
| chart_ppr / QB | Leaf-m 6.216 (211/211) | Leaf-e 6.656 (60/60) | Leaf-e 6.071 (90/90) | Leaf-e 5.617 (120/120) |
| chart_ppr / RB | Leaf-m 4.757 (501/529) | HGB-m 7.685 (60/60) | HGB-m 7.259 (90/90) | HGB-m 6.979 (120/120) |
| chart_ppr / WR | HGB-m 4.489 (836/878) | HGB-m 7.694 (60/60) | HGB-m 7.734 (90/90) | HGB-m 7.470 (120/120) |
| chart_ppr / TE | Leaf-m 4.233 (394/473) | Leaf-e 6.976 (60/60) | Leaf-e 6.744 (90/90) | HGB-m 6.171 (120/120) |
| chart_ppr / FB | Role-e 2.283 (12/26) | Role-e 2.283 (12/25) | Role-e 2.283 (12/25) | Role-e 2.283 (12/25) |
| anytime_td / RB | CAT 0.150 (526/668) | CAT 0.229 (59/60) | CAT 0.222 (84/90) | CAT 0.224 (111/120) |
| anytime_td / WR | CAT 0.126 (871/1082) | CAT 0.249 (56/60) | CAT 0.231 (86/90) | Mix-p 0.220 (112/120) |
| anytime_td / TE | CDF-p 0.140 (452/708) | CDF-p 0.259 (57/60) | CDF-p 0.218 (85/90) | CDF-p 0.200 (110/120) |

A top-group average can be **larger** than the full-population average because high-volume players have more absolute yardage/count risk. Neither direction measures the benefit of specialization: every group uses the same original models. Missing-rank players remain in the full population and remainder.

## Disjoint rank bands: retained reference error and coverage

Cells are **reference MAE [scored/planned]**. The four disjoint bands reproduce the full reference population and total absolute error; the machine summary retains each band’s share. ATD MAE below is a descriptive diagnostic only; Brier above remains primary. An additional overlapping `unranked` group is retained in the complete safe aggregate.

| Category / position | Ranks 1–10 | 11–15 | 16–20 | Remainder incl. unranked |
|---|---|---|---|---|
| pass_yd / QB | 69.439 [57/60] | 61.476 [21/30] | 45.478 [23/30] | 62.236 [110/395] |
| pass_td / QB | 0.964 [57/60] | 0.832 [21/30] | 1.023 [23/30] | 0.813 [110/395] |
| pass_cmp / QB | 5.094 [57/60] | 5.893 [21/30] | 3.904 [23/30] | 5.387 [110/395] |
| pass_att / QB | 7.237 [57/60] | 8.842 [21/30] | 6.121 [23/30] | 8.433 [110/395] |
| pass_int / QB | 0.661 [57/60] | 0.585 [21/30] | 0.609 [23/30] | 0.624 [110/395] |
| rush_yd / RB | 28.286 [56/60] | 30.000 [28/30] | 19.704 [27/30] | 16.231 [415/548] |
| rush_att / RB | 4.435 [56/60] | 5.397 [28/30] | 4.375 [27/30] | 3.566 [415/548] |
| rec / RB | 1.803 [53/60] | 1.441 [28/30] | 1.471 [22/30] | 1.015 [423/548] |
| rec / WR | 2.341 [56/60] | 2.745 [30/30] | 1.898 [25/30] | 1.325 [760/962] |
| rec / TE | 2.303 [57/60] | 1.827 [28/30] | 1.720 [24/30] | 1.097 [343/588] |
| rec_yd / RB | 18.271 [53/60] | 12.214 [28/30] | 13.866 [22/30] | 7.729 [423/548] |
| rec_yd / WR | 35.760 [56/60] | 39.164 [30/30] | 31.142 [25/30] | 18.618 [760/962] |
| rec_yd / TE | 28.551 [57/60] | 23.736 [28/30] | 20.900 [24/30] | 11.647 [343/588] |
| rush_rec_yd / RB | 33.150 [59/60] | 32.607 [25/30] | 24.931 [27/30] | 20.350 [415/548] |
| rush_rec_yd / WR | 35.416 [56/60] | 39.447 [30/30] | 31.163 [26/30] | 18.852 [759/962] |
| rush_rec_yd / TE | 28.750 [57/60] | 23.739 [28/30] | 20.440 [25/30] | 11.842 [342/588] |
| chart_ppr / QB | 6.783 [60/60] | 5.165 [30/30] | 4.333 [30/30] | 7.135 [91/91] |
| chart_ppr / RB | 7.685 [60/60] | 6.408 [30/30] | 6.138 [30/30] | 4.083 [381/409] |
| chart_ppr / WR | 7.694 [60/60] | 7.814 [30/30] | 6.679 [30/30] | 3.989 [716/758] |
| chart_ppr / TE | 7.136 [60/60] | 6.149 [30/30] | 4.264 [30/30] | 3.392 [274/353] |
| chart_ppr / FB | 2.539 [12/25] | — [0/0] | — [0/0] | — [0/1] |
| anytime_td / RB | 0.476 [59/60] | 0.441 [25/30] | 0.475 [27/30] | 0.274 [415/548] |
| anytime_td / WR | 0.479 [56/60] | 0.397 [30/30] | 0.386 [26/30] | 0.233 [759/962] |
| anytime_td / TE | 0.460 [57/60] | 0.321 [28/30] | 0.323 [25/30] | 0.229 [342/588] |

## Timing, coverage and evidence boundaries

- Evaluation: **2026 regular-season Weeks 1–6, 93 games**. Exactly **15,860 category-query opportunities** were frozen before target labels; overlapping categories and model rows are not extra independent NFL outcomes.
- Original generic query pool: **2,999** rows. All original query cutoffs equal kickoff: these are historical **left-limit reconstructions**, not originally issued pregame forecasts. The old seven-day availability assumption remains unchanged; no live consumer guard was relaxed.
- Rankings admit source records strictly before the shared weekly deadline, then take the last eight eligible game slots by game chronology. They use pass attempts (QB), carries (RB rushing), targets (receiving), or carries+targets (combined/ATD; position-specific chart rules). No target-game values, outcomes or model-specific ranking enter membership. Older seasons and potentially prior postseason can enter history.
- History clock audit: no unknown/conflicting clock keys, invalid identities, quarantined rows or conflicting slots in this retained source. This does not authenticate original publication timestamps. Source availability is still reconstructed.
- Unsupported participation and played-missing labels stay unscored and in planned coverage. Missing rank is never zero. Chart has **163 unknown-participation queries**; source chart states were retained and unexpected states would stop execution.
- No authentic historical SITE/R0/raw-provider values or sportsbook-offered population in this panel. No new threshold-probability, correct-side, close-and-correct, market/EV or paper-return result is claimed.
- Six weeks are insufficient for the registered minimum-eight-cluster week interval. Game-cluster intervals (500 resamples) are nominal exposed-development diagnostics, not adjusted confirmation or durable superiority. Full paired results retain adverse findings.
- This wave does not execute the queued 2025 cohort panel or genuine Week 7 cohort analysis, and deploys nothing. No subgroup-specific model or irreducible error floor was established.

| Week | Common ranking deadline (America/Chicago) | Admitted history rows | Last-8 slot rows |
|---|---|---:|---:|
| 1 | 2026-09-09 13:20 CDT | 59842 | 10797 |
| 2 | 2026-09-17 13:15 CDT | 59877 | 10804 |
| 3 | 2026-09-24 13:15 CDT | 60362 | 10898 |
| 4 | 2026-10-01 13:15 CDT | 60875 | 10991 |
| 5 | 2026-10-08 13:15 CDT | 61393 | 11089 |
| 6 | 2026-10-15 13:15 CDT | 61907 | 11185 |

## Reproduction, private evidence and operating status

The retained private grade includes `COMPARISON_ROWS.parquet` with original prediction, actual, error context, membership, source keys, fallback and clock status; it is not a public website asset. Membership and grade were each durably frozen and exact-byte read back. The safe aggregate contains **6,216 complete weekly/season group records and 747 paired contrasts**, with all saved methods, missingness, bias, tails, tolerances, probability reliability and intervals.

Actual main: **87.36 CPU s / 87.25 wall s**, peak RSS **419,270,656 bytes**; **2 CAS writes**, **0 new fits**, **0 model loads**, **0 new forecast inference**, **0 HTTP**. All failures/unexecuted earlier proposals remain preserved. Actual backend settings are UNATTESTED.

- [Complete safe aggregate: all weeks/methods/groups](PUBLIC_RESULTS.json.gz)
- [Compact leaders, bands, diagnostics and exact metadata](SUMMARY.json)
- [Exact-byte persistence and resource receipt](native-v1/COMPLETE.json)
- [Sealed-plan preparation](../../config/top-player-cached-v1.preseal.json)
- [Zero-fit comparison worker](../../tools/top_player_cached_v1.py)
- [Safe aggregate report renderer](../../tools/top_player_cached_report_v1.py)

`CDF-m/e`: empirical leaf-CDF median/mean. `RCDF-e`: response-CDF mean. `CAT`: CatBoost median-objective point for yards, binary probability for ATD. `CAT-e`: count mean-objective point. `CountA-e`: corrected mean-fallback Count A point recipe. `Mix-p`: equal CDF/CatBoost ATD probability. `Leaf-m/e`: chart leaf-CDF median/mean. `HGB-m`: chart absolute-error boosting. Remaining chart position/global/role priors retain their own identities in the machine evidence.
