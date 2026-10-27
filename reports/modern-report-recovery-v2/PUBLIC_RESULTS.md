# Retained modern-season forecast results

These are exposed current-vintage reconstructions, with 2025 and 2026 Weeks 1–6 reported separately. The original reconstructed forecasts were frozen on October 24, 2026, after the target games, with forecasts and scored rows retained in separate recorded phases. This new report recomputed summaries without fitting, loading models, generating forecasts or changing labels. It does not establish a prospective advantage or a deployment.

All numbers below use the original primary role population. Each cell shows primary error followed by scored/offered player-game rows. Signed yards use MAE; counts use MSE; anytime TD uses Brier. Errors in different units cannot be compared. Historical website and raw-provider forecasts are unavailable for these panels.

**Legacy COUNT_A uses warm Poisson objective points and median fallbacks. Its MSE remains descriptive under the original protocol; it is not the corrected count_A_mean_v2 and is not eligible as a complete conditional mean procedure.**

## 2025

| Category | Primary loss | CDF | CatBoost medium | Legacy COUNT_A |
|---|---|---:|---:|---:|
| Passing yards | MAE | 69.746988 (664/1359) | 69.531907 (664/1359) | Outside fixed catalog |
| Passing TDs | MSE | Unavailable | Outside fixed catalog | Outside fixed catalog |
| Completions | MSE | Unavailable | Outside fixed catalog | Outside fixed catalog |
| Passing attempts | MSE | 124.098901 (664/1359) | Outside fixed catalog | Outside fixed catalog |
| Interceptions thrown | MSE | 0.602122 (664/1359) | Outside fixed catalog | Outside fixed catalog |
| Rushing yards | MAE | 19.069604 (1566/2079) | 19.007497 (1566/2079) | Outside fixed catalog |
| Rushing attempts | MSE | Unavailable | Outside fixed catalog | 22.045606 (1566/2079) |
| Receptions | MSE | Unavailable | Outside fixed catalog | 2.829077 (5295/7271) |
| Receiving yards | MAE | 15.126912 (5295/7271) | 15.146870 (5295/7271) | Outside fixed catalog |
| Combined yards | MAE | 19.585080 (5295/7271) | 19.615066 (5295/7271) | Outside fixed catalog |
| Exact offensive PPR | Blocked | Blocked: exact labels | Blocked: exact labels | Blocked: exact labels |
| Anytime rushing/receiving TD | Brier | 0.138396 (5295/7271) | 0.138994 (5295/7271) | Outside fixed catalog |

| CatBoost vs CDF, exact paired rows | Signed primary improvement | Week 95% interval of candidate − CDF | Paired rows |
|---|---:|---|---:|
| Anytime rushing/receiving TD | -0.4317% | [-0.000050, 0.001179] | 5295 |
| Passing yards | +0.3084% | [-1.290302, 1.050443] | 664 |
| Receiving yards | -0.1319% | [-0.022208, 0.060599] | 5295 |
| Combined yards | -0.1531% | [-0.024869, 0.083115] | 5295 |
| Rushing yards | +0.3257% | [-0.194734, 0.070908] | 1566 |

Positive improvement means lower error. These nominal intervals are descriptive and do not adjust for repeated use or model selection. The 2026 panel has only six weeks, so no week interval is reported. Game intervals remain in the private complete aggregate.

## 2026 Weeks 1–6

| Category | Primary loss | CDF | CatBoost medium | Legacy COUNT_A |
|---|---|---:|---:|---:|
| Passing yards | MAE | 62.279621 (211/515) | 63.507248 (211/515) | Outside fixed catalog |
| Passing TDs | MSE | 1.158267 (211/515) | Outside fixed catalog | Outside fixed catalog |
| Completions | MSE | Unavailable | Outside fixed catalog | Outside fixed catalog |
| Passing attempts | MSE | Unavailable | Outside fixed catalog | Outside fixed catalog |
| Interceptions thrown | MSE | 0.526397 (211/515) | Outside fixed catalog | Outside fixed catalog |
| Rushing yards | MAE | 18.425856 (526/668) | 18.625635 (526/668) | Outside fixed catalog |
| Rushing attempts | MSE | Unavailable | Outside fixed catalog | 23.570845 (526/668) |
| Receptions | MSE | Unavailable | Outside fixed catalog | 3.283774 (1849/2458) |
| Receiving yards | MAE | 16.054624 (1849/2458) | 16.105430 (1849/2458) | Outside fixed catalog |
| Combined yards | MAE | 19.925906 (1849/2458) | 20.032110 (1849/2458) | Outside fixed catalog |
| Exact offensive PPR | Blocked | Blocked: exact labels | Blocked: exact labels | Blocked: exact labels |
| Anytime rushing/receiving TD | Brier | 0.136977 (1849/2458) | 0.136472 (1849/2458) | Outside fixed catalog |

| CatBoost vs CDF, exact paired rows | Signed primary improvement | Week 95% interval of candidate − CDF | Paired rows |
|---|---:|---|---:|
| Anytime rushing/receiving TD | +0.3690% | Unavailable: fewer than 8 weeks | 1849 |
| Passing yards | -1.9712% | Unavailable: fewer than 8 weeks | 211 |
| Receiving yards | -0.3165% | Unavailable: fewer than 8 weeks | 1849 |
| Combined yards | -0.5330% | Unavailable: fewer than 8 weeks | 1849 |
| Rushing yards | -1.0842% | Unavailable: fewer than 8 weeks | 526 |

Positive improvement means lower error. These nominal intervals are descriptive and do not adjust for repeated use or model selection. The 2026 panel has only six weeks, so no week interval is reported. Game intervals remain in the private complete aggregate.

## Secondary errors and fallback coverage

| Season | Category | Method | Scored | MAE | RMSE | Bias (forecast − actual) | p95 absolute error | Scored fallbacks |
|---|---|---|---:|---:|---:|---:|---:|---:|
| 2025 | Anytime rushing/receiving TD | CATBOOST_MEDIUM | 5295 | 0.281931 | 0.372818 | 0.007800 | 0.813305 | 105 |
| 2025 | Anytime rushing/receiving TD | LAB_CDF | 5295 | 0.283245 | 0.372016 | 0.005832 | 0.814443 | 105 |
| 2025 | Passing attempts | LAB_CDF | 664 | 8.663631 | 11.139969 | 1.655710 | 23.797957 | 7 |
| 2025 | Interceptions thrown | LAB_CDF | 664 | 0.640959 | 0.775965 | 0.053762 | 1.341966 | 7 |
| 2025 | Passing yards | CATBOOST_MEDIUM | 664 | 69.531907 | 88.743425 | 9.160429 | 181.742526 | 7 |
| 2025 | Passing yards | LAB_CDF | 664 | 69.746988 | 89.851886 | 11.265060 | 193.250000 | 7 |
| 2025 | Receptions | COUNT_A legacy mixed fallback | 5295 | 1.263207 | 1.681986 | 0.117721 | 3.401609 | 105 |
| 2025 | Receiving yards | CATBOOST_MEDIUM | 5295 | 15.146870 | 23.446005 | -4.576739 | 51.816320 | 105 |
| 2025 | Receiving yards | LAB_CDF | 5295 | 15.126912 | 23.512836 | -4.905949 | 52.000000 | 105 |
| 2025 | Rushing attempts | COUNT_A legacy mixed fallback | 1566 | 3.536498 | 4.695275 | 0.085122 | 9.795295 | 40 |
| 2025 | Combined yards | CATBOOST_MEDIUM | 5295 | 19.615066 | 28.992764 | -5.127917 | 61.818848 | 105 |
| 2025 | Combined yards | LAB_CDF | 5295 | 19.585080 | 28.995754 | -5.496695 | 62.000000 | 105 |
| 2025 | Rushing yards | CATBOOST_MEDIUM | 1566 | 19.007497 | 29.572930 | -7.101238 | 64.518996 | 40 |
| 2025 | Rushing yards | LAB_CDF | 1566 | 19.069604 | 29.498220 | -6.542146 | 65.000000 | 40 |
| 2026 | Anytime rushing/receiving TD | CATBOOST_MEDIUM | 1849 | 0.275713 | 0.369421 | 0.002442 | 0.836685 | 82 |
| 2026 | Anytime rushing/receiving TD | LAB_CDF | 1849 | 0.279280 | 0.370105 | 0.005069 | 0.824346 | 82 |
| 2026 | Interceptions thrown | LAB_CDF | 211 | 0.628663 | 0.725532 | 0.012970 | 1.378147 | 1 |
| 2026 | Passing TDs | LAB_CDF | 211 | 0.878612 | 1.076228 | -0.044886 | 2.080813 | 1 |
| 2026 | Passing yards | CATBOOST_MEDIUM | 211 | 63.507248 | 79.940527 | -4.341423 | 156.831839 | 1 |
| 2026 | Passing yards | LAB_CDF | 211 | 62.279621 | 79.369763 | -5.767773 | 158.500000 | 1 |
| 2026 | Receptions | COUNT_A legacy mixed fallback | 1849 | 1.315318 | 1.812119 | -0.041951 | 3.556816 | 82 |
| 2026 | Receiving yards | CATBOOST_MEDIUM | 1849 | 16.105430 | 25.266457 | -6.168801 | 55.154454 | 82 |
| 2026 | Receiving yards | LAB_CDF | 1849 | 16.054624 | 25.277080 | -6.384532 | 55.000000 | 82 |
| 2026 | Rushing attempts | COUNT_A legacy mixed fallback | 526 | 3.742899 | 4.854981 | -0.004880 | 9.528582 | 24 |
| 2026 | Combined yards | CATBOOST_MEDIUM | 1849 | 20.032110 | 29.199184 | -6.146298 | 64.826903 | 82 |
| 2026 | Combined yards | LAB_CDF | 1849 | 19.925906 | 29.114449 | -6.391022 | 64.600000 | 82 |
| 2026 | Rushing yards | CATBOOST_MEDIUM | 526 | 18.625635 | 27.366126 | -5.286977 | 55.116989 | 24 |
| 2026 | Rushing yards | LAB_CDF | 526 | 18.425856 | 26.898132 | -4.832700 | 55.750000 | 24 |

## Scientific limits

- These exposed historical results do not establish superiority over today's website. Original contemporary SITE/raw-provider forecasts are unavailable for these panels.
- CDF gaps remain 2025 passing TDs, completions, carries and receptions; 2026 completions, passing attempts, carries and receptions. Missing forecasts were not regenerated.
- Unknown participation, played-missing statistics and DNP remain separate from supported zeros. Full offered and primary-role populations are retained.
- Every displayed 2025 week interval crosses zero. The existing bootstrap reports week intervals as unavailable for six-week 2026 panels; this uncertainty rule is not an eight-week prerequisite for provisional deployment.
- The current-season-only, prior-plus-current, time-weighted and historical-relationships/current-role families were not compared by this cached recovery.
- Exact website PPR remains label-blocked. Correcting legacy Count A's fallback is a separately versioned forecasting experiment; these saved forecasts were not changed.
- Probability Brier scores are separate from point errors. No market-only, hybrid, +EV or current website-relative improvement is claimed here.
