# Owned-child termination accounting — new guard-only packet

This is a separately versioned software repair, not a reinterpretation of the
original dynamic-history run. Original V1 remains **FAILED**, while its worker
receipt independently verifies eighteen fictional methods passed. The original
missing-counter observation does not prove an underlying cause. Adapter, math
core, eighteen test definitions, original harness and receipts stay byte-frozen.

## Strict transition

`sample()` and its PID/startticks/live-RSS rules remain unchanged. Timeout and
supervisor samples remain outside the new worker-only exception handler.
Missing/zero live RSS, identity conflicts, malformed/negative counters and
other guard failures remain failures.

Only the exact known worker's missing/zero-RSS or vanished-process observation
can enter the new transition after the positive-RSS ready/GO barrier. The
supervisor passes the existing owned `subprocess.Popen` object, original
PID/startticks binding and exact failure snapshot to
`termination_accounting.confirm_owned_child_exit`. It makes **one nonblocking
`child.poll()`** for that transition. `poll()` returning `None` is still live
and fails. No arbitrary PID lookup, process discovery, wait-all, repeated probe
or sleep/retry supplies an exit assertion.

A real integer return code from that exact object confirms waitpid termination.
All observed identity fields must still match; negative/malformed counters and
unrelated errors are not reconciled. The original R/S/Z observation is retained
without relabeling it or asserting why a counter disappeared. Acceptance says
`OWNED_CHILD_EXIT_CONFIRMED_REAP_CHARGE_REQUIRED`; current live RSS is `None`,
never a fabricated live zero or a measured memory peak.

After the original child is reaped, actual full child CPU and positive
`ru_maxrss` are mandatory. CPU cannot be below the retained observed counter.
The existing final guard charges that CPU, the child's highwater, supervisor
CPU/highwater and exact timeout observations under the full resource caps.
Observed sampled peaks and individual highwater sums remain separate; this is
not continuous kernel memory enforcement. A missing/invalid reap charge makes
the new packet fail. Nonzero worker exit and failed test receipts still fail.

## Scope of the proposed software invocation

New pure helper: `nfl_lab/termination_accounting.py`. New guarded runner:
`tools/dynamic_history_guard_software_v2.py`. Exactly six new fictional methods:

1. A live/unconfirmed child with missing/zero counters fails.
2. An exact confirmed exit retains the failure snapshot and requires reap charge.
3. PID/startticks/status-identity conflicts fail even after exit.
4. Unrelated failures, malformed/negative counters, nonowned objects and
   noninteger/unconfirmed return codes fail.
5. Actual full reaped CPU/highwater are charged unchanged.
6. Missing, nonfinite, insufficient CPU or missing/zero highwater fails.

These tests use fictional metadata and do not create processes. The guarded
runner itself has the one supervised software worker, with zero worker children.
Budget proposal: one invocation, six methods, 30 wall/CPU seconds, 512 MiB, one
thread, two-second startup within the total, zero NFL/source/model/network/CAS,
fits, filters, forecasts, scoring or old-suite reruns. Old frozen files are only
hash-authenticated; their code/tests are never imported or executed here.
Exact code/config/environment/inventory, independent PREEXEC and root ledger
GO are required before any invocation. No invocation has occurred yet.

Even a guard-only PASS would not authorize an eighteen-method end-to-end rerun,
alter a cutoff gate, or start the separately unregistered 54-package NFL study.
The historical replay cutoff/readiness issue is a separate new source contract,
and prospective issuance remains strictly before kickoff. No source/model/
workflow/rec-half registration changes belong to this repair.
