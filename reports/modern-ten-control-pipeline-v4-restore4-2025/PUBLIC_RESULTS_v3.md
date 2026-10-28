# 2025 passing count means: four additional challengers

Four retained annual models supplied **34,804 newly reconstructed forecasts**, with no new fits. The matched primary comparison uses **664 supported QB player-games across 272 games and 18 weeks** for each category. Of 1,359 offered QB opportunities, 695 have unknown participation and remain unscored; seven scored forecasts use the registered fallback.

These are exposed historical reconstructions under the original assumed seven-day input availability policy. They are not genuine pregame forecasts, a website-relative gain, or prospective confirmation. The earlier in-memory vectors were not retained; these are new forecasts from the saved models.

All four products are **expected counts**, evaluated primarily with MSE. The reference is the frozen source-matched annual CDF mean. Positive MSE improvements favor the challenger.

| Category | Challenger | Challenger MSE | CDF MSE | MSE improvement | Week-cluster 95% interval for MSE difference |
|---|---|---:|---:|---:|---|
| Passing touchdowns | Response CDF mean | 1.179024 | 1.178470 | -0.047% | [-0.008609, 0.010993] |
| Passing attempts | Response CDF mean | 124.523151 | 124.098901 | -0.342% | [-0.369412, 1.296387] |
| Interceptions | Response CDF mean | 0.598773 | 0.602122 | +0.556% | [-0.005080, -0.001428] |
| Completions | CatBoost medium mean | 55.168167 | 55.481118 | +0.564% | [-1.834154, 1.413116] |

The CDF has lower observed MSE for passing touchdowns and attempts. The interception Response CDF and completions CatBoost have small observed improvements. The interception interval is below zero in this nominal descriptive comparison; the other week intervals cross zero. These results alone do not establish a qualified improvement or an operational selection.

The touchdown challenger has slightly lower MAE despite higher MSE; the declared expected-count objective remains MSE. CatBoost supplies a point mean here, with no derived Poisson distribution or prop probability.

All 18 weeks, including losses, remain in [the detailed tables](READABLE_RESULTS.md) and [aggregate metrics](PUBLIC_METRICS_v2.json). The 2025 rushing-attempt challenger remains unavailable after its failed fit. No new website forecast was issued by this phase.

[Primary QB distribution diagnostics](PRIMARY_QB_PROPER_SCORES.md) are reported separately from the all-role diagnostic table.
