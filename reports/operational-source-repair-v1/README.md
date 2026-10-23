# Operational source repair v1: software and cache acceptance

2026-10-23. This packet prepares the existing lab's daily capture, grading and
weekly learning to use a separate permitted NFL history. It adds **no measured
forecast improvement, model promotion or hosted activation**.

## What changed

- New source adapter selects only NFL statistics, eligible roster context,
  schedule metadata and exact identity inputs. It requests and reads no PFR
  snap data, NGS, news, odds or legacy processed feature table.
- Exact season/week and REG predicates reach parquet before original statistic
  values decode. Only complete weeks whose latest kickoff plus seven days is
  earlier than the declared asof qualify. That historical availability remains
  a reconstruction assumption, not authenticated upstream publication.
- Supported positive official physical events establish playing. Zero-only,
  missing and ACT/INA rows remain unknown and consume their original history
  slots. Supported target zeros and signed yards survive. Invalid target count
  values fail closed. Participation probability and exact offensive PPR remain
  unavailable under their incomplete contracts.
- All four operational CLI commands require the new policy. New reference
  artifacts bind policy, code, source, qualified training view, training
  features and query/input identities. Old PFR-trained artifacts cannot supply
  this path. Replay rejects mismatches and marks participation unavailable.
- Daily and weekly learning use only recent/pooled references. The consumed
  historical search and `selected.json` do not run again. Weekly refresh is
  bounded to 22 supported reference packages and performs no new accuracy score
  or automatic model selection.
- Supplemental grading uses the permitted cached view. Primary retained
  provider final/correction semantics remain separate. Failure paths preserve
  committed captures and continue grading/replay without legacy fallback.
- The existing scheduler keeps one job and its 40-minute cap. Effective command
  limits are 540 seconds daily, 180 acquisition, 720 reference learning and
  180 grading, leaving time for checks, replay and persistence. These are lower
  operational ceilings; original research search/fit gates are unchanged.

Frozen `data.py`, `features.py`, `permitted_source_features.py`, `models.py`,
`model_artifacts.py`, `evaluation.py`, the original research configuration,
rec-half registration and all frozen numerical reports remain byte-identical. Original
forecast/outcome/model records were not rewritten. The website is unchanged.

## Executed here

| Check | Measured result |
|---|---|
| Cached source inventory | 19 authentic body/receipt pairs, 18,394,133 body bytes; 0 new HTTP |
| Root integrated software suite | **690 passed**, 47.38 pytest / 48.07 wall / 54.09 CPU seconds; 724.1 MB peak RSS |
| Real-source prerequisite | One sealed invocation; **52.48 wall / 57.38 CPU seconds**, 696.8 MB combined RSS, 29.93 MB private packet |
| Historical qualified view | **62,388** player-game rows, 2019–2026, 129 season-week blocks |
| Participation | **42,286** supported positive-event played; **20,102** unknown; no certified DNP from this source |
| Supported core statistics | 42,219 supported rows per available target; 67 additional played rows lack those statistics |
| Features and future queries | **97** feature columns; 62,388 historical rows and **681** future query rows across **13 games** |
| Started opportunities | 55 player-games already started and excluded from future feature queries |
| Real model fits / predictions / new accuracy scores / confirmation observations | **0 / 0 / 0 / 0** |

This is source/feature software acceptance. The 681 rows are query features,
not newly issued forecasts. Source played/zero totals cover all supplied skill
roles, including non-QB passing zeros; they are not primary prop comparison
denominators. The source-owner's 35 and integration-owner's 99 focused checks
overlap the root suite and add no football observations. Failed launcher
attempts due to an absent timing binary are retained; no tests ran in them.

Cache acceptance narrowed 2026 to Weeks 1–5. Sixteen original stat/roster reads
record their exact pushed predicates. Query target labels remain blank. Snap
means remain missing and snap-count summaries are zero known observations.
Both original inputs and 55 sealed bindings were checked before/after use.

Independent read-only review accepted the source code and freeze, then checked
saved row/state counts, protected predicates, missing query labels, feature
timing, snap absence, file hashes and original frozen bytes. It ran no producer,
model, test or numerical forecast study.

## All twelve categories

| Target | Source support in this broad historical view | Forecast decision |
|---|---|---|
| pass_yd | 42,219 supported values; signed yards retained | No new accuracy test or promotion |
| pass_td | 42,219 supported count values | No new accuracy test or promotion |
| pass_cmp | 42,219 supported count values | Mixed/failed prior methods retained |
| pass_att | 42,219 supported count values | Mixed/failed prior methods retained |
| pass_int | 42,219 supported count values | No new accuracy test or promotion |
| rush_yd | 42,219 supported values; signed yards retained | No new accuracy test or promotion |
| rush_att | 42,219 supported count values | Original complete-RB/prior protocol remains unresolved |
| rec | 42,219 supported count values | rec-half registration/Weeks 7–14 unchanged, no restart/backfill |
| rec_yd | 42,219 supported values; signed yards retained | Completed history adapter and prior results retained |
| rush_rec_yd | 42,219 supported values | Separate combined/coherence evaluation remains required |
| Exact offensive PPR | **0** qualified labels | Full scoring/source contract remains required |
| Rushing-or-receiving anytime TD | 42,219 conditional played event values | No new probability accuracy/calibration test or promotion |

The [latest numerical matrix](../role-count-boosting-v1/category-status.json)
and [complete research index](../RESEARCH_INDEX.md) retain all actual measured
gains, regressions, failures and missing originals. This source change inherits
none of those gains or independent confirmation.

## Current readiness and next bounded work

**IMPLEMENTED / SOFTWARE_ACCEPTED / CACHE_SOURCE_ACCEPTED.**
**NOT_OPERATIONAL_READY / NOT_RELEASE_READY.**

The new workflow routing remains on the draft research branch. Existing hosted
operation still uses its earlier main code. No new run or scheduler was started.
Before replacing that path:

1. Enforce one quota before incoming source/feature/model writes. Current guards
   detect an overshoot after a bounded write; this is insufficient to claim a
   strict peak guarantee. A failed/over-limit stage must retain its evidence.
2. Add a separately versioned storage/retention design. V1 copies per-asof source
   bodies and subsets; repeated versions can exhaust 512 MiB and then abstain.
   It neither deletes frozen evidence nor promises unbounded future storage.
3. Freeze exact accepted input/query/code files for at most 22 real recent/pooled
   reference packages, replay them and review artifact content before any
   derived model publication. This packet issued none.
4. Verify actual hosted execution, missed schedules, idempotency, grading and
   rollback before claiming the operational handover complete.

These are internal engineering tasks within the existing goal. No new owner
permission or credentials are requested. No website integration is authorized
by this checkpoint; its owner retains activation.

## Reproduction references

[Source contract](../../docs/operational-source-v1.md) ·
[Operational routing](../OPERATIONAL_SOURCE_ROUTING_V1.md) ·
[Frozen policy](../../config/operational-source-policy-v1.json) ·
[Aggregate cache results](aggregate-cache-acceptance.json) ·
[Execution/review receipt](review-receipt.json) ·
[Hash manifest](hash-manifest.json)

Raw bodies, player/query rows, source-derived parquet files and model weights
are not included in the public packet. Local private artifacts are bounded;
their long-term hosted retention is not established by this run.
