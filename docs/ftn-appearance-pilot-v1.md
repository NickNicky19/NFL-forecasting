# FTN participation appearance pilot

Completed one bounded retrospective schema/appearance audit for the preregistered
game `2024_01_BAL_KC`. This adds positive on-field witnesses, without changing an
accepted source policy, model population or label. No statistic, name, outcome,
roster, model or prediction-score values were semantically decoded or joined.

## Source and projection

Source: **FTN Data via nflverse**, with the source-specific loader's
[CC BY-SA 4.0 declaration](https://creativecommons.org/licenses/by-sa/4.0/).
The hosting license is not substituted for that declaration. The earlier
[documentation assessment](participation-substitutes-v1.md) retains the unresolved
document commit/root-tree association and source-coverage limits.

The [2024 participation asset](https://github.com/nflverse/nflverse-data/releases/download/pbp_participation/pbp_participation_2024.parquet)
has release ID `71636554`, asset ID `289570938`, and size **4,644,767 bytes**.
Its SHA256 was independently verified against the catalog declaration **before
Parquet decoding**:
`5e8cf1f6a11bb2be573c3db1533c28a5658907302d1ad45ca769a4ca35890d7c`.
The file and projected rows remain private. Original upstream publication and
historical pregame availability are not authenticated.

Only the seven registered game/play, GSIS-list and list-count columns were
projected. The exact game predicate was counted before player-list output
materialization, then scanned with one thread and batches of at most 512 rows.
The file footer reported 45,919 rows in one row group; this is metadata, not a
claim that other games' rows were audited.

| Audit | Result |
| --- | ---: |
| Fixed-game projected rows / unique game-play keys | 163 / 163 |
| Invalid, duplicate or wrong-game keys | 0 |
| Distinct positive on-field witnesses across supported lists | 92 |
| Distinct offense-list / defense-list witnesses | 66 / 54 |
| Rows with supported canonical semicolon lists, each of three fields | 163 |
| Missing/unresolved lists or duplicate memberships | 0 |
| On-field list equal to offense/defense union | 163 / 163 |
| Offense / defense count consistency | 163 / 163 each |

The offense and defense populations overlap. Their counts must not be added to
obtain the total. The private approved projection is 9,381 bytes, SHA256
`4b5946f063050df232973b387c6ef0e61c536a32bc03a35c016a8a3f8de492c0`.
No player identifier values, lists or individual play rows are exported.

## Execution and review

Two application HTTP transactions completed: a zero-body redirect followed by the
authenticated asset response, with zero retries and 4,644,767 total incoming body
bytes. The frozen ceilings were three transactions, 32 MiB, 60 wall/60 CPU seconds,
256 MiB combined RSS, one numerical thread and the unchanged shared private quota.

The saved outer receipt records **14.622826 wall / 14.230444 combined CPU seconds**
before its final write. Owner tool observations after that write were
**15.297788 / 14.903785 seconds**. Combined RSS samples at 10 ms intervals reached
108,400,640 bytes; the child's separate RSS high-water mark was 182,460,416 bytes.
Samples may miss transient peaks and are not an absolute combined-peak guarantee.
Three earlier code-preparation jobs used 13.883776 wall / 11.440395 CPU seconds;
these are separate measurements, not part of the saved actual-run receipt.

Independent pre-execution static review and postrun metadata-transfer review
passed. The reviewer checked bindings, receipts and aggregate transfer and did not
open the source, projection or player rows. The [aggregate](../reports/ftn-appearance-pilot-v1/aggregate.json),
[exact executed runner](../reports/ftn-appearance-pilot-v1/run.py),
[method manifest](../reports/ftn-appearance-pilot-v1/method-manifest.json) and
[review receipt](../reports/ftn-appearance-pilot-v1/review.json) preserve their
scope. The exact private execution freeze is pinned by hash, not copied with its
private absolute input/output bindings. Publication remains an integrator step.

## Remaining gate

This single-game audit does not establish a complete appearance/DNP denominator,
special-teams coverage, statistical zeros, exact PPR or historically available
pregame features. **No zeros were restored.** Positive appearance never fills a
missing statistic.

Any later comparison against already explicit cached zeros requires a separately
registered join contract and exact input hashes, after the new method screen's
`GLOBAL_FORECASTS_FROZEN` gate. That comparison is queued; no cached statistics or
evaluation labels were opened for this pilot. The official NFL gamebook route
remains not cleared, and no other-source exhaustion claim follows.
