# Receiving targets: true recent-game median controls lost to the CDF

**Decision: retain the target CDF lower median as the lowest-error tested display point on this matched panel.** The new eight-game median had MAE **1.744474 targets**, versus **1.692722** for the CDF median: **0.051752 targets / 3.06% more error**. The three-game median had **1.849596**, or **9.27% more error** than CDF. Both negative results remain in the candidate history; neither is erased or retired for a losing week.

Experiment `e:opportunity-four-target-recent-medians-v2-20261030`; run `r:opportunity-four-target-recent-medians-v2-20261030`. [Exact code/science registered before forecasts](https://github.com/NickNicky19/NFL-forecasting/tree/859da3e2d94f1b318d828dafba8ccd6467f564e7), [protocol](PROTOCOL_V4.md), [scientific specification](../../config/category-topfive-target-recent-medians-v2.science-v5.json), [complete aggregate results](PUBLIC_RESULTS_V2.json), [execution/readback receipt](PUBLIC_EXECUTION_READBACK_V2.json), [all source/failure/software receipts](PUBLIC_PREPARATION_RECEIPTS_V2.json), and [control inventory/reception feasibility](CONTROL_INVENTORY_AND_RECEPTION_FEASIBILITY_V2.json).

## What actually ran

**Zero fits and zero model deserializations.** This was a new executed forecast comparison, not another presentation of cached scores. Two fixed procedures generated **5,998 new target-median forecasts**, with **5,998 original CDF/recent-eight mean control records reused unchanged**, across 2,999 unique query player-games. Mean/median settings belong to their related procedure families and are not independent fitted methods.

For each query, actual earlier target counts were admitted by strictly earlier recorded availability and kickoff, then sorted by game chronology. Unknown/DNP/missing rows consumed the last three/eight roster-game slots. The point was the lower empirical median of qualified values, v[(n-1)//2]. It was not a median of means or a rounded mean. Empty valid windows fell back to the original frozen CDF lower median, with abstention if that was unavailable.

The model/frozen controls, source snapshot and intended population remain unchanged. Exact source reconstruction matched the existing query mean and count aliases in both windows on **all 2,999 rows, with zero differences**. The optimized forecast projection selected only the current batch's exact player IDs, and its entire source-audit digest still matched the full-source qualification. No query was removed or realigned.

Forecasts and retained controls were durably frozen and read back before retained actual labels were projected for grading. Forecast values remained unchanged. Execution was **October 29, 2026, 8:57:33–8:58:27 p.m. America/Chicago**: 54.670 CPU seconds, 54.688 wall seconds, 206,086,144 bytes peak RSS, three managed writes, zero HTTP calls. Writer **CLOSED**. These are exposed reconstructed historical forecasts, not original pregame issuances.

## Fixed population and coverage

Primary: frozen RB/WR/TE cohort, **2,458 planned / 1,855 supported outcomes**, 452 supported players, **93 games, 2026 regular-season Weeks 1–6**, including **369 genuine played zeros**. The same 603 unknown outcomes remain for all procedures. Missing participation or source rows were not set to zero. Every method attempted all intended query rows, including unknown-outcome and sparse-history players.

The intended Weeks 1–7 scope still has **14 Week 7 games missing compatible queries and target labels**. This is not complete Week 7 or complete current-season evidence. The original broader all-role coverage is separately reported and does not dilute primary receiving errors with unrelated structural zeros.

Planned-primary fallback counts: CDF **140**, recent-eight median **250**, recent-three median **344**, original recent-eight mean **250**. These counts include unknown-outcome rows; they are not extra scored NFL observations. Full system scores include the registered fallback.

## Matched point results

All rows below use the same 1,855 supported outcomes. Bias is prediction minus actual. Lower is better for errors. New procedures produce no mean or full predictive distribution.

| Procedure | Output | MAE, targets | MSE | RMSE, targets | Bias, targets | p95 absolute error |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| TGT_CDF_BASE | median | 1.692722 | 5.974124 | 2.444202 | -0.535849 | 5.000000 |
| TGT_RECENT8_LOWER_MEDIAN_CDF_FALLBACK | median | 1.744474 | 6.428032 | 2.535356 | -0.545553 | 5.000000 |
| TGT_CDF_BASE | mean | 1.745460 | 5.631438 | 2.373065 | -0.066236 | 4.726422 |
| TGT_RECENT8_MEAN | mean | 1.761267 | 5.899139 | 2.428814 | -0.069330 | 5.000000 |
| TGT_RECENT3_LOWER_MEDIAN_CDF_FALLBACK | median | 1.849596 | 7.076550 | 2.660179 | -0.467385 | 6.000000 |

Primary eight-game median minus CDF-median MAE difference: **+0.051752 targets**, game-cluster bootstrap 95% interval **[+0.021184, +0.082148]**, 93 game clusters. Three-game median difference: **+0.156873**, interval **[+0.104596, +0.212501]**. Six week clusters are below the registered eight-cluster minimum, so week intervals remain unavailable. These fixed 500-draw, seed-1703 development intervals do not remove exposed-data selection limits or prove future superiority.

The eight-game median beat the simpler eight-game mean by only **0.016792 targets / 0.95%**; its game interval **[−0.044887, +0.013490]** spans zero. This does not establish an improvement over the stronger CDF control.

Adverse findings are retained: eight-game median bias **−0.545553**, MSE **6.428032** and inclusive error <=1 **58.06%**, compared with CDF median bias **−0.535849**, MSE **5.974124** and inclusive <=1 **60.16%**. Its exact-count / strict error <1 rate was higher, **25.55%** versus **22.86%**, while its average and inclusive-tolerance errors were worse. Exact matches, tolerances, MAE and MSE measure different things. Fractional means were not rounded to claim count accuracy.

## Every week, including every loss

| Week | Supported rows | CDF median MAE | New eight-game median MAE | New three-game median MAE | Original eight-game mean MAE |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 317 | 1.637224 | 1.646688 | 1.776025 | 1.759210 |
| 2 | 320 | 1.753125 | 1.821875 | 2.009375 | 1.877281 |
| 3 | 319 | 1.664577 | 1.717868 | 1.890282 | 1.700524 |
| 4 | 319 | 1.736677 | 1.771160 | 1.836991 | 1.807269 |
| 5 | 301 | 1.601329 | 1.720930 | 1.734219 | 1.652858 |
| 6 | 279 | 1.767025 | 1.792115 | 1.842294 | 1.764353 |

The CDF median beat both new median procedures in each of these six weeks. The original eight-game mean still narrowly beat CDF in Week 6; that earlier adverse CDF result remains. No policy receives hindsight credit for selecting a later weekly winner.

## What this does and does not change

This comparison found **no better target display-point replacement**. Keep the CDF lower median as the research leader under MAE; its mean remains separately labeled for expected-value scoring. New point medians do not establish better target probabilities, distributions or EV. No authenticated target betting offers, prices, settlements or original selections were available, and there is no website target incumbent. Those comparisons are unsupported, not zero error.

**No model or point product was admitted, captured prospectively or deployed.** The target field remains forecast-only and requires the established source/wrapper/restoration/consumer and retained-owner process before future capture or website use. Existing nonfocus website categories and original scientific registrations remain unchanged. Same-host issuing readback is not independent numerical QA or off-host restoration; this target owner has not performed that separate acceptance step.

The original fixed seven-day availability reconstruction remains an assumption; historical builder/nullified/two-point target-credit exceptions remain unresolved. Prior history can include 2019–2025 and earlier 2026, with older CDF fallback/feature memory. This is not strict current-season training, a weekly H-MULTI comparison, a verified injury/teammate system or genuine pregame evidence.

## Failure and resource record

Source qualification v2 failed at dtype-sensitive key comparison after **34.793 CPU seconds**, with zero forecasts/fits. Its original code, failure and consumed budget remain. A ten-case fictional identity check passed, then a separately authorized v3 qualification passed after **36.602 CPU seconds** with exact ordered keys and means/counts. The unretained original failed audit vector is not claimed reproduced.

Before the first forecast invocation, the same hypothesis's unexecuted 60 CPU/90 wall allowance was amended to **120 CPU/180 wall** based on measured source and store-write costs; the former specs and source snapshots remain. The source projection optimization preserved exact information, query order and audit digest. No consumed attempt was refunded, and no extra model variant was introduced.

All restricted sources, original forecasts, actuals, point vectors, grades and private bindings remain on the approved owner-controlled run restoration route. Public updates contain safe aggregates, exact code/configuration and checksums. Result status remains `RESULT_SAVED_PUBLICATION_PENDING` until parent publication and remote readback complete. Team-target-share and target-to-reception ideas remain separately tracked prerequisites, not completed forecasts from this wave.
