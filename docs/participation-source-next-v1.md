# Next participation source qualification — UNEXECUTED proposal

Status: **UNEXECUTED / RIGHTS AND SOURCE SEMANTICS NOT YET QUALIFIED**.
This document is preparation, not a registration, acquisition, source-policy
amendment, participant census, experiment, scheduler change or qualification.
No source request, private NFL row/artifact read, fit or forecast was performed.

The highest-value remaining candidate is the **official NFL final gamebook's
participation/lineup report**, obtained through its official game page. A
separate appearance table could establish that a player appeared even when
none of the existing positive-action fields fired. It would address the actual
selection gap. Public/free access is a candidate route; permission for its
proposed automated use and later model inputs has **not** been established by
this review. The next step is a small documentation/schema qualification probe.

## Evidence already available, without repeating it

| Existing evidence | Established result | Remaining limit |
|---|---|---|
| [Permitted source repair](../reports/source-policy-20261023/README.md) and [v2 policy](../config/operational-source-policy-v2.json) | Official positive physical events support playing; eligible unknown rows retain rolling slots | No complete all-phase appearance/nonappearance denominator; zero-only rows and ACT/INA do not prove playing |
| [Original RB prerequisite audit](../reports/source-policy-20261023/rb-gate.json) | The completed 2023 diagnostic found additional snap-supported appearances | PFR AI/ML permission remains unresolved; appearances can still lack a carry value; absent-stat zero convention remains unqualified |
| [Operational repair acceptance](../reports/operational-source-repair-v1/README.md) | Source predicates, qualification, identities and immutable replay were checked | Storage/source correctness supplies no new independent appearance source |
| [Player-context qualification](../reports/player-context-intake-v1/README.md) | Current Sleeper fields and ESPN feed versions have tested identity, null and clock handling | Every participation state remains unknown; no qualified practice-participation panel; mention/injury status is not game appearance or DNP |
| [Optional NGS context](optional_context.md) and [scheme context](scheme-context-study.md) | Earlier NGS/PBP context was acquired and separately tested | These are selected statistical/context observations, not complete player participation; current NGS coverage and authentic historical publication are unavailable |
| [Independent audit intake](../reports/INDEPENDENT_AUDIT_INTAKE_20261023.md) | Independent appearance/zero qualification is a recorded priority; FTN charting is a distinct proposal | No completed FTN charting qualification or official-gamebook appearance contract is identified in the reviewed records |

The latest source-repair counts quoted by the intake are 62,388 historical
rows, 42,286 positive-action played rows and 20,102 unknown rows. These are
previously reported counts, not a new census. The existing cached-source
metadata census, source receipts and research index were considered as lineage
references; no acquisition/census producer or cached body was rerun.

This review does **not** establish that all credible free routes were tried.
It found no cleared source contract that closes the required gap. The precise
missing evidence is a permitted, game-specific, complete all-phase appearance
ledger with exact identities, explicit nonappearance meanings, revisions and
availability clocks; plus explicit target zeros or a separately documented
exhaustive-statistic zero convention for every proposed absent-row zero.

## Candidate source and exact acceptance fields

Use the official page for one predetermined, completed regular-season game:

`https://www.nfl.com/games/lions-at-chiefs-2023-reg-1`

This is a proposed discovery URL, not a newly verified available endpoint.
Accept a gamebook PDF only through an actual link on that page and an official
NFL-controlled host verified from that link. Do not invent a CDN URL, crawl an
archive, switch to a mirror, use a paid product or substitute a PFR table.

Candidate printed section names to verify include `Participation Report`,
starting lineups, `Substitutions`, `Did Not Play` and `Not Active`. These are
expected labels to check, **not an inspected schema declaration**. Preserve the
actual heading text, team attribution and section completeness definitions.
Different or missing headings require an explicit result rather than a fuzzy
parser that assumes the same meaning.

If later qualified, a separately versioned private appearance adapter would
require the following fields; none is being populated here:

| Field | Required meaning |
|---|---|
| `game_id`, official game identifier, `season`, `week`, `game_type`, both teams, kickoff | Exact independent game/calendar binding; REG 2023 for this probe |
| `team`, source jersey token, source lineup position if present, exact source display text | Preserve the original participation entry; display names stay private and never supply an identity join |
| `participation_section`, page/section locator | Exact starter/substitution/DNP/not-active section and an auditable source location |
| canonical GSIS `player_id`, identity-binding state and crosswalk hash | Publisher GSIS ID if present; otherwise only a separately verified unambiguous game/team/jersey crosswalk to historical roster identity |
| source URL, final URL, media type, bytes, SHA256, actual retrieval start/end, ETag/Last-Modified if present | Immutable body/receipt binding; current file metadata does not prove original publication |
| publisher status/revision token and authenticated publication/update time, if actually supplied | Missing values remain missing; no inferred historical release clock |

Historical jersey numbers are not in the current operational roster projection.
A new identity projection would require its own explicit column contract and
collision audit. Missing, reused or conflicting jerseys/identities remain
quarantined; no name matching, current-team inference or numeric ID coercion is
authorized. A reported appearance entry and a contradictory DNP/not-active
entry also quarantine that player-game rather than selecting one record.

## Participation and zero semantics

1. After publisher semantics and completeness are established, an explicit
   starter/substitution appearance could support `played` independently of
   positive stat credits. This is a different evidence table, not an independent
   statistical publisher: both may ultimately originate with the NFL.
2. Explicit game-specific `Did Not Play` / `Not Active` could support their
   documented nonappearance meanings only after that section's all-phase
   definition is verified. A missing name, an active roster flag or a blank
   section does not certify DNP.
3. Combine new appearance proof with an **already explicit** official target
   value of zero on the exact same canonical player/game/team to qualify a
   played-zero observation. Preserve signed zero/negative yardage and supported
   count integers under the existing target contracts.
4. Appearance alone never supplies a missing carry, target, reception, TD or
   yard value. An absent statistics row stays missing until the NFL explicitly
   documents the relevant table/field as exhaustive and its omission as zero.
   One verified table cannot establish every target's convention or exact PPR.
5. Preserve every original opportunity and unknown state. One game can assess
   schema/identity feasibility; it cannot qualify a complete historical panel,
   participation probability model, original RB protocol or forecasting gain.

Final gamebooks are postgame evidence. No fixed publication SLA or correction
schedule is authenticated in the retained records. The proposal must discover
whether the publisher supplies one; “after final” is not a timestamp. Original
historical availability remains unknown. A later model-input proposal must use
actual capture clocks or an explicitly labeled reconstruction assumption and
must preserve existing source/history cutoff gates.

This route supplies **no authenticated pregame availability**. Final
`Not Active` text cannot be backdated into a pregame input. A factual game-day
inactive announcement would need its own official source, exact game/identity
binding, actual pre-cutoff capture and publication/revision proof. Existing
Sleeper/news snapshots remain advisory; missing injury status is not healthy,
and `active` does not prove an appearance. No inactive-announcement capture is
included in this probe.

## Smallest proposed future probe

First review the existing evidence inventory/index and exact source URLs for an
identical prior capture. If one exists, use its existing metadata/result and
stop this acquisition proposal; do not repeat a completed census or request.
Otherwise, a root may separately freeze the following **single** metadata-only
probe with the known working interpreter and existing quota/downloader:

| Ceiling | Proposed bound |
|---|---|
| Invocations / automatic retry | 1 / 0; durable consumption/failure marker |
| HTTP transactions | At most 3 total, one attempt per exact URL; redirects count |
| Bodies | At most 1 MiB official terms/documentation, 1 MiB game-page HTML, 4 MiB linked PDF; 6 MiB combined incoming/decoded body cap |
| Wall / CPU / RSS / threads | 60 seconds / 60 seconds / 512 MiB / 1 |
| New source vintages | One fixed REG 2023 gamebook at most; no other game/year, W6 extension or protected future outcomes |
| Semantic work | Rights/release documentation, link identity, media type, section headings and schema only; no player rows, statistics, target outcomes, forecasts or model values extracted |
| Models, scores, scheduler changes | 0 fits, predictions, accuracy scores or operational changes |

The first candidate documentation URL is
`https://www.nfl.com/legal/terms`; its live availability/content is unverified
here. Preserve the full exact terms URL/version/hash and retrieval clock. Review
applicable publisher restrictions on automated retrieval, private analytical use,
derived model inputs and redistribution **before** following the PDF link.
Public access, a game-page link and nflverse's hosting license are not an
upstream NFL permission grant. A login/paywall, unclear grant, blocked retrieval,
missing official link, byte/time limit or unavailable schema yields a retained
failure/unknown result. Do not bypass, try alternate endpoints or silently widen
the cap. No raw document, identity or row redistribution is proposed.

The probe returns only source/version/hash/byte/clock receipts, documented
rights and release facts or explicit unknowns, section/schema availability and
an identity-feasibility decision. All bodies remain private and count against
the existing shared 512 MiB retention limit. It does not change the current
positive-event qualifier. Any subsequent one-game appearance/explicit-zero
comparison requires a distinct predeclared semantic-read budget and review.

## FTN distinction and next decision

FTN **charting** may support a future fixed turnover-risk or catch-quality
feature qualification, after checking its actual free dictionary, coverage,
definition changes, license and release timing. It is not a complete all-phase
participant ledger. FTN **participation** is a separate product; postseason
availability cannot be used as an in-season pregame feature or repair a REG
participant denominator. Neither route has been acquired or qualified here.

If official-gamebook eligibility or schema fails, retain that exact missing
evidence and consider a separate targeted FTN charting documentation proposal.
Do not repeat positive-action, NGS, PFR or roster-status checks and describe
them as independent new appearance evidence. The shared benchmark code,
published decisions and original source/participant gates remain unchanged.
