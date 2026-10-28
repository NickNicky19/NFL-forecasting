# Forecasting research: complete navigation index

## Recent-season category completion — October 27, 2026

[Current-era category decisions](recent-season-category-decisions-20261027/README.md)
separates the 2025 and 2026 comparisons, Week 7 genuine pregame forecasts,
post-start reconstructions and the actual website fallback. The older
2022–2024 leaderboard remains a separate exposed historical benchmark.

- [Seven restored modern CDF controls, with separate mean and median products](https://github.com/NickNicky19/NFL-forecasting/blob/e3b86c86286512ebfd904f01ee0d809a1252d68a/reports/modern-cdf-control-completion-v1/PUBLIC_RESULTS.md):
  zero fits; fourteen new reconstructed products from seven retained models.
  Corrected Count A mean MSE advantages over these CDF controls are small,
  0.14%–0.54%, and the available paired intervals cross zero.
- [Completed available Week 7 nonpassing comparisons](https://github.com/NickNicky19/NFL-forecasting/blob/92cac4e187a21eaf5757d0f753fb40151cc8091a/reports/week7-nonpassing-completion-20261027/PUBLIC_RESULTS.md):
  thirteen retained final summaries, 971 newly attributed claims and no new
  forecasts. Genuine pregame and post-start lanes remain distinct. The full
  fourteen-game schedule includes a Thursday game outside the original query;
  it was not backfilled.
- [Fixed equal anytime-TD probability blend](https://github.com/NickNicky19/NFL-forecasting/blob/e2cefe973d5f4dbf88eef38937f0413e799270f0/reports/modern-anytime-equal-blend-v1/PUBLIC_RESULTS.md):
  it loses the stronger component on primary Brier in both 2025 and 2026 W1–6.
  The original CPU-cap failure remains failed; the successful continuation
  graded the retained frozen vectors with no new inference or fitting.

These results are not new website-relative or ranking-probability gains. All
three packets passed independent arithmetic and local fresh-process storage
checks; off-host restoration is not established by those checks. No selected
research-model deployment is claimed by this checkpoint.

- [Four restored 2025 passing challengers, primary gains/losses and separate QB distribution diagnostics](https://github.com/NickNicky19/NFL-forecasting/blob/8bc08f10653cc474a914b5366a1a348ff03b3d18/reports/modern-ten-control-pipeline-v4-restore4-2025/PUBLIC_RESULTS_v3.md):
  34,804 new forecasts from four retained models; zero refits; 664 supported QB
  player-games per target across 272 games and 18 weeks. Interception and
  completion mean MSE improve about 0.56%; passing TD and attempt MSE lose.
  Exposed reconstruction, with adverse tails and missing coverage retained;
  no new website issuance or prospective qualification.

## Latest actual work — October 26, 2026

The [accuracy wave](accuracy-wave-20261026/README.md) supersedes earlier
zero-NFL-fit NGBoost status for its separately named pilot only: one fixed
interception-mean NGBoost fit trained on 2019–2021 and scored 633 supported
2022 QB appearances. Its 0.247% MSE lead over matched Leaf-CDF is small, its
interval crosses zero, and MAE/bias worsen. It is research-tested, not selected
or release-ready. Original runtime failures and budgets remain preserved.

The same wave independently verified the Week 7 passing-workload diagnosis and
2022/2023 retained FTN value/denominator/player/timing counters. Actual-volume
substitutions are postgame diagnostics, and FTN source checks are not forecasting
experiments. Complete exact PPR and several source/availability gates remain
unresolved. All twelve category decisions and actual production dependencies
are explicit; no new deployment is claimed. The subsequent
[QB-only grading refresh](accuracy-wave-20261026/QB_REFRESH.md) actually completed:
two retained source bodies, 49 newly numeric-resolved labels, four resolved
genuine-pregame point games and one resolved genuine probability game. Mixed
timing, incomplete rare-event zero coverage and unmatched saved-control vintages
remain explicit. No enabled recurring scheduler is inferred from this run.

The initial aggregate publication is
[`a8f36f3`](https://github.com/NickNicky19/NFL-forecasting/blob/a8f36f356842f711584d519508f7b15018c1e5b9/reports/accuracy-wave-20261026/README.md).
Later local checkpoint additions are versioned separately. The prior index and
study descriptions below retain their original dates and scientific claims.

Subsequent work restored explicit historical zeros for 105 player-games, then
[rescored 85 fixed procedure/output products](accuracy-wave-20261026/RESTORED_2024.md)
on all 272 REG games/18 weeks of 2024. CatBoost controls matched the source,
queries and old labels. Count medians remain separate from count means; exact
PPR remains blocked. The incumbent anytime blend was also checked as an openly
new reconstruction, not recovered old P4 rows. These runs added no model fits,
live selection switches or deployments and retain their original source limits.

The further [hierarchical interceptions pilot](accuracy-wave-20261026/HIERARCHICAL_INTERCEPTIONS.md)
retained one converged fit but no scored forecast archive. Two prediction passes
and both format failures are recorded; no accuracy gain or deployment is claimed.
The [fresh production check](accuracy-wave-20261026/RELEASE_STATUS.md) records
unchanged served assets, failed hosted CI and the existing integrator's concrete
remaining scope/release actions.

Updated 2026-10-23. Scope: recorded work in this lab and the earlier evidence
actually recovered here. This index adds no forecasts, fits, outcomes or scores.
It does not claim to recover every artifact from an earlier chat.

The latest published research is on branch `research/pooled-ypa-20261022` in
[draft PR #1](https://github.com/NickNicky19/NFL-forecasting/pull/1), not merged
into `main`. For frozen studies the website remains a reference; the owner's October 24 instruction separately authorizes provisional website integration through its normal protected writer workflow.

## Start here

| Question | Record |
|---|---|
| Have any methods beaten SITE, and was SITE tested to the same extent? | [Interpretation of observed improvements, incumbent status and independent audit requirements](../docs/website-comparison-interpretation.md). Some matched retrospective errors improve; no category has passed all release gates. The inspected record does not establish comparable predictive validation for the deployed website. |
| What is the latest state of all twelve categories? | [Complete correction comparison](baseline-correction-report-v3/README.md), [latest twelve-category matrix](baseline-correction-report-v3/category-status.json), [six-pipeline booster screen](direct-booster-screen-v1/README.md), and [strong source-matched references](source-matched-base-v1/README.md); [earlier website comparison](role-count-boosting-v1/README.md) remains separate |
| How much better or worse was every latest comparison? | [Every booster setting](direct-booster-screen-v1/aggregate-report.md), [complete numerical results](direct-booster-screen-v1/aggregate-report.json); historical raw/SITE are unavailable for this panel. Independent arithmetic review status is in the screen README/ledger. |
| What happened across the whole execution? | [Single execution ledger](../execution/ledger.jsonl) |
| Which original artifacts were recovered or remain missing? | [Evidence inventory](../execution/evidence-inventory.json) |
| Where are all study packets? | [Reports directory](.) |
| What rules govern research and promotion? | [Execution specification](../EXECUTION_SPEC.md), [lab registration](../config/research.json), each study's separate frozen registration |
| What is the adopted ongoing goal and latest source prerequisite? | [Active goal](../RESEARCH_GOAL.txt), [player-context software/cache checkpoint](player-context-intake-v1/README.md); no new accuracy claim |
| What is the operational source-repair state? | [V1 source acceptance](operational-source-repair-v1/README.md), [v2 strict storage and value parity](OPERATIONAL_STORAGE_V2.md), [22-package real-data reference replay](reference-runtime-v2/README.md); identity/population qualification and hosted activation remain pending |
| What caused the high reference fallback, and what was repaired? | [Exact cached identity adapter](query-identity-v1/README.md): historical identity matches 90→585/681 in a new private metadata version; no forecast accuracy claim or old-output changes |
| Did corrected identities reach features and forecasts? | [Corrected feature and 22-package replay acceptance](canonical-query-reference-v1/README.md): usable recent history 79→478/681 broad roster rows, all five routes agree; no new accuracy score or issued forecasts |
| How is the owner's independent audit being used? | [Audit intake and optional joint-helper repair](INDEPENDENT_AUDIT_INTAKE_20261023.md), [completed source-matched benchmark](source-matched-base-v1/README.md), [source/publication prerequisite follow-up](audit-followup-v1/README.md); software/source checks add no forecast accuracy evidence |
| Where are the additional methods and current booster work? | [All-twelve-category intake](../docs/ADDITIONAL_METHODS_INTAKE_20261023.md), [CPU library capability](../docs/direct-boosters-capability-v1.md), [shared adapter](../docs/direct-boosters-v1.md), [completed report](direct-booster-screen-v1/README.md). Original time stop/six binary failures remain; separate saved-row reporting completed with zero new fits/forecasts. No development nominees; independent verification failures/status stay explicit. |
| Were the six XGBoost touchdown failures resolved? | [Separate technical recovery](direct-xgboost-binary-recovery-v2/README.md), [all 80 comparisons](direct-xgboost-binary-recovery-v2/aggregate-report.json). Six frozen derivatives scored with zero new fits; both settings lose CDF. Both prior FAILED executions remain. |
| Have conservative baseline corrections been tried? | [Completed all-target comparison](baseline-correction-report-v3/README.md): 44 earlier-only fit attempts, 66 scored files, eleven scored categories and exact PPR blocked. Five primary CDF-relative gains, nine losses, eight unchanged; no development nominees. Independent row arithmetic passed. Original CPU stop and V2 retention failure remain FAILED; no website-relative or confirmed gain. |
| What follows the direct learner screen? | [Conditional smooth/change-point opportunity design](../docs/dynamic-opportunity-screen-v1-draft.md) and [targeted FTN charting pilot design](../docs/ftn-charting-targeted-pilot-design-v1.md), with [advertised free asset metadata](ftn-charting-release-metadata-v1/aggregate.json). Designs and asset identities are not fitted gains or qualified datasets. |
| What has the dynamic workload work actually executed? | [Implementation and bounded preparation failures](dynamic-opportunity-backend-v1/README.md): normalized missingness was diagnosed and repaired; four new source and four recovery contracts passed. The real-data continuation hit its fixed preparation-time limit before any forecasts or scores. All earlier failures remain; no predictive gain. The [implemented calendar/roster cache](dynamic-source-calendar-cache-v1/README.md) passed six new fictional equivalence checks and reduced one instrumented fictional call from 23.93 to 9.51 seconds (60.24%); no NFL speed or accuracy gain is established. Old failed study budgets remain consumed. Later computational continuations preserved 24 frozen development packages but have no completed accuracy report; the [V5 retained failure](dynamic-completion-v5/README.md) identifies a reused-body retention-estimate overcharge. A separately versioned computational repair is being prepared without changing scientific formulas or quotas. [Core](dynamic-opportunity-core-v1/README.md), [history](dynamic-opportunity-history-v1/README.md), [guard](dynamic-history-guard-v2/README.md), and [replay](dynamic-opportunity-replay-v2/README.md) retain their separate software scopes. |
| Can actual future captures replace the reconstructed seven-day clock? | [Opt-in prospective availability prerequisite](prospective-availability-v1/README.md): eighteen fictional contracts passed after independent identity/category fixes. No real source-capture producer, feature/model policy, issuance or hosted activation has changed; original historical evidence keeps its frozen timing rules. |
| Has conformal interval calibration been tested? | [Completed fixed 80% chronological interval comparison](conformal-interval-v1/README.md), [all twelve states](conformal-interval-v1/category-status.json) and [full annual/pooled metrics](conformal-interval-v1/aggregate-report.json): all 20 radii selected zero expansion; ten primary interval scores unchanged over 544 games / 36 season-week blocks. Eight new fictional arithmetic/consumer checks passed. Exact PPR remains label-blocked; anytime TD retains its separate probability reference. This exposed interval experiment changes no point, CDF probability or website default. |
| Is the requested NGBoost family available? | [Versioned technical draft](../docs/ngboost-direct-distribution-v1-draft.md): exact 0.5.11 Apache-2.0 source and the eight-package dependency closure are authenticated. An oversized metadata catalog failure is retained; a bounded exact-release route resolved it. The [uninstalled source-bundle extraction](ngboost-vendored-source-bundle-v1/README.md) completed with 287 authenticated files and eight genuine metadata versions; no package imports or installation occurred. Native capability tests and the proposed 66 NFL fit slots have not started. |
| Has independent participation evidence been recovered? | [One-game FTN appearance pilot](../docs/ftn-appearance-pilot-v1.md), [reviewed aggregates](ftn-appearance-pilot-v1/aggregate.json). Asset hash verified, 163 play keys and 92 on-field identifiers; no zeros restored, DNP inference, full-population or in-season qualification. |
| Did the completed explicit-zero audit restore outcomes? | [Full-inventory audit result](raw-orphan-zero-audit-v3/README.md): all 67 raw records and 97-player union retained; zero new support candidates in every category. No accepted-label, model or forecast change. The failed earlier executor remains preserved. |
| What blocked the first zero audit, and what changed? | [Executed context diagnosis](FTN_CONTEXT_METADATA_RESULT_V2.md): one missing player ID among 67 raw records; [completed raw-record quarantine](raw-orphan-context-v1/README.md) now preserves all 67 records, 97 known players plus the orphan, all offers and witnesses. Earlier failures remain. No zero labels or model scores changed; the next numerical audit is separately versioned. |
| Has the hosted safety guard actually run? | [Focused lab PR #2 and actual hosted acceptance](hosted-safety-handover-v1/README.md): existing scheduler exits before source acquisition or detailed publication; private storage and qualified handover remain pending. No successful forecast capture or website change is claimed. |

## Every recorded numerical study packet

These rows index distinct studies, not additional independent football samples.
Later studies repeatedly use exposed periods. Gains against recent/pooled/CDF
controls must not be called gains against the website. Different source
qualification can change denominators; compare each candidate and control on
the exact paired rows in its own report. Positive signed improvement means
`100 * (control_error - candidate_error) / control_error`; zero control error
gives N/A. Numeric MAE and TD Brier are different units.

| Study | Methods and evidence | Improvements, losses and limits | Full results |
|---|---|---|---|
| Initial historical campaign | Recent/pooled, workload, ridge, tree, distributional, ensemble and three feature ablations; 432 configured season/target/method trials; development 2022–23, evaluation 2024 | Development-selected validation primary gains against recent range 3.81–16.18% across supported targets. Broad all-skill cohorts contain non-QB passing zeros; bias/coherence gates fail for some targets. No historical website comparator. | [Report](initial-campaign/README.md), [all summaries](initial-campaign/summary.json), [paired results](initial-campaign/paired.json), [selection](initial-campaign/selected.json) |
| Public NGS ablation | Same fixed ridge/logistic with and without 28 lagged NGS features; exposed 2023 | Three primary losses improve slightly: passing yards +0.0043%, carries +0.7781%, receptions +0.0330%; eight worsen. These are broad all-skill development comparisons against ridge, not website gains. | [Full results and registration](ngs-context-study/summary.json), [source binding](ngs-context-study/ngs-source-binding.json) |
| Public scheme/pace ablation | Same fixed ridge/logistic with a 47-feature PBP/schedule context group; 11 fits; exposed 2023 | All 11 supported primary losses worsen, by 0.24–6.47%. Returned iteration-limit warning retained. Source/timing limitations and missing feature groups remain explicit. | [Report and target table](public-scheme-study/README.md), [full results](public-scheme-study/summary.json) |
| Original archived website comparison | Earlier fixed selected lab models, raw, SITE, recent, pooled; 30 fits; exposed 2026 Week 6 | Pairwise selected-versus-SITE numeric MAE improves five targets and worsens five under this source version. Small rare-event cohorts and a cold-context protocol deviation remain. | [Report](archive-lab-week6-v1/README.md), [full results](archive-lab-week6-v1/report.json), [deviation](archive-lab-week6-v1/protocol-deviation.json) |
| Expanded source/outcome coverage | Revised qualified coverage of the same archived opportunities | Four numeric category losses improve and six worsen in this expanded study. Earlier errors are not compared across changed denominators. This is not another independent week. | [Report](archive-source-coverage-v1/README.md), [full results](archive-source-coverage-v1/report.json) |
| Fixed original-method reconstructions | Held SITE attempts × H3 pooled passing rate; pooled completion rate; projected targets × H3 receiving rate; same-receipt component sum; separate fixed generic references | Passing yards +20.16% SITE MAE with worse bias; completions +3.21% MAE but worse RMSE; receiving yards +0.65% and combined +0.25%, both losing raw. All are exposed Week 6 results. Missing original executables are not claimed reproduced. | [Indexed website scorecard](methods-resumption-20261022/website-comparison.md), [full category records](methods-resumption-20261022/category-status.json) |
| Historical passing efficiency | Same saved tree-attempt point × H3/H8 pooled YPA, common H8 history gate, fixed fallback; zero new fits | On 1,960 QB appearances, MAE: recent 75.6532, pooled 73.5458, H3 76.7268, H8 74.4522 yards. Both candidates lose pooled. This is distinct from the SITE-held H3 formula. | [Report](methods-resumption-20261022/README.md), [full results](methods-resumption-20261022/history-passing.json) |
| Historical rushing efficiency | Same saved tree-carry point × H3/H8 pooled YPC, common H8 gate; zero new fits | RB REG n=4,591: H8 MAE 22.6288 versus pooled 22.8168 (+0.8241%); bias/p90 worsen and both primary intervals cross zero. H3 loses pooled. No website forecast exists for this panel. | [Report](rushing-efficiency-v1/README.md), [full results](rushing-efficiency-v1/report.json) |
| Empirical leaf distributions | Fixed smoothed tree-leaf CDFs, two panels, 66 fits, exposed 2022–24 | Lower-median numeric MAE gains 7.39–18.63% against pooled; TD Brier gains 3.96–4.03%. Some biases worsen; context interception RMSE worsens 14.92%. These are not website gains. Exact PPR blocked. | [Report](all12-leaf-cdf-v1/README.md), [category results](all12-leaf-cdf-v1/category-status.json), [model manifests](all12-leaf-cdf-v1/model-manifests.json) |
| Direct website CDF comparison | Same empirical-CDF family, two panels, pure forecasts and prespecified 50/50 SITE blends; 22 fits; exposed Week 6 | Mixed by target/panel. Rush-yard blend SITE MAE gains 11.26/11.61%; receiving blend gains 2.89/3.13% with worse RMSE/bias. Pure TD Brier gains 3.97/3.24%. Losing variants, coherence and source-vintage limitations retained. | [All twelve targets](website-direct-leaf-cdf-v1/README.md), [all 48 contrasts](website-direct-leaf-cdf-v1/aggregate-report.md), [full results](website-direct-leaf-cdf-v1/aggregate-report.json) |
| Absolute-error boosting | Fixed HGB, two panels, 88 fits; historical 2022–24 plus Week 6; fixed secondary 50/50 SITE blends | Mixed gains and material failures. Carry points collapse to zero for 99 warm Week 6 RB contexts; SITE MAE worsens 134.80%. Historical RB rushing yards/carries also worsen. No version was promoted. New source packet differs from older CDF training. | [All-target report](median-boosting-v1/README.md), [full results](median-boosting-v1/aggregate-report.json), [source policy](source-policy-20261023/README.md) |
| Recorded prop-threshold study | Thirteen already-frozen point variants on saved provider-fed thresholds; zero fits or new model predictions | 604 original lines, 585 supported outcomes, 13 games/one exposed week. All 156 method-target slots and losses retained. Point direction is not an over/under probability. Not another point-model validation sample. | [Report](recorded-thresholds-v1/README.md), [all-target matrix](recorded-thresholds-v1/category-status.json), [full results](recorded-thresholds-v1/aggregate-report.json) |
| Count objective and role partition study | Six Poisson count objectives, separate role estimators, two fixed arms; 136 fits; same source as prior HGB | Both arms improve five Week 6 primary errors, worsen six, and block PPR. Across 44 available historical/Week 6 primary contrasts: 14 improve, six unchanged, 24 adverse. Carry failure is repaired but both arms still lose SITE. Original failed reporting and zero-fit repair remain explicit. | [Latest report](role-count-boosting-v1/README.md), [all 48 slots](role-count-boosting-v1/aggregate-report.md), [full results](role-count-boosting-v1/aggregate-report.json), [independent review](role-count-boosting-v1/review-receipt.json) |
| Source-matched base benchmark | Existing CDF, absolute-error HGB, count A, role B, recent and pooled refitted on identical permitted REG inputs; 168 estimator attempts/66 references; exposed 2022–24 | CDF has lower primary error than HGB on ten of eleven scored categories; combined yards is 0.0277% worse. Many differences are small, some intervals cross zero and secondary bias/tails worsen. Historical raw/SITE unavailable; PPR blocked. Original time stop, binary endpoint report failure and separate analytic diagnostic view are retained. No prospective gain or promotion. | [Report](source-matched-base-v1/README.md), [all comparisons](source-matched-base-v1/aggregate-report.md), [full results](source-matched-base-v1/aggregate-report.json), [exact execution wrappers](source-matched-base-v1/execution-code/README.md) |
| Six direct booster pipelines | XGBoost/LightGBM/CatBoost, two fixed settings each; 198 estimator attempts, 192 successful scored files, six technical binary failures and eighteen exact-PPR blocks; identical permitted source/cohort/features, exposed 2022–24 | Even selected minimum losses give only five small CDF-relative gains (0.0282–1.0140%) and six losses; no pipeline meets the frozen development nomination checks. Count mean MSE, signed-yard MAE and TD Brier are distinct products. Original reporting timeout remains; zero-fit saved-row continuation completed. No historical SITE/raw or prospective gain. | [Report](direct-booster-screen-v1/README.md), [all settings](direct-booster-screen-v1/aggregate-report.md), [all annual/all-offered results](direct-booster-screen-v1/aggregate-report.json), [category matrix](direct-booster-screen-v1/category-status.json) |
| Conservative baseline corrections | Two shrunk intercept/context arms on honest chronological CDF predictions; 44 fit attempts, 66 frozen forecast/scored files, exposed 2022–24 | Against CDF: five primary gains, nine losses, eight unchanged; largest gain 0.5515% passing-TD MSE. Both arms fail advancement in all eleven scored targets; exact PPR blocked. Independent arithmetic accepted all 1,100 main/later pairs. Scientific CPU failure and reporting storage failure preserved; separate zero-fit report completed. | [All twelve targets](baseline-correction-report-v3/README.md), [full aggregate pointers](baseline-correction-report-v3/aggregate-report.json), [matrix](baseline-correction-report-v3/category-status.json), [independent check](baseline-correction-report-v3/review/ARITHMETIC_PASS.json) |

### Original evidence and proposals that are not completed new studies

- Original passing-yard runner/inputs/rows and original attempts coefficients
  remain incompletely recovered. The [inventory](../execution/evidence-inventory.json)
  and [passing documentation](../docs/passing-and-model-engine.md) distinguish
  reported original results, new reconstructions and failed applications.
- `rec-half-adjustment-v1`: `raw + 0.5 * (SITE - raw)`, original registration and
  2026 Weeks 7–14 are preserved in [the frozen record](../config/preserved-rec-half-registration.json).
  Its presence in code is not a recorded prospective win. Generic reception
  models in other studies do not replace this experiment.
- Original RB carry-share proposal: team-volume × shrunken individual carry
  share, five prior seasons and fixed kappa grid `{0,25,100}`. Its complete
  participant/played-zero/prior gate remains unresolved; no original kappa
  selection or validated carry-share result is claimed. See [readiness](source-policy-20261023/rb-gate.json)
  and [readiness code](../nfl_lab/rb_readiness.py).
- Exact offensive PPR: scoring arithmetic, component coverage and source probes
  are recorded; they have not yielded qualified full-contract training/outcome
  labels for these studies. See [component audit](../docs/ppr-component-coverage.md),
  [Week 6 bridge](source-policy-20261023/ppr-w6-positive-bridge.json),
  [dictionary findings](source-policy-20261023/exact-ppr-schema-followup.json) and
  [generator findings](source-policy-20261023/exact-ppr-generator-followup.json).
  The generator probe's final-bookkeeping wall-cap breach remains disclosed.

## Formulas, fitted algorithms and exact parameters

Source code and each immutable study config are the exact implementation
references. A short recipe below does not replace its history qualification,
rounding, training-only preprocessing, fallback or source contract.

| Family | Definition and implementation |
|---|---|
| All original 12 method names | `recent`, `pooled`, `raw_sleeper`, `pinned_website`, `workload`, `ridge`, `tree`, `distributional`, `ensemble`, `ridge_without_opponent`, `ridge_without_workload`, `ridge_without_team`; [code](../nfl_lab/models.py), [engine guide](../docs/passing-and-model-engine.md), [config](../config/research.json) |
| Recent/pooled controls | Shrunk three/eight-game summaries and trained role/global priors; exact missing-history behavior in [models.py](../nfl_lab/models.py) |
| Workload/share/efficiency | Passing exposure × shrunk rate, carry/target volume × signed efficiency and declared prior/fallback paths; [code](../nfl_lab/models.py). These are new lab recipes, not recovered original QB/RB coefficients. |
| Regularized/tree/ensemble | Ridge alpha 32; initial tree 24 trees/depth 6/leaf 30/seed 1701; initial fixed ensemble weights ridge/workload/recent = .50/.25/.25. [Exact implementation](../nfl_lab/models.py) |
| Distributional family | Poisson-form count mean with fitted NB2 dispersion; signed normal yards; Bernoulli event probability; participation modeled separately. [Implementation and support](../docs/passing-and-model-engine.md) |
| Original-style passing yards | Original SITE attempts × `sum(H3 pass_yd)/sum(H3 pass_att)`, exactly three qualified appearances, unchanged SITE-yard fallback; [versioned reconstruction](../nfl_lab/research_passing.py), [contract](../docs/research-passing.md) |
| Completion-rate candidate | Original SITE attempts × `sum(H3 pass_cmp)/sum(H3 pass_att)`, frozen history/fallback rules; [evidence](methods-resumption-20261022/category-status.json) |
| Receiving-yard candidate | Same-cutoff projected targets × `sum(H3 rec_yd)/sum(H3 rec_tgt)`; [completed source/history adapter](../nfl_lab/receiving.py), [retained arithmetic core](../nfl_lab/retained/receiving_yards_core_draft.py), [completed study](methods-resumption-20261022/category-status.json) |
| Combined/PPR/TD definitions | Component-sum point candidate evaluated separately; [combined audit](combined-yard-coherence-2024.md); exact website scoring and event definitions in [scoring.py](../nfl_lab/scoring.py), [PPR qualification](../nfl_lab/ppr_outcomes.py) and [live grader](../nfl_lab/live.py). Do not substitute TD probability for expected TD count. |
| Empirical leaf CDF | 32 depth-8 trees, leaf minimum 30, 5% full-support trained prior; mean/median/law scored separately. [Code](../nfl_lab/cdf_engine.py), [contract](../docs/EMPIRICAL_CDF_RESEARCH.md), [method config](all12-leaf-cdf-v1/method-config.json) |
| HGB absolute-error/binary | 150 iterations, learning rate .05, depth 3/max 15 leaves, leaf 30, L2 10, seed 1702, no early stopping. [Code](../nfl_lab/median_boosting.py), [config](../config/median-boosting-research.json), [contract](../docs/MEDIAN_BOOSTING_RESEARCH.md) |
| Poisson HGB and role partitions | Same fixed topology; six count targets change objective/link; per-role preprocessing/estimators in arm B, exact aliases retained. [Code](../nfl_lab/role_boosting.py), [config](../config/role-count-research.json), [contract](../docs/ROLE_COUNT_RESEARCH.md), [model/environment manifest](role-count-boosting-v1/method-manifest.json) |
| Website blends | Separate fixed 50/50 pure-model/SITE point or genuine TD-probability blends, no fitted weight search. [CDF study](website-direct-leaf-cdf-v1/README.md), [boosting study](median-boosting-v1/README.md) |
| Feature ablations | Opponent/workload/team group removal; [NGS](../nfl_lab/context_study.py); [public scheme/pace](../docs/scheme-context-study.md), [config](../config/scheme-study.json) |
| Statistical resampling | Paired game/week bootstrap under each study's own seed/replicate/confidence rules. This Monte Carlo computation estimates uncertainty; simulated or repeated rows do not become new NFL games. |
| Honest baseline correction | Fixed shrunk mean-log offsets, median residual corrections and binary-logit offsets fitted to earlier chronological CDF predictions; two arms and training-only preprocessing. [Core](../nfl_lab/baseline_correction.py), [exact policy](../config/baseline-correction-v1.json), [all-target results](baseline-correction-report-v3/README.md). |

## Data, versions and availability

- Historical sources include public NFLverse/NFL statistics, weekly rosters,
  schedules, identity metadata, public NGS and the particular PBP assets used by
  the scheme/source studies. Raw/SITE controls come from retained original
  Sleeper/website captures where actually available. ESPN final-status evidence
  supports the specified grading paths. Exact source hashes, clocks and
  coverage belong to each study, not one interchangeable dataset.
- The [original data contract](../docs/data_contract.md) documents the legacy
  pipeline. The later [source-policy update](source-policy-20261023/README.md)
  excludes PFR snap-derived training/inference without a resolved permission
  grant. [New permitted-source builder](../nfl_lab/permitted_source_features.py)
  and [latest source manifest](role-count-boosting-v1/method-manifest.json)
  govern the later HGB/role studies. Old forecast outputs remain retained
  benchmarks; their existence does not requalify old source use or deployment.
- Earlier revised historical downloads and an assumed seven-day availability
  lag are reconstructed evidence. They are not authentic archived pregame
  publications. Preserve cold players, missing outcomes, played zero, DNP,
  unknown participation, fallbacks and corrections as separate states.
- News/injury/weather interfaces or proposals are not completed numerical
  ablations. Authenticated historical injuries/news, routes, future gameplans
  and forecast-weather versions have not all been acquired/tested. There is
  no claim that every possible feature or method has been exhausted.

## What is and is not public

**Published:** reviewed code, formulas/configs, aggregate scores including losses,
coverage/bias/tails/calibration, source/model hashes, software/replay contracts,
review receipts, the ledger and original recovery gaps.

**Private:** retained raw bodies, detailed player/game/play rows, feature/history
tables, row-level forecasts/outcomes/deltas, fitted model weights and private
reference fixtures. Public hashes identify these artifacts but do not supply
their bytes. Therefore the public repository alone is not a self-contained
reproduction package for every historical run.

**Not recovered or not executed:** missing original artifacts named in the
inventory, independently confirmed gains that have not occurred, unrun RB
proposal fits and blocked exact-PPR comparisons. These cannot be supplied by
renaming a formula, report or software test as original NFL evidence.

## Operations and software records

[Hosted verification](hosted-verification.json), [scheduled-delivery evidence](scheduled-delivery-2026-10-22.json),
[handover contract](../docs/operations-and-handover.md), [H3 point-recording prerequisite](h3-recording-contract-v1/README.md),
[source/schema code](../schemas), [software tests](../tests), and study-specific
review receipts document engineering checks. Test counts, replay success and
runtime measurements are not additional predictive observations.

## Meaning of the earlier five improved website-relative categories

Those five are retrospective leads from one exposed Week 6. Historical
passing-TD/interception gains reverse against old HGB, some bias/tail metrics
worsen, and the passing-yard result is an existing byte alias. These findings
do not establish a qualified five-model replacement package. Categories can
qualify independently under their applicable gates. Later confirmation,
operational input timing and consumer/replay/fallback acceptance remain
separate requirements. No method is claimed globally best; no website change
or deployment is performed by creating this index.

The later source-matched benchmark addresses the audit's source-comparability
concern. It does not add another website comparison or future confirmation.
Its complete target matrix preserves all six methods, N/A comparators, losing
combined-yard result, separate mean/median scores and partial participation
coverage. The independent numerical review reused the same cached NFL rows;
arithmetic agreement adds no new games. Player/team/opponent subgroup execution
remains pending an efficiency prerequisite under its original finite budget.

## Actual initial pregame capture (2026-10-24)

[All-twelve-category capture and release status](weekly-provisional-capture-v1/README.md) · [Machine-readable matrix](weekly-provisional-capture-v1/aggregate.json) · [Genuine hosted canary proof](private-draft-canary-v2/ACTUAL_HOSTED_RESULT.json).

Eighteen procedures saved 7,672 candidate rows for 610 distinct player-games in 13 future games; the registered startup rule saved 2,832 selected rows. Outcomes are pending. The harmless hosted storage canary passed; no NFL data was uploaded. Website PR #3 is draft and undeployed; live R0-relative gains remain unknown. Original scientific registrations remain unchanged.
