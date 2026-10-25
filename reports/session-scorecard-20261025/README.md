# NFL session scorecard — October 25, 2026

## Actual findings

Saved predictions now have prediction-versus-actual rows and independently checked errors. This report separates the session's historical leaders from a new partial Week 7 comparison. No absolute optimum, reliable ranking champion or deployment is claimed.

**The largest new observation is adverse to the current selected passing models.** On the same 16 supported QB rows, the saved adjusted website baseline has passing-yard MAE **47.016875 versus 71.0** for the current selected forecast: **33.779% lower observed error**. Its completion MSE is **25.617025 versus 36.551384**; interception MSE **0.360306 versus 0.471705**. These are eight exposed games, incomplete coverage and different input vintages. They do not establish future superiority.

## Every category: this Week 7 snapshot

Each row uses the identical all-arm population within its category: current selected forecasts, captured challengers and available recorded controls. All **1,754** planned current-matched primary-role offers remain in the control CSV; **499** have supported outcomes and **486** have every required control. Missing controls are reported, not converted to zeros. Do not mix these denominators with the larger LAB-only comparisons.

|Category|Lowest observed primary loss|n|Metric|Loss|Current selected loss|Reduction|
|---|---|---:|---|---:|---:|---:|
|Passing yards|Saved adjusted website baseline (`adj`)|16|MAE|47.016875|71.000000|+33.78%|
|Passing TDs|Saved unadjusted projection (`proj`)|16|MSE|1.029013|1.114920|+7.71%|
|Completions|Saved adjusted website baseline (`adj`)|16|MSE|25.617025|36.551384|+29.92%|
|Passing attempts|Saved adjusted website baseline (`adj`)|16|MSE|50.005581|54.693786|+8.57%|
|Interceptions thrown|Saved adjusted website baseline (`adj`)|16|MSE|0.360306|0.471705|+23.62%|
|Rushing yards|Saved adjusted website baseline (`adj`)|36|MAE|27.358889|28.194444|+2.96%|
|Rushing attempts|CatBoost medium|36|MSE|26.867196|29.942361|+10.27%|
|Receptions|Saved adjusted website baseline (`adj`)|120|MSE|2.801348|2.935256|+4.56%|
|Receiving yards|CatBoost medium|120|MAE|19.363089|19.363089|+0.00%|
|Rushing + receiving yards|Saved unadjusted projection (`proj`)|40|MAE|30.061250|30.718047|+2.14%|
|Exact website offensive PPR|No supported winner|0|N/A|N/A|N/A|N/A|
|Anytime rushing-or-receiving TD|Leaf-CDF|54|Brier|0.370773|0.371421|+0.17%|

Passing comparisons cover QBs; rushing primary comparisons cover RBs; receiving, combined and anytime comparisons use their declared RB/WR/TE contracts. Other modeled roles remain in the private rows. QB-rushing baseline fallbacks still count in the actual saved Top-list results.

Yards use prespecified MAE; count comparisons use MSE; anytime uses genuine probability/Brier. An unknown legacy point is not relabeled an authenticated mean. Improvement percentages are loss reductions, not increases in hit rate. Bias and tails can worsen despite a primary improvement.

The larger LAB-only carry comparison has 38 RB outcomes: CatBoost reduces MSE **28.441466 to 25.547162 (+10.18%)** and MAE **4.065333 to 3.891257 (+4.28%)**, while underprediction worsens slightly. The table's all-control carry cohort has 36 rows; its matching losses are **29.942361 to 26.867196**.

## What the recorded controls mean

Pinned website commit: `453e7e6e843b0cb1ae611b0925063e0f96c70196`; `pull/build.py` blob: `13a09f2a3e02e1819432860ee98417cf445cad99`.

The captured `proj` is the pre-adjustment projection. The saved `adj` is `round(base * matchup_factor, 2)`, with a separate historical-average fallback when projection is absent. `source=model/average` remains explicit. Average fallback rows are not relabeled raw-provider forecasts. We scored retained numbers; no baseline was reconstructed from current outcomes.

The anytime control uses the saved `td_chance`. Raw projected TD counts, numeric CatBoost/HGB points and gap scores were not converted into invented probabilities. Numeric website gap rankings have no native probability comparator.

## Historical leaders across the session

This reuses the accepted **41-family methods audit**, with its failed, mixed, incomplete and successful work preserved. The main comparable panel is **REG 2022–2024: 815 games, 54 weeks**; 1,960 supported QB rows, 4,558 RB rushing rows and 15,251 skill rows. It is exposed reconstructed development evidence. Historical contemporaneous website/raw-provider forecasts are unavailable, so these losses cannot be labeled wins over today's live website.

|Category|Fixed procedure under declared product|Primary loss|Lower recorded blend/legacy point|
|---|---|---:|---|
|Passing yards|leaf_cdf_lower_median|MAE 66.16173469|P4_point_heuristic: 66.12044852|
|Passing TDs|distribution_split_cdf_mean|MSE 1.06197450|—|
|Completions|leaf_cdf_mean|MSE 51.37535676|—|
|Passing attempts|distribution_split_cdf_mean|MSE 113.90073106|P4_mean_objective_point: 113.87577075|
|Interceptions thrown|distribution_split_cdf_mean|MSE 0.67756643|—|
|Rushing yards|leaf_cdf_lower_median|MAE 19.71895568|—|
|Rushing attempts|direct_catboost_medium_intended_mean|MSE 24.04640959|P4_legacy_point: 23.94856377|
|Receptions|count_A_mean_fallback_v2|MSE 3.25414645|count_A_legacy_point: 3.24391917|
|Receiving yards|direct_catboost_medium_median_objective|MAE 16.34339800|P4_point_heuristic: 16.34294697|
|Rushing + receiving yards|direct_catboost_medium_direct_total|MAE 20.98392514|P4_point_heuristic: 20.96611282|
|Exact website offensive PPR|No supported winner|N/A|—|
|Anytime rushing-or-receiving TD|equal_CDF_Cat_P4_family|Brier 0.14064701|—|

P4 yard blends are point heuristics, not mixture-law medians. The legacy carry blend and original Count A fallback do not inherit the corrected mean contract because their MSE is lower. Corrected-mean CatBoost carries have MSE **24.046410**, versus **24.024640** for the served legacy Count A; that corrected-contract leader does not beat the served legacy comparison. The historical anytime equal-blend family is already served.

[Historical diagnostics](HISTORICAL_LEADERS.md) include MAE/RMSE/bias, CRPS leaders and old H3/Week 6 limits. Full-law leaders differ from point leaders: Response-CDF leads inspected CRPS for passing yards/TDs/attempts and five skill targets; Leaf-CDF leads completions/interceptions. This does not establish reliable selected over/under rankings.

## Player predictions, outcomes and coverage

The private interactive `SCORECARD.html` contains all **15,444** frozen point predictions across **48** category/procedure combinations, current selected references, actuals, errors, fallbacks and timing lanes. It also includes **2,476** probability forecasts and frozen global Top 12/category Top 5 lists, with player/category/model filters and CSV export. The separate private control CSV adds base, adjusted and native-TD controls on all 1,754 planned current-matched primary offers. Public files contain aggregates only.

The retained game-finality snapshot is **2026-10-25 22:49 UTC**: eight of 13 query games were final. Recovery completed at **23:15 UTC**. It scores **2,251 point incidences across 562 unique player/game/category outcomes**, plus **935 probability incidences**. These repeated model/line forecasts are not independent football samples. It retains 222 played-zero incidences, 6,016 pending-final incidences, 4,414 unknown-participation incidences and 2,763 played-missing-statistic incidences. No DNP is inferred.

**Zero newly captured prospective outcomes are confirmed in this snapshot.** Graded games are in the post-start development lane. Five games received corrected point forecasts before kickoff; two received new probability forecasts before kickoff. Their outcomes remain pending here. Prior owner screenshot exposure remains disclosed. Later game completions are not silently imported into this frozen status snapshot.

The actual saved website Top 24 has **7 hits, 11 misses and 6 pending**: overs 3/11 resolved; unders 4/7 resolved. No selections were reranked or topped up after outcomes. Reconstructed probability lists contain different selections and coverage, so their hit rates do not establish superiority over the website lists.

Probability scores retain over/under/push Brier, actual binary Brier, selected-side Brier, and positive infinite log loss when applicable. No infinite losses occurred in this scored packet. Partial single-week uncertainty is unavailable; old completed-week and scientific gates remain unchanged.

Anytime labels remain selective: **31 YES/23 NO among 54** current-matched supported outcomes. Its 0.17% observed advantage is not broad calibration evidence. Combined-yard components also have incomplete coverage. Exact website PPR remains blocked by its exact scoring/component contract.

## Execution and independent checks

No model was fitted, loaded or newly forecast in this scoring task. The existing ESPN-finality/Sleeper collector and append/resolution rules were reused. Explicit ESPN table fields added supported zeros without zero-filling missing phases or players. Exact frozen ESPN/Sleeper/GSIS joins, signed yards, count support and cross-source conflict quarantine remain enforced.

Two rendering/persistence attempts failed their fixed stage byte bounds. All original failures, cached sources, narrower prototype CSVs and spent resources remain. Completion reused eight cached projections without additional HTTP. A control-CSV duplication attempt failed before writing; its compact replacement retains all offers and leaves all model numbers in the accepted HTML. The shared 512 MiB cap was not raised; no evidence was deleted.

The ESPN-summary wire bodies and failed stage's original wire hashes/HTTP clocks are unavailable. Complete selected box-score/header projections survive with verified hashes. New local-verification clocks are not presented as provider retrieval/publication times. Projection replay does not recover missing wire bodies. The original primary scoreboard and Sleeper statistics bodies remain retained.

The independent read-only reviewer recreated 3,078 canonical observations and verified all 15,444 point values/actuals/errors, 432 point summaries, 2,476 probability rows, 97 probability summaries, 593 selected-list incidences and 122 nonempty list summaries. It also verified every control CSV field and all **80** paired comparison panels. Review adds no NFL observations.

V3 native runtime: **27.988 wall / 28.175 CPU seconds**, exit 0. Saved controls: **11.153 wall / 11.262 CPU seconds**, exit 0. No website, selected policy or scheduler changed. Local fresh-process replay passed; new remote private-body restoration is unverified.

Original H3 findings/worse bias/missing artifacts, mixed passing results, RB rules and `rec-half-adjustment-v1`/Weeks 7–14 remain unchanged. No scientific registration was passed, restarted or weakened. No category was switched live by this report.

## Records

- [Machine-readable aggregate comparisons](AGGREGATE_RESULTS.json).
- [Historical diagnostics](HISTORICAL_LEADERS.md).
- [Complete methods audit](https://github.com/NickNicky19/NFL-forecasting/blob/cae6121e2d4dd0fc5a6c7d2217a93cd242533de7/reports/full-week-method-audit-20261025/README.md).
- [Original forecast/probability capture record](https://github.com/NickNicky19/NFL-forecasting/blob/8a11b27201a0aee56ef6ca6ccf137f406fd1afe0/reports/blinded-week7-comparison-20261025/PROBABILITY_CAPTURE_REPORT.md).

The supported conclusion is lowest observed loss among tested procedures on the named population. It does not establish an absolute NFL optimum, durable future superiority or profitability.
