# Corrected-source distribution comparisons — October 25, 2026

**Completed:** 114 fit calls, 150 frozen forecast files and 150 scored files, with independent numerical acceptance. This is exposed 2022–2024 REG research over 815 games and 54 season-week blocks. Category rows overlap. Original historical SITE/raw/R0 forecasts are unavailable; these are lab-relative comparisons.

[All numerical results](aggregate-report.json) · [Source, coverage and decisions](PUBLIC_RESULT.json) · [Environment](ENVIRONMENT.json) · [Source content hashes](SOURCE_CONTENT.json) · [All twelve categories × methods](../../docs/AFTER_AUDIT_CATEGORY_METHOD_MATRIX_20261025.md)

## Per-category results

Positive percentages mean lower primary loss against the **same-row freshly fitted leaf-CDF**, never higher hit rate. Numeric primary is CRPS; anytime TD primary is Brier. Median MAE and mean MSE/bias/tails are separately retained in the aggregate.

| Target | Resolved / offered | Monotone CDF primary change | CDF-response primary change | Decision |
|---|---:|---:|---:|---|
| pass_yd | 1,960 / 4,091 | -2.8587% | +0.1231% | Retain references |
| pass_td | 1,960 / 4,091 | -0.9657% | +0.3058% | Retain references |
| pass_cmp | 1,960 / 4,091 | -2.5005% | -0.0879% | Retain references |
| pass_att | 1,960 / 4,091 | -1.9766% | +0.1920% | Retain references |
| pass_int | 1,960 / 4,091 | -0.6944% | -0.0097% | Retain references |
| rush_yd | 4,558 / 6,235 | -6.5984% | +0.0522% | Retain references |
| rush_att | 4,558 / 6,235 | -2.2745% | +0.0401% | Retain references |
| rec | 15,251 / 21,504 | -1.2373% | +0.1392% | Retain references |
| rec_yd | 15,251 / 21,504 | -2.6689% | +0.0631% | Retain references |
| rush_rec_yd | 15,251 / 21,504 | -4.1827% | +0.1287% | Exposed research lead; retain live incumbent |
| fantasy_ppr | 0 | Blocked | Blocked | Exact label contract required |
| anytime_td | 15,251 / 21,504 | -0.1825% | 0.0000% (unchanged alias) | Retain references |

The monotone model loses all eleven primary comparisons. The response forest improves eight of ten numeric CRPS values, loses completions and interceptions, and reuses the unchanged TD control. It is a weighted fixed-grid CDF-response split approximation; **the exact DRF/MMD library remains untested**.

## Combined-yard lead and adverse findings

Combined-yard CRPS falls **14.9464347 → 14.9271937 (+0.128733%)** on 15,251 supported rows. Median MAE is **21.0257032 → 21.0094420**; median-p95 absolute error remains 64 yards. Absolute mean bias decreases **0.398512 → 0.355910**. The separately reported mean-point p95 slightly worsens **59.92959 → 59.97417**.

The descriptive paired 95% week interval for candidate-minus-CDF CRPS is **[−0.0333934, −0.0053012]**; the game interval is **[−0.0340844, −0.0047780]**. These are unadjusted, exposed-development intervals. Annual primary gains are **2022 −0.02365%, 2023 +0.13569%, 2024 +0.27975%**; the first year worsens. Combined yards alone meets this study’s strict primary/coverage/absolute-mean-bias/median-p95 rules against both CDF and pooled role-prior controls. That is a research lead, not independent confirmation, scientific qualification or a website win.

Rush-attempt CRPS improves slightly versus CDF but absolute mean bias worsens against the prior control. Other response gains fail a declared bias or tail gate. No gate was relaxed after results. A valid marginal law does not establish calibration or a coherent joint simulator; combined yards was scored directly.

## Cached point-control supplement

The separately registered [cached report](point-control-supplement/README.md)
completed **132 pooled comparisons and 396 annual diagnostics**, with zero new
training, model decoding or inference. All six fixed direct settings remain in
all eleven supported categories; the separately recovered XGBoost binary
procedures are named explicitly. Each comparison verifies original method,
annual year, primary-role keys, cutoffs, labels and identical finite masks.
All have three annual cells and full offered-forecast coverage. Count mean MSE,
yardage median-objective MAE and event Brier remain separate products.

Monotone loses to the lowest-loss direct setting in all eleven categories.
CDF-response is lower in seven, but is below every applicable member of the
named six-direct/fresh-CDF/corrected-mean-Count-A set only for **passing TD,
passing attempts and thrown interceptions**. Older published correction
summaries supply still stronger point references for two of those: passing-TD
context MSE **1.06235040** versus response **1.06197450** (about **0.0354%** lower),
and passing-attempt intercept MSE **114.17545158** versus response
**113.90073106** (about **0.2406%** lower). These are lowest observed values within
specifically named references, not globally best values. The older-correction
addition uses public summaries only; exact older forecast/source comparability
is not authenticated for a new paired test. Most paired intervals cross zero;
passing-TD absolute bias is worse than its strongest direct setting.

Combined yards remains this study's distribution research lead, while
**CatBoost medium point MAE 20.9839251 is lower than response-law median MAE
21.0094420**. CRPS gains do not establish a gain against stronger point forecasts.
The [full comparison table](point-control-supplement/all-132-point-contrasts.csv)
retains losses, bias, tails, both uncertainty views and coverage. The failed V1
cached-report startup remains retained with zero comparisons and no refund.

This is a report-only supplement with source contracts and hashes. The public
package lacks private row-level source/features, forecasts/outcomes and annual
artifacts, so it cannot independently reproduce the original paired scoring.
No entrant, selected, deployed or live-verified candidate follows. Exact annual
laws exist privately; current-source/artifact qualification, future-query
inference, replay, restoration and consumer/fallback acceptance remain with the
incumbent owner. R0, scheduler, visible deployment sequence and original
registrations are unchanged. There is no inherited eight-week prerequisite for
the provisional track; these are operational dependencies.

Lab PR3 has since merged the same count fallback semantics (stored `prior.mean`
for fallback points; warm predictions unchanged). The executed numerical recipe
remains `63e070241396feb9c62fb389ff5cb4f9c74ab1dc`; later operational requalification
and recovery are distinct from this execution source.

## Separate completed anytime-TD calibration

The [fixed calibration comparison](../anytime-calibration-v1/README.md) completed
**16 calibrator fits and zero base refits**, with independent acceptance
(**168,946 checks, zero mismatches**). Its evaluation is **2023–2024 only:
10,157 supported outcomes / 14,282 offers**, not the three-year V2 population.
All eight base/method combinations worsen pooled Brier versus both unchanged
bases: CatBoost medium **0.140820746**, fresh CDF **0.141021013**. Four fixed
recipes were tested on each base: intercept shift, constrained Platt, constrained
beta and increasing isotonic. Fresh-CDF isotonic retains two genuine infinite
2023 log losses. No clipping, row deletion or calibration lead follows.
The linked packet includes exact calibrator source, the historical prepared
design and explicitly curated fictional checks; private controllers and cached
row-level inputs are excluded. These 16 fits are separate from the original
114-call distribution study.

## What ran and what remains

- Fresh controls and challengers use the same corrected features, source, eligible player-games, cutoff assumptions, training-only preprocessing and earlier annual fits. All forecasts freeze before the score phase. Sparse/cold offers and fallback rows remain. Unknown participation/statistics are not scored as zero.
- The approved participation-rate mask is enforced. All **97 feature columns across 51,141 historical keys** match the approved feature view’s numeric values and missingness before fitting. Known physical-activity counts remain distinct from a probability of playing.
- 33 monotone classifiers, 30 response forests, 33 leaf-CDF controls and 18 mean-corrected COUNT_A calls ran. Three TD response aliases add no fit. The 6,793,906 expanded response cells and 1,018,230 query incidences are computational work, not extra football observations.
- Independent acceptance reconstructed all 150 annual, 50 pooled, 2,700 weekly summaries and 188 contrasts/188,000 bootstrap draws, plus 66 direct-law checks, 18 COUNT_A replays and 300 fixed subgroup summaries. **146,931 checks, zero mismatches.** Review adds no independent NFL observations.
- Observed whole-run resources: **649.754867 CPU / 370.016761 wall seconds**, conservative combined RSS **1,183,879,168 bytes**, private retained output **164,574,010 bytes**. Both original and corrected budgets/failures remain recorded.
- Exact PPR remains label-blocked. The cached point-control report is complete as linked above; dedicated probability calibration is complete as linked above, while the workload continuation retains its separate matrix status. Historical source-publication time remains reconstructed; no post-cutoff news/weather/current rankings are fabricated.
- No new model was selected, issued prospectively or deployed by this comparison. Existing production ownership, scheduler and scientific registrations remain intact. A ready challenger must pass actual future inference, source/catalog bindings, durable replay/restoration and consumer/fallback/rollback checks through the existing integrator. No new eight-week prerequisite is imposed on provisional release.

## Retained hosted failure and monitor hardening

[Hosted acceptance of public commit `848da55`](https://github.com/NickNicky19/NFL-forecasting/actions/runs/40157073703/job/121060622243) failed: one fictional normal-exit fixture returned `FAILED` instead of `COMPLETED`; 1,580 tests passed, one skipped, four warnings and 62 subtests were reported in 291.59 seconds. The failed run remains evidence. A fresh synthetic helper reproduced an ownership bug: the supervisor classified its unrelated preexisting child as a worker descendant, then killed and reaped that child.

The current supervisor refuses preexisting direct children and concurrent monitor threads before creating a receipt, changing handlers/subreaper state or launching a worker. The process fixtures now use fresh stdlib monitor interpreters, excluding pytest's children, numerical threads and lifetime memory high water from the monitor. Regression fixtures verify refusal preserves the helper's own unrelated sentinel and leaves no receipt or worker output. Resource caps and worker-descendant escape detection remain unchanged.

Hosted CI for exact public head `c57e6f1` subsequently passed **1,583 tests and
62 subtests, one skipped**, in 196.88 seconds ([run 40158854912](https://github.com/NickNicky19/NFL-forecasting/actions/runs/40158854912)).
That acceptance covers that exact head; the later reporting/calibration-source
supplement has its own subsequent normal CI, and is not covered by this result.

The completed 114-fit NFL run used the [exact archived executed supervisor](execution-source/supervisor-executed.py), SHA-256 `8503e47b07b860d10fe6c55affe5f8104bffe48dcfb293d7a961239e04b153bd`. This post-run hardening did not produce those fits. [The source inventory](SOURCE_CONTENT.json) distinguishes the archived execution source from current supervisor and test hashes. NFL model code, inputs, forecasts, aggregate scores and observed run resources retain their original identities.

## Retained affected trial

The earlier 84-call V1 run omitted the source adapter’s required unavailable-participation mask. Its numeric scores were consistent, but its source qualification failed. It is retained as an affected trial; its source/registration and aggregate hashes are in [the retained packet](retained-v1/AFFECTED_TRIAL.json). V2 restores the mask and refits every affected model and control. Earlier failures and consumed allocations were not refunded or relabeled.

Raw feeds, player-level rows/features, fitted model bodies, private locators, execution/GO receipts and the expanded internal ledger are not published. Source and aggregate integrity do not independently establish upstream truth or untouched predictive confirmation.
