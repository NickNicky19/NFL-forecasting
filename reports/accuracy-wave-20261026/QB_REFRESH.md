# Week 7 QB refresh — frozen forecasts versus outcomes

## Actual work completed

Two original keyless source responses were captured once on October 26: the Week 7 ESPN finality board, then the existing QB-filtered Sleeper route. Full bodies, receipts and **250 canonical append records** are retained privately. These records are not 250 independent player-games.

The frozen query retains **610 player-games, 4,012 category opportunities and 13 games; 12 games are now final**, with Monday pending. QB acquisition covers 88 offered QBs and 880 category opportunities. It newly resolves **49 numeric labels**, including 35 passing labels across eight additional supported QB appearances. Another 201 opportunities have attributed state/record changes; 630 retain their previous state/value.

No forecasts, model fits, calibration, weights, selection rules or list membership changed. All **13,850 non-QB forecast/probability/ranking rows** retain their accepted values and states. New global finality does not upgrade old non-QB statistics. Protected Week 8 outcomes were not opened.

The private lossless view retains **440 primary QB target keys × nine forecast/control columns** by reference to original frozen predictions, plus exact float64 actuals and explicit states. The earlier 180-key diagnosis was the current-website-finite subset. Sparse and unsupported players remain present.

## All timing lanes: descriptive fixed-method comparison

MAE means the average miss in the target's units. RMSE is also in those units and gives extra weight to large misses. Yards retain MAE as primary; count means retain MSE, with MAE displayed separately. These mean products are not silently replaced by MAE medians.

Each row below uses the exact common player-games for current, captured challengers and both saved controls. “Lowest observed” selects among current and the captured fixed lab procedures on this panel. It is not the weekly policy's choice or proof of a lasting winner. Eight games' challengers were reconstructed after kickoff; four resolved games had actual pregame capture.

|Category|Matched players / games|Current MAE / RMSE|Lowest observed captured procedure|Its MAE / RMSE|Primary error reduction vs current|
|---|---:|---:|---|---:|---:|
|Passing yards|24 / 12|61.958 / 76.708|Current Leaf-CDF median|61.958 / 76.708|0.00% MAE|
|Passing TDs|23 / 12|0.749 / 0.928|Corrected Count A mean|0.708 / 0.904|+5.09% MSE|
|Completions|24 / 12|4.527 / 5.379|Current Leaf-CDF mean|4.527 / 5.379|0.00% MSE|
|Passing attempts|24 / 12|6.444 / 7.809|Response-CDF mean|6.324 / 7.684|+3.18% MSE|
|Interceptions|20 / 11|0.546 / 0.628|Response-CDF mean|0.542 / 0.621|+2.05% MSE|

Count A legacy and corrected outputs match on these scored rows. That does not certify the legacy median fallback as a mean. Response attempts slightly improve signed bias; Response interceptions and Count A TDs worsen absolute bias against the nearly unbiased current arm. Every losing arm, tail diagnostic and fallback remains in the aggregate file.

## Actual pregame challenger lane: four resolved games

The original five-game pregame opportunity set remains intact; Monday is pending. These are incomplete-week descriptive results, with no valid multiweek interval or demonstrated durable advantage.

|Category|Scored players / games|Current MAE / RMSE|Lowest observed captured procedure|Its MAE / RMSE|Primary reduction vs current|
|---|---:|---:|---|---:|---:|
|Passing yards|8 / 4|43.875 / 47.622|Current Leaf-CDF median|43.875 / 47.622|0.00% MAE|
|Passing TDs|7 / 4|0.444 / 0.530|Corrected Count A mean|0.403 / 0.505|+9.22% MSE|
|Completions|8 / 4|3.089 / 3.700|Corrected Count A mean|3.006 / 3.472|+11.96% MSE|
|Passing attempts|8 / 4|7.097 / 8.576|Corrected Count A mean|6.551 / 8.123|+10.27% MSE|
|Interceptions|4 / 3|0.290 / 0.291|Corrected Count A mean|0.250 / 0.253|+24.18% MSE|

**Rare-event coverage is selective.** Genuine pregame interceptions have four supported positive outcomes, four played-missing fields, 17 unknown participants and seven pending offers, with no supported zero-interception outcomes. TDs have seven positive outcomes, one played-missing field, 17 unknown participants and seven pending offers, with no supported zeros. Missing fields were not changed to zero. Those apparent rare-event improvements cannot establish complete-population accuracy or calibration. Source and participation repair remain necessary.

## Saved controls and unresolved input timing

On 24 common yard rows, current MAE is **61.958 yards**, saved adjusted **49.289** (20.45% lower), and saved base **46.960** (24.21% lower). The old 16-row/33.78% result remains retained under its own population.

Current selection was issued October 24; saved fields came from the October 25 10:15 board, with upstream publication unverified. Different input vintages prevent isolating an algorithm effect or earning an automatic rollback. The old control CSV actual column was ignored; all refreshed errors use canonical outcome resolution.

## Probabilities and frozen Top lists

Only one of two genuine pregame probability games is resolved in this packet. For primary displayed DraftKings lines, Leaf/Response three-outcome Brier is **0.473890 / 0.480165** for attempts (two rows), **0.533443 / 0.524631** for interceptions (two rows), and **0.355582 / 0.383350** for TDs (one row). Duplicate secondary-source lines are not extra football observations. Three-outcome Brier sums under/push/over losses; it is not numerically interchangeable with binary anytime-TD Brier.

No calibrated probability or reliable ranking winner is established. No authenticated market-price probability was added. The unchanged evaluator preserves impossible-event infinite log loss and its denominator; this refresh actually has zero infinite losses.

The original saved Top Overs remain **3 hits, 8 misses, 1 unresolved**; Top Unders **4 hits, 3 misses, 5 unresolved**. Unqueried non-QB entries retain prior states. No list was reranked, topped up or stripped of losses.

## All twelve categories

Counts below are unique opportunities, not repeated model incidences. This is the frozen Week 7 stream, not total historical research or the complete season. Category outcomes overlap.

|Category|Original unique offers|Supported outcomes retained/refreshed|Current decision|
|---|---:|---:|---|
|Passing yards|88|25|Retain Leaf median|
|Passing TDs|88|23|Retain Leaf mean; Count A lead remains limited|
|Completions|88|25|Retain Leaf mean|
|Passing attempts|88|25|Retain Leaf mean; preserve challenger leads|
|Interceptions|88|20|Retain Leaf mean; zero coverage incomplete|
|Rushing yards|610|74|Retain Leaf median; non-QB labels not refreshed|
|Rushing attempts|610|75|Retain pending reviewed COUNT7 correctness integration|
|Receptions|610|124|Retain pending COUNT7; rec-half unchanged|
|Receiving yards|610|124|Retain CatBoost median|
|Rushing + receiving yards|610|41|Retain direct CatBoost median|
|Exact website offensive PPR|0 supported exact-label forecasts|0|Exact labels blocked; no replacement|
|Anytime rushing/receiving TD|522|55|Retain equal CDF/CatBoost probability blend|

No new category switch was selected under P2. New entrants and correctness repairs still require their existing operational/consumer checks. This does not impose old scientific minimums on provisional releases.

## Resources, artifacts and review

Capture plan: `d0a7b0126089a1affd656f5520291d82297e2559e35575cf3e34f37ef8b8ab82`; finish plan: `9f3555526c164c90fe342d6639c6b6e88e37cb81f3a72496767a51402d24f01b`; worker: `4b0d25789d29a9e7c87f7cd1b78ddee301c433f7bb60d24d77361423f4294789`.

ESPN gzip: 20,719 bytes, SHA-256 `351740a6fefb22573b2ad0b1cc740c467a95954ef808275ceeb17e161a99daae`. Sleeper QB gzip: 9,218 bytes, SHA-256 `c014e700258fcb8e1aa688966df7245f6aae43432eff5d9a0509a1689ec2aab5`. Canonical delta: `814649dc22f8dc54478649953b75b2be023813beb284c43e660a4836a5b5cc69`.

The CLI hash rejection and three output-format/allocation failures remain recorded. Final foreign-key view: 2,145 bytes, SHA-256 `ea7c57e855cd006c6b8e7d1b2026a8996f88338d669bbb8ab221400cb7c62152`; completion receipt: 1,894 bytes, `4ed81bcee9af2ffe3502389894d674d9c7469e316fabd5476e79c6fd068a5c32`. Entire study: **44,529 bytes, below original 54 KiB**. No quota increase or evidence deletion. All attempts total **89.197 CPU / 89.725 wall seconds**, below original 120/180; final RSS 283,836,416 bytes. Retries recomputed arithmetic only, adding no independent evidence.

[Safe aggregates](QB_REFRESH_AGGREGATES.json), 162,055 bytes, SHA-256 `89f51fcc3ee8d801102d26fb3189b0959471ae6fefa803db9660e0166e21c90a`, use `exact-record-columns-v1`: zip each table's columns with each row. Record multiplicity, optional fields, scalar precision and nested values survive; aggregate panel order may differ. Raw sources and private prediction/outcome rows remain private.

Independent post-execution arithmetic/serialization/privacy review reproduces all 440 view rows, 291 point panels, 54 probability panels, 76 impacted ranking panels and 41 common-control panels. Rank membership and order match all 593 accepted ranking rows. The separate read-only reviewer returned actual final POSTEXEC and plain-report/aggregate PUBLICATION PASS.

**No deployment occurred.** Website main remains `453e7e6e843b0cb1ae611b0925063e0f96c70196`; the existing production writer retains the reviewed COUNT7/strict-props integration. Monday grading and later automatic selection are pending until genuinely observed.
