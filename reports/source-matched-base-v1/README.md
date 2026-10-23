# Source-matched historical benchmark

Status: fitted and scored; final report acceptance pending. No promotion.

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
their hashes will be linked here after final acceptance. The website repository
has not been modified or deployed.
