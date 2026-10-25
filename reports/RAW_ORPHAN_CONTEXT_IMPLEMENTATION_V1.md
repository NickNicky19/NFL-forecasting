# Raw-orphan context prerequisite v1

Status: **implemented for review; actual source execution not authorized or run**.
This is a separately versioned structural prerequisite to the earlier proposal.
It does not change the frozen zero-join helper or qualify any new outcome label.

## Contract

`nfl_lab/raw_orphan_context.py` retains the complete 67-record, eight-column
fixed-game context projection in private storage before partitioning identities.
Each record keeps its original fields and projection-local ordinal. A locator is
the immutable projection digest plus ordinal, never an inferred player identity
or a physical source-file offset.

Missing raw IDs remain unidentified. Duplicate canonical IDs remain ambiguous;
no representative is chosen. Missing position is an independent flag, including
when it overlaps a missing identity. No position or identity is copied from the
offered population. Malformed nonnull IDs and other invalid fixed-game context
still fail. Independently valid raw/offered team conflicts remain visible as
unresolved known-player coverage and cannot enter the identified context view.

The private outer union retains every canonical raw identity, all 31 original
offered identities and all 92 authenticated positive FTN witnesses, including
unmatched members. The conservative resource/coverage denominator is the unique
known-player union plus every unidentified raw record, capped at 200. An orphan
cannot fill any known player's missing raw match. Public outputs contain counts
and file identities only; private outputs retain the complete context inventory,
quarantine reasons and unresolved known-player coverage.

## Source and execution boundary

Configuration binds the same cached source, original screen-query/global freeze,
source policy and successful prior context diagnosis. Only the original raw
eight context columns, offered seven context columns and original appearance
projection may be decoded during a separately authorized run. No primitive
statistics, forecasts or model artifacts are decoded. The adapter does not join
or apply zero labels, establish DNP, impute a statistic, establish exact PPR or
assert historical pregame availability. No new acquisition or HTTP is included.

`tools/raw_orphan_context_execute_v1.py` adapts the reviewed sequential-v2
wrapper: a stdlib supervisor runs and reaps a storage-only bootstrap before the
source worker, then imports storage after both child phases have exited. The
original storage module and its unconditional pandas footer remain unchanged.
Existing source/ownership/CAS/quota checks remain in force. The old strict
helper and all failed attempts remain unchanged.

Bounds stay one invocation, 60 seconds wall and CPU, 256 MiB combined RSS with
the existing 240 MiB sampled safety threshold, one numerical thread, zero HTTP,
fits, inference, scores, label applications and automatic retries, and at most
1 MiB attempted new allocations inside the shared 512 MiB quota. PID/start-time
sampling fails closed; known individual child peaks are also checked. Sampling
is not a claim of a continuous kernel-enforced RSS maximum.

## Software checks and remaining decision

The 22 new contracts use explicitly fictional identifiers and context records.
The single bounded invocation passed all 22 checks: 0.279630144 seconds wall,
0.279560046 seconds CPU and 22,122,496 bytes known single-process peak RSS, with
one numerical thread. Audit guards denied source/model access, network and child
processes; no denied effect was attempted. No unchanged suite was rerun. The
[exact receipt](RAW_ORPHAN_CONTEXT_SOFTWARE_CHECKS_V1.json) and
[invocation/harness record](RAW_ORPHAN_CONTEXT_SOFTWARE_INVOCATION_V1.json)
preserve the tested bytes, resource scope and finite bounds. Software checks
establish these structural contracts, not forecast accuracy.

The concrete execution draft targets integration paths and fresh private
namespaces `raw-orphan-context-v1-20261023` and
`raw-orphan-context-v1-supervisor-20261023`. Binding a draft is not execution
authority: independent exact-byte review, root transfer verification, ledger
registration and root GO remain required before any actual context read.
Requested model settings are GPT-6.1 Sol Extra High; actual backend settings are
unattested. No production, scheduler, source-policy or forecasting change is
part of this prerequisite.
