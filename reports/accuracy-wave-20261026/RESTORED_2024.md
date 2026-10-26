# Frozen 2024 models rescored with qualified played-zero labels

## What ran

This separately registered evaluator completed **85 fixed procedure/output comparisons**: 50 original source-matched procedures, 11 compatible CatBoost controls and 24 distinct CDF count-median outputs. **Zero new fits, model inference or HTTP requests** occurred. The forecasts already existed; only the evaluation population changed. This is not 85 new trained models or 85 independent football replications.

Scope is **2024 REG, 272 games and all 18 weeks**, with the complete frozen offered populations retained. The previously examined seasons remain exposed development evidence. The three-year 2022–2024/815-game historical leaderboard remains a separate result; this report does not overwrite it. Contemporaneous historical SITE, raw-provider and live R0 forecasts do not exist for this panel, so their errors are unavailable.

The [appearance qualification](FTN_2024_ZEROS.md) adds genuine explicit-zero labels for 105 player-games. Every procedure sees the same restored outcome population. Old supported labels and the remaining unknown, played-missing and DNP states are preserved. Only accepted mask bits change unknown participation to supported zero; no target-game volume is substituted into a predictor.

## Lowest observed original products on this panel

Lower errors are better. MAE is the average miss in the category's own units. RMSE also uses those units and puts more weight on large misses. Count means retain MSE as primary; yard medians retain MAE; genuine anytime probabilities retain Brier.

These are **fixed-procedure minima on this one historical panel**, not automatically the lowest loss across all earlier ensembles or a deployment selection. In particular, the existing equal CDF/CatBoost anytime blend must be considered separately before identifying an overall probability leader. Percentages and intervals below compare each procedure with the named **Leaf-CDF laboratory control**, not the website.

|Category|Scored / offered|Lowest observed fixed procedure|MAE, original units|RMSE, original units|Primary loss|Reduction vs Leaf|Exploratory 95% interval, loss difference vs Leaf|
|---|---:|---|---:|---:|---:|---:|---:|
|Passing yards|664 / 1,361|Response-CDF|65.9895|84.8957|MAE 65.989458|+0.109%|[-0.61899, +0.40538]|
|Passing TDs|664 / 1,361|Leaf-CDF|0.8642|1.0705|MSE 1.145880|-0.000%|[+0.00000, +0.00000]|
|Completions|664 / 1,361|CatBoost medium|5.6999|7.1078|MSE 50.520815|+0.233%|[-1.82236, +1.58318]|
|Passing attempts|664 / 1,361|CatBoost medium|8.3958|10.6526|MSE 113.477866|+1.239%|[-6.25406, +3.14144]|
|Interceptions|664 / 1,361|Response-CDF|0.6688|0.8033|MSE 0.645300|+0.286%|[-0.00461, +0.00113]|
|Rushing yards|1,536 / 2,047|Leaf-CDF|19.7129|29.3183|MAE 19.712891|-0.000%|[+0.00000, +0.00000]|
|Rushing attempts|1,536 / 2,047|CatBoost medium|3.6032|4.7846|MSE 22.892522|+1.387%|[-0.61634, -0.01187]|
|Receptions|5,200 / 7,148|CatBoost medium|1.3314|1.7870|MSE 3.193526|+1.132%|[-0.05803, -0.01555]|
|Receiving yards|5,200 / 7,148|CatBoost medium|15.9116|24.5446|MAE 15.911597|+0.432%|[-0.11139, -0.02493]|
|Rushing + receiving yards|5,200 / 7,148|CatBoost medium|20.3653|29.8340|MAE 20.365256|+0.447%|[-0.16925, -0.00944]|
|Anytime rushing/receiving TD|5,200 / 7,148|CatBoost medium|—|—|Brier 0.140132|+0.291%|[-0.00090, +0.00007]|
|Exact website offensive PPR|0 supported exact labels|No supported procedure|—|—|Unavailable|—|—|

All scored products cover **272 games and 18 weeks**. Passing categories keep 697 unknown offers each. Rush categories keep 499 unknown and 12 played-missing each; receiving/combined/anytime keep 1,924 unknown and 24 played-missing each. No missing prediction was dropped: every tested product has finite forecasts on its entire original offered population. The source controls and target labels match before scoring.

Intervals use the fixed 500 whole-week bootstrap draws, PCG64 seed 1906, with the same draw matrix and 95% linear-percentile bounds. Player rows are not resampled as independent observations. These exploratory intervals are not multiplicity-corrected selected-winner guarantees, independent confirmation or passage of any scientific registration. Choosing the lowest observed member of a catalog adds selection uncertainty.

## Strong controls, small differences and adverse findings

All 11 direct CatBoost controls pass the exact source identity, 97-feature equivalence, player-game/context, original-label and output-product checks. Their presence prevents calling a result a gain against only a weak control.

CatBoost carries MSE **22.892522** versus corrected Count A **23.060222**: approximately **0.727%** lower, with average misses **3.6032 versus 3.6112 carries**. CatBoost reception MSE **3.193526** versus Count A **3.199604**: approximately **0.190%** lower, with average misses **1.3314 versus 1.3364 receptions**. These are small laboratory procedure differences on this panel, not measured improvements over current live forecasts. Reception CatBoost's p95 miss **3.7085** is worse than Count A's **3.6822** despite its lower primary loss.

Yardage medians remain underpredictive: the lowest fixed rushing-yard model has bias **-7.4108 yards**, receiving **-5.5116**, and combined **-6.3518**. Their p95 absolute errors are **61.25, 52.8772 and 62.8597 yards**. Passing-yard Response-CDF's 0.109% MAE lead has an interval crossing zero. Small point gains do not remove important tail errors.

All 85 products, including losing controls, original-population errors, restored-population errors, fallback counts, bias and tails remain in the [complete aggregate file](RESTORED_2024_AGGREGATES.json). **A lower error after adding zero outcomes is a population change, not evidence that the unchanged model learned or improved.** Method improvements must compare different procedures on the same restored rows.

## Count medians are a separate forecast product

These saved empirical distributions also supply genuine numerical medians. They answer an MAE point question; the original count means answer the existing MSE question. No Count A or CatBoost mean was relabeled a median.

|Category|Lowest observed CDF median|Median MAE|Lowest observed MAE among original mean products|
|---|---|---:|---:|
|Passing TDs|Leaf-CDF median|0.786145|0.862820|
|Completions|Leaf-CDF median|5.545181|5.699850|
|Passing attempts|Response-CDF median|8.167169|8.395763|
|Interceptions|Leaf-CDF median|0.564759|0.662327|
|Rushing attempts|Response-CDF median|3.434245|3.603162|
|Receptions|Leaf-CDF median|1.262500|1.331448|

A median can have lower MAE and higher squared error than a mean. A zero interception median is not a 0% interception probability. This comparison does not change the website's count output contract or establish accurate over/under probabilities; a consumer change would require a separately versioned release.

## Anytime probability diagnostics

On 5,200 supported played outcomes, CatBoost's Brier is **0.140131901** versus Leaf **0.140540754**. Their log losses are **0.441484866 / 0.442361097**. Mean CatBoost probability is **0.1927226**, Leaf **0.1955292**, and the observed event rate **0.1946154**. Mean agreement is a calibration diagnostic, not proof of full reliability. No calibration was fitted on this panel.

All probability endpoints and complete denominators are retained. Actual losses here are finite; the evaluator would preserve positive-infinite log loss for a contrary 0/1 forecast rather than discard it. This is the rushing-or-receiving TD event conditional on played, with no prices, settlement proxies, independent-leg products or numerical prop-threshold claim. The current equal-probability blend is a separate incumbent reference, not included among these fixed minima.

## Check against the existing equal-probability recipe

A separately registered **new reconstruction** also evaluated the existing equal Leaf-CDF/CatBoost anytime recipe on the same restored 5,200 rows. It did not recover missing original P4 vectors or establish equivalence to the actual deployed 2026 model parameters, inputs or issuance. Its fixed weights came from the previously frozen two-member catalog; no weights were fitted on these results.

|Procedure|Brier|Log loss|Mean probability|
|---|---:|---:|---:|
|Leaf-CDF|0.140540754|0.442361097|0.1955292|
|CatBoost medium|0.140131901|0.441484866|0.1927226|
|Existing equal-probability recipe, new reconstruction|0.140174594|0.441443890|0.1941259|

CatBoost's Brier is only **0.0305% lower than this blend**, rather than the 0.291% lead against Leaf alone. The blend has slightly better log loss. The fixed whole-week interval for blend-minus-CatBoost Brier is **[-0.00019646, +0.00029027]**, crossing zero. This is no substantial demonstrated improvement over the incumbent recipe and supports retaining it. It is still historical laboratory evidence, not a historical live R0 comparison.

[Recipe comparison aggregates](ATD_CURRENT_BLEND_AGGREGATES.json) retain the two named reference comparisons, full denominators, infinite-loss support and provenance. A complete lossless immutable-parent reference view stores the exact arithmetic, row order and digest of all 7,148 reconstructed float64 forecasts, without duplicating its already retained component vectors. This is openly exposed, label-loaded reconstruction; no blinded or pregame issuance claim follows. Actual new private view is **159 bytes**; native runtime **19.971 CPU / 19.946 wall seconds**, within 30/60. No fits, inference, selector changes or deployment occurred. The independent reviewer reproduced every reconstructed value, all three probability panels and both bootstrap intervals; actual POSTEXEC and publication/privacy checks passed.

## Evidence, checks and release decision

Forecasts retain their original source policy and chronological fitting/preprocessing. Original historical availability remains the seven-day reconstruction; cutoff equality denotes a historical issue boundary, not genuine pregame issuance. The final FTN labels do not enter features. Source-only repairs did not generate or backdate forecasts.

Sealed evaluator plan: `d5242e8ce9ddb9b2b4515328e052fce52d403024231acec4490283db4b6f55cd`; worker: `4aab8b37c3bc596bf9941e1103fd83d728fb89c11f8e0304ed4306f202eb62ce`. Aggregate: **95,466 bytes**, SHA-256 `f253819b90a1ee30dda1d75a77a70d99803df525152ab951f04933ed7b83ef9e`. Immutable private completion/consumption records total **705 bytes**, within 2 KiB; no row/model copies were made. Native execution: **26.048 CPU / 26.008 wall seconds**, within 45/90; RSS **191,266,816 bytes**. The shared 512 MiB cap remains unchanged.

The separate read-only reviewer reproduced all 85 products and 85 fixed bootstrap intervals, 20 probability diagnostic panels, all coverage and compatibility checks, with **4,367 comparison nodes and zero discrepancies**. It verified 212,094 prediction/fallback row comparisons and 172,603 same-original-label/state comparisons. These checks do not add football observations. Runtime/source pins and immutable CAS readbacks passed; the closed aggregate output contains no private rows, IDs or paths.

**All twelve release decisions remain retain/no new switch in this wave; PPR has no supported replacement.** No new entry was selected, deployed or live-verified by this rescore, and no original scientific gate was passed. Historical leads support further consideration under the existing weekly policy. The [Week 7 scorecard](QB_REFRESH.md) remains the current-season comparison, with its different coverage/timing limits. The authorized production integrator still owns the reviewed correctness package and recurring-runtime integration.
