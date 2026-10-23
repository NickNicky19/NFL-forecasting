# FTN context diagnosis: executed result

## Finding

The separately authorized sequential v2 diagnosis completed successfully under
root GO commit `76010fc`. This was one cached-source metadata query, not a
forecast experiment. It read exactly eight context columns for the fixed game
`2024_01_BAL_KC`, retained all 67 projected rows in aggregate counts, and read
zero primitive-statistics columns. It performed no identity repair, numerical
join, fitted model, forecast scoring, zero application or source-policy change.

| Context field | Null rows | Nonnull mismatches |
| --- | ---: | ---: |
| game_id | 0 | 0 |
| season | 0 | 0 |
| week | 0 | 0 |
| season_type | 0 | 0 |
| player_id | 1 | 0 noncanonical nonnull IDs |
| team | 0 | 0 outside fixed-game teams |
| opponent_team | 0 | 0 reciprocal-mapping mismatches |
| position | 1 | Not an original first-gate requirement |

The missing `player_id` is sufficient to explain the original join failure:
the unchanged `_context(..., raw=True)` first gate explicitly rejects any null
in its required fields, including `player_id`. All observed nonnull fixed-game,
season/week/type, team/opponent and canonical-ID mismatch counts were zero.
The diagnosis reports one failing first-gate row and one failing identity-gate
row. It does not show a malformed nonnull identifier.

The aggregate does **not** establish whether the null player ID and null position
occur on the same row. It also does not establish the number of distinct raw
players: 66 nonnull-ID records need not represent 66 unique players. No NFL player
ID, raw row or arbitrary source value is published here. No context rows were
persisted by the diagnosis. Missing identity remains unidentified.

## Preserved execution history

| Attempt | Actual result | Interpretation |
| --- | --- | --- |
| Original explicit-zero join v1 | `NOT_READY`, `fixed-game context mismatch` | All 67 planned raw rows remained in failure coverage; zero applied labels and no accuracy scores. This attempt stays failed and consumed. |
| Context metadata diagnosis v1 | `FAILED`, `COMBINED_RSS_SAFETY_MARGIN`; worker killed | Corrected explicit-PID sampling observed 253,743,104 bytes against the 251,658,240-byte safety threshold. No diagnosis result was retained; context decoding was not established. This attempt stays failed and consumed. |
| Sequential context metadata diagnosis v2 | `CONTEXT_METADATA_DIAGNOSIS_ONLY`; bootstrap/source return codes both zero | Produced the counts above. This is a separately registered execution version, not a rerun relabeled as the original attempt. |

The original zero-join supervisor's 897,024-byte sampled combined RSS failed to
establish visibility of its known worker, whose individual highwater was
161,746,944 bytes. That old sampler cannot certify a whole-job RSS limit. The
later explicit-PID sampler fixed that visibility defect and exposed a second
issue: `operational_storage.py` has an unconditional pandas import at lines
720–722. Earlier descriptions calling the storage module stdlib-only were wrong.
V1 imported it in both supervisor and worker at the same time; its supervisor
highwater was 114,098,176 bytes and its child highwater was 138,448,896 bytes.

V2 preserved the original storage source and dataframe hooks. It instead ran a
storage bootstrap child, then the source child, then final supervisor storage
writes sequentially. The supervisor remained stdlib-only while either child
ran. Memory limits and safety thresholds were not raised.

## Exact v2 resource observations

| Observation scope | Wall seconds | CPU seconds |
| --- | ---: | ---: |
| Persisted supervisor receipt, before its own write | 20.221535807999317 | 20.736275 |
| Integrator's tool observation, after receipt write | 24.171549898001103 | 24.686275 |

The second row is the exact after-write tool observation supplied by the
integrator. It is not an invented process-exit measurement. The persisted receipt
and after-write observation have different scopes and are both retained.

| Memory/resource item | Observed value |
| --- | ---: |
| Combined RSS peak sampled over the explicit processes | 163,221,504 bytes |
| Maximum individual child `ru_maxrss` over the sequential children | 143,597,568 bytes |
| Supervisor individual `ru_maxrss` | 113,696,768 bytes |
| RSS sampling interval | 0.01 seconds |
| Safety-stop threshold / registered combined RSS limit | 251,658,240 / 268,435,456 bytes |
| External timeout / CPU budget | 60 / 60 seconds |
| Numerical threads / HTTP / automatic retries | 1 / 0 / 0 |
| New retained-output allowance | 1,048,576 bytes |

Sampled RSS can miss transient peaks. Individual highwaters occurred in different
processes/phases and must not be added as though simultaneous. Both phase stop
reasons, the final stop reason and supervisor error were null. Source/accepted
data, policy, forecast outputs and model decisions were unchanged.

## Authenticated identities

| Artifact | SHA256 |
| --- | --- |
| Executed aggregate, 1,759 bytes | `94833d4da0ae532b608de02c64b7509dae6c8de1193b09896adb791bf41793b0` |
| Persisted supervisor receipt, 1,674 bytes | `e7e778fec941625ab835dd5513588615deca7f01cd316a2ee02eb6da73820c4a` |
| Executed registration | `ffdc1d8a41e1f2c02dc9cfd6eaacb0c09c56ad6bd372496d65a7c4bc88dc3b75` |
| Executed freeze | `729ac5375a0b3d5bba134eb3b8ef777820aad31a41aa67056e35be3bd8ab7532` |
| Sequential wrapper | `bbe4efb9da9de716845603d68ed94e1c8f510c4ac52eaaa6a4d0c9ad9e98a6d5` |
| V2 diagnosis module | `41b577b2fa0e09efe300e093ebba7253b775cfd7a3579bc9ddc5be08b03a6f22` |
| Original raw source | `847569d194ca3d96b5efcf91e6eac5e18780fc47568a713fd545a82d29d155c1` |
| Original zero-join failure | `2b1022be9e9804895fce4e9edf419e36473150462b7e6fd1776edad015456a17` |
| Original zero-join supervisor receipt | `daf83611d6f1e0521301f1fac9ec819d25a6bacd73790e057d29571bdb070f2f` |
| Failed context v1 supervisor receipt | `665990cc12f89838cdc0062c700076b39ab5238f0472f5bd35b74742862e2d74` |

The aggregate and persisted supervisor receipt were reauthenticated from existing
saved metadata for this summary. No additional source query, diagnosis or join
was performed while writing it. Hashes authenticate file identity, not player
participation, historical publication time or predictive quality.

## Supported decision

Keep the original strict join helper and failed artifacts unchanged. The smallest
next proposed prerequisite is a separately versioned raw-orphan quarantine
adapter that retains all 67 planned records and all offered/witness coverage,
without fabricating an identity for the unidentified raw row. See
[the proposal](FTN_RAW_ORPHAN_QUARANTINE_PROPOSAL_V1.md).

This result qualifies a narrow source-context diagnosis. It neither restores a
played-zero label nor establishes a forecasting improvement for any category.
