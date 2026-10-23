# Six-cell native binary recovery

The exact root policy is `config/direct-xgboost-binary-recovery-v2.json`, SHA256
`81fcf8f0f24090b048d6dce1e72517bb4f0aa0f8eb2ffabc913ccf5f0098ada8`.
Preparation and fictional wrapper checks do not authorize actual model replay.
An exact execution inventory, independent PREEXEC PASS and root GO are required.

This derivative loads only the six hash-bound original XGBoost TD artifacts in
year-ascending small/medium order. A later model may contain earlier exposed
training information, so earlier-year forecasts must already be frozen before
that model can be loaded. Query row incidences are charged before inference.
All six forecasts must be globally frozen before cached donor label values are
opened. Original queries, preprocessing, fitted weights and fallbacks remain
unchanged. No new model fit, calibration, feature, clipping or tolerance change
is provided here. The accepted canonicalizer validates the native-dtype exact
complement and retains the event scalar unchanged.

The original frozen package is imported intact. The accepted canonicalizer is
loaded from its separately pinned path into that package as a new extension;
the original package files are not edited. Derivative manifests reference each
original model, code/configuration/environment and unchanged preprocessing.

The label donors are exactly the original saved `direct_lightgbm_small` TD
scores. Their forecast values are not used. Identity, row order, team, opponent,
position, season type, cutoff, kickoff and role mask must match the original
query. Actual event, participation and qualified outcome states are preserved,
including missingness. The unchanged scoring, normalization, paired metrics,
subgroups, five controls and uncertainty helpers are reused.

This is one 120 wall-second/180 CPU-second/1 GiB/two-thread invocation, at most
six model loads and 60,000 query prediction row incidences (planned 51,744),
with zero new fits and network calls. New retained content is capped before
write at 16 MiB through an additional admission check on the reviewed CAS cap;
the existing global 512 MiB quota/ownership/immutability checks stay in force.
The reviewed PDEATHSIG/PID-identity resource guards are reused. The outer
supervisor requires the exact pinned GNU timeout parent for 120 seconds.
The worker forbids subprocesses. Its numerical thread controller resolves only
the frozen, already-loaded libc directly, avoiding `ldconfig` discovery while
retaining the original two-thread prediction scopes. Other library discovery
requests fail closed. The worker receives no account/key/proxy environment.

Fourteen new fictional wrapper checks passed in the single registered software
invocation. They cover pre-inference charging, chronological/global freeze
boundaries, donor parity and missingness, forbidden training/source routes,
process-free thread control and the prewrite retention cap. They add no NFL
observations and do not rerun the earlier canonicalizer software tests.

Original failed cells and the original FAILED screen remain unchanged. The
derivative adds no NFL observations, prospective forecasts or confirmation,
and supports no website-relative, release-ready or optimality claim. A failure
retains its spent counters and artifacts and does not authorize a retry.
