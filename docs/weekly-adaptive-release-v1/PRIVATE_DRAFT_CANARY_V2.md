# Hosted harmless draft canary v2: integration preparation

**Prepared, not dispatched or qualified.** No HTTP, credential access, new draft,
canary upload, NFL upload, source publication or ledger mutation occurred here.
Requested model GPT-6.1 Sol / xhigh; actual backend UNATTESTED.

## Exact publication and preserved old behavior

The approved existing workflow was copied from its exact
`dd6492ebb83d22a65fdf3a7173d55ee042798ac7fbdab7a4deac4cf146870dfd`
bytes. The publication base is the already published feature branch commit
`8df7575230fce4c3498bd31042e5dfb775f247ac`. Root must apply only the owned new/
changed files onto that existing tree; this isolated lab base lacks the old
probe files, which are inherited unchanged from the publication base. This
packet does not duplicate, edit or import the old probe/config.

The old normal job and three old probe jobs retain byte-identical behavior.
Only the new dispatch choice and an extra exclusion in the normal lab job are
added ahead of three appended jobs. A fictional source comparison reverses
those two edits and proves the original workflow prefix is exact. There remains
one scheduler and one `nfl-lab-single-writer` concurrency group with
`cancel-in-progress:false`. Existing scientific/data guards and the old strict
v1 INCONCLUSIVE result are unchanged.

## One new runtime, four operations, three roles

The one registered runtime ID is
`069fb200e34e624599aa916455de358a`, derived exactly as
`SHA256('NFLweeklyruntime20261024v2')[:32]`. A repeat run cannot create another
draft under a new ID: the ID is fixed in both code and configuration, old
attempts are not retried, and an existing runtime tag fails before a POST.

| Existing workflow job | Automatic token permissions | CLI operations | Step wall cap | Job cap |
|---|---|---|---:|---:|
| private-draft-v2-write | contents:write, actions:read | initialize, then pin in a fresh Python process | 360s total | 8min |
| private-draft-v2-read | contents:read, actions:read | boundary | 180s | 4min |
| private-draft-v2-qualify | contents:write, actions:read | qualify in a fresh process | 180s | 4min |

Every checkout uses the exact `github.sha`, `persist-credentials:false` and
fetch depth1. Default job names equal their IDs so the genuine Actions job API
checks bind correctly. The read job requires successful write; qualification
requires both predecessors successful and no cancellation. No continue-on-error
or failed/partial-read restoration exception is used in this new mode.

Each native CLI retains120 CPU seconds,180 wall seconds,512MiB address space
and40 HTTP calls. Four calls give at most160 HTTP exchanges overall, including
all control/Actions metadata/download redirect requests. Driver processes also
have finite120 CPU/512MiB limits; children are sequential. Driver step deadlines
are360/180/180s and the native child timeout uses the remaining phase allowance.
The external GNU timeout kills the whole inherited process group; the driver
kills/reaps an unfinished native child on caught failures. There is no child
retry or second scheduler. Per-process limits are not an aggregate sampled RSS
claim; actual hosted resource measurements remain unrun.

Only `initialize`, `pin`, `boundary`, `qualify` are admitted. `append`, `restore`
and every restricted payload path are disabled in this driver, including model,
feature, source, identity, forecast and outcome uploads. Initialization creates
one unpublished draft and one117-byte fixture constructed from the run ID.
Actual token/source/run/job API checks remain in each native CLI. There is no
local owner-token route, fabricated Actions bootstrap or new credential.

## Source pins and GO/handoff boundary

`tools/private_draft_canary_v2.py` verifies the exact immutable canary config and
its source pins before importing the store or launching a credential-reading
CLI. Pins cover the new core and helper, package initialization, native CLI,
store config, formal schema and complete workflow. The driver itself is anchored
by the exact detached immutable checkout and the separately reviewed source
manifest in the preparation receipt. Its config hash is embedded in its source;
no caller can supply another config/path or arbitrary CLI operation.

The driver validates the actual hosted dispatch mode, run attempt1, repository,
source/workflow SHA, job role, detached checkout and dispatch event. Native CLIs
then authenticate the running run/source and current in-progress job using the
Actions API. No token value is read or printed by the orchestration layer.

The first explicit root-approved manual `private-draft-canary-v2` dispatch is
the proposed canary-only GO. This preparation is not that approval. The driver
can generate the v2.1 operation GO files only for the four registered operations,
with fixed runtime ID, exact current source/run/job/workflow/config and exact
physical hashes of canonical inputs. Payload/qualification authorization fields
remain null because no restricted append/restore is possible.

Write outputs canonical binding/before-proof JSON and their SHA256; read outputs
canonical read-proof JSON and SHA256. They contain only the harmless draft/asset/
runtime/tag identities, source/config/fixture/proof/process hashes, job/time
metadata and closed status/boolean route records. All are validated again at
handoff. Empty, substituted, noncanonical, mismatched, partial or extra-field
documents fail. Temporary files are private0600 under a dedicated0700 runner
directory; no temporary folder or file tree is uploaded.

The qualifier prints exactly two final records for root readback:

```
PRIVATE_DRAFT_CANARY_BINDING_V2 <canonical safe binding JSON>
PRIVATE_DRAFT_CANARY_QUALIFICATION_V2 <canonical complete safe proof JSON>
```

The write phase also prints the validated initialized binding, so harmless
destination identity survives a later pin failure. Child failures expose only
strict safe reason/counter metadata; stderr, raw exception details, URLs,
headers, bodies, tokens and private paths are suppressed. No workflow artifact
upload step exists in the new jobs. A successful canary engineering proof is
not restricted-source approval, operational NFL persistence, or a scientific
qualification; old v1 remains INCONCLUSIVE.

## Fictional evidence and next concrete action

The focused suite covers the prior35 store checks, two new strict restore-proof
consumer checks and nine driver/workflow checks:46 methods in total. Driver
tests simulate all three roles/four CLI invocations with explicitly injected
identities and transport; they do not claim genuine hosted processes/tokens.
The existing store test separately restores fictional bytes in an actual fresh
Python process. Workflow tests prove old-prefix equality, one scheduler, exact
checkout, roles, success/cancellation gates, no installs/artifact upload, and
that payload operations cannot obtain a driver GO.

Root must independently review exact source/config/schema/workflow, apply these
owned files to the existing publication base, verify the published source pins,
and explicitly authorize at most one manual dispatch. Actual platform syntax,
hosted token/job checks, boundary evidence, canary readback and measurements
remain UNRUN. Any failure is retained; no automatic retry or cleanup is added.
Only after a successful new-runtime canary packet and separate actual source/
payload rights review could a later private NFL producer be considered.
