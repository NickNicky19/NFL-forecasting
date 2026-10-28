# Detailed 2025 four-challenger comparison

Expected count means; exposed historical reconstruction. Candidate and reference use matching identities, cutoff context, target outcomes and fallback populations. No missing or unknown participant is assigned a zero. All categories have 664 scored primary QB rows, 272 games and 18 weeks.

## Primary QB metrics

| Category | Procedure | MSE | MAE | RMSE | Bias | 95th percentile absolute error | Scored fallbacks | Supported zeros |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Passing touchdowns | Response CDF mean | 1.179024 | 0.883879 | 1.085829 | +0.021519 | 2.064035 | 7 | 233 |
| Passing touchdowns | Annual CDF mean | 1.178470 | 0.884272 | 1.085573 | +0.022391 | 2.040366 | 7 | 233 |
| Passing attempts | Response CDF mean | 124.523151 | 8.683362 | 11.158994 | +1.636886 | 23.938103 | 7 | 36 |
| Passing attempts | Annual CDF mean | 124.098901 | 8.663631 | 11.139969 | +1.655710 | 23.797957 | 7 | 36 |
| Interceptions | Response CDF mean | 0.598773 | 0.639614 | 0.773804 | +0.051959 | 1.346250 | 7 | 385 |
| Interceptions | Annual CDF mean | 0.602122 | 0.640959 | 0.775965 | +0.053762 | 1.341966 | 7 | 385 |
| Completions | CatBoost medium mean | 55.168167 | 5.807423 | 7.427528 | +0.905759 | 15.116369 | 7 | 51 |
| Completions | Annual CDF mean | 55.481118 | 5.857571 | 7.448565 | +1.082728 | 15.152322 | 7 | 51 |

Each procedure has 1,359 offered primary rows, 664 supported played outcomes, 695 unknown participation states, 28 fallback offers, seven scored fallbacks, no certified DNP rows and no played rows with a missing statistic. Unknown roster opportunities do not imply established appearances with missing statistics.

## Paired uncertainty

Intervals use whole-cluster paired squared-error differences, challenger minus CDF. They are nominal descriptive intervals on exposed development data, with 500 fixed bootstrap replicates.

| Category | Week-cluster 95% interval | Game-cluster 95% interval |
|---|---|---|
| Passing touchdowns | [-0.008609, 0.010993] | [-0.007415, 0.007878] |
| Passing attempts | [-0.369412, 1.296387] | [-0.353537, 1.180373] |
| Interceptions | [-0.005080, -0.001428] | [-0.006005, -0.000514] |
| Completions | [-1.834154, 1.413116] | [-2.407768, 1.376540] |

## Every week retained

Negative MSE differences favor the challenger. Positive weeks remain in the comparison.

| Week | Supported QB rows | TD MSE difference | Attempts MSE difference | INT MSE difference | Completions MSE difference |
|---:|---:|---:|---:|---:|---:|
| 1 | 34 | -0.003885 | -0.583659 | -0.002830 | +2.140899 |
| 2 | 41 | +0.013353 | -1.054018 | -0.003426 | -0.599026 |
| 3 | 42 | +0.014798 | +1.075889 | -0.002466 | -4.490523 |
| 4 | 39 | -0.013999 | +0.781096 | -0.010770 | +0.225895 |
| 5 | 34 | -0.029367 | +3.025297 | +0.002103 | +8.350445 |
| 6 | 33 | -0.002923 | +1.363110 | -0.004650 | -3.053180 |
| 7 | 39 | +0.010608 | +2.177559 | -0.004081 | -5.192404 |
| 8 | 34 | +0.028093 | -1.260855 | -0.007055 | -0.824897 |
| 9 | 31 | -0.001027 | +0.429655 | -0.009084 | -0.278244 |
| 10 | 34 | +0.010593 | +3.028021 | +0.002243 | -5.300589 |
| 11 | 37 | +0.006311 | +3.363750 | -0.006523 | +1.102451 |
| 12 | 32 | -0.015205 | +0.858648 | -0.002727 | +1.781773 |
| 13 | 37 | +0.023198 | +1.801315 | -0.006438 | +2.972617 |
| 14 | 36 | +0.007249 | -3.239357 | -0.003836 | -1.333391 |
| 15 | 38 | -0.039400 | +0.012565 | -0.006941 | +2.366043 |
| 16 | 43 | -0.029837 | -1.263484 | +0.002098 | -5.609765 |
| 17 | 37 | +0.041062 | +0.584536 | -0.003093 | +4.749791 |
| 18 | 43 | -0.007691 | -2.483775 | +0.005029 | -0.563418 |

## Distribution diagnostics

The three Response CDF laws also have exact full-support CRPS and log losses. This diagnostic uses **all 6,029 supported offered rows**, including secondary roles, rather than only the primary QB cohort. It should not be compared with the primary QB MSE table or interpreted as a primary QB calibration test. CatBoost remains a point-only product.

| Response target | CRPS | Negative log probability | Infinite log losses |
|---|---:|---:|---:|
| Passing touchdowns | 0.065626 | 0.197285 | 0 |
| Passing attempts | 0.668686 | 0.458810 | 0 |
| Interceptions | 0.042859 | 0.154062 | 0 |

The full-query, cutoff, role and 256-row law partition is preserved during scoring replay, with exact stored mean bits checked. Unsupported labels are masked before scoring. No probability calibration, odds comparison, selection-policy fit, future confirmation, or website deployment is supplied by this comparison.

The 2025 rushing-attempt challenger remains a failed fit dependency. Its failure and all earlier attempts remain in the evidence.
