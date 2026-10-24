# Source producer and bounded opportunity-study draft

New files on isolated base `4115d84836293a2ac90e442f20db6e6303f53fda` implement
the source read plan, not an actual numerical study. No source values, fits,
NFL forecasts, model, HTTP or CAS access occurred during implementation. Only
existing authenticated manifests, file sizes and Parquet schemas/row-count
footers were inspected. No tests have run in this packet.

## Executable prerequisite

`nfl_lab.dynamic_opportunity_source.ProjectionSource` authenticates all source
references through the caller's unchanged owned-reference adapter. Construction
rejects an unsealed actual plan. Its calendar reads exactly eight approved
columns; context projections omit labels/participation. `advance` reads only
newly eligible year/week/team groups under strict reconstructed kickoff plus
seven days **before** the held cutoff. Source years are 2019–2024 only. Raw
statistic/roster projections and qualified history share exact calendar joins.

An all-file identity-only projection supplies original physical row ordinals,
including POST rows if present. It contains only player ID, season, week,
REG/POST type and team. No statistic enters this all-row read. Each later
predicate-filtered primitive batch is matched against its entire ordered
identity inventory, preserving duplicate occurrences. Pointers bind body SHA
and original ordinal; no filtered ordinal impersonates a physical file row.

The recorded carry/target proxy uses all positions before offer filtering.
Known-team orphan credits, missing fields, invalid counts and duplicates remain
visible. Empty/missing is unavailable; explicit zero is supported only as an
explicit count. Every sum remains `all_nfl_credits_complete=false`; this is not
a complete NFL workload or a coherent team allocation.

Membership uses an explicit unique Week 1 same-team anchor and explicit evidence
for every required selected slot. Seven-day-unavailable, missing, duplicate or
conflicting membership consumes its slot and falls back. A first observed later
row is not a true cold start or transaction date. Status ACT/INA never creates
playing, DNP, injury or starter facts. Existing qualified played states and
explicit count equality supply player observations; unknowns stay unknown.
Sparse-zero semantics are not added. All offers retain original references or
explicit auxiliary abstention, including sparse/new/nonmodeled players.

`historical_requests` calls the unchanged V1 recorded-proxy helper and explicitly
new `dynamic_opportunity_history_replay_v2.build_historical_offer_windows`.
Root's separate timestamp-only census found all 25,872 saved 2022–2024 contexts
at kickoff. Their clocks remain byte/value unchanged. Only the separately
versioned exposed historical-replay adapter allows equality; source availability
stays strict. Original V1 and prospective actual-issuance rules remain unchanged.
That V2 module has separate owner acceptance; this packet does not retest it.

## One concrete backend, not another pipeline

`nfl_lab.dynamic_opportunity_study` supplies the 54-slot sequence, pre-work row
reservation, frozen selection/annual/global boundaries, unchanged core forecast
call, matching static formula, fixed conversion and bounded runner. Root assigned
the runtime owner the **one concrete backend** and CLI in separate new files.
This runner deliberately cannot construct an unreviewed backend or execute via
an activation flag. Actual end-to-end readiness requires that concrete backend,
exact environment/input freeze, original storage/evaluator and existing outer
guard acceptance. Callback mocks are software contracts, not an NFL execution.

Development retains six settings × two tasks × two years (2020/2021), selecting
once by pooled MSE and fixed ties. Original CDF forecasts do not exist for these
development years: every offer/failure is retained, selection uses the same
setting-invariant supported modeled-role cohort, and an empty cohort selects
no recipe. No fake historical CDF is created. Forward 2022–2024 uses frozen
recipes and earlier-only priors. Twelve final candidate, twelve matching static,
six auxiliary simple and 24 development packages total 54. Existing canonical
CDF/count_A/role_B/recent/pooled are read as exact saved references, never refit.
Auxiliary targets use explicitly fixed 3/8-slot simple controls and abstentions.

Counts use MSE, receiving yards the declared MAE heuristic; the original shared
scorer/pairs/reports and 500 seed-1703 clustered diagnostics remain required.
No numeric predictive law is attached. Other categories retain their existing
references and explicit untested state; exact PPR stays blocked. These are all
exposed development reconstructions, not prospective or website-relative wins.

## Pre-exposure storage and phase proposal

The old unexecuted 32 MiB proposal is insufficient under conservative full-artifact
estimates. Existing frozen correction files were profiled using size/footer
metadata only: 66 forecasts, maximum 23.877 bytes/row; 66 scored files, maximum
39.743 bytes/row. Planning rates are 32 and 40 bytes/row, plus 20 per retained
paired-loss row, 64 per factored request and 4 MiB control/report/failure reserve.
New schemas/compression can differ, so these are estimates, not guarantees.

The first cache-only census summed apparent path bytes and incorrectly called
them physical/global usage. A corrected metadata-only scan of all 58 registered
roots deduplicated hardlinks: 422,216,321 bytes used, 114,654,591 remaining under
512 MiB. The original receipt remains with this correction. Actual admission
still requires the unchanged locked storage scan; this metadata profile does
not certify it.
The new draft proposes **48 MiB before any actual source values or results**,
under the unchanged shared 512 MiB; 54 packages/600,000 forecast-row incidences,
16 prior-vector formations, two threads and 600 wall/CPU seconds remain fixed.
Actual preflight must calculate all 54 row counts, full requested comparison/loss
counts and request rows before forecasting. If the estimate or exact admission
fails, stop without dropping rows/artifacts or expanding after results. Do not
pretend the ceiling case necessarily fits. Factored histories are stored once;
no repeated full calendar/proxy JSON or full inherited environment per package.
The single backend may use explicitly versioned `FACTORED_SCORED_LABEL_VIEW`
and `REPLAYABLE_PAIRED_LOSS_VIEW` manifests: complete context/forecast/label rows
remain retained or exactly referenced; original scorer/version plus every input
hash and selector replays every logical paired row. Only redundant arrays are
avoided. New manifest/consumer contracts require independent review; no old
report or array contract is changed. Logical scored/loss row counts stay visible.

Cumulative phase caps are source/prior 100, development forecasts 120, selection
10, forward forecasts 120, scoring 60 and reporting 160 seconds wall/CPU, plus
30 for terminal/failure persistence. No unused-time transfer or repeated packages.
Per-package caps remain 20/20 seconds. The existing outer guard owns total600,
1 GiB combined RSS, PID/PDEATHSIG, no network/process escape and retention checks.
These are predata proposals for root/reviewer acceptance, not an actual GO.

## Proposed fictional software packet

Exactly twelve new methods exercise this producer/runner through fictional rows
and mocked I/O. One invocation, 120 wall/CPU seconds, 512 MiB, numerical caps two,
zero child workers/source/model/network/CAS or old test-suite runs. A single
stdlib harness retains consumption/failure and requires zero denied effects.
Exact immutable freeze and root GO precede invocation. Known process highwater
and traced checks are disclosed; no continuous kernel memory guarantee is made.
Requested GPT-6.1 Sol Extra High; actual backend settings remain unattested.
