# 2024 appearance and explicit-zero qualification

## Actual result

The retained-source check restored **444 target-label incidences across 105 unique player-games**: 12 RB, 35 WR and 58 TE player-games. These are overlapping category labels, not 444 independent observations or 105 distinct players.

|Target|Previously unknown target incidences|New explicit zeros|Still unknown|
|---|---:|---:|---:|
|Passing yards|697|0|697|
|Passing TDs|697|0|697|
|Completions|697|0|697|
|Passing attempts|697|0|697|
|Interceptions|697|0|697|
|Rushing yards|511|12|499|
|Rushing attempts|511|12|499|
|Receptions|2,029|105|1,924|
|Receiving yards|2,029|105|1,924|
|Rushing + receiving yards|2,029|105|1,924|
|Anytime rushing/receiving TD|2,029|105|1,924|
|Exact website PPR|Unsupported exact labels|0|Blocked|

Overall, **12,623 unknown target incidences become 12,179**. The five passing categories gain no labels: every previously unknown QB opportunity lacks the required original statistics row. One receiving-population context mismatch remains quarantined for each of four targets. No absent statistic row or null field became zero.

## What qualified a zero

Each added bit required all of:

1. The exact existing frozen 2024 player-game offer was previously unknown.
2. A valid FTN play contained the exact GSIS player and game, with internally consistent player lists/counts.
3. A unique original NFLverse statistics row matched season, REG week, team, opponent and position. Duplicate raw keys were audited across all 18,983 rows before period selection; all members of ambiguous keys would be quarantined.
4. The target's required primitive fields were present, integer typed and explicitly zero. Combined yards require both yardage components zero; anytime TD requires both rushing and receiving TD fields zero.

Appearance alone never supplied a statistic. Missing list membership never supplied DNP. Supported old labels, features and forecasts were not overwritten; the new version saves an added-zero mask referencing the original query order.

FTN's retained file has 45,919 rows; 43,866 rows match the fixed REG query games. There are 25,400 positive appearance-witness player-games across the source, not that many forecast observations. Four duplicate-membership detections arose in two FTN rows; both rows were excluded. Original statistics contain 18,983 rows, including 18,130 REG/query rows. All query games have FTN coverage, without implying that every missing player participated.

## Timing, rights and remaining limits

This is **final historical label qualification**, not archived pregame feature evidence. FTN participation's postseason delivery cannot supply 2024 in-season route or role features. Original publication remains unverified. FTN Data is accessed through nflverse; its retained asset declares **CC-BY-SA-4.0**. Statistics retain their separate original source manifest and receipt. Shared nflverse distribution does not establish independent outcome truth.

The failed V2 qualifier rejected cutoff equality even though the frozen historical feature contract defaults cutoff to kickoff. Separately named V3 accepts equality as historical reconstruction and rejects later or missing cutoffs. Its four finite team aliases match the original source contract; original game and GSIS keys remain unchanged. Neither repair creates actual pregame issuance or new source-publication evidence.

The mask is private. [Safe aggregate proof](FTN_2024_ZERO_AGGREGATES.json) contains counts and hashes only. No source policy, production data route or scoring contract was activated. Exact PPR remains blocked. **No model fitting, inference or accuracy scoring occurred in this qualification.** The separately registered [cached-rescore continuation](RESTORED_2024.md) subsequently completed 85 comparisons on the restored common population; those results are a distinct evaluator run.

## Execution and independent verification

Sealed V3 plan: `f37d45b5f3ed985126abdf2a3a55a329d6d1da0a38723747a356b5c5e50ceae0`; worker: `a64460e38bd0951fe8e8fe63a8cda210117bd7ab9a0f730a98523df1221c5f8c`.

Mask: 4,943 bytes, SHA-256 `8b65efcc4bc480485d80e655d0b8436621e57dc38df0db5a84b779543df4cdb8`; layout covers 39,491 target-row incidence slots. Aggregate proof: 1,087 bytes, `a976af2a7003a57448f63cdeac4ac5df53a168d0857de153e754543951d3d256`.

V3 used **23.970 CPU / 23.897 wall seconds**, RSS 234,569,728 bytes. Including the retained V2 failure: **38.108 CPU / 37.955 wall**, within original 60/180. All attempts retain **6,353 bytes within 8 KiB**; no evidence was removed or quota increased. No HTTP, fits, inference or scoring occurred.

The separate read-only reviewer reproduced every mask byte, source/context/duplicate rule, count and distinct-player-game total, then rehashed the accepted runtime and source bindings. Actual final POSTEXEC and aggregate privacy checks passed. This verifies the new labels under the stated source contract; it is not proof of a forecasting gain.
