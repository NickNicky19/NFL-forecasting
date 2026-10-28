# Week 8 capture and unfinished-study checkpoint

Updated 2026-10-28T16:59:31.874820-05:00. Source: completed7a66 checkpoint plus the separately registered continuations below.

## Current decision

**No new model was selected for live use or deployed by this wave.** Actual served readback at **4:52 p.m. Chicago, October28** remains `DISABLED_USE_R0`, zero selected rows,2,019 publication fallbacks plus449 old-PPR fallbacks. Main is `dbf4a05…`; PR9 `f9f3056…` and PR10 `e12de47…` remain open. The existing production writer retains ownership. The newer audit coordination6481342954 is a request/composition check, not a deployed release.

This wave completed **52 passing-attempt forests and one chart-PPR median fit**, with saved forecasts and independently checked scores. It did not run53 independent NFL trials, retrain every category or prove a gain over today's website.

## 2025 passing attempts: fixed learner, different training history

All four procedures use the same38 features and32-tree CDF learner. Fitting uses the earliest registered cutoff each week and only earlier eligible labels. Time weighting is the fixed365-day half-life, not an optimized decay. Current-season training still has older history in features and the declared CDF cold-start fallback.

| Procedure | MSE, attempts² | MAE, attempts | RMSE, attempts | MSE gain vs frozen CDF |
|---|---:|---:|---:|---:|
| Frozen CDF / identical annual H4 | 124.098901 | 8.663631 | 11.139969 | +0.000% |
| Current-season labels | 128.226919 | 8.929705 | 11.323733 | -3.326% |
| Previous + current-season labels | 120.305733 | 8.631116 | 10.968397 | +3.057% |
| Multiseason, fixed365-day weighting | 121.172371 | 8.573752 | 11.007832 | +2.358% |

Coverage: **1,359 planned QB forecast-query opportunities;664 supported outcomes,272 games,18 REG weeks;695 unknown participation;36 supported played zeros**. These are not authenticated sportsbook offers. Every arm retained all1,359 predictions. H1 had243 fallbacks/117 scored; other procedures28/7. The5,436 new candidate forecasts were frozen and read back before complete outer evaluation. The original cached control adds1,359 rows to the private6,795-row CSV.

H2 improves signed bias (+0.692 vs+1.656 attempts) and p95 miss (22.532 vs23.798). Its game-cluster interval for candidate−CDF MSE is **[−8.881,+1.052]**; its week interval is[−7.551,−0.254]. H3 also has a game interval crossing zero and a worse maximum miss (36.435 vs35.039). All seven comparisons are exposed, nominal development analyses. The completed2026 H2 loss of approximately15.13% remains. This does not select a universal training-history winner or a website replacement.

[Exact public metrics, paired and weekly results](WEEK8_COMMON2025_PUBLIC_RESULTS.json) · [Independent row acceptance](WEEK8_COMMON2025_NUMERICAL_QA_RESULT.json). Model parameters, training-row/weight bindings, full predictions, actuals and the readable CSV remain in the approved private scoring capsules.

## First chart-PPR forecasting comparison

The separate target is `nick-chart-ppr-v1`, using the exact16-term chart scoring contract. The old website scoring target and its records are unchanged. The2026PBP bridge qualified the remaining rare positive scoring case: **13,236 /14,160** total labels;2026 has1,954 known-played complete labels and163 unknown participants. 2025 still has21 rare positive cases requiring an event inventory; their absence did not stop the qualified2026 comparison.

One fixed150-iteration HGB absolute-error learner uses32 existing non-snap/non-old-PPR features, training-only imputation/missing indicators and position indicators. Training: **2024,5,589 supported labels out of5,935 planned**. All training label availability uses the disclosed historical kickoff+7-day assumption; source publication timing is not authenticated. The2026 outcomes were tokenized without numeric conversion until the complete model/forecast capsule was durably frozen.

| Same-chart procedure | MAE, chart points | RMSE, chart points | Signed bias |
|---|---:|---:|---:|
| Fixed HGB median-objective point | 4.702027 | 6.634823 | -1.346343 |
| Training-only position median | 5.739191 | 7.987969 | -1.967973 |
| Training-only global median | 6.239232 | 8.508789 | -2.344002 |
| Position mean: separate expected-value control | 6.054111 | 7.750743 | +0.126567 |

**18.07% lower MAE versus the position median**, game-cluster difference interval[−1.2384,−0.8462] chart points. Week inference is unavailable with six weeks. This beats constant same-chart controls; it is **not a website win, a strong-CDF comparison, a calibrated distribution or prospective confirmation**. A stronger same-chart CDF/direct-distribution comparison remains next.

All **2,117 planned source-listed player-games** received four point outputs:1,954 supported outcomes across93 REG games/2026 Weeks1–6,163 unknown retained. There were2,032 model predictions and85 cold-history fallbacks (78 scored/7unknown). Fallbacks tie their position-median comparator and do not supply a forecasting gain. Their MSE24.0755 also exceeds global-control23.9092. HGB bias is−1.3463 points, worse than the separate mean control's+0.1266. Full source, role and fallback slices remain available.

The private grade capsule includes an8,468-row readable CSV with predictions, actuals, errors, timing, method and fallback. [Full safe results](CONTINUATION_PREREQUISITES_CHART_PILOT_RESULT_V1.json) · [Independent original-prediction and label acceptance](WEEK8_CHART_POINT_NUMERICAL_QA_RESULT.json). No chart output has entered Week8 live capture or replaced old-contract PPR.

## Twelve-category decision and capture record

Historical leaders below reuse the prior2026W1–6 benchmark; the new chart row has its own explicitly different target/population. Losses across rows are not comparable. Existing policy choices are unchanged. All live selected counts are zero. Ready procedures are the existing operational catalogue, not a claim every private per-method coverage cell has been restored.

| Category | Observed compatible research reference | Ready nonreference procedures | Existing selected-feed rows / current baseline rows | Next action |
|---|---|---|---:|---|
| pass_yd | Leaf-CDF median: MAE 62.279621 | CATBOOST_MEDIUM, LAB_CDF | 40 / 40 | RestorefullprivateW8census+assignedhorizon; admitadditionalreadyprocedures throughentrantcontract; no oldH3wintransfer. |
| pass_td | Response-CDF mean: MSE 1.157146 | LAB_CDF | 40 / 40 | ReadyCDFonly; qualifyCountA/Responsefuturequery+supportedrare-eventzeros; scoringopportunity mechanism sourcebridge. |
| pass_cmp | Leaf-CDF mean: MSE 44.178448 | LAB_CDF | 40 / 40 | ReadyCDFonly; qualifyCountA/Responseentry, then held-attemptcompletionconversion withqualifiedthrow/catchquality. |
| pass_att | Response-CDF mean: MSE 104.055610 | LAB_CDF | 40 / 40 | 2025fourhistorycomparisoncompleted; H2/H3gainsnotuniversal2026; source-qualifiedQB/teamresponsibilitygroupnext. |
| pass_int | Leaf-CDF mean: MSE 0.526397 | LAB_CDF | 40 / 40 | ReadyCDFonly; retaincompletedFTNrisk/hierarchicallossesandNGBoostpilot; qualifiednewriskinputs/futureentryneeded. |
| rush_yd | Leaf-CDF median: MAE 18.425856 | CATBOOST_MEDIUM, LAB_CDF | 112 / 154 | RetainCDF/Cat; controlledvolume-versus-signedgain experimentneedsqualifiedcarryroleinformation. |
| rush_att | Count A stored-mean v2: MSE 24.216499 | COUNT_A, LAB_CDF | 112 / 114 | RetainCountA/CDF; full-limited-replacement/teammate/exposuregroupneedsverifiedfacts/denominators; no vacatedtouchassumption. |
| rec | Count A stored-mean v2: MSE 3.331184 | COUNT_A, LAB_CDF | 403 / 409 | RetainCountA/CDF; targetcompetition/catchqualitygroupneedsqualifiedsources; all-playerroutevariantaloneblocked. |
| rec_yd | Leaf-CDF median: MAE 16.054624 | CATBOOST_MEDIUM, LAB_CDF | 403 / 409 | RetainCat/CDF; targetedNGSexpectedYAC denominatoradmission andstrongfixedlearner comparison; no repeatbroad28featuretrial. |
| rush_rec_yd | Leaf-CDF direct-total median: MAE 19.925906 | CATBOOST_MEDIUM, LAB_CDF | 291 / 295 | RetainCat/directCDF; jointrole/dependencearmsneedqualifiedmarginal/jointinputs; oldcopulalosskept. |
| anytime_td | CatBoost probability: Brier 0.136472 | CATBOOST_MEDIUM, LAB_CDF, TD_EQUAL_CDF_CAT | 430 / 438 | RetainCDF/Cat/registeredblend; samecutoffeventprobability grading+qualifiedcompleteparticipation; no one-sidedpricefairprobability. |
| nick-chart-ppr-v1 | HGB chart point vs position-median control: MAE 4.702027 | None; chart research only | 0 / 0 | Firstsamechartpointpilotcomplete; next strongsame-chartCDF/directdistribution+2025rare-eventinventory; future-queryadapter/entry/consumerneeded. OldexactsitePPRunsupported. |

[Machine-readable twelve-category record](WEEK8_CONTINUATION_DECISION_MATRIX.json). It preserves point means/medians, distribution/probability eligibility and separate policy/live status through the linked original product record. Original H3 caveats, mixed passing findings, legacy CountA numerical recipes, RB/receptions registrations and every negative study remain unchanged. No older scientific gate was imposed on provisional operation.

## Week8: what is genuinely captured, and what remains

The existing Parent40729788942 / child40729906573 retains **11,466 private challenger rows reported** and2,956 selected rows. The immutable3907ca38… public feed has **1,951 selected rows across14games**, independently read back with original timestamps. These were issued31.22–128.23hours before kickoff. They are early pregame forecasts, not an actualT−90 refresh.

Only anytimeTD has three ready procedures, counting the registered equal blend. Other numeric categories have one or two. R0, actual website and raw-provider controls are additional records where genuinely captured; they are not invented extra challengers. The full private per-method game/fallback census and the exact **pre-value game→capture assignment** still require authenticated restoration in the approved producer. Do not choose first/latest forecasts after viewing predictions, substitute later refreshes, infer matching rows from total counts or count snapshots as new games.

[Existing stream and shortlist coverage](WEEK8_EXISTING_STREAM_READINESS.md) · [Exact grading/horizon rule](WEEK8_HORIZON_ASSIGNMENT_REVIEW.json) · [Frozen ready-subset contract](../../config/next-checkpoint-week8-ready-shortlist-v1.json). New candidates enter only prospectively after future-query/source/product/restoration admission; no scientific superiority prerequisite was added to valid shadow capture.

The existing production owner received [the concrete continuation](https://github.com/NickNicky19/nicks-expert-nfl-picks/pull/1#issuecomment-6481225367). A later audit coordination [6481342954](https://github.com/NickNicky19/nicks-expert-nfl-picks/pull/1#issuecomment-6481342954) preserves the same owner and reports a conflict-free composition, not merged-source CI or deployment. The retained owner must finish PR9→PR10 normal scope/exact-head/release checks, preserve newer Main data, build a fresh paired board, install the valid feed and verify actual served values. No competing writer/scheduler was created.

**Next configured times, Thursday October29, Chicago:** existing Parent7:36–7:57a.m. (end exclusive); weekly decision1:15p.m.; first input deadline5:45p.m.; kickoff7:15p.m. The next actual eligible scheduled execution remains pending. The producer's sealed output root must retain `WEEKLY_CHOICE.json` / `WEEKLY_CHOICE_COMPLETION.json`; the next absolute runtime root and assignment remain unverified. The prior missed-window/exit78 failure is retained; activation is already enabled. No hindsight backfill.

## Evidence, failures, capacity and remaining information work

The original2025 run stopped at threadpool startup before an actual estimator fit. All55 slots, its charged callback/32-tree allocation and18,510 retained bytes remain recorded; because its whole failure-finalizer clock was not retained, the full600CPU/840wall allowance remains conservatively consumed. A separate runtime-only technical continuation, with the unchanged child/network guard and a pinned already-loaded libc bootstrap, completed52 actual forests/1,664 trees in74.53CPU/74.27wall seconds/364MBRSS. No failed budget was refunded.

The first chart-point launch omitted a required GO field and stopped before imports/data/fits/CAS. Its original stderr and failure receipt remain. A separately recorded GO-only continuation kept the scientific recipe unchanged and completed one150-iteration fit in45.16CPU/45.12wall seconds/497MBRSS. Independent cached-row acceptance checked both studies without refitting/loading models or adding NFL observations. The chart bridge source work and its arithmetic acceptance are separate from these53 new predictive fits.

Actual closing managed-store inventory passed: **724,326,616 / 1,358,954,496 bytes** combined; market lane97,250,064/268,435,456. Shared new-metadata reserve remains16MiB; old caps and original failures are unchanged. New2025V1+V2 private retention16,671,421B; chart bridge839,676B including control; chart point382,433B including control. Complete original forecasts/grades and fresh-process byte checks are retained. Offhost research-packet restoration is not claimed. Publication metadata is separately byte-counted after this snapshot.

The three information studies remain explicit: carry full/limited/replacement/teammate exposure needs verified facts and complete denominators; receiving target/catch-quality needs column/denominator qualification (cached2022/23NGS exists, not a completed modern study); QB/team quality needs more than depth rank and the2025NGSdefinition bridge. The missing2025 common-learner slice is now complete. The ten families/all60 suggestion IDs remain in the original mechanism matrix with their prior failures; this wave did not run a60-candidate cross-product.

**Odds:** zero Odds API calls, key reads or credits in this wave. The approved secret-bearing producer still must verify its separate private raw-odds transport/restoration, actual entitlement/quota and prior176-credit consumption before capture. A football restore does not qualify that route. No new football/market probability, EV-ranking or paper-return improvement is claimed. Existing market experiments and all losses remain intact.

### Next executable work

1. Existing producer/owner: authenticate original Week8 per-method census and pre-value assignment, preserve fresh R0/visible-site comparisons at registered horizons, observe the next qualified run and complete live integration.
2. Research: strong same-chart CDF/direct-distribution control and future-query package; qualify2025rare-event source inventory; then bounded controlled role/opportunity/NGS additions after their specific source admissions.
3. Market: once the approved private route/quota is verified, perform the already specified same-cutoff football/market/hybrid and frozen paper-selection comparisons. No unsupported price probability or forecast-gap EV substitute.

This is a completed finite checkpoint with unfinished programme and operating dependencies explicitly retained, not full completion or an absolute-best-model claim.
