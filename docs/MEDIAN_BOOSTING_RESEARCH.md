# Fixed absolute-error boosting research

`all12-median-boosting-v1-20261023` is a new opt-in point-model experiment.
Its hypothesis is that the absolute-error training objective can improve MAE
relative to the saved empirical CDF lower median, whose tree splits optimized
squared error. A changed source packet makes this a joint learner and source
reconstruction comparison; it cannot identify a learner-only improvement.

The topology is fixed in `config/median-boosting-research.json`: 150 histogram
boosting iterations, learning rate .05, maximum 15 leaves/depth3, minimum leaf30,
L2=10, no early stopping, seed1702, two threads. Numeric labels use absolute
error; anytime TD uses log loss and supplies a genuine event probability.
The prior CDF engine, target contracts, role panels and training-only
`FixedDesign` transform are reused unchanged. Warm supported modeled roles use
the estimator. Cold, unknown, nonmodeled and insufficient training rows retain
the inherited trained role/global full-support prior median or binary
probability. Single-class binary training explicitly uses that prior.

The numeric output is named `point`. It is an MAE-objective heuristic, with
predeclared `max(0, prediction)` for counts and no clamp on signed yards.
Fractional count points remain fractional. Numeric output has no forecast mean,
integer-law median, CDF, variance, quantile, CRPS or probability claim.
Binary probabilities are not clipped; infinite natural log losses retain an
explicit `positive_infinity` state, finite sum/count and infinite count.

The finite plan has up to 66 historical fits for2022/2023/2024 and22 original
website Week6 fits. All twelve targets and both panels are explicit; exact PPR
remains blocked. Historical primary comparisons retain all offered eligible
pairs against saved same-panel CDF medians/probabilities after concatenating
the2022–2024 rows; annual MAEs are not averaged. Annual cells, saved pooled/recent
points, primary-role comparisons and context versus base are secondary. The
W6 primary comparator is the literal original website only. The fixed primary
summary retains48 slots, including4 blocked PPR slots. The96 planned annual/W6
attempt slots include8 blocked PPR slots and at most88 fits. Week
and game intervals reuse the prior fixed500-draw evaluator and are nominal95%,
unadjusted and descriptive. No W6 intervals are produced. The only website
blend is the predeclared secondary fixed50/50 website/candidate point or genuine
event probability; there is no weight search or extra fit.

A source change requires an approved receipt binding exact final inputs and
`source_packet_mode=joint_learner_source_reconstruction`. The separate strict
comparison binder preserves both full populations in private outer audits.
Common identities must match team/opponent/position/kickoff and any recorded
cutoff. Unrecorded saved pooled/recent cutoffs remain unauthenticated.
All paired losses use the new source-qualified outcome. Retained old actuals,
participation, points and source hashes remain explicit. Both-finite conflicting
actuals and proved participation contradictions are quarantined; changed
qualification and missingness remain separate lineage differences. Unmatched
rows and every exclusion remain visible, with no silent denominator change.

The source review and final root/separate read-only reviewer seal are mandatory
technical launch gates. The create-only runner enforces1200 wall/1800 CPU
seconds,60 wall/90 CPU per fit,2GiB process-group RSS and512MiB private output,
with180 wall seconds reserved for reporting. The fit budget may be reduced
before launch. Every attempted failure is consumed and retained. All models and
forecasts across every period freeze before exactly one outcome/report phase.
The runner never appends the integrator's ledger or changes an operational
default, website, recorder or scheduler.

```python
from nfl_lab.median_boosting import MedianBoostingModel, prediction_rows
model = MedianBoostingModel.fit(qualified_old_rows, category, "base")
frozen_points = prediction_rows(model, qualified_query_rows)
```

```sh
python -m nfl_lab.median_boosting_campaign run SEALED_REGISTRY.json NEW_OUTPUT
```

All periods have already been exposed. A calculation-order freeze does not
establish pregame issuance, independent confirmation or qualification. No
replacement or promotion follows from this experiment. Raw rows and fitted
artifacts remain private; only aggregate evidence is suitable for publication.
