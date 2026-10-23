# Owned reference batch validation v1

Conditional recovery registration SHA256:
`d5e040355be0dd07ea0af0c4182e4f7c1fcd386fd8277b52d6a3217dfc196e35`.
Implementation and fictional fixtures do not authorize a real validation or
recovery execution. No original storage, learner or evaluator is changed.

## API and equivalence

`validate_owned_references(storage, bindings) -> (references, receipt)` takes an
existing `OperationalStorage` instance and a nonempty mapping of absolute
Path/string names to mandatory exact lowercase SHA256 strings. The caller joins
frozen relative manifest paths to its authenticated original output directory.
The helper rejects relative/traversal/control/foreign/symlink paths, malformed
hashes and duplicate canonical paths. Distinct legitimate owned aliases of the
same CAS blob remain valid; their quota uses unchanged unique-inode accounting.

The existing exclusive global quota flock is held continuously across:

1. Existing `_refresh()` and unchanged full `_scan()` at entry.
2. Each original `validate_reference` per-reference check: `_check`, `lstat`,
   readonly regular-file mode, content SHA, exact expected SHA, existing CAS
   `_verify_blob` (including its unchanged fingerprint cache), and same-inode
   ownership comparison. Reference result dictionaries match the old API.
3. Existing `_refresh()` and unchanged full `_scan()` in `finally` at exit.

No per-reference full scan occurs. Both full scans retain every registry/root
ownership, symlink, nonregular file, CAS hash, lock identity, external hardlink
and unique-inode quota guard. Registered writers using the same lock cannot run
between references. Uncooperative external filesystem mutation remains subject
to the same underlying storage checks; the helper adds no authority to mutate
retained bytes. A failed entry, reference, refresh or exit scan returns no success;
the lock is released. Exit verification also runs on a failed reference. An exit
failure propagates and retains any earlier exception as Python exception context.

The first result is keyed by canonical absolute reference path. The private
receipt contains version/registration, count, two full-scan calls on success,
lock-scope statement and unchanged entry/exit scan dictionaries. These include
private absolute roots and must not be published. The helper writes no receipt,
row, source or artifact and performs no fit, inference, scoring or network call.
The existing lock API may create its empty lock file when absent, then rejects
an unauthenticated lock identity through the registry, exactly as before.

## Caller eligibility and resource boundaries

Only a separately frozen technical recovery may call this on real inputs. It
must require the original failed completion, immutable forecast freeze, all 198
frozen/18 exact-PPR-blocked slots, and absence of `SCORE_CONSUMED` and scored files.
If scoring started this recovery is ineligible. Preserve every original byte,
resource failure and exposure status; no model/reference fit repeats or cap
increase occurs. The root owns eligibility, exact frozen input/code/dependency
bindings, cumulative law-row accounting, shared quota, clocks and output IO.
This helper does not perform those independent execution-policy checks.

Fictional tests are bounded to 90 wall/120 CPU seconds, one configured numerical
thread. They use temporary fictional bytes only and cover old-API equivalence,
exactly two batch scans, process flock exclusion, a waiting concurrent storage
writer, malformed/unsafe/foreign aliases, read-only/CAS/hardlink/quota/scan-error
guards, and failed-reference/exit-scan cleanup. Real-store validation, NFL/model/
forecast reads, additional scoring, retries or publication are not fixture work.
