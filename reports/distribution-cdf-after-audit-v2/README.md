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

## What ran and what remains

- Fresh controls and challengers use the same corrected features, source, eligible player-games, cutoff assumptions, training-only preprocessing and earlier annual fits. All forecasts freeze before the score phase. Sparse/cold offers and fallback rows remain. Unknown participation/statistics are not scored as zero.
- The approved participation-rate mask is enforced. All **97 feature columns across 51,141 historical keys** match the approved feature view’s numeric values and missingness before fitting. Known physical-activity counts remain distinct from a probability of playing.
- 33 monotone classifiers, 30 response forests, 33 leaf-CDF controls and 18 mean-corrected COUNT_A calls ran. Three TD response aliases add no fit. The 6,793,906 expanded response cells and 1,018,230 query incidences are computational work, not extra football observations.
- Independent acceptance reconstructed all 150 annual, 50 pooled, 2,700 weekly summaries and 188 contrasts/188,000 bootstrap draws, plus 66 direct-law checks, 18 COUNT_A replays and 300 fixed subgroup summaries. **146,931 checks, zero mismatches.** Review adds no independent NFL observations.
- Observed whole-run resources: **649.754867 CPU / 370.016761 wall seconds**, conservative combined RSS **1,183,879,168 bytes**, private retained output **164,574,010 bytes**. Both original and corrected budgets/failures remain recorded.
- Exact PPR remains label-blocked. Strong cached point-control comparisons, dedicated probability calibration and the workload continuation have separate statuses in the matrix. Historical source-publication time remains reconstructed; no post-cutoff news/weather/current rankings are fabricated.
- No new model was selected, issued prospectively or deployed by this comparison. Existing production ownership, scheduler and scientific registrations remain intact. A ready challenger must pass actual future inference, source/catalog bindings, durable replay/restoration and consumer/fallback/rollback checks through the existing integrator. No new eight-week prerequisite is imposed on provisional release.

## Retained hosted failure and monitor hardening

[Hosted acceptance of public commit `848da55`](https://github.com/NickNicky19/NFL-forecasting/actions/runs/40157073703/job/121060622243) failed: one fictional normal-exit fixture returned `FAILED` instead of `COMPLETED`; 1,580 tests passed, one skipped, four warnings and 62 subtests were reported in 291.59 seconds. The failed run remains evidence. A fresh synthetic helper reproduced an ownership bug: the supervisor classified its unrelated preexisting child as a worker descendant, then killed and reaped that child.

The current supervisor refuses preexisting direct children and concurrent monitor threads before creating a receipt, changing handlers/subreaper state or launching a worker. The process fixtures now use fresh stdlib monitor interpreters, excluding pytest's children, numerical threads and lifetime memory high water from the monitor. Regression fixtures verify refusal preserves the helper's own unrelated sentinel and leaves no receipt or worker output. Resource caps and worker-descendant escape detection remain unchanged.

The completed 114-fit NFL run used the [exact archived executed supervisor](execution-source/supervisor-executed.py), SHA-256 `8503e47b07b860d10fe6c55affe5f8104bffe48dcfb293d7a961239e04b153bd`. This post-run hardening did not produce those fits. [The source inventory](SOURCE_CONTENT.json) distinguishes the archived execution source from current supervisor and test hashes. NFL model code, inputs, forecasts, aggregate scores and observed run resources retain their original identities.

## Retained affected trial

The earlier 84-call V1 run omitted the source adapter’s required unavailable-participation mask. Its numeric scores were consistent, but its source qualification failed. It is retained as an affected trial; its source/registration and aggregate hashes are in [the retained packet](retained-v1/AFFECTED_TRIAL.json). V2 restores the mask and refits every affected model and control. Earlier failures and consumed allocations were not refunded or relabeled.

Raw feeds, player-level rows/features, fitted model bodies, private locators, execution/GO receipts and the expanded internal ledger are not published. Source and aggregate integrity do not independently establish upstream truth or untouched predictive confirmation.
