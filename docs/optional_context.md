# Optional context adapter v1

This module is a separate input candidate for a new registered ablation. It does
not change `data.py`, `features.py`, frozen models, campaign definitions or base
feature values. No models were fitted during the adapter's source check. A later
separately registered development study is described below; no candidate is qualified.

## NGS records and features

`load_ngs(cache, seasons)` reads exact asset URLs from the cached nflverse NGS
inventory and acquires supported public passing, receiving and rushing CSV.gz
assets through the existing bounded source cache. It uses two workers and
rejects inventory URLs outside the exact supported release path. Inventory
assets above 5 MiB are rejected. Raw files and source receipts remain ignored.
NFL/NGS upstream rights remain separate; raw or row-level redistribution is not
authorized by this lab.

Source GSIS IDs must exist in the cached registry. Weekly records bind to exact
season/week/team schedule keys; player names are never identity keys. Week-zero
season totals are excluded. Duplicate player/week records fail. Unknown IDs and
unmatched schedule rows are counted in the manifest and excluded. In particular,
the source postseason calendar has some unmatched late-week records; no guessed
calendar conversion is applied.

The returned table has GSIS `player_id`, `game_id`, `season`, `week`, `team`,
`opponent`, `kickoff_utc`, fourteen numeric metrics, per-group retrieval and asset
update clocks, `published_utc`, `updated_utc`, `available_utc`,
`availability_basis` and `history_vintage`. Original weekly publication/update
clocks are unknown. GitHub asset update dates describe file vintage and are not
treated as authentic weekly publication. `available_utc=kickoff+7 days` is an
explicit reconstruction assumption.

`merge_ngs_asof(history, ngs)` preserves rows, indices, outcomes and existing base
features. It adds 28 numeric columns named `f_ngs_<group>_<metric>_mean3` and
`f_ngs_<group>_<metric>_n3`, plus a latest-used availability clock and vintage
label. The three slots are earlier roster games whose assumed outcome clocks
precede the target cutoff; missing NGS observations consume slots. A metric must
also be available strictly before cutoff. The adapter enforces the seven-day
floor and any later supplied publication/update clock. Inputs more than sixty
days after their source game are stale and excluded. Unreported values stay
missing, counts stay explicit, and no old-season carryover fills current gaps.

The passing metrics are time to throw, intended air yards, aggressiveness,
expected completion percentage and completion percentage above expectation.
Receiving metrics are cushion, separation, intended air yards and YAC above
expectation. Rushing metrics are efficiency, eight-defender exposure, time to the
line of scrimmage, yards over expected per attempt and percentage over expected.
Provider units are retained, including its percentage/ratio conventions.

A real 2022–2023 development-only source check acquired six assets totaling
434,656 bytes. It accepted 4,964 distinct player-games, excluded 419 week-zero
aggregate rows and 19 unmatched schedule rows, and found no unknown GSIS IDs.
For 18,128 history rows, 6,274 had at least one prior NGS mean; source loading and
feature generation took 3.114 seconds. Exact source hashes, individual exclusions
and unavailable assets are in ignored `context_ngs_manifest.json` and
`context_ngs_profile.json`. These were coverage/correctness observations before
the separately registered development study.

The available archive does not supply recent 2025–2026 aggregates. These old
inputs therefore cannot fill current forecasts under the sixty-day rule.
Prospective NGS qualification remains pending an available timely source and a
separate registered protocol. Reconstructed history cannot authenticate an
original pregame snapshot.

## Structured public observations

`normalize_observations(records)` retains caller-supplied exact source text and
structured fields. Required fields are `source_url`, `group`, `claim_type` and
`claim_text`. Groups are `news`, `injury`, `environment`, `scheme` or
`source_feature`. Claim types are `reported_fact`, `coach_statement`,
`reporter_interpretation` and `model_hypothesis`; these remain distinct. A supplied
`fact` type is normalized to `reported_fact`. Optional structured fact names,
values, units or confidence fields are retained without deriving them from prose.

Publication, update and retrieval clocks are timezone-explicit. Missing clocks
remain missing. Publication/retrieval must be known, update must not precede
publication, and publication/update must not be later than retrieval. Invalid
or unknown clocks are labeled and excluded from authenticated as-of selection.
Credentials in source URLs and player-name identity substitutions are rejected.

Deduplication uses exact source URL after removal of tracking parameters,
entity, claim type/group and normalized text. The stored claim text itself is
unchanged. Earliest authenticated duplicate snapshots survive; changed text is a
new observation. Different independent source URLs retain their own evidence.
Raw source snapshots remain cached. `observations_asof` rechecks clocks, requires
availability strictly before cutoff, supports exact player/team filters and
defaults to a seven-day content-age limit. A later retrieval does not make old
content fresh.

`load_public_news(cache)` optionally captures the free ESPN NFL public news feed
into a date-specific immutable cache file. It preserves feed excerpts, article
IDs, publication/update/retrieval clocks and the premium flag without retrieving
article bodies. Article categories bind to exact ESPN/GSIS registry IDs; they
establish a source mention, not the subject of a particular injury claim.
Unbound articles remain unbound. Feed text defaults to reporter interpretation;
the collector does not infer injuries, coach intent, private schemes or a
structured fact from an article description.

One real current snapshot had fifty articles with publication and update clocks,
yielding 110 normalized entity observations, including 98 exact category-ID
bindings. Its SHA-256 is
`2fb6d6d9de8fe1f74159b345e59d4c1d6229b8d2536c7946a14497b1f7a4f696`;
retrieval was `2026-10-22T12:51:47.397780+00:00`. Only schema/counts/clocks were
inspected; no claims were used as numerical features or for model fitting.

These observation functions emit no numeric `f_` features and never override a
forecast from a narrative. Injury, news, environment and scheme effects still
need explicit permitted structured sources, predeclared transformations and
separate ablations. Authentic historical news/injury snapshots, forecast weather,
routes, premium tracking and private playbooks remain unavailable here. This
adapter does not establish those mechanisms or fill them with invented claims.

## Subsequent bounded development study, 2026-10-22

`config/context-study.json` was committed before fitting. Eleven new fixed
ridge/logistic fits added prior NGS features and reused unchanged 2023 ridge
controls from the initial campaign. All 6,173 paired outcomes per target and
the base97 feature values were checked for exact agreement. Training used
2019–2022; evaluation used already exposed 2023 development only. No new 2024
testing or future confirmation was used.

Only three primary losses improved: rushing attempts 0.7781%, receptions
0.0330%, and passing yards 0.00429%. The other eight targets worsened. These
small descriptive changes do not qualify or activate an NGS challenger.
Current NGS coverage remains unavailable. New fits took14.06 seconds; all
results, parameters, warnings and failed-status slots are retained privately,
with reviewed derived aggregates in `reports/ngs-context-study/`.
