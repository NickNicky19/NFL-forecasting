# Source-matched base benchmark reports

`build_reports(scored_rows, categories, replicates=500, seed=1703)` returns a
JSON-safe aggregate and a private paired-loss dataframe. For bounded actual
execution, `build_target_report(rows, categories, target=...)` runs that same
implementation with only one target's scored rows in memory. It retains full
frozen category metadata but ignores sibling slot statuses because sibling rows
are not present. The root immediately saves each private paired dataframe and
combines target aggregate items under `reporting_header()`. A fictional fixture
checks target-local/full-wrapper aggregate and loss equivalence. No full-data
concatenation is required for actual reporting. The module performs no file
access, source acquisition, model fitting/inference or promotion. Existing
point summaries and exact pair evaluators supply the point losses; the existing
CDF evaluator supplies law diagnostics. No learner or evaluator is modified.

Input rows use the agreed normalized methods `leaf_cdf`, `median_hgb`, `count_A`,
`role_B`, `recent`, `pooled`, plus diagnostic `role_prior`. Keys are season,
week, game and player; `year` must equal season in 2022-2024. Context/cutoff,
qualified outcomes, frozen primary-role mask, fallback/history state, points and
the CDF score fields accompany them. CDF numeric points are its lower median;
binary points are actual event probabilities. Numeric HGB/reference points
acquire no distribution or conditional median claim. Exact PPR scored rows are
rejected, while its eighteen planned slots remain blocked in the report.

All twelve categories and 216 planned method/year slots remain explicit.
Optional per-category `benchmark_slots` records contain year, method, state and
an optional private reason. Only state and the existence of further failure
detail enter aggregates. Rows require COMPLETED status; missing/failed cells
remain N/A. Pooled comparisons use complete common annual cells, list excluded
years and compute losses from pooled rows, never averaged annual metrics.

Reports contain annual and pooled primary-role/all-offered summaries; eleven
fixed point contrasts per target/population/period (CDF versus the five other
methods, plus median/A/B versus recent and pooled); and CDF-versus-role-prior
CRPS/log-loss diagnostics. Targets and football units are never pooled. Existing
point APIs retain MAE/MSE/RMSE, signed bias, p90/p95/extreme errors, binary Brier,
unclipped log loss and reliability. CDF summaries retain true law means/medians,
CRPS, log mass, interval/tail/PIT diagnostics and observed atom mass. Historical
recorded lines, SITE/raw forecasts and all-query zero-probability calibration
remain explicitly unavailable when the frozen fields do not supply them.

The registered bootstrap operates on paired loss sums/counts for entire
season/week or season/game clusters. It uses local NumPy PCG64 seed 1703, exactly
500 draws, linear 95% percentiles and the inherited minimum of eight clusters.
No row IID bootstrap or global RNG mutation occurs. Infinite log losses remain
in private losses and explicit aggregate infinity states; nonfinite/undefined
paired deltas receive N/A intervals rather than silently discarding rows.

Private paired losses contain one annual copy per target/key/contrast/metric,
with all-offered and primary eligibility masks, context clocks and both losses
and their difference. They omit duplicate pooled/population rows and model point
values already retained in scored rows. Shared categorical metadata and compact
year dtypes bound dataframe overhead. Full-benchmark paired output can still
exceed three million rows in total; target-local execution bounds the live
dataframe, while all serialized outputs count against the shared quota.
Aggregate JSON contains counts and
metrics without player/game identities; NaN is represented as null and infinity
as an explicit state object. Negative improvements and all failures remain.

Every year is repeatedly exposed development reconstruction. These nominal,
unadjusted diagnostics establish no independent confirmation, automatic winner,
promotion, historical website performance or scientific qualification.
