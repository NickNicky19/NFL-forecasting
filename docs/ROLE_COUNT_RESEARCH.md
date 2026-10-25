# Role and count-loss research contract

ID: `all12-role-count-boosting-v1-20261023`. This is a bounded new research
study, with no production activation or promotion. Every retained development
and evaluation period is already exposed. It cannot provide independent
confirmation of an earlier result.

## Fixed changes and unchanged controls

The source is the exact approved NFL-only packet used by the prior HGB study.
No PFR-derived table, snap feature or old PFR-trained model is used for new
fitting or inference. Older outputs remain byte-bound comparison artifacts.
All prior experiment budgets stay spent; the new cap is 136 estimator attempts.

Arm A changes the six count targets to Poisson HGB, with its log link. Arm B
fits a separate estimator and preprocessing within each originally modeled
role. Both arms retain full-training role/global fallback priors. Count models
are point heuristics scored primarily by MAE; the training objective does not
establish a calibrated Poisson law or an accurate conditional mean.

| Target | Arm A | Arm B |
|---|---|---|
| Passing yards | Reuse prior QB HGB | Same A alias |
| Passing TDs | QB Poisson | Same A alias |
| Completions | QB Poisson | Same A alias |
| Passing attempts | QB Poisson | Same A alias |
| Interceptions thrown | QB Poisson | Same A alias |
| Rushing yards | Reuse prior pooled HGB | Role-specific signed-yard HGB |
| Rushing attempts | Pooled Poisson | Role-specific Poisson |
| Receptions | Pooled Poisson | Role-specific Poisson |
| Receiving yards | Reuse prior pooled HGB | Role-specific signed-yard HGB |
| Rushing + receiving yards | Reuse prior pooled HGB | Role-specific signed-yard HGB |
| Exact offensive PPR | Blocked: exact labels unavailable | Same blocked state |
| Anytime rushing-or-receiving TD | Reuse prior probability HGB | Role-specific probability HGB |

The unchanged passing-yard alias is not a new model, validation sample or
reproduction claim. Passing count Arm B aliases Arm A because QB is already the
only modeled role. No duplicate fit is used to inflate the search or evidence.
There are 96 target/arm/period packages: 48 new-model packages, 40 forecast
aliases and eight explicit PPR blocks. The 136 cap counts their underlying
estimator attempts, including failures, rather than counting these packages.

## Inference and failure behavior

Use the existing base feature panel and fixed HGB parameters: 150 iterations,
learning rate .05, depth 3, up to 15 leaves, minimum 30 rows per leaf, L2=10,
seed 1702 and no early stopping. Each estimator requires 60 supported training
rows. Imputation medians and role vocabulary use only that estimator's earlier
training partition; priors use the full earlier supported training set once.

All-zero count and single-class binary groups use the declared prior with a
reason. They receive no fabricated labels or optimizer fit. Constant positive
counts remain valid training data. Cold and nonmodeled roles retain their
original prior policy. Signed yardage is never floored; count outputs must be
nonnegative and binary probabilities must lie in [0,1]. Numeric predictive
distributions, over/under probabilities and push mass remain unavailable.

## Evidence, evaluation and recovery

Train on earlier seasons for 2022-2024 walk-forward evaluation and 2019-2025 for
the original W6 query. Reuse the inherited strict kickoff/availability filter,
which is reconstructed and assumes a seven-day historical label lag. Final
feature and source versions are not authenticated historical publication times.
Save and freeze all forecast packages before one global outcome-scoring phase.

Historical primary comparisons use the category's original primary roles and
the exact old HGB points. Mandatory all-offered and role views expose coverage
and non-QB zero dilution. Historical website and raw Sleeper forecasts remain
unavailable. W6 compares the literal original website/raw/simple/CDF/HGB points
on explicitly paired player-games; every missing offer and fallback remains.
MSE/RMSE, bias, tails, paired game/week dependence and binary log loss/reliability
remain visible. Historical intervals are nominal descriptive diagnostics; W6
has no inferential interval. Aliases add no new football observations.

Completion/attempt and direct combined/component coherence are separate
diagnostics on available common pairs/triples. No missing component is invented,
no output is repaired after scoring, and no combined gain is inherited.

Keep model/config/environment/source manifests and row-level results private;
publish only reviewed code, permitted aggregate results and hashes. A failed
attempt stays consumed. Restore the prior package to recover inference; no
default switch or website change is installed by this study. Frozen H3,
rec-half Weeks 7-14, original RB proposal and all adverse evidence remain intact.
