# Twelve-category role and count comparison

Completed 2026-10-23. All 12 targets are explicit: **11 scored, exact offensive PPR blocked**. One shared pipeline completed 136 estimator fits and froze 88 supported packages; 48 new-model packages, 40 byte aliases and 8 PPR blocks preserve the full 96-package matrix. There are 44 available primary contrasts and 4 blocked contrasts. No replacement is qualified or activated.

The study tests changes to the count objective and role partitions on the exact prior HGB source packet. Arm A uses Poisson HGB for six count targets and reuses the exact old yard/TD forecast bytes. Arm B splits the existing modeled roles; QB-only passing aliases A. Fixed parameters and training-only preprocessing are in [the method manifest](method-manifest.json) and [the registered design](../../docs/ROLE_COUNT_RESEARCH.md). A Poisson training objective supplies a point heuristic, not a calibrated count law.

## Original website comparison

These are original locally saved 2026 Week 6 website points versus candidates calculated after those games. All 2,083 original category opportunities remain. Every row below is paired on that target’s same supported player-games. All rows span 13 games and **one exposed week**. Numeric errors are MAE in target units; anytime TD is Brier. Positive improvement means lower error. No arm is selected from this table.

| Category | Paired n | SITE error | A error | B error | A improvement | B improvement |
|---|---:|---:|---:|---:|---:|---:|
| Passing yards | 27 | 56.622963 | 52.017734 | 52.017734 | +8.13% | +8.13% |
| Passing TDs | 27 | 0.844444 | 0.774597 | 0.774597 | +8.27% | +8.27% |
| Completions | 27 | 4.563704 | 4.875530 | 4.875530 | -6.83% | -6.83% |
| Passing attempts | 27 | 7.145926 | 7.849258 | 7.849258 | -9.84% | -9.84% |
| Interceptions thrown | 27 | 0.663704 | 0.610739 | 0.610739 | +7.98% | +7.98% |
| Rushing yards | 96 | 16.544896 | 14.998443 | 14.901443 | +9.35% | +9.93% |
| Rushing attempts | 69 | 3.425652 | 3.773399 | 3.776561 | -10.15% | -10.24% |
| Receptions | 252 | 1.282183 | 1.345929 | 1.335485 | -4.97% | -4.16% |
| Receiving yards | 252 | 15.340675 | 15.694940 | 15.645688 | -2.31% | -1.99% |
| Rushing + receiving yards | 189 | 19.867989 | 20.628914 | 20.525054 | -3.83% | -3.31% |
| Exact offensive PPR | 0 | N/A | Blocked | Blocked | N/A | N/A |
| Anytime rushing-or-receiving TD | 243 | 0.145864 | 0.141393 | 0.141500 | +3.07% | +2.99% |

Raw Sleeper, original SITE, specified simple control, old HGB and old CDF remain separately named in [the complete category matrix](category-status.json). Each comparison retains its own paired n, error, bias, tails and missingness. The additional all-controls-common cohort avoids comparing unequal populations. Historical outcomes do not recreate old Sleeper forecasts.

## Multi-season historical comparison

2022-2024 expanding earlier-year training uses reconstructed current vintage data and an assumed seven-day historical availability lag. These years were already exposed, including 2024-2025 QB findings; no new confirmation is claimed. The historical primary comparator is **old HGB**, not the website. Original primary role populations are retained, with all offered and role/team/opponent/season/fallback views in the aggregate JSON.

| Category | Primary n / games / weeks | Old HGB error | A error | B error | A improvement | B improvement |
|---|---:|---:|---:|---:|---:|---:|
| Passing yards | 2049 / 854 / 66 | 66.644823 | 66.644823 | 66.644823 | +0.00% | +0.00% |
| Passing TDs | 2049 / 854 / 66 | 0.794243 | 0.834710 | 0.834710 | -5.09% | -5.09% |
| Completions | 2049 / 854 / 66 | 5.661895 | 5.733091 | 5.733091 | -1.26% | -1.26% |
| Passing attempts | 2049 / 854 / 66 | 8.380911 | 8.489839 | 8.489839 | -1.30% | -1.30% |
| Interceptions thrown | 2049 / 854 / 66 | 0.623231 | 0.684734 | 0.684734 | -9.87% | -9.87% |
| Rushing yards | 4766 / 854 / 66 | 33.535879 | 33.535879 | 19.671179 | +0.00% | +41.34% |
| Rushing attempts | 4766 / 854 / 66 | 7.741502 | 3.672528 | 3.668421 | +52.56% | +52.61% |
| Receptions | 15975 / 854 / 66 | 1.300898 | 1.340644 | 1.345025 | -3.06% | -3.39% |
| Receiving yards | 15975 / 854 / 66 | 16.381072 | 16.381072 | 16.383847 | +0.00% | -0.02% |
| Rushing + receiving yards | 15975 / 854 / 66 | 20.918209 | 20.918209 | 20.938837 | +0.00% | -0.10% |
| Exact offensive PPR | 0 | N/A | Blocked | Blocked | N/A | N/A |
| Anytime rushing-or-receiving TD | 15975 / 854 / 66 | 0.143339 | 0.143339 | 0.143271 | +0.00% | +0.05% |

Saved game/week clustered 500-draw intervals are nominal, unadjusted descriptive diagnostics; they do not satisfy confirmation or multiple-search promotion gates. Week 6 has no inferential interval. Aliases and repeated snapshots add no independent observations.

## Adverse findings and decisions

- **No uniform improvement.** Five targets improve the Week 6 primary loss in both arms; six worsen; exact PPR has no qualified score. Improvements do not establish superiority outside this exposed cohort.
- **Counts:** Passing TD and interception Week 6 gains reverse against old HGB historically. Completions and attempts worsen versus SITE. Receptions also worsen; no objective was changed after results.
- **Rushing attempts:** The earlier all-zero HGB failure remains preserved. Both new arms cut historical RB MAE about 53% against that failed model, but still lose SITE by about 10% in Week 6 and lose the older CDF historical control. Fixing that failure does not establish the strongest model.
- **Rushing yards:** Role B historical RB MAE 19.67118 improves sharply against old HGB 33.53588, but old CDF 19.53462 is still lower on those same rows. Week 6 role B MAE improves 9.93% versus SITE. Bias and tails remain separate acceptance conditions.
- **Passing yards:** A/B are unchanged old HGB aliases. MAE improves 8.13% and RMSE improves, but bias worsens from -19.08148 to -20.95869 and p95 absolute error from 119.401 to 125.231 yards. The earlier fixed H3 reconstruction’s 20.16% gain on 27 rows / 13 games / 1 week remains a separate exposed result with worse bias; the missing original runner has not been recovered.
- **Receiving/combined:** Both arms worsen SITE receiving and combined MAE; no component gain is borrowed. The completed YPT adapter/study and the older component-sum study remain separate, consumed experiments.
- **Anytime TD:** Role B Brier 0.141500 versus SITE 0.145864; natural-log loss 0.447029 versus 0.462456 on 243 exact pairs, without probability clipping. Historical B barely improves old HGB and loses old CDF. Reliability bins and sparse tails remain visible; calibration is unconfirmed.

Completions never exceed attempts on 37 common Week 6 offered pairs in either arm. Combined yards is tested separately: on 100 common component triples, role B direct combined points exceed the component sum on 99, maximum absolute gap 14.945925 yards. These are point-coherence diagnostics, not a sum-candidate accuracy test or a joint distribution. Medians/point heuristics need not add. Missing components remain missing.

## Exact PPR source work

The exact website scoring definition, including special-phase credits and its conditional defensive-recovery exception, is retained. All 8 model packages and 4 primary slots stay blocked; generic PPR and absent-field zeros are not substituted. The new [dictionary findings](../source-policy-20261023/exact-ppr-schema-followup.json) and [source-generator findings](../source-policy-20261023/exact-ppr-generator-followup.json) identify all-phase event IDs, lateral recovery-TD recipients and missing inventory semantics. They do not establish exhaustive source/provider equivalence. The source probe made 12 requests / 601,427 bytes, stopped HTTP at 159.35 s, and finished receipt bookkeeping at 191.93 s, exceeding its 180 s total wall cap; the breach is retained without another acquisition attempt.

## Executed software, recovery and verification

The pre-run integrated suite passed 572 software checks in 45.10 s. The new repair/export modules passed 34 integrated fictional fixtures in 2.34 s; worker checks overlap those tests and are not added as football evidence. A separate read-only reviewer accepted the sealed design, key-preserving repair and aggregate-only exporter; numerical verification is recorded in the review receipt.

The original run consumed 136 fits and its first reporting attempt failed on int32/int64 identity-frame dtype equality. All 1,199 original files, 918 frozen bindings, partial outputs, failed completion and consumed marker remain byte-unchanged. A separately sealed zero-fit repair normalized only derived key dtypes, preserving ordered identities, exact non-key values and float bits, and reused the unchanged graders/metrics/intervals. Both reporting phases remain consumed: one failed original plus one successful repair. No forecast was regenerated.

Repair reporting used 215.44 wall / 256.67 CPU seconds, 909,099,008 peak combined RSS bytes and 273,822,976 combined private output bytes, within 600 wall / 900 CPU / two-thread / 1.5 GiB / 800 MiB limits. [Hash manifests](hash-manifest.json), [aggregate report](aggregate-report.json), [all 48 primary slots](aggregate-report.md), model/source/config hashes and full coverage remain available. Player/game/outcome/model rows and weights remain private.

## Continuing evidence boundary

No model is promoted, integrated or deployed. All 11 scored categories wait for independent later evidence and operational/consumer acceptance; exact PPR additionally waits for its label contract. Frozen rec-half-adjustment-v1 registration and Weeks 7–14, original RB protocol, historical exposure and all failed trials remain unchanged. No backfill, restarted experiment, website write, default switch, merge, workflow dispatch, extra recorder or scheduler occurs. The website owner retains production integration.

These forecasts concern individual player-game statistics and the exact rushing-or-receiving TD event. Numeric prop-threshold probabilities, push mass and selected-line performance are unavailable for this point-only family; the prior recorded-threshold study remains separate. There is no absolute-best or “Astra” certification.
