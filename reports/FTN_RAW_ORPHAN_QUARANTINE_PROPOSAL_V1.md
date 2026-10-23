# Raw-orphan quarantine prerequisite v1 — proposal only

Status: **not implemented, not registered for execution, not run**. This document
authorizes no new query or join. The original strict zero-join helper, its code
hash, failed run, source policy and accepted population remain unchanged.

## Purpose and fixed scope

The executed [context diagnosis](FTN_CONTEXT_METADATA_RESULT_V2.md) identified one
null raw `player_id` among 67 fixed-game records. One position is also null;
whether those nulls share a record is unknown. A missing identifier must remain
unidentified. Rejecting an unidentified record as a usable player join key need
not erase that record or every independently qualified offered/witness player.

Propose one new structural adapter version for the same source hash, fixed game
and complete original eight-column context projection. Preserve all 67 planned
raw rows, including the orphan, before considering any primitive-statistics
projection. No source substitution, additional game, identity inference, player
selection or statistical imputation belongs in this prerequisite.

## Required behavior

1. Preserve an immutable complete projected record inventory. A private local
   record locator may use its projection hash plus row ordinal. That locator is
   provenance for an unidentified source record, never a fabricated NFL player
   ID or a claim about an original physical file-row offset.
2. Put each missing-ID raw record into an explicit
   `QUARANTINED_MISSING_PLAYER_ID` record bucket. It cannot supply a player's
   statistic, zero, participation evidence, position or missing-value repair.
   Do not infer its identity from names, roster order, a singleton unmatched
   player, another field, or elimination. Keep its raw record and quarantine
   reason in private coverage; publish only counts.
3. Retain every canonical identified raw record. Preserve duplicate-ID groups
   as ambiguous groups rather than choosing one row. Existing unrelated context,
   team/opponent, timing and source checks stay strict. This proposal changes
   disposition of missing identity to explicit quarantine; it does not permit
   malformed nonnull identities or arbitrary context failures to pass.
4. Flag missing position separately from missing identity without assuming any
   overlap. Do not copy another record's or an offered player's position into the
   raw source. Existing independently qualified offered/history position rules
   remain a separate contract; this prerequisite establishes no new position.
5. Preserve the full outer known-player union of all canonical raw identities,
   all original offered identities and all 92 authenticated FTN witnesses. Keep
   unmatched offered/witness members visible even when they have no raw match.
   The orphan record remains an additional unresolved record denominator, not
   an identified member of that union. No complete-case or positive-activity
   selection is permitted.
6. Report both record coverage and known-player coverage. At minimum reconcile
   `raw_planned_rows = identified_raw_records + missing_identity_raw_records`,
   with ambiguous groups and position flags reported separately. The expected
   planned count is 67 under the pinned source; the known-player unique count
   remains to be measured. Do not overwrite a 66-record identified-view count
   with 67 or pretend the unchanged strict helper consumed the full inventory.
7. Enforce the registered 200-row cap on the complete raw inventory. A future
   union cap must include known-player union size plus unresolved raw record
   count as conservative planned units; no orphan can disappear from resource
   or coverage denominators.

## What this could enable later

A later separately registered candidate audit may use the structurally qualified
identified view while retaining the complete raw/orphan inventory and every
offered/witness opportunity in its new output contract. A known offered player
without a raw match stays unresolved; the orphan cannot fill that gap. Missing
statistics do not become zeros, and an FTN appearance alone does not establish
all target statistics, DNP, exact PPR or historical pregame availability.

Any future component projection, candidate-zero audit or accepted-label change
requires its own exact version, inputs, state/coverage rules and authorization.
This context-only proposal includes no primitive-statistics read, numerical
join, applied label, model fit, accuracy score or forecasting promotion.

## Execution conditions before any future run

The integrator must first approve the concrete adapter scope, freeze code/input
and configuration identities, register one finite invocation and obtain
independent review. Preserve the successful sequential storage architecture and
unchanged original quota/ownership helpers. Proposed upper bounds remain
60 seconds wall/CPU, 256MiB combined RSS with the existing safety margin,
one numerical thread, zero HTTP/fits/scores/retries and at most 1MiB new retained
outputs under the shared 512MiB quota. No resource increase or weaker check is
needed merely to state this proposal.

Acceptance must reconcile every planned raw record and every offered/witness
identity, retain the unidentified record, avoid identity/statistic repair, and
show all quarantine/fallback coverage. Static software checks and a successful
structural run would qualify only this prerequisite; neither would demonstrate
better NFL forecasts. No code or new data execution accompanies this document.
