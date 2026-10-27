# Completed accuracy comparisons — October 26, 2026

This report contains derived aggregate results only. Original player-level data,
model artifacts, private storage locations and operational execution records are
not included.

## Actual model comparisons

|Experiment|Supported outcomes|Candidate MSE|Matched control MSE|Decision|
|---|---:|---:|---:|---|
|Retained hierarchical interception model, no refit|633 QB appearances; 271 games; 18 weeks in 2022|0.731642|NGBoost: 0.687549; Leaf-CDF: 0.689250|Retain controls: candidate error is 6.41% and 6.15% higher|
|One added FTN interception-worthy feature, fixed Count A learner|663 QB appearances; 272 games; 18 weeks in 2023|0.711671|Same learner without the added feature: 0.708188|Retain control: added-feature error is 0.492% higher|

Both experiments predict expected interception counts, with MSE primary.
Their respective MAE values are 0.703100 and 0.683622 interceptions; these are
not calibrated interception-event probabilities. The FTN paired MSE difference
is +0.003483, with exploratory whole-week 95% interval [-0.005432, +0.013285].
The strongest FTN-study control was Threshold-CDF, MSE 0.697533.

These are exposed historical development comparisons, with reconstructed source
availability. They are not prospective wins against today's website. The first
experiment restored retained parameters without refitting; it does not reproduce
an earlier unretained forecast vector. The second used one fixed new estimator.
Both earlier archive failures and the later wrapper failure remain preserved.

## Current-season rare-count coverage

Passing TD and interception outcome support for the existing Week 7 query is
now **28 of 88 opportunities per target**, with 53 unknown and seven pending.
The final two labels are separately identified, derived zero counts supported
by a known-played witness and exhaustive team passing-credit reconciliation;
they are not newly observed individual-stat fields. Unknowns remain unknown.

On the **eight genuinely pregame QB forecasts across four games**, the current
interception model has the lowest recorded MSE among the captured lab procedures.
Some saved control points have lower error, but different input vintages prevent
a clean method comparison. Count A is 16.30% worse and
Response-CDF is 0.84% worse. The earlier challenger lead came from a four-positive
outcome subset and reverses after genuine zeros are restored. This small panel
cannot establish lasting superiority. A broader 24-QB, 12-game common panel
includes post-start reconstructions and is reported separately in private evidence.
No forecasts or selected lists were changed by outcome qualification.

## Storage and live status

The original 512 MiB allocation and failures are preserved. A separate 512 MiB
forward allowance is initialized under a joint 1 GiB cap, including peak writes
and failure evidence. Fresh-process local restoration passed. At the completed
comparison checkpoint, forward usage was 4,738,542 bytes. Off-host restoration
and recurring production use of that allocation are not yet verified.

**No replacement was selected or deployed by this wave.** The website's latest
observed scheduled run failed; its served build remains dated October 25.
Fresh matched-time reference/challenger capture and hosted repairs remain with
the existing production integrator. All twelve category statuses and original
scientific registrations remain preserved; exact website PPR still lacks
complete supported labels. Count-median MAE products stay separate from count
means and probability forecasts. The next bounded source prerequisite concerns
participation and rushing/reception credit completeness; it has no new accuracy
result yet.

## Follow-on source qualification — October 27

Independent review now qualifies **115 rushing-attempt and 859 reception
derived-zero cases across 859 unique player-games** for separately registered
research intake. These are
source-qualified cases, not new predictions or demonstrated model gains. The
original forecasts and all failures remain preserved. A separately registered
intake and cached comparison must run before new accuracy results are reported.

See the [complete aggregate source report](../role-count-source-info-v4/RESULTS.md).
Its source-only study performed no fitting, prediction or scoring. The latest
locked census leaves 509,468,417 bytes free in the new allocation; joint storage
is 564,268,990 bytes, below 1 GiB. No external storage purchase was needed.
