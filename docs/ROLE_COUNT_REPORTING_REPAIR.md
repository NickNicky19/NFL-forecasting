# Role/count study: retained reporting failure and recovery

The original `all12-role-count-boosting-v1-20261023` run consumed all 136
estimator attempts. It froze 88 supported forecast packages; eight exact
offensive PPR packages remained blocked by the outcome-source contract.

Its first reporting attempt failed on strict identity-frame equality: the
same season/week values used `int32` in candidate rows and `int64` in controls.
No cell report completed. The original consumed score marker, partial derived
files, completion receipt, forecasts and model artifacts remain immutable.

`role-count-reporting-repair-v1-20261023` is a separately sealed, evaluation-only
repair. It has zero fits, zero inference calls and one additional reporting
attempt. Cumulative reporting attempts are therefore **two**, including the
failed original. A successful repair does not relabel the original run as
successful or create another football sample.

Only fresh derived identity-key dtypes may be normalized. Ordered canonical
identities, row counts, uniqueness and all non-key values must remain exact;
floating-point bit patterns are checked. Existing source, outcome, cutoff,
cohort, scoring and uncertainty checks remain in force. No sorting or selective
row removal may make an identity mismatch pass.

The repair binds every original run file by SHA-256, rechecks the original
sealed registry and all frozen prediction bindings, and verifies the full
original inventory after reporting. New outputs use a separate create-only
directory. A new consumed receipt is persisted before evaluation outcome reads.

The finite recovery limits are 600 wall seconds, 900 CPU seconds, two threads,
1.5 GiB combined resident memory and 800 MiB combined private output storage.
The old search budget stays spent. No retry, refit, new feature, model choice,
confirmation-period read, activation or website change is part of this repair.

The unchanged public exporter cannot represent this recovery honestly because
it requires successful original completion and one scoring pass. A separately
versioned exporter must validate and disclose the original failed run and the
successful repair independently, while retaining the existing aggregate-only
publication boundary.
