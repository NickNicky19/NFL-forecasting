# Canonical Bernoulli diagnostics v2

Policy SHA256:
`72fb9c42f9d315b1241e0e6b7e48904427aeb20cfb9b5019f089a71f6541ecb0`.
This is a separate diagnostic representation after a failed strict report. The
original source, forecasts, scores, files, invalid state and failed resource
receipts remain unchanged. It is not a new experiment or prediction.

## API and exact scope

`canonical_bernoulli_diagnostics(rows) -> (derivative, receipt)` accepts one
nonempty normalized `anytime_td` law frame, method `leaf_cdf` or `role_prior`.
Root authenticates each raw file before passing it; the planned six calls cover
three exposed years and both laws. This function has no IO, fitting, model/law
calls, source reads, new labels, network or ledger writes.

The input is deeply copied. Only `cdf_actual_below,cdf_actual,crps,log_score` may
change. Every other column—including identity, contexts, state, points,
probabilities, mean, median, quantiles, variance, original primary `brier`,
fallback and history—retains its dtype, values and floating bits, including NaN
payloads and signed zero. Index/columns/row order remain exact. Protected-column
preservation is asserted. The four normalized diagnostic inputs must be float64.

The sole authority is the already frozen event probability `p`; point/mean must
match it exactly, including finite floating bits. Infinite or out-of-range p is
rejected, never clipped. Finite/infinite actuals outside Bernoulli 0/1 support
are rejected. Unknown participation and missing actuals do not imply playing or
zero. Missing p is abstention only when every raw diagnostic is missing.

Supported played 0/1 rows with finite p require complete already-frozen
diagnostics: below/at/CRPS finite, and log score finite or positive infinity.
Missingness conflicts reject rather than adding newly scored rows. All four raw
diagnostics must already be missing on unobserved/abstaining rows. Those rows
remain NaN in the derivative. `DiagnosticInputError`, a `ValueError`, exposes an
aggregate-only `.receipt` on semantic/missingness rejection.

## Four analytic identities

For supported played outcomes and finite p, compute directly:

| Outcome | CDF below | CDF at | CRPS | Natural log score |
| --- | --- | --- | --- | --- |
| 0 | 0 | 1 − p | (p − 0)² | −log1p(−p) |
| 1 | 1 − p | 1 | (p − 1)² | −log(p) |

Contradictory p=0/1 outcomes retain positive infinite log score. CRPS equals
Bernoulli Brier mathematically; it is a secondary diagnostic computed directly
from the same p/y. Original primary Brier/points remain untouched. Raw histogram
endpoint or mass-subtraction roundoff is not accepted as a valid raw CDF and is
never blanket-clamped or given an expanded tolerance. Instead, this explicitly
versioned derivative uses the exact identities, then checks them without any
atol/rtol. No variance or quantile is recalculated.

The caller MUST use the unchanged strict `source_matched_reporting` validator
and existing `build_target_report` after making these six views. This adapter
does not bypass category roles, query binding, protected years, proper-field
support or any other strict check. `_assert_identities` also rejects mathematically
incorrect in-range diagnostics that the old generic bounds check alone permits.

## Receipt and retained evidence

The receipt contains aggregate counts only: eligible/unknown/DNP/missing rows,
raw invalid CDF bounds/order/nonfinite fields, missingness conflicts, invalid
probability/actual counts, negative raw CRPS/log fields and original invalid
state. Each field records changed-value and changed-bit counts, finite-pair
maximum absolute difference, and explicit finite/missing/positive-infinity/
negative-infinity transition counts. No player IDs, game values, raw row arrays
or probabilities are exported in the receipt; it is JSON-safe without NaN.
Raw values stay in the original immutable files; root binds and retains them
alongside separately persisted private derivative views and their hashes.

Fictional checks are capped at 60 wall/90 CPU seconds, 512 MiB, one numerical
thread. They cover the original strict bracket failure, strict acceptance of
the new view, exact identities, all protected bits and primary summary equality,
boundary infinities/transitions, invalid probabilities/labels, missingness and
abstention conflicts, and proof no law or IO API is called. Actual six-view
production/reporting requires root's separate freeze/supervisor and retains all
prior failed versions, resources, slots and exposed-evidence limitations.
