# Canonical identity feature input v1

The new pure adapter adopts an explicitly accepted identity metadata revision.
It never loads private files, obtains source data, writes, fits, predicts or
publishes. Original metadata, features, artifacts and registrations stay frozen.

`validate_canonical_query(payload, original_query, expected_identity_sha256=...)`
reconstructs the exact reviewed five-key private envelope: `evidence_lane`,
`columns`, `index`, `rows` and `receipt`. It accepts the original eleven metadata
columns followed by the four existing identity provenance columns. It verifies
row/index/column order, original context and aliases, accepted dtypes, source and
adapter identity, collision absence, resolution shapes and receipt counts. Both
input and output metadata frame hashes are recomputed with the unchanged
`query_identity._frame_hash`; the receipt digest is retained in validation attrs.
Unknown fields and inconsistent rows, source binding, receipt or hashes fail.

The caller first authenticates the complete private payload and registry file
SHA256 against their frozen registration. The adapter validates the recorded
registry metadata digest's shape; it cannot independently recreate registry
contents from that digest. It does not infer another mapping from history.

`build_canonical_features(history, canonical_query, policy=...)` accepts the
validated dataframe and an already loaded policy mapping, returning
`(features, aggregate_lineage)`. It detects
changes after metadata validation, then calls the unchanged
`operational_sources.build_operational_features(history, queries=query)` exactly
once. The original qualified history is not rebuilt, and there is no retry.
Existing policy/code/history/source/receipt cutoff gates remain active.

The output preserves canonical row/index order, identity aliases and context.
The existing builder normalizes kickoff, cutoff and availability clocks to UTC;
the input availability placeholder must already equal kickoff plus seven days.
That future placeholder is not an observed outcome publication clock. Actual
feature source clocks must be at or before cutoff; any assumed historical
source clock must be strictly earlier. Nonempty history requires its clock.
All twelve query labels remain null, participation remains unknown, and its
probability remains unavailable. Exactly 97 numeric finite-or-missing feature
columns are required; zero, signed values and missing values retain their
existing semantics.

The deterministic aggregate lineage contains versions, metadata/receipt/frame/
feature/source hashes and counts, with no NFL rows or aliases. The caller binds
the actual code-file hashes and records real calculation/persistence clocks in
an outer private receipt. The frozen source cutoff never becomes an issuance
time: this lane is `VERSIONED_METADATA_RECONSTRUCTION_NOT_ISSUED`.

The root separately compares all 97 feature values/dtypes/order for the 150
unchanged-ID rows and nonplayer context features for all 681 rows against the
frozen old feature version. All opportunities remain, including unresolved
identities. Exact PPR, accuracy, official issuance and confirmation remain
unavailable; any later reference runtime uses a separate frozen input revision.
