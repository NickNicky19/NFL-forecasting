# Original website CDF reconstruction

new reconstruction after exposed original2026Week6; candidate not original runner or prospective

All 12 categories, both fixed panels, and both method families are retained. Numeric primary error is MAE; anytime TD primary error is Brier. Each SITE/raw/simple comparison uses its own identical paired rows.

| Category | Panel | Family | State | SITE n / games / weeks | Candidate error | SITE error | Improvement % | Raw n / candidate / raw error | Simple n / candidate / simple error |
|---|---|---|---|---:|---:|---:|---:|---:|---:|
| pass_yd | base | pure_cdf | SCORED_DESCRIPTIVE | 27 / 13 / 1 | 51.7407 | 56.6230 | 8.6223 | 27 / 51.7407 / 51.4470 | 27 / 51.7407 / 55.2789 |
| pass_yd | base | website_equalweight | SCORED_DESCRIPTIVE | 27 / 13 / 1 | 51.9489 | 56.6230 | 8.2547 | 27 / 51.9489 / 51.4470 | 27 / 51.9489 / 55.2789 |
| pass_yd | context | pure_cdf | SCORED_DESCRIPTIVE | 27 / 13 / 1 | 48.7778 | 56.6230 | 13.8551 | 27 / 48.7778 / 51.4470 | 27 / 48.7778 / 55.2789 |
| pass_yd | context | website_equalweight | SCORED_DESCRIPTIVE | 27 / 13 / 1 | 50.7637 | 56.6230 | 10.3478 | 27 / 50.7637 / 51.4470 | 27 / 50.7637 / 55.2789 |
| pass_td | base | pure_cdf | SCORED_DESCRIPTIVE | 27 / 13 / 1 | 0.7037 | 0.8444 | 16.6667 | 27 / 0.7037 / 0.8141 | 27 / 0.7037 / 0.9427 |
| pass_td | base | website_equalweight | SCORED_DESCRIPTIVE | 27 / 13 / 1 | 0.7733 | 0.8444 | 8.4211 | 27 / 0.7733 / 0.8141 | 27 / 0.7733 / 0.9427 |
| pass_td | context | pure_cdf | SCORED_DESCRIPTIVE | 27 / 13 / 1 | 0.8519 | 0.8444 | -0.8772 | 27 / 0.8519 / 0.8141 | 27 / 0.8519 / 0.9427 |
| pass_td | context | website_equalweight | SCORED_DESCRIPTIVE | 27 / 13 / 1 | 0.8474 | 0.8444 | -0.3509 | 27 / 0.8474 / 0.8141 | 27 / 0.8474 / 0.9427 |
| pass_cmp | base | pure_cdf | SCORED_DESCRIPTIVE | 27 / 13 / 1 | 4.8148 | 4.5637 | -5.5024 | 27 / 4.8148 / 4.6030 | 27 / 4.8148 / 5.2049 |
| pass_cmp | base | website_equalweight | SCORED_DESCRIPTIVE | 27 / 13 / 1 | 4.5222 | 4.5637 | 0.9089 | 27 / 4.5222 / 4.6030 | 27 / 4.5222 / 5.2049 |
| pass_cmp | context | pure_cdf | SCORED_DESCRIPTIVE | 27 / 13 / 1 | 4.5556 | 4.5637 | 0.1785 | 27 / 4.5556 / 4.6030 | 27 / 4.5556 / 5.2049 |
| pass_cmp | context | website_equalweight | SCORED_DESCRIPTIVE | 27 / 13 / 1 | 4.3689 | 4.5637 | 4.2688 | 27 / 4.3689 / 4.6030 | 27 / 4.3689 / 5.2049 |
| pass_att | base | pure_cdf | SCORED_DESCRIPTIVE | 27 / 13 / 1 | 7.3704 | 7.1459 | -3.1409 | 27 / 7.3704 / 7.0941 | 27 / 7.3704 / 7.5026 |
| pass_att | base | website_equalweight | SCORED_DESCRIPTIVE | 27 / 13 / 1 | 7.1659 | 7.1459 | -0.2799 | 27 / 7.1659 / 7.0941 | 27 / 7.1659 / 7.5026 |
| pass_att | context | pure_cdf | SCORED_DESCRIPTIVE | 27 / 13 / 1 | 7.2222 | 7.1459 | -1.0677 | 27 / 7.2222 / 7.0941 | 27 / 7.2222 / 7.5026 |
| pass_att | context | website_equalweight | SCORED_DESCRIPTIVE | 27 / 13 / 1 | 7.0548 | 7.1459 | 1.2750 | 27 / 7.0548 / 7.0941 | 27 / 7.0548 / 7.5026 |
| pass_int | base | pure_cdf | SCORED_DESCRIPTIVE | 27 / 13 / 1 | 0.7037 | 0.6637 | -6.0268 | 27 / 0.7037 / 0.6404 | 27 / 0.7037 / 0.6582 |
| pass_int | base | website_equalweight | SCORED_DESCRIPTIVE | 27 / 13 / 1 | 0.6833 | 0.6637 | -2.9576 | 27 / 0.6833 / 0.6404 | 27 / 0.6833 / 0.6582 |
| pass_int | context | pure_cdf | SCORED_DESCRIPTIVE | 27 / 13 / 1 | 0.5556 | 0.6637 | 16.2946 | 27 / 0.5556 / 0.6404 | 27 / 0.5556 / 0.6582 |
| pass_int | context | website_equalweight | SCORED_DESCRIPTIVE | 27 / 13 / 1 | 0.6093 | 0.6637 | 8.2031 | 27 / 0.6093 / 0.6404 | 27 / 0.6093 / 0.6582 |
| rush_yd | base | pure_cdf | SCORED_DESCRIPTIVE | 97 / 13 / 1 | 14.6907 | 16.3908 | 10.3723 | 95 / 14.9789 / 16.4528 | 97 / 14.6907 / 17.0737 |
| rush_yd | base | website_equalweight | SCORED_DESCRIPTIVE | 97 / 13 / 1 | 14.5455 | 16.3908 | 11.2582 | 95 / 14.8249 / 16.4528 | 97 / 14.5455 / 17.0737 |
| rush_yd | context | pure_cdf | SCORED_DESCRIPTIVE | 97 / 13 / 1 | 14.6804 | 16.3908 | 10.4352 | 95 / 14.9474 / 16.4528 | 97 / 14.6804 / 17.0737 |
| rush_yd | context | website_equalweight | SCORED_DESCRIPTIVE | 97 / 13 / 1 | 14.4874 | 16.3908 | 11.6129 | 95 / 14.7550 / 16.4528 | 97 / 14.4874 / 17.0737 |
| rush_att | base | pure_cdf | SCORED_DESCRIPTIVE | 70 / 13 / 1 | 3.6857 | 3.3830 | -8.9481 | 68 / 3.7941 / 3.3121 | 70 / 3.6857 / 4.4446 |
| rush_att | base | website_equalweight | SCORED_DESCRIPTIVE | 70 / 13 / 1 | 3.3279 | 3.3830 | 1.6279 | 68 / 3.4184 / 3.3121 | 70 / 3.3279 / 4.4446 |
| rush_att | context | pure_cdf | SCORED_DESCRIPTIVE | 70 / 13 / 1 | 3.7714 | 3.3830 | -11.4818 | 68 / 3.8676 / 3.3121 | 70 / 3.7714 / 4.4446 |
| rush_att | context | website_equalweight | SCORED_DESCRIPTIVE | 70 / 13 / 1 | 3.3565 | 3.3830 | 0.7833 | 68 / 3.4404 / 3.3121 | 70 / 3.3565 / 4.4446 |
| rec | base | pure_cdf | SCORED_DESCRIPTIVE | 258 / 13 / 1 | 1.2597 | 1.2629 | 0.2517 | 249 / 1.3052 / 1.2969 | 258 / 1.2597 / 1.4739 |
| rec | base | website_equalweight | SCORED_DESCRIPTIVE | 258 / 13 / 1 | 1.2514 | 1.2629 | 0.9085 | 249 / 1.2925 / 1.2969 | 258 / 1.2514 / 1.4739 |
| rec | context | pure_cdf | SCORED_DESCRIPTIVE | 258 / 13 / 1 | 1.2519 | 1.2629 | 0.8655 | 249 / 1.2972 / 1.2969 | 258 / 1.2519 / 1.4739 |
| rec | context | website_equalweight | SCORED_DESCRIPTIVE | 258 / 13 / 1 | 1.2475 | 1.2629 | 1.2154 | 249 / 1.2885 / 1.2969 | 258 / 1.2475 / 1.4739 |
| rec_yd | base | pure_cdf | SCORED_DESCRIPTIVE | 258 / 13 / 1 | 15.2752 | 15.1133 | -1.0712 | 249 / 15.7711 / 15.4837 | 258 / 15.2752 / 16.1440 |
| rec_yd | base | website_equalweight | SCORED_DESCRIPTIVE | 258 / 13 / 1 | 14.6758 | 15.1133 | 2.8948 | 249 / 15.1556 / 15.4837 | 258 / 14.6758 / 16.1440 |
| rec_yd | context | pure_cdf | SCORED_DESCRIPTIVE | 258 / 13 / 1 | 15.2829 | 15.1133 | -1.1225 | 249 / 15.7791 / 15.4837 | 258 / 15.2829 / 16.1440 |
| rec_yd | context | website_equalweight | SCORED_DESCRIPTIVE | 258 / 13 / 1 | 14.6409 | 15.1133 | 3.1256 | 249 / 15.1195 / 15.4837 | 258 / 14.6409 / 16.1440 |
| rush_rec_yd | base | pure_cdf | SCORED_DESCRIPTIVE | 192 / 13 / 1 | 20.3906 | 19.6018 | -4.0241 | 187 / 20.8610 / 19.8159 | 192 / 20.3906 / 19.7294 |
| rush_rec_yd | base | website_equalweight | SCORED_DESCRIPTIVE | 192 / 13 / 1 | 19.2839 | 19.6018 | 1.6220 | 187 / 19.7341 / 19.8159 | 192 / 19.2839 / 19.7294 |
| rush_rec_yd | context | pure_cdf | SCORED_DESCRIPTIVE | 192 / 13 / 1 | 20.2969 | 19.6018 | -3.5459 | 187 / 20.7754 / 19.8159 | 192 / 20.2969 / 19.7294 |
| rush_rec_yd | context | website_equalweight | SCORED_DESCRIPTIVE | 192 / 13 / 1 | 19.1953 | 19.6018 | 2.0737 | 187 / 19.6486 / 19.8159 | 192 / 19.1953 / 19.7294 |
| fantasy_ppr | base | pure_cdf | BLOCKED_CATEGORY_CONTRACT | — | — | — | — | — | — |
| fantasy_ppr | base | website_equalweight | BLOCKED_CATEGORY_CONTRACT | — | — | — | — | — | — |
| fantasy_ppr | context | pure_cdf | BLOCKED_CATEGORY_CONTRACT | — | — | — | — | — | — |
| fantasy_ppr | context | website_equalweight | BLOCKED_CATEGORY_CONTRACT | — | — | — | — | — | — |
| anytime_td | base | pure_cdf | SCORED_DESCRIPTIVE | 249 / 13 / 1 | 0.1368 | 0.1424 | 3.9685 | 0 / — / — | 249 / 0.1368 / 0.1492 |
| anytime_td | base | website_equalweight | SCORED_DESCRIPTIVE | 249 / 13 / 1 | 0.1378 | 0.1424 | 3.2483 | 0 / — / — | 249 / 0.1378 / 0.1492 |
| anytime_td | context | pure_cdf | SCORED_DESCRIPTIVE | 249 / 13 / 1 | 0.1378 | 0.1424 | 3.2417 | 0 / — / — | 249 / 0.1378 / 0.1492 |
| anytime_td | context | website_equalweight | SCORED_DESCRIPTIVE | 249 / 13 / 1 | 0.1383 | 0.1424 | 2.9051 | 0 / — / — | 249 / 0.1383 / 0.1492 |

## Point diagnostics on the SITE paired cohort

| Category | Panel | Family | Candidate RMSE / bias / p90 AE | SITE RMSE / bias / p90 AE | Offered / supported played / CDF fallback |
|---|---|---|---:|---:|---:|
| pass_yd | base | pure_cdf | 63.7074 / -19.7407 / 117.8000 | 73.7983 / -19.0815 / 99.9200 | 37 / 27 / 0 |
| pass_yd | base | website_equalweight | 65.2023 / -19.4111 / 105.2960 | 73.7983 / -19.0815 / 99.9200 | 37 / 27 / 0 |
| pass_yd | context | pure_cdf | 60.0472 / -22.1111 / 100.2000 | 73.7983 / -19.0815 / 99.9200 | 37 / 27 / 0 |
| pass_yd | context | website_equalweight | 63.9771 / -20.5963 / 104.9600 | 73.7983 / -19.0815 / 99.9200 | 37 / 27 / 0 |
| pass_td | base | pure_cdf | 1.0000 / -0.3333 / 2.0000 | 1.1112 / -0.1570 / 1.7500 | 37 / 27 / 0 |
| pass_td | base | website_equalweight | 1.0202 / -0.2452 / 1.8750 | 1.1112 / -0.1570 / 1.7500 | 37 / 27 / 0 |
| pass_td | context | pure_cdf | 1.1386 / -0.3333 / 2.0000 | 1.1112 / -0.1570 / 1.7500 | 37 / 27 / 0 |
| pass_td | context | website_equalweight | 1.0852 / -0.2452 / 1.8750 | 1.1112 / -0.1570 / 1.7500 | 37 / 27 / 0 |
| pass_cmp | base | pure_cdf | 6.4521 / -2.3704 / 11.0000 | 5.7934 / -2.6837 / 10.1180 | 37 / 27 / 0 |
| pass_cmp | base | website_equalweight | 5.8988 / -2.5270 / 10.8750 | 5.7934 / -2.6837 / 10.1180 | 37 / 27 / 0 |
| pass_cmp | context | pure_cdf | 6.0888 / -2.4074 / 12.0000 | 5.7934 / -2.6837 / 10.1180 | 37 / 27 / 0 |
| pass_cmp | context | website_equalweight | 5.7152 / -2.5456 / 10.6360 | 5.7934 / -2.6837 / 10.1180 | 37 / 27 / 0 |
| pass_att | base | pure_cdf | 10.4297 / -5.1481 / 15.2000 | 9.3864 / -5.3919 / 17.0920 | 37 / 27 / 0 |
| pass_att | base | website_equalweight | 9.4825 / -5.2700 / 15.4020 | 9.3864 / -5.3919 / 17.0920 | 37 / 27 / 0 |
| pass_att | context | pure_cdf | 9.3472 / -4.8519 / 15.2000 | 9.3864 / -5.3919 / 17.0920 | 37 / 27 / 0 |
| pass_att | context | website_equalweight | 8.9855 / -5.1219 / 15.4020 | 9.3864 / -5.3919 / 17.0920 | 37 / 27 / 0 |
| pass_int | base | pure_cdf | 0.9230 / -0.5556 / 1.0000 | 0.7693 / -0.1096 / 1.3060 | 37 / 27 / 0 |
| pass_int | base | website_equalweight | 0.7916 / -0.3326 / 1.0750 | 0.7693 / -0.1096 / 1.3060 | 37 / 27 / 0 |
| pass_int | context | pure_cdf | 0.8819 / -0.4815 / 1.4000 | 0.7693 / -0.1096 / 1.3060 | 37 / 27 / 0 |
| pass_int | context | website_equalweight | 0.7704 / -0.2956 / 1.2830 | 0.7693 / -0.1096 / 1.3060 | 37 / 27 / 0 |
| rush_yd | base | pure_cdf | 21.0236 / -5.1237 / 32.4000 | 21.2073 / 4.4073 / 33.6500 | 137 / 97 / 1 |
| rush_yd | base | website_equalweight | 19.4981 / -0.3582 / 31.8660 | 21.2073 / 4.4073 / 33.6500 | 137 / 97 / 1 |
| rush_yd | context | pure_cdf | 20.6827 / -5.1134 / 31.4000 | 21.2073 / 4.4073 / 33.6500 | 137 / 97 / 1 |
| rush_yd | context | website_equalweight | 19.3067 / -0.3530 / 32.2760 | 21.2073 / 4.4073 / 33.6500 | 137 / 97 / 1 |
| rush_att | base | pure_cdf | 5.2290 / -1.6571 / 10.0000 | 4.3587 / -0.0039 / 7.2340 | 100 / 70 / 1 |
| rush_att | base | website_equalweight | 4.4627 / -0.8305 / 7.8390 | 4.3587 / -0.0039 / 7.2340 | 100 / 70 / 1 |
| rush_att | context | pure_cdf | 5.2996 / -1.6571 / 10.0000 | 4.3587 / -0.0039 / 7.2340 | 100 / 70 / 1 |
| rush_att | context | website_equalweight | 4.4826 / -0.8305 / 8.3300 | 4.3587 / -0.0039 / 7.2340 | 100 / 70 / 1 |
| rec | base | pure_cdf | 1.8853 / -0.5000 / 3.0000 | 1.7492 / -0.3029 / 2.8980 | 359 / 258 / 3 |
| rec | base | website_equalweight | 1.7734 / -0.4015 / 2.8875 | 1.7492 / -0.3029 / 2.8980 | 359 / 258 / 3 |
| rec | context | pure_cdf | 1.8750 / -0.5233 / 3.0000 | 1.7492 / -0.3029 / 2.8980 | 359 / 258 / 3 |
| rec | context | website_equalweight | 1.7681 / -0.4131 / 2.8875 | 1.7492 / -0.3029 / 2.8980 | 359 / 258 / 3 |
| rec_yd | base | pure_cdf | 23.7319 / -7.1047 / 42.0000 | 22.2066 / -2.1024 / 35.2840 | 359 / 258 / 3 |
| rec_yd | base | website_equalweight | 22.3249 / -4.6035 / 37.5900 | 22.2066 / -2.1024 / 35.2840 | 359 / 258 / 3 |
| rec_yd | context | pure_cdf | 23.7038 / -7.1589 / 42.3000 | 22.2066 / -2.1024 / 35.2840 | 359 / 258 / 3 |
| rec_yd | context | website_equalweight | 22.3106 / -4.6306 / 36.7670 | 22.2066 / -2.1024 / 35.2840 | 359 / 258 / 3 |
| rush_rec_yd | base | pure_cdf | 29.2674 / -8.6719 / 49.7000 | 27.5085 / -0.8730 / 43.9180 | 259 / 192 / 1 |
| rush_rec_yd | base | website_equalweight | 27.2301 / -4.7724 / 43.3950 | 27.5085 / -0.8730 / 43.9180 | 259 / 192 / 1 |
| rush_rec_yd | context | pure_cdf | 29.2631 / -8.8698 / 48.9000 | 27.5085 / -0.8730 / 43.9180 | 259 / 192 / 1 |
| rush_rec_yd | context | website_equalweight | 27.2002 / -4.8714 / 43.6490 | 27.5085 / -0.8730 / 43.9180 | 259 / 192 / 1 |
| anytime_td | base | pure_cdf | 0.3698 / 0.0023 / 0.7394 | 0.3774 / 0.0020 / 0.7330 | 288 / 249 / 1 |
| anytime_td | base | website_equalweight | 0.3712 / 0.0022 / 0.7517 | 0.3774 / 0.0020 / 0.7330 | 288 / 249 / 1 |
| anytime_td | context | pure_cdf | 0.3712 / 0.0010 / 0.7446 | 0.3774 / 0.0020 / 0.7330 | 288 / 249 / 1 |
| anytime_td | context | website_equalweight | 0.3718 / 0.0015 / 0.7548 | 0.3774 / 0.0020 / 0.7330 | 288 / 249 / 1 |

## Source and evidence limits

- New reconstruction calculated after exposed 2026 Week 6 games; candidate forecasts are neither the original runner nor prospective evidence.
- One exposed week and 13 original games. All fixed panels and both families are shown; no interval, significance, selected winner, qualification, or promotion follows.
- Training uses eligible retained 2019–2025 labels. Historical publication/correction clocks are unauthenticated; the declared seven-day label availability assumption is retained.
- All retained training years and Week 6 outcomes are exposed. V2 uses current revisions and postgame roster evidence; reconstruction does not authenticate the original pregame roster or publication vintage.
- Current-vintage prior-week inputs, identity coverage, missing histories, and trained-prior fallbacks do not establish fully authenticated historical as-of inputs.
- Each comparison uses its own identical supported-played, finite-candidate, finite-control paired rows. Raw/simple matched cohorts can differ from the primary website cohort; losses must not be compared across different denominators.
- Pure numeric primary points are same-law medians. Equalweight numeric blends are point heuristics, with no law-mean, law-median, distribution, or CRPS claim. TD uses genuine Bernoulli probabilities.
- DNP, unknown participation, played missing, quarantines, blocked PPR, failed attempts, and unavailable controls remain explicit. Missing values are not zero.

## Technical coherence audit

Compatible conditional means should add; independently fitted marginal laws are not a joint law. Medians/quantiles need not add. Missing component offers remain unavailable; no invented zero components.

| Panel | Audit | Common finite rows | Violations | Mean absolute gap | Maximum absolute gap | Combined offers without both components |
|---|---|---:|---:|---:|---:|---:|
| base | expected_completions_le_expected_attempts | 37 | 0 | — | — | — |
| base | separately_fitted_expected_combined_vs_sum_expected_components | 100 | 99 | 1.8812 | 15.6795 | 159 |
| context | expected_completions_le_expected_attempts | 37 | 0 | — | — | — |
| context | separately_fitted_expected_combined_vs_sum_expected_components | 100 | 99 | 2.0259 | 7.9949 | 159 |

This saved technical audit makes no new error-score or joint-law claim and applies no point repair.

Exact aggregate inputs, source/code/model hashes, feature panels, proper-law diagnostics, outcome states, and fallback reasons are retained in aggregate-report.json and hash-manifest.json. No raw/player/model-label rows are included.
