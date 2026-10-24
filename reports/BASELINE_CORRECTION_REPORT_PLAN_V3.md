# Compact reporting completion v3 — no actual run

Preserve the original scientific run's CPU failure and V2 reporting's retention
failure. The metadata/log-only inventory found nine complete target report/
paired/subgroup triplets; only `rush_rec_yd` and `anytime_td` lack final artifacts.
No NFL Parquet or target-report values were decoded for this proposal.

## Inventory and finite byte allocation

[Exact names, hashes and sizes](BASELINE_CORRECTION_REPORT_V3_METADATA_INVENTORY.json)
bind all 27 completed files. They total 15,197,939 logical bytes already owned
by CAS, with zero new content bytes required for immutable aliases. All nine
reports, including all losing/mixed results, remain byte-exact. No completed
category is aggregated again.

Observed maximum paired/report/subgroup sizes are 2,910,764 / 170,824 / 61,170
bytes. A stress allocation allowing each of two new files to be twice its
respective observed maximum, plus 2 MiB for compact freeze/matrix/receipts and
1 MiB for logs/failure, totals 15,716,760 bytes against the unchanged 16,777,216
admission cap. This is a conservative allocation estimate, not a guarantee about
future compression or CPU. A cap violation remains terminal; no rows or checks
are dropped to fit.

The V2 sealed freeze is 5,764,340 bytes, SHA256
`da58d76b50747329e3eadd83ee8e506576d6607b4634fa3303e96750a16162fb`.
V3 uses a compact pointer instead of copying that full environment body. Its
28,378-byte unsealed draft has 40 exact delta bindings. At every verification,
load/authenticate the full sealed V2 document and call its **unchanged original
verifier**, including every original environment/code/source/input pin, before
checking the V3 deltas. A summary/hash alone never replaces those checks. No V2
file or global is modified, and both failed namespaces remain immutable.

## Only two unfinished categories

Reuse all nine complete triplets via the original owned CAS importer, without
private row decoding or regeneration. Authenticate all 66 scored candidate and
165 control references through the existing V2 metadata/ownership path. Permit
semantic reads only for 12 candidate and 30 control files for the remaining two
categories. Reuse the unchanged V2 aggregation helper, which calls the original
target report, product pairs, subgroup, later descriptive and nomination rules.
Both arms, all five controls, all three years and 500 fixed bootstrap replicates
stay unchanged. The unsaved V2 calculation of the next target is exposed work,
not a new confirmation sample; only its missing final artifacts are completed.

Retain both new paired and subgroup arrays in the existing consumer format.
The final twelve-target matrix binds all eleven full reports and copies their
pooled-primary cells/nominations; exact PPR stays blocked. No fit, forecast,
scoring/label join, source/model read, predictive law, HTTP or accepted-label
application is introduced. Original SITE/raw Sleeper unavailability remains.

## Execution and software proposal

One actual invocation is proposed: 300 wall/CPU seconds, 1 GiB combined RSS,
two numerical threads, 16 MiB new content under the shared 512 MiB quota and no
automatic retry. The new wrapper lowers the original time bounds, retaining
explicit PID/start-time accounting, parent-death protection, exact GNU timeout,
strict network/process guards, offline dependency import context, original
storage/CAS/admission and full owned-reference entry/exit checks. Source,
environment, evaluator and scientific gates are unchanged. Execution requires
independent exact PREEXEC, root seal, sole-writer coordination and root GO.

Four NEW fictional delta contracts are prepared: nine/two partition and alias
route; exact 12+30 decode paths; predecessor FAILED preservation; compact
pointer rejection/delegation to full original verification. Proposed software
scope is one 30 wall/CPU second, 512 MiB, one-thread invocation with zero NFL
semantic values, network, models, CAS or old-suite reruns. Exact code/tests and
harness freeze must receive root GO before invocation. The original ten-check
failure and separate two-check import proof remain unchanged.

New namespace: `baseline-correction-report-v3-20261023`. New failure/completion
and final report hashes remain available for the independent cached-row
verifier. This is exposed historical reporting, not new NFL evidence,
qualification or deployment. Requested GPT-6.1 Sol Extra High; actual settings
remain unattested.
