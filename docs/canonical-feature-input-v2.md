# Canonical feature input v2: nullable future placeholder

V1's actual acceptance stopped before any shared feature-builder call because
all original query `outcome_available_utc` placeholders were null. V1 code,
tests, documentation, failure and consumed registration remain unchanged. V2 is
a separately frozen technical repair, not an automatic retry of that run.

`canonical_feature_inputs_v2.validate_canonical_query` is the exact unchanged v1
metadata validator. It retains accepted original null metadata, aliases, row
order and receipt/frame hashes. `build_canonical_features(history, canonical,
policy=loaded_policy)` uses the same call signature and returns features plus a
JSON-safe aggregate lineage. It calls the unchanged
`operational_sources.build_operational_features` exactly once; there is no
second feature implementation or retry.

Kickoff and cutoff remain required, with cutoff at or before kickoff. Only the
future query availability placeholder may be null. Any nonnull placeholder must
already equal kickoff plus seven days after UTC normalization. The frozen source
builder has always replaced this query placeholder with kickoff plus seven days;
v2 checks its result against that documented rule rather than against original
nulls. The input canonical dataframe and its provenance hash remain unchanged.
The output placeholder is assumed, not an observed outcome publication receipt.

All historical availability, source receipt/asof, source-code/history hashes,
source cutoff, 97-feature, null-label, unknown-participation, unavailable-Pplay,
context/index and source-lineage guards remain active. Assumed historical source
times must be strictly before cutoff; query source time must be at or before it.
No zero filling, row filtering, identity change, fit or prediction is introduced.

V2 lineage explicitly records `adapter_version=canonical-feature-input-v2`,
`metadata_validator_version=canonical-feature-input-v1`, the missing future
placeholder row count and `assumed_not_observed` semantics. V1 provenance cannot
overwrite the v2 adapter version. The caller authenticates files and binds actual
code hashes, calculation/persistence clocks, quotas and the separate v2 repair
registration. The source cutoff does not become a pregame issuance clock.
