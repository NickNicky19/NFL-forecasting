# Same-chart CDF comparison, completed

`next-checkpoint-chart-cdf-control-v1` completed one new NFL predictive fit and
one grading run. It supplies a stronger same-chart comparison for the retained
HGB pilot. The original HGB study, its 18.07% improvement over a position
constant, and all original failures remain unchanged.

## Decision

The CDF median has the lowest observed chart-point MAE in this matched panel:
**4.6794 points versus HGB's 4.7020**, a **0.48%** reduction. This is a small
observed lead. Its game-cluster interval includes no improvement, and its bias,
p95 error and within-one-point rate are worse. It has not established durable
superiority over HGB.

The CDF also supplies a valid mean and full distribution. These are separate
products. It is a research candidate, not a selected live replacement, an old
website-PPR comparison, or a genuine Week 8 forecast. Future-query integration
and private restoration remain separate acceptance work.

## Target and fixed procedure

The target is `nick-chart-ppr-v1`, scored from the sixteen qualified chart
primitives. Signed official integer yards and count components imply
`S = Z/50` with signed integer `Z`. Each admitted label must satisfy
`abs(50*S-rint(50*S)) <= 1e-8`. Invalid labels abort rather than being rounded
into eligibility. Negative scores and the exact 0.02-point support are retained.

The unchanged leaf-CDF engine fits one 32-tree forest: depth 8, minimum leaf 30,
squared-error splits, all features, no bootstrap, random seed 1701 and two
threads. It uses the same 32 raw information fields and the same 5,589
feature-admitted 2024 rows as the HGB pilot. No new injury, news, weather or role
information was added. The law combines 95% empirical leaf mass and 5% signed
discrete-Laplace role prior. Global/position priors use all 5,589 qualified 2024
labels. The model audit and private bindings explicitly retain this population.

Cold or unknown-feature histories receive the role/global prior as a complete
law. Its exact mean and lower median retain separate identities. The prior-law
median can differ slightly from the empirical HGB fallback median; fallback
and model-only results are reported separately.

The forecast capsule, model, prior/training bindings, leaf assignments and all
query predictions were durably frozen and read back **before** conversion of
2026 actual scores for grading. Full query compatibility against the retained
HGB freeze was checked before consuming the new fit.

## Population and timing

| Population | Planned | Supported | Other states |
| --- | ---: | ---: | --- |
| 2024 training | 5,935 | 5,589 | 345 unknown participation; 1 played missing |
| 2026 Weeks 1–6 query | 2,117 | 1,954 | 163 unknown participation |

The query covers 93 regular-season games and six weeks. Supported outcomes
include 268 played-zero and 1,686 played-score rows. All 2,117 queries retain
forecasts and status records; unknown participation was not converted to zero.
There were 2,032 model outputs and 85 cold/unknown-history fallbacks, of which
78 have supported outcomes. The private scorecard has 16,936 method rows from
eight outputs on 2,117 opportunities; these are not independent NFL outcomes.

This is exposed, current-vintage historical reconstruction under the original
seven-day availability assumption. That assumption is preserved, not repaired
or called an authentic source publication time. Qualified 2025 football may
occur in the lagged 2026 inputs; the fitted target labels are from 2024. Source
roster positions do not establish a future injury/role contract. No historical
SITE predictions or market prices were invented.

## Matched point results

All rows below use the same 1,954 supported query outcomes. MAE, RMSE, bias and
p95 are in chart points. MSE is in squared chart points; bias is prediction
minus actual.

| Procedure / intended product | MAE | MSE | RMSE | Bias | p95 absolute error |
| --- | ---: | ---: | ---: | ---: | ---: |
| CDF lower median / MAE | **4.679406** | 44.040152 | 6.636275 | -1.475619 | 14.414000 |
| Retained HGB median / MAE | 4.702027 | 44.020880 | 6.634823 | -1.346343 | 14.111965 |
| CDF mean / MSE | 4.829280 | **41.610163** | **6.450594** | -0.194699 | 13.590202 |
| Position empirical median | 5.739191 | 63.807644 | 7.987969 | -1.967973 | 17.235000 |
| Global empirical median | 6.239232 | 72.399490 | 8.508789 | -2.344002 | 18.907000 |
| Position empirical mean | 6.054111 | 60.074015 | 7.750743 | 0.126567 | 15.247718 |

The CDF-median/HGB-median mean paired absolute-loss difference is -0.022621
point. The nominal 95% game-cluster interval is **[-0.069387, 0.023196]**, from
500 fixed-seed bootstrap replicates across 93 games. Six weeks are below the
registered eight-cluster minimum for a week interval; that interval is
unavailable. These five prespecified contrast intervals are exposed-development
diagnostics, not selection-adjusted future guarantees.

CDF median improves 18.47% over the position median and 25.00% over the global
median. The valid CDF mean improves MSE 30.74% over the position mean. Those
different comparators do not establish a 30.74% advantage over HGB or the site.

Adverse findings versus HGB remain visible:

- Signed bias is more negative (-1.476 versus -1.346).
- p95 error is larger (14.414 versus 14.112).
- Strict absolute error below one point occurs on 16.07%, versus HGB's 18.58%.
- Inclusive absolute error at most one point occurs on 17.50%, versus 18.58%.
- Maximum error is 36.20 points, versus 36.10.

On the 78 scored fallback rows, CDF median and HGB have identical MAE 4.111538;
the global median's fallback MSE is slightly lower than theirs. On 1,876 scored
model-only rows CDF-median MAE is 4.703017, versus HGB 4.726579. Neither slice is
used to replace the full-system result.

## Weeks retained separately

| 2026 week | Planned | Scored | CDF median MAE | HGB median MAE | CDF improvement |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 360 | 334 | 4.906647 | 4.923549 | +0.343% |
| 2 | 364 | 344 | 4.650523 | 4.715612 | +1.380% |
| 3 | 367 | 343 | 4.624315 | 4.663664 | +0.844% |
| 4 | 362 | 329 | 4.552340 | 4.578547 | +0.572% |
| 5 | 346 | 315 | 4.942921 | 4.895185 | **-0.975%** |
| 6 | 318 | 289 | 4.373979 | 4.405411 | +0.713% |

Positive improvement means `100*(control_loss-candidate_loss)/control_loss`.
Week 5 remains a loss. Role, fallback and all eight output summaries are in the
safe aggregate; original player-level evidence stays in the approved private
store.

## Proper distribution results

The full signed-lattice CDF is compared with its complete role-prior law.
HGB provides points only, so no HGB CRPS or log score is fabricated.

| Proper law / diagnostic | CDF | Role prior |
| --- | ---: | ---: |
| CRPS, chart points | **3.306214** | 4.208508 |
| Natural-log probability-mass loss | **5.925914** | 7.346689 |
| Inclusive central 80% interval coverage | 85.21% | 83.37% |
| Mean interval width, chart points | **15.170839** | 18.891812 |
| 80% interval score | **20.839417** | 29.581167 |

CRPS is 21.44% lower than the proper prior. Its paired game interval is
[-1.030955, -0.776224] chart points. There are zero infinite log-mass losses;
the evaluator preserves positive infinity if an impossible event occurs.
The 0.02 lattice gives the declared mass measure. Interval coverage and width
are diagnostics, not proof of broad calibration. There are no compatible
offered-line prices, EV selections or website probability claims in this study.

## Execution, storage and reproducibility

The exact executed plan is
`config/next-checkpoint-chart-cdf-control-v1.sealed.json` in the integrator source,
SHA256 `250f187df9ddea7fdb19173cf958f33f97c1cbd0ce0ae449e76853502c5aafd7`.
The reviewed local scientific preseal is
[`next-checkpoint-chart-cdf-control-v1.preseal.json`](../../config/next-checkpoint-chart-cdf-control-v1.preseal.json).
The runner and builder are
[`next_checkpoint_chart_cdf_run.py`](../../tools/next_checkpoint_chart_cdf_run.py)
and [`next_checkpoint_chart_cdf_build.py`](../../tools/next_checkpoint_chart_cdf_build.py).

Actual main work: one fit attempt, one completed 32-tree fit, one batch query
prediction and one grading run. Whole wrapper usage was 49.843 CPU seconds,
49.342 wall seconds and 566,157,312 bytes peak RSS. The inner completion receipt
reports 49.841939 CPU / 49.340254 wall seconds. Limits were 120 CPU / 180 wall
seconds, 768 MiB and two threads. Actual agent/model settings are UNATTESTED.

The two managed writes total 1,245,166 bytes of capsules plus 262 bytes of
charged controls: **1,245,428 bytes**, within the separately registered 4 MiB
retained / 8 MiB peak allocation. Both capsules passed exact-byte readback.
Off-host restoration is not established by local CAS readback. The writer is
closed. There was no source acquisition, network call, refit or live write.

| Retained artifact | Bytes | SHA256 |
| --- | ---: | --- |
| Frozen model/predictions capsule | 698,121 | `063ba204d555313c59c1aae18717fc6642791371da28e7455dc79234ac385925` |
| Complete grade capsule | 547,045 | `8920c866bd979a8fc26c19b2da371ae21378bd60c95e06cb3af1ece24a3b14fb` |
| Safe aggregate | 51,207 | `c91cb496940918abb380ff749f6e8e2ea853ac24bd1613749dacb4d52d88831e` |

The private model SHA256 is
`dee275647336f34b0a96fdfad0b7b349c8c1df9e83fd4ce8fa53608ff621e877`.
The private 16,936-row scorecard SHA256 is
`d43c70c2ee74017759d4f0ac27e6bb0c883b9cf77afb9a911ff10612a0e66d57`.
Do not publish raw source records, the pickle or row-level capsules in this
public report. The aggregate is
[`SAFE_AGGREGATE_CDF_CONTROL_V1.json`](SAFE_AGGREGATE_CDF_CONTROL_V1.json).

## Software failures and repair retained

Software V1 failed its strict zero-socket/child-attempt assertion before any
NFL fit. Its empty original output and failure receipt remain retained. A
separately allocated V2 diagnostic found one blocked import-time IPv6 socket
probe through an unnecessary old-helper HTTP dependency; no socket actually
executed. V2 is a diagnostic, not a passing zero-attempt test. Both allocations
remain consumed.

V3 removed only that dependency by extracting sixteen byte/AST-matching pure
helpers; the old source snapshots are retained. Independent static review
verified parity and the scientific source. The unchanged strict V3 fixture
passed with zero socket/child attempts, 1.339137 CPU seconds, 1.342423 wall
seconds and 172,822,528 bytes peak RSS. It exercised full GO admission, signed
support, lattice rejection and independent finite-sum CRPS checks, using no
NFL values, fits, model loads or managed writes. It is separate from the actual
NFL comparison above.

## Operational boundary and next action

An explicit future-query adapter and
[`contract`](../../docs/NEXT_CHECKPOINT_CHART_CDF_FUTURE_CONTRACT_V1.md) passed a
separate technical replay. Seal
`1ff5523bff566087e225d9ef056345df945448459846289b1615d76b34da185a`
authorized one trusted model load and one combined query call. All 2,117 frozen
rows reproduced their mean, lower median, p10 and p90 exactly (maximum absolute
difference zero), with matching fallback identities. Four fictional unseen
rows exercised warm/cold/unknown-clock/missing-query behavior. Model/source,
duplicate, outcome-field and equal-source-clock rejection checks passed before
inference. There were zero fits, grading runs, socket/child attempts, HTTP or
CAS writes. Actual usage was 2.176711 CPU / 1.945813 wall seconds and 239,173,632
bytes peak RSS, with 1,764 bytes of counted safe receipts. See
[`CDF_ADAPTER_REPLAY_NATIVE_V1/COMPLETE.json`](CDF_ADAPTER_REPLAY_NATIVE_V1/COMPLETE.json).

The adapter remains unadmitted to the current producer. Remaining work is a
current qualified feature/identity query, approved-producer restoration,
immutable real pregame capture, consumer tests and a policy decision through
the retained production owner. The reference replay is software verification;
it adds no new NFL outcomes or prospective evidence. This study makes no
deployment, current website-win, scientific-qualification or absolute-best
claim. Independent numerical QA is pending in this report version.
