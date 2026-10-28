# 2026 weeks 1–6: five annual count challengers

Five fixed annual challengers supplied **14,995 new postgame reconstructed forecasts**: 2,999 offered player-game queries for each of five targets. The 20,993 control and paired-loss rows count repeated target/control comparisons; they are not 20,993 independent observations.

Touchdowns and attempts have very small observed MSE improvements against the source-matched annual CDF means. Interceptions, completions and rushing attempts have higher MSE. Every CDF game-cluster interval crosses zero. The previously reported small 2025 interception improvement reverses to a small loss here; neither season establishes a durable champion.

## Matched primary comparisons

Expected count means use MSE as the primary loss. Positive improvement favors the challenger. Each passing target has 211 supported QB outcomes from 515 offers, with 304 unknown participation states. Rushing has 526 supported RB outcomes from 668 offers, with 142 unknown. All comparisons cover 93 games and six weeks.

| Target | Supported primary rows | Challenger MSE | CDF MSE | MSE improvement | Nominal game-cluster 95% interval, challenger minus CDF |
|---|---:|---:|---:|---:|---|
| Passing touchdowns | 211 | 1.157146 | 1.158267 | +0.0967% | [-0.015632, +0.012915] |
| Passing attempts | 211 | 104.055610 | 104.078472 | +0.0220% | [-1.128643, +1.074566] |
| Interceptions | 211 | 0.526589 | 0.526397 | -0.0366% | [-0.004974, +0.004886] |
| Completions | 211 | 44.577931 | 44.178448 | -0.9042% | [-1.677085, +2.321461] |
| Rushing attempts | 526 | 24.645354 | 24.347098 | -1.2250% | [-0.166502, +0.771677] |

Week-cluster intervals are **N/A** because the unchanged shared routine requires at least eight clusters and this sample has six weeks. Game intervals use 500 whole-cluster PCG64 replicates, seed 1703, and nominal 95% percentile limits. This existing reporting rule adds no new provisional release gate. The comparisons remain exposed, descriptive evidence.

## Errors and coverage in original count units

| Target | MAE | RMSE | Bias | 95th percentile absolute error | Scored fallbacks / fallback offers | Supported zeros |
|---|---:|---:|---:|---:|---:|---:|
| Passing touchdowns | 0.876761 | 1.075707 | -0.049753 | 2.101499 | 1 / 30 | 57 |
| Passing attempts | 7.892962 | 10.200765 | -1.356935 | 20.654919 | 1 / 30 | 6 |
| Interceptions | 0.630468 | 0.725665 | +0.014393 | 1.374263 | 1 / 30 | 111 |
| Completions | 5.260677 | 6.676671 | -0.971626 | 13.966916 | 1 / 30 | 10 |
| Rushing attempts | 3.830508 | 4.964409 | +0.109563 | 9.634501 | 24 / 32 | 92 |

Each target retains all 2,999 offered rows: 2,084 supported played outcomes, 909 unknown participation states and six played rows with a missing statistic. The primary QB and RB cohorts have no played rows with a missing statistic. Unknown participation and missing statistics remain unscored; they never become zeros. All-role coverage and every weekly metric are retained in PUBLIC_METRICS_v2.json.

## Rushing carry controls

The new rushing CatBoost mean has MSE 24.645354. Corrected Count A has lower MSE, 24.216499: CatBoost is **1.7709% worse** against that mean control. The legacy mixed point has MSE **23.570845** and remains a separately reported empirical benchmark, ineligible as a count mean product.

| Rushing control | Mean eligible | Control MSE | CatBoost MSE improvement | Nominal game-cluster 95% interval |
|---|---|---:|---:|---|
| Corrected stored-prior Count A mean | Yes | 24.216499 | -1.7709% | [+0.003509, +0.863074] |
| Legacy Count A mixed point | No | 23.570845 | -4.5586% | [+0.422312, +1.775518] |

## Every week retained

Paired squared-error differences are challenger minus control; positive values are losing weeks for the challenger. No week is removed.

| Week | QB pairs | TD vs CDF | Attempts vs CDF | INT vs CDF | Completions vs CDF |
|---:|---:|---:|---:|---:|---:|
| 1 | 37 | +0.028957 | +2.166459 | +0.008481 | -3.683684 |
| 2 | 39 | -0.007915 | -0.215425 | +0.003055 | -2.869166 |
| 3 | 36 | +0.003475 | +1.899159 | -0.000755 | +1.830764 |
| 4 | 34 | -0.002708 | +1.336438 | -0.013224 | -0.213945 |
| 5 | 36 | -0.028699 | -2.736355 | -0.007027 | +3.422042 |
| 6 | 29 | +0.000033 | -3.168315 | +0.011637 | +5.195098 |

| Week | RB pairs | Rushing vs CDF | Rushing vs corrected Count A mean | Rushing vs legacy mixed point |
|---:|---:|---:|---:|---:|
| 1 | 89 | -0.008529 | +0.542046 | +1.391419 |
| 2 | 95 | +0.250661 | +1.226849 | +2.916362 |
| 3 | 89 | -0.047771 | +0.360868 | +1.136270 |
| 4 | 90 | +0.630728 | -0.120534 | +0.262860 |
| 5 | 85 | +0.979946 | +0.236704 | +0.236704 |
| 6 | 78 | -0.025388 | +0.248663 | +0.248663 |

## Method and source record

MSE = mean((forecast count mean − supported actual count)²). Improvement = 100 × (control MSE − challenger MSE) / control MSE. MAE, RMSE, bias and absolute-error percentiles use the original count units; MSE uses squared count units. Bias is forecast minus actual.

The three passing Response CDF procedures report stable expected counts. Completions and rushing use the fixed annual CatBoost medium procedure fitted with Poisson loss; these results use its point mean and supply no derived probability law. Method versions and the unchanged source policy and feature-builder versions are included in PUBLIC_METRICS_v2.json.

The actual original 91-column annual training source, schema, row order, index and full 467e9bf5… digest were recovered before the five 2026 fits. Query, cutoff, source and base-feature contracts match the retained CDF controls. Original TD/interception points passed exact stored-mean bit checks; attempts, completions and rushing use explicitly frozen law means. The original assumed kickoff-plus-seven-day availability rule remains a reconstruction assumption; publisher availability is unknown.

The ten-fit cap is fully consumed: nine models completed and the 2025 rushing-attempt fit failed. Earlier source, runtime and grading-admission failures remain preserved. This grading phase performed zero fits, model loads, inference calls, law calls or HTTP requests. No full-week-seven, prospective pregame, historical website-relative, probability or calibration comparison is supplied. No live model selection or deployment was made.

Requested agent setting: GPT-6.1 Sol / xhigh. Actual backend: UNATTESTED. Independent arithmetic reconciled all 14,995 candidate/label rows, 20,993 control and paired-loss rows, 96 summary/weekly checks and 14 interval checks. The original verifier then failed its general file-ownership classifier and remains FAILED; its final runtime check did not run. A separate metadata-only completion verified 54 owned CAS pairs and 99 reference hashes, with no managed mismatch. It distinguished seven external identical-content copies, including empty execution logs, from owned data. The earlier failed metadata collector is also retained. No NFL arithmetic was repeated, and the completed metadata process does not retroactively attest the failed process. These checks establish neither scientific qualification nor release readiness.
