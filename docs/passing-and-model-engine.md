# Shared engine and passing methods

`nfl_lab.models.fit_predict(train, test, target, method)` is a new lab engine,
version `shared-train-only-v1-20261022`. It serves all twelve targets with the
twelve preregistered method names in `config/research.json`. It does not claim
to recover a missing original executable or establish a predictive gain.

The return index equals the test index. Columns are `mean`, `scale`, `family`,
`p10`, `p50`, `p90`, `p_participation`, and `fallback`. The target distribution
is conditional on playing; `p_participation` remains a separate estimate.
`scale` is standard deviation, with negative binomial variance
`mean + alpha * mean**2` and a Poisson limit when alpha is zero. Count quantiles
are nonnegative integers. Yardage and exact PPR retain signed support. Anytime
TD is Bernoulli and relies on the caller's exact rushing-or-receiving event
definition. Passing TDs and thrown interceptions remain separate targets.

Only explicit played rows with supported finite labels fit target models.
Known DNP, unknown participation, missing outcomes and played zero are distinct.
Missing exact PPR training labels cause abstention; a provider's generic total
is not substituted. Position priors support new/sparse players, and unknown
positions fall back to the supported global prior. Source missingness and
population selection still limit participation probabilities: box-score
absence cannot be classified as DNP by this engine.

Numeric inputs must have an `f_` prefix and a recognizable lag/history/context
name; obvious future/outcome/raw-target columns are rejected. Position, team and
opponent are training-only categorical encodings. Medians, scales, categories,
coefficients, limits and dispersion estimates are fit only on training rows.
Earlier train labels are enforced against the earliest supplied test cutoff
or kickoff, and supplied outcome availability clocks must also precede it.
The source builder must independently verify availability clocks, its seven-day
lag policy and every rolling feature; column naming does not authenticate time.
Unknown test labels and test participation states are never inputs.

Recent/pooled controls shrink three/eight-game summaries to position priors.
Explicitly empty or unknown feature windows retain the prior fallback; the
engine does not extend those windows to skip missing intervening appearances.
Workload passing yards/completions/TDs/interceptions use projected attempts
times pooled/shrunken rates. Completions use a supported completion fraction;
the separate `coherent_completion_samples` helper draws integer completions
bounded by integer attempts. Target-conditioned marginal quantiles cannot be
combined independently and assumed coherent. Team-volume/share candidates for
attempts are new reconstructions. They do not import missing QB/RB coefficients.
Receiving and rushing yards retain signed efficiencies. Missing workload inputs
preserve a recorded recent/prior fallback. Exact PPR and Bernoulli workload
paths also fall back explicitly until their required adapters are available.

Ridge has fixed alpha 32. The bounded tree has 24 trees, depth at most six,
minimum leaf size 30, seed 1701 and at most two workers. Count distributional
means use fixed-penalty Poisson regression, with training residual NB2
dispersion. Binary fits use regularized logistic regression. The fixed ensemble
uses ridge/workload/recent weights .50/.25/.25. Feature ablations remove the
declared opponent, workload or team group and their metadata categories where
applicable. Fitted residual dispersion is not a claim of calibrated intervals.
Fit details and fallback counts are retained in JSON-serializable frame attrs.

Raw Sleeper and pinned website controls require an aligned archive point
`baseline_{method}_{target}`, literal boolean
`baseline_{method}_cutoff_verified`, original
`baseline_{method}_forecast_utc < kickoff_utc`, and a source SHA256 in
`baseline_{method}_source_sha256`. These fields are attestations from the
source-binding adapter, not independent authentication by this engine.
Missing/unqualified bindings abstain. A numerical archived point does not imply
an invented predictive variance or quantiles. An archived anytime probability
does supply a Bernoulli distribution after source qualification.

## Retained passing evidence

The retained audit reports passing-yard website attempts times the pooled YPA
of exactly three qualified prior appearances on 27 player-games across 13
games, including 21 informed forecasts and six unchanged fallbacks. Reported
website/candidate MAE was 56.622963/45.205603 and RMSE was
73.798344/66.822586, while signed bias worsened from -19.081481 to -24.072824
(prediction minus outcome). Candidate calculation occurred after the games.
This historical aggregate evidence is preserved and is not a new score or a
prospective confirmation.

The attempts candidate had 3.4415% worse MAE and 1.7233% better MSE than the
website on that same small comparison. The larger 2024–25 attempts study used a
different simple baseline. Its failed all-missing-input application remains a
failure, and original coefficients/preprocessing are absent. The completion
candidate improved reported MAE while worsening RMSE and bias. Neither tradeoff
is removed by selecting the preferred loss after seeing outcomes.

Exact original runners, bound history, row outputs, attempts coefficients and
preprocessing remain absent from the attachment (see retained
`MISSING_ORIGINALS.json`). This engine's passing workload candidate uses newly
specified priors and projected attempts. It cannot inherit any of those original
reproduction claims or insert the new attempts candidate into the original
website-attempts formula. The original pooled-YPA/completion comparisons remain
unrecovered, not reproduced, and pending independent later confirmation.

## Fitted artifacts and consumer replay

The optional keyword `fit_predict(..., artifact_path=Path("model.json"))`
exports the fitted state from that same fit without changing the default
predictions, candidate settings, or search budget. Files are immutable and
written atomically; an existing destination raises instead of being overwritten.
The finite JSON payload contains coefficients or every learned tree node,
feature preprocessing, position priors, workload rate/share parameters,
participation rates, conditional dispersion, training audit/configuration,
SHA256 hashes of the inference code/configuration, and the exact Python and
dependency versions. Its `environment.requirements_lock` list can be used to
restore those packages. It contains no raw training rows, player history rows,
Python pickle, or executable model payload.

`nfl_lab.model_artifacts.predict_artifact(path, features, input_manifest=...)`
performs inference from frozen state. It never fits a model, accesses training
history, or chooses another configuration. Normal, count, binary, workload,
ensemble and declared prior/fit-failure fallbacks are replayed. Invalid or
all-missing qualified histories retain their original prior fallback. Legacy
calls lacking the history-summary columns can consult old training history in
the default API; an export of that path is explicitly marked unreplayable.
This prevents an artifact from pretending to reproduce unavailable inputs.

The input manifest must attest `source_qualified: true` and
`availability_verified: true`, and provide the SHA256 `input_sha256` binding
the caller's source/feature manifest. Those assertions require actual source
qualification outside this module; they are not independently established by
an arbitrary boolean or checksum. Features must match the artifact's required
column schema. Missing numeric values are supported; missing required columns,
text/infinite numeric values, missing identities and late source cutoffs fail
explicitly. Test labels and target participation outcomes are not inputs.
Feature construction/provenance and actual pre-kickoff persistence remain the
source and capture adapters' responsibilities.

A standalone consumer is available without the training dataset:

```bash
python -m nfl_lab.model_artifacts model.json features.parquet input-manifest.json predictions.json
```

The consumer verifies payload integrity, model identity, full learned tree
structure, code hashes and the environment lock before inference. Point and
distribution outputs match the fitting API within floating-point summation
precision. The local lab helpers `activate_artifact`, `predict_active_artifact`
and `rollback_artifact` maintain an atomic active/previous pointer to immutable
files. Rollback verifies the prior file before changing the pointer; a missing
or corrupt prior leaves the active model intact. Code/environment mismatches
are rejected and require restoring the recorded inference release as well.
These helpers operate only on the caller's local lab paths and do not deploy
or modify the website.

Synthetic contract tests cover learned-tree/linear replay, all registered
methods, count/Bernoulli distributions, all-missing/failed/unfitted fallbacks,
source-schema rejection, immutable exports, checksum/code/environment failures,
process-independent consumer output, restart and verified local rollback.
They establish software replay behavior, not calibrated intervals or future
forecasting superiority. Existing exposed experiment results are unchanged.
