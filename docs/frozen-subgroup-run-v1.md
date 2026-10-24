# Frozen subgroup runner v1

`run_subgroups(execution_config, config_sha256)` consumes an absolute execution
JSON path and its exact SHA256. It is opt-in; implementation and fictional tests
do not authorize actual scored-row reads. Root separately freezes the final
parent scored manifest/files, code, environment, supervisor and execution JSON.
The registration remains `source-matched-frozen-subgroups-v1-20261023`, SHA256
`f07cb07b9180129594ebdc0bba72386ceb777757756900ae4b4004924f6318bc`.

## Execution JSON schema

The exact top-level fields are:

| Field | Meaning |
| --- | --- |
| `registration_id` | `source-matched-frozen-subgroup-run-v1` |
| `subgroup_plan` | Binding of the f07 registration above |
| `parent_policy` | Binding of original benchmark policy `7c834dff5515eab9384218a3144026ffe52933f79ffa70437a4eb9e1ae75324f` |
| `parent_execution` | Binding of that original policy or the separate report recovery execution JSON |
| `parent_kind` | Exactly `benchmark` or `report_recovery` |
| `parent_output` | Exact absolute output namespace named by `parent_execution` |
| `scored_manifest` | Binding of `parent_output/scored-freeze.json` |
| `forecast_freeze_sha256` | Exact original global forecast-freeze SHA |
| `source_policy`, `source_manifest`, `category_contract` | Exact pointers retained from the original benchmark policy |
| `cache` | Exact original shared quota cache |
| `output` | Fresh separate absolute output, outside all input namespaces |
| `code_sha256` | Exact map of every recursive `nfl_lab/*.py` repository-relative name to SHA256, including this runner and its helpers |
| `environment` | Exact Python, executable, nine package versions, and `threads: 1` |
| `budgets` | Exact `LIMITS` dictionary below |

A file binding has required `path,sha256` and optional `bytes,inode,mode`, with
no other keys. Paths must be canonical absolute regular files with no symlinks
or traversal. `inode` is `[device,inode]`; `mode` is an octal string, accepting
either permission-only or full stat mode. Hash and file stamp must remain exact.
Duplicate JSON keys and nonfinite literals are rejected. Source manifest bytes
are hashed without decoding source bodies or observations. Source policy and
category metadata are decoded only from their pinned files. Their pointers must
match the original policy. All twelve category contracts remain, with exact PPR
blocked and unchanged core validation for the eleven supported categories.

`environment` has `python` (full `sys.version` or `platform.python_version()`),
`executable`, `threads:1`, and `packages` with exactly `numpy,pandas,scipy,
scikit-learn,pyarrow,joblib,threadpoolctl,requests,urllib3` and installed versions.
Numerical thread pools are constrained to one during aggregation. Code inventory
verification binds loaded helpers to their actual package files. Root records
the actual agent configuration separately; the runner does not infer it.

`budgets` is exactly:

```json
{"invocations":1,"automatic_retries":0,"max_wall_seconds":300,"max_CPU_seconds":450,"max_RSS_bytes":536870912,"threads":1,"max_shared_unique_file_bytes":536870912}
```

The source policy must retain the existing 512 MiB shared quota. Clocks begin at
function entry and include validation, aggregation, compression and writes. The
existing deadline helper constrains remaining wall time; local CPU/RSS checks
surround cells and success. Root's frozen outer supervisor is authoritative for
the complete process tree, hard limits and a final receipt even if quota or a
deadline prevents the runner from writing its own failure/finish receipts.

For `report_recovery`, `parent_execution.parent_config` must bind the original
benchmark policy and its `parent_forecast_freeze.sha256` must match the specified
global forecast freeze. Source/cache/category pointers still come from the
original policy; they are not invented as extra recovery config fields.

## Input manifest and one invocation

The parent manifest must have `state:SCORED_ROWS_FROZEN`, an exact
`registration_sha256` matching `parent_execution`, all 216 unique registered
annual statuses, `scored_files` and `bindings`. Original manifests use
`forecast_freeze_sha256`; recovery manifests may use
`parent_forecast_freeze_sha256`. Every present form must equal the specified
original forecast freeze. Both forms cannot disagree. No source feature,
query, model, forecast or new label partition is opened for aggregation.

Scored paths have exactly `private/scored/<2022|2023|2024>/<target>/<method>/rows.parquet`
or the parent's `leaf_cdf/role-prior.parquet`. All listed scored references are
authenticated, but no diagnostic `role_prior` rows are decoded or aggregated.
Completed annual statuses and main scored files must match exactly; all eighteen
PPR annual states stay blocked. Failed/unrun statuses remain without invented
rows. Every completed main file requires a positive frozen offered-row count.
Arrow filters constrain season/year before semantic column decoding; a retained
`season_type` column also gets a `REG` filter and consistency check. Row-count
equality prevents silently accepting a filtered subset. Every main file read
must retain its declared year, target, method and row count. The original parent
partition projection can omit `season_type`; this is not a missing observation
to fill. REG provenance comes from the pinned accepted source packet and frozen
parent source pipeline, not from an absent column or the week-number guard.

After static preflight, the unchanged `OperationalStorage` registers the fresh
output and writes `SUBGROUPS_CONSUMED.json` before decoding any scored rows.
An existing output forbids retry. The same existing global flock is held across
manifest verification, reads and writes, excluding registered external writers.
The owned-reference batch helper checks the manifest before decoding it, then
all listed scored references plus manifest/source binding; a final batch checks
those bindings again. Each batch retains unchanged full entry/exit scans, path,
read-only/regular-file/SHA/CAS/inode/ownership/hardlink/quota checks. Static
plans/source/category/config/code pins are also checked again before success.
Storage controls may register the new root; no parent output is written.

## Streaming output and privacy

One target-method pools its completed annual cells at a time, reading only
`READ_COLUMNS`: subgroup identity/context, point/law scores, actual/state fields,
role/fallback/history and optional regular-season type. Scored-file footer/schema
metadata determines whether that optional column is projected; every required
column must exist. It does not read other parquet columns. Present type values
must be REG; absent type metadata is never synthesized. Presence is recorded by
year in each pooled slot. If years differ in optional-column presence, retained
values are validated individually and the optional column is omitted from the
pooled helper input, preserving the same upstream source provenance.
Concatenation retains numeric dtypes, NaN, supported zeros and signed
zero bits; the unchanged subgroup helper validates support, roles and clocks.
Frames are released before compression; public/private objects are released
before the next target-method. No all-target scored or group concatenation occurs.

Each completed or partial cell produces:

- `public/groups/<target>/<method>.json.gz`: nonplayer aggregates and player
  coverage counts, with no player IDs, individual player metrics or game IDs.
- `private/players/<target>/<method>.json.gz`: private player group metrics.

JSON is streamed into gzip with `mtime=0` and no filename header, then only
compressed bytes are passed to the unchanged quota writer. No uncompressed JSON
copies are saved or assembled in memory. The Python aggregate objects and one
compressed buffer remain transient memory and still count against RSS. Sparse
nonplayer groups do not constitute a statistical anonymization claim.

Small public plan/report indexes preserve all 216 annual statuses and all 72
pooled slots: 66 supported target-methods and six blocked exact-PPR slots.
Completed-year subsets and absent years remain explicit; a cell with no completed
years is `MISSING_OR_UNRUN`. Failure detail availability is retained without raw
error strings. Public indexes contain only public file pointers. The private
player file index and validation receipts remain private, including absolute
input roots, code/environment bindings and owned-reference scans. No ranking,
new interval, contrast, model selection, promotion or website change is made.

Failures preserve consumption and existing partial compressed outputs, then
attempt create-only failure/finish receipts. No automatic retry, deletion,
replacement or rescue budget exists. A hard quota can also prevent receipt
writes; the outer supervisor must preserve the final failure/resource evidence.
Exact public exports still require independent review before publication.

## Fictional checks

The owner uses at most 120 wall/180 CPU seconds and one numerical thread. A
storage double exercises all 72 pooled slots/all 216 annual statuses with 198
fictional narrow reads with the parent's omitted optional type column, actual
subgroup evaluators, present/mixed/nonREG metadata and schema/binding failures,
recovery/partial/missing states, privacy, supported zero/unknown/infinite binary
semantics, immutable input dtypes, failure preservation and retry rejection.
A separate tiny real temporary quota unit checks deterministic compressed bytes,
owned aliases and unique-inode deduplication. No real parent data or store is read.
