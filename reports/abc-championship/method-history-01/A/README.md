# A recoverable scientific method history — permitted public report V2

**PARTIAL within the sources listed below.** C remains the shared coordinator. This is a reporting view of existing registries and results; no new forecasting skill, fit, grading, capture or deployment is claimed.

The matching [machine-readable JSON export](PUBLIC_METHOD_HISTORY_INDEX_V1.json) indexes all 4,832 retained legacy evaluation rows, all 1,541 target/method/product combinations, 731 exact-product qualification views and 69 proper-score views. Full score/coverage and weekly tables are reused through immutable original files with exact source indices and content commitments. These are reporting levels, not counts of independent methods. Original identities, aliases, dates and source-record indices remain recoverable.

## Fifty retained mechanism entries

These source-defined families retain their own status and formula. They are not merged solely because a learner/library name matches. Canonical-method definitions and aliases are available through the JSON source index and its linked original registries. Fifteen legacy alias-to-family links are explicit; 219 remain unresolved rather than being assigned by guesswork.

| Original family ID | Readable name | Source status | Relationship / formula | Retained reference |
|---|---|---|---|---|
| raw_sleeper | Retained original provider points | BASELINE_WHERE_ARCHIVED | Recorded values only; no regenerated historical provider forecasts. | reports/methods-resumption-20261022/website-comparison.md |
| original_site | Pinned website adjustment | BASELINE_WHERE_ARCHIVED | Original point multiplied by round(clip(1+(r-1)*n/(n+8),.75,1.25),3), with original category eligibility/rounding/fallback. | config/website-baseline-v1.json |
| recent3 | Recent supported production | SCORED_MULTIPLE_PANELS | (n*recent_mean3+3*earlier_role_prior)/(n+3), with qualified-window and fixed fallback rules. | nfl_lab/models.py |
| pooled8 | Pooled/shrunk production | SCORED_MULTIPLE_PANELS | (n*recent_mean8+5*earlier_role_prior)/(n+5), with explicit missing-window fallback. | nfl_lab/models.py |
| initial_workload | Opportunity times efficiency | SCORED_LEGACY_SOURCE | Separate fixed component-recent opportunity and pooled/shrunk efficiency; exact target recipes and fallback in models.py. | nfl_lab/models.py |
| ridge_logistic | Regularized direct point/event models | SCORED_LEGACY_SOURCE | Ridge alpha32; logistic for Bernoulli; earlier-only imputation, standardization and position/category design. | nfl_lab/models.py |
| initial_tree | Fixed ExtraTrees direct model | SCORED_LEGACY_SOURCE | 24trees/depth6/minleaf30/maxfeatures.8/seed1701; earlier-only feature/label fits, not an unlimited search. | nfl_lab/models.py |
| initial_distributional | Parametric count/signed/event laws | SCORED_LEGACY_SOURCE | Negative-binomial/Poisson counts, normal signed totals and Bernoulli with fixed earlier residual/prior spread; distinct from later empirical CDF. | nfl_lab/models.py |
| initial_ensemble | Original fixed point ensemble | SCORED_LEGACY_SOURCE | 0.5*ridge +0.25*workload +0.25*recent; numeric point averaging is not a full-law mixture. | nfl_lab/models.py |
| feature_removals | Ridge without opponent/workload/team | SCORED_LEGACY_SOURCE | Same earlier-only learner with one predeclared feature group removed; no group selected retrospectively. | nfl_lab/models.py |
| ngs_ablation | 28-feature public NGS addition | SCORED_LEGACY_SOURCE | Hold fixed ridge/logistic; add prior NGS context only. Three small primary gains, eight losses in exposed2023. | reports/ngs-context-study/summary.json |
| scheme_pace_ablation | 47-feature PBP/schedule addition | SCORED_LEGACY_SOURCE | Hold learner fixed; prior team/opponent style, tempo proxy, rest, lagged coach/venue. All11 primary losses worsen. | reports/public-scheme-study/README.md |
| h3_site_pass_yd | SITE-held three-appearance pooled YPA | EXPOSED_W6_RECONSTRUCTION_ORIGINAL_MISSING | Original SITE attempt point * sum(H3 pass_yd)/sum(H3 pass_att); exactly3 qualified appearances; unchanged SITE-yard fallback. | reports/methods-resumption-20261022/category-status.json |
| h3_site_pass_cmp | SITE-held pooled completion conversion | EXPOSED_W6_MIXED | Original SITE attempt point * sum(H3 completions)/sum(H3 attempts), original selected H3 and unchanged completion fallback. | reports/methods-resumption-20261022/category-status.json |
| original_attempt_glm | Frozen attempts workload GLM | HISTORICAL_AND_W6_MIXED_WITH_MISSING_ORIGINALS | Log-link mean of training-standardized log1p(player H3 attempts), log1p(team G5 attempts), positive-attempt fraction and missing flags; lambda1; original parameters/artifact gaps retained. | reports/methods-resumption-20261022/category-status.json |
| held_tree_h3_h8_passing | Historical pooled passing efficiency | SCORED_SEPARATE_HISTORICAL_PANEL | Hold saved tree attempts fixed; multiply by H3 or H8 pooled YPA with commonH8 eligibility/fallback. Both lose pooled yard control. | reports/methods-resumption-20261022/history-passing.json |
| held_tree_h3_h8_rushing | Historical pooled rushing efficiency | SCORED_SEPARATE_HISTORICAL_PANEL | Hold saved tree carries fixed; multiply H3/H8 pooled YPC. H8 small gain versus pooled, with adverse bias/tails and intervals crossing0. | reports/rushing-efficiency-v1/README.md |
| original_rb_protocol | Original five-season RB carry-share proposal | NOT_COMPLETED_PARTICIPATION_AND_PRIORS_BLOCKED | mu=tau*(SC+kappa*p0)/(ST+kappa), original five-prior-season p0/tau0 and kappa{0,25,100}; original history/fallback/window retained. | reports/source-policy-20261023/README.md |
| rec_half_registered | Frozen reception half-adjustment | REGISTRATION_PRESERVED_NO_RECOVERED_PROSPECTIVE_WIN | raw_rec+.5*(adjusted_rec-raw_rec); original registration and2026Weeks7-14, no restart/backfill. | config/preserved-rec-half-registration.json |
| receiving_ypt_h3 | Projected targets times H3 pooled YPT | SCORED_EXPOSED_W6_SEPARATE_FROM_DRAFT | Same-cutoff projected targets * sum(H3 rec_yd)/sum(H3 targets); exact-three history/source adapter and unchanged SITE fallback. | reports/methods-resumption-20261022/category-status.json |
| component_sum | Same-receipt combined-yard point | SCORED_EXPOSED_W6_NOT_INHERITED_GAIN | SITE rush_yd + SITE rec_yd on identical eligible rows; missing components retain registered fallback. | reports/methods-resumption-20261022/category-status.json |
| leaf_cdf | Empirical-leaf marginal forecast law | SCORED_LEGACY_SOURCE_AND_REFIT_PERMITTED_SOURCE | 32 ExtraTrees/depth8/minleaf30/seed1701; 95% leaf empirical distribution +5% earlier role/global support prior. | reports/all12-leaf-cdf-v1/method-config.json |
| median_hgb | Absolute-error/binary histogram boosting | SCORED_SOURCE_MATCHED | 150iterations/.05/depth3/15leaves/minleaf30/L2=10/seed1702; numeric point heuristic, binary genuine class probability. | config/median-boosting-research.json |
| count_A_role_B | Count objective and role-specific boosting | SCORED_SOURCE_MATCHED_WITH_ALIASES | Poisson objective on six counts; B separates roles; passing singleton and noncount aliases retained. Legacy prior-median fallback distinct from mean-v2. | config/role-count-research.json |
| count_A_mean_v2 | Corrected intended-mean Count A | SCORED_CORRECTED_V2 | Same registered Poisson-HGB specification, separately refitted in18V2 calls; required fallback uses stored prior.mean, not prior.median. Original frozen procedure not overwritten. | reports/distribution-cdf-after-audit-v2/README.md |
| direct_boosters | Six native direct configurations | SCORED_SOURCE_MATCHED_WITH_BINARY_RECOVERY | XGBoost/LightGBM/CatBoost ×small64-depth3 ormedium128-depth5; LR.05/L2=10; quantile.5 yards, Poisson counts, binary logloss. | config/direct-booster-screen-v1.json |
| baseline_corrections | Intercept/context corrections to honest CDF | SCORED_NO_NOMINATION | Corrections trained on earlier out-of-fold baseline predictions; log mean offset for counts and logit offset for events, exact frozen regularization/preprocessing. | reports/baseline-correction-report-v3/README.md |
| threshold_cdf | Monotone threshold-distribution challenger | SCORED_CORRECTED_V2_LOSES_ALL11_PRIMARY | Fixed threshold classifiers and monotone valid CDF construction with full-support tails; same information as controls. | config/distribution-cdf-after-audit-v2.json |
| cdf_response | Distribution-sensitive response forest | SCORED_CORRECTED_V2_NOT_EXACT_DRF_LIBRARY | ExtraTrees splits on weighted indicator CDF response grid; empirical outcome leaves plus5% support prior; binary arm exact leaf alias. | config/distribution-cdf-after-audit-v2.json |
| td_calibration | Four probability recalibrations on two bases | 16_FITS_ALL8_POOLED_BRIER_LOSE_BASES | Intercept-only, constrained Platt, constrained beta and increasing isotonic trained earlier-only; true infinite log losses retained. | reports/anytime-calibration-v1/README.md |
| conformal | Fixed80% chronological CQR | SCORED_NO_CHANGE_NOT_PROP_PROBABILITY_PROOF | Earlier calibration residuals choose interval radius; all20 radii zero; point and CDF unchanged. | reports/conformal-interval-v1/README.md |
| weekly_policies | P0/P1/P2/P3/P4 | SCORED_54_WEEK_DEVELOPMENT_REPLAY | Reference; previous-week; cumulative; nested earlier-only recency; frozen equal shortlist blend. Retain all losing weeks and startup/fallback. | reports/weekly-policy-checkpoint-v1/README.md |
| td_fixed_learned_blends | Equal and shrunk probability stacking | SCORED2023_24_NO_ADVANCE | Fixed .5CDF+.5Cat; earlier-only scalar Brier weight shrunk toward .5 with lambda.001; exactly2 weight fits. | reports/anytime-td-blend-v1/README.md |
| combined_joint | Fixed marginals, independence versus Gaussian copula | SCORED2023_24_BOTH_SUM_LAWS_LOSE | Randomized discrete PIT, correlation shrink n/(n+100),4096 fixed draws, sum components per draw; direct-total and Cat controls. | reports/combined-yard-copula-v1/README.md |
| dynamic_workload | Smooth-H8-k25 role shares with held efficiency | COMPLETE_FIXED_NUMERICAL_NEGATIVE_PARENT_RUNTIME_FAILURE_RETAINED | Fixed decayed team/player shares; half-life8/team slots, shrink25, fixed100-strength efficiency prior; same fallbacks/control population. | reports/dynamic-workload-fixed-forward-v1/README.md |
| recorded_lines | Original recorded threshold directions | SCORED_EXPOSED_W6_NO_MARKET_HYBRID_STUDY | 13 fixed point procedures; exact retained line/player/game cohort. Direction accuracy is not calibrated probability or EV. | reports/recorded-thresholds-v1/README.md |
| exact_ppr | Exact versioned website scoring transform | OLD_SITE_TARGET_UNSUPPORTED_NEW_CHART_SEPARATE | Original18primitive fields and conditional defensive-recovery attribution; no unsupported rare component imputed0. | reports/source-policy-20261023/README.md |
| player_context_news | Timestamped factual context intake | ENGINEERING_ONLY_NO_MEASURED_INCREMENTAL_GAIN | Source-linked identity/time/conflict records; no invented injury penalties or private gameplan access. | reports/player-context-intake-v1/README.md |
| ftn_targeted | Interception-worthy and catch-quality features | COMPLETE_RISK_FEATURE_COMPARISON_NEGATIVE_OTHER_FTN_UNTESTED | Permitted source/schema recovery distinct from qualified joins/as-of features; no completed incremental model comparison. | reports/ftn-charting-schema-buffered-v2/README.md |
| ngboost | Native conditional-law boosting | COMPLETE_SMALL_INTERCEPTION_PILOT_ONLY | Poisson/Bernoulli/signed law API and genuine synthetic runtime verified; six-fit NFL preparation inert and paused, previous failures retained. | docs/AFTER_AUDIT_CATEGORY_METHOD_MATRIX_20261025.md |
| remaining_proposals | ExactDRF/MMD,XGBoostLSS,AdaBoost,rich role/joint/market extensions | UNTESTED_OR_PREREQUISITE_ONLY | Not completed by mentioning libraries, acquiring metadata or building software fixtures. No measured gain assigned. | docs/AFTER_AUDIT_CATEGORY_METHOD_MATRIX_20261025.md |
| modern_count_cdf | modern_count_cdf | COMPLETE7RETAINED_LAWS_MEAN_AND_MEDIAN | NOT_RETAINED | reports/modern-cdf-control-completion-v1/PUBLIC_METRICS.json |
| modern_counts | modern_counts | COMPLETE9VALID_OF10OPPORTUNITIES_1FAILED | NOT_RETAINED | reports/modern-2026-cold-grade-v2/PUBLIC_METRICS_v2.json |
| common_history_2026 | common_history_2026 | COMPLETE17FITS_PRIMARY_MSE_ALL_LOSE_DEPTH_MAE_LOWER | NOT_RETAINED | reports/pass-att-common-learner-2026-v5/PUBLIC_METRICS.json |
| common_history_2025 | common_history_2025 | COMPLETE52FITS_H2_MSE_H3_MAE_55NEWOPPORTUNITIES_OLDFAILURES_RETAINED | NOT_RETAINED | reports/next-nfl-checkpoint-20261028/WEEK8_COMMON2025_PUBLIC_RESULTS.json |
| chart_ppr_v1 | chart_ppr_v1 | COMPLETE1HGBPOINTFIT_PLUS1STRONGCDF_CONTROL_FIT_FUTURECONSUMER_UNREADY | NOT_RETAINED | reports/next-nfl-checkpoint-20261028/CONTINUATION_PREREQUISITES_CHART_PILOT_RESULT_V1.json |
| historical_market_no2025 | historical_market_no2025 | COMPLETE_TIMING_UNVERIFIED_EXPLORATORY | NOT_RETAINED | reports/historical-market-comparison-no2025-v3/PUBLIC_METRICS.json |
| contemporary_L2_LAD_market | contemporary_L2_LAD_market | COMPLETE_CONTROLLED_NEWER_FOOTBALL_AND_OBJECTIVE_CORRECTIONS | NOT_RETAINED | reports/next-nfl-checkpoint-20261028/contemporary |
| Week7_numerical_capture | Week7_numerical_capture | COMPLETE_AVAILABLE_GENUINE5POINTGAMES_OTHER_TIMING_SEPARATE_NOTFULLWEEK | NOT_RETAINED | reports/week7-nonpassing-completion-20261027/PUBLIC_METRICS.json |
| modern_count_median_completion | modern_count_median_completion | COMPLETE5CELLS22PROCEDURESUMMARIES_4CACHEDPROJECTIONS_1RETAINEDLAWQUERY_0FITS | NOT_RETAINED | [OWNER_LOCAL_LOCATION] |

## All twelve category views

Each section exposes every exact product alias and every legacy alias in the inspected record set. The JSON preserves all underlying configurations/executions, own scores, coverage and source pointers. Missing fields remain absent or explicitly NOT_RETAINED. Tables are not pooled across incompatible populations.

### pass_yd

Retained legacy evaluations: **415**. Exact qualification product/policy views: **57**.

Exact product aliases: `CATBOOST_MEDIUM`, `EQUAL_CDF_CAT_HGB_POINT`, `HGB_MAE_DIRECT`, `LEAF_CDF`, `RESPONSE_CDF`.

### pass_td

Retained legacy evaluations: **460**. Exact qualification product/policy views: **64**.

Exact product aliases: `CATBOOST_MEDIUM`, `COUNT_A_LEGACY_POINT`, `COUNT_A_MEAN`, `HGB_MAE_DIRECT`, `LEAF_CDF`, `RESPONSE_CDF`.

- **COUNT_A** — Existingregisteredconnection/producerownerauthrouteblocked;noreadablefreshfeedverified;notautomaticwinner. The original scientific reports retain the exact arms, inputs, results and qualification limits.

### pass_cmp

Retained legacy evaluations: **444**. Exact qualification product/policy views: **64**.

Exact product aliases: `CATBOOST_MEDIUM`, `COUNT_A_LEGACY_POINT`, `COUNT_A_MEAN`, `HGB_MAE_DIRECT`, `LEAF_CDF`, `RESPONSE_CDF`.

- **A_COMPLETION_LAW_REPLAY** — NO_NEW_REPLACEMENT. The original scientific reports retain the exact arms, inputs, results and qualification limits.

### pass_att

Retained legacy evaluations: **488**. Exact qualification product/policy views: **85**.

Exact product aliases: `CATBOOST_MEDIUM`, `COUNT_A_LEGACY_POINT`, `COUNT_A_MEAN`, `DEPTH_CDF`, `HGB_MAE_DIRECT`, `LEAF_CDF`, `RESPONSE_CDF`.

### pass_int

Retained legacy evaluations: **482**. Exact qualification product/policy views: **64**.

Exact product aliases: `CATBOOST_MEDIUM`, `COUNT_A_LEGACY_POINT`, `COUNT_A_MEAN`, `HGB_MAE_DIRECT`, `LEAF_CDF`, `RESPONSE_CDF`.

### rush_yd

Retained legacy evaluations: **362**. Exact qualification product/policy views: **57**.

Exact product aliases: `CATBOOST_MEDIUM`, `EQUAL_CDF_CAT_HGB_POINT`, `HGB_MAE_DIRECT`, `LEAF_CDF`, `RESPONSE_CDF`.

- **RUSH_EFFICIENCY_FIXED_WORKLOAD** — CLOSE_RECIPE_NO_GAIN_PRIMARY_DIRECTION. The original scientific reports retain the exact arms, inputs, results and qualification limits.
- **RB_LEAF_PLAYER_DEFENSE_INCREMENT** — DIRECTION_NO_GAIN;NUMERICAL_INCONCLUSIVE;R4UNEXECUTED. The original scientific reports retain the exact arms, inputs, results and qualification limits.
- **ALIGNED_FRESHNESS_RB_LEAF** — INCONCLUSIVE_MEDIAN_REPLACEMENT;CLOSE_MEAN_TIMING_NO_GAIN. The original scientific reports retain the exact arms, inputs, results and qualification limits.

### rush_att

Retained legacy evaluations: **431**. Exact qualification product/policy views: **146**.

Exact product aliases: `A0_BACKFIELD_CDF`, `A1_BACKFIELD_CDF_ROLE_INPUTS`, `A2_DYNAMIC_ALLOCATION`, `A3_CONDITIONAL_PLAYED_EXPOSURE`, `ALWAYS_OVER`, `ALWAYS_UNDER`, `BACKFIELD_CDF`, `CATBOOST_MEDIUM`, `COUNT_A_LEGACY_POINT`, `COUNT_A_MEAN`, `LEAF_CDF`, `ORDERED_CDF`, `S0_RECENCY_ALLOCATION`, `STORED_COUNT_A_MEAN_CONTROL`.

- **BACKFIELD_CDF** — NO_PRIMARY_REPLACEMENT;NUMERIC_SHADOW. The original scientific reports retain the exact arms, inputs, results and qualification limits.
- **STRUCTURED_RUSH_ALLOCATION** — CLOSE_RECIPE_NO_GAIN. The original scientific reports retain the exact arms, inputs, results and qualification limits.
- **PLAYER_CONTEXT_CARRY** — E1_NUMERIC_SHADOW;NO_SELECTION_GAIN. The original scientific reports retain the exact arms, inputs, results and qualification limits.
- **M1_USAGE_CHANGE_ADAPTIVE_ALLOCATION** — CLOSE_RECIPE_NO_GAIN;USAGE_ONLY;PERSONNEL_SOURCE_BLOCKED. The original scientific reports retain the exact arms, inputs, results and qualification limits.
- **BACKFIELD_EXACT_LAW_SELECTION** — 2026SELECTIVE_SHADOW_INCONCLUSIVE/FULL_LAW_NO_GAIN;2023NO_UPGRADE. The original scientific reports retain the exact arms, inputs, results and qualification limits.
- **PERSONNEL_CONDITIONED_RB_OPPORTUNITY** — SEE_EXACT_RECORD. The original scientific reports retain the exact arms, inputs, results and qualification limits.

### rec

Retained legacy evaluations: **423**. Exact qualification product/policy views: **64**.

Exact product aliases: `CATBOOST_MEDIUM`, `COUNT_A_LEGACY_POINT`, `COUNT_A_MEAN`, `HGB_MAE_DIRECT`, `LEAF_CDF`, `ORDERED_CDF`.

### rec_yd

Retained legacy evaluations: **361**. Exact qualification product/policy views: **57**.

Exact product aliases: `CATBOOST_MEDIUM`, `EQUAL_CDF_CAT_HGB_POINT`, `HGB_MAE_DIRECT`, `LEAF_CDF`, `RESPONSE_CDF`.

### rush_rec_yd

Retained legacy evaluations: **358**. Exact qualification product/policy views: **57**.

Exact product aliases: `CATBOOST_MEDIUM`, `EQUAL_CDF_CAT_HGB_POINT`, `HGB_MAE_DIRECT`, `LEAF_CDF`, `RESPONSE_CDF`.

### anytime_td

Retained legacy evaluations: **594**. Exact qualification product/policy views: **5**.

Exact product aliases: `CATBOOST_MEDIUM`, `EQUAL_CDF_CAT_PROBABILITY`, `LEAF_CDF`, `ROLE_LOGISTIC`.

### nick-chart-ppr-v1

Retained legacy evaluations: **14**. Exact qualification product/policy views: **11**.

Exact product aliases: `CATBOOST_MEDIUM`, `CHART_HGB`, `CHART_LEAF_CDF`, `CHART_ROLE_LAW`, `RESPONSE_CDF`.

## Corrections, failures and ownership

The qualification amendment is applied alongside the preserved original record: unsupported Count A median/law views are not tested products. Original versus corrected grades, alias repairs, recovered saved fits, current-vintage reconstruction and genuine issuance remain separately labeled. A2/A3, catchability, carry/context, profile/defense, timing, M1 and unsuccessful later information findings remain. C1 and opportunity team strict fit reproduction remain FAILED; other component PASS results do not replace them.

A executed some permitted B/C joins. The originating model owner remains B/C; A does not claim those fits. Old M2, SKILL, opportunity-v1, frozen M3 and newer receiving-information experiments retain distinct identities. Mostly-fallback system weeks do not prove learned-model weeks. A projection display, direction rule, probability product and complete website selector do not borrow one another's qualification.

## Completeness and remaining gaps

Examined for this public view: existing scientific method/experiment/result registries, the retained all-method aggregate export, twelve-category qualification partitions and their published amendments. The source index binds twenty already-public files at an immutable revision. Broader owner-local branch and execution reviews are not newly disclosed here.

Excluded/unresolved: inaccessible private chats and deleted outputs; uninspected branch contents and arbitrary private-attempt receipts; separate Astra v10/v12 artifacts not actually obtained; historical source vintages and unmatched offers; unresolved alias equivalence; full B/C and original-website owner histories pending their owner contributions. Some exact code/model/fallback fields and own-side results remain NOT_RETAINED in the inspected metadata and are linked to their original owner records rather than invented.

The archived source status RUNNING/REGISTERED is not a fresh process observation. Source-week corrections override old mixed-panel actual-offer headlines; a problem in an old W6-W7 reference panel does not invalidate separately qualified native later offers. Anytime-TD has no assumed NO offer. Legacy website PPR is not substituted for exact chart scoring.

C consolidates this permitted A contribution with B, C and the website owner's separate contributions. No C acknowledgment or perfect lifetime catalog is required before an independently authorized pilot executes.

## V1.1 metadata corrections

The owner-local JSON amendment preserves the original base export and adds the eleven source-target `chart_ppr` records to the exact-chart category index under an explicit display alias. No original target key or score changes. The older legacy website PPR contract remains distinct.

The dated FTN source row has conflicting state/recipe wording. Preserve both as original metadata. Its narrow risk-feature comparison is recorded completed/negative; broader FTN catchability and relationship mechanisms are not established complete by that row. Later B throwaway/interception-worthy information studies are separately owned and remain negative at their tested scope.

## Permitted publication scope

This report publishes scientific method names, stated relationships, aggregate coverage and qualified dispositions. The matching JSON is a source index to the already-public aggregate evidence and method registries. Full private catalogs, internal control/transport records, source/training rows and model artifacts are withheld. No fit, source-vintage, private-row or live-consumer reproduction is established by these reporting files.
