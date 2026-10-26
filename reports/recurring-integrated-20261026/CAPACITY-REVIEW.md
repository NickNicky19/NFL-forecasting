# Recurring checkpoint capacity review — 2026-10-26

Read-only source reviewed: `c9f86d3c436ecfccf150dc3de0ced1d0589eb54a` in `/workspace/nfl-system-audit/producer-operations-final`. This report uses source and existing fictional evidence; it required no source edits, remote calls, private GETs, protected NFL outcomes or new profiling.

The checkpoint is one cumulative logical snapshot. `grade()` copies all previous captures, appends distinct new captures, and retains collector records, resolver versions, finality, week revisions and original durability clocks. The worker independently checks retention. V2 splits that complete canonical document into at most two byte fragments; it does not partition history into independently recoverable capture/week records. Resolved captures are not removed.

The owner reports **2,605 selected rows per real week**. The stress fixture instead contains **5,000 selected rows per fictional game/capture**, with 18,000 candidate forecasts, 5,000 R0 forecasts and 5,000 opportunities per capture. These are different workloads. Do not infer real calendar-day capacity by scaling only selected-row counts.

Daily refreshes of an already assigned game reuse its original capture. Observation deduplication also suppresses specified duplicate evidence. Therefore a daily run does not necessarily add another full capture, and this review makes **no hard three-day failure claim**. New captures, distinct correction/publication-clock evidence and finality receipts can still grow the cumulative document.

| Quantity | Exact bytes |
| --- | ---: |
| V1 decoded / encoded maximum | 67,108,864 / 8,388,608 |
| V2 decoded maximum, two parts combined | 134,217,728 |
| V2 encoded maximum, two parts combined | 16,777,216 |
| Each V2 part: decoded / encoded maximum | 67,108,864 / 8,388,608 |
| GHA `c9f86d3` two-capture decoded snapshot | 111,959,843 |
| Remaining decoded allowance at that point | 22,257,885 (21.23 MiB) |
| Those two encoded payloads combined | 4,820,439 (4.60 MiB) |

The observed decoded size is 106.77 MiB, or 83.42% of the V2 maximum. The GHA writer reached the graded snapshot and later failed at the unchanged CPU cap; this byte measurement is not a successful end-to-end GHA qualification. Evidence: `/tmp/nfl-grade-partition-gha-cpu-20261026/exact-failed-node-events.json`.

A simple three-capture projection, `111959843 * 3 / 2`, is approximately **167,939,765 bytes / 160.16 MiB**, above 128 MiB. This is an estimate using the average of the two fictional captures, including shared history overhead, not a measured third-capture failure or a real-week/day forecast. The exact additional allowance at the measured point is 22,257,885 decoded bytes, subject to every other cap.

Other independent guards remain: 36 captures, 36,000 primary opportunities, 648,000 projected forecast rows, the 144,000 revision guard, 32 MiB total private-runtime storage, 128 remote asset slots, 512 MiB local managed storage/address space, 120 CPU seconds, 180 wall seconds and 40 HTTP calls per checkpoint client. Existing, unknown and orphan assets consume runtime capacity. Current live namespace occupancy was not queried, so no number of remaining successful runs is asserted. **The 36-capture guard does not establish 36-capture capacity.**

Original forecast bodies remain separately archived; previous checkpoints and local resolver records also retain evidence within their respective bounds. None is an implemented bounded history compactor. `history()` reconstructs offers and forecasts from embedded captures, and `restore_previous()` restores and persists the complete durable document. Paging, compression and compact quota walks preserve bytes but do not remove this serialized accumulation. Dropping resolved captures or substituting aggregate reports would not satisfy the current retention/history contracts.

Consequently, cumulative growth is a concrete capacity barrier to a general recurring-readiness claim at the stress-fixture width, independently of CPU optimization. A smaller real workload may support more captures, but an exact operational lifetime is not established. A separately reviewed lossless history-partition/index/compaction contract remains needed before claiming continuing capacity beyond the admitted snapshot.

The owner subsequently reported a new cold mixed native pass: writer **105.10 CPU seconds**, **511,238,144-byte peak**, **39 calls**, approximately **4.869 MB transferred**; reader **42.05 CPU seconds**, **33 GETs**. This is parent-reported follow-up evidence, not an independently rerun result here; its exact source revision was not supplied in that update. Genuine combined Source CI remains pending in that update. A CPU pass does not increase decoded or retention capacity.

Source references, all at the reviewed commit:

- `nfl_lab/audit_weekly_grade_v1.py:43` — byte/count limits; `:1250` — cumulative capture retention; `:1329` — full snapshot assembly; `:1422` — history reconstruction.
- `nfl_lab/audit_weekly_operations_grade_v1.py:506` — lossless retention assertions; `:552` — prior capture reuse.
- `nfl_lab/audit_weekly_grade_checkpoint_v1.py:251` — append every part and then its private root.
- `nfl_lab/audit_weekly_grade_history_v1.py:1045` — complete snapshot restore, durability validation and persistence.
- `nfl_lab/state.py:119` — observation deduplication; `nfl_lab/private_draft_store.py:27` and `:329` — unchanged runtime/asset/call bounds and inventory accounting.

