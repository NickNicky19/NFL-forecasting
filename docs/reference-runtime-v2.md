# Frozen reference runtime acceptance

`nfl_lab.reference_runtime.run_acceptance(config, config_sha256=...)` and
`python -m nfl_lab.reference_runtime --config <path> --config-sha256 <sha>` execute
one separately frozen acceptance. The runner reuses the v2 source validator,
model binding, operational fit/replay wrapper, immutable quota storage and frozen
inference implementation. Existing modules are unchanged.

The exact registered historical/query parquet files are hash checked before
loading. Every query row, order, index and dtype is retained. Training kickoff
and outcome availability must precede the frozen feature cutoff. The cutoff is
never represented as an issuance time: all records carry actual `generated_at`
clocks and the `NONISSUED_RUNTIME_PROBE` evidence label. PPR retains two blocked
slots. No accuracy score, acquisition, promotion or official forecast is made.

Each of 22 fixed recent/pooled packages is consumed before fitting. Original
predictions and artifacts are retained before same process replay, existing
artifact reuse with fitting forbidden, fresh process replay and independent
formula comparison. All eight forecast fields are compared; numeric tolerance
is rtol=1e-10/atol=1e-9 with NaNs equal, family/fallback strings exact and
participation probability unavailable. Finite parameter, quantile order, count and
Bernoulli support checks run after first output bytes are saved; signed yardage
is permitted. Four negative cases and original-artifact
recovery are retained. Failures retain consumed markers and partial evidence.

`StateBoundStorage` delegates to the unchanged global storage transaction and
adds an exact serialized logical state check, including provisional plus final
model bytes and idempotent same-byte reuse. Every output and fresh-child pipe
chunk is persisted through the same global writer. The child writes only stdout;
it verifies retained query/artifact/binding/code hashes and the strict content
contract, blocks fitting/source loaders and source/training/outcome paths, and
allows reads only of its exact context/query/artifact files, repository Python
code and actual Python library/runtime metadata/zoneinfo roots. Paths are
resolved before comparison, all socket audit events are rejected, and it calls
only the frozen inference loader. It does not construct global storage because
that scanner would reread source blobs. The parent has verified blob ownership.

Private query rows, forecasts, artifacts and malformed negative fixtures remain
local. Content review and a separately accepted explicit publication subset
remain later steps. Passing this acceptance establishes inference/replay
behavior on reconstructed inputs; it establishes no prediction accuracy,
calibration, hosted readiness or scientific qualification.

The query forecast budget counts each requested route, including the four
expected rejections and technical recovery. A separate returned-row counter
counts the five complete 22-package passes plus recovery (75,591 rows for 681
queries); conservative route charges total 78,315. Internal fitted training
arrays are parameter and residual fitting work and are reported separately via
artifact supported training population counts. Combined process-tree RSS and
CPU/wall limits are enforced by the frozen outer supervisor; the inner RSS
receipt explicitly reports a single-process high-water value.
