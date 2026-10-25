# Participation and FTN documentation qualification

Documentation only; no dataset rows were acquired or opened. Seven of eight
permitted connected GitHub calls were used, with no retries or direct HTTP.
The official NFL gamebook route remains **NOT_CLEARED**. No source policy,
existing inputs, learner, evaluator, scheduler or publication setting changed.

## Source facts and limits

| Source | Supported documentation | Qualification limit |
| --- | --- | --- |
| nflreadr participation | Loader attributes seasons before 2023 to NFL NextGenStats and 2023 onward to FTN Data. It supports seasons from 2016. The schedule says the NGS feed ceased during 2023. FTN participation is supplied after **all postseason games finish**, with no in-season updates. | This is a retrospective appearance lead. It cannot supply contemporaneous 2026 participation features or authenticate historical pregame availability. The transition and each asset's provenance still need validation. Current source policy excludes NGS. |
| Participation dictionary | `nflverse_game_id`, `play_id`, `players_on_play`, `offense_players`, `defense_players`, `n_offense`, and `n_defense` describe game/play keys and on-field GSIS identifier lists/counts. | An authenticated player list could provide a positive appearance witness without a positive statistical credit. Documentation does not establish every game's/play's completeness, special-teams inclusion, DNP/nonappearance, list encoding or all field/season coverage. Absence from a list is not DNP. |
| FTN charting | A manually charted **subset**, available from 2022, with charting stated to occur within 48 hours after each game. The nflverse schedule polls at 00:00, 06:00, 12:00 and 18:00 UTC; actual new availability depends on FTN. | These statements do not apply to postseason participation. Polling/charting windows are not authenticated row-publication clocks. This is a contextual play-feature lead, not a participant panel. |
| Charting dictionary | Game/play identifiers, pre-snap/play indicators, defender counts, quarterback read categories, and `date_pulled`; the latter is nflverse's FTN API retrieval time. No player-appearance list is documented. `read_thrown` primary-read code `0` starts in 2023; 2022 primary reads are missing. | Retrieval time is not the original publication time. Missing 2022 codes must not become zeros. Charting cannot independently establish a player's appearance or statistical zero. |

Neither source documents complete special-teams coverage or an explicit
statistical-zero/nonappearance contract. Appearance alone never fills a missing
statistic. A later join may retain an already explicit supported zero and add an
independent positive appearance witness; it must preserve missing outcomes and
unknown participation elsewhere. No complete denominator or exact PPR contract
is established here.

## Rights and ownership

Both loader documents expressly identify the **data** as CC BY-SA 4.0. They request
attribution to **FTN Data via nflverse**, or **NFL NextGenStats via nflverse** for
participation through 2022. These are source-specific declarations, rather than
permission inferred from an accessible URL. CC BY-SA is not a noncommercial
license: attribution and applicable ShareAlike obligations matter. Preserve
source/license links and modification notices; any later redistribution or adapted
database needs the applicable license treatment. This packet redistributes no raw
documentation or football data, and the lab's raw-publication prohibition remains.

The already retained hosting `nflverse-data/LICENSE.md` was read once. Its CC BY
4.0 text has SHA256
`2a82ac9bbc3e3ee066908381e8d373896db5a6025d083fbd59692fe9ccfb9111`.
It is distinct from the FTN-specific CC BY-SA declarations and is not a blanket
grant over every upstream source. Source attribution is not independent proof of
the licensor's title, complete coverage or a qualified outcome contract.

## Frozen documentation identities

Actual returned commit: `23f915a5be30415aeaa0c5c80cd23b2c69cda122`;
root tree reported by that commit: `d260d731f0cfdd5cd13657a6332a23d9e7c06393`.
Committer time is 2026-09-17T12:43:00Z, **not** an authenticated original document
publication or dataset availability clock. Exact UTF-8 content was cached once
with returned metadata; all five document Git blob hashes were independently
recomputed and matched. The connector's duplicate body wrappers were omitted
from retention; nonbody metadata was retained.

The retained recursive-tree response instead reports root `sha=23f915a5be30415aeaa0c5c80cd23b2c69cda122`,
which equals the commit ID and differs from the commit response's root tree above.
The five path/blob entries agree, but this connector identity mismatch is
unresolved. No independently reconciled commit-to-root-tree chain is claimed.
Both exact responses remain privately retained. The following commit/path links
are source leads; verified document blob/content identities remain valid without
establishing that chain or qualifying a dataset. No extra call was made.

| Document | Source link (commit/path association unresolved) | SHA256 |
| --- | --- | --- |
| Participation loader | [R/load_participation.R](https://github.com/nflverse/nflreadr/blob/23f915a5be30415aeaa0c5c80cd23b2c69cda122/R/load_participation.R) | `60a1497380a3c9271d72841f8f6e7e57c20b82d4611b9ee8b268606090fe2b9f` |
| Charting loader | [R/load_ftn_charting.R](https://github.com/nflverse/nflreadr/blob/23f915a5be30415aeaa0c5c80cd23b2c69cda122/R/load_ftn_charting.R) | `9e89e80cc034eb952ddbf05bfe3c58975f111a3abe65e393b086e2f56184e175` |
| Availability schedule | [nflverse_data_schedule.Rmd](https://github.com/nflverse/nflreadr/blob/23f915a5be30415aeaa0c5c80cd23b2c69cda122/vignettes/articles/nflverse_data_schedule.Rmd) | `6ea71f130135c4ff7cebc7221319428e3c1ba69fc9b8f1d26a306d5271670278` |
| Participation dictionary | [dictionary_participation.csv](https://github.com/nflverse/nflreadr/blob/23f915a5be30415aeaa0c5c80cd23b2c69cda122/data-raw/dictionary_participation.csv) | `ea1f390aab499695b33c0fc3411da239a63c9777b5e5468d1baddd9417b2f835` |
| Charting dictionary | [dictionary_ftn_charting.csv](https://github.com/nflverse/nflreadr/blob/23f915a5be30415aeaa0c5c80cd23b2c69cda122/data-raw/dictionary_ftn_charting.csv) | `561f76818200cd6bb88a1fa3a74a4640c80e5e0fcf59ade9d01dac18c312e1f4` |

Private documentation manifest SHA256:
`13a84f6619abc9b382fb8dcb3a44d8d15908cad67543c2bbbc09c2287101cd03`.
New namespace files total 99,976 logical bytes, within the 4 MiB document cap and
unchanged shared 512 MiB private quota. Retention execution used 12.265033 wall
seconds, 12.210352 CPU seconds, 106,635,264 bytes peak RSS and one numerical thread.
Earlier local metadata preflights were not CPU-profiled; these figures cover the
retention process. Connector backend HTTP counts, CPU, exact return clocks and
original document publication clocks are unknown, not imputed. Local cache clocks
are retained. All seven calls succeeded; one call remained unused.

## Smallest next pilot — proposed, unexecuted

The source-specific declaration supports preparing a **private retrospective
FTN participation schema/positive-appearance pilot**, with attribution retained.
It does not qualify the accepted operational route automatically. First obtain
one release-metadata response for the `pbp_participation` release and identify the
exact `pbp_participation_2024.parquet` asset: immutable release/asset identities,
size, available digest, and source/license relationship. Asset identity, byte size
and actual schema are presently unverified prerequisites. Do not guess a hash.

After a separate bounded acquisition registration, inspect that single 2024
asset's schema and only game/play keys, GSIS on-field lists and list counts for the
fixed game `2024_01_BAL_KC`; do not read names, statistics, outcomes or NGS fields.
Proposed hard acquisition envelope: one asset, at most three HTTP transactions
including redirects, zero retries, 32 MiB incoming bytes, 60 wall/60 CPU seconds,
256 MiB RSS, one thread and the existing global private quota. If advertised size
or transport cannot satisfy that envelope, stop rather than expand it. A frozen
local projection can then report only key uniqueness, list encodings, missingness,
crosswalk ambiguity and positive-witness coverage, with at most 10,000 projected
play rows and no model work. This proposal is not execution authority.

The pilot's result cannot establish DNP, complete special-teams coverage,
statistical zeros from absent values, in-season availability or PPR labels. The
FTN charting lead remains separate and is not a substitute participant panel.
Other free-source routes are not claimed exhausted.
