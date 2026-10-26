# Hierarchical interceptions pilot — fitted, not scored

## Fixed method

This is one new expected-interception-mean procedure, with MSE primary and
MAE/RMSE/bias/tails secondary. It is not a median, calibrated count law or prop
probability model.

```
log(mean) = intercept + volume_slope * standardized_log_prior_attempt_volume
           + missing_slope * missing_volume_flag
           + player_effect + team_effect + opponent_effect
objective = sum(Poisson mean negative log likelihood)
            + 0.5 * sum(fixed_slopes**2) + 2 * sum(group_effects**2)
```

The intercept is unpenalized. Volume is the existing qualified three-game
passing-attempt mean, using log1p and training-only preprocessing. Unseen group
effects use their zero-centered prior; the only numerical fallback is the
existing training-only QB prior mean. This combined representation/model pilot
does not isolate a learner-only effect.

Training uses the authenticated 1,865 supported QB appearances from 2019–2021.
The planned 2022 comparison retains all 1,354 original offers: 633 supported
outcomes across 271 games/18 weeks, including 342 supported zero interceptions,
and 721 unknown offers. Controls are Leaf-CDF, Response-CDF, corrected Count A,
role prior and the completed NGBoost pilot on the same rows.

These are already exposed development seasons. Keeping labels closed during
this execution does not create untouched confirmation. The seven-day historical
availability reconstruction remains an assumption. Historical SITE/R0 forecasts
are unavailable.

## Actual execution and failure

One fixed L-BFGS-B fit and one declared training fallback-prior estimate ran.
The optimizer converged: retained status 0, failure code 0, 180 coefficients,
with group sizes 113 players/32 offenses/32 opponents. Its iteration count was
not retained and remains unavailable; no refit was used to recreate it.

Full learned float64 parameters, preprocessing, fallback scalar and vocabulary
identity are retained in a real immutable 1,460-byte private artifact, SHA-256
`0f70f2e2a58e71604240039f3896bd0f56678dd363e5045f6669f0d520ec4822`.

The first prediction ran, but its full forecast archive plus required receipts
could not fit the fixed **6,144-byte study allowance**. Parameters and failure
records were retained; evaluation labels stayed closed and no score was computed.

A separately reviewed no-refit continuation restored the model and charged one
additional prediction. Its fixed lossless XOR/byte-shuffle codec also exceeded
the allowed **4,052-byte forecast payload**, before persistence and evaluation
labels. Its exact compressed size was not retained. Neither prediction vector
was retained or hash-bound, so there is no original-vector reproduction claim.

**Consumed totals: one optimizer fit, one fallback-prior estimate, two prediction
passes, zero evaluation scores and zero HTTP requests.** No further retry,
refit, model search, formula change, budget refund or cap increase occurred.

|Attempt|Native CPU seconds|Native wall seconds|Outcome|
|---|---:|---:|---|
|Original fit and prediction|20.846|20.788|Parameters retained; archive too large|
|No-refit restoration and second prediction|16.976|16.902|Archive still too large|
|Cumulative|37.822|37.690|Within original 45 CPU / 90 wall cap|

The continuation was limited to 23 CPU/68 wall seconds and 4,490 additional
private bytes within the unchanged total cap. All seven original/continuation
files remain retained: **1,885 bytes total, including 425 control bytes**, below
the respective 6,144/768-byte caps. The shared 512 MiB cap was not raised and no
evidence was deleted. Independent POSTEXEC checks verified every retained file,
the full model/header round trip, terminal exposure flags and immutable CAS
state. No forecast, accuracy metric or interval artifact exists for this pilot.

## Versions and decision

Original executed plan:
`cb81b711a99b46658f0cf56f5d098597df0de1badb2c8f3ff2a5aae1712804db`;
worker `28bb046fbfce71da227593db33365a28d0375bfd18547b1b28ee63993eea73db`.
No-refit continuation plan:
`599a4b07519a93cc0938569c71e3055e8846c2ca6f711ea332b71737673547c7`;
worker `d0755af2ff4846c40083d293e5a58374390ff49250c704bbfd84ad6a746f9f16`.
Earlier prepared-but-unexecuted code and consumed budgets remain separate.
Requested agents: GPT-6.1 Sol/xhigh; actual backend attestation is unavailable.

**Accuracy: unmeasured. Decision: retain incumbent; no challenger entry,
selection, deployment or scientific qualification.** This cannot be described
as beating any control or the website. A legitimate future technical continuation
needs its own finite allocation, durable complete forecasts and actual scoring.
