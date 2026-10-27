# Modern fixed anytime-TD probability blend

The existing fixed equal mixture was reconstructed from saved CDF and CatBoost event probabilities: **0.5 CDF + 0.5 CatBoost**, with no weight search, calibration fit, model fitting or model calls. The event is at least one rushing or receiving TD, conditional on supported played status. This is a newly versioned historical comparison of an existing recipe, rather than recovered historical website picks.

**The blend does not beat the stronger component on primary Brier score in either period.** CDF has the lower Brier score in 2025; CatBoost has the lower score in 2026 Weeks 1–6. The blend has the lowest 2025 log loss, which remains a secondary finding.

All 11,700 original query rows and 9,729 primary RB/WR/TE offers are retained. 2025 and 2026 are separate exposed current-vintage reconstructions under the original assumed seven-day source timing. Genuine historical website/R0/raw forecasts are unavailable. No category selection, deployment, calibration, market or financial claim follows. Independent numerical and public privacy review passed. Managed private terminal retention and fresh-process owned readback passed. Restoration from a different host remains unverified.

## Primary Brier and secondary log loss

| Period | Procedure | Supported / offered | Brier | Log loss | Infinite log losses | Probability bias |
|---|---|---:|---:|---:|---:|---:|
| 2025 | CDF | 5295 / 7271 | 0.138396228 | 0.436533572 | 0 | 0.005831992 |
| 2025 | CatBoost medium | 5295 / 7271 | 0.138993616 | 0.437240207 | 0 | 0.007800101 |
| 2025 | Fixed equal blend | 5295 / 7271 | 0.138445700 | 0.436248548 | 0 | 0.006816047 |
| 2026 | CDF | 1849 / 2458 | 0.136977356 | 0.433329086 | 0 | 0.005069389 |
| 2026 | CatBoost medium | 1849 / 2458 | 0.136471970 | 0.432080979 | 0 | 0.002442375 |
| 2026 | Fixed equal blend | 1849 / 2458 | 0.136583353 | 0.432266443 | 0 | 0.003755882 |

Log loss is unclipped. Contrary probabilities of exactly zero or one remain positive-infinite row losses, with an explicit summary state and infinity count; they are never removed. All observed primary losses here are finite. Probability bias is forecast probability minus binary outcome.

## Every paired Brier comparison

| Period | Blend compared with | Relative improvement | Week 95% interval, blend − component | Game 95% interval |
|---|---|---:|---|---|
| 2025 | CDF | -0.03575% | [-0.000276735, 0.000342736] | [-0.000315770, 0.000406257] |
| 2025 | CatBoost medium | +0.39420% | [-0.000839457, -0.000226868] | [-0.000908334, -0.000181345] |
| 2026 | CDF | +0.28764% | N/A: six weeks | [-0.000890775, 0.000076374] |
| 2026 | CatBoost medium | -0.08162% | N/A: six weeks | [-0.000352954, 0.000592278] |

Positive improvement means lower Brier. Intervals use 500 whole-week or whole-game PCG64 bootstrap draws, seed 1703. They are nominal exposed-sample diagnostics with repeated-use and model-selection limits. The comparisons with the stronger component cross zero wherever an interval is available. The original six-week interval rule is preserved and is not a deployment waiting period.

## Coverage

| Period | Primary offers | Supported played | Unknown participation | Played missing statistic | DNP | Supported zero | TD event | Fallback offered / scored |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2025 | 7271 | 5295 | 1965 | 11 | 0 | 4288 | 1007 | 180 / 105 |
| 2026 | 2458 | 1849 | 603 | 6 | 0 | 1504 | 345 | 140 / 82 |

Stored component role-prior fallbacks remain part of each procedure. A missing component makes the blend abstain without changing weights; historical R0 is unavailable for fallback. Unknown participation and missing statistics were not converted to zero. Complete all-offered, primary-role and primary-fallback summaries, every week, and ten fixed reliability bins are retained in the machine-readable report. Reliability bins are diagnostics and do not establish calibration.

## Execution and evidence limits

The first run froze both complete blend vectors before labels, then was killed without retaining a grade. Its 31.813 CPU seconds exceed its registered 30-second main CPU cap; it remains **FAILED_CAP_NO_GRADE**. The precise kill cause is unproven. Its 258,361-byte global forecast archive, source evidence and native failure remain preserved. Labels or partial scoring may already have begun in that failed run.

The separately registered scoring-only continuation reused those exact member bytes and probability point bits. It generated zero new vectors and used the unchanged probability-summary kernel. It completed one cached grade in 34.123 CPU / 33.997 wall seconds under its new 60 CPU / 90 wall main cap. The original whole 55 CPU / 75 wall allocation remains recorded; the new 90 CPU / 135 wall technical allocation is separate. No old cap or spent budget was reset.

These repeated procedures do not add NFL observations. Revised historical sources and assumed availability clocks limit any real-time interpretation. The results do not establish an independent prospective advantage, a website-relative gain, qualified calibration, a probability above a prop line, +EV or production activation.
