# Shared data and feature contract

`acquire_history(cache: Path, seasons: list[int]) -> dict` performs free public
HTTP acquisition with three bounded attempts, a 50 MiB per-source limit,
timeouts, atomic writes and SHA-256 verified cache reuse. `cache` is shared at
`/workspace/NFL-forecasting/data`; source files and receipts live in `raw/`.
Acquisition uses two concurrent HTTP workers. Current UTC-year statistics,
weekly rosters and snap counts, plus schedules, players and the NGS inventory,
refresh at most once per UTC day. Historical season files retain the campaign's
fixed current-vintage version. Before a mutable body or receipt is replaced,
its exact bytes are preserved under `raw/versions/<body-sha>/<receipt-sha>/`.
Failed daily refreshes retain the old body, SHA and original `retrieved_utc`;
the returned and persisted receipt has `status=stale_cache`, `stale=true`,
`refresh_error` and `last_refresh_attempt_utc`. A repeated invocation that day
reuses that explicit stale result; the next day permits another bounded attempt.
Freshness/cutoff acceptance remains the forecast consumer's responsibility.
`fetch_cached_json(cache, name, url)` reuses the same cache for named immutable
or date-specific captures. Original retrieval times survive restarts.

`load_history(cache, seasons) -> pandas.DataFrame` is offline. It normalizes the
nflverse `stats_player_week_YYYY.parquet` schema, weekly rosters, PFR snap counts,
the current player GSIS/PFR registry and schedules. The retired legacy stats
schema remains readable as an explicit compatibility path. The legacy 2025
endpoint returned 404 during acquisition, so real acquisition uses the newer
weekly source consistently for every season.

Required output columns are `season`, `week`, `game_id`, `player_id` (GSIS),
`player_name`, `team`, `opponent`, `position`, `kickoff_utc`,
`participation_state`, `pass_yd`, `pass_td`, `pass_cmp`, `pass_att`, `pass_int`,
`rush_yd`, `rush_att`, `rec`, `rec_yd`, `rush_rec_yd`, `fantasy_ppr`, `anytime_td`.
Additional outputs include `rec_tgt`, `rush_td`, `rec_td`, snap counts,
participation evidence, roster status, home/away, full-team statistical totals,
`outcome_available_utc`, `historical_publication_utc` and `history_vintage`.
`load_identity(cache)` exposes exact GSIS/PFR/Sleeper source bindings; conflicting
GSIS/Sleeper mappings are quarantined to null bindings with explicit status and
candidate IDs rather than using player names or choosing one silently.

The population includes offensive QB/RB/FB/WR/TE active and explicit inactive
weekly roster rows plus observed statistical/snap participants. Pure reserve
and practice-squad records do not establish game eligibility. A recorded weekly
statistical event or positive snap count establishes `played`; explicit weekly
`INA` establishes `DNP` when there is no positive participation evidence. Missing
statistical rows alone yield `unknown`. Snap-only played rows keep missing
outcomes. Known played zeros stay zero. DNP missing outcomes are not imputed.
Anytime TD is the binary event of at least one rushing or receiving touchdown.
The historical NFLverse derivation requires both components. The live scorer
can establish a positive event from one recorded positive component; a zero
requires both. Combined yards requires both yardage components.

`fantasy_ppr` is null because nflverse totals do not provide an authenticated
crosswalk for every pinned website Sleeper scoring component and defensive
fumble-recovery adjustment. The generic provider PPR total is not substituted.
The [component audit](ppr-component-coverage.md) qualifies twelve common NFLverse
components, including all-phase lost fumbles, but leaves six rare credit bridges
unqualified. Sparse Sleeper omissions do not establish explicit zeros.

`build_features(history) -> pandas.DataFrame` preserves original rows and index
and adds numeric `f_` columns. Player windows are the last three/eight eligible
earlier games; unknown intervening games consume slots and valid counts are
reported. Inputs include all targets, targets/carries, snap counts, known
participation rate and pooled efficiency with matching numerator/denominator
availability. Team features use full-team totals before filtering player
positions, prior pass/rush opportunity volume, pass ratio, opponent allowed
totals and earlier-opponent-adjusted offensive/defensive residuals shrunk toward
earlier league averages. Schedule inputs include home/away and days since the
team's previous game. Pass attempts plus rush attempts is a play-volume proxy;
neutral-situation pace, sacks and clock pace are not claimed.

Each row may supply `cutoff_utc` at or before kickoff. Default cutoff is kickoff;
an outcome enters features only when its `outcome_available_utc` is strictly
before that cutoff. The historic adapter assumes availability seven days after
kickoff. This conservative lag is a declared research assumption, not evidence
of authentic historical publication. `feature_max_source_available_utc` records
the latest assumed outcome clock used, including league adjustments. All
historic data are current-vintage reconstructions. Roster publication clocks and
historical revisions are unverified; these tables cannot substantiate a
prospective forecast or a historically authentic pregame source population.
Live features currently retain that conservative seven-day policy as well;
it can omit recent statistics already present in a current intake. A separately
tested availability policy is needed before attributing gains to using them.

Acquisition receipts include exact URL, bytes, SHA-256, retrieval time, HTTP
Last-Modified/ETag when present, source transition, rights and optional group
state. The nflverse hosting repository reports CC-BY-4.0; upstream PFR/NFL/NGS
rights remain separate. Raw sources and row-level derived history/features stay
ignored locally; this lab has no raw redistribution authorization. Review any
public derived export separately.

NGS assets were verified through the public release inventory and tested in a
separate finite ablation; NGS features are not enabled. Timestamped public news
observations have an optional adapter. News/injury numeric effects, routes,
coaching/scheme, private tracking and authentic forecast-weather features are
not enabled. Their absence is explicit in
the acquisition/feature manifests. Optional snap-count source gaps do not stop
supported statistics or turn missing rows into DNP.
