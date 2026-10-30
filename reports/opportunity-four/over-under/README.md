# Forecast error and original-line direction: executed checkpoint

Completed **October 29, 2026, America/Chicago**. This continuation scored real saved forecasts and original lines, generated two new targets controls, and checked the results independently. **No new live deployment or original-producer pregame capture occurred.**

## Original-line comparison

The study used 2024 regular season and 2026 Weeks 1–5, separately. It joined **14,810 original quote rows**: 14,342 supported outcomes and 468 unknown-participation records. One representative offer per player/game/category is selected within each registered pool. Multiple books or alternative pool representatives are not additional football observations.

There are 5,071 full canonical opportunities, 4,683 point-common and 4,471 probability-common opportunities, across both seasons. The 72,646 procedure/offer decision records reuse statistic forecasts; **zero models were fitted and zero new statistic forecasts were generated** by this scorer. The old football control F is frozen from the earlier study, not today's website champion.

These are **timing-unverified historical reconstructions**. A source collection clock does not authenticate a pregame quote. Correct/incorrect below means the final statistic was on the selected side of the original line. Actual bookmaker settlements remain **UNRESOLVED**, because their contract and timing are unqualified.

### 2026 point-direction results

The registered rule uses the unrounded forecast: above line = Over; below = Under; equal = abstain. F is the older football point, FC its earlier-trained correction, and H the retained football/market correction.

| Category | Supported / offered | F correct / incorrect | FC correct / incorrect | H correct / incorrect | F → H average absolute miss |
|---|---:|---:|---:|---:|---:|
| Passing attempts | 79 / 79 | 41 / 38 | 42 / 37 | 41 / 38 | 6.2388 → 5.8848 attempts |
| Carries | 101 / 101 | 58 / 43 | 56 / 45 | 58 / 43 | 4.5426 → 3.9454 carries |
| Receptions | 461 / 496 | 230 / 231 | 238 / 223 | 236 / 225 | 1.7883 → 1.6087 receptions |
| Receiving targets | — | — | — | — | TARGET_OFFER_UNAVAILABLE |

H has a lower average numerical miss in each row. Its correct-side counts tie F for passing attempts and carries; receptions gains six correct decisions. The paired H-minus-F direction-error game intervals include zero for all three. **This does not establish a substantial improvement over a current website method.**

Original F point directions, split by selected side:

| Category | Over correct / incorrect | Under correct / incorrect | Unresolved Over / Under |
|---|---:|---:|---:|
| Passing attempts | 19 / 17 | 22 / 21 | 0 / 0 |
| Carries | 21 / 9 | 37 / 34 | 0 / 0 |
| Receptions | 122 / 128 | 108 / 103 | 24 / 11 |

Every procedure's side counts, abstentions and bookmaker-status counts are in [the downloadable side table](CORRECT_INCORRECT_BY_SIDE.csv). A hit rate is correct / (correct + incorrect); pushes, abstentions and unresolved outcomes remain visible. Selective market-point abstentions cannot be compared with fully selecting methods as though their selections were identical.

### Probability results are a separate question

Lower Brier is better. These are identical decisive probability rows within each category. Passing attempts' common probability pool covers **Weeks 1–4**, with no eligible Week 5 common offer.

| Category | Decisive rows | F | Calibrated FC | Shrunk FS | Market M | Hybrid H | Constant 50% |
|---|---:|---:|---:|---:|---:|---:|---:|
| Passing attempts | 46 | **0.243263** | 0.249475 | 0.250000 | 0.248612 | 0.249421 | 0.250000 |
| Carries | 67 | 0.286105 | 0.253711 | 0.250966 | 0.254675 | 0.253808 | **0.250000** |
| Receptions | 419 | 0.281989 | 0.253618 | 0.251094 | **0.249694** | 0.250651 | 0.250000 |

Markets did not improve passing-attempt probabilities here. Carry arms improve on an overconfident F but do not beat 50%. The reception market arm is only 0.000306 better than 50%; H remains worse than 50%. A large improvement against a weak control is not a large edge over a strong control.

F's full three-outcome statistic law and conditional decisive probability arms are scored separately; push/void masses are not invented. The 78 paired contrasts and game/week intervals are retained in [all results](OVER_UNDER_RESULTS.json). Week intervals require the registered minimum eight clusters and are unavailable for these short 2026 panels.

### Paper selections and older results

The scorer preserved **1,271 original frozen paper selections** without choosing new picks. Their prices and assumed returns remain exploratory. For example, 2026 reception market-EV has +8.429 known-settled units, but 3 of 20 selected stakes remain unresolved; carry hybrid-EV loses 6.949 units. Different selected pools and unqualified quote/settlement contracts prevent a verified profitability claim. All losing weeks remain recorded.

2024 stays separate: H point-direction correct counts are 237/457 passing, 354/677 carries and 1,434/2,759 receptions, versus F's 234, 363 and 1,460. H therefore loses direction accuracy in two older categories despite lower point MAE. See the same aggregate's season and weekly records. Original 2025 quote exclusions are unchanged; qualified 2025 football remains permitted independently.

## New targets forecasts

On the unchanged 2026 Weeks 1–6 target panel, **5,998 new point forecasts, zero fits**:

| Procedure | MAE in targets | Difference versus CDF |
|---|---:|---:|
| Existing target CDF median | **1.692722** | Reference |
| New recent-eight-game lower median | 1.744474 | 3.06% worse |
| New recent-three-game lower median | 1.849596 | 9.27% worse |

Both lose to CDF in every week. The primary population retains 1,855 supported of 2,458 planned rows, including 369 played zeros; 603 remain unknown. Exact-count and tolerance tradeoffs are preserved. [Full target report](../../category-topfive-opportunity-target-controls-v2-20261030/README.md).

Target-to-reception integration has a prepared analytic conditional-law proposal, not a new predictive result. It integrates a predicted target distribution through a conditional catch law; actual target-game targets are never a pregame input. Its paired-source qualification and separate finite execution remain next. [Feasibility and precise prerequisites](../../category-topfive-target-reception-feasibility-v1-20261030/FINITE_COMPARISON_PROPOSAL_V1.json).

## Verification and permanent evidence

Independent fresh-process QA checked all **72,646 decisions**, **1,271 original paper rows**, **186,278 aggregate fields**, **180 season summaries**, **1,095 weekly rows** and **78 paired comparisons**. The restored 26,493 market-feature book lists exclude the offering book. Same-host checks do not prove off-host restoration or original quote availability.

- [Independent OU receipt](runtime/ou-vector-qa-v1/PUBLIC_RECEIPT.json), [target receipt](runtime/target-median-qa-v1/PUBLIC_RECEIPT.json).
- [Complete scores, weekly rows, losses and uncertainty](OVER_UNDER_RESULTS.json); [separate generated point/probability leaders](GENERATED_PRODUCT_LEADERS.json).
- [Data readiness by category/source](OVER_UNDER_DATA_READINESS.json); [frozen side rules](OVER_UNDER_POLICY_REGISTRY.json); [canonical run/result linkage](RESULT_INDEX.json).
- [Older Week 6 reported directions](LEGACY_WEEK6_REPORTED_DIRECTIONS.json): reported import, not newly reproduced raw rows or original website recommendations. DK and Sleeper contest thresholds stay separate.
- [Original failed attempt](OU_FAILURE_V1.json): failed package import before NFL numeric decoding; its budget and failure capsule remain preserved. The technical continuation has its own identity.
- [Training-history prose correction](TRAINING_HISTORY_CORRECTION_V1.json): 2026 base/ordered/backfield controls fit 2019–2025 REG; the separate target CDF fits 2022–2025. No scores or forecasts changed.

The approved private grade capsule contains the complete prediction/actual/direction CSV and an interactive player-level scorecard. [Safe manifest and execution receipt](../../category-topfive-opportunity-four-ou-20261030/PUBLIC_EXECUTION_RECEIPT_TECHNICAL_V2.json). Restricted rows and private locations are not public. Off-host restoration remains unattested. Creation-time draft/publication fields remain unchanged; later acceptance/publication records supply the current state.

## Capture, website and ownership

At **9:52 p.m. CDT October 29**, the served pointer still identified the earlier 1,945-row selected feed, with its original October 28 issue times. Website Main is `911a81a31f822de58e0f9c04ded070f8c9752670`; lease 178 remains retained. The latest original scheduled research run `40932594714` is failed, enqueue skipped. This wave captured **zero** new original-producer forecasts and deployed **zero** replacements.

The next configured parent window is **Friday October 30, 7:36–7:57 a.m. CDT**, pending execution. The next remaining registered T−90 deadline is **Sunday November 1, 10:30 a.m. CST**. The missed October 29 morning capture remains missed; the original private method/game census and assignments need owner restoration. [Latest runtime proof](runtime/FINAL_RUNTIME_DELTA_V3.json).

V2 acknowledged the ownership split in comment `6513284161`: the original session retains targets and retained-CDF continuation; V2 owns its distinct source-availability ablation. Its separate reported captures are not original-producer capture. Production-owner acknowledgement and admission remain unobserved.

The retained owner must restore the original census, admit eligible core `stat_point_mae_v2` outputs independently of new wrappers/targets, capture before the actual cutoffs, and return per-method counts, persistence and served-value proof. [Executable package and completion criteria](OWNER_ACTION_PACKAGE.json). There is no new general approval or eight-week prerequisite.

## Post-interruption refresh — October 30, 11:33 a.m. CDT

The workspace returned and all four target/OU freeze and grade capsules matched their original SHA-256 values (11,411,863 bytes total). This is same-workspace restoration evidence, not off-host restoration. No forecasting job was rerun.

Friday’s 7:36–7:57 a.m. CDT parent window has elapsed. Fresh workflow metadata still shows run `40932594714` as the latest original workflow run; no Friday execution was observed. Record the parent window as **MISSED_NO_OBSERVED_EXECUTION**. Other/private capture remains **UNVERIFIED** until owner census restoration. The served pointer, website Main and lease 178 remain unchanged.

The next daily parent slot is Saturday October 31, 7:36–7:57 a.m. CDT, pending execution. The next remaining registered game T−90 deadline is Sunday November 1, 10:30 a.m. CST. Preserve daylight-saving changes and original assignments.

The exact owner package was delivered and remotely read back in [comment 6527892507](https://github.com/NickNicky19/NFL-forecasting/pull/1#issuecomment-6527892507). This is delivery, not acknowledgement or execution. No owner reply or new original-producer capture/release is observed. See [publication proof](PUBLICATION_READBACK_V3.json) and the post-interruption runtime receipt when published.
