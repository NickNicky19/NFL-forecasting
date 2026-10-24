# Exact query identity metadata version

`resolve_query_identities(query, registry, identity_sha256=...)` in
`nfl_lab.query_identity` returns `(new_query, aggregate_receipt)`. It performs no
file access, acquisition, history lookup, feature calculation, model fitting,
inference, outcome read or issuance. The caller first verifies the private
registry file bytes and selects exactly `player_id`, `sleeper_id` and
`identity_status`. The supplied SHA256 binds that exact external source version;
the adapter additionally hashes the selected registry metadata values.

The query contains exactly eleven metadata columns: `cutoff_utc`, `game_id`,
`kickoff_utc`, `opponent`, `outcome_available_utc`, `participation_state`,
`player_id`, `position`, `season`, `team` and `week`. Participation is unknown.
Statistic/target columns and already resolved output columns are rejected.
Original rows, order, index, clocks, context and dtypes are preserved. Only
`player_id` changes when an exact qualified mapping exists. Four appended
columns retain `original_player_id`, `identity_resolution_state`,
`identity_source_sha256` and `identity_adapter_version`. Unresolved identity
keeps its original namespace and explicit reason. The original inputs remain
unchanged; callers save the returned metadata as a separate private version.

A `sleeper:` alias resolves only by exact ASCII digit text and an unambiguous
`source_exact_binding` relationship. Leading zeros are retained. Registry
relations conflicting in either direction quarantine the affected aliases,
including incorrectly labeled exact rows. Missing/non-GSIS registry IDs and
missing Sleeper IDs are counted as unusable and cannot lend an alias to another
candidate. Unknown statuses or nonmissing nontext IDs fail closed. Identical
registry rows are harmless.

Direct strict GSIS text is marked verified only when present in the registry.
Outer U+0020 spaces are removed only if the remaining identifier is strict ASCII
GSIS text already present there. Tabs, Unicode spaces/numerals, embedded spaces,
names, numeric coercion and approximate matches never resolve identity.
Empty or all-whitespace query identities are rejected. Duplicate input
player-games and canonical same-game collisions reject the
whole transformation; no opportunity is selected or dropped.

The receipt contains hashes, version, row totals, resolution counts and registry
quarantine counts. It contains no aliases, canonical player rows or names, and
is deterministic for the same inputs. Metadata coverage does not establish
usable historical observations, feature timeliness, prediction accuracy or
production integration. Original frozen runtime/query versions remain immutable;
a later feature/runtime contract must explicitly adopt this new version.
