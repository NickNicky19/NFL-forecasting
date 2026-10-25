# XGBoost touchdown output recovery

This is a separately versioned technical derivative of the six failed binary
cells in the [direct booster screen](../direct-booster-screen-v1/README.md).
It is not a new fitted model, football sample or confirmation period.

The original native float32 probabilities were exact complements in their
native dtype. Converting both components to float64 could fail the original
strict simplex check. The new canonicalizer validates that exact native
complement, retains the event probability unchanged and computes its complement
in float64. It neither clips probabilities nor relaxes the validation tolerance.
All original failures remain recorded.

## Executed replay: forecasts frozen, scoring stopped

The single registered invocation loaded six original fitted artifacts and
froze all six 2022–2024 forecasts, covering 51,744 query prediction row incidences.
No new fit or HTTP request occurred. Before scoring the first year, the wrapper
rejected the query/outcome context schema: `season_type` was absent from both
original files. No scored forecast file or accuracy report was produced.

Footer-only diagnosis found that all nine original persisted identity/context
fields exist with matching types, and yearly row counts agree: 8,686, 8,606 and
8,580. The wrapper had added a field outside that original persisted contract.
No season type, outcome or participation value is inferred from its absence.
A separately registered scoring-only continuation can use the already frozen
forecasts and the original nine-field contract, explicitly retaining this
metadata limitation. It must not rerun inference or erase this failed invocation.

| Receipt | SHA-256 |
|---|---|
| Execution freeze | `648486d5950d3c5cba9ad5d2e1231e510c90f01fa9be262cdc3b58865b7e11fb` |
| Global six-forecast freeze | `56fc8fae8495463ee50336df33f424f9908b93e261e62aa448eed82995510214` |
| Failed outer completion | `6a016a4d957173f9008d2646420f648d92e94a1b59966267767330b92b2d71a3` |
| Failure receipt | `15b9c25f14abbf26023b90be6c3c60003f730bea41e71701dd21b01424bc03d5` |

The invocation used 42.9543 wall seconds, 47.9540 observed CPU seconds,
493,547,520 bytes sampled combined RSS and 6,336,103 newly retained unique bytes.
It remained within its 120-second wall, 180-second CPU, 1 GiB and 16 MiB limits.
The original screen and this derivative remain separate FAILED executions.
Nothing here demonstrates better accuracy, prospective operation or release
readiness.

## Completed scoring-only continuation (v3)

The separately frozen [v3 policy](../../config/direct-xgboost-binary-scoring-v3.json)
used all six saved forecasts, exact original context and cached outcomes with
the unchanged scorers and controls. It completed with zero fits, predictions,
model loads or HTTP calls. Both earlier executions remain FAILED.

All annual, pooled, all-offered and primary-role results are retained in the
[full aggregate report](aggregate-report.json): 16 summaries, 80 paired
comparisons and both nomination decisions. The primary-role pooled cohort has
15,251 supported appearances, 815 games and 54 season-week blocks.

| Fixed XGBoost setting | Brier | Change versus CDF | Change versus role B | Decision |
|---|---:|---:|---:|---|
| Small | 0.141141369 | -0.1221% | +0.2995% | Not nominated |
| Medium | 0.141593576 | -0.4429% | -0.0200% | Not nominated |

Positive change means lower error. CDF Brier is 0.140969236; role B is
0.141565307 on these same pairs. The small setting also fails the role-B bias
regression check. These additions do not change the original screen's selected
category minima or produce a development nominee.

The continuation took 47.6470 wall seconds and 53.3782 observed CPU seconds,
with 629,538,816 bytes sampled combined RSS and 10,323,912 charged unique bytes.
The actual admission limit was **16 MiB**. Its inherited helper serialized a
**64 MiB reporting label**; that label is not the enforced admission limit.

| Completed receipt | SHA-256 |
|---|---|
| V3 execution freeze | `eb3abc6fc2a5b4c63d5d809cd4ef168314f8b19bb27146935503c798aa76d248` |
| Successful outer completion | `df6fda65d148c1336b5709419f49dea603bbb254c17395527c8622899676aac9` |
| Scored-row freeze | `d87173cfd82945e2df5d1539fc821e0381907ca29b100b7ac6731bf0975f3370` |
| Private aggregate report | `3f97fa78ce4dd43229dc0089c97a70888f71d7341678300ca5512ca9f97d9847` |

This completes the technical scoring recovery. It does not add independent
games or prospective evidence, repair participation/timing limitations, establish
a website-relative gain or qualify a release. Historical raw/SITE forecasts
remain unavailable for this panel. The source-matched CDF remains the stronger
reference than either recovered XGBoost setting.
