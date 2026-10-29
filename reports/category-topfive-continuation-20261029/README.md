# Original NFL continuation: new carry information comparison

Completed October 29, 2026, America/Chicago. Prior checkpoint **b246e44** remains complete; its ordered-history fits and all losses were reused.

## What actually changed

| Comparable RB carry forecasts | Median MAE, carries | Difference |
|---|---:|---|
| New backfield-information CDF | **3.534221** | 3.48% below BASE; 2.36% below ORDERED |
| Prior ordered-history CDF | 3.619772 | Earlier completed procedure, reused |
| Original matched CDF | 3.661597 | Unchanged learner/control, reused |

MAE is the average absolute miss in carries. Lower is better on these same cases.

**One new predictive fit, 32 trees and 2,999 new reconstructed forecasts.** The same original 668 RB queries yielded 526 supported outcomes across 93 games and six weeks. The 142 unknown outcomes remain unknown; 92 supported played-zero outcomes and 32 registered fallbacks are retained. Four procedures produce 11,996 saved rows, not 11,996 independent football observations.

The new group adds observed earlier backfield carry volume, other-RB carries, positive carriers, concentration, own share and missingness from the latest three admitted team games. Base features, CDF learner, priors, query population and controls are unchanged. This does not establish current injury or teammate-availability adaptation. The old assumed kickoff-plus-seven-day timing lane remains explicit.

Game-clustered 95% intervals for candidate-minus-control absolute error are **[-0.2002, -0.0600] carries versus BASE** and **[-0.1550, -0.0269] versus ORDERED**. Six weeks do not meet the registered eight-cluster rule for a week interval. These repeatedly examined development games do not establish future superiority or a gain over today's displayed website forecasts.

Adverse findings are retained: median signed bias worsens against BASE (-0.8669 to -0.9715 carries), and exact-count precision falls. p90/p95 errors improve against BASE. Mean MSE separately improves to23.2957 from24.3471; this is a mean product. Candidate-only CRPS/log loss do not establish better prop probabilities or calibration.

Independent fresh-process acceptance passed **1,253 checks /64 metric cells**, all three capsules and 5,544,062 retained bytes. Frozen point bits, coverage, weekly scores and paired intervals reconciled. The reviewer did not deserialize models or independently reconstruct laws/source rows. Full diagnostics are in [RESULTS.json](RESULTS.json).

## Twelve-category selection and actual live status

The first eleven numeric rows use current2026W1–6 point-display MAE. ATD uses its separate probability primary. These are observed research leaders, not blanket operational admissions. Other research lists and historical panels remain at [b246e44](https://github.com/NickNicky19/NFL-forecasting/blob/b246e44b5fa85ea46a0b6294d1347709933a5fb2/reports/category-topfive-20261029/RESEARCH_RANKINGS.md).

| Category | Comparable research leader | Primary error | Actual website procedure observed |
|---|---|---:|---|
| Passing yards | Leaf CDF median |62.279621 yards|CDF median|
| Passing TDs | Leaf CDF median |0.824645 TD|CDF mean|
| Completions | Leaf CDF median |5.118483 completions|CDF mean|
| Passing attempts | Leaf CDF median |7.772512 attempts|CDF mean|
| Interceptions | Leaf CDF median |0.601896 INT|CDF mean|
| Rushing yards | Leaf CDF median |18.425856 yards|CDF median|
| Rushing attempts | **Backfield-information CDF median** |**3.534221 carries**|Count A declared mean|
| Receptions | Ordered CDF median |1.247701 catches|Count A declared mean|
| Receiving yards | Leaf CDF median |16.054624 yards|CatBoost median|
| Combined yards | Leaf CDF median |19.925906 yards|CatBoost median|
| Nick chart PPR | Same-chart CDF median |4.679406 points|Old-scoring fallback, not new chart|
| Anytime rush/receive TD | CatBoost probability |Brier0.136472|Equal CDF/CatBoost blend|

Only the carry research minimum changes here. Its updated first five distinct procedures are BACKFIELD, ORDERED, uniform analog, BASE CDF and relevance analog; the remaining methods and negative evidence remain in the catalogue. Existing2025/older/W7/market panels are not pooled into this ranking. No new winner is inferred by comparing errors from incompatible populations.

Prepared stat_point_mae_v2 has **zero new operational admissions in this wave**. Its incumbent fallback remains selected until exact restored model/source/wrapper/catalog/epoch and consumer checks pass. The new backfield context model also requires its own named future wrapper; do not broaden the old base-only guard. No ad hoc scientific waiting rule was added.

## Capture and live release

**No new genuine pregame capture or live deployment occurred in this wave.** At **5:26 p.m. Chicago**, the served overlay remained1,945 selected rows, issued around noonOctober28. A later page build is not a new issuance.

The October29 morning capture was missed; failed parent40932594714 skipped enqueue. Earlier genuine forecasts remain preserved:1,951 public feed rows and11,466 reported private challenger rows. Original per-method/game census and original pre-value capture assignments require approved owner restoration; aggregate counts do not prove coverage. The no-op classification patch remains separate from actual before-deadline capture reliability.

The schedule read confirmed CAR@GB kickoff7:15p.m. and registered cutoff5:45p.m.Chicago. Any missed deadline remains missed; later games/captures retain real timestamps. No backdating or selection of a hindsight-best horizon is permitted.

The retained production owner holds lease178. Handoffs6507269410/6507389359 were delivered through researchPR1, with no acknowledgement observed. See [OWNER_ACTIONS.json](OWNER_ACTIONS.json) and the single self-contained [owner request](OWNER_REQUEST.txt). No website write, competing producer, scheduler dispatch, credential access or Odds API request was made here.

## Executable package and V2 evidence

A new [ordered future-query adapter](../../nfl_lab/category_topfive_ordered_future_v1.py) preserves the frozen four slots, exact source/catalog binding, strict clocks, prior fallback and full-law output. **34 new fictional checks passed**; they are not NFL future inference or admission. [Owner sequence](ORDERED_FUTURE_PACKAGE.md) names exact public dependencies and remaining real-source/model checks. The existing point-policy and consumer package was reused.

[V2 read-only handoff](V2_EVIDENCE_HANDOFF.json) provides immutable public code/config/results, run states and the approved private restoration route without private locations. Public evidence does not reproduce missing private originals, deliver them to V2 or assign a duplicate experiment. Original research ownership remains intact.

The next independent research step is to qualify complete opportunity/eligibility evidence for a structured backfield alternative, and advance receiving/QB information groups. TabICL, chronological TabR, genuine relevance training, targetedNGS/FTN, distributional and market tracks remain queued with their original failures/budgets. The ordered2025 and2026 comparisons were not repeated.
