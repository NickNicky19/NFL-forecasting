# Targets to receptions: exact conditional-count feasibility

**Metadata/code preparation only. No NFL numeric projection, model load, rate fit, new forecast, scoring or CAS/HTTP operation was executed.** The completed target-CDF and recent-median studies remain unchanged. This proposal is not an execution authorization or an accuracy result.

## Exact law: no geometric-tail truncation

For one player/query, let the retained target law be

`P(T=t) = (1-a) * w_t + a * (1-q) * q^t`, for nonnegative integer t,

where the empirical weights w have finite support and sum to one, 0<=a<=1 is the prior-mixture weight, and 0<=q<1. This is the parameterization used by the count `SupportPrior` and `MixtureBatch`: normal leaf predictions use prior weight a=0.05; a registered prior fallback can use a=1.

Assume `R | T=t, I ~ Binomial(t, p(I))`, with one fixed catch-probability estimate p in [0,1] for the query information I. This is a conditional independence/exchangeability modeling assumption, not an observed football truth. It excludes unmodeled dependence between target volume/type and catch conversion after conditioning on I.

The target probability-generating function is `G_T(z)`. Independent thinning gives `G_R(z)=G_T(1-p+p*z)`. For the geometric part,

`(1-q)/(1-q*(1-p+p*z)) = (1-q')/(1-q'*z)`,

with **`q' = q*p / (1-q+q*p)`**. Therefore

`P(R=r) = (1-a) * sum_{t>=r} w_t * BinomialPMF(r;t,p) + a*(1-q')*(q')^r`.

For x>=0, with k=floor(x),

`F_R(x) = (1-a) * sum_t w_t * BinomialCDF(k;t,p) + a*(1-(q')^(k+1))`.

For x<0 the CDF is zero. Expand the finite empirical part onto r=0..M, where M is the maximum finite empirical target atom. Each Binomial component has genuinely finite support 0..t. Keep the geometric component analytically on the entire nonnegative integers. This is not a truncated or renormalized approximation to its tail.

**Endpoints:** p=0 gives delta mass at R=0; p=1 reproduces the entire target law. Explicitly implement q'=0/zero-count log mass: the existing generic prior `logpmf` expression contains `r*log(q')`, which is undefined at r=0,q'=0 without a branch. Do not call `SupportPrior.fit` on the transformed law: its training mean floor would change the mathematically required p-times-target prior mean.

The mean is exactly `E[R|I]=p(I)*E[T|I]`. Variance is `p*(1-p)*E[T] + p^2*Var(T)`. Multiplying the target mean is sufficient only for that expected-value output. The reception median is the lower 0.5 quantile of the **full integrated reception CDF**; multiplying a target median by a catch rate is not generally that median.

## Proper scores without an infinite numerical sum

The transformed finite empirical PMF plus geometric prior has the same general shape accepted by the existing `MixtureBatch`. Its analytic absolute-moment CRPS machinery can be adapted per query, preserving q'. A second exact check uses the discrete CRPS sum.

For actual nonnegative integer y, let `K=max(M,y)`. Sum `(F_R(k)-1{y<=k})^2` over k=0..K-1. The complete remaining tail from k=K onward is exactly

`a^2 * (q')^(2*(K+1)) / (1-(q')^2)`.

Thus no arbitrary yard/count grid or probability truncation is needed. Use log-sum-exp for mixture masses, preserve legitimate positive-infinite log loss and its denominator, and verify normalization, support, monotonicity, endpoint identities, moments and both CRPS calculations before NFL inference. Those checks are proposed; none was run in this metadata preparation.

## Small fixed catch-rate comparison

Freeze the target marginal across both arms. One candidate uses an earlier position-pooled catch rate p0. Another uses a player estimate with fixed strength **20 target exposures**:

`p_i = (C_i + 20*p0)/(T_i + 20)`.

C_i and T_i are earlier qualified catches and targets inside a predeclared fixed history, with unknown/DNP slots retained. The proposed initial window is the last eight eligible roster-game slots; p0 is fitted only from pre-2026 qualified pairs. The value 20 is fixed before using evaluation outcomes, not selected from a test leaderboard.

This is a **plug-in point catch probability** motivated by Beta shrinkage. It is not a Beta-binomial conditional law and does not integrate posterior catch-probability uncertainty. A later Beta-binomial experiment would require its own identity, mathematics, budget and comparison.

## Sources, controls and dependencies

Same-source retained history has `rec`, `rec_tgt`, explicit participation/source/physical-witness fields, and clocks. `data.STAT_MAP` maps provider `receptions` and `targets` to those distinct outcomes. Schema presence does not qualify actual values. Before a fit, verify canonical player/game/team/week joins, integer support, R<=T, playing evidence, missingness, T=R=0 as zero exposure, and earlier-only availability. Never create zeros from missing statistics or clip incompatible credited counts.

The strong existing ordered-reception control reports 1,849 supported outcomes out of 2,458 planned receiving queries, with six played-but-reception-missing rows and 603 unknown participants. Target labels support 1,855. Preserve that difference; do not assume the six reception values are zero. Reuse exact supported control labels unless a separately versioned repair changes both arms compatibly. No complete-route feed or full-team target denominator is needed for this single-player conditional baseline.

The ordered/base/backfield control histories are **2019–2025 REG target rows** under their inspected 2026 producer predicate. The distinct target CDF is **2022–2025 REG**. Older feature memory and the seven-day reconstruction assumption remain. [Training-history correction](TRAINING_HISTORY_CORRECTION_SOURCE.json) gives exact code/config/proof identities. Different control training histories must be disclosed; the shared-target-marginal catch-rate ablation isolates conversion more cleanly than attributing all differences against ordered CDF to one mechanism.

If a downstream learner, calibrator or combination is trained on predicted target features, it needs chronological out-of-fold upstream target predictions. The proposed conditional catch law may learn from observed earlier historical target exposure, provided inference integrates the uncertain **forecast** target law. Actual target-game target volume never enters a pregame forecast. A through-2025 target fit cannot generate purported out-of-sample training predictions for its own 2025 labels.

## Execution state

The next steps require a separate finite registered protocol, actual paired-label qualification, permitted model/source restoration, exact portable code and public readback, resource/capacity checks and root GO. Target-law replay must authenticate the retained original mean/median before transformation. Keep MAE medians, expected means/MSE, full-law CRPS/log loss, offered probabilities and price-aware decisions separate. Point gain alone does not qualify probabilities.

No authentic new pregame capture, release or website change is claimed. New candidate forecasts would be frozen through the existing owner workflow before any applicable game cutoff, with the actual website and fixed reference preserved where matching forecasts exist.
