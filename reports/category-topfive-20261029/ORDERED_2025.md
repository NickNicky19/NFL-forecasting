# 2025 ordered-history CDF comparison — completed

**Result:** adding four ordered prior-game slots lowered carry median MAE by **2.00%** and reception median MAE by **0.46%** against the matched retained CDF. The carry game/week intervals exclude zero; reception intervals include zero. This is exposed historical development evidence, not a demonstrated win against today's website.

## Primary median forecasts

| Category | Supported / planned | Matched CDF MAE | Ordered CDF MAE | Lower MAE | Total absolute error reduced |
|---|---:|---:|---:|---:|---:|
| Rushing attempts (RB) | 1,566 / 2,079 | 3.40868455 | 3.34035760 | 2.0045% | 107 count-error units |
| Receptions (RB/WR/TE) | 5,295 / 7,271 | 1.17865911 | 1.17318225 | 0.4647% | 29 count-error units |

MAE is the average distance from the actual statistic, measured here in carries or catches. Lower is better. The reduced total error is not a count of extra winning prop picks.

## Same evidence and fixed learner

- Evaluation: **2025 regular season, all 18 weeks and 272 games**. Models train once on eligible **2019–2024** target rows before the first 2025 query cutoff; no model trained on 2025 is evaluated as a 2025 forecast.
- The exact original annual training view, CDF feature representation, imputation, roles and full-support priors were authenticated. Both retained baseline models were loaded only to check audits and priors; no baseline refit or inference was performed. Complete archived CDF means/medians and corrected Count A means were reused.
- The unchanged learner has 32 ExtraTrees, depth 8, minimum leaf 30, squared-error splits, seed 1701 and two forest workers. Its distribution remains 95% empirical leaf outcomes plus 5% training prior.
- The only new information group is four individual prior-game slots, ages and played/DNP/unknown flags: carries for the carry model; receptions and targets for the reception model. Unsupported values remain missing; unknown/DNP games retain their slots. This does not complete an injury-aware, teammate-availability or finite-allocation system.
- Availability is checked before game chronology. The original seven-day historical availability assumption is preserved; it is not proof of original publication timing. Earlier postseason games may enter historical feature slots, while target training and evaluation remain regular season. Earlier 2025 source values enter only later cutoff-qualified feature queries.
- Every new model and forecast was durably frozen and exactly read back before evaluation labels were projected. All point values, identities and fallbacks remained bit-identical through grading. The periods were already examined, so this is not untouched confirmation or genuine issued pregame evidence.

## Coverage and retained missingness

| Target | Scored | Unknown participation | Played but statistic missing | Genuine supported zero outcomes | Planned fallback rows |
|---|---:|---:|---:|---:|---:|
| Rushing attempts (RB) | 1,566 | 509 | 4 | 288 | 57 |
| Receptions (RB/WR/TE) | 5,295 | 1,965 | 11 | 1,485 | 180 |

All **8,701 original all-role player-game queries** remain in both target attempts: **17,402 new ordered forecast rows**, plus the same number of reused CDF rows and reused corrected Count A points. The 52,206 method rows are not 52,206 independent football observations. The primary target populations contain 9,350 memberships and 6,861 supported target outcomes; categories overlap. Fallback counts and supported populations are unchanged. Unknown values were not converted into zeros.

## Uncertainty and adverse diagnostics

Paired bootstrap: 500 resamples, seed 1703; games and weeks are clustered separately. Intervals below describe candidate-minus-control MAE, so negative values favor the ordered model.

| Category | Game 95% interval | Week 95% interval | Two-target adjusted game interval | Two-target adjusted week interval |
|---|---|---|---|---|
| Rushing attempts (RB) | [-0.101480, -0.034339] | [-0.097047, -0.040869] | [-0.103877, -0.029550] | [-0.101163, -0.038449] |
| Receptions (RB/WR/TE) | [-0.012383, +0.001898] | [-0.011881, +0.001037] | [-0.013346, +0.002628] | [-0.012207, +0.001831] |

These account for the two registered target comparisons, not every adaptive research choice made across the project. Historical selection and source-timing limitations remain.

| Median diagnostic | Carries: CDF → ordered | Receptions: CDF → ordered |
|---|---:|---:|
| Signed bias | -0.78544 → -0.80524 | -0.26006 → -0.26516 |
| 95th-percentile absolute error | 10.00000 → 10.00000 | 4.00000 → 4.00000 |
| Strict error <1 (%) | 13.21839 → 14.43167 | 32.16242 → 32.06799 |
| Inclusive error ≤1 (%) | 35.31290 → 36.33461 | 71.87913 → 72.33239 |

Median underprediction becomes slightly larger in both categories. Reception strict-within-one accuracy declines slightly despite lower MAE. No subgroup training or automatic top-player specialization was performed.

## Mean forecasts remain separate

| Category | CDF mean MSE / RMSE | Corrected Count A mean MSE / RMSE | Ordered mean MSE / RMSE |
|---|---:|---:|---:|
| Rushing attempts (RB) | 22.34080124 / 4.72660568 | 22.24783432 / 4.71676100 | 21.97212298 / 4.68744312 |
| Receptions (RB/WR/TE) | 2.85126621 / 1.68856928 | 2.84721698 / 1.68736984 | 2.83168525 / 1.68276120 |

These are secondary expected-value results, not the median primary. Mean-MSE uncertainty was not newly estimated. A Count A mean is not relabeled a median or an authenticated probability distribution.

## Distribution diagnostics — candidate only

| Category | Ordered CRPS | Ordered log loss | Supported rows | Positive-infinite event losses |
|---|---:|---:|---:|---:|
| Rushing attempts (RB) | 2.40596695 | 2.61205493 | 1,566 | 0 |
| Receptions (RB/WR/TE) | 0.83614515 | 1.66547378 | 5,295 | 0 |

Compatible baseline proper-score reproduction was not run. These candidate diagnostics do **not** establish improved distributions, calibration, over/under probabilities, estimated EV or paper returns. No compatible prop lines/prices were included.

## Every evaluation week retained

| 2025 week | Carry MAE: CDF → ordered | Reception MAE: CDF → ordered |
|---|---:|---:|
| 1 | 3.589474 → 3.484211 | 1.254717 → 1.254717 |
| 2 | 3.184783 → 3.217391 | 1.223684 → 1.233553 |
| 3 | 3.630435 → 3.532609 | 1.255663 → 1.275081 |
| 4 | 3.806818 → 3.579545 | 1.224026 → 1.198052 |
| 5 | 2.872093 → 2.744186 | 1.206406 → 1.199288 |
| 6 | 3.289157 → 3.192771 | 1.209790 → 1.188811 |
| 7 | 3.058140 → 3.046512 | 1.196610 → 1.189831 |
| 8 | 3.602564 → 3.564103 | 1.165354 → 1.157480 |
| 9 | 3.097561 → 3.060976 | 1.054152 → 1.072202 |
| 10 | 3.455696 → 3.341772 | 1.106227 → 1.098901 |
| 11 | 3.839080 → 3.735632 | 1.225694 → 1.222222 |
| 12 | 3.389610 → 3.272727 | 1.251825 → 1.262774 |
| 13 | 3.617978 → 3.561798 | 1.145631 → 1.116505 |
| 14 | 3.035714 → 3.023810 | 1.087413 → 1.059441 |
| 15 | 3.301075 → 3.247312 | 1.193980 → 1.197324 |
| 16 | 3.010989 → 3.010989 | 1.177215 → 1.180380 |
| 17 | 3.387097 → 3.311828 | 1.107595 → 1.088608 |
| 18 | 4.131868 → 4.131868 | 1.115894 → 1.109272 |

## Execution and preserved failures

- Original 2025 V1 failed before training rows, model loads or fits when an acquisition-heavy import attempted a local socket capability probe and the full socket guard rejected it. Its consumed capsule and native failure remain retained; the attempted failure capsule itself was **not** retained. No original fit slots or budget were refunded.
- Separately registered technical V2 replaced only the acquisition-heavy relative data import and its immutable target tuple reference in the original fold adapter. Function AST equivalence and import under the full unchanged socket/child deny passed with zero NFL values, fits or model loads. The exact original training view still had to match before fitting.
- V2 reused the original eight completed fictional checks. It performed **2 new forest fits / 64 trees**, generated **17,402 new historical forecast rows**, then performed 2 law-scoring passes on the same 17,402 query rows. No extra fit was used to repair or rescore.
- Parameters and available partial forecasts are retained on failure within the declared private allocation. The technical retention fix permits evidence-only failure archiving; it does not relax network or numerical execution guards.
- Successful V2 usage: **154.977396 CPU seconds, 151.690195 wall seconds, 727,998,464 bytes peak RSS**, 3 managed writes and zero blocked calls. Exact freeze and grade readbacks completed; all original 2026 failures/results remain unchanged.

## Operational status and next work

**Research comparison completed. No new genuine pregame capture, operational admission, selection, deployment or live website change was made by this study.** It does not change the completed 2026 ranking or establish a win against authentic website forecasts. Any admission/release remains with the existing producer, weekly policy and production integrator.

Next independent work remains qualified carry roles/teammates/team opportunities, receiving opportunity/catch quality, QB volume/throw quality, and genuine matched-time challenger/website capture. A missing route or injury source does not invalidate this completed ordered-history comparison.
