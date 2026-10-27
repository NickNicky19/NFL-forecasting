# Qualified cached rushing and receiving grade, 2026-10-27

All 20 prespecified products completed on unchanged cached forecasts. CatBoost medium has the lowest restored-population mean MSE for both targets; distribution split CDF has the lowest rushing median MAE, and Leaf CDF has the lowest receiving median MAE. These were the prespecified primary controls. No other product improves on its primary control by point estimate. This result changes no model selection, live forecast, scheduler, or scientific qualification.

The new zeros affect evaluation only. Cached training and preprocessing are unchanged, and no model learned the new zero panel. This is an exposed 2024 REG reconstruction using current-vintage inputs and the existing seven-day assumption. It provides no genuine historical as-of result, prospective evidence, independent football observations, or live SITE win.

## Population and retained uncertainty

| Target | Offered | Original numeric | Prior zeros | New derived zeros | Restored numeric | Unknown remaining | Played missing | Quarantines |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Rushing attempts | 2047 | 1524 | 12 | 115 | 1651 | 384 | 12 | 0 |
| Receptions | 7148 | 5095 | 105 | 859 | 6059 | 1065 | 24 | 0 |

The 974 new target incidences represent 859 unique player-games, including 115 cross-target overlaps. All original numeric labels and the full old zero masks remain unchanged. Both restored cohorts cover 272 games and all 18 weeks. No played invalid or DNP rows were introduced. Every offered saved point is finite. Fallback points remain in the scored cohorts: 27 rushing and 114 receiving rows for every non-role-prior product; role prior uses its fallback on all 1,651/6,059 numeric rows.

Positive gain means lower loss than the named control; negative gain means higher loss. Means use MSE; saved CDF medians use MAE. The 95% interval is the paired candidate-minus-primary-control loss difference, so an interval below zero would favor the candidate. All intervals use the same 500 whole-week PCG64 draws with seed 1761. These development intervals do not turn this exposed reconstruction into confirmation evidence.

## Rushing attempts — mean products

Primary control: CatBoost medium. All products use the same 1651 restored numeric rows.

| Method | MSE | Gain vs primary | 95% paired loss difference | Gain vs Leaf | Bias | Absolute error p95 |
|---|---:|---:|---|---:|---:|---:|
| Leaf CDF | 22.4739 | -2.13% | [0.2113, 0.7294] | -0.00% | 0.2882 | 9.4536 |
| Threshold CDF | 23.7837 | -8.08% | [1.1493, 2.4024] | -5.83% | 0.0631 | 9.9669 |
| Distribution split CDF | 22.3482 | -1.56% | [0.0748, 0.6521] | 0.56% | 0.2887 | 9.4707 |
| Role prior | 51.3979 | -133.57% | [26.3908, 32.2336] | -128.70% | 0.5860 | 13.2619 |
| Count A mean v2 | 22.1927 | -0.85% | [-0.0437, 0.4168] | 1.25% | 0.2857 | 9.5391 |
| CatBoost medium | 22.0053 | -0.00% | [0.0000, 0.0000] | 2.08% | 0.2357 | 9.5808 |

## Rushing attempts — median products

Primary control: Distribution split CDF. All products use the same 1651 restored numeric rows.

| Method | MAE | Gain vs primary | 95% paired loss difference | Gain vs Leaf | Bias | Absolute error p95 |
|---|---:|---:|---|---:|---:|---:|
| Leaf CDF | 3.3131 | -0.37% | [-0.0046, 0.0277] | -0.00% | -0.7474 | 10.0000 |
| Threshold CDF | 3.3701 | -2.09% | [0.0313, 0.1106] | -1.72% | -1.0285 | 10.0000 |
| Distribution split CDF | 3.3010 | -0.00% | [0.0000, 0.0000] | 0.37% | -0.7365 | 10.0000 |
| Role prior | 5.7014 | -72.72% | [2.1881, 2.5850] | -72.08% | -2.1520 | 16.0000 |

## Receptions — mean products

Primary control: CatBoost medium. All products use the same 6059 restored numeric rows.

| Method | MSE | Gain vs primary | 95% paired loss difference | Gain vs Leaf | Bias | Absolute error p95 |
|---|---:|---:|---|---:|---:|---:|
| Leaf CDF | 3.0876 | -2.39% | [0.0547, 0.0904] | -0.00% | 0.2293 | 3.4848 |
| Threshold CDF | 3.2160 | -6.65% | [0.1646, 0.2404] | -4.16% | 0.3358 | 3.4310 |
| Distribution split CDF | 3.0802 | -2.15% | [0.0454, 0.0845] | 0.24% | 0.2297 | 3.4985 |
| Role prior | 5.2504 | -74.11% | [2.0021, 2.4407] | -70.05% | 0.4323 | 4.2170 |
| Count A mean v2 | 3.0293 | -0.46% | [0.0006, 0.0251] | 1.89% | 0.2010 | 3.4867 |
| CatBoost medium | 3.0156 | -0.00% | [0.0000, 0.0000] | 2.33% | 0.1866 | 3.5002 |

## Receptions — median products

Primary control: Leaf CDF. All products use the same 6059 restored numeric rows.

| Method | MAE | Gain vs primary | 95% paired loss difference | Gain vs Leaf | Bias | Absolute error p95 |
|---|---:|---:|---|---:|---:|---:|
| Leaf CDF | 1.2124 | -0.00% | [0.0000, 0.0000] | -0.00% | -0.1627 | 4.0000 |
| Threshold CDF | 1.2207 | -0.68% | [0.0012, 0.0153] | -0.68% | -0.2027 | 4.0000 |
| Distribution split CDF | 1.2169 | -0.37% | [-0.0012, 0.0096] | -0.37% | -0.1543 | 4.0000 |
| Role prior | 1.6473 | -35.87% | [0.3905, 0.4727] | -35.87% | -0.4557 | 5.0000 |

## Zero-panel sensitivity

Count A mean v2 improves MSE over Leaf continuity by 1.25% for rushing and 1.89% for receptions, but its MSE is 0.85% and 0.46% higher than CatBoost medium. CatBoost medium improves over Leaf by 2.08% and 2.33%. Distribution split rushing medians improve MAE over Leaf by 0.37%; the paired development interval for Leaf versus that control includes zero. Receiving Leaf medians remain the lowest point estimate; distribution split has 0.37% higher MAE and its paired interval includes zero.

The next table preserves the distinction between the previously restored population and the newly qualified zero panel. These are different evaluation cohorts; their loss levels are not a before/after model-training effect.

| Target | Product | Method | Previous restored loss | New zero-panel loss | Final restored loss |
|---|---|---|---:|---:|---:|
| Rush | mean MSE | Leaf CDF | 23.2146 | 12.5808 | 22.4739 |
| Rush | mean MSE | Threshold CDF | 24.6411 | 12.3315 | 23.7837 |
| Rush | mean MSE | Distribution split CDF | 23.0849 | 12.5085 | 22.3482 |
| Rush | mean MSE | Role prior | 50.7630 | 59.8777 | 51.3979 |
| Rush | mean MSE | Count A mean v2 | 23.0602 | 10.6055 | 22.1927 |
| Rush | mean MSE | CatBoost medium | 22.8925 | 10.1556 | 22.0053 |
| Rush | median MAE | Leaf CDF | 3.4499 | 1.4870 | 3.3131 |
| Rush | median MAE | Threshold CDF | 3.5137 | 1.4522 | 3.3701 |
| Rush | median MAE | Distribution split CDF | 3.4342 | 1.5217 | 3.3010 |
| Rush | median MAE | Role prior | 5.7539 | 5.0000 | 5.7014 |
| Rec | mean MSE | Leaf CDF | 3.2301 | 2.2247 | 3.0876 |
| Rec | mean MSE | Threshold CDF | 3.3062 | 2.6700 | 3.2160 |
| Rec | mean MSE | Distribution split CDF | 3.2232 | 2.2147 | 3.0802 |
| Rec | mean MSE | Role prior | 5.1800 | 5.6768 | 5.2504 |
| Rec | mean MSE | Count A mean v2 | 3.1996 | 1.9986 | 3.0293 |
| Rec | mean MSE | CatBoost medium | 3.1935 | 1.9382 | 3.0156 |
| Rec | median MAE | Leaf CDF | 1.2625 | 0.9092 | 1.2124 |
| Rec | median MAE | Threshold CDF | 1.2692 | 0.9267 | 1.2207 |
| Rec | median MAE | Distribution split CDF | 1.2658 | 0.9208 | 1.2169 |
| Rec | median MAE | Role prior | 1.6969 | 1.3469 | 1.6473 |

The complete private artifact also retains all five strata, MAE/MSE/RMSE, signed bias, absolute-error 90th/95th/max and threshold counts, exact paired cohort counts, fallback counts, literal saved forecasts, original/restored labels and states, provenance, and descriptive player/team/opponent metrics and coverage. Those private identities and row tables are not authorized for public raw export.

## Verification and deployment

The saved result passed immediate private-store readback. Independent verification reconciled the complete saved rows, all 20 products, paired whole-week intervals and every detailed group metric and coverage table. A verifier index-type assertion was corrected without changing the saved forecasts or results; its failed attempt remains recorded. No new model was selected or deployed by this comparison. Historical original website/raw-provider forecasts are unavailable for this panel, so the results do not establish a gain against the current website. Full row-level evidence remains private.

See [MAE, RMSE, bias, tails and complete offered coverage for every product](ALL_PRODUCT_ERRORS.md).
