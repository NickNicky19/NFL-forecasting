# Receiving-target forecasting: first direct CDF comparison

**New research result; no target website deployment.** The lowest observed target display-point error among these tested outputs was the CDF lower median: **MAE 1.692722 targets**, compared with **1.761267** for the prespecified recent-eight unrounded mean. The reduction was **0.068544 targets, or 3.89%**, on identical supported cases. This establishes a development-sample advantage over that target baseline; there is no existing website target product against which to claim a win.

Experiment `e:opportunity-four-targets-frozen-v1-20261029`; run `r:opportunity-four-targets-frozen-v1-20261029`. Exact code and protocol were [published before execution](https://github.com/NickNicky19/NFL-forecasting/tree/7395ef22cbad73e4da961ade563baf8636a792d3). [Scientific definition](../../config/category-topfive-targets-frozen-v1.science.json), [protocol](PROTOCOL_V1.md), [complete machine-readable results](PUBLIC_RESULTS_V1.json), [durable execution/readback receipt](PUBLIC_EXECUTION_READBACK_V1.json), and [all preparation/failure receipts](PUBLIC_PREPARATION_RECEIPTS_V1.json).

## What actually ran

One new unchanged 32-tree leaf-CDF fit, not a cached rescore, trained once on a 34,573-row eligible 2022–2025 regular-season projection admitted before September 1, 2026 UTC. Valid played labels train the model and priors; this total projection is not 34,573 independently scored target outcomes. Existing feature memory can include 2019–2021. There are no within-2026 refits, and this is not completion of the three history-arm comparison.

The CDF, its training-position prior, recent-three mean and recent-eight mean produced **11,996 procedure-row forecasts across 2,999 unique query player-games**. Four procedures share one tree fit; three/eight are settings in one recent-history family. Means and medians from one model are separate outputs, not independent methods.

Execution occurred **October 29, 2026, 6:51:09–6:52:06 p.m. America/Chicago**. Actual usage: 57.365 CPU seconds, 56.761 wall seconds, 319,283,200 bytes peak RSS, three managed writes, zero HTTP calls. The worker closed successfully. Model/train/query/all forecasts were frozen before the scoring worker projected outcome values; issuing-process capsule and member readback passed, and forecast values remained bitwise unchanged during grading. Source qualification had already examined these labels, so the evaluation remains exposed development evidence.

## Coverage

- Intended 2026 regular-season Weeks 1–7; supported **Weeks 1–6, 93 games**.
- Frozen primary RB/WR/TE query: **2,458 planned**, **1,855 scored**, 452 supported players, including **369 genuine played zeros**.
- **603 primary unknown rows** remain: 572 missing official weekly player-game rows and 31 zero-only rows without positive playing evidence. They were not made zeros or removed from coverage.
- All-role query: 2,999 planned, 2,090 supported, 591 played zeros and 909 unknown. This secondary panel does not dilute the primary receiving population with other positions.
- Week 7: **14 scheduled games, no compatible query or raw target-label source**. This is not complete Weeks 1–7 evaluation.
- Six unassigned raw source rows were quarantined using identity metadata before numerical projection; original bytes remain private. Six source/query position differences remain in the frozen cohort.
- The CDF used a prior fallback for 140 of 2,458 planned primary rows; recent-three and recent-eight used 344 and 250 respectively. These are planned-population fallback counts, not independent failed NFL outcomes. Model/system results retain those paths.

## Point results on the same 1,855 supported rows

Lower is better for errors. Bias is prediction minus actual. Means were not rounded.

| Procedure | Output | MAE, targets | MSE | RMSE, targets | Bias, targets | p95 absolute error |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| TGT_CDF_BASE | median | 1.692722 | 5.974124 | 2.444202 | -0.535849 | 5.000000 |
| TGT_CDF_BASE | mean | 1.745460 | 5.631438 | 2.373065 | -0.066236 | 4.726422 |
| TGT_RECENT8_MEAN | mean | 1.761267 | 5.899139 | 2.428814 | -0.069330 | 5.000000 |
| TGT_RECENT3_MEAN | mean | 1.856193 | 6.522362 | 2.553892 | -0.059370 | 5.333333 |
| TGT_ROLE_PRIOR | median | 2.302965 | 10.706199 | 3.272033 | -1.010243 | 7.000000 |
| TGT_ROLE_PRIOR | mean | 2.423124 | 9.705432 | 3.115354 | 0.125915 | 5.814681 |

Prespecified paired CDF-median minus recent-eight-mean MAE: **−0.068544**; game-cluster bootstrap 95% interval **[−0.098089, −0.041109]**, 93 game clusters, 500 draws, seed 1703. The six week clusters are below the registered minimum of eight, so the week interval is unavailable. Exposed-period method development and repeated selection remain limitations; this interval does not prove durable superiority.

Adverse findings remain: CDF median bias **−0.535849 targets**, versus **−0.069330** for the recent-eight mean; its MSE **5.974124** is worse than that mean's **5.899139**. Both have p90/p95 absolute misses of 4/5 targets. Strict absolute error <1 is 22.86% for the integer median versus 38.06% for the unrounded recent-eight mean; inclusive <=1 is 60.16% versus 45.18%. These two tolerance rules measure different events, and neither replaces MAE. The median's exact-count rate is 22.86%; no exact-count claim is made by rounding a fractional mean.

## Each week, including the loss

| 2026 week | Matched scored rows | CDF median MAE | Recent-eight mean MAE |
| --- | ---: | ---: | ---: |
| 1 | 317 | 1.637224 | 1.759210 |
| 2 | 320 | 1.753125 | 1.877281 |
| 3 | 319 | 1.664577 | 1.700524 |
| 4 | 319 | 1.736677 | 1.807269 |
| 5 | 301 | 1.601329 | 1.652858 |
| 6 | 279 | 1.767025 | 1.764353 |

The CDF median lost narrowly in Week 6. That result remains part of its history; no candidate is retired for one losing week.

## Distribution, probabilities and website status

The CDF's count-law CRPS is **1.183528** and log loss **1.977670**, compared with prior CRPS **1.626375** and log loss **2.276286**, on all 1,855 supported labels. No impossible-event loss was dropped; the positive-infinity count happened to be zero. These laws are conditional on played. Point-only recent means have no authenticated distribution score.

No authenticated target betting offers, prices, settlement rules or frozen paper selections were available. Target-threshold calibration, Over/Under results, +EV and profitability remain **unsupported**, not zero error. A reception line is not a target line.

The model is **research-tested, not operationally admitted, not captured prospectively and not deployed**. Exact historical builder/target-credit exceptions, current-source/future wrapper, private fresh-process restoration, consumer schema/labels/sorts/fallback/rollback and retained-owner admission remain. Current public aggregation uses stat ID 115; that does not establish the old source's precise nullified/two-point treatment. The original seven-day source-availability reconstruction remains an assumption. This is current-vintage exposed reconstruction, not authentic saved pregame forecasting. Independent numerical acceptance has not been performed by this target owner.

## Evidence preservation

The original label-empty query qualification, failed strict raw-label identity join, identity-only diagnostic, successful corrected qualification, source GET failures, fictional checks and exact old worker snapshot remain under their original identities. None is counted as a predictive fit. Private forecasts, outcomes, fitted model and bindings are accessible only through the approved run-scoped owner restoration route; no restricted rows or storage destinations are public. This result remains `RESULT_SAVED_PUBLICATION_PENDING` until the parent publishes and verifies remote readback.
