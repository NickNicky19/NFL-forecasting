# Anytime-TD Bernoulli blends — October 25, 2026

**Completed and independently accepted; both descriptive advance flags are false.**

Two fixed blend arms reuse the same saved fresh-CDF and CatBoost-medium probabilities and the earlier-only Beta(1,1) event-rate control. The outcome is at least one rushing or receiving touchdown, conditional on playing, for the original RB/WR/TE population. No sportsbook prices enter this comparison.

[Complete annual/pooled aggregate](aggregate.json) · [Source and acceptance hashes](PUBLIC_PROVENANCE.json) · [Fixed registration](../../config/anytime-td-blend-v1.json)

## Results and adverse findings

The pooled 2023–2024 assessment covers **10,157 supported played outcomes / 14,282 offered forecasts**, **544 games and 36 season-week blocks**. It retains **4,101 unknown-participation offers**, **24 played outcomes with missing labels**, and **366 base-fallback offers** for each component and blend. DNP and invalid-label counts are zero in this assessment. These are overlapping method comparisons on previously exposed historical data.

| Product | Brier | NLL | Probability-minus-event bias | p95 absolute error | Advance |
|---|---:|---:|---:|---:|---|
| Frozen fresh CDF | 0.1410210129387159 | 0.4451926082876003 | 0.0072459151145459234 | 0.8189046947857008 | control |
| Frozen CatBoost medium | 0.1408207456484522 | 0.4446794058279148 | 0.004024617281968897 | 0.8265071831903167 | control |
| Earlier-only Beta(1,1) rate | 0.1558285276544535 | 0.49075734226452783 | -0.006090120915333165 | 0.8131868131868132 | control |
| Fixed 50/50 mixture | 0.14075272099675418 | 0.4444184887625955 | 0.005635266198257413 | 0.821971116952567 | false |
| Shrunk Brier weight | 0.1407477673135858 | 0.4444027028819286 | 0.005506405527502116 | 0.8218580224805802 | false |

Against CatBoost medium, the fixed and learned arms lower pooled Brier by about **0.048305845%** and **0.051823568%**, respectively; against the fresh CDF, by about **0.19024962%** and **0.19376235%**. These comparisons concern only the two specified bases and rate control. They establish no best-overall ranking.

**Both blends worsen absolute pooled bias versus CatBoost medium, and both lose to it on 2024 Brier. Every CatBoost paired week/game 95% interval in the aggregate includes zero.** Both advance flags are false under this study's prespecified diagnostic rule. This study nominates no replacement and performs no automatic selection or deployment; it does not change the separate provisional-release policy.

| Year | CatBoost Brier | Fixed-half Brier | Shrunk-weight Brier |
|---|---:|---:|---:|
| 2023 | 0.13882982883550476 | 0.1386649426752947 | 0.1386657966070088 |
| 2024 | 0.14279876741629124 | 0.14282697690710314 | 0.14281625322461472 |

Pooled Brier intervals below describe candidate-minus-CatBoost loss; negative differences favor the blend.

| Arm | Week 95% interval | Game 95% interval |
|---|---|---|
| Fixed 50/50 mixture | [-0.00025233488230448777, 0.00014684421023920585] | [-0.0002764701546114867, 0.00012677842439189912] |
| Shrunk Brier weight | [-0.00024290850448145635, 0.00012723966384284966] | [-0.00026557380475479385, 0.00010887237745395656] |

The aggregate retains all **6 pooled and 12 annual primary contrasts**, their matching secondary NLL comparisons, fixed-tenth calibration bins, bias, p95, coverage and fallback diagnostics. Paired uncertainty uses **500 PCG64 whole-season-week/game replicates**, seeds **1931/1932**, and linear nominal 95% percentiles. No row bootstrap is used. NLL is unclipped: true infinity remains explicit in the evaluator; this run has zero infinite losses.

A separate independent postrun diagnostic found **171 scored outcomes among 366 fallback offers**, with the same Brier of approximately **0.1118070713** for both bases and both blends. The **9,986 scored nonfallback rows** contain the gains and bias regression. All fallback offers remain in the primary population. The 3,920 player/team/opponent/position/fallback diagnostic records remain private; they add no trial or football observations. No selected-line comparison was made.

## Fixed recipe, source clocks and freeze order

- Fixed arm: `p = 0.5*pCDF + 0.5*pCat`.
- Learned arm: `wCDF = clip((mean((y-pCat)*(pCDF-pCat)) + 0.001*0.5) / (mean((pCDF-pCat)^2) + 0.001), 0, 1)` and `p = wCDF*pCDF + (1-wCDF)*pCat`. The single shrinkage constant is fixed; there is no search.
- Exactly two scalar weight fits use earlier out-of-fold labels: 2022 for the 2023 forecast, then 2022+2023 for 2024. Training requires supported played labels with known availability strictly before the first evaluation cutoff. The prespecified minimum is 200 supported rows, 30 positives and 30 negatives; otherwise the charged weight attempt retains 50/50 with an explicit reason.
- Both component probabilities are required. Equal all-offered availability masks are checked before fitting; unequal masks reject the input. Shared missingness remains an abstention. Contrasts with unequal forecast masks are unavailable rather than scored on intersections. All actual component and candidate masks match, with no unsupported forecasts.
- Both 2023 forecasts and their learned weight freeze before 2023 labels can train 2024. All two learned weights and four forecast factors freeze before evaluation scoring. The **28,564 probability outputs** are repeated method incidences over the same 14,282 offers.
- The same accepted input reader, exact context/label alignment, freezer, probability scorer and cluster bootstrap are reused. Availability remains a current-vintage reconstructed kickoff-plus-seven-day clock, not an authenticated historical publication time.

There are **zero new base-estimator fits, original calibration calls, base-model loads or base inference calls, HTTP calls or operational-CAS writes**. Factor outputs reference the original context, labels and component forecasts instead of copying those rows. Original sixteen calibration attempts, adverse losses and earlier failures remain retained without rerun or refund. All 2022–2024 data are exposed development evidence; historical SITE/R0 forecasts are unavailable. Independent arithmetic acceptance adds no football observations or scientific confirmation.

## Acceptance, resources and software packaging

Independent numerical acceptance passed **7,030 checks** with zero findings, covering **two learned weights, four factor files, fifteen summary cells, eighteen registered contrasts and seventy-two interval records**. Each source/content identity, the one-run authority, results and scope are hash-bound in the accompanying provenance. Player/game rows, IDs and fitted-model bodies are excluded.

The finite allocation was **60 CPU / 90 wall seconds, 512 MiB combined RSS, 8 GiB address space, two threads and 2 MiB private output including terminal reserves**, with zero automatic retries. Observed combined use was **7.5899701109999995 CPU / 5.376708817027975 wall seconds**, **280,682,496 bytes** conservative RSS, and **417,665 payload bytes + 65,536 reserved receipt bytes = 483,201 bytes**. The parent remained a fresh stdlib monitor; the unchanged accepted ownership guard precedes the separate numerical worker.

Public packaging retained two failed fictional-test attempts: first a missing shared runner (5 passed / 1 failed, 1.29 seconds), then a missing startup helper (5 passed / 1 failed, 1.54 seconds). The fixture now uses repository-local shared source; both copied dependencies are byte-identical to the original accepted versions. The final public check passed **6 tests in 1.94 seconds**, with no skipped or weakened check. This packaging repair changes no executed recipe or NFL metric. The unchanged mapped-libc thread helper is also included for runtime source auditing. Scientific replay requires the authenticated inputs and exact execution authority; the fictional tests use generated data.

## Other study checkpoint

The retained V7/V8 workload startup failures produced zero completed forward comparisons. V9 passed startup repair, then **failed numeric-query validation: “approved numeric feature dtype/value changed.”** It still produced zero completed forward comparisons. V9 spent **52.964827 CPU / 42.603011769009754 wall seconds**; the V7–V9 cumulative charge is **122.074228 CPU / 100.09144812399644 wall seconds**. The recorded V9 source phase spent **17.86447758 CPU / 17.873875306017 wall seconds**. Unreported counters remain unavailable; a future correction is unmeasured.

The separate PBP source pilot has completed authenticated acquisition and derived-schema inspection. GSIS conversion, target/participant joins and availability clocks remain unqualified, so it supplies no new qualified outcome labels or forecast improvement. A V10 technical dtype correction remains in preparation with no actual V10 run. No website model, R0 policy, scheduler, frozen registration or scientific qualification changes follow from this blend report.
