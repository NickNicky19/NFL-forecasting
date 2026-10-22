# Public scheme and pace ablation: exposed 2023

The fixed 47-feature group worsened every primary loss versus the frozen 97-feature ridge baseline. No method is promoted or activated. This is one preregistered development comparison on already exposed outcomes, with no new validation or prospective advantage claim.

The run completed all 11 allowed fits in 17.53 seconds under two-thread limits. The anytime-TD logistic model reached its fixed 150-iteration limit; its warning and returned predictions are retained. There was no retry, hyperparameter change, additional fit or later-season outcome evaluation.

Training retained 35,601 rows from 2019–2022. Both sides retained all 9,020 offered 2023 player/game rows and scored the same 6,173 supported played outcomes per category across 285 games and 22 weeks. This is the original broad offensive-skill population, including postseason and non-QB played zeros in passing categories; these MAEs are not QB-only errors. Known DNP, unknown participation and missing statistics remain distinct.

| Target | Primary | Baseline | + public scheme | Loss increase | Paired week delta interval |
| --- | --- | ---: | ---: | ---: | --- |
| pass_yd | mae | 10.196688 | 10.672306 | 4.66% | [+0.232857, +0.853587] |
| pass_td | mae | 0.097513 | 0.103825 | 6.47% | [+0.003588, +0.009753] |
| pass_cmp | mae | 0.725921 | 0.758089 | 4.43% | [+0.011618, +0.055218] |
| pass_att | mae | 1.064518 | 1.103946 | 3.70% | [+0.012367, +0.065575] |
| pass_int | mae | 0.084933 | 0.086819 | 2.22% | [+0.000555, +0.003484] |
| rush_yd | mae | 7.930309 | 8.088598 | 2.00% | [+0.080208, +0.241330] |
| rush_att | mae | 1.339777 | 1.367259 | 2.05% | [+0.013128, +0.041359] |
| rec | mae | 1.161634 | 1.167404 | 0.50% | [-0.000479, +0.012075] |
| rec_yd | mae | 15.281329 | 15.413330 | 0.86% | [+0.064817, +0.196026] |
| rush_rec_yd | mae | 19.887712 | 20.040532 | 0.77% | [+0.093367, +0.210504] |
| anytime_td | brier | 0.132168 | 0.132484 | 0.24% | [-0.000355, +0.001074] |

Intervals are challenger minus baseline primary loss, resampling paired season/week clusters with the existing evaluator: 500 replicates, seed 20261022, nominal 99.5833% intervals under its 12-target adjustment. Configuration search and this reused development population remain exploratory; these intervals cannot authorize promotion. All RMSE, signed bias, probability scores, coverage and fallback counts remain in `summary.json`, including secondary metrics that move differently.

Public nflverse PBP supplied 99,099 play rows across 569 games in 2022–2023; 71,030 were supported competitive scrimmage plays. The source grid keeps 2,780 scheduled team games across all five read seasons, including missing source slots. Public PBP is absent for the 2019–2021 training years. In 2022, 8,246/9,108 rows have supported prior offense style; in 2023, 8,189/9,020 do. Missingness is preserved through the shared model preprocessing. Rest-date support is 9,020/9,020 development rows. Per-feature, per-season support and fallbacks are in the manifest.

The only new acquisition was the public 20,426,548-byte 2022 PBP asset. Cached 2023 PBP was reused. Source body/receipt hashes, schedule/license hashes, code/registration hashes, baseline row hashes, fitted coefficients/preprocessing and local prediction hashes are retained in `summary.json`; observed package/runtime versions and the budget marker are in `execution.json`. Raw plays and local prediction rows remain ignored and are not exported.

The features are earlier offensive/defensive dropback and neutral tendencies, shotgun/no-huddle/red-zone exposures, play volume, game-clock runoff, earlier-opponent adjustment, schedule-derived rest, lagged observed coach changes and earlier same-venue roof/surface context. Outcome-derived inputs require reconstructed kickoff+7-day availability strictly before cutoff, exact last-three game slots and a 60-day stale limit. Unknown source values do not become zeros or cause older-game backfilling. The target realized score/play mix, coach, roof, surface and weather do not enter their own numeric features; only scheduled stadium identity and dates select prior context.

This remains current-vintage reconstruction. Historical source publication, schedule/roster corrections and original coach/venue versions are unauthenticated. Game-clock runoff is a public tempo proxy, not actual snap timing. Route/personnel/coverage counts, private gameplans, authentic historical weather forecasts and authenticated historical injury/news snapshots are unavailable. No numerical proxy is invented for those missing sources. The study remains inactive.

Preregistration: `b27d03aa1b8f41479ffac7c28787bf065c91680e`; implementation committed before fits: `7c44a65b6fbc6620070887fd5259fcdf788666c0`. Ten focused tests and 100 existing schema/data/model/leakage/evaluator/replay/scheduler checks passed before the run. See `docs/scheme-context-study.md` for definitions and reproducible interfaces.
