# Passing attempts: four training-history families

This new, fixed research pilot compared four complete procedures on the same offered QB rows. **None of the four beat the strongest available control in either season.** The time-weighted family beat the recent-three control in both seasons, while the pooled-eight control remained better in 2026. These results support no live model or ranking change.

## Scope and coverage

All forecasts estimate passing-attempt **means conditional on playing**. The evaluation covers 2025 regular-season Weeks 1–18 and 2026 Weeks 1–6. Unknown participation is retained and excluded from conditional-played loss calculations; it is never treated as zero or DNP.

| Season | Offered QB rows | Supported played | Unknown participation | Supported played zeros |
|---|---:|---:|---:|---:|
| 2025 | 1359 | 664 | 695 | 36 |
| 2026 | 515 | 211 | 304 | 6 |

This is a partial participation panel: no offered rows were dropped, and zero DNP or played-missing rows were established in the retained label views. For 2026, the accepted retained qualification supplies labels for every procedure and new control; older outcome labels were not asserted identical.

## Fixed procedures

- **F1:** Mean of supported same-player observations in the current season; an earlier-training QB mean supplies its disclosed cold fallback. Its all-row procedure therefore includes older training information.
- **F2:** Equal appearance-weighted same-player mean from the prior and current seasons; shared QB fallback only when that native window is empty.
- **F3:** Same-player history from 2019 onward with a fixed 365-day half-life; shared QB fallback only when its native history is empty.
- **F4:** The existing regularized team-share workload relation, estimated on earlier seasons and evaluated at cached lagged H3, QB role and team-volume state; its existing recent fallback remains explicit.

The first three formulas and the 365-day decay are new preregistered designs, with no parameter search. They do not reproduce missing original-method parameters. Earlier-season QB priors and workload shares were estimated once for each evaluation year. The two new controls use the unchanged shared recent-three and pooled-eight mean procedures.

## Full conditional-played metrics

MSE is primary; lower MSE, MAE, RMSE and tail error are better. Bias is prediction minus outcome. Every method in a season is scored on the same supported played rows.

### 2025

| Procedure | n | MSE | MAE | RMSE | Bias | 95th-percentile absolute error |
|---|---:|---:|---:|---:|---:|---:|
| F1 Current-season player mean | 664 | 165.712 | 9.562 | 12.873 | 0.706 | 28.298 |
| F2 Prior + current player mean | 664 | 152.998 | 9.133 | 12.369 | 0.341 | 27.057 |
| F3 Time-weighted multi-season | 664 | 146.459 | 9.145 | 12.102 | 1.187 | 25.675 |
| F4 Earlier-trained workload | 664 | 159.260 | 9.729 | 12.620 | 1.522 | 25.751 |
| Recent 3 control | 664 | 156.833 | 9.503 | 12.523 | 2.441 | 27.148 |
| Pooled 8 control | 664 | 155.018 | 9.472 | 12.451 | 2.433 | 26.298 |
| Frozen CDF mean | 664 | 124.099 | 8.664 | 11.140 | 1.656 | 23.798 |

### 2026

| Procedure | n | MSE | MAE | RMSE | Bias | 95th-percentile absolute error |
|---|---:|---:|---:|---:|---:|---:|
| F1 Current-season player mean | 211 | 164.665 | 9.660 | 12.832 | -0.774 | 27.500 |
| F2 Prior + current player mean | 211 | 133.984 | 8.740 | 11.575 | -1.694 | 24.726 |
| F3 Time-weighted multi-season | 211 | 128.672 | 8.554 | 11.343 | -1.045 | 24.787 |
| F4 Earlier-trained workload | 211 | 144.633 | 9.145 | 12.026 | -2.315 | 24.805 |
| Recent 3 control | 211 | 133.882 | 8.739 | 11.571 | -0.981 | 24.893 |
| Pooled 8 control | 211 | 125.492 | 8.425 | 11.202 | -0.829 | 24.191 |

The authentic 2025 frozen CDF recorded mean exactly matches its frozen API point and uses the same outcomes and identities in these comparisons. The 2026 CDF comparator is unavailable; historical website/raw estimates and current R0 are also unavailable. No website-relative gain is established.

## Native fallback and current-season history

Fallbacks belong to each complete procedure. A shared current-season cold mask was not imposed on the older-history families. Counts below distinguish all offered fallback rows from fallback rows with a supported played outcome.

| Season | Procedure | Offered fallback rows | Scored fallback rows | Current-season warm n / MSE | Current-season empty n / MSE |
|---|---|---:|---:|---|---|
| 2025 | F1 Current-season player mean | 451 | 113 | 551 / 141.554 | 113 / 283.508 |
| 2025 | F2 Prior + current player mean | 176 | 22 | 551 / 133.870 | 113 / 246.268 |
| 2025 | F3 Time-weighted multi-season | 119 | 18 | 551 / 132.468 | 113 / 214.678 |
| 2025 | F4 Earlier-trained workload | 0 | 0 | 551 / 133.388 | 113 / 285.415 |
| 2025 | Recent 3 control | 465 | 85 | 551 / 132.102 | 113 / 277.422 |
| 2025 | Pooled 8 control | 246 | 33 | 551 / 132.249 | 113 / 266.037 |
| 2025 | Frozen CDF mean | 28 | 7 | 551 / 111.900 | 113 / 183.584 |
| 2026 | F1 Current-season player mean | 338 | 86 | 125 / 146.284 | 86 / 191.382 |
| 2026 | F2 Prior + current player mean | 126 | 10 | 125 / 120.179 | 86 / 154.049 |
| 2026 | F3 Time-weighted multi-season | 97 | 6 | 125 / 111.705 | 86 / 153.333 |
| 2026 | F4 Earlier-trained workload | 0 | 0 | 125 / 124.338 | 86 / 174.132 |
| 2026 | Recent 3 control | 218 | 27 | 125 / 108.155 | 86 / 171.277 |
| 2026 | Pooled 8 control | 148 | 12 | 125 / 104.037 | 86 / 156.676 |

Warm and empty are diagnostic cohorts defined by qualified current-season same-player history. They do not replace the primary all-offered procedure comparison.

## Paired comparisons and variation across weeks

Deltas are candidate MSE minus comparator MSE on identical offered identities, outcomes and cutoffs. Negative values favor the candidate. Game and week groups are dependent; the week ranges are descriptive and are not confidence intervals or significance tests. Every offered week is retained.

| Season | Family | Comparator | Paired n | Overall MSE delta | Week delta min / median / max |
|---|---|---|---:|---:|---|
| 2025 | F1 | Recent 3 control | 664 | 8.879 | -36.523 / 7.788 / 72.530 |
| 2025 | F1 | Pooled 8 control | 664 | 10.694 | -33.453 / 13.075 / 63.092 |
| 2025 | F1 | Frozen CDF mean | 664 | 41.613 | 19.315 / 34.949 / 86.077 |
| 2025 | F2 | Recent 3 control | 664 | -3.836 | -50.653 / -9.482 / 58.478 |
| 2025 | F2 | Pooled 8 control | 664 | -2.020 | -33.818 / -3.336 / 39.234 |
| 2025 | F2 | Frozen CDF mean | 664 | 28.899 | -13.262 / 23.413 / 79.508 |
| 2025 | F3 | Recent 3 control | 664 | -10.374 | -52.633 / -17.037 / 74.164 |
| 2025 | F3 | Pooled 8 control | 664 | -8.559 | -40.761 / -9.009 / 42.530 |
| 2025 | F3 | Frozen CDF mean | 664 | 22.360 | -40.636 / 25.090 / 62.187 |
| 2025 | F4 | Recent 3 control | 664 | 2.427 | -28.558 / 2.237 / 32.427 |
| 2025 | F4 | Pooled 8 control | 664 | 4.242 | -40.809 / 5.939 / 33.039 |
| 2025 | F4 | Frozen CDF mean | 664 | 35.161 | -38.663 / 42.170 / 87.041 |
| 2026 | F1 | Recent 3 control | 211 | 30.783 | 20.918 / 28.892 / 46.985 |
| 2026 | F1 | Pooled 8 control | 211 | 39.174 | 22.705 / 39.853 / 52.307 |
| 2026 | F2 | Recent 3 control | 211 | 0.102 | -27.583 / -1.639 / 51.122 |
| 2026 | F2 | Pooled 8 control | 211 | 8.492 | -14.486 / 11.807 / 37.742 |
| 2026 | F3 | Recent 3 control | 211 | -5.210 | -33.155 / -4.192 / 38.931 |
| 2026 | F3 | Pooled 8 control | 211 | 3.180 | -12.423 / 2.239 / 25.550 |
| 2026 | F4 | Recent 3 control | 211 | 10.751 | 4.179 / 11.638 / 16.170 |
| 2026 | F4 | Pooled 8 control | 211 | 19.142 | -1.531 / 15.139 / 35.568 |

### 2026 weekly MSE deltas versus pooled-eight

| Week | F1 | F2 | F3 | F4 |
|---|---:|---:|---:|---:|
| 1 | 25.640 | 12.545 | 3.021 | 17.560 |
| 2 | 44.878 | -6.851 | -12.423 | 35.497 |
| 3 | 52.113 | -14.486 | -4.886 | 10.610 |
| 4 | 52.307 | 18.336 | 1.458 | 35.568 |
| 5 | 34.828 | 11.068 | 11.921 | 12.718 |
| 6 | 22.705 | 37.742 | 25.550 | -1.531 |

## Weekly label coverage

| Season | Week | Offered | Supported played | Unknown |
|---|---:|---:|---:|---:|
| 2025 | 1 | 78 | 34 | 44 |
| 2025 | 2 | 78 | 41 | 37 |
| 2025 | 3 | 80 | 42 | 38 |
| 2025 | 4 | 78 | 39 | 39 |
| 2025 | 5 | 70 | 34 | 36 |
| 2025 | 6 | 73 | 33 | 40 |
| 2025 | 7 | 72 | 39 | 33 |
| 2025 | 8 | 68 | 34 | 34 |
| 2025 | 9 | 69 | 31 | 38 |
| 2025 | 10 | 67 | 34 | 33 |
| 2025 | 11 | 72 | 37 | 35 |
| 2025 | 12 | 68 | 32 | 36 |
| 2025 | 13 | 79 | 37 | 42 |
| 2025 | 14 | 70 | 36 | 34 |
| 2025 | 15 | 83 | 38 | 45 |
| 2025 | 16 | 81 | 43 | 38 |
| 2025 | 17 | 85 | 37 | 48 |
| 2025 | 18 | 88 | 43 | 45 |
| 2026 | 1 | 89 | 37 | 52 |
| 2026 | 2 | 89 | 39 | 50 |
| 2026 | 3 | 88 | 36 | 52 |
| 2026 | 4 | 90 | 34 | 56 |
| 2026 | 5 | 81 | 36 | 45 |
| 2026 | 6 | 78 | 29 | 49 |

## Interpretation limits

This is current-vintage reconstruction with the original query cutoffs and a seven-day assumed label-availability lag. It does not establish historical publication availability, original issuance, prospective performance or untouched confirmation evidence. Earlier 2025 labels legitimately enter later 2025 rolling histories; full 2025 labels enter the 2026 annual fold only after the 2025 forecasts are frozen. The 2026 Weeks 7+ protected outcomes were not opened.

The workload procedure and shared controls use cached lagged features whose provider and reconstruction provenance can differ from the accepted qualification used for labels and the first three histories. These are comparisons of complete procedures; they do not isolate a causal effect of only the training window or added context. Missing participation and the limited current-season span restrict generalization.

No probability, sportsbook selection, expected-value, calibration or deployment claim follows from these count means. The recipes remain unchanged after this result.

## All 12 categories

This pilot changes the evidence only for passing attempts. The remaining category adaptations are queued or blocked as below; none inherits a passing-attempt gain.

| Category | This pilot status |
|---|---|
| anytime_td | Queued Bernoulli probability design and proper scoring, no count-mean reuse |
| fantasy_ppr | BLOCKED exact offensive label contract |
| pass_att | Completed four-family count-mean comparison; no promotion |
| pass_cmp | Queued independent count-mean adaptation; no inherited gain |
| pass_int | Queued independently with rare-count zero/participation preservation |
| pass_td | Queued after rare-count zero/participation and source gates; no borrowed effect |
| pass_yd | Queued signed-yard functional choice; mean/median distinction required |
| rec | Queued eligible role/target volume design, no QB transfer |
| rec_yd | Queued independent signed-yard product preregistration |
| rush_att | Queued role/workload-specific count design, no QB transfer |
| rush_rec_yd | Queued direct-total/composite contract; no addition of medians |
| rush_yd | Queued signed-yard median/mean product preregistration |
