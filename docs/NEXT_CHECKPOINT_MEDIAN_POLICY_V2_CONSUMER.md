# MAE-first numeric projection v2: objective and owner integration contract

This is `research-informed-stat-point-mae-v2`, a separate, not-yet-activated
procedure. It keeps original P2, research-informed-v1, their decisions, all
scientific registrations and every old forecast intact. The existing producer,
single writer, private transport and scheduler remain the operational route.

## Why the preceding v1 does not implement the latest display objective

The owner prioritizes a smaller average absolute miss for the displayed numeric
projection. V1 instead kept the six count displays on mean/MSE and imposed three
additional startup vetoes: no 2025 loss regression, no absolute signed-bias
regression and no p95-error regression. Those vetoes were implementation choices
introduced in v1, not original universal owner or scientific-registration gates.

Consequences visible in the frozen evidence:

- The 2026 CDF count medians have lower point MAE but could not enter v1's fixed
  count mean/MSE product. This was a product/operational boundary, not proof that
  the median's lower MAE was false.
- CDF receiving and combined-yard medians have the lower inspected 2026 MAE but
  v1 rejects them because their absolute mean signed error is worse than the
  incumbent CatBoost median.
- The 2025 and p95 diagnostics are useful. A conditional median need not have
  zero mean signed error. That diagnostic alone does not invalidate a median.

V2 uses the explicit new selection product **`stat_point_mae_v2`**, ranked by
compatible 2026 MAE. It admits actual medians as well as correctly typed mean,
empirical or arithmetic-point procedures. A mean or empirical point with lower
MAE is not hidden, and is not relabeled a median. The source model's training
objective and actual output functional remain recorded.

2025, older seasons, bias, RMSE, p90/p95, tolerances, interval uncertainty and
coverage remain visible diagnostics. They do not silently become new universal
vetoes. The switching margin is explicitly zero. Exact ties retain the current
identically typed procedure, then stable procedure ID. V2 was designed after
exposed historical results: its initialization is development-informed and is
not an untouched policy test, a genuine P2 win or scientific qualification.

The strict median/MAE leaderboard, valid mean/MSE leaderboard, full-distribution
and probability leaderboards remain distinct. The numeric projection profile
does not change anytime-TD, prop probabilities, market/EV selection or settlement.
The incumbent TD stream remains identified under its existing Brier policy.

## Implemented pieces

- `nfl_lab/next_checkpoint_median_policy_v2.py`: pure metadata selection with
  exact scoring, source/horizon/population/receipt identities, complete offered
  coverage and included fallback checks. It returns both research leader and
  separately operationally admitted candidate. Every original point functional
  stays explicit. A separately prefixed epoch reuses the unchanged earlier-loss
  cumulative selector; no old P2 record is imported.
- `nfl_lab/next_checkpoint_median_policy_v2_view.py`: full-law lower-median
  extractor and typed consumer bridge. It obtains actual `law.quantile(.5)`,
  checks `F(m-1)<0.5<=F(m)`, retains the mean separately and preserves the full
  trained support/prior. It does not fit, load a model or query player features.
- `config/next-checkpoint-median-policy-v2.json`: source and historical artifact
  context, explicit criteria, finite preparation/software budgets and concrete
  admission dependencies. Original manifest IDs are explicitly distinguished
  from current relocated wrappers; a new hash is not operational qualification.

These source modules are not a source-qualified future producer by themselves.
The existing trusted producer must authenticate model/source/query/cutoff and
actual fit/issue/persistence receipts before handing a law to the extractor.
The strict historical replay and existing future API are unchanged. Do not edit
their default count mean to median and then bless old mean replay bits.

## Exact consumer fields and labels

New rows use `schema_version="stat-point-mae-v2"`,
`selection_product="stat_point_mae_v2"`, `selection_metric="MAE"` and retain
the original `forecast_product` and `prediction_functional`. Public views expose
`selected_projection`, its actual label, and `expected_mean` when available.

| Actual output | Source product / functional | Display label |
|---|---|---|
| Full-law lower median | point_median / full_cdf_lower_median | Selected median |
| MAE-objective point | point_median / median_objective_point | Selected median-objective projection |
| Authentic mean | point_mean / expected_mean or valid_mean_objective_point | Selected mean projection |
| Legacy or other empirical point | point_empirical / original empirical functional | Selected empirical point |
| Arithmetic point blend | point_empirical / arithmetic_point_blend | Selected point blend |

An arithmetic average of medians is not a mixture median. An old mixed fallback
point is not a valid full conditional mean. Such procedures can be compared on
point MAE under their real contracts without acquiring false distribution claims.

Fallbacks preserve original contract version, functional, model/source identity
and reason. A mean fallback receives a mean label. Unsupported PPR continues its
old target and label; it must not pass through the new chart consumer under a
false `nick-chart-ppr-v1` identity.

Every point row retains player/game/target/horizon, 64-hex model/procedure/source
and capture identities, original forecast version and actual issue clocks.
`information_cutoff_utc <= issued_at < issue_deadline_utc < kickoff_utc`.
`issue_deadline_utc` is a registered issue/persistence deadline, not a claimed
source-publication time. Actual feature availability must be no later than the
declared information cutoff, which must be no later than actual issuance.
Unknown warm-player availability remains unsupported; a registered trained-prior
fallback preserves its prior identity rather than fabricating a recent clock.

Counts keep nonnegative support; yards keep signed support. For chart PPR, the
CDF integer is the exact `50*S` lattice and is divided by 50, including negative
values. All point meanings and the unchanged full law remain explicit.

## Minimal retained-owner integration sequence

1. Authenticate the current restored future artifacts and original model bytes.
   The config's original manifest IDs identify historical context; obtain the
   actual restored-wrapper mapping and source/conditioning bindings from the
   existing producer. Preserve its trained fixtures and mean replay checks.
2. Introduce a separate functional-extraction/row-profile version at the existing
   already-qualified law seam. Freeze the new procedure/catalog IDs before its
   current values. No new fit is required merely to extract a retained CDF's
   median, but real reference/fallback replay and private restoration are needed.
3. Register the new MAE projection selection profile separately from existing
   `point_mean` and `point_median` forecast contracts. Preserve standalone mean
   output where supported. Do not overwrite an old mean field with a median.
4. Admit/export exact selected method/model/config/product bindings through the
   normal public scope. Preserve R0, actual website history, private challengers,
   failed/late issuance and truthful fallback. Keep old policies available.
5. Update the active projection chip, Top Over/Under point-gap input and sort
   consumer to use the typed `selected_projection`, with the actual label above.
   Gap ranking remains point-only; it does not become calibrated probability or
   +EV ranking. Original offers, prices and historic picks are not regenerated.
6. Verify actual served payload, values, labels, ranking membership, fallback and
   rollback. Record the live build and original pregame capture assignment. A
   passing preview, source helper or policy selection is not deployed consumption.

No category waits for all other categories or an extra blanket eight-week gate.
Hard source, identity, timing, exact product, finite-value, durable restoration,
consumer, fallback/rollback and existing owner release controls remain required.

## Current exact boundaries

Current prepared inputs still include reconstructed seven-day history and
exposed periods. V2 does not repair that timing assumption or infer injury/role
knowledge. Freshness and new-information studies require separate source rules.
The new chart CDF replay is complete, but current-source, producer restoration
and chart consumer admission remain unfinished. Its adverse findings remain.

Fewer than three genuinely distinct ready learners in a category is an honest
shortfall. Mean and median views of one CDF are different products of one model,
not extra independent learners. Use a unique procedure/point-view identity for
each functional, while preserving a shared base-learner identity for the weekly
3–5-method census. Do not silently spend another learner slot or inflate football
evidence because a retained CDF supplies two point views. Any catalog/schema
extension follows the existing owner entry procedure.

A new entrant's record begins when it is actually
captured before cutoff; no historic reconstruction becomes an issued forecast.
