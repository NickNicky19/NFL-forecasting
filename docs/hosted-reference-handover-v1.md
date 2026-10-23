# Hosted reference handover: remaining integration

2026-10-23. Read-only design review after corrected-identity input acceptance.
This note changes no runtime, workflow, scheduler, model default or website.
Inspected the existing operational code and the public
[canonical reference report](../reports/canonical-query-reference-v1/README.md)
in integration checkout `8bbbfa507538ccdfa13cc6084e4dc0162255ad74`.
No private source, model or forecast rows were opened; no tests, fits, network
requests or hosted executions were performed for this note.

## Accepted evidence and its boundary

The canonical packet retained 681 roster opportunities in 13 games, built 97
features and accepted all 22 recent/pooled packages through five prediction
routes. Recent warm/sparse/prior coverage became 267/211/203; pooled became
132/397/152. These are broad roster opportunities, not verified participants.
The calculation was a **nonissued reconstruction**, with source cutoff around
11:27 UTC and actual reference computation around 14:33 UTC. It supplied no
accuracy score, promotion or hosted issuance evidence. Exact PPR remains blocked;
participation probability remains unavailable. The prior hosted successes in
[operations-and-handover.md](operations-and-handover.md) used older code and do
not establish acceptance of this corrected-input path.

## Existing call paths to retain

| Stage | Current implementation and contract |
|---|---|
| Schedule and single writer | `.github/workflows/lab.yml` calls `cadence.decision`: existing dual UTC cron is gated to 08:36–08:56 America/Chicago; Sunday selects training. `nfl-lab-single-writer` concurrency serializes runs. Delayed scheduled events grade/replay without backfilling issuance. |
| Restore | `tools/restore_state.py:restore_state` reads only already-fetched `origin/lab-state` Git blobs under `state/`; validates paths, declared sizes, conflicts and quotas before writes. It restores neither source cache nor query/features. |
| Daily | `cli.main → live.daily → live._daily`: bounded current Sleeper/ESPN intake, permitted operational history/identity, future population, shared feature builder, recent/pooled artifact fit/replay, then `state.capture` and grading. |
| Weekly | `cli acquire → experiment.acquire_operational_features`; `cli experiment → run_reference_learning`. The latter fits a private latest-row-per-position schema probe, with synthetic game IDs. It is not the accepted 681-row query or an issued forecast. |
| Frozen inference | `operational_models.model_binding` binds exact source/policy/code, training frame, query frame and input hash. `predict_operational_artifact` validates these before core `model_artifacts.predict_artifact`; replay does not fit. |
| Evidence and grading | `state.capture` keeps first player/game/target/model opportunity and actual issue/persistence clocks; `append_outcomes`/`resolved_outcomes` retain correction conflicts. `cli replay` validates saved records and scores saved outcomes; it is not a fitted-artifact replay. |
| Publication | `tools/persist_state.py:reviewed_publication → persist` copies only exact reviewed state path/hash entries, preserves omitted remote evidence, rejects changed existing paths, pushes `lab-state` and verifies remote commit readback. New timing receipts remain local pending another exact review. |
| Consumer | `consumer.consumer_forecast` validates a copied scalar record against `schemas/forecast-v1.json`, binding the untouched original digest. Website integration remains read-only and separately owned. |

## Smallest compatible implementation changes

1. **Use the accepted identity resolver in the existing daily intake.**
   `live._daily` currently builds `mapping` using a dictionary comprehension over
   `source_exact_binding` rows. That bypasses the accepted conflict quarantine,
   exact-text handling and registry-qualified ASCII-space GSIS repair. Replace
   that unchecked mapping before it influences population IDs; applying the
   resolver only after candidate selection cannot recover lost conflicts. Project
   the live population to the exact eleven `query_identity.QUERY_COLUMNS`, call
   `resolve_query_identities(query, registry[three registry columns],
   identity_sha256=verified_identity_file_sha)`, then retain the four provenance
   columns and aggregate receipt in the existing input binding. Reattach Sleeper
   and eligibility metadata by unchanged row index, preserving all opportunities.
   Keep `future_population`'s provider/crosswalk-conflict abstention and first
   frozen `(game_id, sleeper_id)` binding: an identity repair must not rename an
   already captured opportunity. Run the unchanged shared feature builder on the
   resolved query. Bind the adapter code/version and registry/receipt hashes in
   the new input receipt; old manifests and forecasts remain immutable.

   The canonical V2 feature wrapper is specifically for a validated
   `VERSIONED_METADATA_RECONSTRUCTION_NOT_ISSUED` envelope. Its nullable future
   availability repair is accepted, but that envelope cannot be relabelled as
   live issuance. Reuse its underlying resolver and shared feature builder in
   the live caller; do not send an old reconstructed query to `state.capture`.

2. **Keep daily binding semantics explicit.** Daily already fits fixed references
   for the exact new input/query and replays that artifact before capture.
   Weekly artifacts bind a different synthetic query, and daily never loads
   them. Reusing a weekly artifact for a new daily query would fail the existing
   contract. The minimal hosted path keeps the current bounded daily reference
   fit/replay and treats weekly refresh as a probe. No selected challenger,
   second model pipeline or relaxed query binding is needed. A claim that weekly
   parameters supply later daily inference would require a separate contract
   change and acceptance; it is not implemented here.

3. **Apply the already accepted exact state-write bound at operational fits.**
   Daily and weekly currently check state size against 195 MiB before calling
   `fit_operational_reference` with bare `OperationalStorage`. This does not
   reserve the actual provisional-plus-final serialized model peak under the
   separate 200 MiB state ceiling. Reuse `reference_runtime.StateBoundStorage`
   at those existing call sites. Its delegated global writer and transaction
   guard cover both core serializer and final model JSON without changing a
   learner. `operational_io` already bounds compressed state records exactly.

4. **Supply an actual operational publication review.** The workflow checks for
   `config/operational-publication-review-v2.json`; it is absent. Without it,
   `persist_state` deliberately fails before Git publication. The public
   canonical packet's `lab-derived-publication-manifest-v1` is a repository
   export inventory, not this state-publication authorization. Keep the existing
   fail-closed publisher and provide a separately reviewed manifest for actual
   resulting bytes. A static manifest cannot authorize newly generated records
   whose hashes differ on the next run; unattended publication needs an agreed
   content-review step, not a wildcard or automatic inventory approval.

   There is also a receipt scope mismatch: after an allowlisted export,
   `persist` invokes `cli publication` without the reviewed file set. That
   command marks every unrecorded local forecast batch and website snapshot as
   published, even if omitted from the commit. Pass the verified committed
   batch/snapshot identities into that existing receipt path and check their
   exact remote bytes. Aggregate-only publication must create no forecast or
   website-snapshot publication claim.

## Persisted artifacts and ceilings

The operational review manifest is exactly
`{schema_version: operational-publication-review-v2, review_state: ACCEPTED,
policy_sha256: <exact policy SHA>, files: {<state-relative path>: <file SHA>}}`.
Use individual paths such as `health/<digest>.json.gz`,
`operations/<digest>.json.gz`, `training/<digest>.json.gz` or
`scorecards/<digest>.json.gz` only after inspecting their complete contents for
aggregate-only export. Directory names and compression are not content review.
No `state/**` glob is authorized. Ownership controls, writer locks and pending
files are excluded by the existing publisher.

Current packet publication permits reviewed aggregates, code and configuration;
it excludes raw source/identity rows, private query/features, forecast/outcome
rows, input payloads and fitted parameters. In particular, do not add `models/`
or runtime `private/` outputs to Git or Actions uploads. Durable official
forecast/correction records would need their own explicit publication decision;
aggregate-only restoration cannot recover their opportunity keys for retry
deduplication or later grading. Restored models alone would also lack the exact
private query/source dependencies needed for qualified replay. Ephemeral hosted
runners can reacquire bounded permitted inputs for a new binding; this does not
restore an old unavailable snapshot.

Retain the shared **512 MiB** unique-inode physical quota across registered
source/cache/CAS, state, private outputs and publication aliases, plus the
separate **200 MiB logical state** ceiling including model temporary peaks.
Restore checks both. No deletion or eviction makes a failed run pass. Keep two
threads. Actual workflow limits are **40 minutes/job**, **540 seconds/daily**,
**180 seconds/acquire**, **720 seconds/experiment** and **180 seconds/grade**;
the policy's 1,200-second weekly limit is further restricted by that existing
720-second shell timeout. Health artifact retention is 14 days. These limits
supersede the older timings stated in the historical handover document.
The workflow does not currently enforce a process-tree CPU or RSS ceiling;
wire the accepted bounded supervisor into the existing command invocation for
the separately frozen hosted budget, and retain its measured usage/failure.

## Hosted acceptance still required

Freeze the small integration diff, exact code/dependencies/policy, publication
scope and finite invocation/resource budget before actual execution. Use the
existing workflow and save its run ID, attempt, source SHA, cadence result,
step conclusions and actual resource/HTTP receipts. Acceptance must demonstrate:

- Corrected identities and provenance reach newly built features and all fixed
  supported targets without dropping offered rows; unresolved identities remain
  explicit fallbacks, PPR blocked and participation unavailable.
- New official rows pass the existing issue, persistence-completion and remote
  readback clocks before kickoff. Reconstructed cutoff is never issuance time.
  Repetition after restore preserves first frozen identity/opportunity keys and
  does not refit already frozen opportunities.
- Exact artifact replay succeeds with fitting forbidden on its retained query;
  different query/source/code bindings reject. A prior artifact replay uses its
  pinned old code/environment, rather than rewriting its binding under new code.
- Reviewed state survives a fresh hosted restore and hash check; partial-source,
  timeout or quota failure preserves earlier evidence and permits grading/replay
  without legacy source fallback or late issuance. Verify actual on-time
  scheduled delivery; an off-slot success alone does not establish it.

None of these hosted checks was executed in this read-only wave. Existing
active/previous artifact rollback helpers remain local tools; no new pointer,
default promotion, scheduler or website integration is proposed.
