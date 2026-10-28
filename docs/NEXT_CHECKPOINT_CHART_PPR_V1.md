# Chart PPR target and source prerequisites

`nick-chart-ppr-v1` implements the complete supplied transcription. The image
`IMG_4712.jpeg` was referenced but was not available to inspect. The transcription
is the authority. The previous `nfl_lab/scoring.py` and all its historical labels
remain versioned separately.

The formula has sixteen primitive fields. It deducts one point per unique
credited lost fumble across phases. Passing, rushing and receiving conversion
credits each earn two points; a conversion catch does not create an ordinary
reception. Offensive recovery touchdowns and the three specified return
touchdown classes are disjoint from ordinary scorer touchdowns. Unlisted
recoveries, forced fumbles, blocks and return yards add no points. A verified
aggregate covering exactly the three return classes is usable once.

`score_observed` requires integer observed event counts, signed official yards
and every required value. `score_component_expectations` accepts fractional
conditional means and implements linear expectation without requiring a joint
simulator. Component medians and anytime probabilities are different products.
The source adapter reports component evidence and does not infer missing zeros.

| Chart component | Retained NFLverse field and qualification |
| --- | --- |
| Passing yards, TDs, interceptions | `passing_yards`, `passing_tds`, `passing_interceptions`, explicit finite values |
| Rushing yards, TDs | `rushing_yards`, `rushing_tds`, explicit finite values |
| Receptions, receiving yards, TDs | `receptions`, `receiving_yards`, `receiving_tds`, explicit finite values |
| Unique all-phase fumbles lost | `fumbles_lost_total`, generator counts credited stat ID 106 once; no offense-only phase sum |
| Passing, rushing, receiving two points | Three separate `*_2pt_conversions` fields; generator IDs 77, 75, 104 respectively |
| Offensive recovery TD | `fumble_recovery_tds == 0` can prove the subset zero under a complete present-group source contract; a positive total requires offense/defense/special-phase and final-player mapping |
| Kick, punt, field-goal return TD | `special_teams_tds == 0` can prove zero native return classes under the inspected complete superset contract; a positive total is broader than the chart and requires classification |

The inspected generator hash is
`0ccd41c78355ee89c08929c79e81dac75b4d3f7b22d691cddd4f7f875acfac28`.
Its recovery TD count includes lateral recipients (IDs 56, 58, 60, 62).
Its `special_teams_tds` includes all special-play `td_ids()`, including native
punt (34, 36), kickoff (46, 48) and other-return (64) touchdowns plus additional
classes. Ordinary own/opponent recovery counts do not prove recovery TD zeros.
No old Sleeper defensive-credit exception or eighteen-field blanket blocker is
imported into this target. Source mapping does not independently attest the
historical producer binary or official truth.

Retained weekly source bindings authenticate for 2024, 2025 and one operational
2026 snapshot. These have 18,983, 19,422 and 6,488 total source rows before the
declared REG/position/week population filter. The separate 2026 median-boosting
cache copy failed its receipt: actual 380,427 bytes and
`963c09479474b6c3a7dba8a88b6cae6931d077d424617df15cc06dd669211602`;
the receipt describes 386,908 bytes and `17c5e715…`. It was not decoded or
overwritten. The authentic 386,908-byte operational source remains eligible.

The retained full 2024 PBP has 49,492 plays and verified hash `3fd2896b…`.
The earlier qualified count-zero intake admitted only rushing-attempt/reception
zeros. Its admission does not qualify yards, touchdowns or PPR. This new runner
requires a separate root and independent GO, preserves all planned rows, and
admits a positive rare component only after a unique TD-player/game/team ledger
reconciles to its explicit weekly broad total. Missing or ambiguous classifications
remain unsupported. 2025 football labels are authorized by addendum section C;
the completed no-2025 historical-market wave retains its original scope.

A source row does not establish participation. The adapter accepts explicit
source `gp`, qualified snap/inactive evidence, explicit credited ordinary events,
or a compatible nondeleted/non-nullified PBP actor witness. An all-zero row without
a positive witness remains unknown. Known DNP, played zero, played missing and
unknown are different states. Source-listed players do not constitute an
exhaustive offered-player or roster population; statless additions need their
own qualified identity/participation and component inventory.

The current software validation is twenty fictional cases with zero NFL fits,
forecasts or accuracy experiments. Label reconstruction is source work. Any
safe coverage report must include all planned positive rare events and missing
components. An event-free-only population cannot be used for a new predictive
comparison. Generic provider fantasy totals have not established chart parity.

The intended website migration remains with the existing production integrator.
It requires explicit scoring version display, compatible forecast components or
a qualified direct target, source bindings and normal consumer/fallback checks.
The chart has no deployed forecast or measured forecasting gain at this stage;
the old PPR target must not be relabeled as chart PPR.
