# Fixed boosting challenger: completed research checkpoint

**No new model qualifies as a website replacement.** This experiment retains
all twelve categories, the gains, the losses and exact-PPR's source block.
The website remains read-only and no forecasting default changes.

## What forecasting means here

The target is each individual player's full-game statistic in the named
category. A posted prop line is a threshold to compare against that forecast.
These numeric models output MAE point heuristics; they do not supply tested
numeric distributions, over/under probabilities or push mass. A projected total
above a line alone does not establish a reliable over. Anytime TD is separately
a probability of at least one rushing or receiving TD, conditional on the
stated played population. This study does not predict the sportsbook's future
posted line, use new odds acquisition, or establish wagering performance.

## What ran

One new fixed model family, two feature panels, eleven supported targets:
66 expanding-history fits for 2022–2024 and 22 separate Week6 reconstruction
fits trained on 2019–2025. All **88 fits** finished with no technical failure;
eight exact-PPR attempt slots remain blocked. This is not 88 independent methods.
All forecasts were frozen before one global scoring phase. The finite search,
source qualification, feature roles, losses, fallbacks and budgets were sealed
before fitting. Registration: `all12-median-boosting-v1-20261023`.

The numeric model is fixed absolute-error histogram gradient boosting; TD uses
fixed binary log-loss boosting. Both panels use 150 iterations, learning rate
0.05, depth3, at most15 leaves, minimum30 rows/leaf, L2=10, seed1702 and no early
stopping. Cold or otherwise unsupported predictions retain training-only
role/global prior fallbacks. Count points have a declared zero floor; signed
yards do not. No window, coefficient, blend weight or model was retuned after
these scores. See [inference and recovery](../../docs/MEDIAN_BOOSTING_RESEARCH.md).

## Twelve-category primary results

Positive percentages mean lower primary error. Numeric loss is MAE in the
category's units; TD loss is Brier. Both panels are shown without selecting a
winner. Historical comparisons use the prior frozen same-panel empirical-CDF
point/probability on the **same new source-qualified rows**. They are not
historical website comparisons. The Week6 comparator is the literal original
website forecast, paired separately on the same qualified player-games.

| Category | Historical vs old CDF, base / context | Week6 vs website, base / context | Week6 scored |
|---|---:|---:|---:|
| Passing yards | +1.30% / +0.43% | +8.13% / +9.65% | 27 |
| Passing TDs | -3.68% / -5.12% | +0.20% / +0.20% | 27 |
| Completions | +0.86% / +0.26% | -6.41% / +1.86% | 27 |
| Passing attempts | +0.11% / -0.17% | -8.19% / +0.39% | 27 |
| Passing interceptions | +0.31% / +0.08% | -6.03% / -6.03% | 27 |
| Rushing yards | -52.48% / -53.08% | +9.35% / +9.43% | 96 |
| Rushing attempts | -108.12% / -108.95% | -134.80% / -134.80% | 69 |
| Receptions | -2.50% / -2.72% | -3.92% / -3.97% | 252 |
| Receiving yards | -0.95% / -1.02% | -2.31% / -2.24% | 252 |
| Rushing + receiving yards | -0.53% / -0.35% | -3.83% / -3.79% | 189 |
| Exact offensive PPR | blocked / blocked | blocked / blocked | 0 |
| Anytime rush/receive TD | -1.30% / -0.63% | +3.07% / +2.34% | 243 |

Historical primary coverage is 18,303 supported rows per category/panel from
27,128 offered rows, 854 games and66 season-week blocks. These are overlapping
all-role populations, not independent category samples. Passing statistics
include many non-QB zeros; the all-role passing-yard MAE near7.5 is not a typical
QB error. On the prespecified QB subset (2,049 rows), passing-yard MAE is
67.5266→66.6448 for base and66.5739→66.2862 for context. Passing-attempt MAE is
8.3899→8.3809 and8.3060→8.3202 respectively.

Week6 retains all **2,083 original category offers for396 players**; scored
counts above cover13 games in one exposed week. Missing outcomes remain missing.
For example, website passing-yard MAE56.6230 becomes52.0177 /51.1582. Rushing
attempt MAE3.4257 becomes8.0435 /8.0435. Anytime-TD Brier0.145864 becomes
0.141393 /0.142444 (rounded). Category populations differ; do not pool units or
interpret these descriptive percentages as over/under hit rates.

## Material failures and secondary findings

The rushing-attempt candidate returns zero for all99 warm RB Week6 contexts and
a prior of5 for one cold context. It is a technically valid but poor forecast;
this version is excluded from integration consideration. On4,766 historical RB
rows, rushing-attempt MAE rises from3.4992 /3.4836 to7.7415, and rushing-yard MAE
from19.5346 /19.4255 to33.5359. The exact cause has not been established; this
version was not adaptively fixed or refitted. Several receiving and historical
TD comparisons also worsen. A Week6 gain cannot erase those findings.

The separately declared 50/50 website blends are secondary, with no weight
search. They improve Week6 receiving-yard MAE by2.51% /2.49% and combined-yard
MAE by1.72% /1.88%, but worsen receptions0.33% /0.36%, interceptions2.96% /2.96%
and rushing attempts34.46% /34.46%. They establish no qualified replacement.
All pure/blend, raw, website, recent and pooled comparisons, RMSE, signed bias,
tails, fallback and role/team/opponent summaries and player counts remain in the
[full aggregate report](aggregate-report.json) and [readable tables](aggregate-report.md).

## Source and confirmation limits

The new learner uses a separately rebuilt NFL statistics/weekly-roster/schedule/
identity packet. No PFR snap file or old PFR-derived feature table is used for
new fitting or inference. Snap means are disabled/missing and observed-value
counts are zero, not invented snap outcomes. Old forecast outputs remain frozen
comparators only. This changes learner and source qualification together;
results cannot isolate the effect of the learner alone.

Attributed positive physical NFL events qualify participation. Roster status,
penalties and all-zero row presence alone do not. Unknown rows consume history
slots and unsupported conditional values stay missing. This is not a complete
participant panel. The source rule reduces Week6 counts relative to the prior
study, whose scores and original states remain preserved. New scores are
recomputed on exact pairs; no gains transfer across different denominators.
See [the source update, original RB gate and new PPR probe](../source-policy-20261023/README.md).

All retained2019–2025 data and2026Week6 are exposed. Current-vintage revisions
and roster information can confer advantages over original issuance. The
seven-day historical availability assumption is not verified as-of timing.
2026 query features read Weeks1–5 only; target outcomes are isolated Week6 REG.
No later-week statistics were opened. Historical nominal95% game/week paired
intervals use500 fixed bootstrap replicates and are unadjusted descriptive
intervals, not multiplicity-controlled confirmation. No Week6 intervals are
claimed. All48 main comparison slots, including four PPR blocks, remain visible.

Exact PPR's new play-by-play positive-event bridge still qualifies zero rows
under the full original18-component outcome contract. No omitted fields become
zeros and no generic provider total substitutes for website scoring. The
original RB carry-share proposal's complete-participation/five-season-prior
gate also remains unmet. Its original protocol is not this generic carry model.
Frozen passing-yard evidence, original missing-runner caveat, mixed/failed
attempts/completions findings and `rec-half-adjustment-v1` registration/Weeks7–14
remain unchanged. No missed registered forecasts were backfilled or restarted.

## Software, review and next evidence boundary

The integrated software suite passed484 checks before the experiment; five
additional fictional exporter fixtures passed separately. These are not489
checks from one full-suite execution and are not NFL accuracy observations.
The campaign took349.44 wall seconds /472.77 CPU seconds with two threads,
within the sealed20-minute wall/30-minute CPU limits. Frozen artifact replay
matched38 existing case incidences across22 models exactly, without outcomes,
new fits or new accuracy scores. Missing replay-case classes were not fabricated.
See [technical replay](technical-replay-summary.json) and
[the separate read-only review receipt](review-receipt.json).

The reviewer checked saved rows, paired losses, intervals, training-only
preprocessing/prior/fallback provenance, clocks and all public aggregate transfers;
it loaded no models, made no forecasts and added no football observations.
The successful arithmetic review does not establish source completeness or
scientific qualification. All failed checks/trials remain retained privately.

This packet is runnable research, with explicit rollback and frozen versioned
artifacts. It supplies no qualified live default, deployment decision or claim
that all possible forecasting methods have been exhausted. New methods and
fresh same-cutoff pregame confirmation remain necessary. Website integration
belongs to its owner through the separate authorized release process. No new
scheduler, recorder, workflow dispatch, main merge or website write occurred.
