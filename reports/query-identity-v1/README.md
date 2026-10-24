# Exact cached identity adapter: completed metadata acceptance

2026-10-23. **Historical identity matches rose from 90 to 585 of 681 rows.**
This is metadata coverage, not a forecast accuracy improvement.
[Measured aggregate](aggregate.json), [adapter](../../nfl_lab/query_identity.py),
[contract](../../docs/query-identity-v1.md), [registration](../../config/query-identity-v1.json).

The earlier [reference runtime](../reference-runtime-v2/README.md) exposed heavy
prior fallback. Its frozen query mixes GSIS, Sleeper-prefixed and outer-space
GSIS IDs. This new, isolated adapter resolves exact source-qualified mappings
while preserving every original input, forecast and experiment registration.

## Actual cached-data result

| Resolution | Rows |
|---|---:|
| Existing strict GSIS verified in registry | 93 |
| Exact, unambiguous Sleeper-to-GSIS mapping | 493 |
| Registry-qualified GSIS after outer ASCII-space trim | 38 |
| Unresolved: no exact available Sleeper binding | 57 |
| **All original rows retained** | **681** |

531 IDs changed in the **new private metadata version**. Exactly 585 output IDs
match the historical identity table, versus 90 original matches. **96 still lack
historical identity matches**, including 39 registry-resolved identities and
57 unresolved aliases. No missing history was labeled rookie, played zero or
DNP. Registry membership does not prove game-day eligibility or participation.

All 681 rows, 13 scheduled games, original aliases, row order, context and clocks
were retained. Same-input replay and private serialized-output replay agreed
exactly. Original files remained byte-identical. No fuzzy names, numeric ID
coercion, leading-zero deletion or new source acquisition was used. Ambiguous
associations are quarantined; canonical same-game collisions reject the batch.
Unavailable registry bindings are not discarded football outcomes. Cleared
ambiguous aliases cannot be assigned to particular unresolved queries.

The one real acceptance took **2.339 seconds wall, 2.762 seconds CPU and
401,600,512 bytes sampled combined RSS**, two threads. Shared retained unique
file bytes were 33,492,035 at the supervisor snapshot, below 512 MiB. Canonical
rows, aliases, registry and source bodies remain private.

## Verification and limits

Forty new fictional tests passed. The root's 70 targeted integrated checks
include those 40 and the existing reference/runtime contracts; these counts
overlap. The earlier 789-check regression result remains unchanged. A first
fictional initializer typo produced 27 failures/9 passes; it was repaired and
retained before any real acceptance. No checks or data rules were weakened.

A separate read-only reviewer checked the code, supervisor, all 70 frozen
bindings, resource/phase receipts and private output hash. The reviewer did not
decode real canonical rows or independently verify provider identity truth.
Integrity and deterministic mapping acceptance do not certify upstream facts.

**Zero models were fit or invoked, zero accuracy scores were computed, and zero
official forecasts were issued.** Usable history windows and forecast outputs
with these newly resolved IDs have not yet been measured. The original 22
reference packages still bind their original query bytes. Adopting this adapter
requires a new explicit feature/input/runtime version; it cannot silently change
old bindings or backfill the receptions experiment.

All twelve scientific decisions remain unchanged, including the blocked exact
PPR outcome contract. Current population eligibility, corrected-input feature
and runtime acceptance, hosted handover, and the source-matched CDF/boosting
comparison remain necessary. No workflow, scheduler, website or default model
was changed by this packet.
