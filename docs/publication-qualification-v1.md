# Scoped publication qualification views v1

This is a prepared, opt-in input layer. The existing
`prospective.score_saved` and `website_baselines.score_saved_website` remain
unchanged and legacy-inclusive. This module does not repair those callers,
activate hosted operation, score forecasts, or determine scientific confirmation.

## Contract

`qualified_forecast_view(root, state, scope_evidence, expected_policy_sha256)`
returns `(private_entries, aggregate_receipt)`. Each entry contains a copied
original row, its batch and row digests, and selected persistence/publication
proof metadata. `qualified_website_view` returns copied bindings plus their
qualified linked lab entries and both proofs. Returned values are private;
the aggregate receipt contains counts, reason codes, and version hashes only.

`scope_evidence` must map the digest of each **original full**
`lab-publication-scope-v1` envelope to that envelope. Missing evidence yields
`SCOPE_EVIDENCE_UNAVAILABLE`; a one-file envelope is never reconstructed from
a receipt. Current publishers retain only the scope digest in the receipt,
so full-envelope persistence and versioned caller wiring remain required
before hosted acceptance.

The layer reuses `publication_scope.verify_committed_scope` to prove exact
local file bytes, immutable document digest, committed regular-file path,
Git blob, commit, complete scope inventory, and source-policy SHA. The recorded
remote OID readback remains the original publisher's attestation; this layer
performs no network verification or content-publication authorization.

## Selection and rejection

Only scoped v1 receipts can qualify. Kind, batch/snapshot, path, file SHA,
blob, 40-hex commit, verified remote commit, original scope digest, and policy
must agree. Publication timely/late counts and persistence late-game lists
are recomputed from immutable rows. Distinct persistence receipts or a
contradictory scoped receipt quarantine the affected batch/snapshot. Missing
full scopes are unavailable rather than contradictory; another independently
valid full-scope proof can qualify.

Valid proofs are ordered by actual readback time, then receipt digest.
Rows require:

`feature cutoff <= issued <= persistence start <= completion <= actual readback < kickoff`

The original source-integrity marker and code/input hashes must be present.
Duplicate opportunity identities across all original batches are unqualified,
including conflicts with an earlier legacy or otherwise unqualified batch.
No later scoped capture is selected as its replacement. Point-shadow rows
remain explicitly unqualified. No current source-tree hash is substituted
for the forecast's recorded source version.

V1 supports one opportunity per `(player_id, game_id, target, model_id)`.
Multiple registered refresh horizons sharing that identity cannot qualify
through this layer; a later version needs an explicit model/horizon contract.
This constraint does not define confirmation selection or rec-half eligibility.

Website bindings additionally require an independently qualified lab row,
exact row digest, identity/context and clock links, supported original method,
and a value digest. Repeated forecast/method bindings are unqualified, and the
header season/week must match the lab row. Header generation/observation precede the feature cutoff;
lab completion precedes website persistence. Both publication proofs are
established before a caller could rehydrate website values or access outcomes.

Legacy receipts remain immutable and descriptive. Their clocks neither
qualify a row nor suppress a newer scoped proof. A later actual republication
cannot turn an earlier local capture into pregame publication. The layer
imports/calls no outcome resolver, HTTP client, learner, or scorer, and writes
no files. Empty views contain only coverage/reason metadata.

## Frozen boundaries and remaining integration

The aggregate receipt binds the qualifier version/code hash, commit-verifier
code hash, qualification-policy SHA, and explicit expected source-policy SHA.
Publication qualification supplies a necessary input condition, not a
registration or accuracy claim. It does not change the original rec-half
registration, executable/source hashes, Weeks 7–14, existing scorecards,
point-shadow status, or issue clocks. Generic Week 8 classification in an
old consumer is not registration authority.

Next authorized integration must persist original scope envelopes, wire these
views into separately versioned consumers before outcome/rehydration access,
and accept new source/runtime bindings. Old evidence remains unchanged. No
scheduler, default, website, dispatch, or activation changes are included.

## Software checks

Fictional local Git/state checks exercise exact proof identity, complete-scope
absence, legacy/new receipt separation, clock/counter contradictions,
deterministic selection, linked website gating, point-shadow exclusion,
copy/no-write behavior, and a local-Git-only boundary. No real source, forecast,
model, outcome, or website values are read.
