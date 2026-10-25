# Dynamic opportunity history adapter v1

Prepared from `e27c2f4d20ad57d602515d59522a0ad9922bcb6a`, implementing one narrow
prerequisite of `docs/dynamic-opportunity-screen-v1-draft.md`. This packet reads
code/metadata only. No NFL value, source body, model, fit, forecast, HTTP or CAS
access occurred. Eighteen fictional test methods are prepared, not invoked.
The actual 54-package study remains separately unregistered and unconsumed.

## API and retained boundaries

`nfl_lab/dynamic_opportunity_history.py` is pure stdlib plus the unchanged
`state.digest/utc` and tested dynamic core's `Slot`, `Query`, `paired_count`
and version/role constants. It calls no filter, prior formation, static formula,
prediction, scorer, file opener or source loader.

1. `build_recorded_proxy_panel(calendar, credit_rows, *, task, source_binding,
   asof_utc, requested_player_ids=())` produces recorded all-position carry or
   credited-target proxies and explicit completeness/missingness receipts.
2. `build_offer_windows(offers, calendar, membership_rows,
   qualified_player_rows, proxy_panel, *, task, source_binding)` produces exactly
   one request/fallback per original offer, preserving its identity, original
   fields, order and baseline reference. Duplicate original offer IDs fail;
   they are never silently deduplicated into fewer planned opportunities.

Modeled roles remain RB carries and RB/WR/TE auxiliary targets. Other roles,
unlinked identities, unsupported spells, missing volumes and invalid pairs
retain explicit original-reference fallback requests. No fallback point is
invented by the adapter. Actual canonical-category references remain the exact
source-matched CDF products under their own contracts.

## Source and timing lane

The required source binding pins the original permitted policy/manifest,
statistics body hashes by season, raw calendar hash plus complete normalized
calendar-row inventory digest, qualified history frame, qualification policy,
and derived membership/spell manifest. The caller must authenticate these
against actual original owned immutable files. Hashes and supplied `qualified`
states alone do not establish truth, rights or complete participation.

Only `reconstructed_kickoff_plus_7_days`, REG and seven days are accepted here.
Each slot's `available_utc` is exactly its kickoff plus seven days and must be
strictly before the query cutoff for a statistical update. The distinct new
prospective-capture availability lane is rejected; it cannot silently enter
these old features or trained artifacts. Original reconstructed publication
limits and exposure remain disclosed. This adapter creates no authentic
historical issue or source-publication clock.

Calendar metadata must contain unique reciprocal team sides, exact
season/week/game/team/opponent/kickoff, with no ambiguous team-week or duplicate
game/team. Each game ID has exactly two sides; two reciprocal pairs/four teams
cannot share one ID. The offer's week/REG context must match the calendar, and
supplied player-row week/type conflicts are rejected. The nonempty source
season map must contain every calendar/source-row season, and both each row's
body SHA and the bound season SHA must be explicit valid matching hashes;
missing values cannot authenticate through `None == None`.
A slot whose statistics are unavailable still consumes elapsed
team-game time. Post-cutoff primitive counts are not accessed by proxy/window
construction. Cutoff must precede the target kickoff and the proxy panel's
as-of cannot exceed the query cutoff.

## Recorded-credit proxies, not complete NFL totals

Aggregate before position or requested-player filtering. Every count is an
explicit official field; a raw zero requires no fictional individual appearance
claim merely to contribute zero to a recorded sum. At least one supported
explicit count is required: empty/all-missing remains unavailable. Negative,
fractional, boolean and nonfinite counts are invalid. Duplicate canonical
player/team/game records or repeated physical row pointers block the affected
proxy; no convenient copy is selected. A repeated pointer attributed to two
groups blocks both.

Receipts retain rows/explicit/missing/invalid/duplicate counts, known-team
orphan-player rows and credits, credits outside the explicit requested-player
set, and unmapped team/game source-row pointers. Known-team orphan credits are
recorded under their actual raw team identity; unmapped credits are never
assigned to a convenient team. Neither is a certified residual bucket.

Missing fields and recorded orphan credits make the coverage visibly partial.
Admitted groups are named `RECORDED_PROXY_ONLY` and **always** retain
`all_nfl_credits_complete=false`. This admits an explicitly named partial-credit
modeling hypothesis, not an exhaustive NFL denominator or finite team
allocator. A player exceeding that proxy triggers baseline fallback; no
clipping, rescaling, unknown-to-zero or normalization repairs it. Duplicate or
invalid groups cannot supply a likelihood update or a target volume.

## Same-team/season windows and membership prerequisites

The offer carries a derived, source-authenticated spell descriptor:
player/team/season, spell ID, boundary start/kind and membership-manifest hash.
Supported boundaries are season start, verified team change, or verified cold
start. A season-start boundary cannot hide earlier calendar slots. A missing
roster row does not establish a cold start, membership, DNP or played zero.

From the complete calendar after that boundary, take the latest eight elapsed
same-team/season game slots, including unknown/DNP/missing statistics. Do not
search older games to fill invalid or missing selected slots. Each selected
slot requires matching same-spell membership context. Ambiguous or missing
membership consumes its position and blocks the fixed window, retaining the
full selected-slot audit and original fallback. Genuine short/cold windows are
allowed only with the authenticated boundary. The current shared normalized
history does not already supply this new spell manifest; its deterministic
source-bound derivation must be reviewed before actual NFL execution.

Qualified player rows retain played/DNP/unknown separately. The existing
permitted qualifier currently proves no confirmed DNP, so the adapter cannot
manufacture any from INA. A played count needs explicit field support; sparse
zero additionally needs its own zero-semantics binding. Independent appearance
plus an absent count is still missing. Counts and denominator use the same
player-game context; invalid pairs remain visible and cannot get clipped.

## Fixed volume and static control

- Carry volume is the exact original query `f_team_rush_att_mean3`, including a
  supported zero. It is not recomputed, replaced or normalized.
- Target volume is separately named
  `recorded_target_credit_proxy_mean3_finite_slots`: select the latest three
  elapsed same-spell team-game slots and average their finite admitted recorded
  proxies, requiring at least one. Missing slots remain missing and consume
  positions; there is no older-game substitution. Report selected/supported/
  missing counts and retain `all_nfl_credits_complete=false`. This is a new
  feature definition shared identically by dynamic and static comparisons.
  Attempts, offense-plays proxies and offered-receiver sums never define it.

The returned static-control request binds the exact same history and query
digests, fixed volume, earlier-training prior and selected kappa. This module
does not evaluate its formula, learn a prior, select a setting, attach a law or
call the six-setting filter. Later orchestration must use identical information
and category fallbacks for both candidates. Conditional individual means do
not become a coherent unconditional team allocation.

## Small eventual data-read plan, not authorization to run

No NFL source values or Parquet row groups are read in this preparation. A
later independently reviewed, finite registration must pin these existing
private files and exact column/predicate roles before any source-value read:

| Input | Small allowed projection / responsibility |
| --- | --- |
| Existing full permitted REG calendar | Game/season/week/type/date/time/home/away metadata; exact reciprocal team mapping and complete inventory |
| Existing retained official all-position weekly statistics | Exact player/season/week/REG/team-or-recent-team identity, carries and targets, physical row pointer/body hash; derive proxies before role filtering |
| Existing permitted qualified history | Exact player/game/team/opponent/season/role/participation, selected carry/target primitive/support and original seven-day clock; do not reimport PFR/snap data or infer unknown fields |
| Existing weekly membership/identity source | Exact earlier player/team/period identities and conflicting/unknown states; deterministically version spell boundaries, without claiming injury/starter/playing facts |
| Frozen original queries and controls | Original keys, cutoffs, role, unchanged carry-volume feature and exact baseline references; projected before any outcome scoring |

The eventual executor must push source REG/season/week/team predicates before
decoding statistics, use exact calendar joins, and bind each history-role read
to cutoffs strictly after its original seven-day availability. Prior training
remains earlier seasons only. Within-season earlier-game counts used as later
history are explicitly **feature-role outcomes**, not an assertion that no
outcomes were read. They cannot enter an earlier query. Query-target and later
game values are excluded from that query's inputs; evaluation labels/losses
wait for the registered global forecast freeze. Cache each admitted source
version/request once and record columns, predicates, roles and coverage; this
packet creates no second pipeline or acquisition route.

The planned years and all exposed periods remain exactly the original draft;
do not read 2025/2026 NFL values here. The existing 54-package numerical budget,
chronological recipe selection, shared evaluator and future confirmation remain
unconsumed. Exact source-bound spell formation, source projections, unchanged
CDF/control product binding and later fixed catch/YPT propagation are further
reviewed executor prerequisites, not completed NFL comparisons.

## Proposed software scope

One separately authorized invocation of eighteen new fictional methods under
120 wall/CPU seconds, 512 MiB, two threads, zero worker children/NFL/source/model/
network/CAS/fits/predictions. Reuse the accepted ready/GO startup and explicit
PID/startticks/RSS/PDEATHSIG guards. No existing suite or dynamic filter run is
repeated. Core numeric support validation is exercised through this new adapter
callsite only. Exact immutable code/environment/inventory and independent
PREEXEC plus root ledger GO precede any invocation. Fictional software success
would establish contract behavior, not genuine completeness or a forecast gain.
