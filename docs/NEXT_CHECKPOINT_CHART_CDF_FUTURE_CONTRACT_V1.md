# Prepared chart-CDF future-query contract

This is a new research family for `nick-chart-ppr-v1`. Its historical reference
adapter replay passed. It is not wired into the producer or website and is not
a replacement for the old website PPR contract. Technical replay is not Week8
capture.

## Exact product

Let `S` be the sixteen-component chart score. Signed official integer yards and
count components give the exact lattice `S = Z / 50`, with signed integer `Z`.
Labels must pass `abs(50*S - rint(50*S)) <= 1e-8`; invalid labels abort rather
than being rounded into eligibility. Means need not lie on the outcome lattice.

The fixed32-tree leaf CDF uses95% empirical leaf mass plus5% full-support,
signed discrete-Laplace role prior. The prior is fitted to all5,589 qualified
2024 chart labels, including qualified prior-only rows with unavailable
features. Forest fitting uses the same feature-admitted rows as the retained
HGB pilot. Cold/unknown-feature histories use the corresponding full-support
role/global prior as a complete law, not a mean/median mixture.

Outputs are separately named exact-law mean, lower0.5-quantile median, p10 and
p90. FullCDF scoring uses exactCRPS in chart points and log probability mass on
the0.02-point lattice. Neither an anytime-TD probability nor another website
fantasy score is substituted for missing chart primitives. No nonnegative
clipping applies to scores or future output.

## Trusted model

`nfl_lab/next_checkpoint_chart_cdf_inference.py` loads only model bytes whose
SHA256 matches the reviewed manifest. The expected digest must come from the
approved versioned artifact registry, not from a request containing the pickle.
The model must identify `chart_lattice_002_v1`, signed-integer support, the exact
32 raw feature names, registered five positions and32 trees. The frozen
private research capsule retains the inference model, training bindings,
query-leaf assignments and reference outputs.

## Query schema

One row per canonical season/week/game/player, with team, opponent and position
(QB/RB/FB/WR/TE). The approved producer must supply the current player/game/team
identity bridge and current roster position; postgame position metadata used by
the historical study is not a future roster source.

Required metadata: timezone-aware cutoff and kickoff, explicit maximum feature
availability (or unknown), approved input-source-policy SHA256 and the exact
32 lagged input fields. Individual missing numeric fields remain missing and
use the trained design's median plus missing indicator. An absent feature query,
unknown source clock, cold history or unseen role takes an explicitly named
prior fallback. The cutoff must not exceed kickoff, and any known feature clock
must be strictly before the cutoff. Unknown source time is never fabricated.

The model is conditional on the player having played. It supplies no learned
participation/DNP probability and no automatic numerical injury/news penalty.
Caller must retain DNP/unknown/played-zero outcomes separately. An input-source
hash authenticates a contract, not actual publication truth or timestamp quality.

## Failure and consumer behavior

Wrong artifact, source policy, identity duplication, target-game outcome input,
unsupported position or future/equal source clock fails closed. The producer
must preserve the attempted opportunity and its declared fallback/abstention;
no silent complete-case deletion or legacy-scoring relabel is permitted.

A future same-chart consumer can choose the median for MAE or mean for MSE under
a separately versioned policy. Exact outputs must retain target, functional,
model/source/configuration identities and clocks. Old-site PPR fallback remains
an explicitly different target and is never called a chart forecast.

## Remaining acceptance before entry

1. **Completed technical replay:** separate root/independent seal
   `1ff5523bff566087e225d9ef056345df945448459846289b1615d76b34da185a`
   authorized one trusted load and one combined inference call. All2,117 original
   rows exactly reproduced mean, lower median, p10 and p90 (maximum difference0)
   and fallback identities. Four fictional unseen queries exercised warm,
   cold, unknown-clock and missing-query paths. Wrong model/source identities,
   duplicate queries, outcome fields and equal source/cutoff were rejected.
   There were zero fits, grading runs, socket/child attempts, HTTP or CAS writes.
   Actual2.176711CPU/1.945813wall seconds and239,173,632B peakRSS;1,764B safe
   receipts. This was current-vintage historical reference replay and fictional
   software verification, not independent future NFL evidence or off-host
   restoration. Receipt: `CDF_ADAPTER_REPLAY_NATIVE_V1/COMPLETE.json`.
2. Admit an actual future query and current identity/source/roster contract;
   verify source freshness, deterministic fallback and bounded runtime.
3. Restore the private artifact in the approved producer and verify immutable
   pregame persistence/readback under the existing assigned capture horizon.
4. Register the new chart target/catalogue entrant and validated consumer through
   the retained owner. Preserve the original P2 epoch and old scoring history.
5. Keep future grading pending until supported outcomes arrive. No eight-week
   scientific wait is added to operational shadow admission, and no scientific
   superiority or website-relative gain is claimed by this contract.
