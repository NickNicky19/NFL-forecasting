# Hosted safety enforcement before qualified handover

## Scope and actual source state

This narrow patch is based on default-main commit
`3483a25d93d0419936c57af8477ec9ff6f053fb5`. It preserves the one existing
`36 13,14 * * *` cron, `nfl-lab-single-writer` concurrency, manual mode choices,
and the existing routes. It does not import the research branch, activate its
models, change either repository's settings, dispatch a workflow, or write to
the website repository.

Read-only GitHub metadata checked on 2026-10-23 established that this lab is
**public**, its default branch is `main`, and PR #1 remains draft/open/unmerged.
The fetched default workflow blob was
`1d6a8a3e148efa80fcf4e3988028559d4a9aaefc`; the default publisher blob was
`c97fcab90183d10e4c9258be6ede942766fdbe46`. The research publication at
`57b7a106a24c056c370584b79c1926d532443646` is a separate branch, not an accepted
hosted handover. Historical pins do not authorize resetting newer work.

Default-main code inspection identified two concrete policy problems:

- Its history path acquires PFR-derived snap counts, which the newer permitted
  operational source policy excludes.
- Its publisher recursively copies `state/` to the public `lab-state` branch,
  with no exact content-reviewed allowlist. Detailed forecasts, outcomes,
  model weights and input manifests require a private durability contract or
  a separately accepted publication scope.

The old publisher does not directly copy `data/raw`. Its old model schema says
it contains no raw training rows. No current source/state payload was opened
for this packet, and no actual raw-body disclosure is asserted. The evidenced
problem is the source influence and overly broad publication route.

## Minimal behavior change

Immediately after checkout, the standard-library-only
`tools/hosted_safety_guard.py` writes one bounded, fixed-schema readiness receipt
and exits **78**, `BLOCKED_PENDING_QUALIFIED_HANDOVER`. It runs before dependency
installation, state restore, acquisition, forecasts, grading, replay or state
persistence. The existing later steps skip; the blocked run does not pretend
to be a successful forecast capture.

The receipt contains coarse source/run identity and fixed readiness reasons.
It contains no player/game/source/state/model/forecast/outcome values or
credentials. It is limited to 8 KiB, created once without overwriting, and
rejects symbolic-link paths. The only unconditional upload is its exact path
`${{ runner.temp }}/nfl-lab-readiness.json`, retained for 14 days. The older
detailed health upload additionally requires successful readiness.

This is source/publication policy enforcement in the existing scheduler.
The scheduler remains present and reports its blocked state; no recorder is
retired or replaced, and no new scheduler is created. The fixed block has no
activation flag. Merely adding a policy/manifest, changing repository
permissions, or creating a fabricated readiness file cannot unlock it. A
separate reviewed code change and verified handover must replace the block.

The newer branch already has source-policy routing and
`tools/persist_state.py:reviewed_publication`, which checks an accepted
`operational-publication-review-v2` manifest against exact state-relative
paths and byte hashes. Those mechanisms should be reused at handover. This
patch does not activate a partial copy of that larger system on old main.

## Concrete private durability decision

The missing owner-only decision is a genuinely private destination accessible
to the hosted lab with existing credentials and free allowance. Public-repo
Actions artifacts and a branch in a public repository must not be assumed
private. The current local workspace is not proof of cross-run hosted access.
No configured private route has been established.

One concrete option is owner approval to make **this lab repository private**,
then verify same-repository token/artifact access, quotas and bounded restore
before any detailed persistence. This needs no new key or paid service, but
visibility change has consequences for the owner's repository and has not
been performed or assumed authorized here. An existing genuinely private
destination is another option only if the owner identifies and approves it;
cross-repository token access is not assumed.

If the lab remains public, the safe reviewed alternative is to publish only
exact, separately accepted coarse aggregates/operational receipts. The newer
exact publication manifest must reject any absent, mismatched or unreviewed
path. Restricted source bodies, player rows, query rows, forecasts, outcomes
and model weights stay out of public artifacts and branches. This alternative
can report progress; it does **not** create private recoverability or make
pregame capture ready. Until private storage and hosted acceptance exist,
the explicit blocked receipt is the complete permitted hosted payload.

## Remaining acceptance work

The corrected branch has source/identity/runtime work to reuse. Its cold and
new-player prior/fallback coverage must remain explicit. It still cannot infer
true played-zero/DNP status from unknown participation, and exact website PPR
labels remain separately gated. Its seven-day reconstructed availability
assumption is preserved as historical evidence, not relabeled as an actual
source publication time.

Before a verified handover, freeze the exact permitted source/runtime,
forecast horizon and qualified-consumer contracts; establish the approved
private persistence/export/restore route; then run a finite hosted acceptance
packet covering on-time delivery, missed schedules, retries, idempotency,
resource bounds, retention and rollback. Existing saved hosted successes
predate the new branch and do not accept it. No hosted invocation is part of
this patch. Engineering readiness and scientific model qualification remain
separate; no candidate or website default is promoted.

## Focused software check

The registration is
`config/hosted-safety-handover-guard-v1.json`: one fictional invocation, at most
60 wall/CPU seconds, 256 MiB, two threads and no NFL values, fits, predictions,
acquisition or HTTP. It exercises only the new guard and workflow invariants;
it does not rerun unchanged source/model suites. The execution receipt and
exact commit are supplied to the integrator for independent review. A passing
software check is not an actual hosted run or new forecasting evidence.
