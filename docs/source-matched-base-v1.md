# Source matched base development benchmark

`nfl_lab.source_matched_benchmark` orchestrates the separately frozen packet
without changing its learners, source adapters, evaluators or old campaign seals.
Use `run_benchmark(config, config_sha256=...)` and
`report_benchmark(config, config_sha256=...)`, or the module CLI `run` / `report`
with `--config` and `--config-sha256`. Root freezes exact code, dependencies,
source identities, roles, budgets and storage headroom before actual model work.
The existing outer supervisor enforces the whole process resource ceiling.

RUN uses serial year, target and method order. Arrow projects query metadata,
clocks and `f_` features for one evaluation season before decoding, excluding
all target/raw-statistic values and observed participation. Query participation
is unknown. Training reads start in2019 and stop strictly before the evaluation
year, with kickoff and outcome availability strictly before its earliest query
cutoff. No2025/2026 semantic row enters any lane. Earlier exposed evaluation
labels may serve as later-fold training only after earlier-fold forecasts have
frozen; evaluation/scoring-role reads wait for the global freeze.

All216 planned slots remain, including18 blocked exact-PPR slots,30 aliases of
new same-source outputs,102 learned packages and66 reference summaries. Count A
signed/binary aliases the new median HGB; singleton-role B aliases the new A.
Old outputs are never used. Aliases retain hash/provenance and add no fit.
CDF and median calls retain their complete category dictionaries including the
unused context declaration. Only base is fitted. CDF role-prior laws receive
separate frozen forecasts as genuine distribution controls.

Estimator attempts are consumed before each actual optimizer call. Role A/B
use the existing `before_fit` callback; scoped instrumentation enforces per-fit
wall/CPU signal timers without changing estimator inputs or outputs. A quota-owned
mutable `estimator-cpu-guard.json` is active before the native fit and inactive
in `finally`; the independent outer supervisor monitors its process CPU and
monotonic start and kills the whole group with polling margin before60wall or
90CPU seconds when native code delays Python signals. The guard is excluded
from immutable forecast bindings; prior control bodies remain counted in CAS. A whole32-tree
forest counts as one attempt. Reference optimizers are forbidden. Internal
training prior/residual arrays are recorded separately in training audits.
Inference and CDF law recomputation charge the shared row-incidence ceiling;
alias copying is reported separately. Fit failures, blocked slots and unrun
slots remain explicit. No automatic retry occurs.

Every write uses the existing registered OperationalStorage. Joblib artifacts
serialize into BytesIO before quota-checked publication. They contain private
training bindings and empirical supports and must remain private. Original
forecasts, query contexts, models, aliases and attempt statuses are immutable
and hash-bound in one global forecast freeze before SCORE_CONSUMED exists.

REPORT permits one scoring-role label pass after that marker. It uses existing
CDF/point scorers without fitting; CDF scoring recomputes assignments/laws and
charges that work. Every original offered row remains, with conditional-played
primary-role accuracy distinguished from all-offered coverage. Proper law scores
apply only to CDF/role-prior distributions; numeric point methods acquire no
invented law. Reporting reads scored rows for one target at a time and quota-writes its
private paired losses immediately, retaining only small aggregate target items.
The separate reporting helper preserves annual and pooled exact
pairs, all named comparisons, private row losses and fixed500-draw PCG64seed1703
whole-week/game descriptive intervals or an explicit unavailable reason.

An explicit `resume_frozen=True` report continuation is permitted only after a
complete scored-row freeze. It verifies those bytes and performs no fitting,
label reads or model inference. Cumulative saved wall/CPU and row/fit counters
remain charged. A hard-interrupted attempt additionally requires separately
frozen authoritative outer `spent_usage`; usage cannot decrease. There is no
continuation of partial scoring and no automatic retry.

All2022-2024 years are exposed development reconstruction. Historical raw
Sleeper/SITE/incumbent controls are unavailable. Reports imply no independent
confirmation, website-relative improvement, calibrated distribution, winner,
promotion, hosted readiness or issuance. Root alone writes the ledger and
reviews any publication subset; rows, models, bindings and paired losses remain
private.

Live guard schema: `active` boolean, `pid` integer, `process_start_ticks`
(`/proc/<pid>/stat` field22), `process_cpu_start` (`utime+stime` divided by
`SC_CLK_TCK`), `cpu_clock=proc_utime_plus_stime_over_CLK_TCK`,
`monotonic_start`, `attempt`, `max_wall_seconds=60`, `max_CPU_seconds=90`,
and actual `generated_at`. The outer monitor polls at most0.1seconds and stops
at58.5wall or88.5CPU seconds; malformed/stale/wrong-process active markers
fail closed. Guard publication grants a mutable scope for that exact file only.
