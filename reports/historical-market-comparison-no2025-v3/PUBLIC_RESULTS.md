# No-2025 market comparison — reviewed aggregate checkpoint

H lowers the registered primary point loss against the football-only F control in **9 of 10 numeric categories in both 2024 and 2026**. The 2026 control is an older frozen model; the 2024 control uses its corresponding annual model. Independent market and offering-book line heuristics often have lower loss than H. Probability comparisons are mixed; the 2026 passing-yards probability common pool has only 12 player-games. These are timing-unverified research results, with no current-website, best-forever, live-readiness or qualification claim.

F is the authenticated CDF mean for counts and lower median for yards. In 2026 it is the frozen 2024 model trained 2019–2023, with 2025 excluded before lag construction. FC and H are nonnegative-slope L2 empirical point corrections, not stored CDF means/medians; count outputs are clamped at zero while signed-yard intercepts are unbounded. H adds an offering-book-excluded market input to the same learner. FS separately shrinks probability confidence toward 0.5. M and L(B) are independent-book and actual offering-book line-as-point heuristics. No numeric point gap creates a probability.

Calibration used available 2022/2023 development offers; 2022 has no qualifying named-book pairs, so learned market calibration effectively uses 2023. Neither 2024 nor 2026 was used for calibration/tuning. All quotes remain unqualified for historical timing; football availability uses the explicit original seven-day reconstruction assumption. No authenticated historical SITE/R0 comparator is available.

## 2026 — Weeks 1–5

### Primary point comparison

Lower is better. **n/g/w** means player-game-category observations / distinct games / weeks on the same primary-role common cohort. Count primary loss is MSE in counts²; it is not a hit percentage. Yard primary loss is MAE in yards.

| Category | Primary loss | n/g/w | F | FC | M | H | L(B) |
|---|---|---:|---:|---:|---:|---:|---:|
| Passing yards | MAE (yd) | 81/46/5 | 56.0370 | 55.0363 | 53.9136 | 53.4182 | 54.2160 |
| Passing TD | MSE (count²) | 76/44/5 | 1.3846 | 1.3504 | 1.3586 | 1.3225 | 1.3553 |
| Completions | MSE (count²) | 79/46/5 | 30.3694 | 29.3374 | 27.8006 | 28.4229 | 28.5791 |
| Passing attempts | MSE (count²) | 79/46/5 | 68.5083 | 65.4204 | 65.0728 | 64.1352 | 62.9842 |
| Interceptions | MSE (count²) | 77/44/5 | 0.4689 | 0.4707 | 0.4838 | 0.4707 | 0.4838 |
| Rushing yards | MAE (yd) | 153/48/5 | 23.1373 | 24.1762 | 21.7778 | 22.3275 | 21.9641 |
| Carries | MSE (count²) | 101/45/5 | 37.1789 | 31.3017 | 27.7129 | 27.4950 | 27.0421 |
| Receptions | MSE (count²) | 461/48/5 | 5.5223 | 5.4786 | 4.3585 | 4.3962 | 4.3541 |
| Receiving yards | MAE (yd) | 482/48/5 | 23.2220 | 24.1010 | 21.2505 | 21.7345 | 21.2593 |
| Combined yards | MAE (yd) | 119/47/5 | 30.1681 | 29.9995 | 28.1933 | 28.7014 | 28.6597 |
| Anytime rush/receive TD | See event probability | — | — | — | — | — | — |
| Exact PPR | Unsupported exact PPR | — | — | — | — | — | — |

### Signed H contrasts and available uncertainty

Δ=H−baseline in the primary-loss units above; negative favors H. The interval is the stored nominal paired **H−F game** 95% interval. Saved H−FC/M intervals are unavailable.

| Category | ΔH−F | ΔH−FC | ΔH−M | H−F game 95% interval |
|---|---:|---:|---:|---|
| Passing yards | -2.6188 | -1.6181 | -0.4953 | [-6.8045, 2.4209] |
| Passing TD | -0.0621 | -0.0279 | -0.0360 | [-0.1643, 0.0350] |
| Completions | -1.9465 | -0.9146 | +0.6222 | [-5.9403, 2.0984] |
| Passing attempts | -4.3731 | -1.2852 | -0.9376 | [-11.8495, 2.7748] |
| Interceptions | +0.0017 | +0.0000 | -0.0131 | [-0.0103, 0.0140] |
| Rushing yards | -0.8098 | -1.8488 | +0.5497 | [-3.3903, 1.7307] |
| Carries | -9.6839 | -3.8067 | -0.2178 | [-19.3243, 0.1385] |
| Receptions | -1.1261 | -1.0824 | +0.0378 | [-1.4087, -0.8677] |
| Receiving yards | -1.4875 | -2.3665 | +0.4839 | [-2.3597, -0.6137] |
| Combined yards | -1.4666 | -1.2981 | +0.5082 | [-4.2892, 1.2950] |

### Count MAE — secondary, in counts

Same n/g/w as the point table; these are absolute errors, not exact-hit rates.

| Category | F | FC | M | H |
|---|---:|---:|---:|---:|
| Passing TD | 0.9621 | 0.9754 | 0.9671 | 0.9605 |
| Completions | 4.5937 | 4.4880 | 4.1962 | 4.2685 |
| Passing attempts | 6.2388 | 6.0375 | 5.9051 | 5.8848 |
| Interceptions | 0.6036 | 0.6003 | 0.6169 | 0.6003 |
| Carries | 4.5426 | 4.2241 | 3.9307 | 3.9454 |
| Receptions | 1.7883 | 1.8083 | 1.5911 | 1.6087 |

### Probability — Brier loss

Lower is better; ordinary O/U uses the same decisive common cohort for all five arms. ATD uses its separate football-only event cohort because no genuine No quote is available. Log losses and available intervals are retained in PUBLIC_METRICS.json.

| Category | n/g/w | F | FC | FS | M | H |
|---|---:|---:|---:|---:|---:|---:|
| Passing yards | 12/11/4 | 0.258925 | 0.245708 | 0.250000 | 0.250000 | 0.245710 |
| Passing TD | 74/43/5 | 0.255573 | 0.248767 | 0.248887 | 0.243752 | 0.244417 |
| Completions | 58/39/5 | 0.255434 | 0.250633 | 0.250001 | 0.247206 | 0.250552 |
| Passing attempts | 46/31/4 | 0.243263 | 0.249475 | 0.250000 | 0.248612 | 0.249421 |
| Interceptions | 76/44/5 | 0.255164 | 0.249719 | 0.250108 | 0.256215 | 0.249932 |
| Rushing yards | 51/34/5 | 0.258234 | 0.253883 | 0.250000 | 0.251286 | 0.253899 |
| Carries | 67/36/5 | 0.286105 | 0.253711 | 0.250966 | 0.254675 | 0.253808 |
| Receptions | 419/48/5 | 0.281989 | 0.253618 | 0.251094 | 0.249694 | 0.250651 |
| Receiving yards | 179/43/5 | 0.262765 | 0.247191 | 0.249277 | 0.250090 | 0.247211 |
| Combined yards | 21/19/4 | 0.335128 | 0.252422 | 0.250113 | 0.249556 | 0.252258 |
| Anytime rush/receive TD | 829/62/5 | 0.155491 | 0.155491 | 0.155494 | — | — |
| Exact PPR | Unsupported | — | — | — | — | — |

### Bias and error-threshold diagnostics

Bias is prediction−actual in yards or counts. Close columns show strict/inclusive rates: |error|<10 /≤10 yards, or <1/≤1 count. These are threshold diagnostics; p90/p95/max-error percentiles were not computed in this first wave. Full F/FC/M/H diagnostics and simultaneous side-correct-and-close rates are in the JSON.

| Category | F bias | H bias | F close strict/inclusive | H close strict/inclusive |
|---|---:|---:|---:|---:|
| Passing yards | -12.2840 | -10.3485 | 7.4% / 11.1% | 14.8% / 14.8% |
| Passing TD | -0.1623 | -0.1219 | 57.9% / 57.9% | 59.2% / 59.2% |
| Completions | -0.9563 | -0.9411 | 11.4% / 11.4% | 16.5% / 16.5% |
| Passing attempts | -1.8372 | -1.5481 | 16.5% / 16.5% | 10.1% / 10.1% |
| Interceptions | +0.0084 | +0.0444 | 88.3% / 88.3% | 88.3% / 88.3% |
| Rushing yards | -10.6667 | +0.7427 | 34.0% / 35.3% | 26.1% / 26.1% |
| Carries | -2.4257 | -0.2697 | 14.9% / 14.9% | 15.8% / 15.8% |
| Receptions | -0.1650 | -0.0492 | 39.7% / 39.7% | 41.0% / 41.0% |
| Receiving yards | -7.8817 | -0.2165 | 31.7% / 36.1% | 28.4% / 28.4% |
| Combined yards | -15.7311 | -0.0779 | 26.1% / 27.7% | 20.2% / 20.2% |

Whole-week intervals are **N/A for 2026**: the point cohorts cover five weeks and some probability cohorts cover only four. The unchanged minimum-eight-cluster routine is an uncertainty rule, not a new release prerequisite. Results remain exposed-sample research, with no multiplicity-adjusted qualification.

## 2024 — REG historical outer comparison

### Primary point comparison

Lower is better. **n/g/w** means player-game-category observations / distinct games / weeks on the same primary-role common cohort. Count primary loss is MSE in counts²; it is not a hit percentage. Yard primary loss is MAE in yards.

| Category | Primary loss | n/g/w | F | FC | M | H | L(B) |
|---|---|---:|---:|---:|---:|---:|---:|
| Passing yards | MAE (yd) | 465/261/18 | 62.0129 | 59.6682 | 58.1882 | 58.3463 | 58.1000 |
| Passing TD | MSE (count²) | 465/261/18 | 1.3764 | 1.3767 | 1.4263 | 1.3699 | 1.4371 |
| Completions | MSE (count²) | 458/258/18 | 39.0018 | 35.2869 | 32.0770 | 32.3605 | 32.3592 |
| Passing attempts | MSE (count²) | 457/258/18 | 80.7952 | 70.9119 | 65.0635 | 65.6787 | 65.1034 |
| Interceptions | MSE (count²) | 440/247/18 | 0.7074 | 0.7100 | 0.7364 | 0.7100 | 0.7364 |
| Rushing yards | MAE (yd) | 848/265/18 | 26.0920 | 26.5723 | 23.6486 | 24.0197 | 23.6368 |
| Carries | MSE (count²) | 677/261/18 | 33.5961 | 32.4512 | 25.2984 | 25.4616 | 25.4878 |
| Receptions | MSE (count²) | 2759/266/18 | 4.5361 | 4.4477 | 4.1327 | 4.0973 | 4.1717 |
| Receiving yards | MAE (yd) | 2950/266/18 | 21.4139 | 21.6514 | 20.0226 | 20.5132 | 20.0237 |
| Combined yards | MAE (yd) | 1773/263/18 | 29.1957 | 28.5452 | 26.6232 | 26.9122 | 26.6111 |
| Anytime rush/receive TD | See event probability | — | — | — | — | — | — |
| Exact PPR | Unsupported exact PPR | — | — | — | — | — | — |

### Signed H contrasts and available uncertainty

Δ=H−baseline in the primary-loss units above; negative favors H. The interval is the stored nominal paired **H−F game** 95% interval. Saved H−FC/M intervals are unavailable.

| Category | ΔH−F | ΔH−FC | ΔH−M | H−F game 95% interval |
|---|---:|---:|---:|---|
| Passing yards | -3.6666 | -1.3220 | +0.1581 | [-6.0228, -1.4263] |
| Passing TD | -0.0065 | -0.0067 | -0.0564 | [-0.0582, 0.0366] |
| Completions | -6.6413 | -2.9264 | +0.2835 | [-10.1251, -3.5006] |
| Passing attempts | -15.1166 | -5.2332 | +0.6152 | [-23.0090, -8.5864] |
| Interceptions | +0.0026 | +0.0000 | -0.0264 | [-0.0034, 0.0082] |
| Rushing yards | -2.0723 | -2.5526 | +0.3711 | [-2.9305, -1.1034] |
| Carries | -8.1344 | -6.9895 | +0.1633 | [-11.0973, -5.8777] |
| Receptions | -0.4389 | -0.3504 | -0.0355 | [-0.5343, -0.3339] |
| Receiving yards | -0.9007 | -1.1382 | +0.4906 | [-1.3286, -0.4436] |
| Combined yards | -2.2835 | -1.6330 | +0.2890 | [-2.9729, -1.6393] |

### Count MAE — secondary, in counts

Same n/g/w as the point table; these are absolute errors, not exact-hit rates.

| Category | F | FC | M | H |
|---|---:|---:|---:|---:|
| Passing TD | 0.9489 | 0.9659 | 0.9774 | 0.9559 |
| Completions | 4.8990 | 4.6353 | 4.4836 | 4.4979 |
| Passing attempts | 6.9112 | 6.4897 | 6.2976 | 6.3012 |
| Interceptions | 0.7033 | 0.7063 | 0.6955 | 0.7063 |
| Carries | 4.4798 | 4.5578 | 4.0044 | 4.0368 |
| Receptions | 1.6260 | 1.6353 | 1.5638 | 1.5652 |

### Probability — Brier loss

Lower is better; ordinary O/U uses the same decisive common cohort for all five arms. ATD uses its separate football-only event cohort because no genuine No quote is available. Log losses and available intervals are retained in PUBLIC_METRICS.json.

| Category | n/g/w | F | FC | FS | M | H |
|---|---:|---:|---:|---:|---:|---:|
| Passing yards | 226/177/18 | 0.260225 | 0.250565 | 0.250000 | 0.250074 | 0.250565 |
| Passing TD | 464/261/18 | 0.252310 | 0.248759 | 0.248547 | 0.244146 | 0.244609 |
| Completions | 443/256/18 | 0.258133 | 0.250354 | 0.250001 | 0.248183 | 0.250307 |
| Passing attempts | 424/248/18 | 0.259782 | 0.249582 | 0.250000 | 0.249540 | 0.249548 |
| Interceptions | 440/247/18 | 0.247738 | 0.250155 | 0.249839 | 0.245641 | 0.249658 |
| Rushing yards | 571/251/18 | 0.273408 | 0.249923 | 0.250000 | 0.249771 | 0.249920 |
| Carries | 640/259/18 | 0.268284 | 0.249699 | 0.250008 | 0.249941 | 0.249639 |
| Receptions | 2732/266/18 | 0.260275 | 0.248358 | 0.248199 | 0.244248 | 0.245099 |
| Receiving yards | 2133/266/18 | 0.269295 | 0.250553 | 0.250278 | 0.250076 | 0.250554 |
| Combined yards | 1204/246/18 | 0.267439 | 0.250048 | 0.250004 | 0.249952 | 0.250041 |
| Anytime rush/receive TD | 4532/266/18 | 0.150075 | 0.150075 | 0.150076 | — | — |
| Exact PPR | Unsupported | — | — | — | — | — |

### Bias and error-threshold diagnostics

Bias is prediction−actual in yards or counts. Close columns show strict/inclusive rates: |error|<10 /≤10 yards, or <1/≤1 count. These are threshold diagnostics; p90/p95/max-error percentiles were not computed in this first wave. Full F/FC/M/H diagnostics and simultaneous side-correct-and-close rates are in the JSON.

| Category | F bias | H bias | F close strict/inclusive | H close strict/inclusive |
|---|---:|---:|---:|---:|
| Passing yards | -5.5742 | +3.6211 | 9.9% / 11.4% | 10.8% / 10.8% |
| Passing TD | -0.1061 | -0.0264 | 59.1% / 59.1% | 59.1% / 59.1% |
| Completions | -0.7883 | -0.1352 | 13.3% / 13.3% | 14.2% / 14.2% |
| Passing attempts | -0.7965 | +0.2568 | 8.5% / 8.5% | 10.3% / 10.3% |
| Interceptions | +0.0188 | +0.0547 | 84.3% / 84.3% | 84.3% / 84.3% |
| Rushing yards | -10.8538 | +0.3238 | 25.2% / 28.1% | 24.2% / 24.2% |
| Carries | -1.2544 | +0.1314 | 15.4% / 15.4% | 15.7% / 15.7% |
| Receptions | -0.2998 | -0.0121 | 39.4% / 39.4% | 41.2% / 41.2% |
| Receiving yards | -9.1990 | +0.4746 | 34.2% / 37.3% | 30.8% / 30.8% |
| Combined yards | -13.1122 | -0.4246 | 22.3% / 24.6% | 23.1% / 23.1% |

The 2024 cohorts cover 18 weeks; saved nominal whole-week intervals are available in the JSON. The unchanged minimum-eight-cluster routine is an uncertainty rule, not a new release prerequisite. Results remain exposed-sample research, with no multiplicity-adjusted qualification.

## Coverage, verification and retained failures

The whole canonical pool contains 99,388 book-offer incidences. Strict source/original-query context checks retain 6,943 row abstentions with both roles and field reasons. Genuine forecasts cover 34,759 unique player-game-target queries and 92,445 book-threshold incidences. Those counts are not independent NFL games. The public JSON separates primary-role offer counts from ALL-role outcome-state book incidences; those denominators must not be mixed. All-role secondary coverage and fallback counts are distinct from primary-role gains.

The main run used 144 small earlier calibration estimates, **zero base CDF fits**, 33 model loads and no HTTP. Full wrapper time was 73.93 s real / 68.35 s user / 6.88 s system; measured worker peak RSS was 646,021,120 bytes. Forecasts and choices were durably frozen before outer loss computation. Independent read-only QA passed 11,159 checks, 100 point and 100 common-probability metric records, 400 paired intervals, 53,091 original 2024 frozen-point incidences and 312,880 calibrator application values, with no new fits, models, predictions or selections.

V1 remains FAILED at strict role-context agreement; its 30.973 CPU / 30.279 wall / 420,950,016 RSS figures are pre-preservation checkpoints, not full final resource totals. V2 remains FAILED at duplicated football-query identities; its full wrapper was 26.40 s real / 23.03 s user / 3.71 s system, with final RSS unrecorded. V3 used unique original model queries and unchanged-law fanout to all book thresholds. The original four-write cap was preserved; one separately authorized retention slot made five cumulative writes. All failed evidence remains retained. Cumulative named data plus ownership metadata is 17,024,733 bytes, below the 32 MiB/48 MiB retained/peak envelope.

## Limits and follow-up paper accounting

The aged F control can be weaker than a contemporary football model. Independent M or the actual offering-book line often beats H; the numeric gains do not establish the best current forecaster, a website win, or a forever champion. Passing-yards probability coverage in 2026 is only 12 observations. All quote clocks and exact book settlement rules remain unqualified. ATD is only the rushing/receiving event and has no fair market comparison; exact PPR remains unsupported.

The frozen GAP_SCREENED policy is a laboratory F point-gap proxy, not historical website Top Over/Under. At the original main-run checkpoint, paper accounting was pending. It has since completed in a separately versioned zero-fit postprocess: [completed paper accounting, private scorecard and live-status checkpoint](../historical-market-no2025-v1/README.md). No new NFL observations or forecasts were added by that postprocess. The reported hypothetical ROI does not establish authenticated profitability, live readiness, promotion or scientific qualification. No new website feed or scheduler was installed.

[Machine-readable permitted aggregates](PUBLIC_METRICS.json) · [Verification references](VERIFICATION_REFS.json)
