# Daily reference identity and state-bound adapter v1

Isolated software repair under `hosted-reference-adapter-repair-v1-20261023`,
policy SHA256
`de74075418e125a823829b5e431a1e178db83b988ba16c1e6ffc68878f200d05`.
It changes the existing opt-in daily caller. No actual source intake, fitting,
issuance, publication, hosted execution or website operation is included.

## Identity before shared features

The policy route in `live._daily` uses the existing qualified identity loader,
requires its snapshot and namespace to equal the history snapshot, and verifies
the exact `processed/identity.parquet` SHA from `artifact_sha256s` through the
existing owned storage. It no longer chooses a registry candidate with a
dictionary comprehension. The legacy route is unchanged.

The existing `future_population` still determines the broad offered roster and
context, with no crosswalk dictionary on this route. Existing first captured
`(game_id, sleeper_id)` identities are supplied to it as before. After the actual
cutoff is assigned, new pure helper
`hosted_reference_adapter.adapt_live_identities(population, registry,
identity_sha256=..., frozen_by_game_sleeper=...)` returns a new population plus
an aggregate receipt. It performs no I/O, matching by name, numeric conversion,
feature calculation, fitting or capture.

For each unfrozen row, the accepted `query_identity.resolve_query_identities`
qualifies two exact eleven-column metadata views: the observed provider ID and
the explicit `sleeper:<exact text>` alias. This reuses its ASCII-only rules,
registry-qualified outer-space GSIS repair, conflict quarantine and collision
checks. Direct/qualified crosswalk disagreement or an ambiguous crosswalk keeps
the stable Sleeper namespace and existing `conflicting_identity_cold_start`
binding. Unresolved identities remain explicit; no row is selected or dropped.

Frozen rows do not enter candidate resolution and retain their first identity
after every decision. A new resolved identity colliding with a frozen game key
fails the intake. Original row order/index/context remain; only player identity
and its binding can change. Unknown participation is required even for frozen
rows. Newly observed input cannot repair an older frozen forecast or supply
evidence for a pending rec-half observation.

Five caller provenance fields accompany the new query and forecast:
`original_player_id`, `identity_resolution_state`, `identity_source_sha256`,
`identity_adapter_version=hosted-reference-identity-v1`, and
`canonical_identity_adapter_version=source-qualified-query-identity-v1`.
The caller explicitly distinguishes conflict/frozen decisions from the accepted
resolver's candidate states. The aggregate receipt binds both candidate
receipts, exact input/output metadata hashes, counts and source SHA.

The query still enters the unchanged `build_operational_features` once. The
nonissued canonical reconstruction envelope is not relabelled as issuance.
Provenance columns enter the existing feature/input hash; receipt and adapter
code hashes enter source/input manifests. The daily model version additionally
binds this caller, accepted resolver and state-guard code. Actual capture and
persistence clocks are still assigned by the unchanged state helper.

## Exact existing state guard

Daily operational fit/replay receives the accepted
`reference_runtime.StateBoundStorage(active_storage(), state)` proxy. It checks
the exact serialized incoming model bytes plus retained logical state under the
existing global transaction before provisional/core and final JSON publication.
Same-byte owned reuse adds zero bytes. The separate 200 MiB state ceiling and
global 512 MiB private quota both remain; failed provisional CAS bytes remain
retained by the original serializer/storage behavior. No body is deleted to
make a fit pass.

Only the superseded policy-route 195 MiB heuristic is removed. Weekly behavior,
source adapters, learners, methods, target support, PPR block, unavailable
participation probability, grading/outcome/scoring/capture semantics, schedules,
publication authorization and defaults are unchanged. The daily failure wrapper
continues to abstain, preserve earlier records and attempt grading.

## Acceptance boundary

The repair legitimately changes source/runtime code bindings. It cannot use an
old source manifest or artifact under a rewritten hash. Root must separately
freeze and accept a new assembly/version, preserving original raw bytes,
receipts, model artifacts and failed runs. Current root recovery's 82 original
bindings remain unchanged while this software stays isolated.

Fictional tests cover exact/leading-zero aliases, registered ASCII-space repair,
malformed text/types, quarantined conflicting/unusable mappings, provider
disagreement, frozen first identity, final game-key collisions, row/context
preservation and deterministic replay. Production storage plus an inert core
serializer checks rejection at both provisional and final model peaks. Existing
daily replay/retry/season, identity, grading, storage and cadence tests remain
part of the bounded software check. These checks imply no dependable hosted
delivery, official prospective capture, participation proof or accuracy gain.

The first targeted fictional run passed all 96 checks without failure:
12.681035 seconds wall / 14.759272 seconds CPU, peak child RSS 202,334,208 bytes,
with two threads. The daily integration fixture uses inert predictions and
owned fictional identity metadata; the serializer checks use an inert core.
No actual NFL source/model/forecast values or HTTP requests were accessed;
existing reference parameter/replay tests use fictional histories only.
Independent static review and a separately frozen actual assembly
remain required before hosted use.
