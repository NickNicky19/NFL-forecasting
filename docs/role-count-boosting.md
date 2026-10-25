# Fixed role and count objective study

This opt-in sibling study preserves the source packet, category contracts,
base features, training clocks, preprocessing method and cold/nonmodeled role
fallbacks of the frozen absolute-error HGB study. Numeric predictions are point
heuristics. Count Poisson uses a log link and does not supply a calibrated count
distribution. Signed yards keep absolute error and anytime TD keeps log loss.

| Variant | Passing | Rush/reception targets | Anytime TD |
|---|---|---|---|
| A | Four count targets fit pooled Poisson; passing yards byte-alias old base | Two count targets fit pooled Poisson; three signed yard targets byte-alias old base | Byte-alias old base |
| B | Byte-alias A exactly because passing contracts model QB only | Fit each of the five existing modeled roles separately | Fit each of the three existing modeled roles separately |

Passing yards in A and B are exactly the frozen old HGB result. They are retained
as unchanged controls and cannot establish a new research gain. A versus old HGB
on counts changes both the objective and its link. B versus A changes role
partitioning, including training medians and vocabulary fitted per partition.

Full supported earlier training rows fit role/global priors once before
estimator partitions. The model needs 60 supported rows per estimator;
`min_samples_leaf` remains 30. Sparse roles, all-zero Poisson roles and
single-class binary roles use the original prior with an explicit reason.
Positive constant counts and constant signed yards remain valid estimator fits.

The fixed matrix has 96 packages: 48 new model packages, 40 verified byte aliases
and eight blocked exact-PPR packages. At most 136 estimator attempts can occur:
24 pooled count, 100 role-specific rushing/reception and 12 role-specific TD.
The eight PPR packages preserve 24 blocked subfit slots and never load a label
substitute. Attempts and failures are consumed without retry.

Use `python -m nfl_lab.role_boosting_campaign run SEALED_REGISTRY OUTPUT` only
after root and a separate reviewer seal the exact plan, code and source bindings.
Every new and aliased forecast freezes before the one global scoring pass.
Historical primary comparisons pool 2022–2024 eligible paired rows in the
unchanged primary roles against frozen old HGB. All-offered results and every
annual/role/team/opponent/fallback slice remain visible. Week6 compares every
original offer with literal website values and has no confidence interval.
Numeric MAE is primary; MSE/RMSE/bias/tails are secondary. TD reports Brier,
unclipped log loss and fixed reliability bins. Historical game/week intervals
use the existing 500-draw nominal descriptive evaluator.

The separate coherence output records offered-union coverage and point gaps for
completions versus attempts and direct rushing+receiving versus both component
points. Missing component offers stay missing. No sum candidate is fitted or
scored. Every period is exposed; no result qualifies a promotion or prospective
claim. The runner changes no default, website, recorder, scheduler or ledger.
