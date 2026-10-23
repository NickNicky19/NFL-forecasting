# Operational source and storage v2

The frozen policy is `config/operational-source-policy-v2.json`. V2 changes
storage and routing, retaining v1 source eligibility, normalization, feature
values, recent/pooled algorithms, target support, exact PPR gate and unavailable
participation probability. It adds no football observations or accuracy claim.

The accepted v1 policy, reports and private packet remain unchanged. Historical
v1 replay uses Git `a8ddbf9e9d1c7360e0942877fa9183533604f091`. V2 loaders and
reference bindings reject v1 policies, snapshots and reference artifacts.

## Shared quota and immutable data

`OperationalStorage` registers source, feature, live-provider and supplied state
roots under one cache-owned registry and flock. Operational run receipts and
the optional baseline cache are registered before writing. Every supplied state
file counts, including existing evidence. The separate frozen 200 MiB state
limit also applies. Nothing is removed to free capacity.

Known serialized bytes are checked before writing. Downloader chunks, pandas
CSV/parquet output and frozen helper path writes use scoped capture. A scoped
state serializer preserves canonical compression and the state limit under
the same quota transaction. The reference wrapper overrides the frozen core
artifact serializer while it creates its provisional model. Both provisional
and final bytes count. Frozen helper/model files remain unchanged.

External originals are copied into an owned SHA256 store before aliasing.
Published source bodies, subsets, qualified views, features, models and receipts
use verified read-only hardlinks to those owned blobs. Identical bodies reuse
an inode; independent receipt bytes retain their actual retrieval clocks.
Only declared staging and small current-report pointers can replace aliases,
and previous canonical blobs remain retained and counted. No symlinks or
external hardlink aliases are accepted.

The ceiling is at most 512 MiB of unique file bytes by `(device, inode)` across
all registered roots. Logical referenced bytes are reported separately. This
is file-size accounting, not filesystem block allocation. Retained orphan
blobs, incoming partials, manifests, failures and control metadata count. A full
store abstains before another incoming write; finite storage cannot retain
unlimited distinct vintages. Failure markers require capacity too. Failure to
persist one is surfaced as an error and is never reported as saved evidence.

## Operational routes

The existing workflow remains one job with a 40-minute cap and the same command
ceilings: daily 540 seconds, acquisition 180, references 720, grading 180.
Daily, acquisition, reference learning, grading and workflow replay use the
explicit v2 policy. Sleeper/ESPN prefetch, offseason and grading responses use
`operational-live-v2`, without reading or writing legacy live cache paths.
The optional baseline intake uses a private subdirectory there. Command,
cadence, restore and attestation receipts use registered quota serializers.

`tools/restore_state.py` restores only local already-fetched Git state blobs.
It rejects unsafe paths, symlinks and ownership controls, checks declared blob
sizes before reading bytes, and checks both quotas before publication. Same-byte
existing originals retain their inode and mode. Conflicting originals fail.
Git metadata and repository bootstrap are separate from operational artifacts;
restored state payloads and publication aliases count toward the shared quota.

## Publication remains pending

This packet does not authorize a hosted run or publish any private weights.
V2 `tools/persist_state.py` requires a separately frozen content review through
`--publication-manifest`. Without it, publication stops before Git operations.
The future manifest has exactly these fields:

```json
{
  "schema_version": "operational-publication-review-v2",
  "review_state": "ACCEPTED",
  "policy_sha256": "<exact policy file SHA256>",
  "files": {"health/<record>.json.gz": "<exact file SHA256>"}
}
```

Paths are relative to the state directory. The list can select reviewed
aggregates while leaving private rows and weights excluded. Symlinks, absolute
paths and traversal are rejected. Every published path must match its reviewed
hash. Existing remote paths cannot change, and omitted index entries remain
untouched. Publication staging uses owned quota aliases and literal Git paths.
Local ownership markers and writer locks are omitted. New publication timing
receipts stay local until a later exact content review includes them.

Real reference fitting and inference still require the separately frozen
22-package runtime and review. Hosted execution, missed schedules, rollover,
rollback and content approval remain future acceptance work. The website and
its scheduler remain read-only references.
