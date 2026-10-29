# Missing modern count medians: completed comparison

**Completed:** zero new fits; four authenticated cached forecast projections and one retained-model inference. The full five-cell vectors were frozen and read back before labels were decoded.

MAE means the average miss in the statistic’s own units. These are comparisons with the same CDF law’s mean on the same supported QB player-games. They are **not measured improvements over the live website**.

| Period / target | Played rows / games / weeks | CDF mean MAE | CDF lower-median MAE | Signed MAE improvement | Recent3 / Recent8 MAE |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2025 pass_att | 664 / 272 / 18 | 8.663631 | 8.643072 | +0.2373% | 9.268721 / 9.204983 |
| 2025 pass_int | 664 / 272 / 18 | 0.640959 | 0.549699 | +14.2381% | 0.658548 / 0.644614 |
| 2026 pass_td | 211 / 93 / 6 | 0.878612 | 0.824645 | +6.1424% | 1.009631 / 0.879280 |
| 2026 pass_att | 211 / 93 / 6 | 7.898497 | 7.772512 | +1.5951% | 9.102149 / 8.378339 |
| 2026 pass_int | 211 / 93 / 6 | 0.628663 | 0.601896 | +4.2578% | 0.643136 / 0.635798 |

The lower median had the lowest MAE in each of these five cells among the procedures in this screen. This is not an all-method winner claim: the reconciled category record must also retain every other compatible control. Both recent-history controls lost to the CDF mean in all five cells. The zero-interception point scored MAE 0.569277 in 2025 and 0.616114 in 2026, worse than the CDF median in each; it is not a probability model.

## Adverse findings and uncertainty

**All five medians worsened MSE/RMSE.** A mean and median answer different forecast questions. These results do not authorize replacing an expected-value product with an unlabeled median, and they measure no change in over/under probabilities.

| Period / target | Mean → median MSE | Mean → median bias | Mean → median p95 absolute error | Game-cluster interval for median minus mean MAE |
| --- | ---: | ---: | ---: | --- |
| 2025 pass_att | 124.098901 → 131.567771 | +1.655710 → +1.118976 | 23.797957 → 25.000000 | [-0.210171, +0.180146] |
| 2025 pass_int | 0.602122 → 0.881024 | +0.053762 → -0.474398 | 1.341966 → 2.000000 | [-0.131853, -0.047756] |
| 2026 pass_td | 1.158267 → 1.345972 | -0.044886 → -0.360190 | 2.080813 → 2.000000 | [-0.109380, -0.004020] |
| 2026 pass_att | 104.078472 → 106.056872 | -1.422216 → -1.753555 | 20.740355 → 21.500000 | [-0.360632, +0.115040] |
| 2026 pass_int | 0.526397 → 0.867299 | +0.012970 → -0.573460 | 1.378147 → 2.000000 | [-0.099667, +0.060700] |

The intervals are nominal 500-replicate paired game-cluster development intervals with seed 1703. They do not correct selected-winner claims for the complete prior search. 2025 week intervals are retained in the JSON; 2026 has only six weeks, below the registered eight-cluster requirement, so its week interval is unavailable. The 2026 TD game interval excludes zero; the 2026 attempt and interception intervals include it.

## Population and fallbacks

Every arm attempted the original full QB population: 1,359 query rows in each 2025 cell and 515 in each 2026 cell. Each 2025 cell admitted 664 played numeric labels and 695 unknowns; each 2026 cell admitted 211 played labels and 304 unknowns. Unknown participation was never changed to zero. No numeric unqualified counts or context mismatches were encountered; the new quarantine guard remains implemented.

CDF means and medians retain 28 model-fallback query rows in 2025 (7 scored) and 30 in 2026 (1 scored). Recent3 uses 465 / 218 fallback query rows and 85 / 27 scored fallback rows in 2025 / 2026; recent8 uses 246 / 148 query and 33 / 12 scored fallback rows. Their declared fallback is the same stored CDF mean.

The five cells contain 4,263 category-query opportunities and 18,926 method forecast rows. They overlap: the two original QB query populations total 1,874 unique player-games across 365 games and 24 season-weeks. The passing-attempt reference alone has 875 admitted played player-games across the two seasons; repeated category and method rows are not additional players or games. Multiple targets, methods and replicas are not extra NFL observations.

The original seven-day availability assumption, current-vintage history, exposed periods and unknown participation remain limitations. No later protected outcome source was opened.

## Execution and durable evidence

- Plan: `next-nfl-count-median-completion-v1`; root seal SHA256 `c85d13b7c8ee4cc413b6215c7f9f9ea8b8f246c73a04989552c5f396077248e8`.
- Source: `tools/next_checkpoint_count_medians_v1.py`, 36,436 bytes; SHA256 `693cdb4eab64824dfbdc0c6c102eba2e15fad46337e313d80c3bd0a31bbe7eab`.
- Complete forecast capsule: 114,560 bytes; SHA256 `a4a7b96be5a71d28e09c2c806634083e219f867759563c257541966edd785674`.
- Complete grade capsule: 275,677 bytes; SHA256 `2c014fb7247fa8993cfd67b635a1b8863c2410376d158061cf7c87fe1e3154d3`.
- Both capsules and all inner members passed byte exact private CAS readback. Original row-level forecasts and grades stay in the approved private namespace.
- Final usage: 41.456897 CPU seconds; 41.456113 wall seconds; peak RSS 274,694,144 bytes; two managed calls; no retries, HTTP, fits or new priors.
- One original fixture replay passed exact bits; the newly extracted passing-attempt means and fallback reasons matched the existing retained control exactly. This is a separately versioned current-runtime restoration; it does not recover missing original median vectors or authenticate the original runtime.
- The original fixture-startup software receipts remain separate from NFL accuracy evidence. Actual agent/model setting is UNATTESTED.

## Independent cached-row acceptance

A separate root checker passed **14,336 scalar arithmetic checks**, including all
18,926 frozen forecast rows, 8,719 scored method incidences, full forecast/grade
parity, every cell and weekly metric, count support, unknown masks and independently
vectorized game/week bootstrap intervals. It used 1.306056 CPU seconds, 1.308526
wall seconds and 135,892,992 bytes peak RSS, with zero fits, model restores, new
forecasts, network or CAS writes. This checks frozen-row arithmetic; it does not
independently establish the underlying source truth or add football observations.

Receipt: `LOWEST_COUNT_MEDIAN_NUMERICAL_ACCEPTANCE_V1.json`, 2,315 bytes; SHA256
`841c4480e282449db08cefa2881e536496a4f557b9339ebec2f4c33ddcd4249a`.

## Release status

**Research result only; no production change by this worker.** The live count outputs retain their declared contracts. Any MAE-point or median entrant needs separate operational/product selection and consumer validation through the existing production owner. This checkpoint does not claim a better prop probability, ranking or paper return.

All per-week scores, paired comparisons, coverage, bias, tails, tolerance rates and execution identities are in `PUBLIC_RESULTS.json`. Private `GRADED_ROWS.parquet` joins each method point to its actual outcome and error. Original studies, failures, scientific registrations and consumed budgets remain unchanged.
