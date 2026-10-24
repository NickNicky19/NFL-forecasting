# Sequential context diagnosis prerequisite v2

## Correction and preserved failures

The original storage module is **not** stdlib-only. Its footer at lines 720–722
unconditionally imports pandas and captures `DataFrame.to_parquet`/`to_csv`.
Earlier guard-preparation descriptions that characterized this module as
stdlib-only were incorrect. Those descriptions inspected its opening imports
and missed the footer. The original storage source and all dataframe hooks stay
unchanged.

The v1 context-diagnosis guard imported storage in its supervisor before starting
the source worker, loading pandas/NumPy in both processes. The explicit-PID
sampler then correctly stopped at its 240MiB safety threshold: sampled combined
RSS 253,743,104 bytes, supervisor individual highwater 114,098,176 and child
individual highwater 138,448,896 bytes. Its receipt is pinned by v2. The source
worker was killed and no diagnosis result was retained. This does not identify
the original failed context field or establish that context values were decoded.
The old diagnosis and original zero-join attempts remain failed and consumed;
they are neither retried nor relabeled.

## Minimal orchestration change

V2 uses three **sequential** phases under the same external 60-second timeout:

1. A stdlib-only supervisor launches a storage bootstrap child. That child loads
   the unchanged original storage module, atomically persists consumption/freeze
   metadata under its original shared quota and exits. It performs zero source
   queries and imports no source reader or diagnosis helper.
2. After bootstrap has exited and been reaped, the supervisor launches the source
   worker. The worker authenticates the owned bootstrap receipt/freeze and runs
   the same eight-column, fixed-game, counts-only diagnosis. It exits and is
   reaped before the next phase.
3. Only after both children are gone does the supervisor import original storage
   to persist bounded phase logs and final resource receipts.

Before either child starts, an explicit `sys.modules` check rejects heavy pandas,
NumPy, PyArrow or storage imports in the supervisor. The worker keeps the original
full dataframe hooks. There is no storage fork, footer removal, AST transformation,
quota bypass, threshold increase, or source/diagnostic rule relaxation.

The v2 source function reuses the original v1 `diagnose_context` arithmetic.
Only provenance/version/output namespace differ. It still projects exactly
`game_id, season, week, season_type, player_id, team, opponent_team, position`,
for `2024_01_BAL_KC`, at most 200 rows. Invalid identities remain counted.
It emits field-level null/mismatch counts and no IDs, raw context rows, primitive
statistics, model features, fits, forecasts, scores, repairs or applied zeros.
Historical availability and participation are not established by this diagnosis.

## Unchanged limits and new accounting

- One invocation; no automatic retries, HTTP, new acquisition or software
  profiling. One fixed context projection is permitted only after registration
  and integrator GO.
- 60s whole-job wall/CPU, 256MiB combined RSS, 240MiB sampled stop threshold,
  one numerical thread. No RLIMIT_AS and no claim of a continuously enforced
  RSS maximum. Required timeout/supervisor/current-child PIDs and start ticks
  remain explicit; unavailable required RSS fails closed. Known individual
  highwater above 256MiB rejects success. Cumulative child CPU includes bootstrap
  and source phases; wall/CPU reserves never reset between them.
- Bootstrap alarm 20s; source alarm 50s; cumulative child-stop wall 53s and CPU
  54s; supervisor alarm 59s; external pinned GNU timeout SIGKILL at 60s.
  Both children have PDEATHSIG and Python network/process-creation audit denial.
- All original shared 512MiB quota/CAS/flock/ownership checks remain. Attempted
  allocation ceilings are 786,432 source payload bytes, 65,536 bootstrap payload
  bytes, 65,536 final supervisor payload bytes, and 32,768 control/ownership bytes
  for each of three processes. Total 1,015,808 bytes, below the 1MiB allowance.
  Logs are capped at 8192 bytes per stream per phase and drained concurrently.
- Every phase verifies exact code/config/Python/dependency/policy bindings.
  Source references retain original entry/exit ownership checks. Before-write
  receipts and after-write tool observations stay distinct. A maximum over
  multiple children is labeled as such, not attributed to one specific child.

New diagnosis namespace:

`/workspace/website-methods-research/resumed/ftn-context-metadata-diagnosis-v2-20261023`

New supervisor sibling:

`/workspace/website-methods-research/resumed/ftn-context-metadata-diagnosis-v2-supervisor-20261023`

Bootstrap checks both are absent under the original quota lock and consumes the
supervisor namespace before any source phase. A bootstrap failure prevents source
execution; a final supervisor receipt preserves the failed attempt where budget
allows. No failed or interrupted namespace is reused.

## Preparation status

This is code/proposal preparation only. No source query, new runtime profile,
software test, diagnosis, numerical join, forecast experiment, HTTP request or
CAS write was performed by this agent. Static AST checks do not predict the
actual resource footprint; the new design must still pass its registered hosted
run. Requested GPT-6.1 Sol Extra High remains an unverified backend setting.
Only the integrator writes the execution ledger or authorizes a future GO.
