# Week 7 point errors and over/under probability rankings

## Executed status

The requested two-track comparison is now captured and independently replayed. **No new NFL accuracy scores, reliable-ranking finding or deployment is claimed.** These are saved forecasts awaiting qualified outcome grading.

The earlier point packet contains 15,444 forecasts across 48 category/procedure combinations, 610 player-games, 13 games and 11 supported categories. Five games received the corrected point forecasts before kickoff; eight were already-started reconstructions. The pinned current website's selected forecast values reproduce on all 1,754 common opportunities, within floating-point roundoff. This is the current selected website comparator, rather than the older Week 6 SITE reference. Full feature-vintage equality remains unverified.

The probability packet completed at **2026-10-25T21:05:25.611969Z (4:05 PM America/Chicago)**. It contains 2,476 probability forecasts across 1,536 retained offers/event definitions. Those overlapping outputs are not 2,476 independent football observations. There are:

- 594 displayed numeric DraftKings/Sleeper offers;
- 550 separately retained secondary or recorded numeric offers;
- 392 fixed rushing-or-receiving anytime-TD event definitions, not bookmaker quotes.

Two remaining games received the probability packet before kickoff: 369 overlapping probability incidences. Eleven already-started games, covering 2,107 incidences, remain development comparisons. The owner had already shown some Week 7 results in screenshots before this probability policy was defined. No current results were fetched or decoded by this execution, but the earlier exposure is retained explicitly. Hiding results does not make started-game predictions prospective.

## Category coverage

The probability columns refer only to authentic predictive laws. Numeric point-only CatBoost, Count A and point blends remain in the point comparison; no Poisson or other distribution was invented from their points.

| Category | Captured point procedures | Captured probability procedures | Primary displayed numeric offers | Current result |
|---|---|---|---:|---|
| Passing yards | Leaf CDF, CatBoost medium, fixed P4 point blend | Leaf CDF |26|Ungraded|
| Passing TDs | Leaf CDF, Response CDF, CatBoost, legacy/corrected-mean Count A, P4 |Leaf and Response CDF|26|Ungraded|
| Completions |Leaf CDF, CatBoost, legacy/corrected-mean Count A, P4|Leaf CDF|26|Ungraded|
| Passing attempts |Leaf CDF, Response CDF, CatBoost, legacy/corrected-mean Count A, P4|Leaf and Response CDF|26|Ungraded|
| Interceptions thrown |Leaf CDF, Response CDF, CatBoost, legacy/corrected-mean Count A, P4|Leaf and Response CDF|26|Ungraded|
| Rushing yards |Leaf CDF, CatBoost, P4 point blend|Leaf CDF|75|Ungraded|
| Rushing attempts |Leaf CDF, CatBoost, legacy/corrected-mean Count A, P4|Leaf CDF|41|Ungraded|
| Receptions |Leaf CDF, CatBoost, legacy/corrected-mean Count A, P4|Leaf CDF|157|Ungraded|
| Receiving yards |Leaf CDF, CatBoost, P4 point blend|Leaf CDF|156|Ungraded|
| Rushing + receiving yards |Leaf CDF, direct CatBoost total, P4 point blend|Direct Leaf CDF total|35|Ungraded separately|
| Exact website offensive PPR |No qualified replacement|None|0|Exact-label contract blocked|
| Anytime rushing/receiving TD |Leaf CDF, CatBoost binary, fixed equal probability blend|The same three genuine binary procedures|Not a bookmaker line;392 fixed events|Ungraded|

The legacy Count A and corrected-mean fallback procedures retain distinct identities. A Poisson training objective is not treated as a calibrated probability law. These are operationally executable shortlisted procedures, not a claim that every historical hypothesis or unavailable original runner has been recovered.

## Probability and ranking comparisons

For an integer-supported outcome and literal line L, the worker saves all three outcomes:

```text
P(over)  = 1 - F(floor(L))
P(under) = F(ceil(L) - 1)
P(push)  = F(floor(L)) - F(ceil(L) - 1)
```

Half-point lines have zero push mass. Signed yardage remains supported. Exact zero/one probabilities are retained, and a contrary outcome must retain infinite log loss at grading.

Three prespecified ranking procedures were saved: Leaf-CDF side probabilities; Response-CDF for passing TDs/attempts/interceptions with Leaf-CDF elsewhere; and a matched permitted-line-pool scaled point-gap control. Each retains top 12 global overs/unders and top five per numeric category, separately for the whole development slate and future-only games. Fewer eligible offers remain fewer; lists are not padded.

The 24 actual saved website Top entries are retained as a separate reference. The matched-pool gap control does not reproduce every website injury/snap/history filter. The current website's numeric gap ranking supplies no native probability comparator; that probability comparison is unavailable rather than fabricated.

Declared primary scoring is three-way categorical Brier at each displayed numeric offer, separately by category/provider, and binary Brier for anytime TD. Secondary grading includes log loss, calibration/reliability, push mass, coverage, tails and fixed-list outcomes. Point MAE/MSE rankings are evaluated separately under each declared forecast product. No claim of reliable over/under ordering follows from point MAE alone.

## Independent replay and limitations

The separate read-only reviewer restored all 14 CDF states, replayed all 1,692 law-probability rows and 784 genuine binary variants bitwise, rebuilt all 1,536 offers, verified all 24 saved website Top entries, and reproduced all 132 ranking lists exactly. Review used no fits, outcomes, network or writes. The execution itself made zero fits, calibration fits or NFL outcome reads; native use was 32.272 wall seconds and 32.547 CPU seconds.

Source availability remains the original seven-day historical reconstruction; participation/played-zero coverage is incomplete. The lab archive cutoff is October 24 at12:00Z, while the selected website reports October 25 at00:00Z. Saved quote vintages are retained; no fresh odds, prices or provider access was used. Source-publication time is not invented. Synthetic lines and offers outside the authenticated query are counted explicitly, not scored as a favorable subset.

Local immutable persistence and fresh-process replay passed. New remote private-body restoration remains unverified. These shadow outputs have **not** replaced the live Top lists or changed the scheduler. Broad research remains paused outside this narrow requested comparison; old scientific registrations remain unchanged. Calibration and future superiority remain unproven.

## Auditable records

- [Probability capture receipt](PROBABILITY_CAPTURE_RECEIPT.json): versions, hashes, aggregate coverage, resource use and independent acceptance. No raw feeds, row-level forecasts or learned model bodies are published.
- [Earlier point capture receipt](CAPTURE_RECEIPT.json): preserved original point freeze/publication identity.
- [Full-week methods audit](https://github.com/NickNicky19/NFL-forecasting/blob/cae6121e2d4dd0fc5a6c7d2217a93cd242533de7/reports/full-week-method-audit-20261025/README.md): historical gains, losses and comparison limits.

The historical leaders are development leaders on their named populations. Several are already the website's selected families. This packet is the recorded comparison needed to find whether a challenger also beats those current selections on new games; it does not announce a winner before grading.
