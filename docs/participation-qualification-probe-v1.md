# Official NFL terms prerequisite, v1

Status: **PREPARED, UNEXECUTED**. This implementation performs no acquisition until
the integrator freezes and authorizes the sole invocation. It follows the earlier
bounded metadata review in `participation-source-next-v1.md`; that review found no
identical indexed terms/game capture and did not exhaust every unindexed cache.
The census is not repeated here.

## Scope and API

`run_probe(execution_config, config_sha256)` in
`nfl_lab.participation_qualification_probe` returns a metadata receipt. The CLI is
`python -m nfl_lab.participation_qualification_probe --config PATH --config-sha256 SHA`.
The supplied config must match its exact SHA and the module's exact v1 schema,
implementation policy, unchanged source/storage policy, code, interpreter and
dependency pins. The committed config is an execution proposal, not evidence of
an HTTP request or rights clearance.

V1 requests `https://www.nfl.com/legal/terms` first. Only four exact HTTPS legal
URLs on `www.nfl.com` or `nfl.com`, declared in the config, can be redirect
destinations. Redirects are manual and each consumes another transaction; a loop,
different path, host or scheme stops without another request. No automatic retry
or redirect is enabled. Each request uses a fresh session, verified TLS, an honest
probe User-Agent and identity encoding. A no-op auth handler suppresses implicit
netrc credentials; existing managed proxy/CA configuration remains in use.

The approved-rights hash list must be empty. **Every terminal result has rights
UNKNOWN.** A successful public response, link text or permissive-looking phrase
does not establish permission. The registered Lions/Chiefs 2023 Week 1 URL is
retained as the proposed next source, but this code has no game-page or PDF fetch
branch. It does not parse text, headings, links, players, statistics or outcomes.
A later rights review must use the retained terms hash and a separately versioned
plan; v1 cannot be widened, patched into clearance or retried.

## Limits and retention

There is one actual invocation, zero retries and at most three HTTP transactions
including redirects. The total envelope is 6 MiB, with terms/HTML/PDF allowances
of 1/1/4 MiB. Terms-only v1 applies the **same cumulative 1 MiB cap across all
redirect response bodies**; the other allowances remain unused. Actual measured
transaction count may be one through three, or zero on preflight failure.

Only absent/identity `Content-Encoding` is accepted. Other encodings stop before
body consumption. Accepted encoded and decoded byte counts are identical. Every
raw read is at most 64 KiB and the remaining cumulative cap; declared oversize or
invalid lengths stop before a read. With no length, reaching exactly the cap
stops without reading an extra byte and cannot claim a complete document.
Content-Length framing does not authorize reading beyond that length.

Bodies, including partial failed captures, pass through the unchanged
`OperationalStorage` quota writer and are promoted to immutable owned CAS files.
The global private unique-file quota remains 512 MiB; nothing is deleted or
rewritten to make room. Request-consumption markers precede every attempted HTTP
transaction. Capture receipts retain response metadata, hashes, actual request
and capture clocks, received/retained counts and completeness. Original
publication time remains unknown; a Date/Last-Modified header is not promoted to
historical publication evidence. Raw bodies and paths stay private.

The capture output must be a **nonexistent child** of a separately prepared
supervisor directory, separate from the cache. Do not create or register that
child before `run_probe`; an existing child prevents another invocation. The
runner holds the unchanged global flock for reservation, releases it for HTTP,
and uses unchanged locked quota operations for each write/import. This permits
the outer supervisor to retain its own logs and enforce the job deadline.

Whole-job limits are 60 wall seconds, 60 CPU seconds, 512 MiB RSS and one numerical
thread, including imports, preflight, scans, HTTP, writes and finalization. An
authoritative external supervisor must enforce these limits from process start.
The inner budget starts at API entry and reserves three seconds for finalization;
its network alarm does not cover earlier imports/preflight/storage construction.
Inner usage fields are observations before final writes, not the whole-job
resource receipt. Failure/finished receipts are attempted through the same quota;
if quota or the outer ceiling prevents them, the supervisor must retain that
failure and must not retry.

## Evidence boundary and fictional checks

No appearance, played-zero, DNP, PPR, roster coverage, pregame availability or
historical availability claim follows. No source-policy qualification changes,
labels, training, inference, scores, publication or scheduler changes occur.

Fictional fixtures use fake HTTP responses and tiny temporary quota stores only.
They cover terms-only UNKNOWN, redirect charging/host restrictions/loops, no
retry, compression and length rejection, cumulative caps, bounded reads, partial
timeout retention, immutable CAS ownership, invocation consumption and blocked
config widening. The owner fixture envelope is 60 wall/90 CPU seconds, 512 MiB,
one numerical thread and zero actual HTTP. Exact measured usage is reported to
the integrator separately; implementation and fixture limits do not grant actual
execution authority.
