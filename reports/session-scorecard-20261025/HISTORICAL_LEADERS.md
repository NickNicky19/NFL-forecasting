# Historical leaders from the complete session

These are the **lowest observed among tested procedures on the named population**, not global optima or newly verified wins over the current live website. Reuses the accepted41-family full-week audit. No new NFL fit, forecast, outcome, test or acquisition occurred.

Main source-matched panel: REG2022–2024,815games,54weeks;1,960supportedQB outcomes,4,558RB rushing outcomes,15,251RB/WR/TE skill outcomes. Contemporaneous historical website/raw forecasts are unavailable. These periods are exposed development.

|Category|Fixed procedure under stated product|Primary error|Lower recorded blend/legacy point|Current website family|
|---|---|---:|---|---|
|Passing yards|leaf_cdf_lower_median|MAE 66.1617347|P4_point_heuristic 66.1204485|LAB_CDF|
|Passing TDs|distribution_split_cdf_mean|MSE 1.0619745|None lower in named set|LAB_CDF|
|Completions|leaf_cdf_mean|MSE 51.3753568|None lower in named set|LAB_CDF|
|Passing attempts|distribution_split_cdf_mean|MSE 113.900731|P4_mean_objective_point 113.875771|LAB_CDF|
|Interceptions thrown|distribution_split_cdf_mean|MSE 0.677566428|None lower in named set|LAB_CDF|
|Rushing yards|leaf_cdf_lower_median|MAE 19.7189557|None lower in named set|LAB_CDF|
|Rushing attempts|direct_catboost_medium_intended_mean|MSE 24.0464096|P4_legacy_point 23.9485638|COUNT_A_LEGACY|
|Receptions|count_A_mean_fallback_v2|MSE 3.25414645|count_A_legacy_point 3.24391917|COUNT_A_LEGACY|
|Receiving yards|direct_catboost_medium_median_objective|MAE 16.343398|P4_point_heuristic 16.342947|CATBOOST_MEDIUM|
|Rushing + receiving yards|direct_catboost_medium_direct_total|MAE 20.9839251|P4_point_heuristic 20.9661128|CATBOOST_MEDIUM|
|Exact website offensive PPR|Blocked exact labels|N/A|None lower in named set|R0_UNCHANGED|
|Anytime rushing-or-receiving TD|equal_CDF_Cat_P4_family|Brier 0.140647014|None lower in named set|TD_EQUAL_CDF_CAT|

## Actual errors of the named fixed leaders

The metrics below describe the selected fixed leader; they do not imply it minimizes every secondary metric. Count-mean winners are chosen byMSE. Where a complete same-product all-method secondary screen is unavailable, no MAE champion is invented.

|Category|MAE|RMSE|Bias (prediction minus actual)|
|---|---:|---:|---:|
|Passing yards|66.1617347|85.2577694|-0.284183673|
|Passing TDs|0.8332745|1.03052147|0.0682701251|
|Completions|5.72854975|7.16766048|0.17454016|
|Passing attempts|8.35673612|10.6724285|0.504190774|
|Interceptions thrown|0.680138374|0.823144233|0.0115188814|
|Rushing yards|19.7189557|29.3270471|-6.76064063|
|Rushing attempts|3.71612701|4.90371386|0.0903921171|
|Receptions|1.34986856|1.80392529|0.0192610133|
|Receiving yards|16.343398|25.0258941|-5.44388494|
|Rushing + receiving yards|20.9839251|30.2865808|-6.01368624|

## Full-law ranking differs

|Category|Lowest inspected valid-law CRPS procedure|CRPS|
|---|---|---:|
|Passing yards|distribution_split_cdf|46.37774599|
|Passing TDs|distribution_split_cdf|0.5355739553|
|Completions|leaf_cdf|3.954383453|
|Passing attempts|distribution_split_cdf|5.780315507|
|Interceptions thrown|leaf_cdf|0.4033933976|
|Rushing yards|distribution_split_cdf|14.09637272|
|Rushing attempts|distribution_split_cdf|2.543566142|
|Receptions|distribution_split_cdf|0.9100307657|
|Receiving yards|distribution_split_cdf|11.66562191|
|Rushing + receiving yards|distribution_split_cdf|14.92719369|

ResponseCDF has the lowest inspected full-lawCRPS for passingyards/TDs/attempts and allfive skill categories. LeafCDF leads completions/interceptions. Gains are usuallysmall; several paired intervals crosszero and bias/tails canworsen. Onlycombined passed that exposed study's own recorded advance gate; that is not scientific qualification or deployment.

AnytimeTD: equal CDF/Cat probability blend Brier0.1406470136 is the same family currentlyserved. CatMedium is the best individual fixed component Brier0.1407630898. A separately learned2023–24shrunk blend barely improves fixedhalf0.1407527210→0.1407477673 on10,157rows/544games/36weeks, but fails advancement and cannotbe compared directly to the three-yearP4 score.

**No over/under ranking procedure has established reliable superiority.** Numeric point errors, CRPS, threshold calibration, selected-list outcomes and anytimeTD Brier remain separate. Week7 grading is reported separately in README.md; its partial post-start scores are descriptive and establish no reliable ranking superiority.

LegacyW6 pooledH3passingyards45.2056MAE vsoldSITE56.6230 is a separate27row/13game/oneweek exposed reconstruction with worsebias and incompletely recovered originals. H3completions improvedMAE but worsenedRMSE. Initial all-skill/postseason panels include role-inappropriate passingzeros and cannot supply typical-QB rankings.

Exact websitePPR remains blocked: no broad qualified exact18-component label panel. No generic fantasy proxy is substituted.

Machine-readable JSON includes sourceSHA256 bindings, actual secondaryerrors, limitations, fallback identities, older smallsamples and separate observedMAE/MSE/RMSE minima where the accepted published mainpanel supports them.
