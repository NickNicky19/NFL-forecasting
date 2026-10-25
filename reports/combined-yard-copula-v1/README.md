# Cached combined-yard marginal dependence challenger

**Execution completed. Independent numerical acceptance: PASS.** No arm
advances or changes a forecast, website policy, scheduler or scientific status.

This is a narrow exposed-period test of rushing-plus-receiving yards. The
[current-vintage source comparison](../distribution-cdf-after-audit-v2/README.md)
held its97feature contract and frozen leafCDF marginal models fixed. No new base
model was fitted. Actual execution restored nine saved laws and fitted two
pooled dependence coefficients. Requested agent/model settings remain
**UNATTESTED**; the recorded forecasting engine is the existing ExtraTrees
empirical-leafCDF with original signed-support priors, StableMixtureBatch and
PCG64 draws.

## Results and population

The evaluation covers **2023–2024:14,282 offers,10,157 supported played outcomes,
544 games and36 season-week blocks**. The earlier all-category2022–2024 panel
has815 games/54 blocks and is a different cohort. The2022OOF forecasts train
2023dependence;2022+2023OOF forecasts train2024dependence. Every period was
already exposed development evidence. Source availability is reconstructed
kickoff+7days with strict label availability before the first evaluation cutoff;
no authenticated historical publication time is implied.

| All offered combined population | CRPS, lower better | Median-objective MAE, lower better |
|---|---:|---:|
| Independent sum |14.788579443636761|20.77513045190509|
| Shrunk Gaussian-copula sum |14.7915795127966|20.770306192773457|
| Direct combined leafCDF |14.788333759543123|20.75366742148272|
| CatBoost medium point only |—|20.67970571250581|

CRPS gains against the directCDF are **−0.0016613372%** and **−0.0219480660%**:
both sums lose. Their paired week/game CRPS95% intervals include zero. Both
sum medians also lose to the directCDF median. CatBoost medium has lower point
MAE than either sum; both pooled week/game intervals for candidate-minus-Cat
loss exclude zero on the positive side. CatBoost supplies a verified literal
point comparator, not a distribution or coverage comparator. The learned copula
slightly improves medianMAE versus independence but worsens CRPS; both corresponding
paired intervals include zero. No current-website, historicalSITE/R0, global
winner, confirmation, selection or deployment claim follows.

The complete [aggregate](aggregate.json) retains eight pooled/sixteen annual
all-offered contrasts and the separate eight pooled/sixteen annual RB diagnostics,
with500PCG64 whole-week/game intervals using the shared1911/1912 seeds.
[Matched aggregate control diagnostics](matched-control-diagnostics.json) retain
all annual and pooled biases, tails and coverage without individual records.

## Bias, tails, zero mass and coverage

| Pooled all-offered method | Mean bias | Median bias | Median p95 absolute error | Nominal80% coverage |
|---|---:|---:|---:|---:|
| Independent sum |0.1159981543|−6.3767844836|64|87.35847199%|
| Gaussian-copula sum |0.1159981543|−6.5602047849|64|87.88027961%|
| Direct combinedCDF |0.1402534697|−6.6719503790|64|88.24456040%|
| CatBoost medium point |—|−6.25669418|63.439765|—|

The sums' mean bias is smaller than the directCDF's, and their median biases
are less negative. Their80% coverage is closer to nominal than the directCDF,
while all three laws still overcover. Against independence, the learned copula
has a more negative median bias, wider intervals(71.4658855961 versus70.4782908339),
higher interval score(93.5422861081 versus93.4230579896), and greater overcoverage.
Below-p10/above-p90 rates are4.04647%/8.07325% for the copula and4.34183%/8.29969%
for independence, against10% nominal tails. This is mixed diagnostic evidence,
not regression on every metric.

Supported-played mean zero mass is0.1330613713/0.1347777109 versus direct0.1428240571.
Fixed push-mass diagnostics at0,20,40,60,80,100,150,200 andCDF immediately below/at
the observed integer are retained in the aggregate. Fixed-push averages use
all offered forecasts; mean zero mass uses supported played scored rows. These
denominators differ. Joint log density was not computed; no normal yard law or
probability floor was invented.

## Actual method and chronology

For each supported earlierOOF pair, **randomized discrete PIT** is
`U=F(y−1)+V×[F(y)−F(y−1)]`, with identity-seededPCG64 uniformV. It is not mid-PIT.
The sole learned coefficient is
`rho=n/(n+100)×Pearson(ndtri(Urush),ndtri(Urec))`; there is no parameter search.
The2023 fit uses1541 pairs/rho0.16147924063886;2024 uses2978/rho0.14417960651291956.

The independent arm fixesrho0. Both couplings invert the complete original
signed marginalCDFs and form4096 coherent paired sum draws per informed row.
Their empirical sum law approximates the underlying copula sum and uses the
existing empirical-mixtureCRPS. Monte Carlo adds zero NFL observations. Medians
come from each arm's own sum law; marginal medians are never added. Analytic
marginal means do add. The prior's full tail participates in inverse sampling;
finite draws do not make the empirical score an exact infinite-support convolution.

All14,282 offers remain:3978 use qualified native RB marginals and10304 use the
unchanged direct combinedCDF fallback(10198 non-RB and106 RB with unavailable
or fallback components). RB-only diagnostics cover4084 offers/2990 supported
outcomes and are separate. Unknown participation4101, played-missing24,
knownDNP0 and1673 supported zeros remain accounted for. No favorable evaluation
intersection is formed. Both coefficients and four annual forecast factors/draw
hashes freeze before evaluation scoring; scoring regeneration must match those
hashes. The2023 forecast freeze precedes using its earlierOOF labels for2024.

## Source, finite resources and retained failures

[Public registration draft](../../config/combined-yard-copula-v1.json) ·
[Law adapter](../../nfl_lab/combined_yard_copula.py) ·
[Runner](../../tools/run_cached_combined_yard.py) ·
[Supervisor](../../tools/supervise_cached_combined_yard.py) ·
[Study-local native helper](../../tools/combined_yard_native_core_env_f2.py) ·
[Fictional checks](../../tests/test_combined_yard_copula.py) ·
[Aggregate provenance](PUBLIC_PROVENANCE.json).

Actual scientific source commit:`5748e2582ea1ada38c584297a8dfe7c5b3a550c8`.
The original912-second preparation exceeded its900-second envelope and remains
failed; it was not refunded. The later libc-pin repair and missing-VECLIB native
child failure remain in the source history. The final helper is a study-local
versioned derivative: it adds only `VECLIB_MAXIMUM_THREADS=2` to the six forwarded
caps. Original c57 is preserved; the derivative has its own hash. The worker
keeps all seven strict caps, libc authentication and original process/resource guards.

The actual allocation was900CPU/1200wall seconds,2GiBRSS, two threads and64MiB
private outputs, with zeroHTTP/retries/base fits and at most two dependence fits.
Completion reports workerCPU301.683704954 seconds, wall301.59531754700583 seconds,
RSS618651648 bytes, and4644025 retained bytes at its pre-completion snapshot.
These are worker figures, not a substitute for whole-job monitor accounting.
The result contains zero new base fits,two dependence fits,nine model restores.
The actual native supervisor completed within its limits: **428.906018702 CPU
seconds and303.316425316 wall seconds**, with clean process reaping, zero HTTP
and zero retries. Its payload snapshot was4,645,789 bytes; the conservative
combined RSS bound was636,727,296 bytes. These measurement boundaries differ
from the worker's pre-completion snapshot and are retained separately.

The public metadata preparer accepts explicit private input/output locators
rather than publishing internal absolute artifact paths. That packaging-only
change is documented by old/new source hashes; executed method, runner, native
helper remain byte-identical to the actual source tree. The public test oracle
has the separately documented memory fix below; its draw count, complete
pair set, assertions and resource guards are unchanged. The public
registration is its original unactivated draft, SHA5d699f4864025cae985e327b1f7268aedbf0b3f5a655d984fbfd554a14c8b9e7.
The actual sealed activation used SHA7a286685c66ee61495c7dc9bc808e83d064dc6d8462d4fb9c04c98ce1904d777;
only activation state and seal changed, with normalized scientific body equal
to the published draft. The private seal itself is not redistributed.
It performs footer/manifest preparation only and cannot grant a numericalGO.
No private model, player/game rows, forecast factors, cache or original history
is part of this publication packet.

## Complete category status in this supplement

| Category | This wave | Prior evidence retained |
|---|---|---|
| Passing yards |Not retested; unchanged|[CorrectedV2](../distribution-cdf-after-audit-v2/README.md)|
| PassingTD |Not retested; unchanged|[CorrectedV2](../distribution-cdf-after-audit-v2/README.md)|
| Completions |Not retested; unchanged|[CorrectedV2](../distribution-cdf-after-audit-v2/README.md)|
| Passing attempts |Not retested; unchanged|[CorrectedV2](../distribution-cdf-after-audit-v2/README.md)|
| Interceptions |Not retested; unchanged|[CorrectedV2](../distribution-cdf-after-audit-v2/README.md)|
| Rushing yards |Marginal reused; target not retested|[Prior matrix](../../docs/AFTER_AUDIT_CATEGORY_METHOD_MATRIX_20261025.md)|
| Carries |Not retested; unchanged|[Prior matrix](../../docs/AFTER_AUDIT_CATEGORY_METHOD_MATRIX_20261025.md)|
| Receptions |Not retested; unchanged|[Prior matrix](../../docs/AFTER_AUDIT_CATEGORY_METHOD_MATRIX_20261025.md)|
| Receiving yards |Marginal reused; target not retested|[Prior matrix](../../docs/AFTER_AUDIT_CATEGORY_METHOD_MATRIX_20261025.md)|
| Rushing+receiving yards |Two sum couplings completed; no advance|This report|
| AnytimeTD |Not retested; unchanged|[Binary blend](../anytime-td-blend-v1/README.md)|
| Exact websitePPR |Exact label contract remains blocked|[Prior matrix](../../docs/AFTER_AUDIT_CATEGORY_METHOD_MATRIX_20261025.md)|

## NumericalQA finalization

Independent numerical acceptance **passed2,086 checks with zero mismatches**.
The reviewer authenticated46 input and136 code bindings, the saved forecasts,
scored rows, global freeze and completion; independently reproduced16 pooled
and32 annual contrasts and96 paired whole-week/game intervals; and replayed
four fixed informed samples with exact draw hashes and independently computed
empirical CRPS. Four sample replays are not a full replay of every simulated
row, and add no independent NFL observations. See
[acceptance scope](INDEPENDENT_ACCEPTANCE.md).

One final receipt utility failed with a SyntaxError and was corrected without
rerunning rows, models or scoring. That failed utility remains recorded. The
complete review elapsed517.51 seconds within its600-second envelope; metered
checker processes used3.75286 CPU seconds, while total orchestration CPU was
not independently aggregated. Software fixture success, numerical verification
and predictive improvement remain separate claims.


## Hosted acceptance failure and memory repair

The initial publication head `c5e0a218` failed hosted run40201147447, job121192390402:31 failures,1,574 passes, one skip and62 passing subtests. The31 failures were existing subgroup/participation resource checks. The new fictional CRPS oracle formed a full4096-by4096 difference matrix, raising process-lifetime peak RSS; that is consistent with the later resource-check failures. The failed run remains retained.

The public test now evaluates all16,777,216 pair terms in64-row blocks. It keeps the same4096 draws, V-statistic, assertions and resource ceilings; no forecasting code, recorded NFL law, output or score changed. A fresh combined regression passed53 tests in11.80 pytest seconds (12.3911 wrapper wall,14.060416 CPU), with child peak RSS209,899,520 bytes. The old eleven-test standalone run used442,535,936 bytes. These test scopes differ, so these figures are not a forecast runtime comparison. A fresh full hosted successor run is still required before merge. This repair adds no football evidence.
