# One request for Nick to relay to Session B

Session A has pinned B research commit `4d4ea743938d10373ab66893e4a2cc0bfa60e0a0`. Its public reports are accessible; its private forecast/outcome/offer rows are not accessible here. Please export **existing cached evidence only** for the frozen A/B roster. This is not a request to refit, regenerate historical decisions, retry missing archive recovery, or duplicate B's assigned source-expansion/passing-yard/completion diagnostics. If a record is itself missing or a recovery rule prevents its export, report that exact member/gate and export eligible retained subsets; do not bypass the gate.

## First, the smallest useful batch

Export the existing 2026 Weeks 5–7 passing-attempt board: all **84 outer opportunities**, including the 80 supported cases and four unavailable/unknown cases. Include the strict-current Leaf/C02 procedures and the corresponding H-MULTI Leaf/C02 controls, their unrounded mean/lower-median products, actual cached probabilities, exact original thresholds and decision/source clocks. Priority probability records include:

- `H3-PROB-f3e34ecbd1276cf77f3c230f` — strict-current Leaf.
- `H3-PROB-67e6e805abbc1ba2e6eaace2` — strict-current C02.

Identify all included source record/run/member hashes in the manifest. Preserve unavailable prediction versus abstention, learned versus prior/fallback, and unknown participation. Do not export only the winning side, decided rows or selected Top Picks.

## Then, the other already-retained categories

Export retained numerical Week 1–7 player-game queries and finalist outputs, plus the complete supported primary offered boards and their existing P1/P2 decisions. Use the versioned [finite roster](FINITE_CANDIDATE_ROSTER_V1.json), preserving every requested entry's missing/unsupported state. Include the selector's **original choices and state IDs**, not a retrospective recomputation. Later weeks and original pregame packets must be separate tables/partitions.

## Format and required contents

One ZIP containing JSON manifests and Parquet/Zstandard tables; CSV.gz is acceptable where it preserves nulls and exact types. Use immutable, numbered batches no larger than **8 MiB compressed** initially. Dictionaries may reduce repeated method metadata. No fitted model binaries or raw upstream feeds are needed for the first join.

1. **MANIFEST / CONTRACTS**: B repository commit; request/procedure/model/config/run/output IDs and hashes; source and outcome versions; source member hashes and row counts; exact statistic/scoring/period/participation contract; population; fit/history/feature-memory/update/calibration rules; forecast and selection-policy versions; evidence tier; horizon and clocks. Missing metadata is null with a reason. A public-safe hash-only manifest may be published in B; restricted tables must remain private.
2. **QUERY_OUTCOMES**: canonical game and player IDs with namespace/crosswalk version; season/week, team/opponent/position, target, scoring contract and game period; intended eligibility/population masks; participation and supported-zero/missing/DNP states; outcome and source revision/finality/provenance. For chart PPR, include all sixteen primitive values and independent completeness/zero-qualification flags, or explicitly mark the exact-chart outcome unsupported. Do not replace missing rare components with zero.
3. **POINT_FORECASTS**: query key, exact method/model/config/history/output IDs, unrounded forecast, functional (mean/lower median/other), failure/unavailable/fallback reason and parent identity; train/tune/calibration endpoints; permitted source-availability cutoff distinct from retrieval, generation, issuance and persistence; original source/member identity. Numerical kickoff and `:known-target-time-v1` offered reconstructions must retain distinct identities.
4. **PRIMARY_OFFERS**: full original primary board, independent of model identity; original game/player/target/period, exact decimal threshold, side where applicable, provider/book/jurisdiction/offer ID, source/quote/capture/decision clocks and their qualification status; participation/settlement rules and uncertainty. Actual prices are optional for direction scoring and remain null when missing. No reception line may become a target line.
5. **OFFER_PROBABILITIES / DECISIONS**: exact opportunity/method/output/policy identity; cached `p_under`, `p_push`, `p_over` and log probabilities where retained; support and participation conditioning; actual saved side or declared deterministic research rule; original versus reconstructed status; abstention separate from unavailable output; fallback origin; original Top6/10/20/abstaining-policy flags if retained. Preserve pending/unknown outcomes.
6. **ROW_PROPER_SCORES**: retained per-row CRPS/NLL and exact outcome/law/contract hashes where available. These scores transfer only after A verifies identical outcomes and contracts. Include a complete retained law representation only if a different shared threshold/outcome truly requires it; do not invent a law from a point.

Keys must allow exact player-game identity matching, not merely equal row counts or fuzzy names. Keep repeated books, refreshes and alternate horizons separate. A will report common-core, pairwise, A-only/B-only and full-system coverage, with separate RB/QB rushing views.

## Approved destination and acknowledgement

Receiver: **Session A's existing approved managed private store**, opaque ingress ID **`AB-20261031-B-CACHED-EXPORT-V1`**, under the registered `session-a-b-matched-v1-20261031` evidence root. The absolute receiver binding stays in A's private transport configuration. Use the established owner-controlled private artifact exchange; confirm the receiver/route acknowledgement before transferring restricted bytes. If no cross-session route is shared, give Nick the private ZIP through the already permitted attachment route to attach to Session A. Do not use a public repository or public-repository Actions artifact as private transport. Do not post private locators or credentials in Git or chat.

Return a permitted manifest ID, complete hashes/bytes/row counts, precise missing members and transfer state. Delivery, receiver acknowledgement, actual restore and paired scoring are separate states. This request is not proof that B has received it.

Existing production release/capture and B's owned diagnostic/recovery jobs continue independently. No new spending, keys, wagers, production writes or scheduler is requested.
