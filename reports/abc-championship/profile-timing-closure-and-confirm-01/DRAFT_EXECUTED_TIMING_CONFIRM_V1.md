# Executed timing closure and product decisions — draft V1

**New exact-version saved-output joins completed:** B’s `B-QB-ALIGNED-FRESHNESS-v1` completion F0–F3 now have **2026 W1–5, 88 decided retained actual-line cases / 51 games** on A’s annual-source board. C’s exact C04 F0–F3 point rules now have **W1–5, 412 common decided cases / 53 games**, with broader board coverage retained. These extend A owner-local coverage; B’s four-week native panel and C’s two-week native panel remain separate. This replay adds no new games or original issuance.

**Replacement decision:** retain the stronger compatible controls. B’s new timing mean gain is inconclusive and still below A CatBoost/HGB. C’s one-day means lose to their own seven-day baselines; its medians do not establish improvement. No A model release, new fit, model inference, or new original selection was performed for these joins.

## 1. Scope, records and independent checks

Requested primary window remains2026 W1–8. The tables below use only **`ANNUAL_NAMED_NJ`, W1–5**: retained real lines with **unverified quote/decision timing**, chronological/current-vintage reconstruction and exposed development outcomes. They are not authenticated original pregame selections or verified bookmaker returns.

- **B:** eligible88, forecast-selected88, decided88, unavailable/unknown/abstention/push0;51games/88player-games. Fixed shared mask. Saved fallback state is `none`; this is not independent fit reproduction. Mean, median and P2 are separate products; P2 matches median direction here and remains in machine tables.
- **C:** full annual eligible469, forecast-selected421 (**89.77%**),48unavailable,9selected participation-unknown,412decided;53games. Fixed pool 412/412, no pushes/abstentions. F2/F3 row fallback/profile/imputation flags are **UNKNOWN_NOT_EXPORTED**. Only F0/F1 reuse exact C03 flags.
- **W6–7 remain separate diagnostics:** B’s56 site-threshold rows and C’s255 additional decided rows do not turn this into seven qualified actual-offer weeks. No W8 retained offers in these joins. The unresolved W5 A/B source-overlap disposition remains separately source-bound; do not sum panels or treat repeated player-games as independent.
- Independent membership/side checks: [B calculation](B_TIMING_INDEPENDENT_CALCULATION_V1.json), [C calculation](C04_INDEPENDENT_ARITHMETIC_V1.json), and [public-projection validation](TIMING_PUBLIC_PROJECTION_VALIDATION_V1.json). No independent fit or historical quote-clock authentication.

## 2. Completion: exact new B F0–F3

Namespace **`B-QB-ALIGNED-FRESHNESS-v1`**; QB/full-game-OT completions; unchanged strict point-versus-line rule. F0 original inputs/seven-day; F1 profile/seven-day; F2 original inputs/aligned48-hour reconstruction; F3 profile/aligned48-hour reconstruction. The 48-hour policy is reconstructed. Each row: 88 eligible/selected/decided, 51 games, W1–5, same evidence tier.

| Exact arm / output | Over W–L/N/% | Under W–L/N/% | Combined W–L/N/% | MAE / bias | Brier | Own combined week 95% | Wins vs strongest retained |
|---|---:|---:|---:|---:|---:|---:|---:|
| `F0` / mean | 6–3/9/66.7% | 37–42/79/46.8% | **43–45/88/48.9%** | 5.12265 / -3.10254 | 0.26191 | 41.8–56.6% | -9 |
| `F0` / lower_median | 11–4/15/73.3% | 36–37/73/49.3% | **47–41/88/53.4%** | 4.75000 / -2.22727 | 0.26191 | 49.4–57.9% | -5 |
| `F1` / mean | 6–6/12/50.0% | 34–42/76/44.7% | **40–48/88/45.5%** | 5.09227 / -2.86827 | 0.26752 | 35.1–51.7% | -12 |
| `F1` / lower_median | 8–8/16/50.0% | 32–40/72/44.4% | **40–48/88/45.5%** | 4.88636 / -2.22727 | 0.26752 | 36.7–49.4% | -12 |
| `F2` / mean | 11–4/15/73.3% | 36–37/73/49.3% | **47–41/88/53.4%** | 4.99811 / -2.59437 | 0.26255 | 48.8–59.5% | -5 |
| `F2` / lower_median | 11–7/18/61.1% | 33–37/70/47.1% | **44–44/88/50.0%** | 4.82955 / -2.01136 | 0.26255 | 43.8–55.4% | -8 |
| `F3` / mean | 6–5/11/54.5% | 35–42/77/45.5% | **41–47/88/46.6%** | 5.09373 / -2.53946 | 0.26466 | 34.4–56.8% | -11 |
| `F3` / lower_median | 12–8/20/60.0% | 32–36/68/47.1% | **44–44/88/50.0%** | 4.87500 / -1.98864 | 0.26466 | 39.6–54.5% | -8 |

**Strong controls on those same88 cases:** A `CATBOOST_MEDIUM / mean_objective_point` **25–13/38 Over;27–23/50 Under;52–36/88 (59.09%) combined**. A `HGB_MAE_DIRECT / mae_objective_point` ties combined52/88 with26–14/40 Over and26–22/48 Under. Always-Over48/88 (54.55%); Always-Under40/88 (45.45%). None of the new B products beats the better constant side or the52-win learned leaders here. B F2mean versus CatBoost is−5wins/−5.68points, game 95%[−15.82,+3.45], week 95%[−11.28,+1.59].

| Exact within-method contrast | Output | Change in wins | Change, percentage points | Game95%, points | Week95%, points |
|---|---|---:|---:|---:|---:|
| F1−F0: Profile under seven-day | mean | -3/88 | -3.41 | [-9.77, +2.91] | [-9.39, +1.35] |
| F1−F0: Profile under seven-day | lower_median | -7/88 | -7.95 | [-15.76, -2.20] | [-17.02, -4.72] |
| F2−F0: Timing without profile | mean | +4/88 | +4.55 | [-1.24, +12.16] | [-4.88, +14.71] |
| F2−F0: Timing without profile | lower_median | -3/88 | -3.41 | [-10.91, +4.07] | [-11.43, +2.25] |
| F3−F2: Profile under alternative | mean | -6/88 | -6.82 | [-14.88, -0.53] | [-16.39, -2.08] |
| F3−F2: Profile under alternative | lower_median | +0/88 | +0.00 | [-9.24, +8.80] | [-8.19, +4.76] |
| F3−F1: Timing with profile | mean | +1/88 | +1.14 | [-4.60, +6.86] | [-5.93, +8.82] |
| F3−F1: Timing with profile | lower_median | +4/88 | +4.55 | [-2.25, +11.18] | [+1.75, +6.61] |

B’s broader 2025/2026 numerical timing benefit remains in its original population. Here F2mean MAE improves5.12265→4.99811, but **F3mean MAE worsens5.09227→5.09373** versus F1. All Briers exceed the matched binary 0.25 reference. AUC/reliability remain in machine tables. No confidence, 90%, Top Picks or profitability claim follows.

**Decision:** timing/profile direction replacement **INCONCLUSIVE / KEEP_STRONG_RETAINED_CONTROL**; Preserve numerical benefits for scoped owner review; close this exact timing comparison without more lag/seed/offset/cutoff search.

## 3. Receptions: exact C04 point replay

Namespace **`C-RECEIVING-ALIGNED-TIMING-v1`**; WR/TE reception mean and median; unchanged unrounded point-versus-line rule. **F0 is the exact C03 R1 support baseline; F1 is C03 R2 player-profile**, both seven-day. F2/F3 use the corresponding aligned one-day timing sensitivity. **Typed points only**, no probability/Brier/confidence/EV. Each row: 412 fixed decided, 53 games, W1–5; outer board 469 offers.

| Exact arm / output | Over W–L/N/% | Under W–L/N/% | Combined W–L/N/% | MAE / bias | Brier | Own combined week 95% | Wins vs strongest retained |
|---|---:|---:|---:|---:|---:|---:|---:|
| `F0` / MEAN | 109–84/193/56.5% | 127–92/219/58.0% | **236–176/412/57.3%** | 1.71332 / -0.40538 | N/A points only | 54.5–59.2% | -3 |
| `F0` / MEDIAN | 78–57/135/57.8% | 154–123/277/55.6% | **232–180/412/56.3%** | 1.72573 / -0.75000 | N/A points only | 53.9–57.9% | -7 |
| `F1` / MEAN | 106–92/198/53.5% | 119–95/214/55.6% | **225–187/412/54.6%** | 1.71458 / -0.39448 | N/A points only | 51.7–56.6% | -14 |
| `F1` / MEDIAN | 76–52/128/59.4% | 159–125/284/56.0% | **235–177/412/57.0%** | 1.71845 / -0.75243 | N/A points only | 53.9–59.3% | -4 |
| `F2` / MEAN | 103–98/201/51.2% | 113–98/211/53.6% | **216–196/412/52.4%** | 1.72536 / -0.36688 | N/A points only | 48.8–54.1% | -23 |
| `F2` / MEDIAN | 74–53/127/58.3% | 158–127/285/55.4% | **232–180/412/56.3%** | 1.71359 / -0.69903 | N/A points only | 52.5–59.3% | -7 |
| `F3` / MEAN | 106–100/206/51.5% | 111–95/206/53.9% | **217–195/412/52.7%** | 1.72352 / -0.35116 | N/A points only | 51.4–53.2% | -22 |
| `F3` / MEDIAN | 73–50/123/59.3% | 161–128/289/55.7% | **234–178/412/56.8%** | 1.71602 / -0.70146 | N/A points only | 53.4–59.6% | -5 |

**Strong learned control:** retained `C::PLAYER-CONTEXT-MATCHUP-01::v1.1::P1::mean` scores **78–50/128 Over;161–123/284 Under;239–173/412 (58.01%) combined**. A Leaf mean238/412 and median236/412 remain visible; Always-Under211/412, Always-Over201/412. F2mean loses23wins to the239-win leader: game 95%[−10.37,−0.96]points, week 95%[−13.19,−1.94]. F3median loses5wins: game 95%[−4.85,+2.19], week 95%[−4.29,+0.80]. Do not label a constant-side gain as strongest-method superiority.

| Exact within-method contrast | Output | Change in wins | Change, percentage points | Game95%, points | Week95%, points |
|---|---|---:|---:|---:|---:|
| F1−F0: Profile under seven-day | MEAN | -11/412 | -2.67 | [-4.28, -1.20] | [-3.61, -1.50] |
| F1−F0: Profile under seven-day | MEDIAN | +3/412 | +0.73 | [-0.97, +2.23] | [-0.58, +1.84] |
| F2−F0: Timing without profile | MEAN | -20/412 | -4.85 | [-9.09, -1.27] | [-8.60, -2.40] |
| F2−F0: Timing without profile | MEDIAN | +0/412 | +0.00 | [-2.85, +2.64] | [-3.12, +3.42] |
| F3−F2: Profile under alternative | MEAN | +1/412 | +0.24 | [-1.42, +1.84] | [-1.20, +2.47] |
| F3−F2: Profile under alternative | MEDIAN | +2/412 | +0.49 | [-1.47, +2.59] | [-1.64, +2.44] |
| F3−F1: Timing with profile | MEAN | -8/412 | -1.94 | [-6.12, +1.95] | [-3.42, +0.12] |
| F3−F1: Timing with profile | MEDIAN | -1/412 | -0.24 | [-3.02, +2.46] | [-1.25, +1.24] |

**Decision:** **CLOSE_RECIPE_NO_GAIN** for the one-day timing direction recipe; retain seven-day/control products in their existing scopes. F2mean loses20decisions and F3mean loses8 against their own baselines; medians tie or loseone. This longer panel does not establish that all freshness, role or receiving-profile mechanisms fail. No probability claim is added to C’s original two-week law panel.

## 4. What actually advanced, and what remains qualified

These exact products now have five scored season-weeks on the annual diagnostic panel: **duration only**, not inherited base history or automatic primary approval. Timing, support, superiority and operational admission remain separate; no five-new-future-week wait.

No historical season added. Missing 2026 W6–8 and prior-season actual-offer cells remain queued with line/source/history dependencies. Preserve [prior A results and adverse diagnostics](../profile-increment-to-release-01/closure-next-02/) without reruns. Defense effects remain in completed C03/R0–R3 evidence; none fitted here.

## 5. Genuine packets, producer and website state

- **C frozen75:** `C-C04-20261110-W10-FIRST-01`,25 players×3reception procedures, one WAS–NYG game, issued2026-11-10 19:37:43.972513 UTC; server run 42889831779 persisted/completed19:55:36 UTC. **Zero offers and zero selected sides.** KickoffNov 13 01:15UTC (Nov 12 7:15p.m.CST), still future; grade only when qualified final outcomes arrive. Fresh-display expiry is **Nov 12 03:34:29UTC**, before kickoff; retain original bytes for later grading. C owns this grading. Native missing/duplicate event checks hold the other13 W10 games.
- **Original incumbent:** preserve the earlier1610-forecast c134 packet. Later `01a283a2...`: 1,614 forecasts / 424 player-games / 14 games, generated 20:46:29 UTC, captured 20:46:31 UTC; separate refresh. Scheduled run 42898382015 succeeded20:45:25–20:53:09 UTC. Quote clocks remain unverified; these counts are forecasts.
- **Served state:** readback22:49UTC reports `DISABLED_USE_R0`,0selected research rows/2027reference fallbacks, pointer/hash match. No CountA activation verified. C research site has owner-local75-row browser parity plus separately verified public bytes; A did not execute public browser/mobile DOM verification. No original-site model consumption established.
- **A current-shadow inputs:** current C source bytes and all seven ACT WAS/NYG RB candidates exist. Not starter/health probabilities. Exact fresh A F0/F3 rolling history still needs the compatible dense weekly roster/presence/participation census, qualified game-version/finality map and real observation clocks. C’s retained PBP projection also omits **EPA actually consumed by F3**. Keep all 13 held W9 games excluded. Sparse stats cannot replace dense census or turn absence into zero. This is a precise source-contract gap, not generic raw-data absence.
- **CountA is separate:** existing registered A producer still needs current `SOURCE.json`, qualified query completion, `feature_capture_receipt` and a real repaired issuedRoot (≤61440serialized bytes including issuance fields), followed by permitted derived publication and original-owner admission. F3’s EPA requirement is **not a CountA prerequisite unless CountA’s own bound recipe consumes it**. Corrected `FORECASTS.parquet.point` is the stored mean; old `legacy_point` is mixed fallback and old `mean` isNaN. Do not repeat completed restoration or substitute barepredict/median.

Receipts, owner lease 178 and clocks: [readback refresh](RECEIPT_AND_CAPTURE_REFRESH_V1.json), [current source qualification](CURRENT_SHADOW_SOURCE_QUALIFICATION_V1.json). C at d3d1 acknowledges older A1511/B0503 aggregates; B’s 19:22 receipt pins A662. A375/a969 C03/CMP are published; **new peer acknowledgement/admission not observed**. Do not repeat joins.

## 6. All twelve category/product dispositions and next executor

Package decisions only. Original-site overlay remains R0 fallback; no A activation.

| Category | Numerical / direction / probability / selector disposition | Next owned action or exact dependency |
|---|---|---|
| pass_yd | Retain existing candidates; no new timing join here; no new release | B: next qualified coverage; website owner: eligible admission. |
| pass_td | Existing CountA delivery **BLOCKED** at current producer receipt, not a new fit | A producer: current SOURCE/query/issuedRoot; website owner: admit/verify valid feed. |
| pass_cmp | New five-week point/law diagnostic complete; timing replacement **INCONCLUSIVE**, retain52/88 compatible learned controls | B: acknowledge scoped results; A: qualified W6–8 offers. |
| pass_att | Prior exact joins complete; no new timing replacement claimed | A/B: retain completed ATT; add only missing exact-version coverage. |
| pass_int | No new profile/timing evidence in this package; keep existing eligible path | A/B producer owners: exact offered-line and current-feed evidence. |
| rush_yd | Prior A five-week signal **INCONCLUSIVE** for replacement; no rerun | A/C: compatible current census/finality/EPA; A: preserve adverse results. |
| rush_att | Closed negative allocation/carry recipes remain closed; no new policy | A: qualified role/opportunity follow-on; capture ready references. |
| rec | Exact C04 five-week point replay complete; **CLOSE_RECIPE_NO_GAIN** for one-day direction; retain stronger compatible239/412 procedure for existing review scope | C: intake exact evidence and grade frozen packet; website owner: admission. |
| rec_yd | No new exact-line timing decision; prior context/source limits preserved | C: finite receiving coverage/source work; no invented tracking. |
| rush_rec_yd | No new compatible composite offered-line panel | A/C: component-complete outcomes, exact rule and matching offer. |
| anytime_td | **BLOCKED** for this package’s offered-event comparison | Source/product owner: event offer and compatible TD/participation/settlement contract. |
| nick-chart-ppr-v1 | **BLOCKED** for this package’s offered/chart product | Label/website owners: exact chart-offer and 16-primitive grade contract. |

Top Picks: website owner leads the exact changed selector replay; B verifies, C records. Category history does not qualify a changed ranker. Keep independent display/direction paths isolated; missing replay must not block eligible releases.

## 7. Reproducibility and durable-publication stages

This draft formats existing aggregates only; no regrading. Formatting environmentPython3.12.14. Root execution code/configuration, bootstrap seed and command bindings are in the [B scoring GO](B_TIMING_COMPLETION_SCORING_GO_V1.json), [C scoring GO](C04_SCORING_GO_V1.json), and independent receipts. Common protocol SHA256`fa19581487519a854948269bc1ce328cbbcdc734afee2464f1ff778d1ff241a1`; scorer SHA256`2ba450f91bb5fac869ce3adde031099390ec70408a91204653869032b49b2bce`. Join-registration hashes identify separate job documents.

| Exact result | Bytes /SHA256 | Durable stage at draft |
|---|---|---|
| B exact timing result |358620 /`841d874dd4eb15d7aca10195464ba54a6200d1ee0639e89df12885bf23707cf0`| Root retention/readback **pending receipt at draft**; do not call fully durably closed yet. |
| C04 exact point result |143263 /`787ad98445bb56063fed86a95cfed360e939e2a041b0ef9efe5c8f6921e9e91a`| Native readback **PASS**, preserved score/view plus failure/correction receipts. |
| A frozen source bundle |`753970f359a5089286dde4c7ace6eeeb02c82b59eed07a50fd8ecc797eec8c33`| Protected owner-local; no public raw-row permission implied. |
| A exact offers /corrected labels |`f224f17930e8da7ed5683808de3339d9656cc4b71edb0deefcfb9c48dfd82ffb` /`61da98ad90542b07c6c6664b674086ba4f9474e597325aba62dec44bb2fa72f5`| Existing protected source bindings retained. |

Full weekly/cumulative records, controls, paired intervals and member-hash bindings: [B public table index](b-timing-public-v1/INDEX.csv), [C public table index](c04-public-v1/INDEX.csv). Failures/corrections remain preserved. Five exposed week clusters, repeated players and multiple views limit bootstrap interpretation; crossing zero does not prove equivalence. Publication, acknowledgement and use remain separate.

**Boundary:** saved-output joins complete. Current A source closure, CountA issuance, selector replay, missing periods and consumer receipts retain their owners. No new fit, inference, selection or release; independently eligible delivery/capture continues.
