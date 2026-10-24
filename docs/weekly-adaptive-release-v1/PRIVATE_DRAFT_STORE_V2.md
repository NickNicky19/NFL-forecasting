# Private runtime draft store v2: implementation and preparation

**PREPARATION ONLY. No actual HTTP, credential access, new draft, canary upload,
restricted payload upload or operational activation occurred in this packet.**
Requested model GPT-6.1 Sol / xhigh; actual backend UNATTESTED.

## Revision 2 / catalog v2.1: review findings retained and repaired

Independent review requested changes to the first 23-test implementation:
incomplete proof schemas, missing phase-input GO pins, unresolved POSTs missing
from slot accounting, and inability to reuse a verified completed digest blob.
The exact original preparation receipt is preserved separately as
`reports/private-draft-storage-v2/PREPARATION.initial23.json`; commit 8319230 and
all original canary failures remain. The old tests were narrower than the
required contracts, and their pass is not retroactive approval.

Proofs now use closed phase-specific `weekly-private-proof-v2.1` schemas. The
read proof must have all ten exact ordered principal/sequence/route records;
status, message-match, rate, retry and failure flags are revalidated, not
replaced by summary booleans. The qualified proof embeds and revalidates both
complete prior proofs, with their exact hashes, three valid pairwise-distinct
64-hex process identities, distinct authenticated job IDs, source/run/attempt/
config and causal UTC clock chain. Absent identities, empty routes, unknown
fields, permission/source mismatch or future/inconsistent clocks fail closed.

Every operation GO is now `weekly-private-operation-GO-v2.1`, pinning runtime ID,
workflow/job identity and exact physical hashes of every phase input:

| Operation | Exact `input_sha256` fields |
|---|---|
| initialize | empty object; exact `runtime_id` is mandatory |
| pin | binding |
| boundary | binding, before |
| qualify | binding, before, read_proof |
| append | binding, payload_manifest, qualification |
| restore | binding, descriptor |

Append additionally retains its exact canonical manifest/qualification pins.
An input substitution is rejected before token discovery or HTTP. Actual CLI
execution requires a genuine hosted Actions context and exact detached source
checkout, then authenticates the running run/source/workflow and current job
against GitHub API metadata. The workflow must explicitly check out
`${{ github.sha }}`, grant `actions:read` in every phase, and leave API job names
equal to the job IDs. Contents permission remains read only in the boundary
job and write in the other phases. There is no local-owner credential route,
environment fabrication, or token-prefix masquerade bootstrap in this code.
Tests inject a fictional transport and explicitly labelled fictional context;
those proofs are incompatible with actual Actions proofs.

Unresolved asset POST reservations now consume both bytes and asset slots. No
129th asset is sent when retained/pending slots have reached 128. A completed
existing `blob-<sha>.bin` may be reused only after exact name/size/server digest,
runtime membership, uploaded state, full byte/hash readback and fresh draft
checks. Reuse issues GETs, never a replacement/repeated blob POST. Incomplete,
corrupt or mismatched assets fail. A prior ambiguous POST is not retried; a new
explicitly authorized operation may verify its completed result and reference
it, while retaining the original reservation/failure evidence.

The explicitly versioned `private-runtime-kinds-v2.1` catalog adds
`feature_snapshot`, `source_snapshot` and `identity_snapshot` for later real
capture. Config and formal schema are repinned for review. A kind name grants
no source rights: exact source policy, payload manifest and restricted-write GO
remain mandatory; raw source is never placed in a public export. Actual rights
review and every actual runtime/qualification/upload remain pending.

## Separate acceptance and preserved failures

The root's `DRAFT_STORAGE_V2_REVIEW.md` and observed diagnostic run 40078527990
motivate a new engineering criterion. The original strict 404 canary remains
INCONCLUSIVE, including original/recovery runs 40072854281/40073778089. Its draft
422575680, original single-asset identity, source and scheduler are untouched.
This implementation explicitly rejects that release as a runtime destination.

V2 requires fresh write-token exact 117byte canary restoration with unpublished
draft checks, valid own-repository authentication and anonymous public positive
controls, all six anonymous API/browser routes 404, and all four authenticated
read-token API routes either 404 or the exact 403 resource-permission response
with nonzero rate balance and no Retry-After. Arbitrary 403, 429, 2xx/3xx,
transport failure or partial controls do not qualify. The after-read fresh write
process restores exact bytes and rechecks the draft. Three proofs bind the same
current source/run/attempt, config and runtime. Qualification phases must use
different process identities. Nothing changes the original 404-only result.

The new runtime is accessible to repository writers/administrators. It is not a
vault against them. Qualification of the harmless runtime does not authorize a
restricted source/payload by itself.

## Concrete code and finite limits

- `nfl_lab/private_draft_store.py`: append-only blob and restore-manifest
  production, bounded inventory, private local files, independent restore and
  qualification functions.
- `tools/private_draft_store_v2.py`: explicit operation CLI. Without `--execute`
  it performs no credential discovery or transport. Execution additionally
  requires a physically hash-pinned operation GO, exact repository/source/run/
  attempt/permission identity and the existing single-writer contract.
- `config/private-draft-storage-v2.json`: exact code-pinned configuration;
  changing bytes requires a new reviewed version. Its false preparation flags
  report the current authorization state; they are not a source of permission.
- `schemas/private-draft-store-v2.json`: closed payload and operation-GO schemas.
- `nfl_lab/private_draft_probe_helpers.py`: only unchanged fixture, redirect and
  positive-control helpers from the retained probe. The requested lab base lacks
  the separate probe tool, so the new standalone checkout cannot import that
  external worktree. No old transport is copied: the new opener preserves the
  session's default proxy and CA handling and has no cookie jar or automatic
  redirects. The preparation receipt binds the exact helper provenance.

Each operation has at most 40 HTTP exchanges, 120 CPU seconds, 180 wall seconds
and 512 MiB address space. One real exchange, including response reading, has at
most 20 seconds. No child process or retry is started by the CLI. Asset bytes are
at most 8 MiB, runtime retained bytes 32 MiB, asset count 128. Response metadata is
at most 256 KiB, operation transfer 40 MiB, each list page 100 records and at most
four pages. A short final page is required; malformed/duplicate/incomplete
inventory fails. Every listed asset, including unknown/orphan names, counts.
Unknown size/state or an asset over the cap fails rather than being ignored.

Before every asset POST, inventory reserves capacity and a private O_EXCL,
fsynced reservation consumes the attempt before transport. Every unreconciled
reservation is conservatively charged in addition to listed assets. Exact
server name/size/digest membership avoids counting a successful reservation
twice. Existing names are never overwritten. Ambiguous POSTs have no automatic
retry; partial/orphan assets and reservations remain for explicit reviewed
GET-only reconciliation. Creation has the same durable no-retry reservation.
The journal must remain dedicated to this runtime and retained across process
handoffs; losing it is not permission to retry an ambiguous mutation.

Capacity checks require the existing `nfl-lab-single-writer` workflow concurrency
contract. GitHub has no transactional compare-and-reserve API for this draft;
the prototype does not claim cross-host quota safety against independent
concurrent writers. Root must pin the actual existing workflow before execution.
Repository writers can change/publish drafts; fresh checks stop the producer
when observed, but cannot prevent a writer from doing so between API calls.

Authentication is constructed only for exact same-repository api.github.com or
uploads.github.com routes. Download redirects permit only the retained known
GitHub CDN hosts, at most two hops, using freshly constructed anonymous headers.
No URL, signed redirect, raw header, body, exception detail, credential or
private path is printed. The CLI prints operation/state/counters/receipt digest.

## Payload and restore contract

Allowed kinds are `forecast_batch`, `outcome_snapshot`, `selection_receipt`,
`model_artifact`, `runtime_manifest`, `feature_snapshot`, `source_snapshot` and
`identity_snapshot`. Ledger and raw-feed kinds are rejected.
Non-model kinds accept JSON/gzip; model artifacts may additionally be opaque
pickle/NPZ. No model is decoded or executed. The manifest has exactly:

```
schema_version="weekly-private-payload-v2", payload_kind, format,
bytes, sha256, source_policy_sha256
```

The append GO must pin the exact canonical payload-manifest digest and exact
qualified-runtime proof digest. Manifest/body size and hash must agree. This
allowlist cannot infer legal/source rights or discover a deliberately mislabelled
opaque payload. **Before any restricted write, root must review the actual
producer, source policy, payload scope and source/storage rights.** Raw upstream
feeds, internal ledger and public raw redistribution are outside this packet.
Public selected-derived export remains the separate reviewed website flow.

One append uploads `blob-<physical_sha256>.bin` and a separately digest-named
immutable restore manifest. Each POST has a fresh unpublished identity check
before it and a draft check afterward. The remote manifest binds the blob's
asset identity, byte/hash/type/source policy and producer process/runtime.
Failures after the first POST can leave an orphan; it is retained and counted.

The actual restore command runs in a different Python process. It verifies
both assets are members of this exact runtime, checks metadata/hash/length,
fetches the exact remote manifest and payload, rechecks unpublished draft state,
and creates the local destination using O_EXCL/0600. A directory-descriptor
O_NOFOLLOW walk rejects ancestor and final symlinks, including replacement
races. Files and parent directory are fsynced; an existing/partial destination
is never overwritten or deleted. It rereads the exact local bytes and emits a
private restore proof with actual completion timestamp. No producer should
claim durable issuance until that independent restore proof exists.

Process identity hashes Linux boot ID, PID and process start ticks. This is a
local separate-process witness, not a claim of a second host or remote service.
No `/proc/.../task` discovery or scientific process/memory inspection is used.

## Minimal existing-workflow integration contract (not applied)

No workflow, scheduler, original probe or data guard is changed here. The normal
writer/lease and `nfl-lab-single-writer` group must remain. First integrate and
review exact source/config/schema and workflow permissions; root then supplies
one initial harmless runtime GO. Use only the existing automatic GitHub token.

1. **Initialize, contents:write:** one new runtime ID, one draft and one 117byte
   canary. Opaque IDs and canary hashes are not an obscurity boundary. Stop on
   any ambiguous POST; do not rerun automatically.
2. **Pin, fresh contents:write process:** exact canary readback and draft checks.
3. **Boundary, contents:read job:** positive controls plus all ten known-ID
   negative routes under the v2 criterion, pinned to the prior write proof.
4. **Qualify, fresh contents:write process:** exact before/read proof hashes,
   same source/run/config and final independent canary restoration. Failure or
   cancellation of a required phase prevents qualification.
5. **Append, contents:write:** only after separate runtime acceptance and actual
   payload/source review, with exact payload-manifest and qualification digests.
6. **Restore, new contents:write Python process:** exact remote/local readback
   and post-read draft check. Its receipt is required before operational use.

Each phase is an explicit CLI process:

```text
python3 -I -B tools/private_draft_store_v2.py OPERATION --execute
  --authorization PRIVATE_GO --authorization-sha256 EXACT_PHYSICAL_GO_SHA
  --journal PRIVATE_0700_JOURNAL --receipt NEW_PRIVATE_RECEIPT
```

Initialize adds `--runtime-id`; other phases add `--binding`. Boundary adds
`--before`; qualify adds `--before --read-proof`; append adds `--payload
--payload-manifest --qualification`; restore adds `--descriptor --destination`.
The phase's environment must match GITHUB_ACTIONS=true, exact repository,
workflow_dispatch/run_attempt 1, source SHA and run ID, plus STORE_PERMISSION.
No token is an argv value. Source-specific private input
locations are supplied as private CLI arguments and never emitted by the CLI;
the example uses placeholders rather than actual filenames or payloads.

Root permits cross-job public-safe outputs containing only opaque release/asset/
runtime IDs, source/config/fixture/proof digests, byte counts, statuses and proof
booleans. Draft browser routes can use a strict opaque `browser_tag` identity
(`untagged-<20hex>` or this runtime tag), reconstructed locally into the fixed
GitHub route. Never pass signed URLs, bodies, tokens or private filesystem paths.
Disable shell tracing and use non-sensitive fixed temporary basenames and unexpanded shell variables in workflow run text; do not echo private command arguments. No private receipt/model/forecast is attached as a public workflow artifact.
Any concrete restore-manifest public metadata projection still needs the
declared scope review; this CLI does not automatically export one.

## Executed fictional evidence and outstanding actual work

The revised focused suite passed 35 methods, including actual fresh-process exact restore
against the in-memory fictional service. It covers the precise403 criterion,
mandatory controls, incomplete/bad proofs, draft mutation, retained orphans and
pending charges, pagination/caps, wrong types/hashes, ambiguous POST no-retry,
append-only behavior, redirect header stripping, exact GO CLI execution,
corruption, O_EXCL and symlink-race failures. All transport calls were injected
mocks; no real endpoint or credential was touched. The earlier 21/23-method
passes remain recorded with the independent changes-requested finding; focused
revision runs overlap and are not cumulative distinct evidence.

Actual runtime canary creation, new-runtime boundary qualification, genuine
separate-job readback, persistence/retention operating checks, actual source
rights/payload review, producer wiring and provisional publication remain
UNRUN. This implementation is reviewable code, not permission for those actions.
