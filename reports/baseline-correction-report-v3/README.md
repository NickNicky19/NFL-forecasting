# Honest baseline corrections: all twelve categories

Two fixed correction arms completed their saved-row report. **Neither arm is nominated in any of the eleven scored categories.** Exact website PPR remains blocked because full-contract labels are not qualified. Independent cached-row arithmetic verification **PASSED**: 176 summaries, 880 main and 220 later paired comparisons, all eleven nomination lists and nine byte-reused reports reconciled.

These are **exposed 2022–2024 chronological development reconstructions**, across 815 distinct games and 54 season-week blocks. They are comparisons against the source-matched CDF, **not contemporaneous website or raw Sleeper forecasts**; those historical comparators are unavailable. Category observations overlap. Repeated methods and snapshots add no football games.

## Every primary category comparison

I = `cdf_offset_intercept_v1`; C = `cdf_offset_context_v1`. Positive signed improvement is lower primary error against the explicitly named CDF control. This is not prop-direction hit rate. Counts target a mean and use **MSE**; signed yards use the declared **MAE** point objective; anytime TD uses **Brier**. Do not pool their units. All scored primary cells cover the same 815 games/54 blocks within their category.

| Target | Matched player-games | Primary loss | CDF loss | I loss | I gain vs CDF | C loss | C gain vs CDF | Decision |
|---|---:|---|---:|---:|---:|---:|---:|---|
| [pass_yd](target-reports/pass_yd.json) | 1,960 | MAE | 66.16173469 | 66.16173469 | +0.0000% | 66.16173469 | +0.0000% | Neither nominated |
| [pass_td](target-reports/pass_td.json) | 1,960 | MSE | 1.06824166 | 1.06778155 | +0.0431% | 1.06235040 | +0.5515% | Neither nominated |
| [pass_cmp](target-reports/pass_cmp.json) | 1,960 | MSE | 51.37535676 | 51.40822167 | -0.0640% | 51.65201367 | -0.5385% | Neither nominated |
| [pass_att](target-reports/pass_att.json) | 1,960 | MSE | 114.20693762 | 114.17545158 | +0.0276% | 114.94990933 | -0.6505% | Neither nominated |
| [pass_int](target-reports/pass_int.json) | 1,960 | MSE | 0.67906633 | 0.67917922 | -0.0166% | 0.67961718 | -0.0811% | Neither nominated |
| [rush_yd](target-reports/rush_yd.json) | 4,558 | MAE | 19.71895568 | 19.71895568 | +0.0000% | 19.71895568 | +0.0000% | Neither nominated |
| [rush_att](target-reports/rush_att.json) | 4,558 | MSE | 24.29274701 | 24.40616026 | -0.4669% | 24.22763024 | +0.2681% | Neither nominated |
| [rec](target-reports/rec.json) | 15,251 | MSE | 3.26820150 | 3.27501313 | -0.2084% | 3.26980279 | -0.0490% | Neither nominated |
| [rec_yd](target-reports/rec_yd.json) | 15,251 | MAE | 16.37243459 | 16.37243459 | +0.0000% | 16.37243459 | +0.0000% | Neither nominated |
| [rush_rec_yd](target-reports/rush_rec_yd.json) | 15,251 | MAE | 21.02570323 | 21.02570323 | +0.0000% | 21.02570323 | +0.0000% | Neither nominated |
| Exact website PPR | 0 | unavailable | — | — | — | — | — | BLOCKED: exact labels |
| [anytime_td](target-reports/anytime_td.json) | 15,251 | BRIER | 0.14096924 | 0.14096516 | +0.0029% | 0.14097367 | -0.0031% | Neither nominated |

Across these 22 candidate/CDF primary cells: **5 improve, 9 worsen, 8 are unchanged**. These counts are descriptive and dependent, not replications or a pooled accuracy score. All 22 fail the fixed development nomination rules. Even a development nomination would require later independent confirmation and operational qualification.

## What was actually fitted

- Exactly 44 earlier-only fit attempts: eleven targets × two arms × 2023/2024. All 66 offered-population forecast and scored files are frozen. The 22 startup-2022 files retain the exact appropriate CDF reference. All 2023 forecasts froze before 2023 labels trained later corrections; the global forecast freeze preceded final scoring.
- Count means: nonnegative CDF **mean** × exp(X beta), fitted Poisson mean objective with fixed ridge lambda 1 including the intercept. Exact baseline zero is retained. A Poisson objective supplies no calibrated count law.
- Signed yards: CDF **median** + X beta; fixed median regression, alpha .1, no separate fitted intercept, fixed solver and time limit. Signed support is retained. These four yardage categories produce unchanged predictions under both arms in this study.
- Anytime TD: genuine saved probability with a shrunk logit correction, fixed lambda 1, exact 0/1 retained without undisclosed clipping. Only these actual binary probabilities receive Brier/log-loss scoring.
- Context: lagged workload trend, prior player-game count and team-opportunity proxy, plus original missingness flags. Earlier-training-only imputation/standardization. No newly qualified injury, news, route or weather information entered this study.
- Nonprimary roles retain their original CDF reference; sparse/missing features are retained with flags and declared whole-package fallback. All offered rows and known participation/outcome states remain visible.

[Exact core](../../nfl_lab/baseline_correction.py), [fixed scientific policy](../../config/baseline-correction-v1.json), [orchestrator](../../tools/baseline_correction_orchestrator.py), and [original execution record](../baseline-correction-v1/README.md) define the recipe and failure handling. The original scientific policy SHA-256 is `0e94af3599fb525e933989c6adaa29385f4da6ef13f6cba5258f47d205aea03a`.

## Full comparisons, uncertainty and limitations

Each target link above opens its complete immutable aggregate report: both arms versus CDF, count A, role B, recent and pooled controls; annual and pooled results; all-offered and primary-role coverage; MAE/MSE/RMSE, signed bias, p90/p95/max misses, fallback/outcome states, binary log loss and reliability; 2023–2024 descriptive pairs; and every nomination reason. The compact [twelve-category matrix](category-status.json) and [full index/pointers](aggregate-report.json) preserve all twelve targets. Private row-level paired losses and player/team/opponent subgroups remain retained under their owned hashes, not redistributed publicly.

The unchanged uncertainty procedure uses 500 PCG64 seed-1703 paired whole-week/game nominal development diagnostics, with linear percentile intervals. These are exposed-data diagnostics, not untouched confirmation or simultaneous production certification. The primary includes startup aliases; the separate 2023–2024 descriptive view must not replace it after seeing results. The independent arithmetic check verifies interval metadata/cluster membership without a second bootstrap.

The original reconstructed kickoff-plus-seven-day lag and incomplete participation/true-zero evidence remain. Missing outcomes are not imputed or relabeled DNP/zero. Authentic historical SITE/raw forecasts are N/A. These limits prevent claims about future advantage or the complete deployment population. Exact PPR has zero qualified scored rows, not fabricated zeros.

## Execution and preserved failures

The original 44-fit study remains **FAILED / CPU_LIMIT during reporting**, despite saving all forecasts/scored rows and four reports. Its separate V2 reporting pass remains **FAILED / retention admission**, saving five more reports. V3 reused all nine complete report/paired/subgroup triplets byte exactly and aggregated only combined yards and anytime TD from twelve saved candidate plus thirty control files; all 231 candidate/control references were authenticated. It added zero fits, forecasts, outcome joins, source queries, model/law calls or HTTP.

[Actual V3 supervisor](actual-execution.json): COMPLETED, 72.74647138 wall seconds, 85.153985091 CPU seconds, 622,813,184 bytes sampled combined peak RSS; 5,686,616 charged new retained bytes. Caps: 300 wall/CPU seconds, 1 GiB combined RSS, two explicit numerical threads, 16 MiB new/512 MiB shared. Sampled RSS can miss brief peaks. The metadata seal transfer's one-thread conformance was **unverified**; that limitation is retained in [the transfer record](review/metadata-transfer-limits.json), separately from accepted byte integrity and the actual explicitly capped run. No failed execution was relabeled successful.

No scientific promotion, RELEASE_READY claim, website/default change, scheduler activation or deployment results from this study. Retain the strong incumbent; continue with new information and separately registered candidates.

## Independent arithmetic acceptance

[Exact receipt](review/ARITHMETIC_PASS.json): one saved-row check read 231 scored files / 1,992,144 row incidences (repeated method/category rows, not independent games). It reconciled numeric errors, binary scores, coverage/support, contexts, fallbacks, startup aliases and nomination rules. Wall 18.015486967 seconds, CPU 18.001860787 seconds, peak process RSS 177,819,648 bytes; zero denied effects. It did not retrain, generate forecasts, access source/query/model data or resample bootstrap intervals. Interval metadata/cluster membership passed; subgroup values were not independently recomputed. No new confirmation sample or website-relative gain follows.
