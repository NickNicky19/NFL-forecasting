# Ordered CDF future-query package

This completes a new pure future-query seam for the frozen four-slot recipe. It
does not replace the original strict historical replay API, acquire current
sources, load a production model, persist forecasts or admit a release.

## Obtain the executable sources

The existing public dependency is
[`nfl_lab/ordered_recent_v1.py`](https://github.com/NickNicky19/NFL-forecasting/blob/00e2a3db317ae60815320a1f822d9e497b2896c3/nfl_lab/ordered_recent_v1.py):
6,013 bytes; SHA-256
`d7266d47462865d832079bde1a5ff757e217c6c6297e76028398a97100ef3d0e`;
Git blob `94fde122be5d71a856a3897e92977a00cd8d5690`.

The new module is `nfl_lab/category_topfive_ordered_future_v1.py`, 10,630 bytes,
SHA-256 `c33801ffb53e30a0a8041b32c877ce04e5b3eee380000638e9cba959895f43c4`.
This checkpoint includes the new module at its importable package path. Exact
public commit/readback is recorded separately in PUBLICATION_RECEIPT.json.
Retrieve both modules under the same `nfl_lab` package with the existing locked
NumPy/Pandas environment. No agent can access another session's local files by
assumption; use immutable public Git files or the approved private owner route.

## Exact retained-owner sequence

1. Restore the approved 2026 ordered-model capsule through the established
   authenticated producer/private-checkpoint workflow. Authenticate the original
   model members and the current source/wrapper/catalog mapping. The 2025 model
   is a historical comparison artifact, not the model to issue 2026 forecasts.
2. Create a distinct entrant/procedure binding for `rush_att` and/or `rec`. It
   names this adapter version, unchanged ordered-feature version, exact model,
   procedure and source-policy SHA-256 identities, unchanged base feature list,
   and the truthful source-availability policy. Compute
   `feature_schema_sha256(target, base_features)` from the adapter. Obtain the
   expected binding from the admitted catalog, never the incoming request.
3. Produce the existing qualified base-feature frame for one issue-cutoff group.
   Group different cutoffs before calling. Required identity/context are season,
   week, game, player, team, opponent, position, kickoff and cutoff. Required
   source clock is `feature_max_source_available_utc`; every exact base feature
   remains present. Do not include target-game outcomes or already computed
   ordered features. Warm unknown feature clocks force a trained-prior fallback.
4. Before decoding/projecting prior statistic values at the upstream seam,
   admit history by `outcome_available_utc < cutoff` and `kickoff_utc < cutoff`.
   Preserve the actual named timing policy. The old seven-day reconstruction is
   not authenticated publication time. Explicitly unknown history clocks cannot
   be invented. Supply only the admitted projection to
   `prepare_future_queries(base, history, binding=..., trusted_binding=...)`.
   That method preserves the original four slots, ordered by game chronology,
   including nonnumeric DNP/unknown slots, and rejects target-game history.
5. Call `predict_prepared_batches(trusted_model, prepared,
   trusted_binding=...)` only inside the existing trusted future producer.
   It validates the frozen context panel, exact base-plus-ordered schema and
   immutable prepared frame. It preserves complete original predictive laws,
   prior-only fallback and per-row reasons. It verifies complete/no-duplicate
   output positions. Consume the entire generator before declaring completion.
6. Preserve the complete returned laws and model/source/functional identities.
   Reuse the already implemented `full_law_functionals` helper for separately
   typed means and actual lower medians. The mean is not another fitted method.
   Put MAE-selected projections only in the new `stat_point_mae_v2` product;
   preserve expected-value and probability products and their original epochs.
7. Exercise real current-query inference, fresh-process restoration/replay,
   missing-source/prior and rollback cases under the retained runtime budget.
   Capture the actual website and fresh R0 at the same registered horizon.
   Freeze complete immutable outputs before the real deadline. If a deadline
   has passed, admit a later entrant prospectively; never backdate or overwrite.
8. Only the retained production owner may admit, select, publish and integrate
   the typed consumer. Record delivery, acknowledgement, each executed gate,
   actual capture, public payload and displayed-value readback separately.

## What ran

One newly registered fictional source-contract invocation passed **34 checks**,
including feature bit parity with the unchanged helper, chronology, DNP/unknown
quarantine, naive/unknown/equal/future clocks, source/catalog/schema mismatch,
target leakage, tampering, fallback, full-law preservation and output census.
Actual CPU 0.372967 s, wall 0.374940 s, peak RSS 94,511,104 bytes. No NFL rows,
model loads, predictive fits, real inference, network calls, private writes or
capture occurred. The older 36-case point-policy check was reused, not rerun.

Current-source qualification, actual model restoration and owner admission remain
unexecuted dependencies; the fictional check cannot set those gates true.
