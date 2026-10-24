# Calendar and roster lookup cache proposal V1

**Proposal only. The patch is unapplied. No test, profile, NFL row, model, prior,
score, acquisition, CAS operation or study retry was executed for this packet.**

Base: `569c0dce2636fe442c27356e1903672d37d35d56`. The exact proposed source diff
is [the patch](../proposals/dynamic-source-calendar-cache-v1.patch). Root's live
files and current interval-experiment bindings remain unchanged.

## Observed fictional bottleneck

The retained `fictional-profile-v1/PROFILE.json` reports one fictional
common-cutoff batch with60 offers,576 calendar sides,1020 roster/history rows
and10880 raw rows. Its profiled historical_requests cumulative time was
1.345269s; `_calendar` ran64 times with0.692233s cumulative time. The membership
function's0.679745s overlaps that calendar time and must not be added to it.
These measurements establish a fictional repeated-work opportunity, not an NFL
speed gain, forecast improvement or refund of any failed execution's budget.

## Small proposed change

Within each historical_requests call, take a private deep copy of the calendar
and run the **unchanged full calendar validator once** for the source producer.
Its period/game indexes are passed only to private credit, participation-history
and membership helpers. Public standalone helper entries still run the full
validator on every call. The two frozen downstream proxy/window adapters remain
byte-unchanged and each independently validates the same snapshot. Expected
calendar validation count for the original60-offer batch is therefore **3,
rather than64**. This deliberately keeps the two frozen downstream checks.

Build one per-player roster lookup over the already declared complete batch
roster list. Keep original order, duplicate rows, null IDs, every team and every
status. Do not index by player+team, which could hide a conflicting team spell.
The original per-offer season/player, source-availability, Week1-anchor,
conflicting-team and membership-slot checks still run on every offer. An
unindexable source identifier falls back to the original full roster scan;
it is never dropped or repaired. No membership eligibility result is memoized.

The cache expires on return. There is no global cache, cross-cutoff reuse,
modified source query, altered row pointer, skipped missing appearance, changed
seven-day/equality gate, fabricated participation, zero filling or inferred
transaction. Every original opportunity, fallback, unknown and supported zero
must remain. The existing proxy sums remain all-position recorded-credit
proxies, not complete NFL totals.

The semantic producer version staysV2 because the scientific/source contract
does not change. A distinct `runtime_optimization_version` identifies this
implementation as `dynamic-source-calendar-cache-v1-20261024`. Its executable
hash and this version must be bound by any future registration; it cannot inherit
the failed runtime's identity or claim those attempts completed.

## Finite proposed acceptance packet — not authorized/executed here

One separately frozen invocation, <=6 NEW fictional methods,120wall/CPU seconds,
512MiB, two numerical threads, zero NFL semantics/priors/models/scores/network/
CAS writes or old test-suite bodies. Use the existing single-process software
guard pattern. Before execution, bind the unchanged original V2 source oracle
by its exact hash, the candidate patch/result, all dependency bytes, the new
fictional fixtures, harness and interpreter. No runtime source rewriting or
monkeypatch of a frozen validator is part of the proposed production adapter.

1. Compare original and candidate complete results on both task fields and
   a common-cutoff batch containing sparse/new roles, duplicates and fallbacks.
   Remove **only** the declared new top-level runtime_optimization_version from
   the candidate before byte-canonical comparison. Do not normalize, ignore or
   replace any source/manifest hash, selected slot, count, reason or fallback.
2. Exercise missing/duplicate/nonreciprocal calendar sides and altered seven-day
   availability. They must still fail through the original full validator.
3. Retain duplicate Week1 entries, all statuses and conflicting other-team rows;
   compare spell, membership audits and original row order with the oracle.
4. Preserve unknown participation/missing normalized fields/explicit played zero,
   available<cutoff strictness, all elapsed slots and no primitive access before
   availability. Include unindexable-ID fallback to the original scan.
5. Call the producer twice with distinct cutoffs/calendars. A changed calendar
   must be revalidated; no earlier index/membership result may cross the call
   boundary. Public helper calls must still validate calendars independently.
6. Count calendar invocations on the original fictional60-offer fixture and
   verify the expected3 calls (one producer, two unchanged downstream checks),
   plus exact original offer/member/credit/history/proxy coverage.

After those checks, the same finite invocation may time the exact original
fictional profile fixture **once with the old source and once with the cache**,
in that fixed order. No repetition until a favorable timing, parameter search,
NFL data or invented speed claim. Publish both wall/CPU/highwater measurements,
equivalence, spent budget and any failure. Correctness is mandatory; report the
timing difference descriptively even if it is slower or inconclusive.

## Actual study remains separate

Existing scientific source executions remain FAILED with their original consumed
resources and zero forecasts. This packet authorizes no numerical retry, prior
formation, new data lane, changed100s source-phase limit, extra search slots or
refunded budget. A later actual attempt needs its own immutable runtime/source
manifest, source-phase allocation, retained failures, independent review and
root ledger GO. The root integrator remains the sole ledger writer.
