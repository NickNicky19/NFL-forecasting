# Matched twelve-category comparison — 2026 Weeks 1–7

**Current-season point/P1 comparison and 24-law replay completed; historical same-finalist extensions and owner release remain unfinished.** This is exposed historical development, with current-vintage inputs and the preserved seven-day availability assumption. These are not forecasts originally issued before these games.

## Current-season category decisions

MAE means the average absolute miss, in yards, counts or chart points. The Over/Under columns below belong to the listed **point leader**, using its unrounded point against the original recorded line. Rushing MAE is on the prespecified RB population; the offering-board side counts include supported QB rushing and registered fallbacks as well, so they are a different population. They are statistical direction counts on the supported offered subset, not venue-settled returns. The numerical-MAE population is broader.

| Category | Lowest observed point procedure | MAE / probability loss | Scored player-games | Lower MAE versus base CDF | Its Over correct/decided | Its Under correct/decided | Current served family/product |
|---|---|---:|---:|---:|---:|---:|---|
| Passing yards | LEAF_CDF / median | 62.9544 | 241 | 0.000% | 39/67 (58.2%) | 38/76 (50.0%) | LAB_CDF intended_median |
| Passing TDs | HGB_MAE_DIRECT / mae_objective_point | 0.7864 | 241 | 1.286% | 24/40 (60.0%) | 59/102 (57.8%) | LAB_CDF expected_mean |
| Completions | RESPONSE_CDF / median | 5.1743 | 241 | 0.558% | 37/61 (60.7%) | 38/83 (45.8%) | LAB_CDF expected_mean |
| Passing attempts | RESPONSE_CDF / median | 7.7759 | 241 | 0.689% | 20/40 (50.0%) | 47/103 (45.6%) | LAB_CDF expected_mean |
| Interceptions | LEAF_CDF / RESPONSE_CDF median tie; side counts shown for LEAF_CDF | 0.5892 | 241 | 0.000% | 4/5 (80.0%) | 65/138 (47.1%) | LAB_CDF expected_mean |
| Rushing yards (RB) | RESPONSE_CDF / median | 19.4608 | 586 | 0.061% | 57/114 (50.0%) | 197/329 (59.9%) | LAB_CDF intended_median |
| Carries (RB) | BACKFIELD_CDF / median | 3.6280 | 586 | 3.451% | 44/88 (50.0%) | 120/239 (50.2%) | COUNT_A expected_mean |
| Receptions | ORDERED_CDF / median | 1.2800 | 2000 | 0.117% | 154/255 (60.4%) | 366/662 (55.3%) | COUNT_A expected_mean |
| Receiving yards | RESPONSE_CDF / median | 16.7850 | 2000 | 0.098% | 166/308 (53.9%) | 327/621 (52.7%) | CATBOOST_MEDIUM intended_median |
| Rushing + receiving yards | LEAF_CDF / median | 20.8600 | 2000 | 0.000% | 73/148 (49.3%) | 168/320 (52.5%) | CATBOOST_MEDIUM intended_median |
| Anytime rushing/receiving TD | EQUAL_CDF_CAT_PROBABILITY / probability | Brier 0.145766 | 2000 | Separate probability objective | Unavailable | Unavailable | LAB_CDF/CATBOOST_MEDIUM event_probability |
| Chart PPR | RESPONSE_CDF / median | 4.6404 | 2241 | 0.464% | Unavailable | Unavailable | Legacy fallback; chart not active |

The clearest numeric difference is carries: 3.628 versus 3.758, a 0.1297-carry decrease. Its paired game-cluster interval is approximately −0.1993 to −0.0652 carries; week-cluster interval −0.1741 to −0.0898. Most other leads are tiny and their paired intervals cross zero. Chart response-CDF improves by 0.0216 points on this panel. All periods have been inspected; the shortlist and output choice introduce selection uncertainty. These are comparisons with the named laboratory CDF, **not proven percentage gains over the actual live website**.

## Five procedures per category and every output

[Ranked numeric procedure shortlist](RESEARCH_POINT_PROCEDURE_RANKING_W1_7.csv) · [All point products, errors, bias, tails, coverage and paired uncertainty](POINT_PRODUCTS_W1_7.csv) · [Every method/output’s own Over/Under record](EACH_POINT_PRODUCTS_OWN_OVER_UNDER_W1_7.csv) · [Weekly own-side records](EACH_POINT_PRODUCTS_OWN_OVER_UNDER_BY_WEEK.csv.gz) · [Complete immutable main aggregates](ALL_FINALISTS_AGGREGATES_V1.json.gz).

| Category | Five meaningful procedure groups (point-MAE order; output variants share one group) |
|---|---|
| Passing yards | LEAF_CDF, RESPONSE_CDF, EQUAL_CDF_CAT_HGB_POINT, HGB_MAE_DIRECT, CATBOOST_MEDIUM |
| Passing TDs | HGB_MAE_DIRECT, LEAF_CDF, RESPONSE_CDF, COUNT_A_LEGACY_POINT, CATBOOST_MEDIUM |
| Completions | RESPONSE_CDF, LEAF_CDF, CATBOOST_MEDIUM, COUNT_A_LEGACY_POINT, HGB_MAE_DIRECT |
| Passing attempts | RESPONSE_CDF, LEAF_CDF, HGB_MAE_DIRECT, COUNT_A_LEGACY_POINT, CATBOOST_MEDIUM |
| Interceptions | LEAF_CDF, RESPONSE_CDF, HGB_MAE_DIRECT, COUNT_A_LEGACY_POINT, CATBOOST_MEDIUM |
| Rushing yards (RB) | RESPONSE_CDF, LEAF_CDF, EQUAL_CDF_CAT_HGB_POINT, CATBOOST_MEDIUM, HGB_MAE_DIRECT |
| Carries (RB) | BACKFIELD_CDF, ORDERED_CDF, LEAF_CDF, COUNT_A_LEGACY_POINT, CATBOOST_MEDIUM |
| Receptions | ORDERED_CDF, LEAF_CDF, HGB_MAE_DIRECT, COUNT_A_LEGACY_POINT, CATBOOST_MEDIUM |
| Receiving yards | RESPONSE_CDF, LEAF_CDF, EQUAL_CDF_CAT_HGB_POINT, CATBOOST_MEDIUM, HGB_MAE_DIRECT |
| Rushing + receiving yards | LEAF_CDF, RESPONSE_CDF, EQUAL_CDF_CAT_HGB_POINT, CATBOOST_MEDIUM, HGB_MAE_DIRECT |
| Anytime rushing/receiving TD | Normalized leaf CDF, CatBoost binary, Equal CDF/CatBoost probability blend, Role logistic, Retained Platt curve — late entrant, separate appendix |
| Chart PPR | RESPONSE_CDF, CATBOOST_MEDIUM, CHART_LEAF_CDF, CHART_HGB, CHART_ROLE_LAW |

Legacy Count A empirical points and corrected stored means remain separate outputs of the same family. The yardage three-way point blend is the declared equal CDF/CatBoost/HGB recipe, not an old P4 recipe or the median of a mixture distribution. Response-CDF, ordered CDF and backfield CDF have distinct procedure/source bindings. The depth passing-attempt comparator has only Weeks 1–6 and remains a secondary partial record; it does not shrink the full Weeks 1–7 headline core.

## Mean, law, probability and selection products

Mean MSE/RMSE leaders are retained separately in the release manifest; they are not automatically the means of the displayed model. Valid saved laws provide CRPS, threshold probabilities, pushes and direct log-tail loss. Count A/CatBoost point objectives do not create an assumed PMF. Numeric threshold Brier uses one-half of the sum over Under/Push/Over outcomes; conditional market comparisons use a separate binary score. Anytime TD retains Brier as primary.

Full board, Top 6/10/20, confidence-abstaining, always-side, disagreement and paired game/week-aware comparisons are retained. Own Over rates compare different selected subsets; a 4/5 result is not stronger evidence than a much larger sample. The highest retrospective Over and Under performers are never spliced into a historical strategy. Original website recommendations remain in [their separate immutable report](../category-topfive-original-leans-release-ou-20261030/README.md).

## Scope, labels and coverage

All 107 scheduled games are represented (16/16/16/16/15/14/14); 4,985 qualified roster queries were attempted and 502 source identity rows quarantined. Full finalist grading materialized 283,673 product rows, with 188 missing depth outputs; these are repeated procedure/product incidences. There were 124,110 supported scored incidences in the primary-role population, not that many independent football games.

The exact outcome version contains 43,470 target-label opportunities including forecast-only targets. Passing labels support 241 played QB cases of 718 queried; RB rushing supports 586 of 1,244; receiving/ATD supports 2,000 of 4,267; chart supports 2,241 of 4,985. Unknown participation stays unknown, never zero or DNP. The source-qualified chart uses signed official yards and all sixteen specified primitives. Week 8 outcomes were not admitted. Full system missingness and fallback counts appear alongside the common supported core.

The recorded board has 3,998 unique primary lines: 2,705 in Weeks 1–5, 676 in Week 6 and 617 in Week 7. Quote clocks and venue participation/settlement rules remain unqualified. Statistical direction can be scored; authenticated historical execution cannot be claimed. Targets and chart have no qualified actual offers. Anytime TD is a separate event target.

## Market evidence and limits

The archive contains 2,642 valid same-book/same-line two-sided price pairs, only in Weeks 1–5. An independent-book, same-naive-collection-clock reference supports 1,068 opportunities before outcome qualification. Offering-book exclusion is preserved. No historical quote clock, original cutoff or settlement contract is established. Week 6–7 lines have no prices; ATD Yes prices do not identify fair No probabilities. No −110 defaults, manufactured offers, EV/ROI or profitability claims are used. The fixed-half hybrid and line-as-point heuristic are exploratory and reported separately.

## What actually ran and was checked

Twenty-five successful new fitted models were saved: nine HGB, thirteen missing fixed Count A/CatBoost/response cells and three chart/event models. Two chart/event resource failures remain visible; the failed response and logistic cells were retried in isolated fresh processes without rerunning the successful CatBoost. Retained-model restorations, 283,485 frozen output rows, later materialized missing rows, scoring runs and NFL outcomes are distinct counts.

Independent grading checked the main point/side arithmetic and all 24 cached law packages. Law QA covered 77,594 distribution rows, 16,892 line-probability records and 308 policy records; only sixteen outcome-blind query slots were independently re-inferred, with nine supported CRPS outcomes. This is not complete independent re-inference of every vector. [Main QA](primary-scoring/INDEPENDENT_FRESH_QA_ALL_FINALISTS_V1.json) · [Law QA](law-qa/ACTUAL_INDEPENDENT_QA_V1.json).

[Readable private scorecard receipt](READABLE_PRIVATE_SCORECARD_V1.json): 204,431 prediction/actual CSV rows and 258,748 line/direction CSV rows, exact ZIP readback. These remain restricted private evidence; approved owner restoration is required. No player-level raw data are placed in this public repository.

## Historical seasons and training histories

Current models generally use earlier multiseason training through 2025; chart models use admitted 2024 chart labels. Best on 2026 does not mean trained only on 2026. The old 2025 ordered-history and 2022–2024 benchmarks remain intact, including negative findings. Their populations, source timing and feature treatment can differ from this repaired panel. They are not silently copied into a matched same-finalist tournament. Missing same-contract historical cells and clean H-CURRENT/H-RECENT/H-MULTI cells remain unfinished; no through-2025 model is applied to its own 2025 outcomes as out-of-sample evidence.

## Production, capture and exact remaining owner action

**This session is research-only.** Website Main remains `1ec93e068a91abd51c990937d1019e4a831694b4`; no later owner acknowledgement was returned by the October 31, 10:00 a.m. CDT read. The served payload SHA is `369fec9caec012cb292284006a60bb25727d6d9d853f00560dbffe57f1ea1fa4`: 1,945 forecasts issued October 28, zero new MAE-profile rows. A fresh 10:00 a.m. CDT check also executed the exact served JavaScript consumer and matched all 1,945 saved values and labels; browser DOM was not visually observed. [Fresh consumer readback](LIVE_CONSUMER_READBACK_V2.json) · [Category release manifest](CATEGORY_RELEASE_MANIFEST_V2.json.gz). The exact live family/procedure/model bindings are recorded; chart PPR is not active. Live COUNT_A entries identify the served family and mean-labeled product; the serving wrapper has not been asserted identical to the laboratory corrected-mean recipe.

The retained owner holds lease 178. The ready release package at commit `341742de83975264a07d035d4b6289e57c2ec1e9` has verified delivery; owner acknowledgement and execution remain unverified. It must restore parent `40729788942` / child `40729906573`, authenticate SOURCE/query-completion/feature-capture receipts and actual model/wrapper/slot bindings, admit separately typed selected_projection while preserving independent means/probabilities, perform current-query inference, immutable persistence, fallback/rollback and publish/read back the actual consumer. Newly tested response, ordered/backfield, target and chart adapters retain their own guards. Ready older core products do not wait for this new research package.

The **October 31, 7:36–7:57 a.m. CDT** parent window has elapsed. A 10:00 a.m. CDT read found no newer public parent execution; latest remains failed `41104520104`. Classify this public window MISSED_NO_OBSERVED_PUBLIC_EXECUTION, while private per-method capture remains unverified until owner census restoration. Next remaining Sunday T−90: **November 1, 10:30 a.m. CST**. This future configured deadline is not completed capture. The last inspected parent `41104520104` failed with capture enqueue skipped. Original assignments and the per-method Week 8 census still require approved owner-controlled restoration. No capture was backdated and no older issue time was replaced.

## Reproducible records and next executable work

[Registration](EXECUTION_PROTOCOL_V1.json) · [Finalist/source amendments](FINALIST_AMENDMENTS_V1_1.json) · [Population/contracts](POPULATION_AND_PRODUCT_AMENDMENTS_V1.json) · [Canonical project index](../opportunity-four/README.md). Source configurations, models, source snapshots and full row vectors stay in the approved managed store; public code, aggregate scores and safe hashes provide the evidence index. Local-only artifacts remain PUBLICATION_PENDING until exact remote readback. Original caps, exhausted allocations, failures, losing weeks and scientific registrations are preserved. Lossless metadata compression stayed within the same accounting; no unique source/model/vector was discarded.

The late ATD supplement and exploratory M/H independent check are complete. Publish every result with remote readback; complete compatible historical cells under finite registrations; continue the four-category information backlog independently of owner-only release. No probability or EV ranking is activated solely from lower point MAE.

## Highest observed point-direction side rates — separate selected subsets

These are descriptive maximums among the full-seven-week eligible outputs. Each method’s complete decision rule and all contrary rows remain in the full table. Tiny interception samples are visibly weak evidence; these maxima are not a stitched selection strategy.

| Category | Highest observed Over point rule | Correct / decided | Highest observed Under point rule | Correct / decided |
|---|---|---:|---|---:|
| pass_att | COUNT_A_LEGACY_POINT / legacy_empirical_point | 19/35 (54.3%) | COUNT_A_LEGACY_POINT / legacy_empirical_point | 51/108 (47.2%) |
| pass_cmp | CATBOOST_MEDIUM / mean_objective_point | 35/53 (66.0%) | CATBOOST_MEDIUM / mean_objective_point | 44/91 (48.4%) |
| pass_int | LEAF_CDF / median | 4/5 (80.0%) | LEAF_CDF / mean | 8/10 (80.0%) |
| pass_td | LEAF_CDF / median | 27/44 (61.4%) | COUNT_A_LEGACY_POINT / legacy_empirical_point | 44/68 (64.7%) |
| pass_yd | LEAF_CDF / mean | 36/61 (59.0%) | HGB_MAE_DIRECT / mae_objective_point | 37/73 (50.7%) |
| rec | ORDERED_CDF / median | 154/255 (60.4%) | ORDERED_CDF / mean | 271/481 (56.3%) |
| rec_yd | CATBOOST_MEDIUM / median_objective_point | 171/317 (53.9%) | RESPONSE_CDF / mean | 201/363 (55.4%) |
| rush_att | BACKFIELD_CDF / mean | 70/130 (53.8%) | BACKFIELD_CDF / mean | 104/197 (52.8%) |
| rush_rec_yd | RESPONSE_CDF / mean | 117/230 (50.9%) | RESPONSE_CDF / mean | 130/238 (54.6%) |
| rush_yd | LEAF_CDF / median | 58/110 (52.7%) | EQUAL_CDF_CAT_HGB_POINT / empirical_point_blend | 199/327 (60.9%) |

## Probability and complete-rule results

[Every full law](probability-projection/DISTRIBUTION_PRODUCTS_W1_7.csv.gz) · [Every supported threshold/ATD probability product](probability-projection/PROBABILITY_PRODUCTS_W1_7.csv.gz) · [Full-board, Top6/10/20 and abstaining football selection rules](probability-projection/FOOTBALL_PROBABILITY_SELECTIONS_W1_7.csv.gz) · [Matched market/hybrid policies](probability-projection/EXPLORATORY_MARKET_SELECTIONS_W1_7.csv.gz) · [Paired market Brier differences](probability-projection/EXPLORATORY_MARKET_PAIRED_BRIER_W1_7.csv.gz) · [Line-as-point heuristic](probability-projection/LINE_AS_POINT_HEURISTIC_W1_7.csv.gz). TopN is prespecified per category/week, not an asserted reproduction of the website’s overall multi-category Top Picks.

| Category | Full-law CRPS leader | Raw football threshold Brier leader | Best fixed-shrink threshold Brier | Highest full-board football decision result |
|---|---|---|---|---|
| chart_ppr | RESPONSE_CDF: 3.281089 | Unavailable | Unavailable | No numeric offers |
| pass_att | RESPONSE_CDF: 5.555103 | LEAF_CDF: 0.263985 | LEAF_CDF: 0.254173 | LEAF_CDF: 68/143 (47.6%) |
| pass_cmp | RESPONSE_CDF: 3.688927 | LEAF_CDF: 0.256732 | LEAF_CDF: 0.250857 | RESPONSE_CDF: 75/144 (52.1%) |
| pass_int | LEAF_CDF: 0.360168 | LEAF_CDF: 0.247501 | LEAF_CDF: 0.247725 | LEAF_CDF: 69/143 (48.3%) |
| pass_td | LEAF_CDF: 0.571764 | LEAF_CDF: 0.240694 | LEAF_CDF: 0.240309 | LEAF_CDF: 85/142 (59.9%) |
| pass_yd | LEAF_CDF: 44.860151 | LEAF_CDF: 0.257921 | LEAF_CDF: 0.250778 | LEAF_CDF: 77/143 (53.8%) |
| rec | ORDERED_CDF: 0.917611 | ORDERED_CDF: 0.258155 | ORDERED_CDF: 0.246598 | LEAF_CDF: 521/917 (56.8%) |
| rec_yd | LEAF_CDF: 12.005365 | LEAF_CDF: 0.263184 | LEAF_CDF: 0.250944 | RESPONSE_CDF: 493/929 (53.1%) |
| rush_att | BACKFIELD_CDF: 2.560732 | BACKFIELD_CDF: 0.264806 | BACKFIELD_CDF: 0.248118 | ORDERED_CDF: 169/327 (51.7%) |
| rush_rec_yd | LEAF_CDF: 14.788712 | LEAF_CDF: 0.269162 | LEAF_CDF: 0.252539 | RESPONSE_CDF: 243/468 (51.9%) |
| rush_yd | LEAF_CDF: 13.707890 | LEAF_CDF: 0.255676 | LEAF_CDF: 0.245241 | LEAF_CDF: 260/443 (58.7%) |
| anytime_td | Unavailable | Unavailable | Unavailable | No numeric offers |

The independent market QA checked 33,418 probability rows, 233,926 selection flags and 12,320 cumulative/weekly policy records without rerunning fitting, inference or bootstrap intervals. On matched available price rows, reception football Brier 0.262294 became 0.249144 under the fixed-half hybrid, while simple shrinkage was lower at 0.248383. For passing attempts, football 0.242228 was lower than hybrid 0.242392 and market 0.246809. For carries, hybrid 0.244868 narrowly beat shrinkage 0.245065 on only 94 scored offers. These are timing-unverified conditional probability comparisons, not authentic execution, ROI or a universal market advantage.

## Recovered historical context, not newly executed fits

The completed 2025 ordered comparison remains reusable: carry MAE 3.408685 base versus 3.340358 ordered on 1,566 outcomes; receptions 1.178659 versus 1.173182 on 5,295. The separately completed 2025 passing-attempt common-learner history study used 52 prior fits, 664 supported QB cases and all 18 weeks. Prior-plus-current had lowest MSE 120.305733; fixed-365-day decay had lowest MAE 8.573752 among its history arms. These were already completed results, not new fits in this checkpoint or matched repaired-2026 gains. The exact compatibility/gap audit is retained in the execution evidence archive. Full same-finalist older-season coverage and the fixed-current-2026 three-history tournament remain incomplete.

## Completed fifth anytime-TD contender — late appendix

The earlier accepted Platt curve was restored without refitting and applied as a separately named late contender. Its original 2022–2023 training acceptance was authenticated, not independently reproduced. The first cached grading run hit its 120-CPU-second cap after saving the complete scores; that failure remains. A separate 80.44-CPU-second post-retention admission authenticated the saved artifacts and independently checked all scores, weekly counts and unchanged original controls without rerunning scoring, inference or bootstrap. [Admission receipt](fitting/ACTUAL_ATD_POSTRETENTION_ADMISSION_V1.json) · [Complete late appendix](ATD_LATE_AGGREGATES_V1.json.gz).

| Meaningful procedure | Brier (2,000 identical supported cases) | Log loss |
|---|---:|---:|
| EQUAL_CDF_CAT_PROBABILITY | 0.145765931 | 0.456502080 |
| CATBOOST_MEDIUM | 0.145838864 | 0.456937852 |
| LEAF_CDF | 0.145998085 | 0.457045103 |
| ATD_CDF_RETAINED_PLATT_NLL_IDENTITY01 | 0.146490971 | 0.458665019 |
| ROLE_LOGISTIC | 0.146818014 | 0.460794879 |

The equal CDF/CatBoost blend remained lowest. Both role logistic and the late retained Platt curve lost. Five meaningful procedures now have current-panel probability scores, but the fifth was not part of the original global freeze and has no retroactive pregame history. No probability release or website change followed from this appendix.

## Permanent run/result index

[Safe execution evidence archive](EXECUTION_EVIDENCE_V2.zip) preserves each public-safe receipt, failure, configuration contract, correction and historical compatibility audit under its original relative path, including `ALL12_RUN_RESULTS_INDEX_V2.json.gz`. Large immutable point/law/market/ATD aggregates are separate files; private rows and model artifacts remain private. Index publication is complete only after the exact commit/tree/body remote readback receipt.

[Weekly point/mean/event errors and full operational coverage for every output](WEEKLY_POINT_PRODUCTS_W1_7.csv) directly projects already-completed per-week aggregates. It retains partial depth eligibility, unknowns, fallbacks, zeros and product labels. Weighted weekly MAEs reproduce the cumulative figures. No model was refitted or rescored. Missing metrics remain empty with reasons.

## Constant 50/50 probability control — actual matched completion

[Control comparison](probability-projection/FLAT50_COMPARISON_V1.json) · [Complete control aggregates](FLAT50_AGGREGATES_V1.json.gz). The same recorded board contains 3,998 within-query offers; 3,738 belong to the numeric primary roles. Prop-board results use all actual offered roles, including supported QB rushing. The control’s Brier was exactly 0.25 on supported rows; no observed pushes occurred. Integer-push handling was still preserved and checked. The probability-only control always abstains from selecting a side.

| Category | Supported offered cases | Best tested football/shrink Brier | 50/50 Brier | Lower observed loss |
|---|---:|---:|---:|---|
| pass_att | 143 | 0.254173 (LEAF_CDF/SHRINK_0_5) | 0.25 | FLAT_50_CONTROL_ABSTAIN |
| pass_cmp | 144 | 0.250857 (LEAF_CDF/SHRINK_0_5) | 0.25 | FLAT_50_CONTROL_ABSTAIN |
| pass_int | 143 | 0.247501 (LEAF_CDF/FOOTBALL) | 0.25 | LEAF_CDF/FOOTBALL |
| pass_td | 142 | 0.240309 (LEAF_CDF/SHRINK_0_5) | 0.25 | LEAF_CDF/SHRINK_0_5 |
| pass_yd | 143 | 0.250778 (LEAF_CDF/SHRINK_0_5) | 0.25 | FLAT_50_CONTROL_ABSTAIN |
| rec | 917 | 0.246598 (ORDERED_CDF/SHRINK_0_5) | 0.25 | ORDERED_CDF/SHRINK_0_5 |
| rec_yd | 929 | 0.250944 (LEAF_CDF/SHRINK_0_5) | 0.25 | FLAT_50_CONTROL_ABSTAIN |
| rush_att | 327 | 0.248118 (BACKFIELD_CDF/SHRINK_0_5) | 0.25 | BACKFIELD_CDF/SHRINK_0_5 |
| rush_rec_yd | 468 | 0.252539 (LEAF_CDF/SHRINK_0_5) | 0.25 | FLAT_50_CONTROL_ABSTAIN |
| rush_yd | 443 | 0.245241 (LEAF_CDF/SHRINK_0_5) | 0.25 | LEAF_CDF/SHRINK_0_5 |

Thus model/shrink probabilities did not beat a 50/50 control for passing yards, completions, passing attempts, receiving yards or combined yards on this full offered panel. This prevents describing their relative model lead as demonstrated probability skill. Do not activate confident probability/EV rankings from those point-MAE results. Other categories’ modest observed probability gains remain exposed development evidence, with uncertainty and timing limits.

## Descriptive weekly leaders

[Week-by-week lowest observed errors](WEEKLY_OBSERVED_LEADERS_V1.csv) lists all twelve categories over Weeks 1–7, using the same frozen role populations and supported output definitions. It includes sample sizes and exact products. These are hindsight weekly winners, not forecasts of which method would win, not the policy’s actual advance choices and not a deployable weekly switching backtest. Tied minima remain tied numerically; the CSV uses a deterministic method-name tie display.

## Complete selection rules at comparable coverage

[Full policy comparison](probability-projection/COMPLETE_POLICY_COMPARISON_V1.md) compares 556 already-scored point/probability/control policy products and preserves 121 equal-capacity groups. On this full offered board, Always-Over beat the fitted selectors for passing attempts and completions. Count A mean had 87/142 correct passing-TD decisions; backfield CDF mean 174/327 carries; leaf-CDF median 521/917 receptions. These are descriptive exposed-data maxima, including ties, unresolved rows and registered fallbacks—not an earlier-trained switching rule. Top 6/10/20, abstention and each method’s own sides remain separate; equal capacity is not identical selected players.

The first 2025 proper-score extension stopped before labels because a restored BASE mean did not match the saved point bit-for-bit. Its 78.75-CPU-second failure, 2,079 produced-but-unretained new replay rows and original intact artifacts are recorded. Source inspection found a changed inference batch shape and an incorrect check against old unavailable optional-product placeholders. The separately versioned continuation below restored the exact original batching and saved every replay before checking. No old study was erased or declared invalid from the first failure, and no target outcomes were used to choose a numerical tolerance. The successful continuation is a new traceable result, not a relabeling of that failure.

## Completed 2025 BASE/ORDERED distribution comparison

The corrected continuation completed with strict original mean/median/fallback replay parity, two retained BASE restorations and no refitting. It reused original ORDERED proper-score vectors. Across 272 games and all eighteen 2025 regular-season weeks:

| Category | Supported primary cases | BASE CRPS | ORDERED CRPS | Relative lower CRPS | Game-cluster paired difference interval |
|---|---:|---:|---:|---:|---|
| rush_att | 1566 | 2.426268791 | 2.405966952 | 0.837% | [-0.033983, -0.005052] |
| rec | 5295 | 0.838962759 | 0.836145149 | 0.336% | [-0.004682, -0.000955] |

NLL reductions were smaller, with paired intervals crossing zero. Week-cluster and two-target adjustment diagnostics are retained in the full aggregate. This is exposed, current-vintage historical development under the original seven-day and participation limitations, not a new label repair or proof against website forecasts. The 9,350 primary query memberships include 6,861 supported outcomes; 34,804 actual full-context query passes were necessary to reproduce the original batching. Previously unavailable optional products were not relabeled as originals. [Actual execution](historical-2025-proper-gap/ACTUAL_EXECUTION_V2.json). The first failed attempt remains unchanged.

[Full new 2025 proper-score results and every weekly gain/loss](HISTORICAL_2025_BASE_ORDERED_PROPER_AGGREGATES_V2.json.gz) preserve the exact original BASE bit-parity diagnostics, source/model identities, both target uncertainty intervals and unknown/fallback coverage. These remain separate from the 2026 label-repaired panel.

## Paired uncertainty against the strongest alternative

[All 23 strongest-control comparisons](STRONGEST_CONTROL_PAIRS_AGGREGATES_V1.json.gz) reuse frozen original vectors: eleven point-MAE pairs, eleven compatible mean-MSE pairs and the ATD blend against CatBoost. No model or prediction was regenerated. These controls are the strongest alternative procedure groups on the declared core, with nominal game/week-aware intervals and development-selection limits.

| Category | Point leader | Next-best procedure | Lower average absolute miss | Game-cluster interval for leader minus control |
|---|---|---|---:|---|
| chart_ppr | RESPONSE_CDF/median | CATBOOST_MEDIUM/median_objective_point | 0.018439 | [-0.053260, 0.016141] |
| pass_att | RESPONSE_CDF/median | LEAF_CDF/median | 0.053942 | [-0.139835, 0.033065] |
| pass_cmp | RESPONSE_CDF/median | LEAF_CDF/median | 0.029046 | [-0.104173, 0.042923] |
| pass_int | LEAF_CDF/median | RESPONSE_CDF/median | -0.000000 | [-0.032660, 0.032524] |
| pass_td | HGB_MAE_DIRECT/mae_objective_point | LEAF_CDF/median | 0.010243 | [-0.047180, 0.024335] |
| pass_yd | LEAF_CDF/median | RESPONSE_CDF/median | 0.302905 | [-1.050624, 0.370941] |
| rec | ORDERED_CDF/median | LEAF_CDF/median | 0.001500 | [-0.013180, 0.009695] |
| rec_yd | RESPONSE_CDF/median | LEAF_CDF/median | 0.016500 | [-0.063600, 0.029182] |
| rush_att | BACKFIELD_CDF/median | ORDERED_CDF/median | 0.087031 | [-0.148411, -0.022647] |
| rush_rec_yd | LEAF_CDF/median | RESPONSE_CDF/median | 0.003000 | [-0.075480, 0.066538] |
| rush_yd | RESPONSE_CDF/median | LEAF_CDF/median | 0.011945 | [-0.128673, 0.109643] |

Carries improve 2.343% versus the stronger ordered-history control (3.628 versus 3.715), compared with 3.451% versus base CDF. The paired game interval against ordered is −0.1484 to −0.0226 carries. Most other differences remain small and uncertain. The chart leader’s game interval crosses zero against CatBoost, despite a lead against base CDF. Interception medians tie in aggregate, with different individual errors. ATD blend’s 0.050% Brier advantage over CatBoost has intervals crossing zero. No new significance veto or automatic promotion was added.

## Exact retained-owner release action

[One self-contained owner action request](OWNER_ACTION_REQUEST_V3.md) names the delivered package, checkpoint, guards, remaining game deadline and required live receipt. No new website writer or scheduler was created. The original ready core release remains independent of new research and probability work.

[Latest completed control/history execution index](ALL12_RUN_RESULTS_SUPPLEMENT_V3.json) supplements the immutable earlier run index. The separately saved failures, actual successful continuations and independent checks are individually linked.
