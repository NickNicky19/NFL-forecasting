**Audit navigation:** [main conclusions](README.md) · [original public evidence sources](SOURCE_MANIFEST.json). Collated compressed audit bundles and internal intermediate files are retained locally and are not included in this public publication. Named source-file and bundle-part references in the narrative describe those retained records; original public reports provide the underlying published evidence.

# Passing methods: full-week published-evidence audit

This is a source/configuration and published-aggregate audit of all five passing targets. No NFL row, player history, model body, protected outcome, new fit, scoring or HTTP was accessed. It adds no football evidence. Actual agent/model settings are UNATTESTED.

## Current champion and comparable point frontier

The current P2_SELECTED startup is LAB_CDF for all five passing targets: its law median for yards and law means for TD/CMP/ATT/INT. P2 is an earlier-evidence selector; its historical decision sequence differs from today's frozen startup. Current served model hashes/clocks and exact recipes are in RECIPES.json. No annual historical model is asserted to equal the exact current issued artifact.

The main comparable panel is primary-role QB REG2022–24: 1,960 supported outcomes from4,091 offers,815 games,54 season-week blocks. Both annual fitting and in-season features obey each study's earlier-only clock. All periods are exposed; authentic historical SITE/raw forecasts are unavailable. Supported zeros remain, unknown participation is not zero.

| Target | Current-family historical point loss | Lowest observed compatible point loss | Improvement | Product limitation |
|---|---:|---:|---:|---|
| pass_yd | 66.1617346939 | P4 66.1204485231 | +0.062402% | P4 arithmetic point heuristic; valid CDF median remains66.16173469 |
| pass_td | 1.0682416632 | distribution_split_cdf 1.0619745014 | +0.586680% | Mean/MSE; no selected-winner qualification |
| pass_cmp | 51.3753567567 | leaf_cdf 51.3753567567 | +0.000000% | Mean/MSE; no selected-winner qualification |
| pass_att | 114.2069376247 | P4 113.8757707477 | +0.289971% | P4 arithmetic mean point, not a predictive count law |
| pass_int | 0.6790663330 | distribution_split_cdf 0.6775664280 | +0.220878% | Mean/MSE; no selected-winner qualification |

These are minima in the inspected named set, with aliases retained but not counted as extra trials. P4 yardage is explicitly a point heuristic, not a mixture median. Its lower MAE is useful evidence for point accuracy and does not satisfy the present law-median contract. Passing-count P4 is an arithmetic mean-objective point blend; original member fallback semantics remain disclosed.

## Strongest leads, bias, tails and uncertainty

- **Passing yards:** P4 MAE66.12044852 vsCDF66.16173469 (+0.0624%). Bias−.291004 vs−.284184 (slightly worse),p95169.05454 vs174. Week CI[−.47735738,.36011787],game[−.39924164,.31569846]. No full law. Response median66.20306122 is worse; response mean-MSE is separately lower.
- **Passing TD:** response MSE1.061974501 vsCDF1.068241663 (+0.586680%). Week CI[−.01173831,−.00132306] and game[−.01152039,−.00099639] are both below0 in this exposed diagnostic. Against the stronger context correction1.062350396, the lead is only0.0353833%; both paired intervals include0. Bias worsens .0353651→.0682701 versus that stronger control; p95 improves1.9479428→1.9212898. It is not a confirmed selected winner.
- **Completions:** CDF mean51.37535676 remains the named minimum. Intercept51.40822167,response51.54021018,context51.65201367 and all six direct settings are higher. Response bias .219361 vsCDF.174540 andp9514.14483 vs14.13286 are also worse.
- **Attempts:** P4 MSE113.87577075 is below response113.90073106,intercept114.17545158,CDF114.20693762. P4 bias−.0174284 vsCDF+.4749922 andp9521.18429 vs21.68900 improve. Its week CI[−1.81899988,1.12481625],game[−1.84229727,1.07106965] include0. Response vsCDF +0.268116% has intervals including0 and worse absolute bias .504191 vs.474992; its gap to stronger intercept is0.240613%.
- **Interceptions:** response meanMSE.677566428 vsCDF.679066333 (+0.220878%); week[−.00417842,.00090849],game[−.00375114,.00128089] include0. Bias .011519 vs.012315 andp951.447898 vs1.462396 improve; CRPS slightly worsens.

All intervals above are published whole-cluster diagnostics on reused exposed outcomes. Different seeds/comparators are not substituted. No intervals were computed for retrospectively selected minima or cross-study winners here.

## Full-law CRPS is a different ranking

| Target | Lowest inspected valid-law CRPS | Fresh CDF CRPS | Response change vsCDF |
|---|---:|---:|---:|
| pass_yd | distribution_split_cdf 46.3777459895 | 46.4348924250 | +0.123068% |
| pass_td | distribution_split_cdf 0.5355739553 | 0.5372165863 | +0.305767% |
| pass_cmp | leaf_cdf 3.9543834528 | 3.9543834528 | -0.087895% |
| pass_att | distribution_split_cdf 5.7803155069 | 5.7914328268 | +0.191961% |
| pass_int | leaf_cdf 0.4033933976 | 0.4033933976 | -0.009674% |

Response CRPS gains for yards/TD/attempts do not establish successful advancement: bias/tail gates and annual behavior remain. For INT the lower response mean MSE coexists with worse CRPS. Count A/direct/P4/corrections provide points and no invented numeric law.

## Every main named setting

Losses below are yardage MAE or passing-count mean/intended-mean MSE. A dash is not an experiment or missing outcome filled with zero. Count A/role B legacy fallbacks and HGB point heuristics remain separately tagged in JSON.

| Study / method | pass_yd | pass_td | pass_cmp | pass_att | pass_int |
|---|---:|---:|---:|---:|---:|
| source_matched / leaf_cdf | 66.16173469 | 1.06824166 | 51.37535676 | 114.20693762 | 0.67906633 |
| source_matched / median_hgb | 67.21232333 | 1.22140669 | 53.40568576 | 117.80261792 | 1.08073782 |
| source_matched / count_A | 67.21232333 | 1.07586790 | 52.34181392 | 116.61481832 | 0.69193033 |
| source_matched / role_B | 67.21232333 | 1.07586790 | 52.34181392 | 116.61481832 | 0.69193033 |
| corrected_distribution_V2 / count_A_mean_v2 | — | 1.07829924 | 52.24684383 | 116.29355852 | 0.69100093 |
| six_direct / direct_xgboost_small | 71.03298274 | 1.08208573 | 53.31955899 | 117.50942793 | 0.67974329 |
| six_direct / direct_xgboost_medium | 68.01353996 | 1.07202235 | 52.80482701 | 117.58476031 | 0.69197410 |
| six_direct / direct_lightgbm_small | 66.65100556 | 1.08232651 | 53.31257751 | 117.87530267 | 0.67993010 |
| six_direct / direct_lightgbm_medium | 67.45280892 | 1.07138355 | 52.14003261 | 116.02132407 | 0.69250139 |
| six_direct / direct_catboost_small | 66.60262694 | 1.07403115 | 55.57918900 | 124.66186585 | 0.67934616 |
| six_direct / direct_catboost_medium | 66.62424219 | 1.09786758 | 52.71348329 | 115.62508141 | 0.70130158 |
| corrections / cdf_offset_intercept_v1 | 66.16173469 | 1.06778155 | 51.40822167 | 114.17545158 | 0.67917922 |
| corrections / cdf_offset_context_v1 | 66.16173469 | 1.06235040 | 51.65201367 | 114.94990933 | 0.67961718 |
| corrected_distribution_V2 / threshold_cdf | 66.95153061 | 1.07817869 | 53.37862725 | 116.87899778 | 0.68410868 |
| corrected_distribution_V2 / distribution_split_cdf | 66.20306122 | 1.06197450 | 51.54021018 | 113.90073106 | 0.67756643 |
| weekly_P0_P4 / P0 | 66.16173469 | 1.06824166 | 51.37535676 | 114.20693762 | 0.67906633 |
| weekly_P0_P4 / P1 | 66.66941236 | 1.07482469 | 51.74366340 | 113.96346761 | 0.69504557 |
| weekly_P0_P4 / P2 | 66.21615902 | 1.07220331 | 51.64478443 | 114.05014961 | 0.68075325 |
| weekly_P0_P4 / P3 | 66.28498609 | 1.07018054 | 51.86699400 | 114.28940566 | 0.68013198 |
| weekly_P0_P4 / P4 | 66.12044852 | 1.07156786 | 51.49733703 | 113.87577075 | 0.68345850 |

Count A legacy→mean-correctedV2 MSE: TD1.07586790→1.07829924; CMP52.34181392→52.24684383; ATT116.61481832→116.29355852; INT.69193033→.69100093. This changes a procedure/fallback, not an old frozen forecast. RoleB is an exactQB CountA alias; passing-yard CountA/roleB alias HGB. Current served CountA in other categories is still old frozen output; a corrected producer is not an automatic website replacement.

## Earlier panels: retain their actual gains and exclusions

- **Original/Week6:** H3 passing yards MAE45.20560313 vsoriginal SITE56.62296296 and published W6 CDF base51.74074074/context48.77777778. Both records report37offers/27supported QBs and identical named control aggregates, but this audit did not read paired row identifiers or create a new H3–CDF interval. H3 RMSE66.82259 is worse than CDF context60.04720; bias−24.07282 vs−22.11111 is worse. Original runner/history/availability qualification remains incomplete. Original attempts had mixed MAE/MSE results and a failed all-missing application; missing coefficients are not recreated by the generic workload model.
- **Initial campaign:** all12method names are inventoried: recent,pooled,raw_sleeper,pinned_website,workload,ridge,tree,distributional,ensemble and three ridge feature ablations. Broad all-skill/postseason2022–23development/2024validation contains many non-QB passing zeros; tree was the validation primary-MAE minimum for allfivepassing targets. Those tiny all-role errors are not typical-QB/currentpanel errors. Historical raw/SITE slots without authentic archives remain unavailable.
- **NGS/scheme:** fixed ridge +28NGS features and +47scheme/pace features were separately evaluated on broad2023population. NGS yardage improvement was tiny; scheme worsened all11supported targets. No passing production gain is inferred.
- **Historical H3/H8:** held tree attempts and commonH8 history gate on1960QB REG rows: H3MAE76.72678,H8 74.45225,pooled73.54578. Both lose pooled; current97-feature CDF result is another source/population contract.
- **Legacy854gameCDF:** base/context plus same-law means/medians/CRPS are separate. HGB/source changes and eligibility revisions prevent combining those old2049QB/postseason rows with the later1960REG panel. HGB/context and Count/Role aliases retain all adverse controls; their counts were originally primary-MAE points, not today's mean-MSE claim.
- **Recorded-threshold subset:** all13named point procedures are retained on the literal eligible-line mask (often26rather than27QBs). Its lower MAE/direction scores are not whole-cohort or probability/financial gains.
- **CQR:** all20radii across10numeric targets selected0; passing intervals and point/CDF products unchanged.
- **Untested/nonpassing families:** no completed passing NGBoost or learned full-CDF stack is established. Software or source/schema checks do not mean those families lost. The latest completed negative workload acceptance supplied separately by root is a nonpassing study; it does not update passing scores or justify stale globalpartial claims.

## Recipes, files and readiness

RECIPES.json contains exact category38base/59context feature names, the approved97column/source identities, complete native settings, correction chronology, threshold grids/source hashes, earlier prior/ensemble formulas and current issued model/procedure hashes. FixedDesign uses training-only column medians, missing indicators and role one-hot; initial ridge/tree pipeline uses its separate training standardization/category design. Unknown/DNP/missing/played-zero and fallback counts remain separate in each source record.

Each pass_*.json contains every extracted metric record for that target, within-panel/product minima, main named frontier, source path+JSON pointer and references to all published paired comparisons. PUBLISHED-ANNUAL.json preserves three-year candidate/correction/direct/original-control aggregate diagnostics. No aggregate arithmetic recovers unseen player-level pairing or actual historical publication.

No alternative is scientifically or operationally promoted by this audit. Exposed numerical leads can guide separately authorized provisional engineering without pretending to satisfy old scientific confirmation; exact current inference/source/artifact restoration, same-cutoff durability and consumer/fallback acceptance remain the implementation owner's job. No production change, dispatch, fit, model load, source acquisition or outcome scoring occurred.
