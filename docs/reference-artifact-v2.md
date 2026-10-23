# Derived reference content contract

`nfl_lab.reference_contract` reviews the existing finite JSON artifacts without
changing learners, serializers, source rules or fitted parameters. It accepts
only the eleven supported targets with `recent` (window 3, strength 3) or
`pooled` (window 8, strength 5). Exact PPR remains blocked. Every object has an
exact field allowlist, including the wrapper, artifact, configuration, training
audit, temporal audit, inference node, priors, residual distribution, source
schema, environment and operational binding. Extra fields fail even when their
checksum has been recomputed.

Permitted learned content is global and fixed NFL position aggregates of mean,
variance and supported observation count, plus global and position residual
dispersion. Counts reconcile with the training audit; count-target means are
nonnegative and Bernoulli means lie in [0, 1]. Numeric parameters must be finite.
No row arrays, query values, source paths, source bodies, player/game identity
values, arbitrary position keys or free text fields are accepted. Schema column
names may include the existing identity fields; their values are absent.
Participation is exactly unavailable in both inference and audit.

Core and operational code locks, all fifteen existing operational code hashes,
the five-package core environment lock, config digest, policy/source/snapshot/
training/input/query digests and internal payload checksum are checked. An
optional expected target, method and full binding must match exactly. A review
receipt contains only hashes, target/method and aggregate support count. These
checks establish schema and byte bindings; they do not establish authentic
historical source publication times, upstream rights or calibrated count laws.

The independent calculator uses the serialized aggregates and frozen query
features, without training labels or fit/replay helper calls. It computes the
shrunken conditional mean and fallback reason independently, derives normal,
NB2/Poisson or Bernoulli scale and quantiles with SciPy, and emits all eight
forecast columns. The frozen runtime compares numeric columns at rtol 1e-10,
atol 1e-9 with matching NaNs and exact family/fallback strings. This supplies
software evidence, with no accuracy score or new confirmation evidence.

The runtime's four preregistered failures are query mutation, source binding
mutation, internal checksum corruption and artifact target/method mismatch.
Replaying the original valid immutable artifact checks technical recovery only;
it does not demonstrate hosted rollback or scheduling recovery.

`build_publication_manifest` is a pure generator. The root supplies an explicit
`review_state="ACCEPTED"` after exact content review under existing lab
authorization, a nonempty relative path to file SHA256 map, and the policy hash.
Every selected file must pass this derived artifact contract and match both
hash and policy. Selection does not scan or include other private state files.
The returned document has exactly the `operational-publication-review-v2`
schema documented in `operational-source-v2.md`. The function writes nothing,
performs no Git operation and makes no new private data permission claim.
Raw/query/history/source bodies remain private. Actual publication and hosted
acceptance are separate operations.
