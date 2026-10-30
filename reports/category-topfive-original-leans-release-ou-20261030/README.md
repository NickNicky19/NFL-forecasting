# Original recorded leans: category-by-side results and release status

**October 30, 2026 — America/Chicago. This is the original research session, not the retained production owner.** The latest user clarification preserves production read-only here. The website owner still holds lease 178, run `NFL-WEB-PRODUCTION-REPORT-INTEGRATION-20261025-122500Z`. No website write, dispatch, new inference, pregame capture or deployment occurred in this wave.

## Answer: how often our saved Over and Under leans were correct

I joined the **original archived sides and original lines**, not newer projections or hindsight sides, to the pinned site's supported outcome cache. Source: website commit `1ec93e068a91abd51c990937d1019e4a831694b4`; `track_record.json` Git blob `8d098ac2118a91bdc59c48d3f68e6d8b23021217`; grader `statistical-v3-identity-20261025`.

The quoted snapshot is reproduced exactly: **Over 394 hits / 397 misses = 49.8% on 791 decided; Under 349 / 236 = 59.7% on 585 decided.** These side pools have different category/player/line composition. This is not evidence that always choosing Under would win or that a new model earned the older record.

**The category quotations were hits / decided, not hits / misses:** passing TDs 53/75 means 53 hits, 22 misses; completions 38/61 means 38 hits, 23 misses; receptions 221/363 means 221 hits, 142 misses; passing attempts 35/58 means 35 hits, 23 misses.

### All originally saved qualifying leans

| Category | Over hits | Misses | Decided | Hit rate | Under hits | Misses | Decided | Hit rate | Pending / unresolved | Decided games |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Passing yards | 16 | 12 | 28 | 57.1% | 21 | 21 | 42 | 50.0% | 22 / 0 | 44 |
| Passing TDs | 20 | 12 | 32 | 62.5% | 33 | 10 | 43 | 76.7% | 23 / 0 | 45 |
| Completions | 15 | 2 | 17 | 88.2% | 23 | 21 | 44 | 52.3% | 20 / 0 | 41 |
| Passing attempts | 10 | 4 | 14 | 71.4% | 25 | 19 | 44 | 56.8% | 19 / 0 | 39 |
| Interceptions | 20 | 21 | 41 | 48.8% | 12 | 3 | 15 | 80.0% | 13 / 0 | 40 |
| Rushing yards | 64 | 88 | 152 | 42.1% | 23 | 16 | 39 | 59.0% | 44 / 2 | 46 |
| Carries | 29 | 26 | 55 | 52.7% | 24 | 20 | 44 | 54.5% | 22 / 0 | 44 |
| Receptions | 92 | 65 | 157 | 58.6% | 129 | 77 | 206 | 62.6% | 97 / 4 | 46 |
| Receiving yards | 108 | 132 | 240 | 45.0% | 44 | 31 | 75 | 58.7% | 81 / 3 | 46 |
| Combined yards | 20 | 35 | 55 | 36.4% | 15 | 18 | 33 | 45.5% | 21 / 1 | 43 |

### Originally highlighted Top Picks

These are original `archive.picks` memberships, preserved separately from ordinary leans and newer selected-ranking companion documents. Overall: **Over 23/44 = 52.3%; Under 22/41 = 53.7%**.

| Category | Over hits | Misses | Decided | Hit rate | Under hits | Misses | Decided | Hit rate | Pending / unresolved | Decided games |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Passing yards | 1 | 2 | 3 | 33.3% | 4 | 4 | 8 | 50.0% | 3 / 0 | 11 |
| Passing TDs | 2 | 2 | 4 | 50.0% | 0 | 0 | 0 | — | 2 / 0 | 4 |
| Completions | 0 | 0 | 0 | — | 0 | 1 | 1 | 0.0% | 3 / 0 | 1 |
| Passing attempts | 2 | 0 | 2 | 100.0% | 6 | 3 | 9 | 66.7% | 2 / 0 | 10 |
| Interceptions | 0 | 4 | 4 | 0.0% | 0 | 0 | 0 | — | 0 / 0 | 4 |
| Rushing yards | 7 | 3 | 10 | 70.0% | 2 | 2 | 4 | 50.0% | 4 / 0 | 12 |
| Carries | 0 | 0 | 0 | — | 0 | 1 | 1 | 0.0% | 1 / 0 | 1 |
| Receptions | 2 | 2 | 4 | 50.0% | 5 | 3 | 8 | 62.5% | 4 / 0 | 10 |
| Receiving yards | 8 | 7 | 15 | 53.3% | 3 | 3 | 6 | 50.0% | 4 / 0 | 15 |
| Combined yards | 1 | 1 | 2 | 50.0% | 2 | 2 | 4 | 50.0% | 0 / 0 | 6 |

### Period, missingness and evidence limits

- The snapshot covers **2026 Weeks 4–8**. Weeks 1–3 have no original forecast archive in this source; their retrospective outcomes are not substituted for missing decisions. Week 4 has many original late exclusions, not complete advance coverage.
- There are **2,178 original lean records**: 1,376 decided, 362 pending, 10 unresolved and 430 excluded by their original late flag. There are **108 original Top Pick records**: 85 decided and 23 pending. Top Picks overlap the underlying opportunities and are not additional independent football observations. Decided leans cover **46 unique games**.
- Week 8 has only one completed graded game in this snapshot. Weeks 6/7 have all games completed but retain unresolved outcomes. The machine table marks every partial/unresolved week and separates original-record games from games with decided outcomes.
- No observed statistical pushes, attributed DNPs or voids occurred in these retained qualifying grades. Zero observed counts do not authenticate a bookmaker contract. Missing participation remains unresolved.
- **These are statistical hits/misses at the saved lines, not verified sportsbook settlements.** The archive save clock is not a per-row original forecast or quote timestamp. Pregame timing remains limited; existing late flags are preserved. No original time was invented.
- Ordinary leans retain no complete model/policy identities. Top Picks have three sparse explicit model references; all other missing attribution stays unknown. Nothing is automatically labeled R0 or credited to the new MAE release.
- Original prices and quote clocks are absent from all 2,286 joined decision records. Therefore no current-row EV, ROI, calibrated probability or venue-settled claim is made. Receiving targets, chart PPR and compatible anytime-TD offer histories are unavailable in this archive.
- Game/week cluster bootstrap intervals are included in the machine report (1,000 replicates, seed 20261030). They are descriptive, unadjusted and unstable for small samples. The 17 decided completion Overs, for example, are a small selected sample.

[Machine report, full reconciliation, weekly and model/policy views](ORIGINAL_LEANS_REPORT_V1.json) · [Cumulative CSV](ORIGINAL_LEANS_CUMULATIVE_V1.csv) · [Weekly CSV](ORIGINAL_LEANS_WEEKLY_V1.csv) · [Original-version CSV](ORIGINAL_LEANS_BY_VERSION_V1.csv).

## Threshold verification: no confirmed rounding/grading defect

Twenty-six fictional numerical cases exercised the exact current producer, ranking eligibility/validation, grader and browser functions. Count means such as **1.88 remain fractional expected values**. Passing TDs at 1.5, receptions at 4.5, completions at 19.5, integer equality and signed yards grade correctly. Negative yardage examples correctly remain ineligible for the current minimum-line Top Pick rule while their ordinary statistical direction is graded.

The exact chart scorer produces **1.94** in the fractional fixture and generic numeric grading passes; the full chart consumer remains unadmitted. Six explicitly specified count-law probability arithmetic cases pass, including integer push mass. These are software/math checks, not NFL probability-accuracy results. The two retained fixture-runtime failures are not website defects. [Actual case/source receipt](threshold/THRESHOLD_REAL_PATH_RESULTS_V1_2.json) · [Readable verification](threshold/README.md).

## Selection comparisons: completed work reused, new limited replay executed

Existing football/calibrated/shrunk/market/hybrid comparisons were reused without new fits. They used an older frozen football control, not today's website champion, and timing-unqualified historical prices. In 2026, football had the lowest inspected passing-attempt Brier (.243263); every carry arm lost to the .25 constant-50% control; reception market Brier .249694 only narrowly beat .25. No matched target market existed. [Exact prior arms, scopes, losses and adverse paper results](REUSED_PROBABILITY_STUDIES_V1.json).

The previous player top-10/15/20 MAE study is not a Top Picks strategy. A newly registered **descriptive replay within the retained original highlighted pool** ranked its recorded absolute standardized gap scores, without choosing a favorable new line or forcing equal sides:

| Capacity policy | Selected | Hits | Misses | Pending | Decided hit rate |
|---|---:|---:|---:|---:|---:|
| Top 6 | 30 | 12 | 12 | 6 | 50.0% |
| Top 10 | 50 | 20 | 20 | 10 | 50.0% |
| Top 20 | 92 | 40 | 33 | 19 | 54.8% |
| Top 20, abstain unless absolute original score ≥ 2 | 15 | 5 | 5 | 5 | 50.0% |

Always-Over and always-Under controls on the identical selected opportunities, plus weekly/category/side coverage, are retained in the result. **This is not a complete full-board probability/EV tournament or a future-facing win.** The original highlighted pool already had side-specific selection restrictions. No policy was activated; original recommendations were not changed. [Protocol](TOP_CAPACITY_REPLAY_PROTOCOL_V1.json) · [Complete replay](TOP_CAPACITY_REPLAY_RESULTS_V1.json). Missing compatible current-law/offer/price vectors block those specific head-to-head arms, not ordinary hit-rate reporting or the prepared point release.

## Reproducible evidence and sustainable storage

The public scorer and serializer preserve original sides and grade identities. The private player-level scorecard retains prediction, original line/side, actual, error, game/player ID, provenance, timing limitations and grade state. It contains **2,286 records / 1,869,269 bytes**, SHA-256 `06ea1d00a290b5afc3c8e73d7263dd2a28f033b1a876211ddc7cab126655c26d`, evidence ID `original-recorded-leans-20261030-v1/scorecard`.

The complete inherited managed writer and shared lock froze it; a **separate local process** authenticated the same immutable CAS alias and full checksum. All original caps, failures, uploaded-byte accounting and the existing 80 MiB upcoming-write reservation remain intact. Four missing upload paths were restored from retained exact bytes (17,649,073 bytes) without deleting any original or weakening accounting. The original 20-second accounting attempt failed; its separate runtime continuation consumed 36.88 CPU seconds, and independent readback 18.57 seconds. **Off-host transport/restoration remains unverified and owner-controlled.** Restoring those historical ZIPs is not restoration of the separate production model/source checkpoint, which remains pending. [Freeze](PRIVATE_FREEZE_V1_1.json) · [Fresh-process readback](PRIVATE_READBACK_V1_1.json) · [Original-input restoration](UPLOAD_RESTORATION_V1.json) · [Failures/corrections](FAILURES_AND_CORRECTIONS_V1.json).

Reproduction: reconstruct the input bundle from the eleven immutable source paths/blob identities in the report; run `tools/category_topfive_original_leans_report_v1.cjs` on that private bundle, apply `category_topfive_original_leans_public_v1.cjs` to the public result and private records, and run `category_topfive_original_capacity_replay_v1.cjs` on the same original inputs/grades. Preserve source contracts and outcome versions. Do not publish the private bundle or scorecard. The complete original functions and commands for threshold checks are pinned in their receipts.

## Website integration and actual release status

The additive reporting module provides category, side, original cohort, week and model filters; its 21 fictional fixtures pass, and the **actual computed report validates and renders**. It displays sample sizes, partial weeks and unknown attribution. It never converts a historical rate into an individual player's estimated probability. [Minimal owner insertion and neutral historical-heading change](ui/OWNER_INTEGRATION_V1.md) · [Real aggregate consumer check](REAL_AGGREGATE_CONSUMER_CHECK_V1.json).

Production has not changed here. A refreshed read confirms website Main remains `1ec93e068a91abd51c990937d1019e4a831694b4`; the last independent served-code/value verification found **1,945 existing forecasts and zero stat_point_mae_v2 rows**. The original category receipt retains all exact incumbent versions and values. The new research reporting module and new MAE products are prepared, not live.

The latest actual research parent remains **41104520104**, failed with capture enqueue skipped. Next configured parent: **Saturday October 31, 7:36–7:57 a.m. CDT**. Next registered remaining game deadline: **Sunday November 1, 10:30 a.m. CST**. Both are pending; the daylight-saving transition is preserved. No missed capture was backfilled.

The retained website owner must execute the already delivered MAE package at `341742de83975264a07d035d4b6289e57c2ec1e9`, restore its approved checkpoint/current source bindings, admit and capture each ready typed point product independently, and publish/verify actual values. Add this reporting payload/module through the same writer and build. Keep projection-gap labels honest; probability and EV views remain unavailable until their separate policies and data qualify. **User acknowledgement of the checkpoint is recorded; no retained-owner execution acknowledgement or release has been observed.** A handoff is not deployment.

This wave completed statistical regrading, one bounded descriptive capacity replay, engineering checks and managed evidence retention. It performed **zero new predictive fits, forecasts, pregame captures, API odds calls or deployments**. Four-category predictive research, earlier negative evidence, scientific registrations and original/V2 ownership remain intact.

[Category-level actual live versions, issue clocks, zero new issuance counts and latest build/capture identities](CATEGORY_RELEASE_AND_ROLE_STATUS_V1.json) · [Exact reporting owner addendum](OWNER_REPORTING_ADDENDUM_V1.json).
