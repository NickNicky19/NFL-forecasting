# Saved payout information versus football probabilities

Executed October 26, 2026. Registration: `saved-sleeper-payout-proxy-v1`.

## What we found

On **342 matched prop offers across eight games**, a fixed half-football, half-payout-proxy blend had **3.07% lower Brier probability error** than the frozen Leaf-CDF football probabilities. It had **1.10% lower error** than a control that simply moved the football probabilities halfway toward 50%.

This is a modest, measured development lead. It does **not** mean 3.07% more winning props, lower yardage prediction error, or a demonstrated improvement over today's deployed category champions. The football comparator here is the named Leaf-CDF probability procedure at each saved Sleeper line. Its probabilities are not interchangeable with the website's selected point forecasts or point-gap rankings.

The available records are **Sleeper payout multipliers**, not authenticated The Odds API bookmaker prices. The original adapter retained neither the under option's threshold nor quote timestamps. Pairing both multipliers with the saved over threshold assumes their original common-market contract. Gross-versus-profit payout meaning, standalone settlement, boosts and pick'em semantics are unverified. Consequently, the transformation below is a **payout-derived proxy**, not an authenticated fair/no-vig probability or an expected-return calculation.

The bounded search of known website code and caches did not recover a verified The Odds API player-prop price archive. The existing DraftKings adapter retains thresholds without side prices. This does not prove no archive exists elsewhere. The owner has been asked for an existing timestamped export; no API key, new spending or paid request is needed for that route.

## Fixed experiment

All arms and the finite budget were fixed before this study's label join. The session had already examined the completed games and owner screenshots, so freezing now does not make these results untouched confirmation.

For a given saved Sleeper threshold:

```text
F = frozen football P(over) / [P(over) + P(under)]
M = under_payout / (over_payout + under_payout)
H = 0.5 * F + 0.5 * M
N = 0.5 * F + 0.25
C = 0.5
```

`N` tests whether reducing overconfidence explains the apparent benefit without payout information. `C` is the constant-half control. There were no fitted weights, calibrators, new football fits, searches or Monte Carlo draws. Missing/zero football nonpush denominators remain missing. Finite positive payouts are required.

Every current offer is a half-point line. Probabilities forecast **over conditional on no push**; the separate integer-line evaluator excludes actual pushes from every conditional score and retains push counts. No market push mass is invented. There are zero integer-line observations in this run.

Primary scoring uses the same five-arm complete population, selected without outcomes. Supported played-zero and played-nonzero observations are scored; missing statistics, unknown participation and pending games remain separate. DNP is not inferred as zero. All 633 source opportunities remain in the private prediction and CSV exports.

## Matched pooled probability scores

Lower Brier and log loss are better. Brier is the average squared difference between a probability and the actual over/not-over outcome. AUC describes ordering on all scored offers; it is not the hit rate of a Top list.

|Procedure|Brier|Natural-log loss|AUC|
|---|---:|---:|---:|
|Football Leaf-CDF (`F`)|0.249150|0.695513|0.586181|
|Saved payout proxy (`M`)|0.244085|0.681216|0.603900|
|Fixed football/payout blend (`H`)|**0.241503**|**0.675862**|**0.604586**|
|Confidence-reduction control (`N`)|0.244184|0.681484|0.586181|
|Constant 50% (`C`)|0.250000|0.693147|0.500000|

All five use the identical **342** supported outcomes. Observed over frequency was 47.66%; mean predictions were 44.26% for F, 49.71% for M, 46.98% for H and 47.13% for N. H's average probability bias was -0.68 percentage points, compared with -3.40 for F and -0.53 for N. This is aggregate calibration-in-the-large, not evidence of reliable probability calibration in every bin or category.

The prespecified original-role secondary panel has **328** scored offers: Brier F **0.251282**, M **0.243916**, H **0.242466**, N **0.245225**. The pooled gain is therefore not solely from extrapolated QB-rushing rows.

## Every category

Positive percentages mean lower probability error. These are **category-specific threshold-probability** results, not improvements in numerical player-stat forecasts. Offered counts include source opportunities without football probabilities.

|Category|Source offers|Scored|Football F Brier|Blend H Brier|H vs F|H vs neutral N|
|---|---:|---:|---:|---:|---:|---:|
|Passing yards|26|16|0.261806|0.251248|+4.03%|+0.19%|
|Passing TDs|26|16|0.244622|0.243149|+0.60%|+0.03%|
|Completions|26|16|0.252300|0.242043|+4.07%|+2.27%|
|Passing attempts|26|16|0.204828|0.221785|-8.28%|+0.79%|
|Interceptions thrown|26|16|0.243193|0.243724|-0.22%|+0.84%|
|Rushing yards|69|41|0.262548|0.251037|+4.38%|+0.02%|
|Rushing attempts|41|23|0.335369|0.283677|+15.41%|-0.09%|
|Receptions|156|92|0.227877|0.224012|+1.70%|+3.44%|
|Receiving yards|151|89|0.244930|0.242461|+1.01%|+0.10%|
|Rushing + receiving yards|33|17|0.274120|0.256324|+6.49%|+0.11%|
|Exact website PPR|0|0|N/A|N/A|N/A|N/A|
|Anytime rushing/receiving TD|0|0|N/A|N/A|N/A|N/A|

The blend improves eight categories against F and worsens passing attempts and interceptions. The apparently large carry improvement is largely confidence reduction: **H is slightly worse than N for rushing attempts**. Receptions has the largest incremental H-versus-N reduction, **3.44%**, on only 92 outcomes. No per-category winner is independently confirmed.

**A stronger passing comparator changes the answer.** The prespecified Response-CDF secondary covers passing TDs, attempts and interceptions: 78 offers, 48 scored outcomes. Its original probability Brier is **0.232152**; the payout blend is **0.236444**, approximately **1.85% worse**. The neutral control scores **0.237813**. Adding payout information does not automatically improve every football model.

Exact website PPR still lacks its complete label contract and usable price records. Anytime TD has no eligible paired payout records here; an over/under proxy must not be relabeled its event probability.

## Coverage and timing

- Source offers: **633** across ten numeric categories, all half-point thresholds.
- Same-line, same-snapshot complete football/payout pairs: **580**; **53** lack the exact frozen football probability.
- Supported outcomes: **342** in **eight games** of one exposed week, comprising 317 nonzero and 25 played-zero observations.
- Matched unresolved offers: **238**: 216 pending-final, 11 played with a missing statistic, 11 unknown participation. No resolved-only selection or unknown-to-zero filling.
- Outcomes use the already accepted **October 25, 22:49 UTC** finality snapshot. No later game results were acquired or silently imported.
- **35** new payout transformations in one not-yet-started game were durably frozen before its kickoff, using retained old thresholds and unverified quote age. They remain pending and are not represented as fresh-market issuance or scored prospective confirmation.

Predictions and a deterministic selection digest were persisted before the accepted label HTML was decoded. The digest was checked unchanged after joining labels. That ordering protects this execution from label-based reranking; it does not remove prior research exposure.

## Paired uncertainty and rankings

The average paired Brier difference H minus F is **-0.007648**; H minus N is **-0.002681**. H improved both comparisons in seven of eight game blocks and worsened both in one. Descriptive leave-one-game-out pooled ranges are **[-0.012574, -0.005526]** against F and **[-0.003275, -0.002248]** against N. These are sensitivity ranges, **not confidence intervals**. No p-value or durable superiority claim is made from one exposed week.

Before labels, each arm selects at most 12 overs/12 unders globally and five per category/side, with one prop per player-game-side, stable tie breaking and side probability above 50%. Pending selections remain; no replacements are added after outcomes.

|Procedure|Top overs: hit / miss / pending|Top unders: hit / miss / pending|
|---|---:|---:|
|Football F|7 / 2 / 3|3 / 3 / 6|
|Payout proxy M|6 / 3 / 3|6 / 1 / 5|
|Blend H|8 / 3 / 1|3 / 2 / 7|
|Confidence control N|7 / 2 / 3|3 / 3 / 6|
|Matched website point-gap control|5 / 6 / 1|4 / 1 / 7|

The gap control and probability lists share the same **580** finite-gap opportunity pool. Their selected props and resolved coverage differ. This small partial table does not establish a reliable ranking winner or a matched win over the website's actual live Top lists, which use a different offering pool. The constant-half arm selects nothing because no side exceeds 50%. N preserves F's ordering by construction. Numeric gap scores are not fabricated probabilities and receive no Brier score.

## Execution, reproducibility and decision

The study's bounded run allowed 120 CPU seconds, 180 wall seconds, 512 MiB RSS, 128 KiB new private artifacts, zero HTTP, zero fits and zero football inference. Native scoring runtime was **29.067 CPU / 28.863 wall seconds**. A redundant second prediction export exceeded the original byte allocation after predictions, selection freeze and results were already durable. Its failure record remains intact.

A separately pinned export-only continuation reused those frozen predictions/results and the same accepted labels: **8.081 CPU / 7.969 wall seconds**, exit 0. It neither repeated scoring nor regenerated forecasts. The original byte allowance and global 512 MiB retention cap were preserved; no evidence was deleted. Private CSV contains all 633 offers, F/M/H/N probabilities, actuals and explicit outcome states. Public files contain derived aggregates only.

Source commit: `5061e4a807f896f48e23555b18e5af754c8f357d`.
Plan SHA-256: `57d0327dd5b59ea9a2415bb60326b802a577428d4eff41ef4007f146d9908742`.
Export continuation plan: `767401e6d1b61b72aefaa9df5fdd4b3f30f0573f85e99a52d554341432c42957`.
Full artifact and executable hashes, all category scores and aggregate ranking summaries are in [AGGREGATE_RESULTS.json](AGGREGATE_RESULTS.json).

Requested backend was GPT-6.1 Sol Extra High; actual backend is **UNATTESTED**. Separate source, evaluator and read-only review agents were used in isolated worktrees; only the integrator writes the canonical execution ledger.

The independent read-only reviewer accepted all **633 offers, 580 complete pairs and 342 scored outcomes across eight games**, and verified **19 score panels, 48 paired/game analyses, 266 ranking lists** and the frozen selection digest. A separate publication review approved these two aggregate files with no player/game identities, raw payouts, selected picks, private paths or model bodies. Review added no NFL observations.

**Decision:** retain this as a measured payout-proxy development result and a candidate for authenticated later comparison. Do not deploy a universal blend or claim a The Odds API price win from these records. No website policy or scheduler changed; original scientific registrations and failed methods remain untouched. The missing item for the genuine bookmaker-price comparison is a permitted saved export with bookmaker, player/game, matching over/under line and prices, and quote timestamps. An improved point forecast, a better threshold probability and a better Top-list ranking remain separate claims.
