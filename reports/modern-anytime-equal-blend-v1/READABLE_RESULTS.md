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

## Every weekly primary-role result

| Period | Week | Procedure | Supported / offered | Brier | Log loss | Infinity count | Bias |
|---|---:|---|---:|---:|---:|---:|---:|
| 2025 | 1 | CDF | 318 / 428 | 0.124341904 | 0.409463074 | 0 | 0.052033754 |
| 2025 | 2 | CDF | 304 / 430 | 0.164267491 | 0.503356105 | 0 | -0.017488859 |
| 2025 | 3 | CDF | 309 / 430 | 0.142576545 | 0.449811635 | 0 | 0.007135139 |
| 2025 | 4 | CDF | 308 / 431 | 0.145830376 | 0.452198329 | 0 | -0.011898239 |
| 2025 | 5 | CDF | 281 / 375 | 0.142530806 | 0.441724401 | 0 | -0.023581312 |
| 2025 | 6 | CDF | 286 / 398 | 0.144664791 | 0.458140436 | 0 | 0.003929484 |
| 2025 | 7 | CDF | 295 / 398 | 0.124269042 | 0.397070350 | 0 | 0.013643133 |
| 2025 | 8 | CDF | 254 / 345 | 0.149628520 | 0.461356818 | 0 | -0.023562806 |
| 2025 | 9 | CDF | 277 / 378 | 0.146831347 | 0.459948846 | 0 | 0.005536577 |
| 2025 | 10 | CDF | 273 / 373 | 0.149410718 | 0.460498670 | 0 | -0.022002282 |
| 2025 | 11 | CDF | 288 / 402 | 0.126438155 | 0.406551546 | 0 | 0.032650888 |
| 2025 | 12 | CDF | 274 / 377 | 0.120283258 | 0.393650334 | 0 | 0.034497918 |
| 2025 | 13 | CDF | 309 / 428 | 0.147613872 | 0.456060043 | 0 | -0.009804411 |
| 2025 | 14 | CDF | 286 / 374 | 0.136228610 | 0.430155210 | 0 | 0.003026955 |
| 2025 | 15 | CDF | 299 / 425 | 0.140996649 | 0.443216863 | 0 | 0.006171038 |
| 2025 | 16 | CDF | 316 / 428 | 0.139506151 | 0.433138639 | 0 | -0.014810533 |
| 2025 | 17 | CDF | 316 / 427 | 0.126243446 | 0.405790139 | 0 | 0.021755808 |
| 2025 | 18 | CDF | 302 / 424 | 0.121608033 | 0.400114174 | 0 | 0.040774953 |
| 2025 | 1 | CatBoost medium | 318 / 428 | 0.122871108 | 0.404589140 | 0 | 0.055887786 |
| 2025 | 2 | CatBoost medium | 304 / 430 | 0.164794618 | 0.505377760 | 0 | -0.013587320 |
| 2025 | 3 | CatBoost medium | 309 / 430 | 0.143376719 | 0.450907997 | 0 | 0.010098228 |
| 2025 | 4 | CatBoost medium | 308 / 431 | 0.149428063 | 0.460300357 | 0 | -0.010565483 |
| 2025 | 5 | CatBoost medium | 281 / 375 | 0.140430725 | 0.434916234 | 0 | -0.022295589 |
| 2025 | 6 | CatBoost medium | 286 / 398 | 0.145065415 | 0.458495923 | 0 | 0.005953320 |
| 2025 | 7 | CatBoost medium | 295 / 398 | 0.126222660 | 0.400829973 | 0 | 0.015764672 |
| 2025 | 8 | CatBoost medium | 254 / 345 | 0.150488783 | 0.464838912 | 0 | -0.022520772 |
| 2025 | 9 | CatBoost medium | 277 / 378 | 0.146520239 | 0.458514567 | 0 | 0.008654572 |
| 2025 | 10 | CatBoost medium | 273 / 373 | 0.148320708 | 0.456241356 | 0 | -0.019740272 |
| 2025 | 11 | CatBoost medium | 288 / 402 | 0.127350459 | 0.409692901 | 0 | 0.033292770 |
| 2025 | 12 | CatBoost medium | 274 / 377 | 0.120343776 | 0.391874185 | 0 | 0.036577530 |
| 2025 | 13 | CatBoost medium | 309 / 428 | 0.148113956 | 0.456664407 | 0 | -0.006354707 |
| 2025 | 14 | CatBoost medium | 286 / 374 | 0.138494119 | 0.435145407 | 0 | 0.004424761 |
| 2025 | 15 | CatBoost medium | 299 / 425 | 0.142379226 | 0.445133176 | 0 | 0.009873089 |
| 2025 | 16 | CatBoost medium | 316 / 428 | 0.138640564 | 0.430154081 | 0 | -0.013308734 |
| 2025 | 17 | CatBoost medium | 316 / 427 | 0.127273919 | 0.406059490 | 0 | 0.020336887 |
| 2025 | 18 | CatBoost medium | 302 / 424 | 0.123702352 | 0.404992396 | 0 | 0.040834705 |
| 2025 | 1 | Fixed equal blend | 318 / 428 | 0.123384814 | 0.406564566 | 0 | 0.053960770 |
| 2025 | 2 | Fixed equal blend | 304 / 430 | 0.164293549 | 0.503820083 | 0 | -0.015538089 |
| 2025 | 3 | Fixed equal blend | 309 / 430 | 0.142695821 | 0.449756781 | 0 | 0.008616684 |
| 2025 | 4 | Fixed equal blend | 308 / 431 | 0.147357701 | 0.455505192 | 0 | -0.011231861 |
| 2025 | 5 | Fixed equal blend | 281 / 375 | 0.141233949 | 0.437767803 | 0 | -0.022938450 |
| 2025 | 6 | Fixed equal blend | 286 / 398 | 0.144613874 | 0.457678393 | 0 | 0.004941402 |
| 2025 | 7 | Fixed equal blend | 295 / 398 | 0.125055350 | 0.398568084 | 0 | 0.014703903 |
| 2025 | 8 | Fixed equal blend | 254 / 345 | 0.149835679 | 0.462373281 | 0 | -0.023041789 |
| 2025 | 9 | Fixed equal blend | 277 / 378 | 0.146427490 | 0.458494303 | 0 | 0.007095575 |
| 2025 | 10 | Fixed equal blend | 273 / 373 | 0.148621264 | 0.457625931 | 0 | -0.020871277 |
| 2025 | 11 | Fixed equal blend | 288 / 402 | 0.126643121 | 0.407396919 | 0 | 0.032971829 |
| 2025 | 12 | Fixed equal blend | 274 / 377 | 0.120065691 | 0.392207098 | 0 | 0.035537724 |
| 2025 | 13 | Fixed equal blend | 309 / 428 | 0.147621392 | 0.455732738 | 0 | -0.008079559 |
| 2025 | 14 | Fixed equal blend | 286 / 374 | 0.137117706 | 0.431980383 | 0 | 0.003725858 |
| 2025 | 15 | Fixed equal blend | 299 / 425 | 0.141386658 | 0.443343873 | 0 | 0.008022063 |
| 2025 | 16 | Fixed equal blend | 316 / 428 | 0.138808875 | 0.430844507 | 0 | -0.014059633 |
| 2025 | 17 | Fixed equal blend | 316 / 427 | 0.126500634 | 0.405328071 | 0 | 0.021046348 |
| 2025 | 18 | Fixed equal blend | 302 / 424 | 0.122400545 | 0.401985399 | 0 | 0.040804829 |
| 2026 | 1 | CDF | 316 / 428 | 0.138746033 | 0.433515106 | 0 | 0.003078639 |
| 2026 | 2 | CDF | 319 / 419 | 0.124660264 | 0.410330952 | 0 | 0.046717445 |
| 2026 | 3 | CDF | 318 / 425 | 0.153221679 | 0.475897533 | 0 | -0.009795858 |
| 2026 | 4 | CDF | 318 / 420 | 0.139863627 | 0.435686795 | 0 | -0.012673646 |
| 2026 | 5 | CDF | 300 / 396 | 0.131860939 | 0.421052697 | 0 | -0.008198061 |
| 2026 | 6 | CDF | 278 / 370 | 0.132738675 | 0.421365137 | 0 | 0.011159376 |
| 2026 | 1 | CatBoost medium | 316 / 428 | 0.140501883 | 0.437515843 | 0 | 0.001258067 |
| 2026 | 2 | CatBoost medium | 319 / 419 | 0.123239729 | 0.407249171 | 0 | 0.044332207 |
| 2026 | 3 | CatBoost medium | 318 / 425 | 0.151617073 | 0.472210330 | 0 | -0.011391807 |
| 2026 | 4 | CatBoost medium | 318 / 420 | 0.139516765 | 0.434514502 | 0 | -0.013879021 |
| 2026 | 5 | CatBoost medium | 300 / 396 | 0.130145268 | 0.415509025 | 0 | -0.012549483 |
| 2026 | 6 | CatBoost medium | 278 / 370 | 0.133095189 | 0.423593645 | 0 | 0.006393514 |
| 2026 | 1 | Fixed equal blend | 316 / 428 | 0.139489677 | 0.435127579 | 0 | 0.002168353 |
| 2026 | 2 | Fixed equal blend | 319 / 419 | 0.123820010 | 0.408434402 | 0 | 0.045524826 |
| 2026 | 3 | Fixed equal blend | 318 / 425 | 0.152255429 | 0.473519368 | 0 | -0.010593832 |
| 2026 | 4 | Fixed equal blend | 318 / 420 | 0.139529508 | 0.434619185 | 0 | -0.013276334 |
| 2026 | 5 | Fixed equal blend | 300 / 396 | 0.130855000 | 0.417828459 | 0 | -0.010373772 |
| 2026 | 6 | Fixed equal blend | 278 / 370 | 0.132810031 | 0.422061751 | 0 | 0.008776445 |

## Fixed reliability bins

| Period | Procedure | Probability bin | Rows | Mean predicted probability | Observed event rate |
|---|---|---|---:|---:|---:|
| 2025 | CDF | 0.0–0.1 | 1018 | 0.069777513 | 0.054027505 |
| 2025 | CDF | 0.1–0.2 | 2089 | 0.141702616 | 0.116323600 |
| 2025 | CDF | 0.2–0.3 | 1206 | 0.245318116 | 0.271973466 |
| 2025 | CDF | 0.3–0.4 | 687 | 0.342200945 | 0.347889374 |
| 2025 | CDF | 0.4–0.5 | 204 | 0.438751836 | 0.455882353 |
| 2025 | CDF | 0.5–0.6 | 82 | 0.546474283 | 0.512195122 |
| 2025 | CDF | 0.6–0.7 | 9 | 0.618684911 | 0.777777778 |
| 2025 | CDF | 0.7–0.8 | 0 | N/A | N/A |
| 2025 | CDF | 0.8–0.9 | 0 | N/A | N/A |
| 2025 | CDF | 0.9–1.0 | 0 | N/A | N/A |
| 2025 | CatBoost medium | 0.0–0.1 | 1376 | 0.073233428 | 0.058866279 |
| 2025 | CatBoost medium | 0.1–0.2 | 1760 | 0.142870535 | 0.123863636 |
| 2025 | CatBoost medium | 0.2–0.3 | 1096 | 0.245791598 | 0.270072993 |
| 2025 | CatBoost medium | 0.3–0.4 | 620 | 0.343576024 | 0.364516129 |
| 2025 | CatBoost medium | 0.4–0.5 | 304 | 0.439998578 | 0.368421053 |
| 2025 | CatBoost medium | 0.5–0.6 | 97 | 0.542494271 | 0.494845361 |
| 2025 | CatBoost medium | 0.6–0.7 | 36 | 0.638320852 | 0.666666667 |
| 2025 | CatBoost medium | 0.7–0.8 | 6 | 0.719068497 | 0.333333333 |
| 2025 | CatBoost medium | 0.8–0.9 | 0 | N/A | N/A |
| 2025 | CatBoost medium | 0.9–1.0 | 0 | N/A | N/A |
| 2025 | Fixed equal blend | 0.0–0.1 | 1174 | 0.072209824 | 0.053662692 |
| 2025 | Fixed equal blend | 0.1–0.2 | 1934 | 0.141065924 | 0.124612203 |
| 2025 | Fixed equal blend | 0.2–0.3 | 1158 | 0.245723504 | 0.271157168 |
| 2025 | Fixed equal blend | 0.3–0.4 | 675 | 0.344107933 | 0.324444444 |
| 2025 | Fixed equal blend | 0.4–0.5 | 250 | 0.438954616 | 0.456000000 |
| 2025 | Fixed equal blend | 0.5–0.6 | 77 | 0.545540192 | 0.493506494 |
| 2025 | Fixed equal blend | 0.6–0.7 | 27 | 0.627008024 | 0.666666667 |
| 2025 | Fixed equal blend | 0.7–0.8 | 0 | N/A | N/A |
| 2025 | Fixed equal blend | 0.8–0.9 | 0 | N/A | N/A |
| 2025 | Fixed equal blend | 0.9–1.0 | 0 | N/A | N/A |
| 2026 | CDF | 0.0–0.1 | 388 | 0.069470423 | 0.038659794 |
| 2026 | CDF | 0.1–0.2 | 727 | 0.143003983 | 0.136176066 |
| 2026 | CDF | 0.2–0.3 | 433 | 0.245322900 | 0.251732102 |
| 2026 | CDF | 0.3–0.4 | 179 | 0.338660132 | 0.374301676 |
| 2026 | CDF | 0.4–0.5 | 91 | 0.436056183 | 0.384615385 |
| 2026 | CDF | 0.5–0.6 | 29 | 0.541567982 | 0.620689655 |
| 2026 | CDF | 0.6–0.7 | 2 | 0.611658710 | 1.000000000 |
| 2026 | CDF | 0.7–0.8 | 0 | N/A | N/A |
| 2026 | CDF | 0.8–0.9 | 0 | N/A | N/A |
| 2026 | CDF | 0.9–1.0 | 0 | N/A | N/A |
| 2026 | CatBoost medium | 0.0–0.1 | 461 | 0.068553618 | 0.045553145 |
| 2026 | CatBoost medium | 0.1–0.2 | 689 | 0.144427889 | 0.155297533 |
| 2026 | CatBoost medium | 0.2–0.3 | 397 | 0.245542539 | 0.244332494 |
| 2026 | CatBoost medium | 0.3–0.4 | 183 | 0.346756489 | 0.344262295 |
| 2026 | CatBoost medium | 0.4–0.5 | 76 | 0.439546960 | 0.394736842 |
| 2026 | CatBoost medium | 0.5–0.6 | 37 | 0.542295517 | 0.594594595 |
| 2026 | CatBoost medium | 0.6–0.7 | 4 | 0.627611919 | 0.750000000 |
| 2026 | CatBoost medium | 0.7–0.8 | 2 | 0.742071090 | 1.000000000 |
| 2026 | CatBoost medium | 0.8–0.9 | 0 | N/A | N/A |
| 2026 | CatBoost medium | 0.9–1.0 | 0 | N/A | N/A |
| 2026 | Fixed equal blend | 0.0–0.1 | 417 | 0.068911039 | 0.047961631 |
| 2026 | Fixed equal blend | 0.1–0.2 | 715 | 0.143379865 | 0.139860140 |
| 2026 | Fixed equal blend | 0.2–0.3 | 416 | 0.245414124 | 0.259615385 |
| 2026 | Fixed equal blend | 0.3–0.4 | 185 | 0.344378643 | 0.329729730 |
| 2026 | Fixed equal blend | 0.4–0.5 | 78 | 0.435827023 | 0.397435897 |
| 2026 | Fixed equal blend | 0.5–0.6 | 34 | 0.539016888 | 0.647058824 |
| 2026 | Fixed equal blend | 0.6–0.7 | 4 | 0.642178400 | 0.750000000 |
| 2026 | Fixed equal blend | 0.7–0.8 | 0 | N/A | N/A |
| 2026 | Fixed equal blend | 0.8–0.9 | 0 | N/A | N/A |
| 2026 | Fixed equal blend | 0.9–1.0 | 0 | N/A | N/A |
