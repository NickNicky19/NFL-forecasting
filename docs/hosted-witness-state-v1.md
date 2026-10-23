# Weekly state cap and original publication witnesses v1

This software packet prepares two prerequisites for the existing reference
route. It does not activate hosted runs, wire qualified scorers, authorize
exports, register refresh horizons, or establish prospective confirmation.

## Weekly reference storage

`experiment._run_reference_learning` passes the unchanged
`reference_runtime.StateBoundStorage` to both existing
`fit_operational_reference` and `predict_operational_artifact` call sites.
Only the operational 195 MiB estimate is removed. The proxy checks exact
serialized provisional and final model bytes against the separate 200 MiB
logical state ceiling, including their overlapping peak, and delegates to
the same global storage writer and 512 MiB maximum quota. Identical retained
bytes keep the existing zero-incoming-byte behavior. Failed writes preserve
earlier evidence and the existing terminal failure receipt path.

Training/query/source bindings, model code, package and wall budgets, private
probe semantics, replay comparisons, and the legacy route are unchanged.
The weekly schema probe remains nonissued and supplies no accuracy evidence.
The changed `experiment.py` requires a newly accepted source/runtime assembly;
old source manifests or artifacts must not be patched to inherit its hash.

## Exact original scope retention

After `verify_committed_scope` validates the entire caller-supplied scope,
`record_scoped_publication` saves that exact full envelope as an immutable
`publication_scopes/<digest>.json.gz` record using existing state/quota
primitives. It reads the saved envelope back and checks identity before any
publication timing receipt. Verification or witness persistence failure
therefore creates no new timing claims. A supplied operational storage object
also scopes direct calls through the existing quota adapter.

Receipt idempotency uses `(batch or snapshot, original scope digest)`.
An identical scope retry changes no receipts. A separately verified different
scope may append its own supplied actual readback clock for the same record;
legacy/scoped earlier clocks are never borrowed. Late remains late, including
kickoff equality. Earlier receipt bytes remain unchanged. Aggregate-only or
empty scopes retain their original envelopes and create zero forecast claims.

If any pre-existing scoped receipt already names a digest without a retained
original witness, this producer refuses to save that envelope now. Otherwise
making it available later could incorrectly qualify the old clock. A genuinely
new verified scope/commit and actual readback proof are required; missing old
evidence remains unavailable.

`saved_scope_evidence(state, expected_policy_sha256)` returns copied original
envelopes keyed by digest for the prepared qualification layer. It reads only
the scope-record directory: regular files, no symlink or ancestor symlink,
no parent traversal, bounded compressed/decoded gzip and cumulative inventory,
canonical JSON/digest filename, exact envelope schema/commit/file map and
expected 64-hex policy, even for an absent directory. Policy disagreement fails
closed. The legacy producer may still retain a `None`-policy envelope, but that
envelope is unavailable to this qualified-view loader.
Absent evidence returns an empty mapping; no scope is guessed from a receipt.

The loader is a metadata integrity reader, not an ownership or remote proof.
Existing quota-owned CAS aliases use hard links and remain supported. The
caller retains the existing storage ownership/integrity boundary. The
qualification layer independently revalidates the committed path/file/blob
proof before using an envelope. The loader does not inspect forecast, source,
model, outcome, website, or Git content and performs no network operation.

## Software checks and remaining work

Fictional local Git/state checks cover exact round trips, ordering, absence,
schema/hash/policy/path/gzip/link contradictions, persistence and quota failure,
same-scope retry, new-scope actual clocks, and aggregate-only exports. Weekly
fixtures stub all learner calls and exercise proxy propagation, provisional
failure, final peak failure, retained evidence, and replay.

Qualified-consumer wiring, explicit refresh contracts, private durable hosting,
old-execution retirement, and actual hosted source/runtime acceptance remain
separate work. Original rec-half registration, windows, records and scorecards
are unchanged. No scheduler, default, website, dispatch, or promotion changes
are included.
