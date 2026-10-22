# Archived Week 6 source-coverage variant

Separate registered zero-fit study `archive-source-coverage-v1-2026-10-22`. Registration and protocol-deviation addendum were committed in `198638a` before evaluation; producer code `90ae24a`. The single evaluation completed in 2.93 seconds with zero fits, zero prediction changes and no method selection or promotion.

The original sparse-Sleeper study and its report, predictions, trial metadata and 30-fit count are unchanged. This version supplements missing target outcomes only with cached NFLverse statistics qualified by the common grading adapter: exact Sleeper/GSIS identity, independent final ESPN game ID, kickoff, teams and canonical NFLverse player/game. It retains all archived opportunities and records every source gap. Missing Sleeper fields remain missing in the saved source columns; explicit dense NFLverse zeros are supported observations. Missing or ambiguous identities, inactive players and played rows without statistics receive no imputed zeros. Both sources have unknown publication order; numeric or known participation disagreements are quarantined. No conflicts occurred in this evaluation.

## Outcome coverage

| Target | Offered | Original supported | Expanded support | Added zeros | Unresolved |
|---|---:|---:|---:|---:|---:|
| pass_yd | 37 | 27 | 27 | 0 | 10 |
| pass_td | 37 | 23 | 27 | 4 | 10 |
| pass_cmp | 37 | 27 | 27 | 0 | 10 |
| pass_att | 37 | 27 | 27 | 0 | 10 |
| pass_int | 37 | 15 | 27 | 12 | 10 |
| rush_yd | 137 | 81 | 97 | 16 | 40 |
| rush_att | 100 | 59 | 70 | 11 | 30 |
| rec | 359 | 180 | 258 | 78 | 101 |
| rec_yd | 359 | 178 | 258 | 80 | 101 |
| rush_rec_yd | 259 | 47 | 192 | 42 | 67 |

Support increased from 664 to 1,010 of 1,399 numeric category opportunities: 346 added outcomes, including 243 explicit zeros. The remaining 389 opportunities remain unscored. Combined yards also gains 103 nonzero outcomes where one original component field was missing. Passing interceptions now include 12 qualified zero-interception outcomes, expanding from 15 to 27; this directly addresses the sparse-positive-only subset in the original report. Source-gap counts are retained by target in the JSON report.

## Same-actual forecast comparison

The table uses identical supported player/game outcomes and finite saved forecasts across all five methods. Pairwise website comparisons retain larger populations where raw forecasts are missing. The fixed selected algorithms and all forecasts are reused exactly; no current artifact or future-trained model is used.

| Target | Matched n | Website MAE | Raw MAE | Recent MAE | Pooled MAE | Selected MAE |
|---|---:|---:|---:|---:|---:|---:|
| pass_yd | 27 | 56.6230 | 51.4470 | 46.4646 | 47.9565 | 50.9528 |
| pass_td | 27 | 0.8444 | 0.8141 | 0.7864 | 0.7558 | 0.7751 |
| pass_cmp | 27 | 4.5637 | 4.6030 | 4.9822 | 4.9037 | 4.6174 |
| pass_att | 27 | 7.1459 | 7.0941 | 7.5026 | 7.3371 | 7.2767 |
| pass_int | 27 | 0.6637 | 0.6404 | 0.6051 | 0.6184 | 0.5934 |
| rush_yd | 95 | 16.7033 | 16.4528 | 17.1235 | 16.3591 | 15.8922 |
| rush_att | 68 | 3.4676 | 3.3121 | 4.4800 | 4.2094 | 3.8854 |
| rec | 249 | 1.3003 | 1.2969 | 1.4800 | 1.4611 | 1.3489 |
| rec_yd | 249 | 15.6145 | 15.4837 | 18.5760 | 18.2021 | 16.7417 |
| rush_rec_yd | 187 | 20.0701 | 19.8159 | 24.1146 | 23.6712 | 21.9140 |

On pairwise website support, selected MAE is lower in four categories and higher in six. Receptions changes from a lower selected MAE on the original sparse subset (1.4472 versus website 1.4954, n=180) to a higher selected MAE with expanded support (1.3170 versus 1.2629, n=258). Receiving-yard selected MAE is 16.3491 versus website 15.1133 on 258, and combined-yard selected MAE is 21.4713 versus 19.6018 on 192. Their descriptive game-cluster MAE-difference intervals are [0.0056, 0.1091] for receptions, [0.7185, 1.7583] for receiving yards and [0.7990, 2.9765] for combined yards. These intervals do not provide prospective confirmation or multiplicity-adjusted method qualification.

Passing-yard support and results are unchanged: n=27 across 13 games, selected MAE 50.9528 versus website 56.6230, RMSE 63.6188 versus 73.7983. Signed bias worsens from -19.0815 to -22.9350. Recent (46.4646) and pooled (47.9565) controls still have lower passing-yard MAE than the selected tree. No method is newly selected on these results.

## Limits and preservation

This is one already-exposed week using current reconstructed source vintage, not authenticated historical source availability or independent future confirmation. The original training used the common fixed archive cutoff and assumed seven-day label availability; this zero-fit outcome variant changes neither training nor predictions. All paired week intervals remain unavailable under the existing eight-week minimum; the 500-replicate game bootstrap is descriptive. Coverage expansion does not prove complete population coverage or calibrated count incidence.

The [original cold-context deviation](../archive-lab-week6-v1/protocol-deviation.json) carries forward: 13 cold category rows comprise three player-games, and nine numeric selected tree/ridge forecasts used fitted context inference rather than promised pure priors. Recent/pooled used priors on those nine rows. No retrospective forecast repair or qualification is claimed.

All 9,839 saved method rows remain present. Exact PPR lab outcomes remain unsupported; archived anytime probabilities remain unbound. Signed yards and integer count support are preserved. There were no refits, tuning sensitivities, raw-source redistribution, Week 8+ outcome queries, website changes, frozen reception experiment changes or promotion. The original pooled-YPA executable was not reproduced.

The separate aggregate report retains all 50 numeric target/method summaries, 60 strict same-actual pairwise comparisons, five-method common metrics, source hashes and all outcome exclusions. New row-level outcomes and forecast copies remain local and ignored. The execution receipt records original and derived artifact hashes and replay checks.
