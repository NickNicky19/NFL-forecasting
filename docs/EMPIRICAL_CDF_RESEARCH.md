# Empirical leaf distribution research

`all12-leaf-cdf-v1-20261023` is an opt-in research family. It does not change
the daily registry, recorded website forecasts, registered rec-half experiment,
or public model defaults. No category is qualified by this document.

## Fixed method

Each tree leaf retains the distribution of its original training labels. The
forecast averages 32 normalized leaf distributions and mixes in a fixed 5%
training-only position prior. The trees use depth 8, minimum leaf size 30,
squared-error splits, all declared features, seed 1701 and two threads.
Numeric medians, missing indicators and position vocabulary use training data.
Category owners declared two feature panels before scoring: player history,
then the same history plus team, opponent, rest and home context.

The count prior is geometric with mean `max(.05, training role mean)`. Signed
integer yards use a discrete Laplace prior centered on the lower training role
median, with `q = max(1, mean absolute deviation)/(1 + max(1, mean absolute
deviation))`. The binary-event prior is the Beta(1,1) posterior predictive.
These priors provide support; their use does not establish calibration.

The same law supplies a mean, lower median, variance, quantiles and exact
discrete CRPS/log mass. Count and binary support remains valid; negative yards
remain legal. Marginal distributions do not supply a joint player/game law.
Independent component draws are not used to construct combined yards or PPR.

## Evidence and comparison

The fixed campaign evaluates 2022, 2023 and 2024, fitting each year on eligible
earlier-season labels available before the first evaluation cutoff. All years
are already exposed. Source data are current-vintage reconstructions with an
assumed seven-day outcome lag, not authenticated historical publication.

Each fixed panel's primary comparison is median MAE against the unchanged
saved pooled point. Anytime TD uses probability Brier score. Saved recent
points, context versus player history, both point functionals, proper scores,
calibration and tails are reported separately. Saved control points are not
relabelled medians. Historical website/Sleeper forecasts are unavailable for
this panel. The separate Week 6 website scorecard remains separate evidence.

There are 24 fixed primary slots. Eleven categories support numerical studies;
exact PPR retains its blocked slots. Maximum 72 fit attempts, including those
six blocked annual cells; no failed fit is replaced. The campaign caps wall
time at 1,800 seconds, CPU at 2,400 seconds, process-group RSS at 2 GiB and
private outputs at 1 GiB. Each trial has 60 wall/90 CPU seconds. Reporting has
a 180-second wall reserve. Whole-week and game bootstrap intervals use 500
fixed-seed draws and are nominal 95%, unadjusted descriptive intervals. No
familywise, untouched-confirmation or promotion claim follows.

## Input, replay and failure contracts

The private sealed registry binds exact code, environment, category features,
source/control bytes, the prior software profile and separate read-only
review. The runner checks the seal in both parent and trial processes:

```sh
python -m nfl_lab.cdf_campaign run SEALED_REGISTRY.json NEW_OUTPUT_DIRECTORY
```

The output directory must be new. Reusing it fails; interrupted and failed
cells remain consumed. The runner preserves all planned opportunities and
stores model parameters, imputation, supported training keys/labels, leaf
memberships, histograms, query assignments, pre-score forecasts and attributed
outcomes. Calculation timestamps describe the actual research run after the
games. A freeze receipt does not turn historical predictions into pregame
forecasts. Row-level source/model artifacts remain private.

Inference is a pure explicit call using a trusted local model artifact:

```python
import joblib
from nfl_lab.cdf_engine import prediction_rows

model = joblib.load("trial/model/model.joblib")
forecasts = prediction_rows(model, qualified_feature_rows, score=False)
```

Rows bind season, week, game and player identity; team, opponent and position;
kickoff/cutoff; the declared lagged numeric features; and games-prior history.
The caller authenticates source identity, rights, version and availability.
The campaign additionally checks unique identities, temporal boundaries and
support. A warm row without a source clock fails; cold/unknown history may
have no clock. A missing or nonpositive games-prior count uses a trained role
prior. Nonmodeled roles also retain explicit role/global prior forecasts.
No supported training labels means abstention. Missing/invalid fields never
become outcome zeros. Played zero, missing statistic, DNP and unknown
participation remain separate. Exact combined labels need both components.

The consumer must read `mean` and `median` as different fields. Neither is a
replacement for an original saved website forecast. There is no inferred
market line, EV, injury status or unconditional participation claim.

## Exact PPR and integration boundary

`nfl_lab.ppr_outcomes.qualify_ppr_panel` preserves every planned offensive
opportunity and requires explicit scoring components, independent participation
and complete identity. Generic provider fantasy totals and absent rare-event
fields do not fill the scoring-source gap. Its fictional tests do not provide
NFL accuracy observations.

Any operational integration needs a separate qualified candidate, exact
source/conditioning compatibility, reference replay, inference manifest and
approval through the website owner's process. This family is outside the
default registry, so recovery consists of retaining the incumbent and stopping
the explicit research invocation. Immutable experiment records and failed
trials remain retained. No website merge, deployment, recorder or scheduler
activation is part of this work.
