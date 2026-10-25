# Rushing-yard efficiency test

**Executed once; primary result inconclusive; no default replacement.**

The new question was whether a pooled eight-appearance efficiency estimate adds
value when multiplied by the same saved chronological carry forecast. A fixed
three-appearance variant was secondary. Both use the same eight-appearance
history gate and exact saved pooled-yard fallback. The workload, window,
fallback and five comparisons were frozen before new predictions or scores.

## Primary RB regular-season result

All four methods score the same **4,591 supported appearances**, covering
815 games, 226 players and 54 season-weeks in exposed 2022–2024 history.

| Method | MAE, yards | RMSE, yards | Signed bias, yards |
|---|---:|---:|---:|
| Saved recent-yard control | 23.479260 | 30.551776 | +0.816308 |
| Saved pooled-yard control | 22.816821 | 29.773570 | +1.287695 |
| Held tree carries × pooled H3 efficiency | 22.980071 | 29.969438 | +2.580478 |
| Held tree carries × pooled H8 efficiency | 22.628778 | 29.491359 | +2.866207 |

H8 reduces primary MAE by **0.188043 yards, or 0.824142%**, versus pooled.
Bias worsens from +1.287695 to +2.866207; the absolute-error p90 also worsens
from 43.536913 to 44.193417. H3 loses pooled. H8 is better than H3, but that
secondary result does not replace the primary comparison.

Both prespecified primary paired intervals include zero:

| Cluster | H8 minus pooled MAE interval, yards |
|---|---|
| Season-week | [−0.379353, +0.031556] |
| Game | [−0.420866, +0.011100] |

These are descriptive bootstrap intervals from 500 draws. The ten declared
intervals use nominal 99.5% confidence each under a nominal 95% Bonferroni family
adjustment; there are only about 1.25 draws per extreme tail. The shared helper's
retained field named `simultaneous_confidence` is the individual adjusted level,
not 99.5% family coverage. Both cluster views remain visible. No favorable view
was selected, and these intervals do not establish untouched confirmation.

## Coverage and football definitions

All **27,128** original offered opportunities remain, including other positions
and postseason. There are 18,585 supported outcomes, 3,515 played with missing
yards, 3,488 DNP and 1,540 unknown participation. Missing yardage is not zero.

The primary RB/REG population has 6,235 offered rows: 5,390 played, 782 DNP and
63 unknown. Of the 4,591 scored rows, 2,058 are informed and 2,533 use fallback;
772 supported outcomes are zero yards. RB postseason has 306 separate offered
rows and remains a point diagnostic. All 20,587 non-RB opportunities use the
unchanged pooled-yard point; their results are not an efficiency-model gain.

On the 2,058 informed primary rows, H8 MAE is 23.501869 versus pooled 23.921356.
The full population remains the primary analysis. No informed-only winner or
player selection rule is introduced.

Histories preserve observed team-spell closure before role and period filtering,
unknown appearances, explicit inactive DNP, played zero and signed yards.
Supported prior postseason observations are validated and traced before exclusion
from REG efficiency sums; unsupported observations stop selection. The contract
supports legal zero-carry/nonzero-yard source accounting without inventing a
carry; no such selected observation occurred in this study. Fictional tests of
that case do not add football evidence.

## Provenance, execution and decision

The efficiency layer uses zero new fits. Saved tree carry forecasts retain their
original chronological training identities; original tree nodes remain missing.
Substituting a website carry point would create a different candidate and could
not inherit these results. This is separate from the original five-prior-season
RB carry-share proposal, whose missing inputs remain unresolved.

One execution and one scoring pass used 6.396 CPU seconds, 6.186 wall seconds,
two threads and 3,640,590 private output bytes. Seventeen fictional guard cases
passed before the run. A separate read-only reviewer checked every history
closure, saved-point binding, 132 metric tables and all ten intervals. That is
arithmetic/source acceptance, not another football sample or qualification.

The underlying sources are revised historical data with an assumed seven-day
availability lag. All years were already exposed. No historical raw Sleeper or
website forecasts exist for this panel. The result therefore adds **no new
website-relative gain**, pregame evidence, qualified default or deployment.

Full [derived aggregate results](report.json) retain coverage, role/year/period
diagnostics, tails, source/code hashes, finite budget and adverse findings.
The [current twelve-category index](category-status.json) keeps the earlier
website comparisons separate from this new historical study.
Private inputs, forecasts, selected histories and reference rows are retained
outside public Git. No workflow, default, recorder or website code changed.

See the separate [archived website scorecard](../methods-resumption-20261022/website-comparison.md)
for the existing website-relative comparisons.
