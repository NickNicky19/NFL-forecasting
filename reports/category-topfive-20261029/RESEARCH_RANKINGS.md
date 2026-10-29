# Current category leaders and up-to-five method reconciliation

2026 regular-season Weeks1–6,93games,6weeks; exposed current-vintage reconstruction. This reuses completed scores and does **not** fit, infer, grade new NFL rows, select a live release or recreate the top-player analysis.

MAE is the average miss in yards/counts/chart points. Numeric means, medians and empirical recipes can all compete as display points, with truthful contracts. Two views of one CDF count as one method. AnytimeTD stays an event probability ranked by Brier.

## Current comparable decision table

| Category | Lowest observed display point / probability | Loss | Supported/planned | Distinct tested methods | Actual website at dated readback |
|---|---|---:|---:|---:|---|
| Passing yards | CDF_MEDIAN (median) | 62.279621 | 211/515 | 2 | P2_SELECTED point_median (40 rows) |
| Passing TDs | CDF_MEDIAN (median) | 0.824645 | 211/515 | 4 | P2_SELECTED point_mean (40 rows) |
| Completions | CDF_MEDIAN (median) | 5.118483 | 211/515 | 2 | P2_SELECTED point_mean (40 rows) |
| Passing attempts | CDF_MEDIAN (median) | 7.772512 | 211/515 | 10 | P2_SELECTED point_mean (40 rows) |
| Interceptions | CDF_MEDIAN (median) | 0.601896 | 211/515 | 5 | P2_SELECTED point_mean (40 rows) |
| Rushing yards | CDF_MEDIAN (median) | 18.425856 | 526/668 | 2 | P2_SELECTED point_median (112 rows) |
| Rushing attempts | ORDERED_CDF:median (median) | 3.619772 | 526/668 | 6 | P2_SELECTED point_mean (112 rows) |
| Receptions | ORDERED_CDF:median (median) | 1.247701 | 1849/2458 | 5 | P2_SELECTED point_mean (401 rows) |
| Receiving yards | CDF_MEDIAN (median) | 16.054624 | 1849/2458 | 2 | P2_SELECTED point_median (401 rows) |
| Rush + receiving yards | CDF_MEDIAN (median) | 19.925906 | 1849/2458 | 2 | P2_SELECTED point_median (291 rows) |
| Chart PPR (new target) | LEAF_CDF_CHART_MEDIAN_V1 (median) | 4.679406 | 1954/2117 | 5 | Old-PPR fallback, different contract |
| Anytime rushing/receiving TD | CATBOOST_MEDIUM (probability) | 0.136472 | 1849/2458 | 3 | P2_SELECTED binary_probability (428 rows) |

ChartPPR uses **nick-chart-ppr-v1**, not the old website contract. The latter remains unsupported. The live column uses the independently prepared Oct29,2:41p.m.Chicago public-payload census: **1,945 selected rows**, incumbentP2 and original products. Its forecasts were issued Oct28,12:01p.m.Chicago, not freshly captured when the Oct29 page was built. Exact bindings remain in the private audit; the prior named-family catalog is retained separately. No historical website/R0 forecasts exist for this current generic panel, so these are laboratory comparisons, not measured live-website gains.

## Up to five distinct tested procedures, per category

Every list uses the same full primary population for that category. The best retained display view is shown; all mean/median/empirical views and all additional losing families remain in the machine record. A five-method list is not proof that all five are ready for capture.

### Passing yards

| Rank | Family / retained view | MAE (ATD: Brier) | Bias | p95 absolute error | Fallback scored/planned |
|---:|---|---:|---:|---:|---:|
| 1 | LEAF_CDF / CDF_MEDIAN | 62.279621 | -5.767773 | 158.500000 | 1/30 |
| 2 | CATBOOST / CATBOOST_MEDIUM | 63.507248 | -4.341423 | 156.831839 | 1/30 |

Only 2 distinct tested procedures have comparable current-panel evidence; shortfall from five: 3. No extra CDF mean/median alias fills the list.

Separate expected-value leader among eligible saved mean products: **CDF_MEAN**, MSE **6362.064610**, RMSE **79.762551**, MAE **64.075619**. Legacy mixed CountA is not admitted as a mean.

### Passing TDs

| Rank | Family / retained view | MAE (ATD: Brier) | Bias | p95 absolute error | Fallback scored/planned |
|---:|---|---:|---:|---:|---:|
| 1 | LEAF_CDF / CDF_MEDIAN | 0.824645 | -0.360190 | 2.000000 | 1/30 |
| 2 | RESPONSE_CDF / RESPONSE_CDF_MEAN | 0.876761 | -0.049753 | 2.101499 | 1/30 |
| 3 | RECENT8_CDF_FALLBACK / RECENT8_POINT_CDF_MEAN_FALLBACK | 0.879280 | -0.064378 | 2.250000 | 12/148 |
| 4 | RECENT3_CDF_FALLBACK / RECENT3_POINT_CDF_MEAN_FALLBACK | 1.009631 | -0.090040 | 2.583333 | 27/218 |

Only 4 distinct tested procedures have comparable current-panel evidence; shortfall from five: 1. No extra CDF mean/median alias fills the list.

Separate expected-value leader among eligible saved mean products: **RESPONSE_CDF_MEAN**, MSE **1.157146**, RMSE **1.075707**, MAE **0.876761**. Legacy mixed CountA is not admitted as a mean.

### Completions

| Rank | Family / retained view | MAE (ATD: Brier) | Bias | p95 absolute error | Fallback scored/planned |
|---:|---|---:|---:|---:|---:|
| 1 | LEAF_CDF / CDF_MEDIAN | 5.118483 | -0.805687 | 14.000000 | 1/30 |
| 2 | CATBOOST / CATBOOST_COUNT_MEAN | 5.260677 | -0.971626 | 13.966916 | 1/30 |

Only 2 distinct tested procedures have comparable current-panel evidence; shortfall from five: 3. No extra CDF mean/median alias fills the list.

Separate expected-value leader among eligible saved mean products: **CDF_MEAN**, MSE **44.178448**, RMSE **6.646687**, MAE **5.196570**. Legacy mixed CountA is not admitted as a mean.

### Passing attempts

| Rank | Family / retained view | MAE (ATD: Brier) | Bias | p95 absolute error | Fallback scored/planned |
|---:|---|---:|---:|---:|---:|
| 1 | LEAF_CDF / CDF_MEDIAN | 7.772512 | -1.753555 | 21.500000 | 1/30 |
| 2 | HISTORY_DEPTH_CDF / CDF_H4_PLUS_TIMESTAMPED_DEPTH | 7.818086 | -2.303030 | 21.272581 | None/30 |
| 3 | RESPONSE_CDF / RESPONSE_CDF_MEAN | 7.892962 | -1.356935 | 20.654919 | 1/30 |
| 4 | HISTORY_DECAY_CDF / CDF_H3_TIME_WEIGHTED_TRAINING | 7.958584 | -2.025298 | 21.077734 | None/30 |
| 5 | HISTORY_CURRENT_CDF / CDF_H1_CURRENT_SEASON_TRAINING | 8.248874 | -1.740103 | 21.938199 | None/266 |

Other tested families retained: RECENT8_CDF_FALLBACK, HISTORY_PREVIOUS_CURRENT_CDF, POOLED8_COMMON, RECENT3_COMMON, RECENT3_CDF_FALLBACK.

Separate expected-value leader among eligible saved mean products: **RESPONSE_CDF_MEAN**, MSE **104.055610**, RMSE **10.200765**, MAE **7.892962**. Legacy mixed CountA is not admitted as a mean.

### Interceptions

| Rank | Family / retained view | MAE (ATD: Brier) | Bias | p95 absolute error | Fallback scored/planned |
|---:|---|---:|---:|---:|---:|
| 1 | LEAF_CDF / CDF_MEDIAN | 0.601896 | -0.573460 | 2.000000 | 1/30 |
| 2 | ZERO_INT_POINT / ZERO_INTERCEPTION_POINT_NOT_PROBABILITY | 0.616114 | -0.616114 | 2.000000 | 0/0 |
| 3 | RESPONSE_CDF / RESPONSE_CDF_MEAN | 0.630468 | 0.014393 | 1.374263 | 1/30 |
| 4 | RECENT8_CDF_FALLBACK / RECENT8_POINT_CDF_MEAN_FALLBACK | 0.635798 | -0.034162 | 1.500000 | 12/148 |
| 5 | RECENT3_CDF_FALLBACK / RECENT3_POINT_CDF_MEAN_FALLBACK | 0.643136 | -0.017845 | 1.666667 | 27/218 |

Separate expected-value leader among eligible saved mean products: **CDF_MEAN**, MSE **0.526397**, RMSE **0.725532**, MAE **0.628663**. Legacy mixed CountA is not admitted as a mean.

### Rushing yards

| Rank | Family / retained view | MAE (ATD: Brier) | Bias | p95 absolute error | Fallback scored/planned |
|---:|---|---:|---:|---:|---:|
| 1 | LEAF_CDF / CDF_MEDIAN | 18.425856 | -4.832700 | 55.750000 | 24/32 |
| 2 | CATBOOST / CATBOOST_MEDIUM | 18.625635 | -5.286977 | 55.116989 | 24/32 |

Only 2 distinct tested procedures have comparable current-panel evidence; shortfall from five: 3. No extra CDF mean/median alias fills the list.

Separate expected-value leader among eligible saved mean products: **CDF_MEAN**, MSE **696.278439**, RMSE **26.387088**, MAE **19.520373**. Legacy mixed CountA is not admitted as a mean.

### Rushing attempts

| Rank | Family / retained view | MAE (ATD: Brier) | Bias | p95 absolute error | Fallback scored/planned |
|---:|---|---:|---:|---:|---:|
| 1 | ORDERED_CDF / ORDERED_CDF:median | 3.619772 | -0.992395 | 10.000000 | 24/32 |
| 2 | ANALOG_UNIFORM / ANALOG_UNIFORM:median | 3.659696 | -0.990494 | 10.750000 | 24/32 |
| 3 | LEAF_CDF / CDF_MEDIAN | 3.661597 | -0.866920 | 10.750000 | 24/32 |
| 4 | ANALOG_RELEVANCE / ANALOG_RELEVANCE:median | 3.667300 | -0.990494 | 10.750000 | 24/32 |
| 5 | COUNT_A / COUNT_A_LEGACY_MIXED_POINT_REUSED | 3.742899 | -0.004880 | 9.528582 | 24/32 |

Other tested families retained: CATBOOST.

Separate expected-value leader among eligible saved mean products: **ORDERED_CDF:mean**, MSE **23.909217**, RMSE **4.889705**, MAE **3.771292**. Legacy mixed CountA is not admitted as a mean.

### Receptions

| Rank | Family / retained view | MAE (ATD: Brier) | Bias | p95 absolute error | Fallback scored/planned |
|---:|---|---:|---:|---:|---:|
| 1 | ORDERED_CDF / ORDERED_CDF:median | 1.247701 | -0.415900 | 4.000000 | 82/140 |
| 2 | LEAF_CDF / CDF_MEDIAN | 1.252569 | -0.404543 | 4.000000 | 82/140 |
| 3 | ANALOG_RELEVANCE / ANALOG_RELEVANCE:median | 1.267712 | -0.382910 | 4.000000 | 82/140 |
| 4 | ANALOG_UNIFORM / ANALOG_UNIFORM:median | 1.273661 | -0.383451 | 4.000000 | 82/140 |
| 5 | COUNT_A / COUNT_A_LEGACY_MIXED_POINT_REUSED | 1.315318 | -0.041951 | 3.556816 | 82/140 |

Separate expected-value leader among eligible saved mean products: **COUNT_A_MEAN**, MSE **3.331184**, RMSE **1.825153**, MAE **1.333367**. Legacy mixed CountA is not admitted as a mean.

### Receiving yards

| Rank | Family / retained view | MAE (ATD: Brier) | Bias | p95 absolute error | Fallback scored/planned |
|---:|---|---:|---:|---:|---:|
| 1 | LEAF_CDF / CDF_MEDIAN | 16.054624 | -6.384532 | 55.000000 | 82/140 |
| 2 | CATBOOST / CATBOOST_MEDIUM | 16.105430 | -6.168801 | 55.154454 | 82/140 |

Only 2 distinct tested procedures have comparable current-panel evidence; shortfall from five: 3. No extra CDF mean/median alias fills the list.

Separate expected-value leader among eligible saved mean products: **CDF_MEAN**, MSE **591.892661**, RMSE **24.328844**, MAE **16.932785**. Legacy mixed CountA is not admitted as a mean.

### Rush + receiving yards

| Rank | Family / retained view | MAE (ATD: Brier) | Bias | p95 absolute error | Fallback scored/planned |
|---:|---|---:|---:|---:|---:|
| 1 | LEAF_CDF / CDF_MEDIAN | 19.925906 | -6.391022 | 64.600000 | 82/140 |
| 2 | CATBOOST / CATBOOST_MEDIUM | 20.032110 | -6.146298 | 64.826903 | 82/140 |

Only 2 distinct tested procedures have comparable current-panel evidence; shortfall from five: 3. No extra CDF mean/median alias fills the list.

Separate expected-value leader among eligible saved mean products: **CDF_MEAN**, MSE **803.718978**, RMSE **28.349938**, MAE **21.013661**. Legacy mixed CountA is not admitted as a mean.

### Chart PPR (new target)

| Rank | Family / retained view | MAE (ATD: Brier) | Bias | p95 absolute error | Fallback scored/planned |
|---:|---|---:|---:|---:|---:|
| 1 | CHART_LEAF_CDF / LEAF_CDF_CHART_MEDIAN_V1 | 4.679406 | -1.475619 | 14.414000 | 78/85 |
| 2 | CHART_HGB / HGB_CHART_MEDIAN_V1 | 4.702027 | -1.346343 | 14.111965 | 78/85 |
| 3 | CHART_ROLE_LAW / ROLE_LAW_CHART_MEAN_V1 | 5.739089 | -1.968280 | 17.235000 | 0/0 |
| 4 | CHART_POSITION_PRIOR / POSITION_CHART_MEDIAN_2024 | 5.739191 | -1.967973 | 17.235000 | 0/0 |
| 5 | CHART_GLOBAL_PRIOR / GLOBAL_CHART_MEDIAN_2024 | 6.239232 | -2.344002 | 18.907000 | 0/0 |

Separate expected-value leader among eligible saved mean products: **LEAF_CDF_CHART_MEAN_V1**, MSE **41.610163**, RMSE **6.450594**, MAE **4.829280**. Legacy mixed CountA is not admitted as a mean.

### Anytime rushing/receiving TD

| Rank | Family / retained view | MAE (ATD: Brier) | Bias | p95 absolute error | Fallback scored/planned |
|---:|---|---:|---:|---:|---:|
| 1 | CATBOOST / CATBOOST_MEDIUM | 0.136472 | 0.002442 | 0.836685 | 82/140 |
| 2 | EQUAL_CDF_CAT_BLEND / TD_EQUAL_CDF_CAT | 0.136583 | 0.003756 | 0.830812 | 82/140 |
| 3 | LEAF_CDF / LAB_CDF | 0.136977 | 0.005069 | 0.824346 | 82/140 |

Only 3 distinct tested procedures have comparable current-panel evidence; shortfall from five: 2. No extra CDF mean/median alias fills the list.

## Pairing, uncertainty and remaining errors

- The exact original full-population1956 memberships, labels and fallback cohorts are reused. New ordered/analog metrics reproduce the same frozen CDF controls; no new row-level comparison occurs in this reconciliation. The common-learner attempt study has the same515planned/211supported QB population and authenticated frozenCDF control; training policy is its intended difference.
- Every existing full-population paired comparison/interval remains in the JSON. Missing pairwise intervals are marked unavailable; aggregate differences cannot reconstruct game covariance. Only six weeks are present. Selected lowest values are exposed minima, not universal guarantees.
- Ordered carries reduce medianMAE3.661597→3.619772; receptions1.252569→1.247701, with game95% intervals including zero. Carry/reception median biases worsen; carry p90 worsens while p95 improves. Three of four analog comparisons lose; uniformcarry improves only one total absolute-error unit. No negative result is removed.
- All unknown participation and played-missing outcomes remain; no zero imputation. Parent source receipts preserve historical as-of limitations. Current query coverage is not a real sportsbook offered-pool guarantee.

## Distribution, probability, markets and Week7

- Current proper-law results are retained separately. PointMAE does not select an over/under model. New analog/ordered laws lack a compatible frozenBASE proper-score comparator in this panel; no distribution superiority is established. CountA/CatBoost count objectives do not manufacture a predictive count law.
- ATD2026W1–6 Brier: CatBoost0.1364719698071096; equalblend0.1365833529639841; CDF0.13697735571021438. The tiny CatBoost lead does not itself admit a live switch.2025CDF led the separate2025panel.
- GenuineWeek7 primary comparisons remain their own five-game panel, with their captured clocks and exact paired rows. Current W1–6 reconstruction is not pooled with them. Week7 offered-probability lane has only two genuinely captured games; five-game point timing does not transfer to it.
- Offered-market2026W1–5 panels have different populations/timing/price qualifications and are retained separately. Their modernFootball, calibration, market and hybrid losses cannot be inserted into this generic current leaderboard. No new prices, EV decisions or paper returns were calculated.

## Operational shortlist and next admission

| Category | Existing operational-family candidates to census | Shortfall from5 | New admission still needed |
|---|---|---:|---|
| Passing yards | LEAF_CDF, CATBOOST | 3 | Current-source, artifact/wrapper and typedMAE view/future capture through retained owner; exact census pending. |
| Passing TDs | LEAF_CDF | 4 | Current-source, artifact/wrapper and typedMAE view/future capture through retained owner; exact census pending. |
| Completions | LEAF_CDF | 4 | Current-source, artifact/wrapper and typedMAE view/future capture through retained owner; exact census pending. |
| Passing attempts | LEAF_CDF | 4 | Current-source, artifact/wrapper and typedMAE view/future capture through retained owner; exact census pending. |
| Interceptions | LEAF_CDF | 4 | Current-source, artifact/wrapper and typedMAE view/future capture through retained owner; exact census pending. |
| Rushing yards | LEAF_CDF, CATBOOST | 3 | Current-source, artifact/wrapper and typedMAE view/future capture through retained owner; exact census pending. |
| Rushing attempts | LEAF_CDF, COUNT_A | 3 | Current-source, artifact/wrapper and typedMAE view/future capture through retained owner; exact census pending. |
| Receptions | LEAF_CDF, COUNT_A | 3 | Current-source, artifact/wrapper and typedMAE view/future capture through retained owner; exact census pending. |
| Receiving yards | LEAF_CDF, CATBOOST | 3 | Current-source, artifact/wrapper and typedMAE view/future capture through retained owner; exact census pending. |
| Rush + receiving yards | LEAF_CDF, CATBOOST | 3 | Current-source, artifact/wrapper and typedMAE view/future capture through retained owner; exact census pending. |
| Chart PPR (new target) | None admitted for this new chart contract | 5 | Chart current-source, private restoration and separate consumer target; old-site PPR remains fallback. |
| Anytime rushing/receiving TD | LEAF_CDF, CATBOOST, EQUAL_CDF_CAT_BLEND | 2 | Current-source, artifact/wrapper and typedMAE view/future capture through retained owner; exact census pending. |

Existing-family readiness is not proof of actual upcoming capture, and is not a new operational admission. Ordered/analog/ResponseCDF/history variants need their exact current-source, future-query, restoration, product and fallback packages before entrant capture. Research ranking includes unready candidates; shadow capture may begin once operational requirements pass. R0 and actual displayed forecasts remain additional references, not duplicates that fill a five-model quota.

The [public aggregate](PUBLIC_RESULTS.json) preserves the50-family historical catalogue plus new ordered/analog mechanisms,2025and2022–24 context, genuineWeek7 losses and distribution/probability/market panels. Exact source bindings remain in the private audit. EarlierXGBoost/LightGBM/HGB/NGBoost/FTN/hierarchical/threshold/copula/calibration/workload experiments are retained with their actual periods and failures; no earlier loss is transplanted into2026.

No new cached rescoring is requested: the identified MAE cells already exist. Remaining gaps need missing forecasts, law extraction, qualified new information or operational entry, each with its own finite allocation. No live forecasts, ranking or scheduler changed here.
