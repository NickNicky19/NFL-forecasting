# Genuine hosted private checkpoint: preparation

This packet adds no scheduler, owner token route, actual HTTP or NFL execution.
It reuses `private_draft_store.append/restore`, the deterministic opaque bundle
codec and its existing owned-CAS extraction/manifest relocation. The codec's
historical schema names are format identities; every new writer/restore origin
here is `github_actions`. No owner-origin proof is accepted or fabricated.

The controller is deliberately disabled: its procedure is
`PREPARED_PENDING_ROOT_REVIEW_AND_GO`, and its compiled config seal is pending.
Root must review, merge the fixed-build packet, wire the existing workflow, pin
the final workflow/helper/source bytes, approve the exact procedure and seal its
config hash before execution. The normal whole-commit checkout anchors the CLI
itself; its own bytes are excluded from the config pins to avoid a hash cycle.

## Exact required payload

Before source acquisition or fitting, a claim step in the same genuine job
uploads only the exact canonical root registration `9fdae2...ca72`, using
`manifest-<registration SHA256>.json`, with reuse disabled. It fully reads back
the asset and writes a canonical safe receipt to
`<RUNNER_TEMP>/<build-mode>-<run>/private-checkpoint-claim/CLAIM_RECEIPT.json`.
The root's physical registration pin is `4c526ccd...d85802c` from commit
`4179899`; the old prepared/null registration is not accepted.

The receipt schema is `weekly-gha-private-checkpoint-v1-source-claim`. Its closed
keys are schema_version, state (`ONE_TIME_SOURCE_CLAIMED`), repository, run_id,
source_sha, job_id, api_job_id, process_identity, registration_sha256,
registration_bytes, asset_id, asset_name, binding_sha256, procedure_sha256 and
claimed_at. Procedure SHA is the physical checkpoint config SHA. Safe
`claim_receipt_json`/`claim_receipt_sha256` step outputs feed the worker's
`BUILD_CLAIM_RECEIPT_JSON`/`BUILD_CLAIM_RECEIPT_SHA256` environment. Root supplies
the separate worker change that checks physical receipt equality, real current
job identity and exact remote registration readback before provider reads.

Claim initializes the shared future build root and original quota owner before
the worker. The worker must verify that claim and reject preexisting consumed,
source/fit/model/result markers before reusing the root. No alternative cache
owner or extra quota is introduced. Any existing claim name rejects a new
dispatch of the same registration before data access. Ambiguous claims retain
their reservation and stop. The existing global workflow concurrency serializes
actual runs; this check-and-upload sequence is not an independent atomic
transaction across unrelated external writers.

The same producer **job** is `genuine-hosted-fixed-build-v1`. Its training worker
exits before this fresh helper CLI step starts: the worker's source audit is
preserved. The helper authenticates the actual Actions run/source/job through
the existing API validator before reading private build metadata or bytes.
It accepts only a complete `GENUINE_HOSTED_FIXED_BUILD_V1` result whose genuine
job identity equals that authenticated producer job and whose 18 slots exactly
match 11 CDF, 2 CountA and 5 CatBoost fixed jobs. Failed/partial builds stop.

All 78 files are required; there is no optional dropping or recursive archive:

| File cohort | Count | Kind |
| --- | ---: | --- |
| New trained bodies | 18 | `model` |
| Original future-inference manifests | 18 | `model_manifest` |
| Exact e7 policy raw sources, 2019–2026 | 19 | `source_raw` |
| Original receipts for those sources | 19 | `control` |
| FINISHED as BUILD, BUILD_REGISTRATION, SOURCE_READBACK, source-manifest | 4 | `control` |

The original daily raw namespace and 38 source bindings must exactly match the
19 expanded e7 URL/name templates. Original source receipt status, URL and body
hash are checked. Source raw and model bodies are hashed/encoded opaquely;
neither Parquet rows nor serialized models are decoded. Every input must be an
immutable alias in the original build's existing owned CAS. Only the original
manifest/receipt/control JSON metadata is decoded.

Training feature tables and separate slot files are not silently added. Their
provenance/slot receipts already remain in the required BUILD/manifest metadata.
The raw snapshot can later feed unchanged
`acquire_operational_history(source_cache=<restored source-cache>)`, which
verifies/adopts original body/receipt bytes without another download. Feature
rebuilding and future inference need their own registered execution; the helper
does neither.

## Admission, append and failure

At most 8 opaque groups, at most 64 files per group and at most 8 MiB per asset
are allowed. All groups are fully encoded and hashed in memory before the first
checkpoint payload POST. The earlier claim POST contains only root control data.
The complete private index is also preflighted using maximum-length future
asset IDs. It has a 256 KiB bound (with compression headroom), records exact file
lists, original origins, group descriptors, explicit path mapping and 18 model
pairs. It is appended as another private `runtime_manifest/gzip` payload.

Before the first POST, a fresh draft/inventory check must fit every required
group, the index and conservative per-entry metadata reserves within the
unchanged 32 MiB runtime cap and 128 asset slots. All existing unknown/orphan
assets, canary bytes and pending POST reservations count. Each later native
append repeats the unchanged core inventory/draft checks. The global existing
owned storage quota remains 512 MiB, including staging, compressed downloads,
CAS copies, aliases, controls and receipts.

The old failed metadata reservation remains an authentic safe input: 80,745
bytes, one slot, `manifest-baca684...0c0e9.json`. Its exact metadata is copied
into the new operation journal without sending a POST. Core inventory resolves
the extra charge only if exact name/size/server digest proves the asset already
exists. No old request is claimed successful or automatically retried.

Before each append, a private native GO receipt binds the registered procedure,
actual job/run/source/runtime, computed payload-manifest hash and exact computed
scope hash. Its authority is `ROOT_APPROVED_PROCEDURE`, with no human approval
claim. These are narrow post-build scopes derived under the reviewed procedure,
not a new upstream rights claim. Only the explicit e7 private whitelist is in
scope; public raw/source/model export is zero.

An ambiguous POST stops immediately and preserves its reservation; no automatic
retry occurs. Failure output exposes only a finite reason, counts and safe
reservation metadata. The next separately authorized attempt must carry those
reservations forward. A complete checkpoint or handoff is not claimed on a
partial append. A full snapshot that does not fit fails without increasing quota
or omitting required source/model files.

The hosted client also emits safe name/hash/byte intent metadata immediately
after the unchanged core reservation is written and before transport. This
lets root conservatively carry an unresolved reservation after runner loss or
hard termination. It contains no URL, body, token or private path and makes no
POST-success claim. Successful acknowledgement is still a separate event.

## Fresh-job restore

The separate `genuine-hosted-fixed-build-restore-v1` job uses the same ordinary
automatic `contents: write` token with `actions: read`. It authenticates its own
actual current job and verifies the exact producer job succeeded and completed
before this job started. Only a safe digest-bound index descriptor and harmless
runtime identity pass via job outputs. No private paths, file list, raw body,
signed/browser/CDN URLs, model bytes or private index are printed or uploaded as
public artifacts.

The fresh process calls unchanged `core.restore` for the index, validates its
closed schema/complete scope/producer identity against actual API job evidence,
then restores each exact descriptor. Inflation is bounded before JSON parsing.
It verifies the complete group partition and extracts through the existing CAS
helper. All original 19 receipts are rechecked. Existing manifest relocation
preserves original manifests and exact newly trained body hashes while issuing
new path-bound manifest hashes. It makes no old-hash reproduction claim and
does not deserialize a model.

The private restore result contains exact per-operation standard restore proofs,
producer/restorer identities, source versions, new manifest refs, private path
mapping and source-cache root. These prove **checkpoint bytes**, not selected
forecast durability. A later selected body needs its own exact-body fresh
restore and the independently verified acceptance required by the public export
gate. No index/group proof is relabeled as that selected-body proof.

## Existing workflow integration contract

The reviewable snippet is
`website_packet/gha-private-checkpoint-v1/lab-job-integration.yml`.
It is not a new workflow and has not been applied. Root merges it after ng's
fixed-build commit `c45421a2c744d8f13da3aad7dcc9001415c58999`:

1. Add the pre-source claim after dependencies, and its safe claim outputs to
   the separately reviewed worker gate. Add safe checkpoint output mappings and
   the producer follow-on step after successful training and before termination.
2. Add the single dependent fresh restore job to the same `lab.yml`. Preserve
   the existing global `nfl-lab-single-writer`, `cancel-in-progress: false`, old
   modes, normal job and schedule. Use exact `github.sha` checkout with persisted
   credentials disabled. The normal job remains excluded for this manual mode.
3. Re-pin final workflow/helper hashes in the procedure, set its reviewed state
   and compile its config SHA into the driver. Root then authorizes one actual
   source/build/checkpoint/restore dispatch; no actual dispatch is authorized by
   this preparation.

Seal order avoids circular hashes: finish workflow wiring; seal the trainer
config and its driver; then pin those trainer files in checkpoint config; finally
compile checkpoint config's SHA into this checkpoint driver. Both drivers are
anchored by the exact reviewed checkout. The prepared config records the trainer
files from `c45421a`; they become locally available after root merges that packet.

Each phase admits at most 9 core operations, each retaining the existing
40-HTTP-call bound: at most 360 HTTP calls per phase, with no retry. The whole
checkpoint CLI is capped at 120 CPU seconds, 180 wall seconds and 512 MiB address
space, with no child process or model imports. The snippet uses a hard 190-second
outer KILL and a five-minute restore job cap. Root must account for the added
180-second producer phase in the fixed-build job's total cap. This does not
refund or reset any source/fit budget; only the separately registered fixed18
build may fit models.

The additional one-time claim uses one core client, at most 40 HTTP calls and
the same 120 CPU/180 wall/512 MiB address-space phase bounds. Its control asset
and pending/unknown reservations count in the same 32 MiB runtime. Root must
also charge this pre-source phase; repeat dispatch does not grant another fit
budget. Claim plus append thus admit at most 400 metadata/transfer roundtrips
in the producer job, with at most 360 in the separate restore phase.

The helper's logic/transport is stdlib, but the unchanged original
`OperationalStorage` imports pandas/numpy when it binds its DataFrame write
hooks. No DataFrame operation is called by this checkpoint. The producer reuses
the already installed fixed-build environment. The fresh restore job installs
only six exact bootstrap pins already present in the original requirements
lock, with binary wheels/no dependency resolution, and sets two-thread numeric
environment limits. No install was performed during this preparation. This is
not a claim that a bare fresh Python runner already has those dependencies.

The existing transport preserves session proxy/CA. API authentication stays on
the exact repository API/uploads origins; authorized CDN download redirects
strip authentication/cookies. No new credentials, local owner bootstrap,
PATCH/publish/delete, arbitrary URL, public raw export or alternate source
pipeline is introduced.

## Fictional checks

Fourteen end-to-end/negative methods passed on the complete invented 78-file
fixture, including actual fresh-Python restore, exact new manifest relocation,
source-cache readback, same-process denial, corrupt payload rejection, unknown
asset quota failure before POST, old pending byte/slot charge, safe handoff,
all-group preflight and ambiguous-POST no retry. That run used 21.920803 combined
CPU seconds, 20.995349 wall seconds, 68,059,136 bytes parent peak RSS and
66,256,896 bytes largest sequential child peak RSS. Two later pure metadata
checks passed for pretransport intent safety and the exact six-pin dependency
subset. Four additional claim checks passed for exact readback, duplicate
dispatch denial, ambiguous claim no retry and unregistered-body rejection. Those
six focused checks used 0.850914 CPU seconds and 0.384484 wall seconds. The prior
successful iterations are retained separately.

These are software checks with in-memory injected transport and invented bytes,
not real GitHub/NFL/model or predictive evidence. Original CAS bootstrap imports
pandas/numpy; no DataFrame processing, model loading, fitting, source acquisition,
credential access or actual remote operation occurred. Real serialized sizes,
complete remote admission and actual hosted/fresh-job readback remain unrun.
