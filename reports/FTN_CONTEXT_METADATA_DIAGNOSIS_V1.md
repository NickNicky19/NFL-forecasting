# Fixed-game context diagnosis prerequisite

## Existing failed attempt is preserved

The one authorized FTN zero-join attempt failed at the original first context
gate, before primitive-statistics projection, with 67 planned raw context rows,
31 accepted/offered rows, and 163 appearance rows. It applied no zeros and ran
no forecast fits or accuracy comparisons. Its failure SHA256 is
`2b1022be9e9804895fce4e9edf419e36473150462b7e6fd1776edad015456a17`;
its supervisor receipt SHA256 is
`daf83611d6f1e0521301f1fac9ec819d25a6bacd73790e057d29571bdb070f2f`.

No context projection was persisted before that failure. Therefore the existing
artifacts cannot identify which context field failed. Do not infer an actual
field defect, repair identities, or rerun the consumed join from this message.

The original supervisor recorded a sampled combined RSS of 897,024 bytes while
its worker's individual `ru_maxrss` was 161,746,944 bytes. That combined sampler
does not establish visibility of the known supervisor/worker or certify the
whole-job memory budget. Its best-effort `/proc/.../task/.../children` traversal
can omit processes without checking that required known PIDs were observed.
The precise environmental reason for the missing traversal is unestablished.
These are source/software findings, not changes to NFL forecasting scores.

## Smallest separately registered substitute

The new diagnostic reads only these original eight context columns from the
same authenticated raw source, using only `game_id == 2024_01_BAL_KC` and a
200-row materialization cap:

`game_id, season, week, season_type, player_id, team, opponent_team, position`

It excludes every primitive statistics column, accepted outcome/feature table,
appearance feed, candidate forecast, and score. It performs no join and requires
no valid identity to count a projected row. All returned rows contribute to
aggregate null/mismatch counts. It emits counts for the original first context,
second team/opponent, and third identity gates; no row, player ID, arbitrary
source value, or statistic value is retained. Position null counts are reported
separately because position was not part of the original first-gate requirement.

Results can identify a field-level prerequisite. They cannot apply source
repairs, establish participation, restore zeros, qualify PPR, select forecasting
methods, or validate forecast accuracy. Existing data and failed artifacts remain
unchanged. A later source substitution or corrected join needs its own version,
registration and authorization; this is not a retry of the failed join.

## New sampler and execution boundaries

The new wrapper explicitly binds the known timeout, supervisor and live-worker
PIDs plus process start ticks. Every required process must have matching
`/proc/<pid>/stat` and status identity and a positive, correctly encoded `VmRSS`.
There is no empty-descendant-discovery or missing-RSS-to-zero fallback. Missing
worker visibility is accepted only after `poll` confirms that exact child exited;
otherwise the worker is killed and the job fails closed. Reaped child CPU is
added; an exit race may conservatively overcount rather than omit it.

The reviewed helper creates no native subprocesses; Python socket/process
creation audit events are denied. This is not a hostile-native-code sandbox.
RSS remains a 10ms sampled observation that can miss transient peaks. A 240MiB
stop threshold reserves 16MiB under the 256MiB budget; no RLIMIT_AS is used.
Required direct-process accounting is checked before any worker/source read.

The exact pinned GNU timeout `--signal=KILL 60s` parent, PDEATHSIG worker cleanup,
five numerical thread variables set to one, Python `-B`, 50s worker alarm, 53s
worker-stop reserve, 54s combined CPU reserve and 59s supervisor alarm remain.
Logs are drained and capped at 8192 bytes per stream; source exception messages
are not printed. Whole-job allocation ceilings total 1MiB: 786,432 worker payload,
131,072 supervisor payload, and 65,536 control/ownership bytes per process.
Original shared 512MiB flock/CAS/ownership checks remain unchanged. Original and
new code, binary/config/source-policy bindings and package versions are checked
before source decode and again before success. Input owned references are
authenticated on entry and exit. Before-final-write and after-write resource
observations are distinguished; no exact unseen exit/continuous peak is claimed.

Fresh diagnosis namespace:

`/workspace/website-methods-research/resumed/ftn-context-metadata-diagnosis-v1-20261023`

Fresh supervisor sibling:

`/workspace/website-methods-research/resumed/ftn-context-metadata-diagnosis-v1-supervisor-20261023`

Either namespace already existing consumes/fails a repeated invocation. Retain
failures; automatic retries are zero. The integrator alone writes the ledger.

## Prepared status

This change supplies source, an unbound template and an exact bound registration
and execution-freeze copy for the integrator's review. Bound JSON is a software
binding, not execution authorization. Integration, independent preexecution
acceptance and integrator GO are required. No new source query, primitive decode,
join, diagnosis execution, fit, score, HTTP request or test rerun occurred during
preparation. Static AST/manifest checks do not certify actual runtime behavior.
The old 32-test result belongs to the old helper; no new test count is claimed.
Requested GPT-6.1 Sol Extra High is not an actual backend-settings attestation.

After exact integration and GO, with the five thread variables set to one:

```sh
/usr/bin/timeout --signal=KILL 60s /workspace/nfl-venv/bin/python -B /workspace/nfl-methods-integration/tools/ftn_context_metadata_execute_v1.py --freeze /workspace/nfl-methods-integration/config/ftn-context-metadata-execution-v1.json --freeze-sha256 ACTUAL_BOUND_FREEZE_SHA256
```

No source artifact or retained context data is bundled for public redistribution.
