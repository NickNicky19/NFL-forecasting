# New ordered-history and analog forecasting comparisons

Completed after checkpoint1956b605. This is a new predictive wave, not a rerun of its cached leaderboard/top-player/actual-volume studies.

## Actual new results

**Same eligible 2026 regular-season Weeks1–6:93games,6weeks.** Median forecasts are compared by average absolute miss (MAE). Smaller is better.

| Category | Existing CDF median | New ordered-history CDF | Uniform analog | Relevance-weighted analog |
|---|---:|---:|---:|---:|
| Rushing attempts | 3.661597 | **3.619772** | 3.659696 | 3.667300 |
| Receptions | 1.252569 | **1.247701** | 1.273661 | 1.267712 |

The new ordered model reduces carry MAE by **0.041825 carries (1.14%)**, and reception MAE by **0.004867 catches (0.39%)**. Across the paired rows that is22fewer total absolute carry-error units and9fewer reception-error units, not22/9additional correct predictions. These are small observed reductions, not a large new accuracy breakthrough.

Both nominal game-cluster95% intervals include zero: carry candidate-minus-control MAE **[-0.104762,+0.013454]**, receptions **[-0.016785,+0.007366]**. The registered two-target simultaneous intervals also include zero. With six week clusters, the minimum-eight-cluster week interval is unavailable. These data have already been exposed to research; this is not untouched confirmation.

Uniform analog carries improve only0.0519% (one total absolute-error unit across526rows). Relevance carries worsen0.1558%; uniform receptions worsen1.6839%; relevance receptions worsen1.2090%. All four analog primary uncertainty intervals include zero. Each definition, every week and every loss remain; no method was removed for one negative week.

### Mean/MSE product remains separate

| Category | New ordered mean MSE / RMSE | Strong corrected Count A mean MSE / RMSE | Decision on this historical mean comparison |
|---|---:|---:|---|
| Carries | 23.909217 /4.889705 carries | 24.216499 /4.921026 | Ordered has1.27% lower MSE |
| Receptions | 3.336766 /1.826682 catches | 3.331184 /1.825153 | Retain Count A; ordered loses0.17% |

The corrected laboratory Count A recipe is not assumed identical to the website’s current restored wrapper/fallback. These are matched laboratory gains, not measured errors of the contemporaneous live website. A median-MAE lead does not select the mean, full distribution, probability component or prop ranking.

### Adverse and coverage findings

- Carry median bias worsens from **-0.8669 to-0.9924**. Its p95 absolute error improves10.75→10, while p90 worsens8.5→9. Exact-count accuracy (strict error<1) falls14.83%→13.88%; error≤1 improves29.47%→32.32%.
- Reception median bias worsens-0.4045→-0.4159; p90=3andp95=4tie. Exact-count accuracy is unchanged32.50%; error≤1 improves69.98%→70.47%.
- Carries: **668planned/526supported**,142unknown. Receptions: **2,458planned/1,849supported**,603unknown and**6played with missing statistic**. Those six are not relabeled unknown or zero.
- Original CDF/ordered fallback populations are identical: carries32planned/24scored; receptions140planned/82scored. All planned rows remain, including sparse players, unknown outcomes and fallbacks.
- Frozen top10/15/20 memberships from the completed study were reused to evaluate **new** predictions. Several reception/RB/TE groups worsen. No subgroup-specific training or policy was tested, and no inspected subgroup winner is automatically selected.

Full marginal count-law scores were calculated for the new candidates. The retained BASE control packet supplies points, not compatible saved proper scores in this comparison. No improved over/under probabilities, calibration, ranking, market edge or paper profitability is established. Real offered lines/prices are absent here.

## Methods and source identities

**Ordered-history CDF:** unchanged32ExtraTrees, squared-error splits, depth8, minimumleaf30, seed1701, max_features1.0, two threads. It adds the four most recent availability-qualified game slots: count/opportunity values, age and played/DNP/unknown flags. Carry adds20fields; receptions adds24including earlier catches and targets. Unknown slots remain slots, with unsupported statistics missing. The law remains95%empirical leaf distribution +5%training role/global prior. This tests the complete added group, not each field separately or a full injury-aware role system.

**Analog:** same original BASE information and earlier training population. Median/IQR transforms and missing indicators are fitted only on training data; retrieve up to64same-position earlier player-games. One recipe uses uniform weights; the other uses a fixed Gaussian distance kernel, bandwidth equal to the64th neighbor distance, shrunk50%toward uniform. Both retain the same5%prior. They share one fitted context per category and strongly correlated forecasts; they are not independent football replications. Neither is learned TabR, specialized top-player training or a completed general relevance-weighted training programme.

Original source and training-frame integrity were authenticated in private execution receipts. The original history has an assumed seven-day availability lag; that is not verified historical publication timing. Unknown clock handling remains strict; live issuance rules are unchanged.

Training target rows are2019–2025regular season before2026-09-01. Existing qualified earlier postseason rows may contribute historical features. Evaluation is2026W1–6REG. The ordered2025annual comparison remains unrun; older completed2025studies and the no2025market experiment remain unchanged.

## Actual execution and evidence

- **2new supervised CDF fits/64trees**, producing**5,998new all-role category forecasts**. The two original CDF artifacts were loaded for audits/priors only; their cached forecasts were reused without refitting or new control inference.
- **2new analog preprocessing/context preparations**, producing**11,996new forecasts** from two fixed weight recipes. Zero additional CDF fits or model loads.
- Total**17,994new category/procedure forecast rows**, containing separate mean/median views of each law. They represent repeated predictions on2,999player-games,93games and6weeks; they are not17,994independent NFL observations. Headline primary opportunities are3,126planned/2,375supported per procedure.
- Every new model/context and original prediction was privately frozen and read back before its evaluation labels were opened. Restricted training/query/forecast/actual/neighbor/weight/score rows remain private and replayable.
- Original ordered V1 completed both fits and the freeze, then failed on missing score placeholders. V2 grading hit a CPU limit because its global profiling guard slowed storage walking (actual63.2676CPU against60,0models/laws/CAS); that adverse overrun and the preconstructor retention error remain. V3 used constant-time fit-entry rejection, completed grading in36.15CPU/35.93wall, and preserved all frozen point bits. No refitting or replacement of original predictions occurred.
- V3 performs two retained-model law-scoring/replay passes over5,998rows; it is not described as zero mathematical inference. It generates zero new point forecasts. The original failed invocation remains failed.
- Analog scientific execution succeeded once:73.63CPU/73.65wall,421.4MBRSS, two private writes. Its independent QA helper’s first categorical-comparison failure remains; corrected technical QA changes no model/data/metric.
- Independent ordered checks:47primary checks plus3,026final retained-vector/metric checks. Analog:29,462law/point/moment/quantile/proper-score/neighbor/ESS checks. These verification counts are not predictive experiments or football samples. Eight ordered and28analog fictional checks are software evidence only.

## Twelve-category status

This table combines the newly tested count panels with explicitly reused1956results. It never chooses a cross-season minimum. “Research lead” is not an operational admission or a guaranteed future winner.

| Category | Current comparable research lead | New work this wave | Actual live procedure at last readback / next dependency |
|---|---|---|---|
| Passing yards | CDF median | None; prior result reused | CDF median; retain source/epoch and capture |
| Passing TDs | CDF median for display MAE | None | CDF mean; new median-view admission |
| Completions | CDF median for display MAE | None | CDF mean; new median-view admission |
| Passing attempts | CDF median for display MAE | None | CDF mean; new median-view admission |
| Interceptions | CDF median for display MAE | None | CDF mean; retain adverse bias/probability diagnostics |
| Rushing yards | CDF median | None | CDF median; separately test genuinely forecast volume/efficiency |
| Rushing attempts | **Ordered CDF median**; ordered mean also leads named MSE controls | Two analog recipes and one ordered model | Count A declared mean; ordered/current-source+future-entry+MAE consumer admission |
| Receptions | **Ordered CDF median**; Count A still wins named mean/MSE comparison | Same three new recipes | Count A declared mean; new point/source/future-entry admission |
| Receiving yards | CDF median | None | CatBoost median; receiving opportunity/catch-quality studies remain |
| Rushing+receiving yards | CDF median, direct total | None | CatBoost median; preserve direct/dependence controls |
| Chart PPR | Chart CDF median; new chart target | None | Old-PPR fallback; chart current-source/restore/consumer qualification |
| Anytime rushing/receiving TD | CatBoost has lowest inspected Brier, tiny old lead | No new probability experiment | EqualCDF/CatBoost blend; complete label/threshold/probability evidence separately |

No old scientific gate, original P2/v1 epoch, H3/RB/receptions registration or failure was rewritten. `stat_point_mae_v2` keeps mean/probability products separate and does not silently impose its superseded v1bias/tail/2025vetoes. Under the new policy, operational readiness is still explicit. The new recipes are research-tested candidates; no operational gates were invented as passed.

## Live release and genuine capture

**This wave changes no live forecast, ranking or scheduler.** Last bounded production readback (Oct28,10:58p.m.Chicago): websiteMain252a7ae…, unchanged overlay765b74e3… with**1,948selected forecasts**,448old-PPR and68other reference fallbacks. No new MAE admission or owner acknowledgement was observed after comments6486755400/6486760186.

Website `AGENTS.md` requires the retained implementation lease; revision178 remains with the existing manual production owner and has no inactivity expiry. This research session did not take it over, write website code or dispatch another producer. The exact existing MAE package must proceed through that owner: authenticate restored wrappers, admit typed `selected_projection` point views/catalog/epoch, capture before cutoff, validate consumer labels/sorts/fallback/rollback, publish and verify served values. This is the existing authorized action, not a new general approval request or an eight-week scientific wait.

The new ordered models additionally need a qualified current-history feature adapter, future artifact/source bindings, durable producer restoration, replay/fallback checks and challenger entry. A small historical lead alone does not make a model operationally ready. Preserve the incumbent wherever entry is pending.

Next configured existing capture is **October29,7:36–7:57a.m.Chicago**, end exclusive; weekly decision1:15p.m., first input cutoff5:45p.m., kickoff7:15p.m. Actual execution is pending. There are no new genuine pregame captures from this wave. The established producer must restore the private per-method census and original game-to-capture assignments, keep freshR0/actualwebsite shadows, and record any shortfall from3–5ready methods. Two point views of one CDF do not add a learner; the two analog variants share a context. Do not backfill missed issuance.

## Remaining original and additional research

1. Complete retained-owner MAE view admission and genuine same-cutoff capture; do not wait for every study/category. Observe and retain actual scheduled run IDs and failures.
2. Execute a separately registered2025annual evaluation of the frozen ordered recipe where source/control identities support it. It is additional exposed development evidence, not untouched confirmation. Do not rerun completed F1–F4 history averages or the52fit common-learner study unchanged.
3. Continue qualified carry roles/teammate competition/team opportunities, receiving allocation/catch quality and QB-volume/throw-quality additions against a fixed strong learner. This individual-history feature group does not complete verified injury/role/teammate systems.
4. Keep broad/sparse populations and frozen top-player views. Specialized training and later chronological role-adaptive policies remain separate experiments, not inferred subgroup wins.
5. Ordered sequences beyond this four-slot group, learned TabR/relevance, TabICLv2 runtime/median pilot, targeted NGS/FTN, distributional learners and declared calibration/stacking alternatives retain their actual queue states. Existing negative workload/FTN/NGS/copula/calibration studies stay visible.
6. Actual offered-line probabilities and football/market/hybrid/paper-selection studies require authenticated price/settlement/timing/private transport. No new Odds API call, key access, wager or claim of improvedEV was made. The prior176-credit consumed/uncertain accounting remains; the website secret’s absence from this runtime is not evidence it is absent there.

[Scientific configuration](SCIENTIFIC_CONFIG.json) · [All public aggregate results](RESULTS.json.gz) · [Verification summary](VERIFICATION.json).

## Closeout served-data check

At **October29,12:17a.m.Chicago**, websiteMain252a7ae… and the exact served metadata/pointer hashes were still unchanged. The prior authenticated1,948-selected census remains applicable; no full overlay or browser rerun was needed. This four-GET check records no new release/capture. The ownership/acknowledgement query remains dated10:58p.m.; no claim of owner inactivity follows. Exact served-identity receipt remains in the private audit packet.

## Public and private audit scope

Automatic approval review rejected public export of sealed configurations containing private artifact locations, integrity bindings and operational storage metadata. This public packet includes the executed algorithm modules, scientific parameters, aggregate results and non-sensitive verification summary. Full original runners, model parameters, data, sealed configurations and detailed receipts remain preserved privately. Reproducing NFL scores requires approved access to those private inputs. No branch reference was updated to include the rejected metadata.
