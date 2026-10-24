# Source-matched historical benchmark

Status: completed; independent numerical and integrity review passed. No promotion.

[All comparisons](aggregate-report.md) · [Complete aggregate results](aggregate-report.json)
· [Twelve-category matrix](category-status.json) · [Method/source manifest](method-manifest.json)
· [Exact execution wrappers](execution-code/README.md)

This experiment directly addresses the owner's October 23 independent audit:
refit the existing empirical leaf CDF, absolute-error boosting, Poisson count
and role boosting, recent and pooled controls on **identical permitted inputs,
player-games, chronological cutoffs and outcome qualification**.

The fixed development panel is regular-season 2022–2024, trained on earlier
seasons starting in 2019. All these evaluation years are exposed. The input is
a later source vintage with a reconstructed seven-day availability assumption,
not an authentic archived pregame feed. Historical raw Sleeper and website
forecasts are unavailable for this panel. These results cannot establish a
website-relative or prospective gain.

## Main findings

The common scored primary populations cover 815 games and 54 season-week blocks:
1,960 QB appearances for each passing category, 4,558 RB appearances for rushing,
and 15,251 RB/WR/TE appearances for receiving, combined yards and anytime TD.
These categories overlap; their row counts must not be added as independent
observations. Full offered primary populations are 4,091 QB, 6,235 RB and 21,504
skill-player opportunities respectively.

CDF has lower primary error than the original HGB on ten of eleven supported
categories; combined-yard MAE is 21.025703 versus 21.019873, **0.0277% worse**.
Against HGB, passing-attempt MAE improves 0.5763% and anytime-TD Brier improves
0.1471%; both paired week intervals cross zero. Several other differences are
small. These are descriptive error differences, not prediction-hit percentages
or twelve qualified improvements.

The large rushing differences against the weak pooled HGB must face the stronger
role model: CDF rushing-yard MAE is 19.718956 versus role B's 19.839430, a 0.6072%
reduction; carry MAE is 3.544976 versus 3.709749, a 4.4416% reduction. Bias and
tail tradeoffs remain in the full table. CDF's passing-yard p95 absolute miss
is 174 yards versus HGB's 169.704503 despite lower primary MAE.

Forecast products also differ. CDF's interception **median** MAE is 0.623980
versus count A's 0.679580, but median RMSE is 1.005343 versus 0.831823 and bias
is -0.477041 versus -0.004294. Its separately saved **mean** has RMSE 0.824055
and bias +0.012315. A median point result cannot certify an expected-count or
threshold-probability product. No post-hoc bias offset or probability clipping
was fitted.

## What ran

- 168 estimator attempts and 66 recent/pooled reference calls, without retries.
- 198 frozen supported method/year/target packages; 18 exact-PPR slots blocked.
- One later first-scoring phase wrote all 198 main and 33 CDF-prior scored files.
- Fixed numeric primary loss: point MAE; anytime-TD primary loss: Brier.
  CDF lower median and mean have separate scoring. Numeric boosting/reference
  points acquire no invented probability law.
- All annual/pooled and primary-role/all-offered comparisons are retained.
  Paired uncertainty uses 500 PCG64 draws, seed 1703, whole-game and whole-week
  clusters, nominal 95% linear-percentile intervals. These are exposed-sample
  diagnostics, not a promotion or multiplicity certificate.

Coverage-field note: inherited paired-comparison `offered_rows` and
`supported_played_rows` describe the full aligned offered population even in a
`primary_roles` contrast. `paired_rows` is correctly role filtered. Use each
population's separate summaries for offered/unknown/missing/fallback coverage;
the compact matrix does so explicitly.

Exact recipes and budgets are in the [original registration](../../config/source-matched-base-benchmark-v1.json),
[runner](../../nfl_lab/source_matched_benchmark.py),
[unchanged reporting helper](../../nfl_lab/source_matched_reporting.py) and
[report-only v2 policy](../../config/source-matched-frozen-report-v2.json).

## Retained technical failures

The original job stopped at its 1,200-second wall limit after all forecasts
were frozen, before scoring began. Its authoritative receipt reports
1,198.815180 wall seconds and 1,269.298613 CPU seconds. Repeated whole-store
verification scans were the bottleneck. A separately reviewed batch verifier
preserves the same integrity, ownership, hardlink and quota checks while holding
the same writer lock; the original failure and limits remain recorded.

The separate first-score recovery used 318.121865 wall seconds and 331.776467
CPU seconds. All scoring completed, but the final anytime-TD report rejected
380 raw CDF endpoints above 1 by at most 4.440892098500626e-16. Independent
inspection traced this to binary64 cumulative-mixture summation. Frozen event
probabilities were valid and bit-identical to the stored points and means.
No strict check was relaxed, and the failed run/raw rows were retained.

Report-only v2 uses a separately versioned analytic Bernoulli diagnostic view
from the same saved event probability. Only the two scored CDF brackets, CRPS
and log score are derived again. All identities, outcomes, states, points,
probabilities, means, quantiles and variances remain unchanged. It reads no
models, feature tables, queries or new outcome partitions and performs no
new fitting, forecast inference or model-law evaluation. Raw diagnostic values,
invalid counts, differences and both failed receipts remain available privately.
Its separate one-invocation budget is 300 wall/450 CPU seconds, two threads and
2 GiB combined RSS; it does not reset either failed budget.

Report-only v2 completed in **144.954284 wall / 151.692386 CPU seconds**, with
683,474,944 bytes sampled peak combined RSS. All three sequential invocations
together used 1,661.891330 wall / 1,752.767466 CPU seconds; their maximum sampled
combined RSS was 760,012,800 bytes. The two earlier invocations remain FAILED.
Final retained private unique-inode bytes were 174,138,433 of 536,870,912.
No new fit, forecast inference, model-law execution, source/outcome-partition
semantic read or HTTP request occurred in v2.

Independent review reconciled all 616 method/population/period summary cells
and 1,144 paired contrasts to the same cached rows, checked all 1,763 input/code
bindings, all six derivative views, all 30 declared annual alias pairs, and all
output hashes. Eleven already-written paired files were byte identical after
reaggregation. This verifies arithmetic and integrity; it adds no NFL evidence.

The analytic diagnostic view preserves frozen quantiles. A future complete law
version must separately qualify CDF, log mass, CRPS, variance and quantile
consistency: changing CDF arithmetic can move a binary quantile at a floating
point tie. No old point, quantile, model or trial was silently replaced here.

## Coverage and interpretation

Independent complete participation and played-zero evidence remain unresolved.
Positive official physical activity can establish playing; absent activity,
roster status and missing fields do not establish zero outcomes. Unknown rows
retain offered opportunities and are not scored as zero. Primary roles are QB
for passing, RB for rushing, and RB/WR/TE for receiving, combined yards and
anytime TD; all offered positions are reported separately.

Exact website offensive PPR remains blocked by incomplete qualified labels for
its full scoring contract. No generic fantasy total substitutes for that target.
The registered reception half-adjustment and original RB protocol are unchanged.
Combined yards are evaluated independently. These fits do not demonstrate a
participation model, news/injury effects, calibrated numeric boosting laws,
independent confirmation, operational hosted acceptance or a live replacement.

Raw sources, fitted weights, player/game rows, forecasts, scored rows, paired
losses and reference fixtures stay private. Reviewed aggregate exports and
their hashes are recorded in the publication manifest. The prepared player,
team and opponent subgroup consumer has not executed: synthetic profiling
identified an efficiency prerequisite under its unchanged 300-second cap.
There are no subgroup winner claims.

Separately reviewed daily identity/state-budget and exact publication-scope
software repairs were integrated after this benchmark's frozen code checks.
Their 192 combined fictional checks passed; actual new-source/runtime assembly,
legacy publication-receipt qualification and hosted handover remain pending.
Use the benchmark's frozen snapshot, not later runtime code, to interpret its
artifacts. No scheduler, default model or website was changed or deployed.
