# Receiving-targets frozen CDF pilot — protocol v1

Experiment: `e:opportunity-four-targets-frozen-v1-20261029`  
Run: `r:opportunity-four-targets-frozen-v1-20261029`

**Prepared, not executed.** No new target fit, forecast, accuracy result, pregame capture or deployment is claimed by this protocol. The exact machine-readable scientific definition is [the scientific configuration](../../config/category-topfive-targets-frozen-v1.science.json).

## Question and fixed comparison

Does the existing 32-tree empirical leaf-CDF, newly trained to predict provider-reported receiving targets, have lower point-display MAE than a recent-eight-target mean on the same frozen 2026 player-games? The strong learner and its reception-feature representation remain unchanged; this does not test new teammate or injury information.

Fit once on eligible 2022–2025 regular-season outcomes recorded before September 1, 2026 UTC. No 2026 refits, tuning, calibration or stacking. Existing feature memory can include 2019–2021 history. This is **REC_TGT_FROZEN_PRESEASON_2022_2025**, not the completed weekly H-MULTI or history-arm experiment.

Four procedures share one fit: target CDF; its training-position geometric prior; unrounded recent-three target mean; unrounded recent-eight target mean. Recent-three/eight are two settings in one family. The CDF supplies a genuine mean, lower count median and count law; point-only means do not imply a predictive distribution. The primary comparison is CDF lower-median MAE against recent-eight mean MAE, explicitly comparing their display points. All compatible mean and median outputs are retained separately.

## Population and labels

The frozen query has 2,999 player-games across 93 regular-season games in 2026 Weeks 1–6. Primary RB/WR/TE coverage is 2,458 planned rows, with 1,855 qualified labels, including 369 played zeros; 603 remain unknown. All original queries remain; nonprimary coverage is separate. Week 7 remains in the intended scope with 14 games lacking compatible query and raw target sources. This does not claim complete Weeks 1–7 evidence.

Labels are provider weekly `targets`, not receptions or a betting line. Exact game/player/season/week/team/opponent joins are required. Played zero needs an explicit recorded zero plus a positive physical playing witness. Missing rows and zero-only rows without playing evidence remain unknown. Six raw rows missing player identity are quarantined by metadata before numerical projection, with originals retained. Six source/query position differences remain in the frozen query cohort.

The original seven-day availability reconstruction remains unchanged. This is exposed current-vintage reconstruction, not genuine saved pregame evidence. Current public aggregation code counts stat ID 115; the exact historical builder and nullified/two-point credit exceptions remain unverified. The source qualification supports a provider-field research comparison, not full operational source admission.

## Scoring and evidence

Primary: MAE in targets. Also report MSE/RMSE, bias, p90/p95 absolute errors, strict error <1 and inclusive error <=1. Integer exact counts apply only to the registered lower median; means are never rounded to inflate that rate. Full-law CRPS and log loss are secondary; positive infinite losses and their full denominator remain.

Prespecified paired CDF-median versus recent-eight-mean differences use game and week clusters, 500 bootstrap draws, seed 1703, and at least eight clusters. Six weeks do not support an admitted week interval. Report full planned, predicted, scored, fallback, unknown and missing-source coverage, each week and pooled Weeks 1–6. There is no target market, EV-policy or website-relative result without an authentic matching product.

## Once-only execution and reproduction

The portable [runner](../../tools/category_topfive_targets_frozen_v1_run.py), [product helper](../../nfl_lab/category_topfive_targets_product_v1.py) and [label helper](../../nfl_lab/category_topfive_target_labels_v2.py) receive restricted bindings only through an approved private sealed plan. That plan is restored through the established owner-controlled private evidence route for this run; raw sources, rows, fitted artifacts, storage destinations and credentials are not public.

`python -B tools/category_topfive_targets_frozen_v1_run.py --plan <approved-private-sealed-plan.json> --sha256 <exact-plan-sha256> --go <root-go.json>`

Before fitting, the runner requires independent source review, immutable public-protocol readback proof, exact source/environment bindings, the root sealed GO and a closed previous managed writer. Budget: one 32-tree fit, 180 CPU seconds, 270 wall seconds, 1 GiB RSS, 16 MiB retained/32 MiB peak private bytes, three managed writes, no HTTP or automatic retry. All four procedures attempt all queries. Model, training/query projections and 11,996 expected forecast rows are durably frozen and exactly read back before outcome projection in the scoring worker. Outcomes already used in source qualification are exposed development evidence. Forecast values cannot change during grading. Every terminal failure consumes its allocation and is preserved.

QL1's label-empty-query finding, QL2's identity failure, the identity diagnostic, successful QL3, source GET failures and fictional checks remain separate preparation records. They are not predictive fits or accuracy results. Prior auxiliary target work retains its original identity and reproduction limitations.

No target product is operationally admitted, selected for live use or deployed. Source-credit qualification, current-source/future wrapper, private restoration, consumer and owner release checks remain separate dependencies. The website has no existing target incumbent; reception lines cannot substitute for target offers.
