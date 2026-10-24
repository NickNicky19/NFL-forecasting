# Direct CPU booster adapter — implemented, not NFL evaluated

The [adapter](../nfl_lab/direct_boosters.py) reuses the existing training-only
`FixedDesign`, supported played-label filters, role/global priors, forecast-row
contract and frozen-row evaluator. Optional libraries are lazily imported and
their installed version must equal the caller's frozen version. A consuming
fit gate runs before estimator construction. No evaluation set or early stopping
is used. Native package installation/smokes have a separate capability budget.

## Six fixed pipelines

Each of XGBoost CPU, LightGBM and CatBoost has a small (64 trees, depth 3) and
medium (128 trees, depth 5) specification. Learning rate is .05, L2 penalty 10,
and numerical threads 2. Full native parameters and fixed seeds are returned by
`parameters`; they are not interchangeable across libraries. Native categorical
handling is not tested in this first screen: all use the same numeric design,
missing indicators and training-derived role one-hot columns.

| Support/product | Native objective | Primary development loss | Fallback |
| --- | --- | --- | --- |
| Nonnegative count mean | Poisson objective | MSE | Existing supported role/global prior **mean** |
| Signed yardage point | .5 quantile | MAE | Existing supported role/global prior median |
| Anytime event probability | Binary log loss | Brier | Existing supported role/global prior probability |

CatBoost Poisson predictions explicitly request `prediction_type=Exponent`;
raw log scores are not treated as counts. Invalid shape, nonfinite values,
negative native count means and invalid probability vectors fail without
clipping. Signed predictions remain signed. Count objectives do not supply a
calibrated Poisson predictive law. Numeric rows retain no fabricated CDF,
quantiles, spread or log masses.

The minimum modeled sample is 60 supported played rows, as in the existing
control. Single-class binary or all-zero modeled count training avoids an invalid
native fit and retains the declared role/global prior. Cold/new players and
nonmodeled roles use supported priors; missing outcomes and unknown participation
never enter training as zero. Query labels/participation are not read by inference.
Count prior means retain the shared prior's original positive mean floor; this is
a versioned fallback, not a claim that all-zero training implies nonzero events.

Artifacts contain private training bindings. `save` requires caller-supplied
quota-owned storage and writes both serialized model and manifest through it;
no direct joblib-to-file path is inherited. Partial failures stay retained.

## Evidence boundary

The accompanying tests use mocked native estimators and fictional rows only.
They test contracts, not NFL accuracy or native library compatibility. No new NFL
model fit, forecast or score is established by this adapter. A separately reviewed
numerical registration must bind the actual compatible package versions, exact
source/features/comparators, exposed chronological blocks and finite resources
before real fitting. Count challengers face the source-matched CDF's saved mean,
yardage points its median, and anytime TD its event probability. Exact PPR remains
blocked by its full label contract. Historical raw/SITE forecasts are unavailable
for that panel; they cannot be reconstructed from outcomes.
