# Historical market comparison: completed checkpoint — October 28, 2026

## What actually finished

The four supplied archives were authenticated and retained privately. **2025 is excluded from all new training, features, labels, calibration and model lineage.** The 2026 market archive covers Weeks 1–5 only. The missing old combined ZIP and optional workbook are not prerequisites.

The completed run reused retained CDF models, made **34,759 unique player-game-target queries**, and froze **92,445 book-threshold forecasts** before the outer scoring step. It fitted **144 small earlier-only correction/calibration estimates**, with **zero new base CDF fits**. The original offered pool has 99,388 book-offer incidences; 6,943 strict context abstentions are retained. Repeated offers are not additional football observations.

The private readable scorecard covers **62,576 matched evaluation offer rows**, including predicted numbers, actual statistics, errors, probabilities, selected offers and assumed settlement. Full original opportunities and abstentions remain in the main immutable forecast package. The readable CSV is not claimed to cover the entire original pool.

## Plain answers

- **Did market information improve the statistic forecast?** Yes, descriptively: hybrid H lowers its declared primary point loss versus F in nine of ten numeric targets in both 2024 and 2026. The independent market or offering-book line heuristic often has still lower loss. In 2026, F is an older 2024 model trained through 2023 to honor the 2025 exclusion. These are not measured wins over the current website.
- **Did it improve prop probabilities?** Results are mixed. Calibration and shrinkage explain much of the gain; H does not consistently beat the calibrated football or market controls. The 2026 passing-attempt probability worsens versus F, and the common passing-yards probability sample is only 12 player-games.
- **Did price-based selection improve paper decisions?** No durable improvement is established. All five policies lose known units in 2024; three have positive known units in the smaller 2026 sample. Quote timing and actual book settlement rules are unqualified, and unknown selected outcomes remain ungraded. These are hypothetical results, not authenticated profit or actual website-ranking gains.

## Twelve-category decision matrix — 2026 Weeks 1–5

F is football-only; FC applies the same correction without market input; M uses other books excluding the offering book; H adds that independent market input; L uses the offering-book line as a point heuristic. The table reports the same common rows. Count primary loss is MSE; yard primary loss is MAE. The separate MAE column is in the original units. Positive percentages mean lower primary loss.

| Category | Matched n / games / weeks | F → H MAE | H primary loss improvement vs F | Lowest observed primary loss arm | Release decision |
|---|---:|---:|---:|---|---|
| Passing yards | 81 / 46 / 5 | 56.037 → 53.418 | +4.67% (MAE) | H | Retain R0; no new selection |
| Passing TD | 76 / 44 / 5 | 0.962 → 0.961 | +4.48% (MSE) | H | Retain R0; no new selection |
| Completions | 79 / 46 / 5 | 4.594 → 4.268 | +6.41% (MSE) | M | Retain R0; no new selection |
| Passing attempts | 79 / 46 / 5 | 6.239 → 5.885 | +6.38% (MSE) | L (line heuristic) | Retain R0; no new selection |
| Interceptions | 77 / 44 / 5 | 0.604 → 0.600 | -0.37% (MSE) | F | Retain R0; no new selection |
| Rushing yards | 153 / 48 / 5 | 23.137 → 22.327 | +3.50% (MAE) | M | Retain R0; no new selection |
| Carries | 101 / 45 / 5 | 4.543 → 3.945 | +26.05% (MSE) | L (line heuristic) | Retain R0; no new selection |
| Receptions | 461 / 48 / 5 | 1.788 → 1.609 | +20.39% (MSE) | L (line heuristic) | Retain R0; no new selection |
| Receiving yards | 482 / 48 / 5 | 23.222 → 21.734 | +6.41% (MAE) | M | Retain R0; no new selection |
| Combined yards | 119 / 47 / 5 | 30.168 → 28.701 | +4.86% (MAE) | M | Retain R0; no new selection |
| Anytime rush/receive TD | 829 / 62 / 5, football-only | N/A; Brier 0.155491 | No matched market gain | F = FC; FS slightly worse | Retain R0; one-sided quotes do not identify M/H |
| Exact website PPR | No qualified exact labels | N/A | N/A | No supported winner | Retain existing reference; label-blocked |

A lower count MSE need not mean lower MAE; interceptions demonstrate the distinction. These corrections are empirical point procedures, not complete new predictive laws. The 2026 paired whole-week intervals are unavailable with only five weeks; nominal game intervals and separate 2024 results are in the full report. Bias and close-error diagnostics are retained; first-wave p90/p95/max-error summaries were not computed.

[Full 2024 and 2026 tables, biases, probability scores and uncertainty](../historical-market-comparison-no2025-v3/PUBLIC_RESULTS.md) · [Point/probability aggregate data](../historical-market-comparison-no2025-v3/PUBLIC_METRICS.json)

## Frozen paper-policy comparison

One hypothetical unit per selected offer, maximum five per week/category, fixed eligibility and ties; no picks were regenerated. Gap is a laboratory F projection-gap proxy, **not the historical website Top Overs/Unders**. All policy results below use their own selected sets; different hit rates are not paired accuracy comparisons. Unknown stakes are excluded from known-settled ROI and retained in coverage. No selected push or DNP void occurred in these actual packets.

| Season | Policy | W / L / unknown | Known net units | Known-settled ROI | Selected / common pool |
|---|---|---:|---:|---:|---:|
| 2024 | footballEV | 420 / 450 / 21 | -45.646 | -5.25% | 891 / 9543 |
| 2024 | hybridEV | 226 / 332 / 23 | -71.368 | -12.79% | 581 / 9543 |
| 2024 | independentmarketEV | 73 / 113 / 5 | -32.074 | -17.24% | 191 / 9543 |
| 2024 | probabilityfirst | 264 / 293 / 24 | -32.062 | -5.76% | 581 / 9543 |
| 2024 | projectiongap | 436 / 411 / 11 | -44.452 | -5.25% | 858 / 9543 |
| 2026 | footballEV | 97 / 100 / 2 | -4.273 | -2.17% | 199 / 1048 |
| 2026 | hybridEV | 56 / 62 / 4 | +1.980 | +1.68% | 122 / 1048 |
| 2026 | independentmarketEV | 28 / 24 / 3 | +6.284 | +12.08% | 55 / 1048 |
| 2026 | probabilityfirst | 61 / 61 / 5 | +3.216 | +2.64% | 127 / 1048 |
| 2026 | projectiongap | 96 / 95 / 4 | -8.172 | -4.28% | 195 / 1048 |

These sums combine categories descriptively; no pooled interval was computed. Private per-category and per-week records preserve all negative weeks, denominators, drawdowns and the original game/week uncertainty. F/H/M choose different counts and price ranges, so the sums do not establish a like-for-like ranking winner. [Permitted aggregate paper results](PAPER_PUBLIC_RESULTS.json).

## Evidence, storage and deployment

Independent numeric review checked the original frozen predictions, correction applications, matched metrics and paired intervals; this is arithmetic assurance on the same NFL evidence, not new validation games. A separate composite paper check completed its aggregate/bootstrap assertions and then verified all 62,576 CSV records by immutable offer keys, including numeric values, errors and frozen selection fields. Three earlier checker failures remain failed: physical-row-order equality, index-sensitive Series equality and a new categorical display-sort assumption. Their exact programs and consoles are retained; the final value checker changes no forecast, pick, grade or scientific metric. [Executed CSV verification receipt](PAPER_CSV_QA_V4_STDOUT.json). Original source memory failures, main context/duplicate-query failures and the first paper CPU/write failure remain failed. Technical continuations received separately recorded budgets. The successful paper postprocess made no new fits, probabilities or selections.

The new private allocation is 256 MiB; both old 512 MiB caps remain unchanged. Uploaded originals, duplicate private copies, all failures, receipts and peak writes are accounted for. A fresh process verified 11 CAS references and all 65 ZIP members, with all seven control hashes unchanged. Accounted new-allocation usage is 76,554,615 / 268,435,456 bytes, including uploaded originals and the full metadata reserve; global usage is 686,853,951 / 1,342,177,280 bytes. No constructor, managed write, NFL table decode, model fit or scoring occurred in that check. [Readback and capacity evidence](STORAGE_READBACK_PUBLIC_V1.json). Off-host restoration of this research packet remains **unproven**.

**No new model, probability component, ranking or scheduler was deployed in this wave.** The live readback at 2026-10-28T03:57:50Z returned `DISABLED_USE_R0`, with zero selected or frozen selected rows. Served payload SHA256: `275d356379c90e38ed9dd4d6fc2863c955437b18bb0c70ecbf2533e5bacda9ae`. Website main inspected: `e336bf7a68c32267c3c3eec48892aeadcd03a90e`; PR #10 remained open. A passing research comparison is not live website consumption.

## Concrete continuation through the existing owner

1. All numeric categories: capture current R0, credible football challengers and compatible current offers at the same real pregame cutoff; do not use this stale archive as a live feed. Then compare the intended point and probability products independently.
2. Passing TD/interceptions and sparse workloads: continue independent participation and supported zero qualification; unknown participation stays unknown. Retain the mixed/loss findings.
3. Anytime TD: a separately registered football-only Yes-price paper comparison remains executable without a No quote; it was not run in this common-market wave. Qualify event/participation and a genuine compatible No quote or a separately justified margin model before calling M a fair market probability. Never normalize Yes prices across players.
4. Exact PPR: complete the actual scoring-component labels before numerical comparison. This does not delay the other eleven targets.
5. The existing website integrator has the precise private Odds API producer request in [PR #10 comment 6460378852](https://github.com/NickNicky19/nicks-expert-nfl-picks/pull/10#issuecomment-6460378852): one separately budgeted zero-credit events check after private transport/reservation is verified. Zero API requests/credits or key reads occurred in this wave. The old one-time 176-credit batch is not reset.
6. Preserve the existing scheduler and weekly product-specific selection policy. Configured daily timing is 08:06 America/Chicago; selected capture/grading/selection success has not been established by a configured schedule. Operationally ready selected replacements still go through the existing production owner; no extra eight-week prerequisite is introduced.

Research-tested, operationally ready, selected, deployed, live-verified and scientifically qualified remain separate statuses. No new archive-derived entrant has earned those later statuses here.
