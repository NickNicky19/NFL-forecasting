# Exact publication receipt scope v1

Technical repair registered by `publication-scope-repair-v1-20261023`, policy
SHA256 `a504e66caeff2ee4155146b5dd5ba0ba0b17a83f408ccf89e7ec004384bc85d3`.
No actual publication, dispatch, model change or website change is included.

## Existing publisher, explicit scope

`tools/persist_state.py` retains v2's exact accepted content-review manifest,
quota-owned copying, Git push and remote OID readback. After that readback it
passes the **same file map** to `cli publication --publication-scope-stdin`
through JSON stdin, without creating an unmanaged transport file. The legacy
publisher takes an explicit state-file inventory before staging and passes that
inventory; it no longer assumes that every local batch was committed.

The transport has exactly these fields:

```json
{
  "schema_version": "lab-publication-scope-v1",
  "commit": "<40 lowercase hex characters>",
  "verified_remote_commit": "<same commit observed by the publisher>",
  "policy_sha256": "<exact v2 policy SHA256, or null for legacy>",
  "files": {"health/<digest>.json.gz": "<exact file SHA256>"}
}
```

This is receipt evidence, not export authorization. V2 still requires the
separately accepted content-review manifest before any Git publication. The
stdin witness alone does not authenticate a remote: the existing publisher must
have actually pushed and checked the remote OID. The CLI independently proves
the file bytes in that local commit object; it performs no additional network
request. An unscoped publication command fails closed.

## Verification before receipts

`publication_scope.verify_committed_scope` requires an actual commit object,
disables Git replacement objects, and checks every selected state-relative path
against its regular-file Git tree entry, blob bytes and SHA256. Local bytes must
match exactly. Symlinks, traversal, controls, wrong hashes, missing committed
files, a wrong commit/tree and mismatched policy/schema are rejected. V2 also
uses the existing storage ownership/reference check. Selected file bytes and
decoded immutable records are bounded by the existing 200 MiB state ceiling.

Only selected `forecasts/<state-digest>.json.gz` and
`website_bindings/<state-digest>.json.gz` can generate claims. Their canonical
state digest must equal the filename, and their row kickoff clocks must parse.
All selected files are checked before any receipt is appended. Aggregate-only
or empty exports generate zero forecast or website publication claims, even
when other local batches exist. No broad forecast or website snapshot scan is
used to discover what was published.

`record_scoped_publication` preserves the receipt kinds and adds explicit scope
schema/digest, exact state path/file SHA, Git blob OID and verified commit fields.
Publication clock is the actual current CLI observation; equality with kickoff
counts as late. V2 receipt writes use the existing `operational_io` quota save;
no quota, manifest or content-rights check is relaxed. A failed write may retain
earlier completed receipts, which are idempotent on retry.

## Legacy evidence is not repaired retroactively

Original receipts remain byte-identical. Only an already **scoped v1** receipt
suppresses a repeat scoped proof; an older broad claim for the same batch does
not prevent appending a new proof with today's actual clock. Old clocks are not
requalified. The same rule applies to website bindings.

Existing evaluators that select publication records without filtering the new
scope schema can still mix legacy and scoped records. Their consumption is
outside this repair and remains unqualified until separately versioned consumer
wiring explicitly chooses qualified evidence. This repair does not certify old
receipt timing, scientific readiness, prospective eligibility or hosted success.
New CLI/source bindings must be assembled and accepted separately; old source
manifests and fitted-artifact bindings cannot be patched to match the new code.

## Fictional software execution

The first run retained one fixture failure and 30 passes: an attempted in-place
adoption of unmanaged fixture bytes was correctly rejected by the storage
writer. The fixture was repaired to create its bytes through the quota writer.
Subsequent targeted runs passed 68 and then 69 checks; the final run includes
the legacy same-batch and ancestor/tree symlink cases. These are overlapping
suites, not distinct observations. Cumulative measured test time was 25.329158
seconds wall / 30.702221 seconds CPU; peak child RSS was 195,256,320 bytes,
with two threads. All Git remotes were fictional local directories. No actual
source/model/forecast values, HTTP requests or hosted publication were used.
