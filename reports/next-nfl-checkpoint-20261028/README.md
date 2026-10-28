# NFL category checkpoint — October 28, 2026

## Current decisions first

**No new research replacement was selected or deployed by this checkpoint.** The actual Week 8 website still serves its Classic reference fallback. Fresh live reads at **19:10 UTC** show `DISABLED_USE_R0`, **zero selected rows** and2,468 baseline fallbacks. Website Main advanced legitimately to`dbf4a05de77e3abcd497125fa0cb0479ac4c327a` through a64-data-path scheduled update. A newer1,951-row, eleven-category producer/consumer preview succeeded; it remains undeployed. Preserve the older1,960-row preview and17:44 live snapshot as history. [Latest production readback](RESUME_PRODUCTION_READBACK.md) supersedes their current-status claims.

The table below identifies the lowest observed compatible **football** procedures in the inspected 2026 Weeks 1–6 panel. These are exposed current-vintage reconstructions, under the original seven-day availability assumption, across 93 supported REG games. They are not wins against today's website; historical contemporaneous SITE/raw-provider/R0 records are unavailable. Counts use the expected-value objective; yards use the median/MAE objective. A displayed MAE is the average distance from the actual statistic, not a pick win percentage. MSE uses squared units: passing-attempt MSE104.06 corresponds to RMSE10.20 attempts, not an average104-attempt miss. The exact RMSE values remain in the product record.

| Category | Observed 2026 football procedure | MAE in category units | Primary loss | Supported / planned | Latest verified feed preview choice | Actual live selected / baseline rows |
|---|---|---:|---:|---:|---|---:|
| Passing yards | Leaf-CDF median | 62.280 yd | MAE 62.279621 | 211 / 515 | CDF, 40 rows | 0 / 40 |
| Passing TDs | Response-CDF mean | 0.877 TD | MSE 1.157146 | 211 / 515 | CDF, 40 | 0 / 40 |
| Completions | Leaf-CDF mean | 5.197 completions | MSE 44.178448 | 211 / 515 | CDF, 40 | 0 / 40 |
| Passing attempts | Response-CDF mean | 7.893 attempts | MSE 104.055610 | 211 / 515 | CDF, 40 | 0 / 40 |
| Interceptions | Leaf-CDF mean | 0.629 INT | MSE 0.526397 | 211 / 515 | CDF, 40 | 0 / 40 |
| Rushing yards | Leaf-CDF median | 18.426 yd | MAE 18.425856 | 526 / 668 | CDF, 112 | 0 / 154 |
| Rushing attempts | Count A, stored-mean fallback v2 | 3.797 carries | MSE 24.216499 | 526 / 668 | Count A mean v2, 112 | 0 / 114 |
| Receptions | Count A, stored-mean fallback v2 | 1.333 catches | MSE 3.331184 | 1,849 / 2,458 | Count A mean v2, 403 | 0 / 409 |
| Receiving yards | Leaf-CDF median | 16.055 yd | MAE 16.054624 | 1,849 / 2,458 | CatBoost medium, 403 | 0 / 409 |
| Rushing + receiving yards | Leaf-CDF median, direct total | 19.926 yd | MAE 19.925906 | 1,849 / 2,458 | CatBoost medium, 291 | 0 / 295 |
| PPR | Old exact-site target unsupported; new chart labels now partly qualified | No forecast score | No accuracy comparison | Chart: 13,235 / 14,160 source-listed rows across three seasons | Reference fallback; no chart forecast | 0 / 449 |
| Anytime rushing/receiving TD | CatBoost binary probability | Use probability scores | Brier 0.136471970 | 1,849 / 2,458 | Equal CDF/CatBoost probability blend, 430 | 0 / 438 |

The preview and live boards have different creation times and coverage. Their row counts are not paired accuracy samples. All actual live rows in the last column are current Classic fallback, including PPR; none is a chart-PPR migration.

Legacy Count A mixes warm mean-objective points with median fallbacks. Its stored-mean correction lost all four earlier reported MSE comparisons against that older numerical recipe; it is a correctness repair, not an accuracy upgrade. The legacy points and older slightly lower-loss P4 point blends remain explicit benchmarks. Averaging points does not make a mixture median, and neither point recipe supplies a calibrated probability law.

[Complete product-specific decisions](PUBLIC_CATEGORY_DECISIONS.json) preserve the separate mean, median, distribution, probability and selection cells, exact controls, bias/tails, uncertainty, fallbacks and next dependencies. [Latest live board/pointer counts](RESUME_PRODUCTION_READBACK.json) authenticate the served counts above; the earlier [board](LIVE_BOARD_READ_V2.json) and [pointer](LIVE_POINTER_CURRENT_V3.json) remain separate snapshots. The current reference is not automatically identical to the earlier Week 6 SITE comparator or original R0 shadow.

### What the policy currently selects

The existing `weekly-adaptive-release-v1` producer uses **P2: cumulative comparable earlier current-season, current-epoch genuine pregame losses**, retaining registered startup choices until usable common evidence exists. Its margin is zero; ties retain the current choice, then R0, then stable method ID. No eight-week scientific prerequisite was added. The registered startup is CDF for passing/rushing yards, Count A for carry/reception means, CatBoost for receiving/combined points, and the equal anytime probability blend.

New reconstructed leaders do not silently rewrite that issued epoch or its choice. A new initial evidence/selection contract would be separately versioned. The older registrations and every losing week remain intact. The table distinguishes observed laboratory leaders from that registered choice and from actual website use. Member-only later ATD P2 capability and its equal-blend startup limitation remain disclosed in the machine-readable record. Top Over/Under and biggest-gap ordering still use the declared scaled point-gap procedure; this integration does not install a probability or price/EV ranking.

## Work actually executed

| Packet | New fits / model loads | Forecasts or rows | Measured execution | Result |
|---|---:|---|---|---|
| Objective-matched yardage correction | 24 small LAD fits / 0 base CDF fits or loads | 20,212 book-level forecast rows frozen; 6,871 matched player-game-target rows | 40.888 CPU / 40.397 wall s; 374,013,952-byte RSS | All 24 optimization certificates passed; 13 of 16 new-vs-original correction contrasts improve, 3 lose |
| Contemporary football/market comparison | 0 fits / 0 model loads or law queries | 1,780 ordinary + 1,025 ATD planned; 1,708 + 829 scored | 32.933 CPU / 32.803 wall s; 262,017,024-byte RSS | All eleven supported categories compared; original common cohort and fallbacks preserved |
| Frozen yardage tail/side supplement | 0 | Same 6,871 rows; 56 aggregate arm/cell records | 0.077 CPU / 0.076 wall s | p90/p95/max misses, pushes/ties, strict/inclusive close and close-and-correct rates completed |
| Frozen paper-selection sensitivity | 0 | Same 3,800 already-selected stakes; 102 unresolved | 0.474 CPU / 0.474 wall s; 128,524,288-byte RSS | 90 category and 10 season records; no new picks, probabilities or settlements |
| Chart-PPR label reconstruction, technical V2 | 0 predictive fits / forecasts / accuracy comparisons | 14,160 planned source-listed rows; 13,235 complete supported labels | 37.612 CPU / 37.594 wall s; 398,225,408-byte RSS including persistence | Full private capsule exact readback and independent arithmetic acceptance passed |

These are different counters. Book rows, model outputs, simulations, fixtures and repeated scoring do not add independent NFL games. No new football outcomes were created. The 24 new fits are restrained corrections, not 24 newly trained football CDF models. All comparison periods are already exposed development evidence.

The relevant independent numerical checks passed: LAD certificates/prediction arithmetic and paired metrics; contemporary cached transforms, 111 metric records and all 58 prespecified contrasts; paper aggregate identities/bounds; and all 13,235 chart scores. The first contemporary checker stopped before NFL decode because the system interpreter lacked PyArrow; its failure remains, and the separately authorized technical V2 used the installed scientific environment. Twenty fictional chart cases remain software checks, separate from these NFL results.

## Did market information improve forecasts?

### New contemporary comparison, same original 2026 Weeks 1–5 offered cohort

This fills the old comparison's stale-football-control limitation without refitting. It admits compatible retained 2026 CDF/recent-leader predictions, using their qualified already-fitted football lineage through 2025. Offering-book exclusion, original book priority, original player-game cohort and original 2023-only correction parameters remain fixed. Both the old L2 and new LAD transformations are separately identified empirical points; they do not become authenticated CDF means, mixture medians or distributions by being scored.

| Yardage category | Rows / games / weeks | Current CDF MAE | Independent market-line point MAE | Current-input LAD hybrid MAE | Gain vs current CDF | Gain vs market-line point |
|---|---:|---:|---:|---:|---:|---:|
| Passing yards | 81 / 46 / 5 | 54.333333 | 53.913580 | 53.256937 | +1.98% | +1.22% |
| Rushing yards | 153 / 48 / 5 | 23.431373 | 21.777778 | 21.759061 | +7.14% | +0.09% |
| Receiving yards | 482 / 48 / 5 | 22.286307 | 21.250519 | 21.192862 | +4.91% | +0.27% |
| Combined yards | 119 / 47 / 5 | 30.621849 | 28.193277 | 28.151011 | +8.07% | +0.15% |

**Every LAD-hybrid versus market-line game interval crosses zero.** For passing yards the paired MAE difference is -0.656643 yards, nominal game 95% interval [-3.156822, +1.830891]. The other three intervals are [-0.158825, +0.111805], [-0.233258, +0.115607] and [-0.178147, +0.108279] yards. Five-week inference is correctly unavailable under the registered minimum-eight-cluster uncertainty rule. This is an uncertainty rule, not a new release waiting period. Intervals are nominal exposed-sample diagnostics and are not simultaneous confirmation of the selected best arm.

For count objectives, transported L2 hybrid MSE is 1.316566 for TDs, 28.422868 for completions, 64.370931 for attempts, 0.463948 for interceptions, 27.495039 for carries and 4.254973 for receptions (each in squared category units) on their respective fixed cohorts. The market-line heuristic has lower completion MSE (27.800633), and the CDF control has lower interception MSE (0.463710). Reception hybrid versus market MSE difference is -0.103487, interval [-0.229790, +0.019764]; its stronger lead against CDF does not establish superiority to the market control.

The frozen correction's football coefficients are effectively zero for several targets/books. Replacing an older football input with a newer one can therefore leave the hybrid unchanged. This is **transport of a frozen correction**, not evidence that a newly fitted contemporary hybrid learned useful football context. Historical collection clocks remain unverified quote clocks. A single line remains a heuristic point, not an identified mean or complete law.

[Every category, week, bias, tail, precision rate and prespecified contrast](contemporary/INDEX.json) is retained. Supported ordinary rows are 1,708 of 1,780: 35 unknown reception rows, 35 unknown receiving-yard rows, one unknown rushing-yard row and one unknown combined row remain unscored. ATD has 829 supported of 1,025, with 194 unknown and two played-invalid outcomes. All 2,805 cached modern rows were admitted; this study had zero admission-age fallbacks, and the original model's one ATD cold-start prior remains explicit.

### New LAD objective versus the original L2 recipe

The 24-fit recipe holds the original data, 2023 calibration training, scaling, nonnegative slope constraints, offering-book exclusion, fixed original fallback and original cohort unchanged. Training-only yard scale is `max(1 yard, 1.4826*MAD(y))`; the fixed scaled objective is `sum(abs(residual))/scale + 10*sum((beta/scale)^2)`, with an unpenalized signed intercept. ADMM has fixed rho=1, at most20,000 iterations and a declared primal/dual certificate tolerance; there was no hyperparameter search.

On the original 2026 football inputs, hybrid MAE falls from 53.418231 to53.256937 passing, 22.327483 to21.759061 rushing, 21.734463 to21.265444 receiving and28.701447 to28.130534 combined. The 2024 passing hybrid worsens from58.346254 to58.595276; the 2024 football-only corrected passing and combined points also lose. All24 fits certify, but only38,944 of40,424 two-arm offered-row incidences have finite inputs for a new correction; missing-input original-L2 preservation/fallback cases remain. Optimization success is not coverage or forecasting success.

[Full LAD results](LAD_SAFE_AGGREGATE.json) and [large-miss/side diagnostics](LAD_TAIL_SIDE_DIAGNOSTICS.json) retain all gains and losses. Independent acceptance checked stored scalar certificates and arithmetic; dual vectors were not retained, so no independent dual-vector reconstruction is claimed. No new optimization was run by the reviewer.

## Did probabilities or paper selections improve?

The new contemporary packet has genuine **ATD event probabilities**, not arbitrary-line numeric prop probabilities: CatBoost Brier0.154359986, current CDF0.155426404 and equal blend0.154730080 on the same829 outcomes. CatBoost log loss is0.476583775 versusCDF0.478574179. The paired differences remain uncertain; these offered rows differ from the broader1,849-row annual panel. No fair ATD market probability is inferred from a one-sided Yes quote.

Cached numeric point summaries do not supply arbitrary-line probabilities. This packet consequently makes **no new numeric over/under-probability win**. The original football/calibrated/shrunk/market/hybrid probability experiment remains separately available; its controls, calibration losses and adverse results were not renamed or rerun. Current same-cutoff market capture remains a separate production dependency.

The zero-fit sensitivity retains unknown settlements instead of declaring the known subset final. The following bounds use the original frozen side and payout for every unresolved one-unit stake. They are broad deterministic bounds, not confidence intervals; endpoints across overlapping offers/policies need not be jointly attainable.

| Season / frozen policy | Known net units | Unresolved stakes | Outer final-unit range |
|---|---:|---:|---:|
| 2024 football EV | -45.646 | 21 | [-66.646, -24.922] |
| 2024 independent market EV | -32.074 | 5 | [-37.074, -27.201] |
| 2024 hybrid EV | -71.368 | 23 | [-94.368, -46.036] |
| 2024 probability first | -32.062 | 24 | [-56.062, -11.191] |
| 2024 projection-gap proxy | -44.452 | 11 | [-55.452, -35.062] |
| 2026 football EV | -4.273 | 2 | [-6.273, -2.238] |
| 2026 independent market EV | +6.284 | 3 | [+3.284, +10.508] |
| 2026 hybrid EV | +1.980 | 4 | [-2.020, +6.587] |
| 2026 probability first | +3.216 | 5 | [-1.784, +7.258] |
| 2026 projection-gap proxy | -8.172 | 4 | [-12.172, -5.023] |

All five2024 policies remain negative even at their most favorable unresolved endpoint. The2026 hybrid/probability-first sign can change. The2026 market policy's known positive result is concentrated by category and selected pool; it is not broad evidence of profitability. Quote-time, jurisdiction and actual settlement qualification remain incomplete. These are exploratory paper records, not wagers, the actual website's historical ranking or an authenticated execution record. [Category contributions, full ROI denominators and bounds](PAPER_SENSITIVITY_PUBLIC.json) preserve all90 nonempty category-policy cells; zero-selection cells remain in the original report.

**Plain answers:** odds improved some recorded point errors; a durable improvement over the current website is unproved. Probability gains are mixed and the new modern numeric probability comparison remains unrun. Price-based paper rules have positive and negative results, including all five losing2024 policies; reliable live or authentic historical profitability has not been established. MAE, probability loss, ranking hit rate and paper ROI are different products.

## New chart PPR: actual implementation and label result

`nick-chart-ppr-v1` is a new sixteen-primitive linear target. Its exact formula is:

`0.04*pass_yd +4*pass_td -pass_int +0.1*rush_yd +6*rush_td +rec +0.1*rec_yd +6*rec_td -fum_lost +2*(pass_2pt+rush_2pt+rec_2pt) +6*off_fum_rec_td +6*(kick_return_td+punt_return_td+fg_return_td)`.

It uses unique credited all-phase lost fumbles, separate conversion credit and signed official yards. It adds no ordinary recovery, forced-fumble or blocked-kick bonus and imports no old recovery truthiness exception. The image file named in the addition was not separately available; this implements the complete supplied text transcription, without claiming to have inspected the image.

| Season / REG scope | Planned source-listed rows | Complete numeric labels | Unknown participation | Played missing components | Rare-positive planned / numeric |
|---|---:|---:|---:|---:|---:|
| 2024 Weeks1–18 | 5,935 | 5,589 | 345 | 1 | 16 / 12 |
| 2025 Weeks1–18 | 6,108 | 5,693 | 394 | 21 | 21 / 0 |
| 2026 Weeks1–6 | 2,117 | 1,953 | 163 | 1 | 1 / 0 |
| Total | 14,160 | 13,235 | 902 | 23 | 38 / 12 |

Supported played-zero scores are634,716 and268 respectively. The 900 unknown-participation rows with otherwise complete components remain null. A complete weekly nonnegative broader category's zero can support a subset zero under its reviewed source contract; a positive broader category requires event classification. The2024 PBP inventory permits12 rare-positive numeric rows, while remaining ambiguous special/recovery classes and2025/2026 positive classes stay unsupported. No event-free-only predictive sample was selected.

The raw2026 median-boosting file mismatches its old receipt, so it was quarantined before decoding. A separately authenticated operational2026 snapshot was used. This neither invalidates all2026 football nor repairs older fitted inputs retroactively. The initial label run failed before NFL decode on three symbolic source aliases; its failure capsule and consumed budget remain. The independent-reviewed technicalV2 pins the same bytes at canonical paths and preserves both histories.

[Exact scorer](../../nfl_lab/next_checkpoint_chart_ppr.py), [contract](../../config/next-checkpoint-chart-ppr-v1.json), [adapter](../../tools/next_checkpoint_chart_ppr_labels.py), [coverage](CHART_PPR_LABEL_COVERAGE.json), [software fixtures](CHART_PPR_FICTIONAL_VALIDATION.json) and [independent acceptance](verification/chart_labels_readonly_acceptance_v1.stdout.json) are reviewable. The private capsule hash is `5ef732638c2d468bfe2b2f212cb85b1a1e02fb45ed0f51b2d511c71308467c82` (838,547 bytes), with inherited-CAS exact readback. No original raw dataset or row-level labels are published here.

**Partial chart labels are now available; this is no longer an all-labels-impossible claim.** No chart forecast comparison, trained model or public consumer migration has occurred. The full predictive evaluation population is not admitted by this label packet; rare/unknown rows and offered/statless-player coverage need an explicit next contract. For an expected score the linear component expectations add; quantiles/probabilities require a supported joint law or direct distribution. Component medians and anytime-TD probabilities cannot substitute for missing score ingredients. The older pinned-site scoring target, results and label block remain unchanged.

## What remains new in roles/NGS/opportunity research

[Mechanism matrix](INFORMATION_MECHANISM_MATRIX.md) and [all sixty suggestion mappings](INFORMATION_MECHANISM_MATRIX.json) reconcile private ledgers and recent completions. The2026 same-learner history/depth study is complete (17fits): all history alternatives and the depth addition lose primary MSE. Its2025 slice remains queued. Fixed workload smoothing is numerically complete and adverse: carryMSE25.318253 versusCDF24.292747; receptionMSE3.342880 versus3.268201; receiving-yardMAE16.922633 versus16.372435. Failures/resource limitations remain; there is no replenished budget.

Broad28-feature NGS (three small gains/eight losses), FTN risk (adverse), NGBoost's small interception pilot, the adverse hierarchical interception candidate, threshold-CDF, copula, calibration and fixed blends are completed work. They are not marked untested. PFR-derived snaps remain excluded; primary-receiver route fields are not all-player routes; FTN postseason participation is not an authenticated live route feed. NGS2025 Completion Probability needs a definition bridge.

The next three controlled information groups remain carries/teammates/exposure; receptions/receiving catch quality; and QB/team volume/throw quality. Complete recent-season information for these groups is not yet source-qualified. A narrowly changed older cached NGS exposure-weighted diagnostic is possible only after a new denominator/column admission and finite registration; it would not finish the2025/2026 study. F8 needs authenticated multi-line offers; F9 needs compatible joint/team outputs; F10 needs earlier chronological out-of-fold laws. AdaBoost remains a lower-priority point control; distributional forests, XGBoostLSS and conditional stacking retain their real prerequisites. No60-candidate cross-product was opened.

## 2025 scope and original archive inventory

The latest complete addition explicitly permits qualified **2025 football** in new comparisons. The finished no2025 historical-market wave remains unchanged, including its excluded model lineage. The new modern-cached transport uses a separately identified qualified football lineage through2025; it does not admit2025 quotes or rewrite the old experiment. Four ZIPs are actually supplied/authenticated:2022(2,456,642B),2023(4,435,820B),2024(7,144,476B),2026(3,612,135B). No2025 ZIP is present. [Original source qualification](../historical-market-no2025-v1/source-qualification.json), [capture](../historical-market-no2025-v1/archive-capture-v2.json) and [fresh-process receipt](../historical-market-no2025-v1/archive-fresh-readback-v2.json) preserve all hashes,39members and17,649,073 compressed bytes. The2026 market file stops at source Weeks1–5, not Weeks6–7.

## Production handoff, real runtime and remaining owner actions

At the earlier source refresh, website main was`e336bf7a68c32267c3c3eec48892aeadcd03a90e`. Current main is now`dbf4a05de77e3abcd497125fa0cb0479ac4c327a`, a scheduled data-only update; preserve its64 changed data paths. The exact-head CI below predates this new Main and does not verify its combined source. PR9 is open at`f9f3056e23d1f62c1fc85828adc5a666cd52ea35`; exact-head CI40576824120 passes. PR10 is open at`e12de4763d048f6dec8e2d6cc0f89f43e18f2736`, stacked onPR9; CI40648049705 passes. Existing reports record200/223Python checks plusfourNode suites respectively; those were not rerun or counted as new NFL accuracy evidence here.

Producer`0409a253d6a365c31a2d421941b8ee5f40d6fd02`, actual successful run40644670107, froze1,960 forecasts at2026-10-28T06:57:46Z. Exact feedSHA`73edf46ba1081f5ae4e19f04e70f9839ab5816dd8cd3e65f80121a025667d9a8` restored and exported; the anonymous four-second consumer preview accepted all rows on a fresh paired board. Six means/four medians/one probability preserve their contracts. This is not this checkpoint's new market hybrids or chart-PPR model.

The manual production lease remains owned by`NFL-WEB-PRODUCTION-REPORT-INTEGRATION-20261025-122500Z`, revision178. Its ordinary authorization records merge/deploy/main-write false. PR10 additionally needs the existing owner scope to cover exactly`.github/workflows/hourly.yml`, `config/weekly-derived-selected-policy-v4.json`, `tools/weekly_public_feed_v4.py`, `tests/test_weekly_public_feed_v4.py`. Root has not taken that lease, used its run ID, merged through a connector, dispatched a workflow or installed another writer/scheduler. The PR Completion workflow also requires exact-head landing confirmation and its normal landing helper; broad continuation is not fabricated as that record.

**Exact remaining integration action:** the existing owner resumes its retained writer, reconciles PR9 with legitimate current Main and completes the required exact-resulting-head checks/landing record, integratesPR9, then retargets/reconcilesPR10 against the resulting currentmain, verifies combined source and a fresh pairedbuild, and completes its exact-new-head landing/deployment record. Preserve all newer work. Inspect the actual served payload and all eleven category traces after release. No new general research approval or eight-week scientific delay is needed.

**Parent activation has since been resolved by the existing owner.** Guarded Parent40729788942 and its automatic child40729906573 succeeded, including produce, independent restore and export. The newer feed`3907ca38138ed633556d894b90a347e8f6db68b9f3275a0c5621fbd952e23452` issued17:14:38Z/published17:15:18Z has1,951 selected public rows,11 categories and0 new fits. The same e12 consumer preview accepted all1,951 chosen nonreference rows in3.352559seconds/six requests. This is genuine pregame capture and a successful automatic child, still an undeployed website preview. Original successful1,960-row capture and pre-activation failure40718723483 remain preserved. No repeat flag-activation request is needed.

A later actual scheduled Parent40745398328 triggered18:28:09Z outside its qualified window. Cadence returned`due=false`, `MISSED_SCHEDULE_WINDOW_NOT_BACKFILLED`, enqueue skipped, and the retained original-handover step exited78 with`QUALIFIED_HOSTED_HANDOVER_NOT_ACCEPTED`, `PRIVATE_DURABILITY_NOT_VERIFIED` and`EXACT_PUBLICATION_REVIEW_ABSENT`. Its receipt records0 acquisition/capture/publication. Preserve this failure and diagnose it through the existing owner; do not delete safety checks or backfill a missed pregame run. Next configured Parent window is October29 **12:36–12:57UTC** (end exclusive,07:36–07:57Chicago); the website's existing08:06 daily build is separate. A configured or triggered schedule does not establish a qualified scheduled capture. [Full latest runtime evidence](RESUME_PRODUCTION_READBACK.json).

The live14-game board confirms earliest kickoff2026-10-30T00:15Z. The registered next weekly decision deadline is**2026-10-29T18:15Z** and first-game input cutoff22:45Z (the existing5,400-second horizon). Choice persistence belongs at`<sealed output_root>/WEEKLY_CHOICE.json` and`WEEKLY_CHOICE_COMPLETION.json`; the next absolute output_root and successful automatic execution are not established. [Actual schedule readback](LIVE_SCHEDULE_READBACK_V1.json) is distinct from configured cached policy. The owner must retain actual run, persistence, grading and displayed-value receipts when execution occurs.

**Odds API:** zero API calls, credits, key reads or new raw acquisition occurred here. Existing authorization remains; root's missing binding does not prove the website secret is absent. Private transport/restore and quota remain owner-runtime dependencies. Preserve the previous176-credit batch's unknown consumption status. Use the existing secret-bearing producer, verify the approved private route before raw acquisition, then run the already bounded account/events check and separately account actual prop requests while reserving upcoming-game capacity. Public-repository Actions artifacts are not private storage. No key extraction, new scheduler, spending, wagers or stale archive-as-live-feed was introduced.

## Storage, reproducibility and claim boundaries

The separately versioned successor reserves **16MiB for new task metadata**, counting these worktrees, code, plans, reports, failures and the complete addition. It retains all old512+512+256MiB allocations, the original4MiB metadata reserve and failed writes. New combined ceiling is1,358,954,496bytes (1,296MiB); this is one shared16MiB reservation, not five renewed allowances. V1–V5 allocation descriptors preserve prior versions. New private results use the unchanged inherited CAS/shared lock inside the original256MiB lane, with complete retention/peak gates. The final inventory receipt records actual post-work usage; the older no-write admission is preserved separately.

[Executed final inventory](FINAL_CAPACITY_PUBLIC.json) passes with old controls unchanged and no managed writes: combined accounted706,432,803bytes of1,358,954,496; market-lane accounted79,356,251 of268,435,456; new metadata actual5,035,430 of16,777,216. Original metadata actual4,179,949 remains inside4,194,304; the near-full old512MiB lane was not used for new writes. The complete wave sized LAD9MiB retained/16MiB peak, contemporary6/12MiB and chart3/6MiB including its original failure, plus the shared16MiB metadata reservation. These are finite envelopes inside unchanged old data caps, not refunded allowances. Actual new private physical growth was2,801,636bytes. The final inventory itself used13.347CPU/12.977wall seconds and145,465,344-byte RSS; available local disk was13,343,604,736bytes. No paid-storage need was established. An8MiB future private-capture route fits local capacity but still needs the existing producer's actual authorized transport/restoration binding; this report does not invent that remote destination or record it as executed.

Four successful private comparison capsules retain forecasts, parameters and row-level scores; both chart attempts and all failure receipts are retained. Forecast capsules were read back before scoring. Independent readers started separate processes. **Restoration on another host remains unproven.** No unique evidence was deleted, moved outside accounting or published as raw football/price data. [Scientific environment](SCIENTIFIC_ENVIRONMENT.json) records installed versions; historical source availability remains an assumption where declared. Actual agent backend attestation is unavailable; requested settings were SolExtraHigh, with at mostfour concurrent agents including the integrator.

The public report supplies implementation/configuration hashes and safe aggregate results. Replaying the numerical studies also requires the approved private input/model packets; public aggregate hash agreement does not independently authenticate source truth or historical availability. [Implementation identities](IMPLEMENTATION_COPY_RECEIPT.json) link exact frozen code copies. Original experimental registrations, evaluation protocol, forecasts, exposed periods, spent budgets and losing weeks remain unchanged.

A lower observed loss advances a research hypothesis. Operational readiness, weekly selection, provisional deployment, independent live consumption and scientific qualification are recorded separately. This checkpoint completes these finite research/label/diagnostic packets; it does not claim that every category is finished or that any method is an absolute NFL optimum.

## Capacity-interruption recovery

The selected-model capacity interruption did not erase the saved scientific work. A separately bounded byte-only check authenticated all six research/failure capsules, all22 source-copy pairs, the complete36,397-byte addition and the reviewed publication bundle. No NFL tables were decoded and no fits, forecasts or scores rerun. [Integrity receipt](RESUME_INTEGRITY_CHECK.json). The ephemeral upload cursor was reconstructed from the last confirmed Git tree; later tree creation is journaled durably before continuing. Unknown interrupted orphan-tree operations remain unknown; no commit/ref update or deployment was invented.
