# Count fallback comparison: 2025 and 2026

Replacing median fallbacks with stored training means worsened primary MSE in all four tested season/category cells. This experiment provides no accuracy gain or promotion recommendation.

The candidate and comparator use identical warm Poisson objective forecasts. Only explicit fallback rows change: the original procedure uses a stored role/global median; the candidate uses that same prior’s mean. All warm forecast bits and fallback reasons were held fixed. No model was refitted or new prior estimated.

## Primary-role errors

| Season | Category | Scored rows | Original MSE | Mean-fallback MSE | Signed improvement |
|---|---|---:|---:|---:|---:|
| 2025 | Rushing attempts | 1566 | 22.045606 | 22.247834 | -0.9173% |
| 2025 | Receptions | 5295 | 2.829077 | 2.847217 | -0.6412% |
| 2026 | Rushing attempts | 526 | 23.570845 | 24.216499 | -2.7392% |
| 2026 | Receptions | 1849 | 3.283774 | 3.331184 | -1.4438% |

Positive improvement means lower error; all four values are negative. MSE is the registered count-mean loss. MAE measures a different point objective.

## Secondary errors

| Season | Category | Procedure | MAE | RMSE | Bias | p95 absolute error |
|---|---|---|---:|---:|---:|---:|
| 2025 | Rushing attempts | Original mixed | 3.536498 | 4.695275 | 0.085122 | 9.795295 |
| 2025 | Rushing attempts | Stored-prior mean | 3.567657 | 4.716761 | 0.155103 | 9.645785 |
| 2025 | Receptions | Original mixed | 1.263207 | 1.681986 | 0.117721 | 3.401609 |
| 2025 | Receptions | Stored-prior mean | 1.272452 | 1.687370 | 0.133832 | 3.399231 |
| 2026 | Rushing attempts | Original mixed | 3.742899 | 4.854981 | -0.004880 | 9.528582 |
| 2026 | Rushing attempts | Stored-prior mean | 3.797210 | 4.921026 | 0.118951 | 9.528582 |
| 2026 | Receptions | Original mixed | 1.315318 | 1.812119 | -0.041951 | 3.556816 |
| 2026 | Receptions | Stored-prior mean | 1.333367 | 1.825153 | -0.007311 | 3.549990 |

Bias is forecast minus outcome. MAE and RMSE worsened in all four cells. Bias and tail changes are retained rather than used to select a favorable metric.

## Fallback coverage

| Season | Category | Primary offered / scored | Fallback offered / scored | Original fallback MSE | Mean-fallback MSE |
|---|---|---:|---:|---:|---:|
| 2025 | Rushing attempts | 2079 / 1566 | 57 / 40 | 27.825000 | 35.742256 |
| 2025 | Receptions | 7271 / 5295 | 180 / 105 | 2.961905 | 3.876692 |
| 2026 | Rushing attempts | 668 / 526 | 32 / 24 | 20.250000 | 34.400587 |
| 2026 | Receptions | 2458 / 1849 | 140 / 82 | 2.024390 | 3.093436 |

The four complete vectors contain 23,400 offered player/category-game rows. Only 758 fallback rows change; unchanged scored warm rows have exactly zero paired error difference. Forecast and scoring coverage are unchanged. Unknown participation and missing statistics are excluded from scoring and retained separately from supported played zeros.

## Paired uncertainty

| Season | Category | Week 95% interval | Game 95% interval |
|---|---|---|---|
| 2025 | Rushing attempts | [-0.067197, 0.568587] | [-0.019218, 0.450822] |
| 2025 | Receptions | [0.006496, 0.033215] | [0.004893, 0.031377] |
| 2026 | Rushing attempts | N/A: fewer than eight weeks | [0.197469, 1.130733] |
| 2026 | Receptions | N/A: fewer than eight weeks | [0.018829, 0.074641] |

Intervals describe candidate MSE minus original MSE using 500 whole-week or whole-game bootstrap draws. They are nominal exposed-sample diagnostics, without adjustment for repeated use or model selection.

These are current-vintage historical reconstructions: 2025 covers 272 regular-season games/18 weeks; 2026 covers the 93 supported games in Weeks 1–6, conditional on supported played outcomes. They are not originally issued forecasts or independent prospective confirmation. The four cells are repeated method/year summaries rather than four independent validation samples. All original modern CDF controls for these targets are unavailable, and historical website/raw comparisons are unavailable.

Exact offensive PPR remains label-blocked in the wider twelve-category program. This correction does not test the four requested training-window families or establish scientific qualification, operational readiness, financial performance, or a live deployment.
