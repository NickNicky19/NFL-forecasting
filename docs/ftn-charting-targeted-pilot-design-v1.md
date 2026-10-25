# Targeted FTN charting pilot — design only

No acquisition, source enablement, software test or model study is executed by
this document. Reuse the [cached documentation qualification](participation-substitutes-v1.md).
The integrator separately obtained one release-metadata response; no charting
asset was downloaded. The current Git HTTP refusal remains a transport limit:
do not unset the proxy, change routes to bypass it or spend keys/call allowance.

## Source identities and narrow first asset

The previously authenticated dictionary content has SHA256
`561f76818200cd6bb88a1fa3a74a4640c80e5e0fcf59ade9d01dac18c312e1f4`;
the charting loader has SHA256
`9e89e80cc034eb952ddbf05bfe3c58975f111a3abe65e393b086e2f56184e175`.
Their cached Git blob identities are valid; the older connector's unresolved
commit/root-tree association remains unresolved. No new documentation call is
needed or claimed.

Choose only `ftn_charting_2024.parquet` from
`nflverse/nflverse-data`, release tag `ftn_charting`: asset **288253518**,
advertised **563,180 bytes**, advertised SHA256
`9396c95effac1a81cc30efcf9c4c87ab89855548ae605404318ae949d4356119`.
These are integrator-recorded release metadata, not independently downloaded or
byte-verified content. Freeze the retained metadata response identity before a
future request. A changed asset size/digest fails this pilot; do not substitute
another season or format. Other discovered assets are outside this pilot.

The FTN-specific loader declares CC BY-SA 4.0 and attribution **FTN Data via
nflverse**. Preserve the source, license, attribution and modification notices
privately; raw/row-level redistribution remains prohibited by this lab's scope.
The hosting repository's different CC BY 4.0 text is not a substitute license.
This is not automatic permission to modify the accepted operational source
policy or use this source in the current models.

## Exact schema capability check

The minimal required charting fields are these nine dictionary names:

| Fields | Dictionary type | Intended capability |
| --- | --- | --- |
| `nflverse_game_id` | character | Exact PBP game key |
| `nflverse_play_id` | numeric | Exact PBP/GSIS play key |
| `season`, `week` | numeric | Key-context consistency |
| `is_interception_worthy` | logical | Targeted QB turnover-risk signal |
| `is_catchable_ball`, `is_drop` | logical | Distinct receiver catch-quality signals |
| `is_throw_away` | logical | Explicit throwaway/context qualification |
| `date_pulled` | POSIXct | nflverse FTN retrieval clock, not publication |

The first capability pilot reads **footer/schema only**, not these columns'
values. Retain field names/types/nullability and file/row-group counts; do not
decode or export footer min/max statistics, player/game values or row samples.
An actual Arrow type must be recorded rather than guessed from the dictionary.
Numeric keys need later finite/integer/exact-join validation; a schema alone
cannot prove it. Unsupported/missing fields make the relevant capability
unready, without invented aliases, type coercion or substitute fields.

`read_thrown` is deliberately excluded from this minimal feature group. If a
later role extension uses it, preserve its character codes: `0` primary read
starts in **2023**; 2022 primary reads are **NA**, never `0`. `1`, `2`, `CHK`,
`DES` and `SD` denote different documented read contexts. This is a season
definition change, not a zero or category that can be inferred retroactively.
Other pressure/personnel/depth fields are outside this first group.

## Player crosswalk and denominator prerequisites

Charting does **not** provide QB/receiver GSIS identities in this dictionary.
Any later player feature requires a separately frozen permitted PBP source and
an exact join:

`(nflverse_game_id, nflverse_play_id)` to `(game_id, play_id)`.

Minimum PBP dependencies are `game_id`, `play_id`, `season`, `week`,
`season_type`, `posteam`, `defteam`, `passer_player_id`, `receiver_player_id`,
plus independently documented attempt/target eligibility fields such as
`pass_attempt`, `no_play`, `play_type`, `sack`, `qb_scramble`, `qb_spike` and
`two_point_attempt`. Their exact semantics/schema and source-policy permission
must be qualified before that join; the field list is a dependency, not a claim
that every definition has been verified here. No names, fuzzy matching,
roster-based inference or carry-forward identities. Missing receiver IDs do not
become a credited target; missing passer IDs do not become an assumed starter.

Both sides need unique game/play keys, exact season/week/team context, original
counts and a full outer unmatched/ambiguous inventory. Duplicate-key groups
remain unresolved; never keep a convenient first row. Known player IDs must
match the lab's canonical namespace, with sparse/new/unmatched players retained.
PBP is a player-assignment and exposure source here, not an independent
revalidation of FTN's subjective charting labels.

The documented charting is a **subset**; it does not establish all attempts,
targets or game coverage. A later study must retain separate counts for:

- All eligibility-qualified PBP attempts/credited targets.
- Exact charted matches and unmatched PBP/charting plays.
- Per-flag nonmissing, explicit false and explicit true observations.
- Missing/ambiguous player and play identities.

For example, an IWP rate denominator is only eligible charted pass attempts
with a known IWP flag and identified QB; a catchability or drop denominator is
only eligible charted credited targets with that particular known flag and
identified receiver. These denominators can differ. Report their coverage
against all eligible PBP exposures separately. Do not divide a charted-subset
numerator by all attempts, equate missing flags with false, assume all flags are
applicable to every play, or infer that a drop flag logically determines the
catchability flag. Conflicts require explicit diagnosis. A zero denominator is
unknown, with an eventual registered fallback, not a zero rate.

No charting absence establishes DNP, complete participation, a statistical zero
or exact PPR. This source is separate from FTN postseason participation and the
ongoing raw-orphan zero-support audit.

## Availability and later experiment boundary

The loader says charting occurs within 48 hours and the schedule polls at
00/06/12/18 UTC. These are documentation statements, not original row-release
receipts. `date_pulled` is nflverse's API retrieval time, not necessarily first
publication or local feature availability. A current download and upstream
release/update time cannot authenticate a historical pregame clock. Preserve
the current reconstructed timing lane unchanged. Any future operational feature
requires actually archived source versions/capture clocks available before its
registered cutoff; source corrections append new versions.

After schema and a separately registered key/player capability pilot, predeclare
one turnover-risk-only ablation for `pass_int` and a distinct catch-quality-only
ablation for `rec`/`rec_yd`. Hold learner, cohort, cutoffs and comparator versions
fixed while changing the qualified feature group. Fit pooling, rates,
preprocessing and missingness treatment on earlier training only. Do not invent
prior gains or add these fields to the current frozen runs. Later model budgets,
chronological splits, primary probability/point scores and confirmation must be
registered separately; this document chooses no fitted formula or winner.

## Proposed bounded schema-only pilot — not authorized here

One asset; at most three HTTP transactions including redirects; zero retries;
2 MiB incoming ceiling; 60 wall/CPU seconds; 256 MiB combined RSS; one numerical
thread; at most 4 MiB new private attempted allocations under the unchanged
512 MiB shared quota. No PBP download/join, column-value decode, NFL forecast,
fit, score, label application, source-policy change or public raw upload. Reuse
the existing permitted acquisition and owned-cache route only after exact
code/config/environment/resource review and root registration/GO. Redirects and
partial bodies count; transport failure remains a retained terminal result.

Retain the original binary privately once, compute the actual SHA256 and compare
advertised size/digest, cache the exact response and source/license metadata,
and emit only public-safe capability counts/types/hashes. A successful schema
check enables only the next bounded key/crosswalk design. It establishes no
coverage, useful feature values, historical availability or forecasting gain.

Preparation used cached docs only, with no new source calls/install/tests/CAS
writes or charting/PBP/model-value reads. A broad local text search incidentally
surfaced numbers from an already-public, already-exposed scheme report; those
were not inputs to this design. No new source or confirmation period was opened.
Requested settings: GPT-6.1 Sol Extra High; actual backend settings unattested.
