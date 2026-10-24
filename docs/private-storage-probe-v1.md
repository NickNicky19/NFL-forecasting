# Harmless private-storage canary

This is preparation for one separately reviewed manual `storage-probe` run in
the existing LAB workflow, published only to a feature branch from `0c4d8a3`.
The planned dispatch explicitly selects that feature ref and `storage-probe`;
this probe does not require a main merge or a push that starts the data job.
Implementation and its mocked tests perform no HTTP; a separate root-run hosted
attempt is preserved below. This enables no sensitive producer and makes no private
durability claim. Owner authority is recorded by the integrator in
`docs/weekly-adaptive-release-v1/OWNER_AUTHORITY.md`.

The same workflow and `nfl-lab-single-writer` concurrency group contain three
dependent jobs, each with a fresh automatic same-repository `github.token`:

1. **Write, contents:write:** verify the target repository and absent run-specific
   tag, create one unpublished draft, recheck its identity and upload one harmless
   fixture of at most1KiB. Verify exactly one matching asset. There is no repeat
   POST, overwrite, delete, publish, cleanup or ambiguous-failure retry.
2. **Read, contents:read:** authenticate the repository-scoped job token with
   its own exact repository metadata and public visibility. Independently prove anonymous public
   metadata/asset/API-octet/browser routes using the fixed `cli/cli` `v2.0.0`
   checksum asset; the job token is never sent to another repository. Require404
   for authenticated read-only and anonymous API access to the known canary
   release metadata, asset metadata, asset list and octet route. Browser checks
   after each API group are both anonymous, labelled
   `anonymous_browser_after_read_only_api_404` and
   `anonymous_browser_after_anonymous_api_404`. They do not establish coverage
   of an authenticated browser session. Any2xx/3xx
   response fails the private boundary, including an empty200 list. A403,
   authentication/rate-limit/transport failure is inconclusive and fails the job.
3. **Restore, contents:write:** only after read succeeds, recheck the same draft
   and single asset before an authenticated API-octet download, stripping auth
   from any signed CDN redirect. Require the original exact fixture bytes and
   SHA256, then re-read and pin the unchanged unpublished draft and single asset
   before reporting PASS. Browser URLs remain unauthenticated negative checks; a private browser
   URL is not expected to succeed in restore. A changed or missing draft fails.

The denied read job cannot inspect draft fields by definition. Its IDs and hash
come directly from the write job; the fresh restore job confirms the same draft
after the negative checks. All accessible canary metadata must match the exact
repository, release ID, tag and asset identity, with `draft=true` and
`published_at=null`. No inaccessible response is treated as a metadata witness.

Probe requests have20-call and1MiB request/response-body transfer ceilings per
job; each entire real HTTP exchange has a20s hard kernel deadline (including
slow response reads) and a20s socket timeout. The script has120CPU/wall
limits and512MiB address space, and workflow/external timeout ceilings are3min
and180s. Public controls and ten negative checks normally consume17 calls, with
at most19 if both public downloads need two redirects. No probe artifact is
uploaded. Checkout and runner platform traffic are outside the probe HTTP client
counter. No package install, paid fallback, key, account or private NFL input is
used. Only this workflow's manual probe mode skips the unchanged LAB data job.

Authentication is allowed only to exact `api.github.com` routes and the one
validated official `uploads.github.com` asset POST. Manual redirects can reach
only three exact GitHub asset CDN hosts and never receive Authorization.
Browser downloads never receive Authorization. Unexpected routes, hosts,
methods, metadata and redirects fail closed. Signed URLs, response/error bodies
and tokens are never emitted. Output is a bounded public-safe summary of states,
booleans, counters, IDs and the harmless fixture hash; every phase records
`private_durability_qualified=false`.

Reviewer corrections retain all previous attempts. The final restore state
check occurs after the real byte download; a concurrent publication, draft-ID
change or asset removal fails. Positive controls distinguish the authenticated
own-repository lane from anonymous external public lanes. Browser fields make
only anonymous claims. No hosted probe is authorized by this code correction.

## Local verification

Only the new stdlib mocked suite was run:

```bash
python3 -I -B -m unittest discover -s tests -p test_private_storage_probe.py -v
```

First run:12 methods,11 passes and1 failure in0.024s. The mock draft helper
converted an intentionally invalid `assets=None` to an empty list. Correcting
that helper preserved the malformed input for the existing rejection guard.
Second run:12 methods,12 passes in0.017s. After extending hard-deadline, upload
and restore-failure checks, the next run also passed12/12 in0.016s.
The fourth run, including the exact original LAB-job-body SHA check, passed12/12
in0.017s. Final static review removed an overstrict unauthenticated-browser
restore requirement, which would contradict the browser-denial check. The final
API-only authenticated restore version passed12/12 in0.023s.
After the three independent-review corrections, the expanded14-method suite
passed14/14 in0.026s. It additionally rejects post-download draft/asset mutations
and checks authenticated-own-repository versus anonymous-external control routes.
Transport is injected throughout;
no HTTP, release, upload or workflow dispatch occurred. The suite covers all
ten read failures, public-control failure, draft/asset changes, restore mismatch,
token/scope/attempt guards, redirect/auth handling and finite request budgets.

Actual success requires verification of all three hosted jobs in the same
single-attempt run plus independent review. Until then the storage candidate is
unqualified. A read-only token that can read the canary is a real boundary
failure; no alternate interpretation or sensitive use is authorized.

## Existing-canary recovery v1: separate review and authorization

Actual hosted run `40072854281`, source `c57d8e6` (the same four source blobs as
local `dcf07089d81e4d5e1b1c07823a722063563601b7`), failed WRITE with
`ASSET_IDENTITY_REQUIRED` after five HTTP calls. Draft release `422575680` and
asset `671552361` were created. Read and restore jobs did not run. The harmless
fixture is117bytes with SHA256
`e9c2a9701a6588a3367f4be0fc086633a031fba35dbc3f8e5f8139c4bb48b19a`.
This failure remains evidence; no reupload, recreation, deletion or automatic
retry is proposed.

Root's two read-only diagnostic GETs found that GitHub's draft asset browser URL
uses `untagged-0a85e829d75c8e410fb0`, despite the intended original tag. The old
creation path and its strict tag-based URL check remain unchanged. A new exact
browser contract, `exact-existing-untagged-v1`, is confined to recovery of this
single existing harmless asset. The reviewed config
`config/private-storage-existing-canary-v1.json` fixes the repository, original
run, release/asset IDs, original tag, asset name/size/digest and complete HTTPS
own-repository browser URL. Its full file SHA is authenticated by the script.
No destination or config path is accepted from CLI input.

The new manual mode is `storage-probe-existing`, in the same workflow and three
jobs with fresh automatic write/read/write tokens. The first job calls
`existing-pin`: GET metadata pins the unpublished draft and single asset,
including the exact20hex `untagged-` URL and genuine digest. It downloads the
original exact body through the authenticated API with no auth sent to the CDN,
then checks the draft/asset again. It emits only public-safe IDs, hashes and the
new recovery run identity. `existing-read` requires those same-run pin outputs
before public controls and all ten negative checks. `existing-restore` requires
the same pin, the successful read job, exact original body/hash and a final
draft/asset pin. All recovery clients categorically reject every non-GET method.

The fixture and desired tag always bind original run `40072854281`; each new
receipt separately identifies the actual recovery run and schema
`lab-existing-canary-recovery-v1`. A rerun of the original run or attempt2 is
rejected. No Authorization reaches browser/CDN hosts. Typical calls are5 for
metadata pin,17 for read and5 for restore; maxima are6/19/6 with two CDN redirects,
within unchanged20-call/1MiB and120CPU/180wall/512MiB bounds. The whole script
still has the original120s hard wall limit.

This is a separately reviewed evidence-recovery run, pending new root GO. It is
not a retry of either POST. A read-only token that can access the existing draft
still fails the private boundary. No successful read/restore or private durable
qualification is inferred from the original creation or these fictional tests.

Recovery preparation ran only the expanded local mocked suite:21 methods,
21passes,0failures in0.044s. The fourteen prior test methods remain, with the
workflow skip assertion extended to include the recovery mode. Seven new methods
cover exact config/origin binding, GET-only pinning, pre-anonymous asset rejection,
same-run pin proof, distinct recovery receipts, fixed anonymous browser checks,
config tamper and post-download mutation. No HTTP or hosted dispatch occurred
during this recovery preparation.

## Diagnostic-only v1: collect all routes without changing qualification

Actual existing-canary run `40073778089` completed its fresh write-token pin:
the117byte original body restored exactly and the final draft check passed.
The read job stopped at eight HTTP calls with `INCONCLUSIVE_DENIAL`, before its
anonymous routes completed. Restore was skipped. This failed/incomplete privacy
result stays retained; it does not establish a private boundary.

The separately reviewed manual mode `storage-probe-diagnostic-v1` proposes at
most one third GET-only hosted diagnostic with the identical immutable source
config, original run `40072854281`, release/asset IDs and harmless fixture. It
creates, uploads, overwrites, publishes and deletes nothing. New receipts use
schema `lab-existing-canary-diagnostic-v1` and explicitly retain both earlier
failed run identities. The normal creation/recovery modes keep their original
fail-fast404 qualification and restore-after-success rules.

Three fresh automatic-token jobs run diagnostic-pin, diagnostic-read and
diagnostic-restore. The first and last reuse exact before/after unpublished
draft/single-asset pins and body/digest/hash readback. The read phase requires
valid own-repository authenticated positive control and anonymous public
metadata/download controls before sampling all ten protected routes, even when
an earlier route returns403. Browser requests remain anonymous. Each record
contains only constant route/principal labels, integer status ornull, old-rule
classification and booleans for exact message equality to GitHub's resource
permission message, rate-header presence/nonzero, retry-header presence,
request-ID presence and request failure. No raw header values, request IDs,
response/error bodies, token or signed URL is emitted.

The message-match boolean is diagnostic evidence only:403 remains inconclusive
even with a nonzero rate limit and exact resource-permission message. Every
2xx/3xx protected response explicitly sets FAIL_PRIVATE_BOUNDARY, including a
response whose oversized body is rejected before full reading. Protocol or
transport failures remain inconclusive. All routes are sampled within the old
20-call/1MiB/20s-request/120s-script/3min-job ceilings, without retry.
Any visible/inconclusive route makes the diagnostic read job NONZERO; the
workflow may therefore conclude failure. No continue-on-error hides that state.

Only after valid controls and all-route collection does the failing diagnostic
read step emit a public-safe completion flag. Only this diagnostic mode may run
fresh write-token restoration after that completed failed read, requiring the
flag plus the same-current-run config/fixture pin outputs. Cancellation,
failed/incomplete controls or missing pin outputs do not authorize it. Normal
modes still require success. The fresh restoration teaches only that the write
token can retrieve this harmless body; it cannot rescue privacy qualification.
Every receipt keeps private_durability_qualified=false. There is no sensitive
producer activation, second cron, new account/key/spending, or actual hosted
diagnostic executed during this preparation. Root retains the separate exact
review and one-run GO.

Local diagnostic preparation ran28/28 mocked methods successfully in0.072s,
including the21 retained methods and seven new diagnostic methods. These cover
all-route403 collection with unchanged old fail-fast behavior, visible/redirect/
oversized200 privacy failures, safe output redaction, mandatory controls,
nonzero-read completion output, narrowly gated fresh restoration, transport
errors and no retry. The existing source config hash is unchanged. No actual
HTTP, dispatch, upload, deletion or NFL value read occurred in this preparation.
