# Week 7 passing forecasts: completed-game comparison

Completed-game source qualification adds **two QB player-games and ten passing label incidences**. One is an explicit zero-interception outcome. The original 88 offered QB player-games and all 13 query games remain; no offered player was dropped. All 13 games now have qualified finality for the scoped passing evaluation.

The complete prior accepted state is retained: the original QB refresh, twelve final summaries, two publisher-qualified zero-passing appearances and the later derived TD/interception count-credit closures. New finality does not upgrade unqueried QB nonpassing or non-QB labels. Forecast values, probability vectors and ranking selections retain their original frozen versions.

## Complete offered passing population

|Target|Offered|Supported positive|Supported zero|Played, statistic missing|Unknown participation|Pending|
|---|---:|---:|---:|---:|---:|---:|
|Passing yards|88|27|2|1|58|0|
|Passing TDs|88|21|9|0|58|0|
|Completions|88|27|2|1|58|0|
|Passing attempts|88|27|2|1|58|0|
|Interceptions|88|13|17|0|58|0|

Monday contributed two qualified passers among seven already offered QBs; the other five remain unknown. Active roster status is not proof of playing. Missing statistics and unknown participation were not filled with zeros, and no DNP was newly inferred. TD/interception support is now **30/88**; yards, completions and attempts each have **29 supported plus one played-missing**. The nine TD zeros include the prior attributed derived zero; this packet adds no TD zero. The 17 interception zeros include one new explicit Monday zero.

## Exact common point comparisons

Current selection is the reference captured with the original Week 7 forecast package; its original source vintage is retained. The same finite forecasts and outcomes are compared for every captured method and both original saved controls. Counts retain **MSE** as primary; yards retain **MAE**. Displayed MAE and RMSE use the target’s units. A lowest observed procedure is a descriptive panel result, with no new weekly selection. Count A legacy and mean-v2 errors tie on these common rows; that tie does not certify legacy fallback mean semantics.

### All timing lanes: 26 common players in 13 games

|Target|Current MAE / RMSE|Lowest observed captured procedure|Its MAE / RMSE|Primary error reduction|
|---|---:|---|---:|---:|
|Passing yards|63.885 / 79.372|CatBoost median|63.681 / 79.223|+0.32% MAE|
|Passing TDs|0.788 / 0.970|Frozen Count A mean v2|0.753 / 0.946|+4.95% MSE|
|Completions|4.962 / 5.953|Current selection|4.962 / 5.953|+0.00% MSE|
|Passing attempts|6.998 / 8.654|Frozen Count A mean v2|6.760 / 8.515|+3.20% MSE|
|Interceptions|0.572 / 0.636|Response-CDF mean|0.568 / 0.631|+1.54% MSE|

### Genuine pregame lane: 10 common players in five games

|Target|Current MAE / RMSE|Lowest observed captured procedure|Its MAE / RMSE|Primary error reduction|
|---|---:|---|---:|---:|
|Passing yards|52.500 / 63.815|CatBoost median|51.883 / 61.654|+1.18% MAE|
|Passing TDs|0.635 / 0.815|Frozen Count A mean v2|0.611 / 0.791|+5.80% MSE|
|Completions|4.507 / 5.802|Frozen Count A mean v2|4.301 / 5.449|+11.79% MSE|
|Passing attempts|8.406 / 10.355|Frozen Count A mean v2|7.658 / 9.456|+16.61% MSE|
|Interceptions|0.511 / 0.545|Current selection|0.511 / 0.545|+0.00% MSE|

### Post-start reconstruction lane: 16 common players in eight games

|Target|Current MAE / RMSE|Lowest observed captured procedure|Its MAE / RMSE|Primary error reduction|
|---|---:|---|---:|---:|
|Passing yards|71.000 / 87.705|Current selection|71.000 / 87.705|+0.00% MAE|
|Passing TDs|0.883 / 1.056|Frozen Count A mean v2|0.842 / 1.031|+4.64% MSE|
|Completions|5.246 / 6.046|CatBoost median|5.262 / 6.016|+0.98% MSE|
|Passing attempts|6.117 / 7.396|Response-CDF mean|6.007 / 7.289|+2.85% MSE|
|Interceptions|0.610 / 0.687|Response-CDF mean|0.603 / 0.679|+2.35% MSE|

**Current selection still has the lowest captured genuine-pregame interception error.** Count A has 6.52% higher MSE and Response-CDF 0.53% higher MSE in that ten-player lane. The earlier positive-only apparent interception lead remains reversed after supported zeros are restored. Genuine-pregame Count A MSE is 5.80% lower for TDs, 11.79% lower for completions and 16.61% lower for attempts. CatBoost yard MAE is 1.18% lower. These are five games of one week; no durable superiority, calibrated probabilities or scientific promotion is established.

The post-start panels retain their original lane and prior values. Pooling them with genuine pregame forecasts does not turn reconstruction into prospective evidence. The wider full supported pools include sparse/fallback cases absent from the 26-row common comparator; all losing methods, signed bias, tails, fallback and missing states remain in the exact aggregate.

## Saved controls and probability evaluation

On the 26 common yard rows, current MAE is **63.885**, original saved adjusted **47.353**, and original saved base **44.637**. In the ten-row pregame lane these are **52.500 / 47.891 / 37.870**. Their input vintages and upstream issuance remain unmatched. These are retained controls; no fresh same-cutoff R0 or algorithm effect is established.

The genuine pregame probability lane now has two resolved games and four supported QB rows per displayed passing target. Three-outcome Brier sums under/push/over errors; it is not binary anytime-TD Brier.

|Displayed target|Leaf Brier|Response Brier|Scored rows / games|
|---|---:|---:|---:|
|Passing yards|0.665627|N/A|4 / 2|
|Passing TDs|0.369152|0.356835|4 / 2|
|Completions|0.663329|N/A|4 / 2|
|Passing attempts|0.705833|0.701935|4 / 2|
|Interceptions|0.583961|0.583941|4 / 2|

There are no realized pushes or infinite log losses in these displayed passing panels. The unchanged evaluator still retains impossible-event infinity and its denominator. Duplicate secondary source lines are not additional player-games. Four rows per panel do not establish reliable calibration or a ranking winner.

The original saved Top Overs remain **3 hits, 8 misses, one unresolved**; Top Unders remain **4 hits, 3 misses, five unresolved**. All 593 ranking inputs retain membership and order. Unqueried nonpassing outcomes remain in their prior states even when their game is now final.

## All twelve category states

|Category|Supported unique outcomes in retained view|This packet’s effect / decision|
|---|---:|---|
|Passing yards|29|Two newly supported QB outcomes; retain current selection|
|Passing TDs|30|Two newly supported QB outcomes; retain current selection|
|Completions|29|Two newly supported QB outcomes; retain current selection|
|Passing attempts|29|Two newly supported QB outcomes; retain current selection|
|Interceptions|30|Two newly supported QB outcomes; retain current selection|
|Rushing yards|74|Unqueried labels preserved; no new category switch|
|Rushing attempts|75|Unqueried labels preserved; no new category switch|
|Receptions|124|Unqueried labels preserved; no new category switch|
|Receiving yards|124|Unqueried labels preserved; no new category switch|
|Rushing + receiving yards|41|Unqueried labels preserved; no new category switch|
|Exact offensive PPR|0|Exact label contract blocked; no replacement|
|Anytime rushing/receiving TD|55|Unqueried labels preserved; no new category switch|

These are unique offered player-game/category outcomes, not repeated model incidences or a complete-season score. The 610-player-game query, 4,012 category opportunities, sparse offers and prior unresolved nonpassing states remain. These results select no category replacements.

The new outcome evidence is observed after finality. It does not establish historical pregame availability for those sources. Genuine pregame forecasts and post-start reconstructions retain their separate timing lanes. No authenticated market-price comparison, expected-return result, reliable probability calibration or durable multiweek winner is established.
