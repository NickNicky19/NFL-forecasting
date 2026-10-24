# Operational storage v2 checkpoint

This is software and reused-cache acceptance, not new predictive validation.
The [owner-supplied audit intake](INDEPENDENT_AUDIT_INTAKE_20261023.md) also
records the independently confirmed and repaired optional joint sampler.

## Executed

- **759 software checks passed**, one unchanged real-cache PPR audit deselected
  because it reads 2026 Week 6 beyond this packet's Week 5 bound. Its previous
  accepted result remains preserved. Two fictional concurrency-test Python
  deprecation warnings are retained. Root run: 54.194 wall / 66.193 CPU seconds,
  591,138,816 bytes peak combined RSS, two threads.
- One frozen cache-only invocation: **66.620 wall / 76.130 CPU seconds**,
  930,488,320 bytes peak combined RSS, two threads. No HTTP, fits, model
  predictions, accuracy scores or new confirmation observations.
- Exact value/dtype/order parity with v1 for **62,388 historical feature rows**
  over 1,950 historical games and **681 metadata-only query rows / 13 games**.
  Each view has 97 feature columns; 120 floating columns were compared by bytes,
  preserving nulls and signed zero. Query outcomes remain null.
- Same-asof retry changes no stored data. The nearby earlier-asof capture reuses
  **56 identical original/subset files, totaling 22,421,598 bytes**, as verified
  owned inodes. External legacy originals are copied and never hardlinked.
- Snapshot-stage unique file bytes: **30,696,603** versus 84,198,589 logical
  referenced bytes. Supervisor measured 30,756,451 retained unique file bytes
  before its final completion receipt. Both are below the unchanged 536,870,912
  byte ceiling; incoming writes are checked before publication, including
  instrumentation markers and bounded log chunks. File sizes are not filesystem
  allocation blocks. Different stages have different metadata totals.
- All **126 frozen bindings** and **40 legacy inode/mode/size identities** remain
  unchanged. Historical source predicates remain REG only, 2019–2025 and 2026
  Weeks 1–5. No future confirmation outcomes were read.

Before the single invocation, reviewer feedback tightened acceptance
instrumentation and pinned the actual dependency venv. Earlier freeze files
remain preserved, with zero invocations consumed before the final freeze.
The first routing-owner fixture attempted a forbidden in-place alias mutation;
its failure is retained, and the fixture was corrected to simulate corruption
by atomic replacement. Checks were not weakened. Owner runs overlap root tests
and are not additional NFL observations.

## All twelve categories

All numerical decisions remain in the
[latest category matrix](role-count-boosting-v1/category-status.json). This
packet trains or scores none of them. The reused source panel contains 42,286
positive-action supported played rows and 20,102 unknown rows, with no certified
DNP rows. It is not a complete participant denominator. Eleven targets have
supported labels; **exact website PPR has zero qualified labels**. No missing
values or unknown appearances became zero, and no participation probability
was inferred from this selected panel.

## What changed

The [v2 policy](../config/operational-source-policy-v2.json),
[storage contract](../docs/operational-storage-v2.md) and
[routing contract](../docs/operational-source-v2.md) enforce one globally locked
prewrite quota across original sources, subsets, features, private model
staging, live provider caches, state records, run receipts and Git state
restoration. Owned immutable content reuse avoids repeated body copies.
Both the global 512 MiB and existing 200 MiB state ceilings apply.

One existing scheduler is retained. Its schedule, fixed reference algorithms,
source qualification, original registrations and frozen evidence are preserved.
No deletion or expiry was introduced. A full store abstains; unlimited distinct
vintages cannot fit finite storage. Longer-term lifecycle policies require
versioned acceptance before use.

Git state restoration preflights incoming payloads. New publication requires an
exact reviewed subset manifest, preserves old remote entries and rejects
changed existing records. This packet exports code, configuration and aggregate
receipts only. No private source/player rows, query rows or weights are included.

## Remaining work

This version is **not OPERATIONAL_READY or RELEASE_READY**. The separately
frozen 22-package recent/pooled runtime, reference artifact content review and
actual hosted/handover/retry/rollover/rollback checks remain pending authorized
work. No new dispatch, lab merge, website change or production activation is
claimed. The website owner controls integration.

The next numerical priority from the audit is a separately registered
source-matched CDF / fixed boosting / simple-control comparison across all twelve
targets, retaining the PPR block. Previously exposed years stay development.
The older Week 6 cutoff predates these source receipts, so it cannot inherit
operational as-of verification. Role/participation and narrowly qualified
turnover-risk/catch-quality additions follow their own finite ablations.

[Aggregate receipt](operational-storage-v2/aggregate-cache-acceptance.json) ·
[Hash manifest](operational-storage-v2/hash-manifest.json) ·
[Independent review](operational-storage-v2/review-receipt.json)
