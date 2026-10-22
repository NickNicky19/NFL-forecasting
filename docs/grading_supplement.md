# Cached NFLverse grading supplement

`load_cached_grading_context(cache, seasons)` verifies exact source SHA-256 values
against cached raw bytes before calling the existing offline `load_history` and
`load_identity` functions. It performs no downloads and creates no official
outcomes. Its only materialization is the shared loader's ignored processed
history. Every cached weekly crosswalk used by identity resolution is verified.

`cached_nflverse_outcome(context, forecast, completed_game, status_receipt=None)`
returns a candidate supplemental observation. The caller must provide an
independent boolean completed flag, the provider game ID and the provider
schedule's kickoff/home/away. The provider ID must match the frozen forecast ID.
NFLverse's different canonical game ID is bound by exact season, week, team,
opponent and kickoff. Ambiguous or mismatched identities remain unsupported.

Frozen GSIS IDs remain exact. A frozen `sleeper:<id>` namespace resolves only
through a unique verified `source_exact_binding` GSIS/Sleeper crosswalk.
Conflicting/unknown bindings are quarantined. Original forecast IDs are retained
as state keys; canonical NFLverse IDs are additional provenance.

Only recorded weekly statistics for known played players supply numeric values.
A recorded zero remains zero. Missing statistics, snap-only played records,
unknown participation and DNP never become inferred zeros. Signed yards remain
signed. Combined yards requires both components; exact pinned PPR remains
unsupported. Statistics snapshots captured before kickoff or after the grading
context's clock are rejected. Independent completion establishes the game state;
the source's final-publication clock remains unverified.

The live adapter retains independently qualified observations from both
providers, including supported zeros missing from the sparse primary source.
The helper does not choose a winner between conflicting providers or establish
correction precedence. Conflicts remain quarantined; unchanged target content
is deduplicated by the shared outcome writer. Original
retrieval clocks, source SHA-256 values, stale status, refresh errors, exact
bindings and gap reasons are retained. `source_timestamp` remains null: HTTP
file vintage and retrieval do not establish football-statistic publication or
correction order. Conflicts therefore need the existing quarantine policy.

These records are current-vintage source observations, not authentic historical
pregame evidence. Raw source and row-level derived data remain ignored locally;
no raw redistribution, website writes, new credentials or paid source is used.
