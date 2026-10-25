# Prospective local-capture availability v1

Prepared from `e8d5c65b85ea3d639c0739e540d3441907c0cc47`. This is an
**opt-in, unwired software prerequisite**, with eighteen fictional checks
prepared but not run. It supplies no NFL forecast, accuracy result, qualified
prospective observation, durable hosted handover, or release decision.

## Problem and exact boundary

The current permitted operational source policy requires every retained week's
maximum scheduled kickoff plus seven days strictly before its as-of clock.
`features.py` also uses assumed historical availability. Exactly weekly games
can therefore lack the preceding game at the next cutoff. Those reconstructed
studies, source policies, code hashes, artifacts and results remain unchanged.

A genuinely captured final prior-game observation can have a different
prospective availability clock. This new module validates that lane explicitly;
it does not assign new clocks to old training rows or substitute current
retrieval for historical publication. The lane is
`original_local_capture_before_cutoff`. Unknown publisher publication remains
`None`, even when local availability is proven.

There is no new recorder, source endpoint, scheduler, CLI route, storage system
or default-model switch. The current single workflow remains under its
verified fail-closed guard. Existing private-durability and consumer-activation
decisions are unchanged.

## Small API

New module: `nfl_lab/prospective_availability.py` (stdlib plus existing
`state.digest` / `state.utc`). It performs no file/network access, history search,
model loading, fitting, forecast generation or state write.

1. `validate_model_contract(binding, *, expected) -> dict`
   checks a separately versioned model/availability/feature compatibility
   record against caller-authenticated expected hashes. An old manifest lacks
   the required new schema and cannot be silently reused.
2. `qualify_history_capture(version, *, query, model_binding, expected,
   parent_version=None) -> dict`
   checks one already selected prior appearance before calculation. Returns
   `ELIGIBLE` with a retained source-availability clock and original hashes,
   or distinct `DNP` / `UNKNOWN_PARTICIPATION` unavailability. Invalid identity,
   timing, primitive support or evidence raises `ContractError` with a fixed
   reason. There is no numerical zero or older-game replacement on failure.
3. `qualify_forecast_completion(availability, *, calculation, batch,
   persistence) -> dict`
   validates actual calculation and local persistence after execution, using
   the unchanged `state.capture` batch/completion schema. The result says
   `LOCAL_COMPLETION_QUALIFIED`, with remote durability and scientific
   qualification explicitly unestablished.

The two phases are necessary: a pre-calculation adapter cannot know future
calculation or persistence completion clocks. A preflight result always says
`PENDING_ACTUAL_PERSISTENCE`. It alone cannot qualify an issued forecast.

## Caller authentication and receipts

Every evidence envelope is `{document, sha256}`, hashed with existing
`state.digest` canonical bytes. The module verifies these bindings. Its caller
must first authenticate the original immutable files through existing owned
storage and source/qualification policy contracts. Supplying a matching hash
or a `qualified` string is not independent evidence of truth, rights, identity,
successful persistence or the original issue time.

The expected policy names exact statistics and independent-finality source IDs
and pins source, qualification, availability and feature hashes. The new source
policy must preserve the permitted source whitelist/rights and explicitly name
the existing final-status source. This document does not instantiate or
activate such a policy. The present seven-day policy is not relabeled as that
new policy.

### Required immutable source-success receipt

`schema_version = local-source-capture-success-v1`:

| Field | Meaning |
| --- | --- |
| `source_id`, `source_policy_sha256` | Exact permitted source and contract |
| `body_sha256`, `original_receipt_sha256` | Original body and original acquisition receipt |
| `capture_started_utc`, `body_completed_utc` | Actual request/body-completion observations |
| `persist_started_utc`, `persist_completed_utc` | Actual original local immutable-save success clocks |
| `status = success` | The save actually succeeded; failed attempts remain failed |
| `upstream_publication_utc` | Authentic publisher clock if supplied, otherwise `None` |

All clocks require explicit time zones and satisfy
`capture_start <= body_complete <= persist_start <= persist_complete`.
The success receipt can only be produced after original body+receipt saving
has completed under the existing writer/quota/immutable-save contract. Never
fill its completion from a later inventory, replay, modification time or
successful cache read. A stale cache retains its original capture clocks; a
failed refresh cannot give the old bytes a new availability time.

Both statistics and independent final-status bodies need that receipt. For a
conservative final-stat intake, the status receipt must show completed game
identity after prior kickoff and finish persistence before the statistics
capture starts. A cached pre-final statistics body cannot inherit a later
completed flag. This ordering does not prove provider final publication or
exclude later official corrections.

### Exact finality and row qualification

`completed-game-qualification-v1` binds the completed boolean, status-capture
hash, parser hash and exact game/season/week/REG/full-game-including-OT,
kickoff/team/opponent identity. `qualified-history-row-v1` binds the actual
qualified-row hash, statistics-capture hash, finality hash, qualification-policy
hash, actual qualification clock and successful immutable persistence clock.
That qualification completion is the conservative `source_available_utc`.

The history game ID must differ explicitly from the forecast game ID, even if
contradictory kickoff metadata would otherwise make the target look earlier.
The qualified row retains player identity, canonical participation state,
identity/conflict states and primitive-level support. Counts must be finite
nonnegative integers; yards may be signed. If both passing completions and
attempts are required, completions cannot exceed attempts. An explicit zero is
valid; a source-qualified sparse zero additionally requires a pinned
zero-semantics proof. Missing/null/invalid is never filled. DNP and unknown
participation are returned separately without statistical zero imputation.
Rare crediting, position/population and scoring definitions remain the original
qualifier's responsibility; this adapter adds no universal carries-times-rate
or receptions-times-rate identity.

The caller retains every planned player-game, including new/sparse players.
Absent history is an explicit unavailable slot/fallback under the candidate's
own frozen rules. This function cannot skip to an older convenient appearance,
prove full team membership, qualify an absent statistic, or establish a
participation-probability denominator.

## Timing and completion gates

Required source sequence:

`prior kickoff < completed-status capture <= final-status durable success`

`<= statistics capture <= statistics durable success <= row qualification`

`<= qualification durable success <= actual calculation start <= cutoff`

The final postflight gate adds:

`calculation start <= calculation complete <= forecast persist start`

`<= forecast persist complete <= cutoff < forecast kickoff`.

An actual original calculation receipt binds the preflight decision hash and
actual start/end clocks. The query and preflight bind a nonempty unique set of
requested target IDs. Each requested target must have exactly one matching
forecast row with that decision/calculation binding; exact future identity and
original model ID must match. Other category rows may have distinct preflight
bindings in the same batch and are not qualified by this decision. Missing,
duplicated or wrong-category rows cannot satisfy a requested target.
The existing immutable batch digest must equal the persistence receipt's batch
reference, and its late-game accounting must reconcile. A missing or late
completion never becomes success. The module does not qualify public/private
remote durability, issue horizons or model predictions merely by checking
local clocks.

## Corrections and immutable versions

An original version has no parent. An `append_correction` requires the exact
retained parent envelope/digest, same player-game identity and source origin,
and a genuinely later statistics capture. Both immutable versions remain.
Only the new capture/qualification clock belongs to the correction; its value
cannot enter an earlier cutoff. The module neither mutates state nor resolves
conflicting outcomes. Caller qualification must keep existing unresolved
identity/participation/numeric conflicts quarantined. It does not replace
`state.resolved_outcomes` or invent an upstream correction order from downloads.
Selection among available versions remains an explicit candidate/source rule,
not a new last-write-wins rule hidden in the adapter.

## Model, training and confirmation compatibility

The model contract explicitly binds model ID/artifact, training-manifest,
availability/source/qualification/feature hashes, prospective registration,
and separate training/inference availability lanes. Historical seven-day
training with authentic prospective inference is an explicit mixed-lane
candidate version, needing its own feature-shift analysis and future
confirmation. Training clocks are never backdated. A model trained under the
old source/feature policy is not made compatible merely by renaming a field.

The new feature adapter/caller and registration remain unimplemented. No old
receptions registration, engine hash, Weeks 7–14, H3 adapter, RB carry protocol
or promotion gate transfers to this version. Exposed historical periods remain
exposed. All twelve target consumers must preserve their own primitive,
population, scoring and forecasting-functional contracts; this availability
module establishes no target's predictive improvement or exact-PPR labels.

## Current loader gaps, recorded once

| Existing contract | Available now | Required new evidence |
| --- | --- | --- |
| `data._download` | Body SHA, original receipt, retrieval clock, immutable body/receipt archive | Actual source persistence-completion success receipt; `retrieved_utc` alone is insufficient |
| `operational_sources` | Exact permitted snapshot/policy/code/frame bindings; strict seven-day eligibility | Separate opt-in source/feature policy/caller, not a rewrite of that frozen namespace |
| `live.schedule_games` / grading | Completed flag, exact game tuple and source-body/status hashes | Immutable finality-capture success and exact qualified-finality receipt before statistics intake |
| `state.save` / `state.capture` | Immutable fsynced records; batch start and separate completion clock | New calculation/availability bindings in a separately versioned producer; original records cannot be retrofitted |
| Qualified participation/statistics | Supported positive evidence, preserved missingness | Independent genuine-zero support where absent; capture timing does not create zero evidence |

These fields must be produced prospectively by the existing permitted intake
and writer after separate exact integration review. They are not inferred or
manufactured here. No source values were inspected during this preparation.

## Proposed bounded software packet (not run)

`config/prospective-availability-v1-software-proposal.json` proposes one guarded
invocation of eighteen new fictional test methods in
`tests/test_prospective_availability.py`: mixed-lane/new-model contracts;
recent captured prior-game eligibility; source/feature/query version mismatch;
retrieval-only rejection; late captures; strict kickoff cutoff; finality identity
and state; pre-final cache rejection; evidence/qualifier hash bindings;
DNP/unknown/played-zero distinction; missing primitives; count/signed support;
sparse-zero proof; completion/attempt support; immutable correction parent;
actual completion receipt success; and late/mismatched completion rejection.

Ceiling: 120 wall seconds, 120 CPU seconds, 512 MiB, two threads, zero worker
children, NFL/source/model/network/CAS access or model fits/predictions. No
existing suite is rerun. Exact guarded harness/inventory and root-ledger GO are
required before any invocation. Software success would verify the supplied
contract arithmetic, not authenticate a real capture or establish readiness.
