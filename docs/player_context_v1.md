# Opt-in player context v1

`nfl_lab.player_context` reads existing private source captures. It has no HTTP,
collector, scheduler, writer, model loading, fitting, prediction or automatic
activation. It does not alter frozen forecasts, populations or numeric features.
Injury/roster flags never establish game participation, healthy status or DNP.
Any numerical effects require separately registered extraction and ablation.

## Trusted input

`load_source_snapshot(manifest_path, trusted_manifest_sha256=..., source_id=...)`
requires an independently trusted lowercase SHA-256 of the exact manifest bytes.
A boolean assertion of trust is insufficient. Schema version is
`player-context-source-manifest-v1`; `sources` is a list with unique `source_id`.
Allowed identities and exact URLs are the registered Sleeper NFL players and
ESPN NFL news feed (`SOURCE_URLS`). Each source entry has:

* `source_id`, `source_url`, `body_path`, `sha256`, integer `body_bytes`;
* `receipt_path`, `receipt_sha256`;
* timezone-explicit `retrieval_started_at`, `retrieved_at`, `first_observed_at`,
  `captured_at`, in that order (equality allowed);
* `clock_basis="local_capture_receipt"`, `upstream_publication_at=null`.

The receipt repeats every source identity, body hash/length and clock/basis field.
Paths resolve relative to the manifest directory unless absolute. Every adapter
rechecks manifest, receipt and body hashes and duplicate JSON keys. SourceSnapshot
retains immutable bytes; decoded output is advisory and never accepted back as
trusted input. A changed file cannot replace bytes in an already loaded version.
An exact version binds both body and receipt hashes. Identical body bytes with
different authenticated capture receipts remain distinct versions; repeated
identical versions add no evidence. Conflicting bodies at the latest equal capture
clock cause abstention.

`first_observed_at` means the first **complete local body observation**, preferably
equal to retrieval completion. It is neither upstream publication nor first
historical availability. All capture evidence must precede cutoff strictly.
Historical `injury_start_date` and `news_updated` are retained source values and
never substitute for availability. Explicit positive finite freshness is required.
Packaging delay cannot freshen a body: direct freshness uses first observation.

## Advisory APIs

`sleeper_context(snapshot, identity_bindings=())` retains every provider record,
including inactive players, non-skill positions and unlinked identities. Field
descriptors preserve `absent`, JSON `null`, `empty` string/container and exact
`value`, including false and zero. The exact original record is retained privately.
Missing injury fields never become healthy. `participation_state` stays `unknown`.

Optional exact crosswalk rows contain string `sleeper_id`, GSIS `player_id` and
optional `team`. Names are never used as joins. Provider map key must equal its
embedded string player ID. Invalid IDs, conflicting GSIS bindings, duplicate GSIS
owners and conflicting registry/source teams quarantine affected records. Unknown
team cannot satisfy a requested team. A valid unlinked player keeps explicit
`sleeper:<source-id>` identity and the existing forecast fallback.

`player_context_asof(snapshots, cutoff_utc, sleeper_id=..., max_age_hours=...,
player_id=None, team=None, identity_bindings=())` selects the newest exact capture
strictly before cutoff. A missing/quarantined player in that capture does not
fall through to an older roster record. Stale sources, identity/query conflicts
and missing versions return explicit fallback reasons. Advisory availability never
changes an existing forecast or its fallback.

`news_context(snapshot, identity_bindings=())` reuses canonical observation
normalization. Crosswalk rows contain string canonical decimal `espn_id`, GSIS
`player_id` and optional `team`. ESPN integer source ID tokens have an explicit
lossless decimal representation; float/bool/name/whitespace/leading-zero tokens
cannot bind. Category IDs establish **mentions only**, never the subject of an
injury claim. Excerpts remain `reporter_interpretation`, with original text,
field states, premium flag and source clocks preserved. No article bodies are
fetched. Unknown or conflicting entities remain unbound.

`news_context_asof(..., max_snapshot_age_hours=..., max_content_age_hours=...)`
first gates the exact captured feed, then reuses canonical `observations_asof`.
Unknown publication, later-than-retrieval source clocks, old content and invalid
update order are ineligible. A local retrieval never substitutes for publication.
Article/category rows remain distinct even where canonical prose IDs coincide.

## Explicit cache replay

A separately declared cache replay can add `capture_mode="authenticated_cache_replay"`,
`clock_basis="local_cache_replay_receipt"`, `source_vintage_at`,
`origin_receipt_path` and `origin_receipt_sha256`. The wrapper receipt repeats mode,
vintage and original receipt hash. The original receipt is retained as immutable
bytes and must bind `url`, body `sha256`, integer `bytes`, and timezone-explicit
`retrieved_utc` exactly equal to `source_vintage_at`, before local replay start.
All four new wrapper clocks describe the replay only. Eligibility begins after
the new wrapper capture; original missing capture clocks are never invented.
Freshness uses the original retrieval and news clock validation also uses that
original retrieval, so later wrapping cannot rejuvenate old source content.

Software fixtures are entirely fictional. Passing them establishes software
behavior only; it does not qualify current source coverage, an extraction model,
forecast accuracy, causal injury effects or all twelve target effects. Raw source
text, player records/IDs and row-level derivatives stay private.
