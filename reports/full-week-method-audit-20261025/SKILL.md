**Audit navigation:** [main conclusions](README.md) · [original public evidence sources](SOURCE_MANIFEST.json). Collated compressed audit bundles and internal intermediate files are retained locally and are not included in this public publication. Named source-file and bundle-part references in the narrative describe those retained records; original public reports provide the underlying published evidence.

# Full-week audit: five skill categories

Read-only synthesis dated 2026-10-25. No new experiments, tests, model restores, forecasts, NFL row reads, scoring, protected outcomes, HTTP or CAS work. Actual backend: **UNATTESTED**.

## Lowest observed losses in the named compatible panels

These are exposed descriptive minima among the named methods below. They establish neither global optimality nor future accuracy. Count MSE, yard point MAE and distribution CRPS remain separate products. The corrected fixed catalog is fresh leaf CDF / corrected Count-A mean-v2 / six direct boosters plus the two new distribution learners. The wider point column retains frozen legacy methods and weekly policies; those products can have lower observed errors without acquiring a new mean/law identity.

| Target | Scored / offered | Lowest corrected fixed point loss | Lowest named frozen/policy point loss | Lowest corrected full-law CRPS |
|---|---:|---|---|---:|
| rush_yd | 4,558 / 6,235 | leaf_cdf MAE **19.718955682317** | leaf_cdf MAE **19.718955682317** | response **14.096372718811** |
| rush_att | 4,558 / 6,235 | direct_catboost_medium MSE **24.046409592787** | P4 MSE **23.948563771899** | response **2.543566142104** |
| rec | 15,251 / 21,504 | count_A_mean_v2 MSE **3.254146452089** | legacy_count_A MSE **3.243919170097** | response **0.910030765704** |
| rec_yd | 15,251 / 21,504 | direct_catboost_medium MAE **16.343397995396** | P4 MAE **16.342946966774** | response **11.665621906037** |
| rush_rec_yd | 15,251 / 21,504 | direct_catboost_medium MAE **20.983925135032** | P4 MAE **20.966112819114** | response **14.927193694912** |

**Version distinction:** the frozen Count-A points use a numeric prior median on explicit fallback rows. Corrected `count_A_mean_v2` substitutes the training role/global prior mean on those rows, and belongs to the later corrected-feature/refit study. The old frozen carries/reception MSEs are 24.024641840981808 / 3.2439191700973486 in the policy catalog; corrected mean-v2 gives 24.296955539604067 / 3.2541464520891097. Do not relabel the old procedure or attribute the entire between-study difference solely to fallback. Tiny last-bit differences between independently aggregated exports are retained in their exact source cells.

**P4 remains visible:** its equal-weight yard point is an arithmetic average of component points, not an intended median or a mixture median. Its carries MSE 23.948563771898566 and yard MAEs 16.342946966774235 / 20.966112819114475 are the lowest observed broader point heuristics in this inventory. Receptions illustrates a different result: fixed legacy Count A is below every P0–P4 policy; P2 is the lowest policy at 3.245656825932383. The smaller heuristic losses are not silently excluded. No full-CDF P4 blend was evaluated.

## Bias, tails and uncertainty

Corrected fixed-point diagnostics (prediction minus outcome; p95 is absolute error):

| Target | Method | Bias | p95 |
|---|---|---:|---:|
|rush_yd|leaf_cdf|-6.760640632|62.000000000|
|rush_att|direct_catboost_medium|+0.090392117|10.071771728|
|rec|count_A_mean_v2|+0.019261013|3.704759699|
|rec_yd|direct_catboost_medium|-5.443884937|53.896859014|
|rush_rec_yd|direct_catboost_medium|-6.013686242|63.740447096|

P4 improves the carry, receiving-yard and combined-yard primary losses versus P0 CDF, with both nominal week/game delta intervals below zero. Its biases are +0.099597866, −5.600048822 and −6.214534420; p95s are 10.086334702, 54.137940484 and 64.040433050. These tails worsen versus P0, and receiving-yard bias/tail worsen versus fixed CatBoost medium despite the tiny 0.000451029-yard MAE reduction. The policy intervals are **P4 versus P0**, not intervals versus the retrospectively lowest fixed member or new response model.

| CRPS: response minus fresh CDF | Relative reduction | Week95% delta interval | Game95% delta interval |
|---|---:|---|---|
|rush_yd|0.052166837%|[-0.029665580219253754, 0.015181200388143402]|[-0.03367452515278206, 0.020206033459072115]|
|rush_att|0.040147535%|[-0.00644709185054538, 0.0042019687072511495]|[-0.005443186373024728, 0.0036016732145733063]|
|rec|0.139181345%|[-0.002028962950081443, -0.0005965754841828424]|[-0.0020970579791450184, -0.000535056455028216]|
|rec_yd|0.063095939%|[-0.018355111853050957, 0.0035902896604855677]|[-0.01710853574237144, 0.002310504304736544]|
|rush_rec_yd|0.128733072%|[-0.03339335375903333, -0.005301181867587126]|[-0.03408435813796178, -0.004777961275085665]|

Only receptions and combined have both CRPS intervals strictly below zero. Rushing-yard, carry and receiving-yard intervals cross zero. These are nominal, unadjusted exposed-sample intervals: 500 PCG64 whole-cluster draws, week seed1911/game1912. Response rushing-yard absolute mean bias and median p95 worsen; receptions mean bias worsens slightly; receiving-yard mean bias and median p95 worsen. The recorded V2 gates pass **combined only**, as an exposed research lead; no operational readiness, selection, deployment or scientific qualification follows. A lower CRPS does not make its median the lowest point MAE.

The policy/direct/correction convention uses 500 PCG64 whole-week/game draws with seed1703; cached later correction pairs use1911/1912. H8 rushing efficiency uses separately adjusted nominal99.5% intervals from500 draws, both crossing zero. Do not combine these intervals or treat resamples as new games.

## Cohorts, coverage and clocks

- Main REG2022–24 panel: 815 games /54 season-week blocks. RB rush categories have6,235 offers,4,558 supported played labels,1,665 unknowns,12 played-missing,157 forecast fallbacks. RB/WR/TE reception/yard/combined categories have21,504 offers,15,251 supported labels,6,229 unknowns,24 played-missing,545 fallbacks. Known DNP is zero in this limited source qualification; that does not prove a complete NFL appearance/nonappearance panel. Supported played zeros and signed/negative yards remain category-specific.
- Original leaf-CDF panel includes postseason:854 games/66 weeks,4,801 rush-role or16,246 broad-skill scored rows. Its context rush-yard median MAE19.303895 and CRPS13.821810 cannot be called better than the later REG-only19.718956/14.096373 on changed rows.
- Initial campaign validation2024 uses6,214 broad all-skill played rows/22 weeks, including postseason, with many low/zero role-inappropriate outcomes. Its yard/count errors are not RB/receiver-specific current-panel errors. Development-selected validation methods and retrospective minima are both retained in the machine inventory.
- H8 rushing efficiency has its own4,591-row RB REG panel and explicit participation/source contract. The 2023–24 combined-law study has10,157 supported/14,282 offers over544 games/36 weeks; its lower numerical CRPS values must not be ranked against the three-year panel.
- W6 comparisons concern the retained2026 Week6/13-game archive, not current website forecasts. Original, expanded-coverage, CDF and later strict-positive/HGB/count source versions have different common masks. No error is transferred across their denominators.
- Training is earlier-only, normally2019..year−1 for2022–24; W6 reconstruction uses2019–25 and prior2026 weeks. Historical availability is current-vintage kickoff+7days reconstruction, not authenticated original publication/issuance. Corrected features admit known availability strictly before cutoff, order recent history by kickoff and mask unavailable participation-rate denominators. This audit opens no2025+ outcomes.

## Exact feature and preprocessing differences

The original/fixed category panels use30 numeric base features for rushing and combined yards,21 for receptions/receiving yards, plus21 fixed context features when that panel is declared. Exact feature names and modeled/primary roles are preserved in `method-configs.json`. `FixedDesign` fits numeric training medians (all-missing→0), appends missing indicators and training-only position one-hot levels; it does not fit preprocessing on queries or standardize those tree/HGB inputs. Initial ridge uses a different training-only median/SD design with clip[−8,8] and team/opponent/position categories. The correction context standardizes its three declared covariates separately.

The newer source packet excludes PFR snap inputs and leaves snap summaries disabled/missing, rather than asserting zero snaps. The later corrective study keeps the97-column schema while masking the unavailable participation-rate feature. No routes, injuries, scheme or original historical publication clocks are silently filled in. Source hashes and exact per-library booster parameters are in the machine-readable config inventory. These source changes prevent attributing every between-study error difference to the estimator alone.

## The whole-week method record

| Family | Executed result / reason it is separate or excluded from a current winner claim |
|---|---|
| Original H3 / rec-half | Receiving H3 MAE15.513290 vsSITE15.614538 on249 rows, but raw15.483695 is lower and tails/RMSE worsen. Same-receipt combined sum20.020267 vsSITE20.070107 on187 rows also loses raw19.815882. Generic reception ridge is not rec-half. Frozen rec-half stays raw+0.5×(adjusted−raw),2026Weeks7–14; no new confirmation is invented. |
| Original RB volume/share proposal | Five-prior-season/complete participation/absent-stat-zero gates remain unmet; no fitted prior, kappa selection or accuracy result. It is not the later generic Poisson or dynamic model. |
| Rushing H3/H8 efficiency | Held tree carries×pooled YPC; H8 MAE22.628778 vs pooled22.816821 (+0.824142%), but worse bias/p90 and both primary intervals cross zero.2,533 fallbacks/2,058 informed of4,591; original tree nodes unavailable. |
| Recent/pooled/workload | Shrunk3-game/8-game references and fixed workload×rate/share hypotheses; earlier mean priors and explicit missingness. Generic component mean sums are not joint medians. Full six-family source-matched benchmark retains all controls and aliases. |
| Initial ridge/tree/distributional/ensemble | Twelve frozen families/ablations; development2022–23 and validation2024 already exposed. Tree/ridge gains on broad skill rows do not transfer to RB/receiver masks; coherence/bias gates and iteration warnings remain. |
| NGS / public scheme and pace | Same ridge with28NGS or47scheme features on2023. Carries/rec NGS gains small; all11scheme primary losses worsen. Missing present-day inputs are not fabricated. |
| Empirical leaf CDF |32 depth8 trees/minleaf30,95%leaf empirical+5%full-support prior; mean and literal lower median distinct. Original all-period base/context results both retained; current source-matched base is the reference. |
| Direct W6 CDF / SITE blend | Two fixed panels and pure/50–50 point variants, mixed gains. Rush-yard blends improveSITE MAE11.26/11.61%; receiving blends2.89/3.13% with worse bias/RMSE. Different source cohort; no current-site gain. |
| Absolute-error HGB |150iterations/.05/depth3/15leaves/minleaf30/L2=10. WarmW6RBcarry points collapse tozero;MAE8.0435 vsSITE3.42565,134.80%worse. HistoricalRBcarry/rush-yard losses remain. New source plus learner cannot isolate algorithm effect. |
| Count A / role B | Poisson objective repairs zero collapse; A pooled, B role-specific, shared training-only design/priors. SignedA aliasesHGB; single-roleB aliasesA. Old numeric fallbacks are medians; mean-v2 is a separate corrected procedure. |
| Six direct boosters | XGB/LGB/Cat small64/depth3 ormedium128/depth5,learningrate.05,L2=10,2threads. CountPoisson/MSE and yard.5quantile/MAE, no numeric laws. Catmedium leads this skill subset of direct settings, yet rushCDF and receptionCountA are stronger controls. None passed original research nomination gates. |
| Two CDF corrections | Fixed intercept or7-column context, penalized count log-offset / signed median-offset.2022startupCDF aliases;2023uses2022OOF,2024uses2022+23. Failed fits retain frozen points. All44cached paired comparisons/132annual diagnostics remain, including weaker skill results. |
| Monotone thresholdCDF | Fixed-grid HGBclassifier, threshold-only monotonicity;60iterations/.05/15leaves/minleaf40/L2=10. Loses all11 primary proper-score comparisons and direct point minima. |
| CDF-response forest | Squared splits of sqrt(trapezoid weight)×1[Y≤grid],same32-tree topology, empirical law. Five skill CRPS minima, mixed secondary gates; exact DRF/MMD implementation is not claimed. |
| Weekly P0–P4 | P1last eligible week;P2season cumulative;P3earlier-only nested half-life{1,4}×margin{0,.005};P4fixed equal-weight shortlist with member-reference fallback. Point-heuristic frontier retained; no bootstrap policy reselection or full-CDF mixture. |
| Recorded prop thresholds |13already-frozen variants,604literal thresholds/585supported overall,one exposed week. Three-way direction errors are not over probabilities, returns, extra point validation or new models. |
| Conformal intervals | Fixed80% study2023–24,20radii allzero expansion;interval scores unchanged. It changes no point or CDF-probability ranking. |
| NGBoost / generic joint software | No completed NFL NGBoost accuracy screen in the audited records. Runtime/law fixtures and failed preparations are not fitted gains. Optional general joint sampler repair had no live caller or accuracy result. |
| Dynamic workload | smooth-H8-k25:8slots,half-life8,kappa25,hazard0;earlier roleprior/fixed volume;catch/YPT strength100. Carry/rec/recyd loseCDF4.22145%/2.28499%/3.36052%,bothintervals adverse. Auxiliary targetMSE+.38002%on5,599rows does not transfer to final targets;MAE/bias/p95worse.30frozen forecasts/12labels/30views complete, but sourceCPUfailure and gradingACKfalse/native absence/UNKNOWNwhole resources preserved. |
| Combined independent/copula sums |2023–24only;randomized discretePIT,rho=n/(n+100)×Pearson(normalPIT),4,096draws,2dependencefits/0basefits. Both CRPS14.788579/14.791580 lose direct14.788334; medianMAE20.775130/20.770306 lose direct20.753667 and Cat20.679706. More coherent sum does not establish better predictions. |

## Earlier supported minima are preserved

Initial broad-cohort2024 observed MAE minima: rush yards tree7.527142612; carries tree1.267490743; receptions ridge_without_team1.146986262; receiving yards ridge_without_team14.719962314; combined ridge_without_team19.681314086. The development-selected rec/combined methods were instead ridge_without_opponent, with1.149562954/19.698714894. Retrospective lower validation losses do not rewrite the development choices. These are separate broad/postseason cohorts and count-MAE points, not current count-mean MSE evidence.

## What is served, and what is ready

The root-supplied saved website observation identifies CDF rush yards; legacy Count A for carries/receptions; CatBoost medium for receiving/combined yards. Carries model1fa38b... and receptionsd0e206... share old procedureaf504c72.... The metadata labels them expected_mean/point_mean, but that does not repair the old median fallback or turn them into mean-v2. No future performance outcomes were read.

Root separately reports a newer corrected producer completed its capture/restore/export, while the website still serves the earlier feed. This audit has not independently queried that later deployment state. Research-tested, artifact-restorable, provisionally served and scientifically qualified are recorded separately. No ranking here instructs a deployment or imposes an inherited eight-week gate on the independently authorized provisional track.

## Deliverables and limits

- `skill-cells.json`:31 public aggregate sections with exact target-specific tables, annuals, paired deltas, coverage, bias/tails and intervals; large HGB subgroup tables omitted, no individual rows reconstructed.
- `named-frontiers.json`:375 named metric cells and69 separate cohort/target/objective minima. The three-year point and law frontiers are explicit; no cross-cohort tournament.
- `method-configs.json`:exact public hyperparameters, feature lists, source/training metadata and registrations;`recipes-and-gaps.json`:22family recipes,aliases,missingness,failures and readiness.
- `additional-family-metadata.json`:recorded threshold cells, weekly configurations, preserved rec-half/RB gates, NGBoost/joint metadata and original coherence diagnostics.
- `source-hashes.json`:92 source/report/config/code bindings;`current-served-metadata.json`:saved feed identity only. Private source rows, model weights, forecast factors and full continuation harness are not reproduced.

This is a bounded aggregate/source audit, not a fresh numerical reproduction of every historical experiment. Previously verified dynamic/joint outputs are reused; their privacy reviews are not rerun. No public full replay or raw-feed redistribution right is inferred. Missing outcomes, DNP, unknown participation, fallback and supported zeros remain separate. No result is a claim that the current website has already beaten its old forecast or that an unrun method is optimal.
