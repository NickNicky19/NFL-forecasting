# All-seven-week roster preparation adapter

This is source preparation, not an executed NFL comparison. No model/label/forecast was loaded or fitted. Only Parquet footer/schema and the roster's week-number metadata column were read. All seven roster weeks are present. Original Week 7's 610 queries cover thirteen remaining games; its earlier Thursday rows were excluded. The new library enumerates every game from an outcome-blind roster universe and retains quarantine counts.

## Entry points

`roster_queries(...)` calls the pinned existing weekly roster builder for each week with an enumeration cutoff preceding all games, then declares reconstructed-kickoff contexts. That enumeration clock is not an original forecast issue or known publication time. No status is interpreted as played/DNP.

`historical_features(...)` builds one target week at a time around unchanged `features.build_features`. Raw history is limited to earlier seasons and earlier 2026 weeks. Old history through Week 5 plus the separately authenticated raw qualified Week 6 history suffices. Explicit unknown availability rows are omitted and counted, not replaced. Known availability must match the preserved kickoff-plus-seven-day assumption; genuinely different availability needs a different corrected adapter. Internal blank-query availability placeholders cannot enter an earlier window and are dropped from returned feature-only contexts. No operational manifest or genuine pregame receipt is created.

An optional root-pinned augmentation hook supports existing ordered/backfield columns without changing base features. Root must inspect/pin that callable separately. `reusable_overlap(...)` admits cached predictions only on identical canonical keys, context, cutoff and exact model feature inputs. All mismatches remain in the primary population for fresh inference; the old 2,999-row benchmark stays separately identified.

## Labels and execution gates

Existing weekly2026 statistics and chart PBP footer ranges end at Week 6. The thirteen-game nonpassing outcome packet cannot prove full Week 7 coverage. The pinned website Week 7 stat cache is a candidate source for ordinary statistics and rushing/receiving TD labels, subject to exact roster/GSIS/Sleeper/team/game joins, participation and true-zero qualification. It does not establish all sixteen chart primitives. Full Week 7 chart labels require another qualified retained source or bounded permitted acquisition. That gap blocks chart rows only.

The root integrator must register/pin a finite runner, source references, storage and GO before invoking library functions. Freeze per-method forecasts before evaluation labels. This adapter never overrides genuine future-source as-of guards. Historical roster timing and corrected-stat vintages remain uncertain: all new reconstructions are stream C, exposed development.
