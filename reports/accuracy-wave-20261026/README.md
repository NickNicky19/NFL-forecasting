# NFL accuracy wave — October 26, 2026

## Completed now

**One genuine NFL NGBoost fit and inference completed**, plus a new passing-workload diagnostic on retained Week 7 outcomes. Both received independent read-only post-execution acceptance. No live model replacement or deployment occurred in this wave.

The latest owner instruction reauthorizes provisional releases under the existing weekly policy. Original scientific registrations, protected outcomes and their qualification requirements remain intact. These research results do not satisfy those registrations by relabeling.

## Track B: first completed NFL NGBoost pilot

Target: **interceptions thrown, expected mean**. Primary objective: MSE. One fixed 16-stage NGBoost Poisson model, depth 2, minimum leaf 30, learning rate 0.05, seed 1761; no setting search. NGBoost 0.5.11 trains on 1,865 supported QB appearances from 2019–2021 and predicts every one of the 1,354 original 2022 opportunities before joining evaluation labels.

The matched scoring population is **633 QB appearances, 271 games, 18 weeks**. It includes 342 supported zero-interception outcomes. The 721 unknown-participation opportunities remain unknown, not zero. All supported rows have every required control; none is dropped for a missing forecast. There are 16 cold-start fallback forecasts among all offered rows, including one scored row.

|Expected-mean procedure|MAE, interceptions|RMSE, interceptions|MSE|Signed bias|95th percentile absolute error|
|---|---:|---:|---:|---:|---:|
|Role prior|0.707079|0.833012|0.693909|+0.004417|1.341555|
|Corrected Count A|0.694537|0.839903|0.705437|-0.011741|1.507224|
|Response-CDF|0.692030|0.830904|0.690401|-0.011857|1.552404|
|Leaf-CDF|**0.690292**|0.830211|0.689250|-0.011499|1.590228|
|NGBoost pilot16|0.695979|**0.829186**|**0.687549**|-0.018663|1.398114|

NGBoost reduces MSE **0.247% versus the strongest matched MSE control, Leaf-CDF**, and 2.536% versus Count A. Its MAE and underprediction worsen versus Leaf-CDF. Its tail error improves against Leaf-CDF but remains worse than the simple role prior. A tiny primary reduction is not a substantial demonstrated product improvement.

The prespecified 500-replicate whole-week bootstrap gives a candidate-minus-Leaf MSE interval **[-0.013056, +0.010208]**, crossing zero. This is an unadjusted exposed-development sensitivity analysis, not independent confirmation or a selected-winner guarantee. Chronological fitting does not erase prior exposure to 2022–2024.

The native Poisson law has log loss **1.078344 on 632 model-only rows**; the one scored fallback has a different prior law. No full-system distribution-score win, calibrated prop-probability win or current-website win is inferred from that secondary number. Historical contemporaneous website/provider forecasts are unavailable for this panel.

Features reuse the reviewed corrected source `7d2c6f5c439f81844d790a77f9338e8854784092`: availability admission before kickoff-recency selection, explicit unknown clocks excluded, training-only preprocessing, and masked unavailable participation/snap inputs. Historical source timing still uses the disclosed seven-day reconstruction. No new injury, weather, charting or private game-plan information was added.

Existing legacy feature/query/control files were authenticated by their original manifests and exact hash/stat/owner checks; the source manifest was already CAS-owned. The new model, lossless float64 forecasts, freeze and scores are strict immutable CAS artifacts. This does not retroactively establish missing old native-CAS lineage or an exhaustive census of all workspace legacy private data.

**Decision: research-tested; retain the incumbent.** This one-year pilot has no operational entry package or prospective advantage and is not selected, deployed or scientifically qualified.

## Track A: passing regression and workload diagnosis

All **180 original QB-category opportunities** remain: 36 QBs, five passing targets and 13 query games. The main four-arm comparison uses the same 16 supported QB appearances in eight exposed games; the larger diagnostic pool has 17 supported QBs and 83 supported category labels.

|Category|Current selected MAE|Saved adjusted baseline MAE|Current RMSE|Saved adjusted RMSE|Units|
|---|---:|---:|---:|---:|---|
|Passing yards|71.000|47.017|87.705|61.174|yards|
|Passing TDs|0.883|0.798|1.056|1.019|TDs|
|Completions|5.246|3.864|6.046|5.061|completions|
|Passing attempts|6.117|5.038|7.396|7.071|attempts|
|Interceptions|0.610|0.502|0.687|0.600|interceptions|

The yard comparison's 33.78% MAE reduction is retained. **The selected forecasts were issued October 24; baseline fields come from the October 25 10:15 board.** Provider publication remains unknown. These are different input vintages, so the table does not isolate an algorithm effect or earn an automatic rollback. Attempt baseline maximum error is also worse despite its lower average error.

The clock-corrected same-model replay exactly reproduces all five current passing categories, 36/36 points each. The separate earlier empty-history reconstruction failure therefore does **not** explain away this current-site regression.

New postgame diagnostics hold each arm's implied efficiency fixed and substitute realized attempts or completions. On the same 17 selected-model yard rows, MAE is **67.647 yards** with the retained forecast, **46.248** with actual attempts and **40.558** with actual completions. These use information unavailable before kickoff and are **not new forecasting methods or deployable gains**. Actual-attempt substitution worsens underprediction (-5.412 to -13.965 yards). Each diagnostic has its own exact same-row original companion; different denominators are never mixed.

This identifies opportunity/conversion error as useful research work. It does not show how much of the diagnostic reduction can be achieved before games. [Full diagnosis](PASSING_DIAGNOSIS.md) retains fixed strata, paired game/leave-one-game-out sensitivity, adverse findings and all source limitations.

## Every category: current decision and active work

These are the existing served families, not newly proven champions. All retain decisions preserve the existing P2 policy and actual deployment sequence. Current-season same-cutoff evidence remains distinct from historical laboratory comparisons.

|Category|Existing served output/family|This wave / next distinct dependency|Decision|
|---|---|---|---|
|Passing yards|Leaf-CDF median|Regression/workload diagnostic completed; matched provider timing and role/opportunity information needed|Retain; no ready replacement selected|
|Passing TDs|Leaf-CDF mean|Regression diagnostic completed; scoring-opportunity/conversion control remains distinct from tested count forests|Retain|
|Completions|Leaf-CDF mean|Regression diagnostic completed; fixed-attempt conversion and qualified catchability work queued|Retain|
|Passing attempts|Leaf-CDF mean|Regression diagnostic completed; team opportunity/QB role model needs timely participation evidence|Retain|
|Interceptions|Leaf-CDF mean|One actual NGBoost pilot completed; targeted FTN value/player/denominator qualification queued|Retain; pilot gain small and mixed|
|Rushing yards|Leaf-CDF median|Reuse completed direct/efficiency/workload losses; role and signed-gain additions need qualified inputs|Retain|
|Rushing attempts|Legacy Count A intended mean|Corrected-mean COUNT7 consumer package ready with existing integrator; dynamic workload losses preserved|Retain pending integrated correction|
|Receptions|Legacy Count A intended mean|COUNT7 correction pending; qualified target/catch-quality additions queued; rec-half unchanged|Retain pending integrated correction|
|Receiving yards|CatBoost medium median|Strong direct control retained; new depth/catch-quality information needs qualification|Retain|
|Rushing + receiving yards|CatBoost medium direct median|Pooled copula/joint losses retained; qualified shared-role dependence remains distinct|Retain|
|Exact website offensive PPR|R0 baseline|Complete exact scoring labels and rare conditional components remain blocked|No supported replacement|
|Anytime rushing/receiving TD|Equal CDF/CatBoost probability blend|Existing calibration/blend failures retained; complete played-zero/TD labels and threshold calibration needed|Retain|

Legacy Count A fallbacks must not be relabeled corrected expected means. An expected-value objective and an MAE median product remain separate. The prior historical leader report displays MAE and RMSE in original units for all ten numeric targets; it does not establish a universal acceptable error or a current-site win.

The 41-family [method inventory](https://github.com/NickNicky19/NFL-forecasting/blob/cae6121e2d4dd0fc5a6c7d2217a93cd242533de7/reports/full-week-method-audit-20261025/METHOD_INVENTORY.json) remains the base. Fixed workload, monotone threshold-CDF, anytime calibration, simple copulas and historical P1–P4 comparisons have already run, often losing. No budgets were refunded. Exact distributional forests, XGBoostLSS, hierarchical role/allocation, native categorical additions and full-law stacking remain separate pending studies. AdaBoost stays lower priority. FTN 2022/2023 raw/schema acquisition already exists; the next task is actual value/denominator/player/timing qualification, not another download.

## Probabilities and rankings

The saved Sleeper payout proxy result remains exploratory: it lacks authenticated bookmaker price semantics, matching under-side thresholds and quote clocks. This wave did not claim a market-only, calibrated-threshold or reliable Top-list winner. The earlier 3.07% payout-proxy blend improvement does not establish those claims.

Future ranking comparisons must freeze the offered pool, eligibility, tie rules, list size and abstention procedure before grading. Keep all pending selections and evaluate probability scores separately from selected hits. The planned Week 7 outcome refresh must respect genuine prekickoff versus development lanes; existing old-finality rows cannot be silently called fresh completed-game coverage.

The refresh preflight found the known full-week source bodies require **178,739 compressed bytes before receipts and grading output**, exceeding approximately **60 KiB** of remaining managed-store headroom. No new outcome download or refresh grading occurred. A one-game full-summary footprint is unknown; smaller old projections do not establish that its full wire body fits. Existing future-game outcomes therefore remain pending in this evidence stream. The separate 8 KiB FTN qualification proposal is preparation, not an executed source qualification or an accuracy result.

## Actual deployment and recurring operation

Fresh GitHub and TLS reads found website main **`453e7e6e843b0cb1ae611b0925063e0f96c70196`**, app SHA-256 **`409dcb4830cf91b08c2202232e392cae3e0ef02c2f9e72c94e27af2ff0e594ec`**, existing overlay **`3691be0265c1d4e4f1a7ee0631168337c49f66ce80abd6005a5dc4fd4ccfc267`**. Readback completed October 26 at **13:07 UTC**. That verifies the existing deployment, not a new release by this wave.

The exact reviewed 13-path [COUNT7/strict-props Main package](https://github.com/NickNicky19/NFL-forecasting/blob/23e471d/reports/main-count7-strict-props-release-20261026/README.md) is available to the established integrator. It replaces older Main packets and must not be stacked onto the separate Phase 2 alternative. Genuine COUNT7 retains its original expiration **October 27, 00:15 UTC**; no extension or backdating. These are correctness/operation repairs, not measured forecasting gains.

The actual active production lease is **`NFL-WEB-PRODUCTION-REPORT-INTEGRATION-20261025-122500Z`**, coordination revision **168**, source **`484dbeff5c3fb34673380bf52b0f30ee0354a521`**. This research run does not own that lease. The existing writer must reconcile the prepared Main paths with its authorized scope before implementation. No competing writer, lease takeover, new scheduler or fake deployment was created. Hosted CI, integrated build identity and actual selected-feed consumption remain pending for that package.

Research main refreshed to **`3d0c11871fc53923ba4656dd423bc9ca0b8ef5e1`**. The existing cron is 12:36/13:36/14:36 UTC; guarded runtime/registration/private-storage handover remains incomplete. A configured cron does not prove successful capture, grading, training or selection. Last registered weekly deadline is **October 29, 18:15 UTC**, subject to actual schedule refresh and runtime qualification. Next capture/grading/selection evidence belongs to the existing controller records and canonical execution ledger; a future execution is pending until observed.

## Retained failures and verification

Passing diagnostics had two prewrite 16 KiB allocation failures. A final lossless foreign-key encoding retained all original opportunities and derived quantities in **14,913 bytes across both attempt directories**. Deterministic arithmetic was recomputed; it added no independent football observations. Cumulative native runtime **40.213 CPU / 38.276 wall seconds**, within the original 45/90 budget.

NGBoost first rejected an unregistered preexisting psutil native dependency before data decoding/fitting. A separately sealed continuation pinned all 28 exact package files and retained strict native checks. The original 5,836-entry runtime receipt and failed trial remain intact. The successful fit used **34.722 CPU / 34.392 wall seconds**; including the prior failure, **39.064 CPU / 37.866 wall seconds**, within the original 120/180 budget. New artifacts total **26,093 bytes**, within 64 KiB. The shared managed-store 512 MiB cap was unchanged and no evidence was deleted.

The read-only reviewer reconstructed all A rows and panels and all B forecasts, controls, fallbacks, training preprocessing and 500 bootstrap replicates; it verified immutable CAS bindings plus 5,879 dependency/source references and 287 vendored files. Review adds no NFL observations. Agent capacity failures were recorded; replacements used the explicitly requested GPT-6.1 Sol/xhigh setting, while actual backend attestation remains **UNATTESTED**.

Records: [NGBoost aggregates and hashes](NGBOOST_AGGREGATES.json), [passing aggregates](PASSING_AGGREGATES.json), [full passing report](PASSING_DIAGNOSIS.md), [prior historical leaders](https://github.com/NickNicky19/NFL-forecasting/blob/6d5d75517ef6f5a92dc32500702f704ee0b13d28/reports/session-scorecard-20261025/HISTORICAL_LEADERS.md). Restricted row-level forecasts, exact outcomes, model bytes and private fixtures remain private.
