# Actual initial provisional release — 2026-10-24

**The initial selected display is live and verified. The full operational goal is not complete.** This checkpoint records existing evidence through 2026-10-24T22:19:29.835450+00:00; preparing it made no new HTTP requests, tests, model decodes, fits or outcome reads.

## Actual deployment

- [Live Props page](https://nicknicky19.github.io/nicks-expert-nfl-picks/#/props): 1,754 selected rows across 13 future games and 11 targets are primary displays.
- [Lab run 40135574441](https://github.com/NickNicky19/NFL-forecasting/actions/runs/40135574441): all three capture/restore/export jobs succeeded, using [source 93e20191](https://github.com/NickNicky19/NFL-forecasting/commit/93e2019144be7b51248ce548fe247c6dcd949b71); [actual export job](https://github.com/NickNicky19/NFL-forecasting/actions/runs/40135574441/job/120996934563).
- [Website PR #3](https://github.com/NickNicky19/nicks-expert-nfl-picks/pull/3) merged at **2026-10-24 21:56:34 UTC**, with [source head 32870c19](https://github.com/NickNicky19/nicks-expert-nfl-picks/commit/32870c1909b4b99a4580b4224f92f8143f493318) and [merge 315be5e8](https://github.com/NickNicky19/nicks-expert-nfl-picks/commit/315be5e86a1a3a93022b68c453739076487e2077). The [normal Hourly run 40136412412](https://github.com/NickNicky19/nicks-expert-nfl-picks/actions/runs/40136412412) and its [first Pages deployment](https://github.com/NickNicky19/nicks-expert-nfl-picks/actions/runs/40136412412/job/120998759798) succeeded. Build source is the merge commit; [generated output 02f55b0f](https://github.com/NickNicky19/nicks-expert-nfl-picks/commit/02f55b0fad18d0699ac2b227ac5745cdd795969d) is recorded separately.
- TLS-enabled readback matched all six expected assets. Actual browser DOM checks passed **nine scenes: three products × 320/390/1280 pixels**, with no injected fixtures or page-data mutation. The first local certificate failure remains recorded; the successful attempt preserved TLS verification and existing trust settings.

The [public machine-readable checkpoint](PUBLIC_RELEASE.json) contains aggregate results, exact public commits/run/job links, asset hashes and live checks. Detailed operational receipts and the expanded internal execution ledger remain private. Individual forecast values, provider rows, model artifacts and private operational locators are not copied here.

## Category display

| Category | Registered startup method | Product | Public selected rows | Website-relative gain |
| --- | --- | --- | ---: | --- |
| pass_yd | LAB_CDF | point_median | 36 | N/A |
| pass_td | LAB_CDF | point_mean | 36 | N/A |
| pass_cmp | LAB_CDF | point_mean | 36 | N/A |
| pass_att | LAB_CDF | point_mean | 36 | N/A |
| pass_int | LAB_CDF | point_mean | 36 | N/A |
| rush_yd | LAB_CDF | point_median | 99 | N/A |
| rush_att | COUNT_A | point_mean | 99 | N/A |
| rec | COUNT_A | point_mean | 362 | N/A |
| rec_yd | CATBOOST_MEDIUM | point_median | 362 | N/A |
| rush_rec_yd | CATBOOST_MEDIUM | point_median | 261 | N/A |
| anytime_td | TD_EQUAL_CDF_CAT | binary_probability | 391 | N/A |
| fantasy_ppr | R0_UNCHANGED | R0 unchanged; exact PPR labels blocked | 0 | N/A |

Totals are **605 count means, 758 yard medians and 391 TD probabilities**. The TD startup method uses equal 0.5 LAB_CDF / 0.5 CATBOOST_MEDIUM weights. The 2,832 private selected rows include 1,078 retained outside the canonical visible board; those remain outside-board R0/fallback coverage. A zero in the PPR selected-row column records no selected PPR release; existing R0 remains available.

**Live website-relative gains are N/A because these future games are unplayed.** The startup choices draw on exposed 2022–24 source-matched reports ([historical report commit](https://github.com/NickNicky19/NFL-forecasting/commit/adbd11e7d7aaa1756509eb02c621699ca1ea8678)), without an original historical SITE/R0/raw comparator. This release establishes neither a new predictive win nor optimality or scientific confirmation. All categories remain scientifically unqualified.

The canonical R0 engine, picks, leans, ranking and scoring remain preserved, with R0 shown as an explicit reference alongside selected primary displays. Exact PPR remains label-blocked. The [frozen policy](https://github.com/NickNicky19/NFL-forecasting/blob/93e2019144be7b51248ce548fe247c6dcd949b71/config/weekly-provisional-live-policy-v1.json), SHA-256 `0ee3eccf4f0e9ed85ee46c6ba4f6df404459fb4f3cabba469bf6dffd9ee2456c`, retains its original staged fields and bytes; this separate checkpoint records the later release. Original scientific registrations and gates remain unchanged.

## Remaining work

- The existing daily website updater is configured for **08:06 America/Chicago**. Its next configured run is **2026-10-25 13:06 UTC**; that scheduled execution has not yet been observed.
- Lab recurring capture/grading and weekly training/selection/publication handover remain **pending implementation and hosted verification**. ChatGPT research automation remains **paused**. No duplicate scheduler was created.
- The next registered decision deadline is **2026-10-29 18:15 UTC**; this checkpoint does not enable it automatically. Pending finite experiments remain tracked in [RESEARCH_INDEX](../RESEARCH_INDEX.md).

All earlier failed software/resource/source/inference attempts, unknown counts and consumed claims remain privately retained; reviewed source summaries also appear in the versioned [V3](https://github.com/NickNicky19/NFL-forecasting/tree/93e2019144be7b51248ce548fe247c6dcd949b71/reports/weekly-initial-continuation-v3), [V4](https://github.com/NickNicky19/NFL-forecasting/tree/93e2019144be7b51248ce548fe247c6dcd949b71/reports/weekly-initial-continuation-v4), [V5](https://github.com/NickNicky19/NFL-forecasting/tree/93e2019144be7b51248ce548fe247c6dcd949b71/reports/weekly-initial-continuation-v5) and [V6](https://github.com/NickNicky19/NFL-forecasting/tree/93e2019144be7b51248ce548fe247c6dcd949b71/reports/weekly-initial-continuation-v6) reports. The initial TLS failure and successful browser attempt retain separate private receipts. The GitHub execution ledger remains an earlier public snapshot; this aggregate publication does not upload the expanded internal ledger. No earlier evidence or budget is reset by this release.
