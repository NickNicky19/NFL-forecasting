# Harmless private-storage canary

This is preparation for one separately reviewed manual `storage-probe` run in
the existing LAB workflow, published only to a feature branch from `0c4d8a3`.
The planned dispatch explicitly selects that feature ref and `storage-probe`;
this probe does not require a main merge or a push that starts the data job.
No hosted run, release creation or upload was executed
during implementation. It enables no sensitive producer and makes no private
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
