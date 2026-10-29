# Current numeric projection and top-player checkpoint

October 28, 2026, Chicago. This completes a bounded cached-forecast comparison and a postgame diagnostic; it does not complete the research programme.

## Twelve-category decision

**The table ranks the same cached 2026 regular-season Weeks 1–6 populations, covering 93 games. It is not a measured win over the contemporaneous website.** MAE means average absolute miss in the statistic’s units; smaller is better. Anytime TD uses Brier loss, not point MAE.

| Category | Lowest recorded cached output | Primary loss | Supported / planned | Named lab control loss | Error reduction vs that control | Website now |
|---|---|---:|---:|---:|---:|---|
| Passing yards | Leaf-CDF median | MAE 62.279621 | 211/515 | CDF_MEDIAN 62.279621 | +0.00% | CDF_MEDIAN |
| Passing TDs | Leaf-CDF median | MAE 0.824645 | 211/515 | CDF_MEAN 0.878612 | +6.14% | CDF_MEAN |
| Completions | Leaf-CDF median | MAE 5.118483 | 211/515 | CDF_MEAN 5.196570 | +1.50% | CDF_MEAN |
| Passing attempts | Leaf-CDF median | MAE 7.772512 | 211/515 | CDF_MEAN 7.898497 | +1.60% | CDF_MEAN |
| Interceptions | Leaf-CDF median | MAE 0.601896 | 211/515 | CDF_MEAN 0.628663 | +4.26% | CDF_MEAN |
| Rushing yards | Leaf-CDF median | MAE 18.425856 | 526/668 | CDF_MEDIAN 18.425856 | +0.00% | CDF_MEDIAN |
| Carries | Leaf-CDF median | MAE 3.661597 | 526/668 | COUNT_A_MEAN 3.797210 | +3.57% | Count A, declared mean; exact corrected-lab recipe equivalence unverified |
| Receptions | Leaf-CDF median | MAE 1.252569 | 1849/2458 | COUNT_A_MEAN 1.333367 | +6.06% | Count A, declared mean; exact corrected-lab recipe equivalence unverified |
| Receiving yards | Leaf-CDF median | MAE 16.054624 | 1849/2458 | CATBOOST_MEDIUM 16.105430 | +0.32% | CATBOOST_MEDIUM |
| Rush + receiving yards | Leaf-CDF median | MAE 19.925906 | 1849/2458 | CATBOOST_MEDIUM 20.032110 | +0.53% | CATBOOST_MEDIUM |
| Chart PPR | Leaf-CDF median | MAE 4.679406 | 1954/2117 | HGB_CHART_MEDIAN_V1 4.702027 | +0.48% | Old-site PPR fallback; different target |
| Anytime rush/receiving TD | CatBoost probability | Brier 0.136472 | 1849/2458 | TD_EQUAL_CDF_CAT 0.136583 | +0.08% | TD_EQUAL_CDF_CAT |

The full numeric shortlist favours the CDF median on MAE. Means remain separately evaluated by MSE/RMSE. Several count medians worsen MSE and underprediction; the interception median’s adverse findings remain. The ATD CatBoost lead is only about 0.08% versus the equal blend and does not by itself select a live switch. The chart CDF’s roughly 0.48% MAE lead has uncertainty including no gain and worse bias/tails.

The generic player-game queries are not an authenticated offered-prop population. Laboratory Count A corrected means are not assumed identical to the website’s restored wrapper/fallback recipe. Historical SITE/raw-provider forecasts are absent for this panel. Do not label these percentages website-relative gains.

## Top-player findings

Weekly rankings use earlier supported opportunities in the last eight game slots, separately within position; every model receives the same membership. The weekly deadline is the earlier of the full-calendar first kickoff minus six hours and known original query cutoffs. Last-eight slots preserve unknown/DNP slots. Unsupported rank history remains unranked.

- Top-10 QBs, passing yards: CatBoost MAE **68.0409**, CDF median **69.4386**, on the same **57** supported rows out of 60 planned.
- Top-20 RBs, carries: corrected Count A mean MAE **4.6631**, CDF median **4.7297**, on the same **111/120** rows.
- Top-10 WRs, receiving yards: CDF mean MAE **33.6796**, CDF median **34.5357**, CatBoost median-objective point **35.7598**, on **56/60** rows.

These exposed subgroup leaders are descriptive. No specialized model was trained, no outcome-selected membership was used, and reducing the evaluated population does not prove a model improved. Full, top10/15/20, disjoint ranks1–10/11–15/16–20/remainder and the unranked subset remain in the [full cohort report](../top-player-cached-20261028/README.md). Unranked belongs to remainder; it is not an extra disjoint group.

## Postgame volume diagnostic — not a candidate forecast

| Target | CDF median MAE | Fixed prior rate × lagged volume | Same prior rate × actual target-game volume | Supported rows |
|---|---:|---:|---:|---:|
| Passing yards | 62.2796 | 72.9763 | 55.6720 | 211 |
| Rushing yards | 18.4259 | 20.2744 | 12.1122 | 526 |

Actual attempts/carries are postgame information. The matched same-rate substitution reduces error by 23.71% for passing and 40.26% for rushing; those gains cannot be deployed. The comparison with CDF also changes the recipe, so it is not a pure volume decomposition or an attainable floor. Versus CDF, the nominal game-cluster MAE-difference intervals are passing [-13.4601,+1.5200] and rushing [-7.8736,-4.8774]. Only six weeks are present, so the registered minimum-eight-cluster week interval is unavailable.

The first diagnostic failed before labels on a historical clock check. Its original source, consumed attempt and failure capsule remain. V2 separately admits the original historical cutoff-at-kickoff left limit, matching the original feature/CDF contract. All 2,999 historical queries use that equality and have strictly earlier feature maxima. This is not originally issued pregame evidence and does not relax live issuance checks.

## What actually ran and was checked

- **Zero new predictive fits, model loads, inference or genuine new pregame forecasts in this packet.** Prior 52 common-learner fits, chart HGB/CDF fits and count-median recovery were reused, not rerun.
- One all-category cached cohort run: **15,860 target memberships**, **58,833 repeated model-point rows**, **2,999 unique player-games**, **11,457 supported target outcomes**, **93 games**, **6 weeks**. The 6,216 aggregate records and 747 pair comparisons are not independent football observations.
- Independent cohort QA reconciled **170,047 checks**, all metrics, paired intervals, membership/fallback/source identities and disjoint/nested bands. The separate diagnostic QA reconciled 850 checks. Those are verification counts, not new NFL data.
- The separately versioned MAE display engine and typed consumer passed 36 fictional software cases; the cohort transport check also used fictional values. Software checks do not establish forecasting accuracy.
- New private evidence retained **1,744,429 bytes** including the failed diagnostic; original caps/failures remain. Each immutable capsule passed exact readback and independent fresh-process hash/row verification. Offhost restoration of these new capsules is not claimed. Shared metadata remains within its separately allocated 16MiB; no paid storage or new credentials were used.

## Selection, release and capture

The new `stat_point_mae_v2` numeric display policy removes the preceding implementation-specific 2025/bias/p95 automatic vetoes. It keeps those diagnostics and all source, artifact, future inference, durable capture, consumer, fallback and retained-owner checks. Median, mean, empirical-point and arithmetic-blend meanings stay typed. Original P2/v1 and all scientific registrations remain unchanged.

The aggregate initializer executed for all eleven numeric targets and kept the probability stream separate. All new operational admissions remain false until the retained owner authenticates them. The first uncompressed policy report exceeded its 64KiB output cap; the original failure remains. A separately registered gzip-only continuation saved the same decisions in 9,103 bytes, with exact readback. This was aggregate policy evaluation, not a new fit or accuracy scoring run.

**New policy/products are not active.** The existing live release is preserved: website Main `252a7aeff73acd6eb0f36dfc4f585a1af2b27a0a`, immutable overlay `765b74e3bf8cb0f45a7e073cea489e47ef9b7b028c6428bd9578fff0454ea1ad`, **1,948 selected forecasts** plus 448 old-PPR and 68 other reference fallbacks. At the 8:54 p.m. Chicago refresh, served metadata/pointer hashes were unchanged from the complete prior readback. This refresh did not rerun the full UI/browser check.

The retained production writer must admit the new point-view/product/catalog, authenticate current restored wrapper bindings, capture before cutoff, publish through the existing workflow, and verify actual consumer values/labels/sorts/fallback/rollback. This is an authorized integration dependency, not a new general owner-approval request or an eight-week scientific wait. Do not silently substitute a median into an old mean contract. Chart PPR additionally needs current-source, private restoration and exact new-chart consumer admission.

Existing research Main cron was checked: `36 12,13,14 * * *` UTC includes the configured **October 29, 7:36–7:57 a.m. Chicago** window. The 1:15 p.m. decision, 5:45 p.m. first input cutoff and 7:15 p.m. kickoff remain. No new scheduled execution, full per-method Week8 census or exact headline game-to-capture assignment is claimed; those require the retained producer/private metadata. The latest observed scheduled Parent remains preserved failed run40745398328.

## Remaining executable queue

1. Complete retained-owner point-product admission and genuine same-cutoff website/R0/challenger capture. Preserve both views of a shared CDF as products, not invented independent learners.
2. Run a finite ordered-recent-game feature pilot against an unchanged strong learner, then a bounded past-only analog/relevance comparison. Those mechanisms are not completed by this subgroup analysis.
3. Qualify the free TabICLv2 runtime/checkpoint and true median path before its NFL pilot; no Torch/TabICL package or GPU runtime has yet been admitted. The official checkpoint is 114,324,594 bytes. Learned TabR remains a later chronological retrieval study.
4. Continue roles/teammate/opportunity, targeted NGS and chart source qualification. Source-ready football work continues independently of raw odds transport.
5. Real quote trajectories and price-aware probability/EV work still require the approved private producer route and authentic timestamped prices; static archive rows do not create quote movement. No new API requests, market probability, paper return or wagering result was produced here.

2025 football remains permitted and separately reported in the completed earlier studies. The completed no2025 market study stays frozen. This new cohort packet is 2026 W1–6 only; 2025/older cohort analysis and genuine Week7 cohort comparisons remain distinct unfinished work.

## Replay and audit files

- [Cohort aggregate results](../top-player-cached-20261028/PUBLIC_RESULTS.json.gz), [cohort independent QA](NEXT_TOP_PLAYER_INDEPENDENT_QA_V1.json).
- [Diagnostic results](NEXT_ACTUAL_VOLUME_PUBLIC_V2.json), [diagnostic independent QA](NEXT_ACTUAL_VOLUME_INDEPENDENT_QA_V1.json).
- [New display/consumer contract](../../docs/NEXT_CHECKPOINT_MEDIAN_POLICY_V2_CONSUMER.md), [current production readback](NEXT_RUNTIME_REFRESH_V1.md).
- [Existing all-method ledger](LOWEST_ALL_METHOD_LEDGER_V1.json) remains supporting historical evidence; no cross-population minimum was promoted into this table.

Restricted row-level membership, original prediction/actual/error/fallback/source records remain in the authenticated private grade capsule. They are not public raw-feed assets.

- [Executed MAE policy decisions](../next-nfl-median-policy-v2-20261028/COHORT_DECISIONS_GZIP_V2/DECISIONS.json.gz) preserve all readiness reasons and separate mean/median leaders.

- [Independent aggregate-policy QA](NEXT_POINT_AGGREGATE_GZIP_INDEPENDENT_QA_V1.json) reconciles all11 MAE and mean/MSE decisions, six readiness gates, retained live contracts and unchanged TD stream (354 software/arithmetic checks, not NFL games).
