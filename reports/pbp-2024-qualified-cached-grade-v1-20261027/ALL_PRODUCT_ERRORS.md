# All 20 cached products: error, tails and coverage

This separate read-only summary copies the existing retained aggregate metrics. It performs no new scoring, fit or inference and changes no bound plan, code or terminal reference. Every row uses the final restored numeric population, including saved fallback points.

MAE, RMSE, bias and absolute-error tails are in original units: rushing attempts or receptions per player-game. MSE is in squared count units. Bias is forecast minus actual, so positive values indicate overprediction. Mean products have primary MSE and saved CDF median products have primary MAE; MAE and RMSE are shown for all products for interpretation. Count A and CatBoost have mean products only.

## All product errors

| Target | Product | Method | Scored n | MAE | MSE | RMSE | Bias |
|---|---|---|---:|---:|---:|---:|---:|
| Rush attempts | mean | Leaf CDF | 1651 | 3.6219 | 22.4739 | 4.7407 | 0.2882 |
| Rush attempts | mean | Threshold CDF | 1651 | 3.7234 | 23.7837 | 4.8768 | 0.0631 |
| Rush attempts | mean | Distribution split CDF | 1651 | 3.6137 | 22.3482 | 4.7274 | 0.2887 |
| Rush attempts | mean | Role prior | 1651 | 6.0476 | 51.3979 | 7.1692 | 0.5860 |
| Rush attempts | mean | Count A mean v2 | 1651 | 3.5396 | 22.1927 | 4.7109 | 0.2857 |
| Rush attempts | mean | CatBoost medium | 1651 | 3.5306 | 22.0053 | 4.6910 | 0.2357 |
| Rush attempts | median | Leaf CDF | 1651 | 3.3131 | 22.2774 | 4.7199 | -0.7474 |
| Rush attempts | median | Threshold CDF | 1651 | 3.3701 | 23.4973 | 4.8474 | -1.0285 |
| Rush attempts | median | Distribution split CDF | 1651 | 3.3010 | 22.0618 | 4.6970 | -0.7365 |
| Rush attempts | median | Role prior | 1651 | 5.7014 | 55.6856 | 7.4623 | -2.1520 |
| Receptions | mean | Leaf CDF | 6059 | 1.3526 | 3.0876 | 1.7571 | 0.2293 |
| Receptions | mean | Threshold CDF | 6059 | 1.4185 | 3.2160 | 1.7933 | 0.3358 |
| Receptions | mean | Distribution split CDF | 6059 | 1.3523 | 3.0802 | 1.7551 | 0.2297 |
| Receptions | mean | Role prior | 6059 | 1.8821 | 5.2504 | 2.2914 | 0.4323 |
| Receptions | mean | Count A mean v2 | 6059 | 1.3268 | 3.0293 | 1.7405 | 0.2010 |
| Receptions | mean | CatBoost medium | 6059 | 1.3194 | 3.0156 | 1.7365 | 0.1866 |
| Receptions | median | Leaf CDF | 6059 | 1.2124 | 3.0926 | 1.7586 | -0.1627 |
| Receptions | median | Threshold CDF | 6059 | 1.2207 | 3.1480 | 1.7743 | -0.2027 |
| Receptions | median | Distribution split CDF | 6059 | 1.2169 | 3.1066 | 1.7626 | -0.1543 |
| Receptions | median | Role prior | 6059 | 1.6473 | 5.2763 | 2.2970 | -0.4557 |

## Absolute errors and fallback coverage

P90, P95 and max are absolute errors in the same original count units. The last two tail columns count rows with absolute error at least 5 or at least 50. Fallback counts refer to the numeric scored cohort; fallback rows remain in every applicable error metric.

| Target | Product | Method | Absolute P90 | Absolute P95 | Absolute max | Error ≥5 rows | Error ≥50 rows | Scored fallbacks |
|---|---|---|---:|---:|---:|---:|---:|---:|
| Rush attempts | mean | Leaf CDF | 7.7381 | 9.4536 | 24.4172 | 411 | 0 | 27 |
| Rush attempts | mean | Threshold CDF | 7.8241 | 9.9669 | 24.1994 | 409 | 0 | 27 |
| Rush attempts | mean | Distribution split CDF | 7.7381 | 9.4707 | 24.2421 | 413 | 0 | 27 |
| Rush attempts | mean | Role prior | 10.2619 | 13.2619 | 26.2619 | 983 | 0 | 1651 |
| Rush attempts | mean | Count A mean v2 | 7.7381 | 9.5391 | 24.8055 | 403 | 0 | 27 |
| Rush attempts | mean | CatBoost medium | 7.7381 | 9.5808 | 24.6197 | 391 | 0 | 27 |
| Rush attempts | median | Leaf CDF | 8.0000 | 10.0000 | 26.0000 | 428 | 0 | 27 |
| Rush attempts | median | Threshold CDF | 8.0000 | 10.0000 | 26.0000 | 443 | 0 | 27 |
| Rush attempts | median | Distribution split CDF | 8.0000 | 10.0000 | 26.0000 | 435 | 0 | 27 |
| Rush attempts | median | Role prior | 13.0000 | 16.0000 | 29.0000 | 894 | 0 | 1651 |
| Receptions | mean | Leaf CDF | 2.6874 | 3.4848 | 9.6146 | 100 | 0 | 114 |
| Receptions | mean | Threshold CDF | 2.6772 | 3.4310 | 9.6093 | 98 | 0 | 114 |
| Receptions | mean | Distribution split CDF | 2.6769 | 3.4985 | 9.5301 | 101 | 0 | 114 |
| Receptions | mean | Role prior | 2.7830 | 4.2170 | 11.7603 | 208 | 0 | 6059 |
| Receptions | mean | Count A mean v2 | 2.7042 | 3.4867 | 9.6089 | 102 | 0 | 114 |
| Receptions | mean | CatBoost medium | 2.7050 | 3.5002 | 9.6630 | 101 | 0 | 114 |
| Receptions | median | Leaf CDF | 3.0000 | 4.0000 | 10.0000 | 178 | 0 | 114 |
| Receptions | median | Threshold CDF | 3.0000 | 4.0000 | 10.0000 | 186 | 0 | 114 |
| Receptions | median | Distribution split CDF | 3.0000 | 4.0000 | 10.0000 | 178 | 0 | 114 |
| Receptions | median | Role prior | 4.0000 | 5.0000 | 13.0000 | 386 | 0 | 6059 |

## Offered population and label coverage

Each product retains its full original offered population. All 20 products have zero missing or invalid saved offered points. Numeric scoring coverage is limited by the retained actual-label state; unknown and played missing outcomes are not converted to zeros.

| Target | Offered | Finite offered points per product | Original numeric | Prior qualified zeros | New derived zeros | Final scored numeric per product | Unknown remaining | Played missing | Games / weeks scored |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Rush attempts | 2047 | 2047 | 1524 | 12 | 115 | 1651 | 384 | 12 | 272 / 18 |
| Receptions | 7148 | 7148 | 5095 | 105 | 859 | 6059 | 1065 | 24 | 272 / 18 |

Both targets have zero quarantined claims, zero played invalid labels and zero DNP rows in these offered populations. The 974 newly qualified target incidences represent 859 unique player-games, with 115 cross-target overlaps. The complete private artifact preserves all five cohort strata and descriptive player/team/opponent summaries.

## Scope and interpretation

The new zeros affect evaluation only. Cached training and preprocessing remain unchanged, and no model learned this new zero panel. This is an exposed 2024 REG reconstruction with current-vintage inputs and the existing seven-day assumption. It provides no genuine historical as-of result, prospective evidence or live SITE win. No production selection or scientific qualification changes follow from these metrics.

Prespecified primary controls were CatBoost medium for both mean products, distribution split CDF for rushing median products, and Leaf CDF for receiving median products. The separate readable results report retains paired control comparisons and the fixed 500 whole-week PCG64 seed 1761 development intervals.


Only derived aggregate errors are published; full source and row-level evidence remain private.
