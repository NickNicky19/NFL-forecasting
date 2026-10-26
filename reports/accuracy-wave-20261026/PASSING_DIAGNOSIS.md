# Passing forecast error diagnosis — October 26, 2026

## What was executed

This bounded diagnostic reuses authentic saved predictions and the already accepted Week 7 outcome snapshot. **No models were fitted, no new pregame predictions were generated, and no new outcomes were acquired.** It audits every retained QB opportunity and separates volume mismatch from an implied yardage-rate mismatch through explicitly postgame calculations.

All **180** original QB-category opportunities remain: **36 player-games across 13 scheduled games**, five passing categories. The identical four-arm comparison has **16 supported QBs across eight games** in each category. At least one arm has a supported label for **17** QBs. Missing raw controls on the additional player remain missing. Do not mix those denominators.

There are 71 played-nonzero category labels, 12 played-zero, 12 played-missing-statistic, 20 unknown-participation and 65 pending-final opportunities. DNP and missing fields are not converted to zero. This is one previously exposed partial week, not independent confirmation.

## Retained baseline advantage, in understandable units

Each cell uses the same 16 player-games within its category. MAE is the average absolute miss; RMSE is in the original category units and penalizes large misses more heavily. These reproduce the adverse scorecard result while adding explicit units and diagnostic context.

|Category|Current selected MAE|Saved base MAE|Saved adjusted MAE|Current RMSE|Adjusted RMSE|
|---|---:|---:|---:|---:|---:|
|Passing yards|71.000 yards|48.866 yards|47.017 yards|87.705 yards|61.174 yards|
|Passing TDs|0.883 TD|0.828 TD|0.798 TD|1.056 TD|1.019 TD|
|Completions|5.246 completions|4.568 completions|3.864 completions|6.046 completions|5.061 completions|
|Passing attempts|6.117 attempts|5.624 attempts|5.038 attempts|7.396 attempts|7.071 attempts|
|Interceptions|0.610 INT|0.556 INT|0.502 INT|0.687 INT|0.600 INT|

Passing yards retains MAE as its declared primary. Counts retain their expected-value/MSE comparisons; displaying count MAE does not turn those outputs into median forecasts. Adjusted-control reductions in count MSE are TD **6.87%**, completions **29.92%**, attempts **8.57%**, interceptions **23.62%**. The base TD control has lower MSE than adjusted: **1.029013 versus 1.038363**.

The adjusted passing-yard control has **33.78% lower MAE**, bias **-0.239 versus -4.875 yards**, and maximum miss **149.94 versus 219 yards**. Attempt bias and maximum miss worsen even though its MAE/MSE improve: adjusted bias **+1.916 versus +0.464 attempts**, maximum miss **22.45 versus 15.889**. Keep that adverse finding.

## What the workload diagnostic says

For each arm, define an implied point ratio `r = forecast_yards / forecast_attempts` when forecast attempts are positive. The identity is:

```text
forecast_yards - actual_yards
  = r * (forecast_attempts - actual_attempts)
    + (actual_attempts * r - actual_yards)
```

This is an arithmetic error decomposition. Independently estimated means and medians do not make `r` an authenticated conditional efficiency estimate. A second diagnostic substitutes actual completions into `actual_completions * forecast_yards / forecast_completions`. Neither diagnostic is a pregame predictor.

|Retained arm|Eligible QBs|Original yard MAE on those same rows|With actual attempts|With actual completions|
|---|---:|---:|---:|---:|
|Current selected / reproduced Leaf-CDF|17|67.647|46.248|40.558|
|Saved base control|16|48.866|36.215|30.859|
|Saved adjusted control — attempt diagnostic|17|47.016|34.640|N/A|
|Saved adjusted control — completion diagnostic|16|47.017|N/A|32.747|

Actual-workload substitution reduces the recorded miss for every arm. This motivates better pregame workload/conversion forecasts; it does **not** show that these lower errors are operationally attainable. The current-selected actual-attempt diagnostic also worsens underprediction: bias **-13.965 versus -5.412 yards** on the same 17 rows. The completion diagnostic has bias **-5.570**. Every substituted result includes its exact same-population original-score companion.

## Source timing and the clock bug

Current selected forecasts were issued October 24. Their retained feature capture completed **October 24 at 09:08:31 UTC** under the frozen kickoff-plus-seven-day historical reconstruction. Saved base/adjusted controls come from a board generated **October 25 at 10:15:15 UTC**. Original provider publication time remains unknown.

Therefore, the retained-baseline advantage mixes procedure and input-vintage differences. This packet does not causally assign it to the algorithm, fresh provider role information or another feature. Authentic matched future captures are needed to isolate those explanations.

An older archived feature representation had a datetime-unit bug: zero qualified warm histories became 572 of 610 after normalization. However, the existing corrected-model replay already reproduces the actual selected website values on **36 of 36 opportunities in each passing category, exactly**. Across all categories, 1,728 of 1,754 values are bit-exact and the remaining 26 differ only by roundoff, at most `1.776e-15`. **The old empty-history bug is not an explanation established for these current selected passing forecasts.** That completed acceptance is reused, not counted as new football validation.

Exact game/player/team/opponent joins, per-row issue/cutoff/model/source identities and reconstructed feature-availability clocks are retained or resolved through hash-bound original records. Unknown selected fallback state and upstream publication remain explicitly unknown.

## Strata and uncertainty

Strata were fixed before scoring: supported prior appearances, current-selected predicted attempts below/above 20, and explicitly outcome-based actual-attempt bins. Every arm shares the same pregame workload anchor and common original-score population. All 16 matched QBs have at least three source-supported prior appearances; no sparse/new-player superiority can be inferred. Verified replacement/injury-role status is unavailable in these inputs and is not invented.

One matched low-predicted-workload QB accounts for a **219-yard** selected miss versus **9.68 yards** for the adjusted control. On the other 15 matched QBs, current MAE is **61.133 versus 49.506 yards**. This diagnostic neither drops that player from the main result nor turns a one-player subgroup into a selected strategy.

For adjusted versus current passing yards, paired MAE difference is **-23.983 yards**. Descriptive leave-one-game-out differences range **[-29.194, -11.119]**. The analogous MSE sensitivity ranges for passing TDs and attempts cross zero. These are sensitivity ranges, not confidence intervals; one exposed partial week does not establish durable superiority.

## Persistence, failures and decision

Two serialization attempts exceeded the fixed 16 KiB allocation before saving a numerical body. Their consumed records, first immutable failure record, source versions and spent resources remain. The final format references unchanged original forecasts/outcomes/metadata by exact input hashes and row keys, retaining all new derived values, every opportunity and every metric panel.

Final private body: **13,906 bytes**, SHA-256 `2424acffda93eeea07d6ec05b6b4ded0b5fa878fe955a0761745e79fccc43d24`. All retained stage artifacts total **14,913 bytes**, below the unchanged **16,384-byte** allocation. The shared 512 MiB cap was not raised and nothing was deleted. Final native runtime: **8.939 CPU / 8.428 wall seconds**; all stages including failure-metadata persistence: **40.213 CPU / 38.276 wall**, within the original 45 CPU / 90 wall allocation. Peak RSS: **166,043,648 bytes**. Recomputed deterministic arithmetic adds no football observations.

Post-execution independent review: **PASS**. The separate read-only reviewer reconstructed all **180** source-keyed opportunities and **144** derived diagnostic rows, and verified **20** comparison, **30** paired, **12** postgame and **28** stratum panels, all **180** source/history/clock joins, coverage and retained bytes. It also checked these aggregate files for consistency and privacy. Review added no NFL observations. [All aggregate comparisons](PASSING_AGGREGATES.json) include the count MAE/MSE/RMSE, bias, tails, prespecified strata and paired sensitivity ranges. No player/game identities, row forecasts/outcomes or raw source bodies are published.

**Decision:** this is an executed diagnostic, not a new deployable forecasting recipe or a causal same-cutoff model comparison. Preserve the current weekly-policy decision process, investigate workload/role and fresh baseline capture, and test authentic provider-anchored corrections only with adequate earlier archived forecasts. Do not fit a flexible correction to these 16 QBs. No model, website policy, scheduler or scientific registration was changed.
