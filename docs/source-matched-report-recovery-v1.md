# Source matched report recovery v1

This is an opt-in technical recovery of the original benchmark's **first**
scoring phase. Original completion remains `FAILED/WALL_LIMIT`: 1,198.815180
seconds wall / 1,269.298613 seconds CPU, peak combined RSS 760,012,800 bytes.
All 198 packages froze, with 18 exact-PPR blocks and 168 estimator / 66 reference
calls; parent `SCORE_CONSUMED`, scored rows and report were absent. The original
1,200-second limit is unchanged. No original output can be rewritten here.

Policy SHA256 `d5e040355be0dd07ea0af0c4182e4f7c1fcd386fd8277b52d6a3217dfc196e35`
and clarification SHA256
`751c318afbae59c9f235cc9d43d57a1534446d9c4148f4ec7fe881b4e2b1e4f0`
were separately declared. The repeated verification bottleneck was whole-store
directory/stat/inode/quota scans and selected reference digests. Existing CAS
body hashes are memoized by stat fingerprint; this is not a claim that every
CAS body was rehashed 1,407 times.

## API and execution config

`run_recovery(config, config_sha256=...)` or
`python -m nfl_lab.source_matched_report_recovery --config <path>
--config-sha256 <SHA>` is standalone and never calls the old RUN or REPORT API.
Root must freeze the exact new module/helper, dependencies, parent metadata and
execution config before actual use. Execution config keys are:

- `registration_id`: `source-matched-report-recovery-v1-20261023`.
- `policy`, `clarifications`, `parent_config`, `parent_execution_freeze`,
  `parent_completion`, `parent_forecast_freeze`: exact `{path, sha256}` bindings,
  optionally with `bytes`. All paths are canonical absolute paths.
- `output`: the separate namespace fixed in the recovery policy.
- `additional_bindings`: array of exact file bindings, including the executing
  recovery module and `owned_reference_batch` helper.

Parent execution metadata retains its array of 82 bindings with exact byte
hashes, sizes, original inodes/modes, Python/executable, nine package versions
and two threads. These are checked before labels and again before final success.
The original public policy, source inputs, queries, category contracts, aliases,
fitted models and forecasts are unchanged. New CLI publication code is not part
of this accepted old source chain and must remain isolated until its acceptance.

## Eligibility and one scoring phase

The runner requires the exact declared failed completion, matching resources,
the complete 216-slot ordered plan, 198 `PREDICTION_FROZEN` states, 18 blocked
PPR states, no fatal RUN error, all 1,407 frozen bindings, unchanged 168/66
counters and parent cumulative row charges 1,733,424. Any parent scoring marker,
scored file, scored freeze or report makes this version ineligible.

The existing `Session` supplies source/category pinning and quota serializers;
its writable output is redirected to the new namespace. The separately reviewed
batch helper verifies all parent owned references plus the global freeze under
one existing global flock, with full unchanged entry/exit scans and every
original per-reference check. No per-reference whole-store scan is repeated.
Only after that succeeds does `REPAIR_SCORE_CONSUMED.json` precede the first
label read. There is exactly one Arrow-filtered label read for each of
2022/2023/2024, using the unchanged base reader and exact saved queries.

The unchanged `_outcomes`, normalizer, point scorer and CDF scorer are reused.
CDF and role-prior scoring recompute their saved laws and charge those rows
before each call. Estimator methods, core `fit_predict`, operational reference
fit/prediction, old RUN/REPORT and network entry points are forbidden. There is
no feature rebuild, source acquisition, model fit, new forecast or protected
year access. Numerical counters remain cumulative under the original 3M ceiling;
168 estimator attempts and 66 reference calls cannot increase.

All scored files freeze before aggregate reporting. The unchanged reporting
helper runs one target at a time with 500 PCG64-seed-1703 week/game cluster
replicates. Private paired losses are written per target, without a combined
large frame. All annual cells, missing/failed states, offered rows, roles,
unknown/DNP/missing/played-zero distinctions and 18 PPR blocks remain explicit.
Partial scoring failure saves its slot statuses when storage permits; its
consumed marker prevents retry. No partial-scoring continuation is offered.

`scored-freeze.json` contains `state=SCORED_ROWS_FROZEN`, new config SHA, parent
forecast freeze SHA, all slots, new-output-relative `scored_files`, own output
hash `bindings` and cumulative work usage. Scored paths are
`private/scored/<year>/<target>/<method>/rows.parquet`, with CDF's
`role-prior.parquet` separately diagnostic. Parent files and all original code
pins are verified again before `report.json` is written.

## Resources and interpretation

The recovery has a separate additional **600 wall / 900 CPU seconds**, **2 GiB
RSS**, **two-thread** budget. An outer frozen supervisor enforces process-tree
resources; inner accounting checks the same additional limits and preserves
parent work counters. The existing global 512 MiB private retention quota covers
all new files. New resources, original failed resources and sequential totals
are reported separately. The original run never becomes a budget pass.
The report's inner clock starts at `run_recovery`; the separately retained
outer completion is authoritative for the full producer's additional and total
resources, including preflight and imports.

This code has only fictional software evidence until a separately frozen actual
execution and independent review. Historical 2022–2024 outcomes are exposed
development data. No confirmation, historical raw/SITE comparison, promotion,
publication, hosted acceptance or website change follows from this recovery.

## Fictional software checks

The first run passed 11 checks, including the complete 198-package/18-block
scoring path with the real target-local reporting helper. A second run passed
34 checks (one expensive end-to-end case deselected): the recovery guards,
retained partial-resource-failure statuses/no-retry case, and the batch helper's
23 production-storage fixtures. These suites overlap. The orchestration fixture
uses a storage double and serialized inert model objects; it does not establish
real artifact or quota acceptance. The batch's ownership/quota behavior is
tested separately against the unchanged real storage implementation.

No test failed. Cumulative measured software time was 76.349074 seconds wall /
77.383640 seconds CPU; peak child RSS 220,893,184 bytes, with two threads. No
actual NFL, private source/model/forecast values, fitting, scoring, aggregation
or network was accessed by the owner. Actual recovery remains root-only after
the exact dependency/code/input freeze and independent review.
