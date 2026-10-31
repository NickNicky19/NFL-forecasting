# Fourth managed peer: source preparation

State: `SOURCE_SEAL_ONLY_NO_STORE_OPENED`. This prepares storage, not an NFL
fit, captured forecast, scored comparison or production release. The current
source seal is [POLICY_DESCRIPTOR_V1_1.json](POLICY_DESCRIPTOR_V1_1.json).
The original unexecuted source seal remains preserved as V1.

The new `matched-all12-forward-v1-20261030` namespace is a sibling beneath the
already approved private workspace. Its private path is derived from the
existing policy and is intentionally absent from this public receipt.

| Account | Bytes |
| --- | ---: |
| Complete old allocation, unchanged | 1,367,343,104 |
| Separate new peer peak | 134,217,728 |
| New complete peak | 1,501,560,832 |
| Finite wave retained envelope | 100,663,296 |
| Old upcoming-capture peak reservation, preserved | 83,886,080 |

Complete usage is **old complete accounted bytes + new peer physical bytes**.
The old complete stack already includes legacy, prior, market, uploaded
originals and the 4/16/8 MiB metadata reserves. Legacy is not added again.
The old stack is attached with `__new__` and readonly control validation;
its constructors and write methods are not called. Every new write checks
that the old allocation can still accommodate its 80 MiB reservation.

The new class inherits the original CAS, atomic, stream, alias, restoration
and permanent shared-flock primitives. It adds policy binding, accounting and
root disjointness only. The 96 MiB retained limit is enforced by
`verify_retained_checkpoint()`; every worker must call it before reporting
a completed checkpoint. It counts all new controls, partials, failures and
unique CAS blobs. The physical 128 MiB prewrite limit permits temporary
write peaks. Exceeding the retained limit leaves the checkpoint incomplete.
No unique evidence may be deleted to recover a failed allocation.

## Before any initialization

The root integrator must independently review the exact sealed source and
verify fictional initialization/readonly-reattachment behavior. Required
checks are descriptor rejection before existing peer attachment, identical
permanent flock/thread context, disjoint roots, old limits and reserve,
nonduplicated accounting, quota rejection and inherited writer identities.
AST parsing and the metadata-only `describe` execution are not software-test
passes or completed capacity inventory. No private initialization has run.

After that review, the root can use the existing finite accounting allocation:

```sh
PYTHONDONTWRITEBYTECODE=1 python -B tools/category_topfive_matched12_storage_v1.py --mode describe
```

For `initialize`, pass `--allocation-sha256` from the exact reviewed seal and
`--root-go ROOT_REVIEWED_MATCHED12_STORAGE_V1`. The helper rejects drift.
Its `inventory` mode uses an existing fourth-peer readonly attachment and
fresh inherited reference validation; it requires the same digest and GO.
Private store opening/initialization remains unexecuted until root review.
No network, model loads, forecasts, NFL decoding or scoring are involved.

The immutable private outer descriptor binds full policies and source hashes.
The public seal includes only safe byte counts and hashes. Local persistence,
fresh-process readback and off-host restoration must be reported separately;
this source preparation proves none of those operating stages.

## Fictional checks completed

[Fictional V1.1 result](FICTIONAL_RESULT_V1_1.json): 24 checks passed using
the actual inherited CAS implementation in temporary fictional stores and a
simulated complete prior peer. CPU 0.760s, wall 0.419s, peak RSS 57,552,896
bytes. These verify shared locks, inherited writers, immutable old controls,
read-only restoration, exact nonduplicated accounting, descriptor rejection
before peer attachment, peak-quota rejection, preserved upcoming reservation
and the retained-checkpoint limit. No real managed store was opened.

The first fixture failed because its private quota call omitted the required
transaction; [failure](FICTIONAL_FAILED_V1.json), original fixture and separately
registered corrected fixture remain preserved. Actual production capacity,
local fresh-process readback and off-host restoration remain unverified here.
