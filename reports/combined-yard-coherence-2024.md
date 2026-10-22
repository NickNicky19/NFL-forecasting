# Frozen 2024 combined-yard audit

The frozen tree method is the only finite method whose direct combined-yard
means materially differ from its rushing-plus-receiving means. Replacing them
with the component sum slightly reduces descriptive MAE, worsens RMSE and
absolute bias, and has a paired week MAE interval spanning zero. This audit does
not establish improvement or select/promote a model.

The audit reads the original `lab-v1-2026-10-22` parquet files without any fit,
changed input row, new forecast, quantile addition, or row-level export. These
2024 outcomes were already exposed; all results are descriptive current-vintage
historical reconstruction. Source-file SHA256 pins and full aggregate counts
are in `combined-yard-coherence-2024.json`.

All 12 methods have the same 9,000 aligned player/game rows: 7,365 played,
1,121 known DNP, and 514 unknown participation. Of the played rows, 1,151 lack
one or more supported component outcomes. Each finite method scores the same
6,214 supported played pairs, 69.04% of the full offered population, across 285
games and 22 weeks including postseason. No missing outcome is filled with zero. Both raw
Sleeper and pinned website controls lack authentic pregame forecast bindings
for all 9,000 rows and therefore have no numerical score.

There are zero identity, participation-state or participation-probability
incompatibilities, and zero discrepancies between available frozen combined
outcomes and frozen rushing-plus-receiving outcomes. This checks the frozen
source crosswalk's arithmetic; it does not independently establish provider
truth or authentic historical pregame availability.

All metrics below use the same supported rows. Bias is prediction minus actual.
Units are yards. The two methods without forecasts retain their missingness.

| Method | Direct MAE | Sum MAE | Direct RMSE | Sum RMSE | Direct bias | Sum bias |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| recent | 23.0338 | 23.0338 | 30.2833 | 30.2833 | 1.4266 | 1.4266 |
| pooled | 22.1996 | 22.1996 | 29.2251 | 29.2251 | 1.5907 | 1.5907 |
| workload | 23.0114 | 23.0114 | 30.2111 | 30.2111 | 1.3548 | 1.3548 |
| ridge | 19.7414 | 19.7414 | 27.6051 | 27.6051 | -0.3417 | -0.3417 |
| tree | 20.1266 | 20.0585 | 27.8012 | 27.8266 | -0.0009 | 0.0123 |
| distributional | 19.7414 | 19.7414 | 27.6051 | 27.6051 | -0.3417 | -0.3417 |
| ensemble | 20.9941 | 20.9941 | 28.3363 | 28.3363 | 0.5245 | 0.5245 |
| ridge_without_opponent | 19.6987 | 19.6987 | 27.5719 | 27.5719 | -0.4294 | -0.4294 |
| ridge_without_workload | 21.9313 | 21.9313 | 29.6087 | 29.6087 | -0.0587 | -0.0587 |
| ridge_without_team | 19.6813 | 19.6813 | 27.6103 | 27.6103 | -0.5288 | -0.5288 |
| raw_sleeper | missing | missing | missing | missing | missing | missing |
| pinned_website | missing | missing | missing | missing | missing | missing |

For tree, all 9,000 forecast rows differ by more than 1e-9 yard, and 6,976 differ
by more than one yard. Mean absolute discrepancy is 2.5679 yards; maximum is
16.4609. Every other finite method has zero discrepancies above 1e-9; its
apparent numerical error differences, at most approximately 1e-13, are floating
point arithmetic rather than evidence of forecasting improvement.

Tree's component-sum-minus-direct paired deltas are MAE -0.06814, RMSE +0.02539,
and bias +0.01314 yard. Whole-week bootstrap intervals are respectively
[-0.14014, +0.00944], [-0.08802, +0.14370], and [-0.08727, +0.13860]. The audit
uses 500 replicates, seed 20261022, paired resampling of season/week clusters,
player-row-weighted metrics, and Bonferroni adjustment across 12 methods
(99.5833% nominal simultaneous intervals). At this finite bootstrap size the
extreme tails are approximate; no selection/promotion conclusion is drawn.
The separate paired game-cluster MAE interval, using all 285 game clusters and
the same 500-replicate/seed/12-method adjustment, is [-0.17006, +0.01831] and
also spans zero. Its RMSE interval is [-0.08651, +0.11513], and bias interval is
[-0.07371, +0.09889]. Method adjustment applies separately within each cluster
analysis; no joint inferential claim across the two analyses is made.
The JSON preserves both sets of per-method intervals, including near-zero numerical
differences, rather than dropping unfavorable or missing comparisons.

Reusable command: `python -m nfl_lab.coherence_audit <frozen-campaign-directory>
--output <aggregate-json-path>`. Five focused synthetic tests verify paired
metrics/week resampling, unequal week sizes, strict missingness, incompatible
participation, unmatched/duplicate identities, and the finite bootstrap budget.
