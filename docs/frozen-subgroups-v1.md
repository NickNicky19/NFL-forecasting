# Frozen subgroup consumer v1

Registration: `source-matched-frozen-subgroups-v1-20261023`, SHA256
`f07cb07b9180129594ebdc0bba72386ceb777757756900ae4b4004924f6318bc`.
This is a supplemental descriptive report declared before the parent global
forecast freeze and scoring. It adds no NFL observations or predictive evidence.

## Pure API and caller bindings

`build_frozen_subgroups(scored_rows, category) -> (public_report, private_player_report)`
accepts one nonempty target-method dataframe containing only completed, already
scored annual cells pooled across exposed 2022–2024 regular seasons. The fixed
methods are `leaf_cdf`, `median_hgb`, `count_A`, `role_B`, `recent`, `pooled`.
Exact PPR and the diagnostic `role_prior` are excluded. The fixed category must
declare its supported target, `READY` state, exact support and primary roles.

The caller must authenticate exact input file hashes against the parent's
`SCORED_ROWS_FROZEN` manifest and freeze this consumer's code before use. Hash
verification, file reads, quota writes and the one bounded aggregation execution
belong to the caller. The helper performs no IO, fit, prediction, source read,
label construction, resampling, contrast, ranking or promotion. Stream and
release one target-method at a time; never concatenate every target's rows.
Parent failed, unrun and all eighteen blocked exact-PPR slots remain in the
parent report; absent annual cells are reported without synthesizing rows.

Inputs use the parent's normalized scored schema: KEYS `season, week, game_id,
player_id`; `year, target, method, point, probability, mean, median, actual,
participation_state, outcome_state, primary_role, fallback, history_state,
position, team, opponent, kickoff_utc, cutoff_utc`; and CDF score fields
`p10,p90,variance,crps,log_score,cdf_actual_below,cdf_actual`. Inapplicable numeric
fields remain numeric NaN. Extra input columns are ignored. Unique nonnull KEYS,
one target-method, integer exposed years, regular-season weeks, exact boolean
primary-role membership and nonnull UTC-normalized cutoff no later than kickoff
are required. An optional `season_type` must be `REG`. This verifies internal
consistency; the authenticated parent manifest establishes source provenance.

## Fixed populations, groups and metrics

Every offered row appears in `all_offered`; its frozen role mask determines
`primary_roles`. There are exactly seven grouping dimensions without any
cross-products: player, team, opponent, position, history state, fallback and
outcome state. Groups are ordered by labels, never performance. Missing group
labels have JSON `value: null` and `missing_group_value: true`; sparse and fully
unscored groups remain. Included/absent years are explicit. Pooled metrics are
computed on pooled rows, not annual metric averages. Targets and units stay
separate. No subgroup intervals or significance claims are added; parent
category game/week intervals remain the uncertainty reference.

Every summary calls unchanged `role_boosting_campaign.summary`, preserving
MAE/MSE/RMSE, bias, p90/p95/max absolute errors, offered/scored counts, distinct
scored players/games/season-weeks, genuine binary Brier/log loss and reliability.
Additional descriptive counts retain supported played zero and negative rows,
missing actuals/points, played invalid support, unknown participation, known DNP,
fallback rows and distinct offered populations. Only supported played outcomes
with finite points enter point errors. Unknown, DNP and missing fields never
become zeros. Signed integer yards remain signed.

Only `leaf_cdf` calls unchanged `cdf_evaluation.summarize`, retaining its saved
mean/median summaries, CRPS, log score, quantile coverage, CDF brackets, existing
key-stable descriptive PIT and binary reliability. No distribution is attached
to any numeric point family. These existing metrics do not establish calibration.
Binary probabilities are checked in [0,1] without clipping. Impossible events
retain positive infinite log loss and its explicit existing status/count.
Both returned dictionaries are JSON-safe with no JSON NaN/Infinity: unavailable
floating metrics become null and any infinite numeric metric is represented by
`{"state":"positive_infinity"}` (or negative infinity for a derived metric).

## Output privacy and execution limits

The first dictionary contains the two population summaries, six nonplayer group
dimensions and player coverage counts only: number of offered, scored and
unscored player groups plus offered/scored rows. It contains no player IDs,
individual player group metrics, game IDs or row forecasts. The second dictionary
is marked `PRIVATE_PLAYER_GROUPS_DO_NOT_PUBLISH` and contains player group metrics
for each population. Both are aggregates; the caller keeps the second private in
the existing quota. Sparse nonplayer aggregates are allowed by the registration;
this consumer does not claim statistical anonymization. Public export still
requires independent review of its exact contents and parent bindings.

Fictional software checks use at most 120 wall seconds/180 CPU seconds, one
thread. No actual aggregation is authorized by implementation or fixture tests.
The later root invocation needs a separate exact scored-file binding freeze and
uses the registered 300 wall/450 CPU seconds, 512 MiB RSS/shared unique file-byte
caps, one thread, no retry, and no fits/predictions/HTTP/new labels/search.
