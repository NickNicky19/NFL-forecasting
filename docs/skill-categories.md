# Skill category implementation and evidence

Implemented adapters are research candidates. No new method inherits earlier
reported gains, claims prospective issuance, or qualifies for promotion merely
because these arithmetic and contract tests pass. The shared finite campaign
configuration and evaluator control any model comparison.

## Provenance

The unchanged public research arithmetic core is
`nfl_lab/retained/receiving_yards_core_draft.py`, copied from the supplied retained
receiving core. Its SHA256 is
`54c8ec8f274263cbfe9692777725828cf9ee4af8232c367c02eb98a9ff753ded`.
The original test file SHA256 was
`8d1fc7d25d1c93eed899f5a8bb9ff4d5f9fa2e08303ca63309840b76c8638b66`;
the committed tests change only its import to the package path. Core version
`rec-ypt-core-draft-20261022-01` and Decimal arithmetic remain unchanged.

Offensive PPR weights and the `idp_fum_rec` exception follow the read-only
website's `pull/scoring.py` at commit
`c8120e3cb26a908b8d5a99329b0f28ae49473ea1`, SHA256
`31672c10d526d591db8951157b0ecd669b4d02b412a75deec337618bff18dab2`.
No website files, raw licensed odds, original private handoff, or original
unrecovered model fits are published in this implementation.

## Public Python interfaces

| Interface | Behavior |
| --- | --- |
| `scoring.score_ppr(stats)` | Exact rounded website PPR or explicit missing/invalid component names |
| `scoring.ppr_points(stats)` | Exact float or `None` |
| `scoring.anytime_td_outcome(stats, participation=..., population=...)` | Binary rushing/receiving TD event; missing/unknown and settlement population explicit |
| `scoring.anytime_td_probability(rush_td_mean, rec_td_mean, ...)` | New Poisson control; passing, special-team and fumble-return TDs excluded |
| `receiving.evaluate_receiving(context, opportunities=..., statistics=..., projection=..., trusted_hashes=...)` | Pinned-source identity/clock/complete-sequence adapter around the exact core |
| `receiving.reception_half_adjustment(raw, unchanged_adjusted)` | Frozen arithmetic only |
| `skill.fit_predict_skill(train, test, target, method)` | Calls shared `models.fit_predict`; no duplicate fitting engine |
| `skill.independent_combined_yard_predictions(train, test, method)` | Separate direct combined prediction and compatible rushing/receiving mean sum for paired scoring |
| `skill.combine_mean_predictions(rushing, receiving, correlation=0)` | Sum aligned means; compute explicit normal moment intervals, never sum quantiles |
| `skill.rb_team_share_workload(...)` | New RB volume/share hypothesis with caller-declared prior |
| `skill.signed_workload_efficiency(...)` | New signed pooled efficiency hypothesis with caller-declared prior |
| `skill.sample_joint_components(means, history, cutoff_utc=..., ...)` | Bounded deterministic joint sampling with common participation and earlier training dependence |
| `skill.summarize_joint_components(samples)` | Score each aligned draw, then compute mean and quantiles of combined yards, exact PPR and TD event |

## Missingness and population

All 17 website weight components and `idp_fum_rec` must be explicit for exact
PPR. A known zero is valid; a missing field, null, boolean, nonfinite value or
invalid negative count abstains. Signed yards and fractional forecasts survive.
No generic provider PPR total repairs an unsupported scoring crosswalk. nflverse
historical exact PPR remains missing until a complete source crosswalk exists.

The fumble exception is nonlinear: PPR of component means can differ from mean
PPR over joint outcomes. Therefore joint PPR is scored draw by draw. An anytime
TD means at least one rushing or receiving touchdown. Known DNP is zero in an
all-player outcome population and absent from a conditional-on-playing outcome
population. Neither treatment determines a sportsbook's settlement rules.

## Receiving history contract

`SourceDocument` carries immutable bytes, a source reference, a genuine capture
clock and a time basis. The caller's trusted hash manifest must bind each source.
The projection document must match the original player/game/team/opponent/
period/season/week, target estimate, website baseline and capture clock. Hash
checks establish byte identity, not the truth or publication time of statistics.
Revised historical downloads cannot be relabeled pregame evidence.

The opportunity extraction has one explicit entry per season week before the
target, including byes and periods before roster entry. Its upstream roster and
schedule source must preserve prior-team opportunities after trades. Game rows
bind game/team/opponent/week/end time. The statistics document contains matched
identities, participation and source clocks. Unknown or absent intervening rows
block the triple; played missing or unfavorable yardage cannot be skipped in
favor of older appearances. Explicit DNP and bye do not count as appearances.
The original core uses current-season/current-team history, so a trade in the
latest triple, early season or a new player with fewer than three appearances
uses the unchanged website baseline. No previous season is borrowed.

`rec-half-adjustment-v1` remains exactly
`raw + 0.5 * (unchanged_adjusted - raw)`, registration
`2026-10-16T19:36:46.224755Z`, 2026 Weeks 7–14. The arithmetic helper creates no
official recorder, restarts no window, backfills no forecast and does not claim
recovery of original earliest-common-timely source bindings.

## New method versions and comparison requirements

* `rb-team-volume-shrunken-share-new-v1`: team carries × pooled player carry
  share, shrunk with explicit caller-supplied prior opportunities/share. It is
  RB-only and does not invent the missing original five-prior-season fits.
* `signed-workload-pooled-efficiency-new-v1`: workload × signed pooled yards per
  opportunity with explicit prior exposure. Missing paired history falls back
  to the declared prior instead of dropping the unfavorable/missing row.
* `rush-rec-compatible-component-means-new-v1`: sum compatible means. The direct
  combined target must be scored independently on the same rows. Structural
  coherence does not establish predictive improvement.
* `empirical-copula-coherent-passing-components-new-v2`: earlier complete training
  rows supply common opportunity ranks. Conditional binomial draws enforce
  catches ≤ targets and scorer counts ≤ opportunity. Passing uses one
  mutually exclusive allocation of touchdown completions, other completions,
  interceptions and other incompletions: TD ≤ completions and
  completions + interceptions ≤ attempts. Impossible marginal means fail.
  Passing yards require completion exposure and are zero at zero completions.
  Signed yards are zero at zero workload; one participation draw applies to
  every component. Insufficient complete history explicitly falls back to an
  independent copula. Tied ranks are randomized across the entire tie interval
  to preserve marginal zero mass. This is a separate distributional hypothesis.

Nonempty dependence history must have `outcome_available_utc` and an aware
`cutoff_utc`; only strict earlier availability enters. Known DNP/unknown rows
are excluded using required canonical `participation_state`; missing canonical
columns or conflicting legacy state fail closed. Common
history-vintage labels survive in sample metadata. A reconstructed availability
assumption is not an authentic historical pregame capture. Joint means are
Monte Carlo summaries, and normal component-sum intervals are moment
approximations. Neither is a fitted/calibrated uncertainty result by itself.

V2 repairs three defects reported in the October 23 owner-supplied external
audit and confirmed by independent static review. V1 remains recoverable in
Git; none of the standalone model scores are recomputed or replaced. The
sampler has no live/weekly caller. This ordinary opportunity model is not a
complete official unusual-play crediting model or a qualified exact-PPR model.
No predictive or calibration improvement is established by its repair.

## Validation

The targeted suite covers the retained synthetic arithmetic tests, each missing
PPR component, rare-event/defensive-fumble scoring, signed yards, unknown/DNP
states, frozen reception arithmetic, source alteration and late clocks,
complete-history selection, trade/bye/new-player/early-season fallbacks,
shared-engine direct-versus-summed combined evaluation, deterministic coherent
joint samples, rare tied-rank zero mass and future/unknown availability attacks.
These are implementation checks, not additional football observations.
