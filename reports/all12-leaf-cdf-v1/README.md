# Twelve-category empirical distribution study

One fixed study completed **66 fits**, with no failed trials, across eleven numerical categories. Exact PPR retains its six blocked annual cells. Twelve individual category owners supplied contracts; one shared pipeline ran every fit, and a separate reviewer checks saved artifacts.

## New historical results

**These are gains against a pooled-history control, not the website.** Both feature panels are retained. The table uses the prespecified lower-median MAE (native category units), except anytime TD, which uses probability Brier score. Primary role populations differ; category errors are never pooled. Every scored category spans 854 games and 66 season-week blocks including postseason. All 2022–2024 evaluation data were already exposed.

| Category | Matched player-games | Pooled error | Base / context error | Base / context gain vs pooled |
|---|---:|---:|---:|---:|
| Passing yards | 2,049 | 73.302682 | 67.526598 / 66.573939 | +7.88% / +9.18% |
| Passing TDs | 2,049 | 0.883939 | 0.765739 / 0.760859 | +13.37% / +13.92% |
| Completions | 2,049 | 6.166736 | 5.711079 / 5.671547 | +7.39% / +8.03% |
| Pass attempts | 2,049 | 9.076338 | 8.389946 / 8.306003 | +7.56% / +8.49% |
| Interceptions thrown | 2,049 | 0.699747 | 0.625183 / 0.623719 | +10.66% / +10.87% |
| Rushing yards (RB) | 4,801 | 22.728293 | 19.414289 / 19.303895 | +14.58% / +15.07% |
| Rush attempts (RB) | 4,801 | 4.258878 | 3.481150 / 3.465320 | +18.26% / +18.63% |
| Receptions | 16,246 | 1.453835 | 1.261541 / 1.259695 | +13.23% / +13.35% |
| Receiving yards | 16,246 | 18.606186 | 16.074111 / 16.074295 | +13.61% / +13.61% |
| Rush + receiving yards | 16,246 | 23.742480 | 20.591222 / 20.610304 | +13.27% / +13.19% |
| Exact offensive PPR | — | — | — | Blocked scoring-source contract |
| Anytime rush/receiving TD | 16,246 | 0.144872 | 0.139134 / 0.139039 | +3.96% / +4.03% |

Each fixed panel's same-law mean, RMSE, signed bias, p95 misses, proper scores, calibration, fallback and full-population coverage are retained in [the twelve-category matrix](category-status.json). Nominal 95% game/week intervals use 500 draws and are unadjusted descriptive intervals. No panel is selected as a winner and no category is qualified for deployment.

## Adverse findings and limits

Median points lower MAE while some categories underpredict more. Examples: context RB rushing yards bias is -6.95 yards, receiving yards -5.96 and combined yards -6.79. The context interception median also worsens RMSE by 14.92% versus pooled, despite its lower MAE. The corresponding mean forecasts are scored separately; a lower median is never relabelled an expected mean. Context adds little to several receiving targets and slightly worsens receiving/combined median MAE. Direct combined-yard means remain nonadditive with independently fitted components (mean absolute gap 1.80 yards; maximum 25.51); no joint-law or accounting-coherence qualification is claimed. Passing count mean inequalities had no violations in the aligned audit.

Exact PPR has no qualified outcome contract in this panel. The strict adapter preserves explicit zeros, negative scores, missing components, DNP and unknown participation. Generic provider fantasy totals and absent rare-event fields are not substituted.

## Website-relative evidence remains separate

See the [original website scorecard](../methods-resumption-20261022/website-comparison.md). Its strongest lead remains the reconstructed passing-yard H3 method: 20.16% lower MAE on 27 matched observations in 13 games from one exposed week, with worse underprediction. That method is different from these forests. Other original category gains, losses and mixed results remain in the matrix; historical control gains do not transfer to website forecasts.

## Replay, software and resources

[Method/config](method-config.json), [model and forecast hash manifests](model-manifests.json), and [inference/failure/recovery contracts](../../docs/EMPIRICAL_CDF_RESEARCH.md) accompany this report. Private row-level/model inputs remain retained; no raw feed or player rows are redistributed.

The actual run took 441.01 wall seconds and about 541.47 total CPU seconds; peak trial RSS was 640,794,624 bytes, aggregation peak RSS was 549,494,784 bytes, and outputs were about 268 MB. All declared resource limits held. The final software suite passed 423 tests; those fictional/regression checks add no NFL evidence. Separate read-only review independently accepted all 66 model artifacts, saved forecast laws and report arithmetic, including 198 paired intervals and 56 saved reference fixtures. This verifies implementation and arithmetic; it adds no NFL games or independent confirmation. A separate review receipt binds final public content. No website write, default switch, workflow dispatch, scheduler activation or new recorder occurred.
