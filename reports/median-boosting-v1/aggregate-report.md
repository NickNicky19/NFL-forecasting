# Fixed absolute-error boosting reconstruction

Exposed joint learner/source historical and original-website reconstruction; saved aggregates only

Numeric error is MAE; anytime TD error is Brier. Historical primary rows are pooled before calculation. Every fixed panel and category remains visible.

| Category | Panel | Period | State | Comparator | n / games / weeks | Candidate error | Control error | Improvement % |
|---|---|---|---|---|---:|---:|---:|---:|
| pass_yd | base | pooled2022-2024 | SCORED_DESCRIPTIVE | old_cdf | 18303 / 854 / 66 | 7.5054 | 7.6042 | 1.2982 |
| pass_yd | base | website_week6 | SCORED_DESCRIPTIVE | website | 27 / 13 / 1 | 52.0177 | 56.6230 | 8.1331 |
| pass_yd | context | pooled2022-2024 | SCORED_DESCRIPTIVE | old_cdf | 18303 / 854 / 66 | 7.4653 | 7.4975 | 0.4296 |
| pass_yd | context | website_week6 | SCORED_DESCRIPTIVE | website | 27 / 13 / 1 | 51.1582 | 56.6230 | 9.6511 |
| pass_td | base | pooled2022-2024 | SCORED_DESCRIPTIVE | old_cdf | 18303 / 854 / 66 | 0.0899 | 0.0867 | -3.6802 |
| pass_td | base | website_week6 | SCORED_DESCRIPTIVE | website | 27 / 13 / 1 | 0.8427 | 0.8444 | 0.2014 |
| pass_td | context | pooled2022-2024 | SCORED_DESCRIPTIVE | old_cdf | 18303 / 854 / 66 | 0.0906 | 0.0862 | -5.1219 |
| pass_td | context | website_week6 | SCORED_DESCRIPTIVE | website | 27 / 13 / 1 | 0.8427 | 0.8444 | 0.2014 |
| pass_cmp | base | pooled2022-2024 | SCORED_DESCRIPTIVE | old_cdf | 18303 / 854 / 66 | 0.6370 | 0.6425 | 0.8570 |
| pass_cmp | base | website_week6 | SCORED_DESCRIPTIVE | website | 27 / 13 / 1 | 4.8562 | 4.5637 | -6.4091 |
| pass_cmp | context | pooled2022-2024 | SCORED_DESCRIPTIVE | old_cdf | 18303 / 854 / 66 | 0.6364 | 0.6380 | 0.2577 |
| pass_cmp | context | website_week6 | SCORED_DESCRIPTIVE | website | 27 / 13 / 1 | 4.4790 | 4.5637 | 1.8559 |
| pass_att | base | pooled2022-2024 | SCORED_DESCRIPTIVE | old_cdf | 18303 / 854 / 66 | 0.9440 | 0.9450 | 0.1070 |
| pass_att | base | website_week6 | SCORED_DESCRIPTIVE | website | 27 / 13 / 1 | 7.7309 | 7.1459 | -8.1864 |
| pass_att | context | pooled2022-2024 | SCORED_DESCRIPTIVE | old_cdf | 18303 / 854 / 66 | 0.9372 | 0.9356 | -0.1700 |
| pass_att | context | website_week6 | SCORED_DESCRIPTIVE | website | 27 / 13 / 1 | 7.1183 | 7.1459 | 0.3867 |
| pass_int | base | pooled2022-2024 | SCORED_DESCRIPTIVE | old_cdf | 18303 / 854 / 66 | 0.0702 | 0.0704 | 0.3104 |
| pass_int | base | website_week6 | SCORED_DESCRIPTIVE | website | 27 / 13 / 1 | 0.7037 | 0.6637 | -6.0268 |
| pass_int | context | pooled2022-2024 | SCORED_DESCRIPTIVE | old_cdf | 18303 / 854 / 66 | 0.0702 | 0.0703 | 0.0778 |
| pass_int | context | website_week6 | SCORED_DESCRIPTIVE | website | 27 / 13 / 1 | 0.7037 | 0.6637 | -6.0268 |
| rush_yd | base | pooled2022-2024 | SCORED_DESCRIPTIVE | old_cdf | 18303 / 854 / 66 | 10.6376 | 6.9762 | -52.4832 |
| rush_yd | base | website_week6 | SCORED_DESCRIPTIVE | website | 96 / 13 / 1 | 14.9984 | 16.5449 | 9.3470 |
| rush_yd | context | pooled2022-2024 | SCORED_DESCRIPTIVE | old_cdf | 18303 / 854 / 66 | 10.6339 | 6.9466 | -53.0816 |
| rush_yd | context | website_week6 | SCORED_DESCRIPTIVE | website | 96 / 13 / 1 | 14.9841 | 16.5449 | 9.4335 |
| rush_att | base | pooled2022-2024 | SCORED_DESCRIPTIVE | old_cdf | 18303 / 854 / 66 | 2.5193 | 1.2105 | -108.1197 |
| rush_att | base | website_week6 | SCORED_DESCRIPTIVE | website | 69 / 13 / 1 | 8.0435 | 3.4257 | -134.8014 |
| rush_att | context | pooled2022-2024 | SCORED_DESCRIPTIVE | old_cdf | 18303 / 854 / 66 | 2.5193 | 1.2057 | -108.9496 |
| rush_att | context | website_week6 | SCORED_DESCRIPTIVE | website | 69 / 13 / 1 | 8.0435 | 3.4257 | -134.8014 |
| rec | base | pooled2022-2024 | SCORED_DESCRIPTIVE | old_cdf | 18303 / 854 / 66 | 1.1476 | 1.1196 | -2.4978 |
| rec | base | website_week6 | SCORED_DESCRIPTIVE | website | 252 / 13 / 1 | 1.3325 | 1.2822 | -3.9241 |
| rec | context | pooled2022-2024 | SCORED_DESCRIPTIVE | old_cdf | 18303 / 854 / 66 | 1.1483 | 1.1179 | -2.7184 |
| rec | context | website_week6 | SCORED_DESCRIPTIVE | website | 252 / 13 / 1 | 1.3331 | 1.2822 | -3.9701 |
| rec_yd | base | pooled2022-2024 | SCORED_DESCRIPTIVE | old_cdf | 18303 / 854 / 66 | 14.3995 | 14.2641 | -0.9494 |
| rec_yd | base | website_week6 | SCORED_DESCRIPTIVE | website | 252 / 13 / 1 | 15.6949 | 15.3407 | -2.3093 |
| rec_yd | context | pooled2022-2024 | SCORED_DESCRIPTIVE | old_cdf | 18303 / 854 / 66 | 14.4101 | 14.2648 | -1.0182 |
| rec_yd | context | website_week6 | SCORED_DESCRIPTIVE | website | 252 / 13 / 1 | 15.6837 | 15.3407 | -2.2361 |
| rush_rec_yd | base | pooled2022-2024 | SCORED_DESCRIPTIVE | old_cdf | 18303 / 854 / 66 | 19.6653 | 19.5619 | -0.5286 |
| rush_rec_yd | base | website_week6 | SCORED_DESCRIPTIVE | website | 189 / 13 / 1 | 20.6289 | 19.8680 | -3.8299 |
| rush_rec_yd | context | pooled2022-2024 | SCORED_DESCRIPTIVE | old_cdf | 18303 / 854 / 66 | 19.6561 | 19.5874 | -0.3504 |
| rush_rec_yd | context | website_week6 | SCORED_DESCRIPTIVE | website | 189 / 13 / 1 | 20.6213 | 19.8680 | -3.7916 |
| fantasy_ppr | base | pooled2022-2024 | BLOCKED_CATEGORY_CONTRACT | — | — / — / — | — | — | — |
| fantasy_ppr | base | website_week6 | BLOCKED_CATEGORY_CONTRACT | — | — / — / — | — | — | — |
| fantasy_ppr | context | pooled2022-2024 | BLOCKED_CATEGORY_CONTRACT | — | — / — / — | — | — | — |
| fantasy_ppr | context | website_week6 | BLOCKED_CATEGORY_CONTRACT | — | — / — / — | — | — | — |
| anytime_td | base | pooled2022-2024 | SCORED_DESCRIPTIVE | old_cdf | 18303 / 854 / 66 | 0.1400 | 0.1382 | -1.2976 |
| anytime_td | base | website_week6 | SCORED_DESCRIPTIVE | website | 243 / 13 / 1 | 0.1414 | 0.1459 | 3.0651 |
| anytime_td | context | pooled2022-2024 | SCORED_DESCRIPTIVE | old_cdf | 18303 / 854 / 66 | 0.1390 | 0.1381 | -0.6321 |
| anytime_td | context | website_week6 | SCORED_DESCRIPTIVE | website | 243 / 13 / 1 | 0.1424 | 0.1459 | 2.3448 |

## All annual and website comparisons

Annuals, recent/pooled controls, role subsets and fixed website blends are secondary. Each comparator keeps its own paired cohort. All statuses and both role populations are retained in JSON.

| Category | Panel | Period | Family | State | Comparator | n / games / weeks | Candidate error | Control error | Delta |
|---|---|---|---|---|---|---:|---:|---:|---:|
| pass_yd | base | 2022 | pure | SCORED_DESCRIPTIVE | old_cdf | 6112 / 284 / 22 | 7.2019 | 7.2673 | -0.0654 |
| pass_yd | base | 2022 | pure | SCORED_DESCRIPTIVE | pooled | 6112 / 284 / 22 | 7.2019 | 7.7698 | -0.5678 |
| pass_yd | base | 2022 | pure | SCORED_DESCRIPTIVE | recent | 6112 / 284 / 22 | 7.2019 | 7.9758 | -0.7739 |
| pass_yd | context | 2022 | pure | SCORED_DESCRIPTIVE | old_cdf | 6112 / 284 / 22 | 7.0830 | 7.1751 | -0.0921 |
| pass_yd | context | 2022 | pure | SCORED_DESCRIPTIVE | pooled | 6112 / 284 / 22 | 7.0830 | 7.7698 | -0.6868 |
| pass_yd | context | 2022 | pure | SCORED_DESCRIPTIVE | recent | 6112 / 284 / 22 | 7.0830 | 7.9758 | -0.8928 |
| pass_td | base | 2022 | pure | SCORED_DESCRIPTIVE | old_cdf | 6112 / 284 / 22 | 0.0894 | 0.0851 | 0.0043 |
| pass_td | base | 2022 | pure | SCORED_DESCRIPTIVE | pooled | 6112 / 284 / 22 | 0.0894 | 0.0992 | -0.0098 |
| pass_td | base | 2022 | pure | SCORED_DESCRIPTIVE | recent | 6112 / 284 / 22 | 0.0894 | 0.1010 | -0.0116 |
| pass_td | context | 2022 | pure | SCORED_DESCRIPTIVE | old_cdf | 6112 / 284 / 22 | 0.0890 | 0.0844 | 0.0046 |
| pass_td | context | 2022 | pure | SCORED_DESCRIPTIVE | pooled | 6112 / 284 / 22 | 0.0890 | 0.0992 | -0.0101 |
| pass_td | context | 2022 | pure | SCORED_DESCRIPTIVE | recent | 6112 / 284 / 22 | 0.0890 | 0.1010 | -0.0119 |
| pass_cmp | base | 2022 | pure | SCORED_DESCRIPTIVE | old_cdf | 6112 / 284 / 22 | 0.6274 | 0.6348 | -0.0075 |
| pass_cmp | base | 2022 | pure | SCORED_DESCRIPTIVE | pooled | 6112 / 284 / 22 | 0.6274 | 0.6627 | -0.0353 |
| pass_cmp | base | 2022 | pure | SCORED_DESCRIPTIVE | recent | 6112 / 284 / 22 | 0.6274 | 0.6817 | -0.0544 |
| pass_cmp | context | 2022 | pure | SCORED_DESCRIPTIVE | old_cdf | 6112 / 284 / 22 | 0.6184 | 0.6278 | -0.0093 |
| pass_cmp | context | 2022 | pure | SCORED_DESCRIPTIVE | pooled | 6112 / 284 / 22 | 0.6184 | 0.6627 | -0.0442 |
| pass_cmp | context | 2022 | pure | SCORED_DESCRIPTIVE | recent | 6112 / 284 / 22 | 0.6184 | 0.6817 | -0.0633 |
| pass_att | base | 2022 | pure | SCORED_DESCRIPTIVE | old_cdf | 6112 / 284 / 22 | 0.9264 | 0.9439 | -0.0175 |
| pass_att | base | 2022 | pure | SCORED_DESCRIPTIVE | pooled | 6112 / 284 / 22 | 0.9264 | 0.9870 | -0.0607 |
| pass_att | base | 2022 | pure | SCORED_DESCRIPTIVE | recent | 6112 / 284 / 22 | 0.9264 | 1.0155 | -0.0892 |
| pass_att | context | 2022 | pure | SCORED_DESCRIPTIVE | old_cdf | 6112 / 284 / 22 | 0.9159 | 0.9300 | -0.0140 |
| pass_att | context | 2022 | pure | SCORED_DESCRIPTIVE | pooled | 6112 / 284 / 22 | 0.9159 | 0.9870 | -0.0711 |
| pass_att | context | 2022 | pure | SCORED_DESCRIPTIVE | recent | 6112 / 284 / 22 | 0.9159 | 1.0155 | -0.0996 |
| pass_int | base | 2022 | pure | SCORED_DESCRIPTIVE | old_cdf | 6112 / 284 / 22 | 0.0713 | 0.0713 | 0.0000 |
| pass_int | base | 2022 | pure | SCORED_DESCRIPTIVE | pooled | 6112 / 284 / 22 | 0.0713 | 0.0783 | -0.0069 |
| pass_int | base | 2022 | pure | SCORED_DESCRIPTIVE | recent | 6112 / 284 / 22 | 0.0713 | 0.0788 | -0.0075 |
| pass_int | context | 2022 | pure | SCORED_DESCRIPTIVE | old_cdf | 6112 / 284 / 22 | 0.0713 | 0.0720 | -0.0007 |
| pass_int | context | 2022 | pure | SCORED_DESCRIPTIVE | pooled | 6112 / 284 / 22 | 0.0713 | 0.0783 | -0.0069 |
| pass_int | context | 2022 | pure | SCORED_DESCRIPTIVE | recent | 6112 / 284 / 22 | 0.0713 | 0.0788 | -0.0075 |
| rush_yd | base | 2022 | pure | SCORED_DESCRIPTIVE | old_cdf | 6112 / 284 / 22 | 10.8696 | 7.2138 | 3.6558 |
| rush_yd | base | 2022 | pure | SCORED_DESCRIPTIVE | pooled | 6112 / 284 / 22 | 10.8696 | 8.6560 | 2.2136 |
| rush_yd | base | 2022 | pure | SCORED_DESCRIPTIVE | recent | 6112 / 284 / 22 | 10.8696 | 8.8774 | 1.9922 |
| rush_yd | context | 2022 | pure | SCORED_DESCRIPTIVE | old_cdf | 6112 / 284 / 22 | 10.8651 | 7.1890 | 3.6761 |
| rush_yd | context | 2022 | pure | SCORED_DESCRIPTIVE | pooled | 6112 / 284 / 22 | 10.8651 | 8.6560 | 2.2091 |
| rush_yd | context | 2022 | pure | SCORED_DESCRIPTIVE | recent | 6112 / 284 / 22 | 10.8651 | 8.8774 | 1.9877 |
| rush_att | base | 2022 | pure | SCORED_DESCRIPTIVE | old_cdf | 6112 / 284 / 22 | 2.5247 | 1.2317 | 1.2930 |
| rush_att | base | 2022 | pure | SCORED_DESCRIPTIVE | pooled | 6112 / 284 / 22 | 2.5247 | 1.4935 | 1.0312 |
| rush_att | base | 2022 | pure | SCORED_DESCRIPTIVE | recent | 6112 / 284 / 22 | 2.5247 | 1.5587 | 0.9660 |
| rush_att | context | 2022 | pure | SCORED_DESCRIPTIVE | old_cdf | 6112 / 284 / 22 | 2.5247 | 1.2243 | 1.3004 |
| rush_att | context | 2022 | pure | SCORED_DESCRIPTIVE | pooled | 6112 / 284 / 22 | 2.5247 | 1.4935 | 1.0312 |
| rush_att | context | 2022 | pure | SCORED_DESCRIPTIVE | recent | 6112 / 284 / 22 | 2.5247 | 1.5587 | 0.9660 |
| rec | base | 2022 | pure | SCORED_DESCRIPTIVE | old_cdf | 6112 / 284 / 22 | 1.1547 | 1.1396 | 0.0151 |
| rec | base | 2022 | pure | SCORED_DESCRIPTIVE | pooled | 6112 / 284 / 22 | 1.1547 | 1.2988 | -0.1441 |
| rec | base | 2022 | pure | SCORED_DESCRIPTIVE | recent | 6112 / 284 / 22 | 1.1547 | 1.3497 | -0.1950 |
| rec | context | 2022 | pure | SCORED_DESCRIPTIVE | old_cdf | 6112 / 284 / 22 | 1.1565 | 1.1392 | 0.0173 |
| rec | context | 2022 | pure | SCORED_DESCRIPTIVE | pooled | 6112 / 284 / 22 | 1.1565 | 1.2988 | -0.1423 |
| rec | context | 2022 | pure | SCORED_DESCRIPTIVE | recent | 6112 / 284 / 22 | 1.1565 | 1.3497 | -0.1932 |
| rec_yd | base | 2022 | pure | SCORED_DESCRIPTIVE | old_cdf | 6112 / 284 / 22 | 14.5152 | 14.3194 | 0.1958 |
| rec_yd | base | 2022 | pure | SCORED_DESCRIPTIVE | pooled | 6112 / 284 / 22 | 14.5152 | 16.4052 | -1.8900 |
| rec_yd | base | 2022 | pure | SCORED_DESCRIPTIVE | recent | 6112 / 284 / 22 | 14.5152 | 16.9849 | -2.4697 |
| rec_yd | context | 2022 | pure | SCORED_DESCRIPTIVE | old_cdf | 6112 / 284 / 22 | 14.5297 | 14.3120 | 0.2177 |
| rec_yd | context | 2022 | pure | SCORED_DESCRIPTIVE | pooled | 6112 / 284 / 22 | 14.5297 | 16.4052 | -1.8755 |
| rec_yd | context | 2022 | pure | SCORED_DESCRIPTIVE | recent | 6112 / 284 / 22 | 14.5297 | 16.9849 | -2.4552 |
| rush_rec_yd | base | 2022 | pure | SCORED_DESCRIPTIVE | old_cdf | 6112 / 284 / 22 | 20.1285 | 19.9593 | 0.1692 |
| rush_rec_yd | base | 2022 | pure | SCORED_DESCRIPTIVE | pooled | 6112 / 284 / 22 | 20.1285 | 22.6624 | -2.5339 |
| rush_rec_yd | base | 2022 | pure | SCORED_DESCRIPTIVE | recent | 6112 / 284 / 22 | 20.1285 | 23.4702 | -3.3417 |
| rush_rec_yd | context | 2022 | pure | SCORED_DESCRIPTIVE | old_cdf | 6112 / 284 / 22 | 20.1165 | 19.9777 | 0.1387 |
| rush_rec_yd | context | 2022 | pure | SCORED_DESCRIPTIVE | pooled | 6112 / 284 / 22 | 20.1165 | 22.6624 | -2.5459 |
| rush_rec_yd | context | 2022 | pure | SCORED_DESCRIPTIVE | recent | 6112 / 284 / 22 | 20.1165 | 23.4702 | -3.3537 |
| fantasy_ppr | base | 2022 | pure | BLOCKED_CATEGORY_CONTRACT | — | — / — / — | — | — | — |
| fantasy_ppr | context | 2022 | pure | BLOCKED_CATEGORY_CONTRACT | — | — / — / — | — | — | — |
| anytime_td | base | 2022 | pure | SCORED_DESCRIPTIVE | old_cdf | 6112 / 284 / 22 | 0.1433 | 0.1383 | 0.0051 |
| anytime_td | base | 2022 | pure | SCORED_DESCRIPTIVE | pooled | 6112 / 284 / 22 | 0.1433 | 0.1445 | -0.0011 |
| anytime_td | base | 2022 | pure | SCORED_DESCRIPTIVE | recent | 6112 / 284 / 22 | 0.1433 | 0.1494 | -0.0061 |
| anytime_td | context | 2022 | pure | SCORED_DESCRIPTIVE | old_cdf | 6112 / 284 / 22 | 0.1407 | 0.1379 | 0.0028 |
| anytime_td | context | 2022 | pure | SCORED_DESCRIPTIVE | pooled | 6112 / 284 / 22 | 0.1407 | 0.1445 | -0.0038 |
| anytime_td | context | 2022 | pure | SCORED_DESCRIPTIVE | recent | 6112 / 284 / 22 | 0.1407 | 0.1494 | -0.0087 |
| pass_yd | base | 2023 | pure | SCORED_DESCRIPTIVE | old_cdf | 6090 / 285 / 22 | 7.6638 | 7.8366 | -0.1728 |
| pass_yd | base | 2023 | pure | SCORED_DESCRIPTIVE | pooled | 6090 / 285 / 22 | 7.6638 | 8.6081 | -0.9443 |
| pass_yd | base | 2023 | pure | SCORED_DESCRIPTIVE | recent | 6090 / 285 / 22 | 7.6638 | 8.8683 | -1.2045 |
| pass_yd | context | 2023 | pure | SCORED_DESCRIPTIVE | old_cdf | 6090 / 285 / 22 | 7.6616 | 7.6966 | -0.0350 |
| pass_yd | context | 2023 | pure | SCORED_DESCRIPTIVE | pooled | 6090 / 285 / 22 | 7.6616 | 8.6081 | -0.9465 |
| pass_yd | context | 2023 | pure | SCORED_DESCRIPTIVE | recent | 6090 / 285 / 22 | 7.6616 | 8.8683 | -1.2067 |
| pass_td | base | 2023 | pure | SCORED_DESCRIPTIVE | old_cdf | 6090 / 285 / 22 | 0.0854 | 0.0854 | 0.0000 |
| pass_td | base | 2023 | pure | SCORED_DESCRIPTIVE | pooled | 6090 / 285 / 22 | 0.0854 | 0.0994 | -0.0140 |
| pass_td | base | 2023 | pure | SCORED_DESCRIPTIVE | recent | 6090 / 285 / 22 | 0.0854 | 0.1012 | -0.0158 |
| pass_td | context | 2023 | pure | SCORED_DESCRIPTIVE | old_cdf | 6090 / 285 / 22 | 0.0879 | 0.0837 | 0.0042 |
| pass_td | context | 2023 | pure | SCORED_DESCRIPTIVE | pooled | 6090 / 285 / 22 | 0.0879 | 0.0994 | -0.0115 |
| pass_td | context | 2023 | pure | SCORED_DESCRIPTIVE | recent | 6090 / 285 / 22 | 0.0879 | 0.1012 | -0.0133 |
| pass_cmp | base | 2023 | pure | SCORED_DESCRIPTIVE | old_cdf | 6090 / 285 / 22 | 0.6465 | 0.6527 | -0.0062 |
| pass_cmp | base | 2023 | pure | SCORED_DESCRIPTIVE | pooled | 6090 / 285 / 22 | 0.6465 | 0.7113 | -0.0648 |
| pass_cmp | base | 2023 | pure | SCORED_DESCRIPTIVE | recent | 6090 / 285 / 22 | 0.6465 | 0.7391 | -0.0926 |
| pass_cmp | context | 2023 | pure | SCORED_DESCRIPTIVE | old_cdf | 6090 / 285 / 22 | 0.6509 | 0.6481 | 0.0028 |
| pass_cmp | context | 2023 | pure | SCORED_DESCRIPTIVE | pooled | 6090 / 285 / 22 | 0.6509 | 0.7113 | -0.0605 |
| pass_cmp | context | 2023 | pure | SCORED_DESCRIPTIVE | recent | 6090 / 285 / 22 | 0.6509 | 0.7391 | -0.0882 |
| pass_att | base | 2023 | pure | SCORED_DESCRIPTIVE | old_cdf | 6090 / 285 / 22 | 0.9422 | 0.9388 | 0.0034 |
| pass_att | base | 2023 | pure | SCORED_DESCRIPTIVE | pooled | 6090 / 285 / 22 | 0.9422 | 1.0358 | -0.0936 |
| pass_att | base | 2023 | pure | SCORED_DESCRIPTIVE | recent | 6090 / 285 / 22 | 0.9422 | 1.0720 | -0.1298 |
| pass_att | context | 2023 | pure | SCORED_DESCRIPTIVE | old_cdf | 6090 / 285 / 22 | 0.9357 | 0.9338 | 0.0019 |
| pass_att | context | 2023 | pure | SCORED_DESCRIPTIVE | pooled | 6090 / 285 / 22 | 0.9357 | 1.0358 | -0.1001 |
| pass_att | context | 2023 | pure | SCORED_DESCRIPTIVE | recent | 6090 / 285 / 22 | 0.9357 | 1.0720 | -0.1363 |
| pass_int | base | 2023 | pure | SCORED_DESCRIPTIVE | old_cdf | 6090 / 285 / 22 | 0.0727 | 0.0737 | -0.0010 |
| pass_int | base | 2023 | pure | SCORED_DESCRIPTIVE | pooled | 6090 / 285 / 22 | 0.0727 | 0.0793 | -0.0065 |
| pass_int | base | 2023 | pure | SCORED_DESCRIPTIVE | recent | 6090 / 285 / 22 | 0.0727 | 0.0797 | -0.0069 |
| pass_int | context | 2023 | pure | SCORED_DESCRIPTIVE | old_cdf | 6090 / 285 / 22 | 0.0727 | 0.0752 | -0.0025 |
| pass_int | context | 2023 | pure | SCORED_DESCRIPTIVE | pooled | 6090 / 285 / 22 | 0.0727 | 0.0793 | -0.0065 |
| pass_int | context | 2023 | pure | SCORED_DESCRIPTIVE | recent | 6090 / 285 / 22 | 0.0727 | 0.0797 | -0.0069 |
| rush_yd | base | 2023 | pure | SCORED_DESCRIPTIVE | old_cdf | 6090 / 285 / 22 | 10.2448 | 6.6678 | 3.5770 |
| rush_yd | base | 2023 | pure | SCORED_DESCRIPTIVE | pooled | 6090 / 285 / 22 | 10.2448 | 7.9337 | 2.3111 |
| rush_yd | base | 2023 | pure | SCORED_DESCRIPTIVE | recent | 6090 / 285 / 22 | 10.2448 | 8.1603 | 2.0845 |
| rush_yd | context | 2023 | pure | SCORED_DESCRIPTIVE | old_cdf | 6090 / 285 / 22 | 10.2460 | 6.6236 | 3.6224 |
| rush_yd | context | 2023 | pure | SCORED_DESCRIPTIVE | pooled | 6090 / 285 / 22 | 10.2460 | 7.9337 | 2.3123 |
| rush_yd | context | 2023 | pure | SCORED_DESCRIPTIVE | recent | 6090 / 285 / 22 | 10.2460 | 8.1603 | 2.0857 |
| rush_att | base | 2023 | pure | SCORED_DESCRIPTIVE | old_cdf | 6090 / 285 / 22 | 2.5039 | 1.2056 | 1.2984 |
| rush_att | base | 2023 | pure | SCORED_DESCRIPTIVE | pooled | 6090 / 285 / 22 | 2.5039 | 1.4637 | 1.0403 |
| rush_att | base | 2023 | pure | SCORED_DESCRIPTIVE | recent | 6090 / 285 / 22 | 2.5039 | 1.5153 | 0.9886 |
| rush_att | context | 2023 | pure | SCORED_DESCRIPTIVE | old_cdf | 6090 / 285 / 22 | 2.5039 | 1.2030 | 1.3010 |
| rush_att | context | 2023 | pure | SCORED_DESCRIPTIVE | pooled | 6090 / 285 / 22 | 2.5039 | 1.4637 | 1.0403 |
| rush_att | context | 2023 | pure | SCORED_DESCRIPTIVE | recent | 6090 / 285 / 22 | 2.5039 | 1.5153 | 0.9886 |
| rec | base | 2023 | pure | SCORED_DESCRIPTIVE | old_cdf | 6090 / 285 / 22 | 1.1497 | 1.1190 | 0.0306 |
| rec | base | 2023 | pure | SCORED_DESCRIPTIVE | pooled | 6090 / 285 / 22 | 1.1497 | 1.2645 | -0.1148 |
| rec | base | 2023 | pure | SCORED_DESCRIPTIVE | recent | 6090 / 285 / 22 | 1.1497 | 1.3157 | -0.1661 |
| rec | context | 2023 | pure | SCORED_DESCRIPTIVE | old_cdf | 6090 / 285 / 22 | 1.1503 | 1.1176 | 0.0327 |
| rec | context | 2023 | pure | SCORED_DESCRIPTIVE | pooled | 6090 / 285 / 22 | 1.1503 | 1.2645 | -0.1142 |
| rec | context | 2023 | pure | SCORED_DESCRIPTIVE | recent | 6090 / 285 / 22 | 1.1503 | 1.3157 | -0.1655 |
| rec_yd | base | 2023 | pure | SCORED_DESCRIPTIVE | old_cdf | 6090 / 285 / 22 | 14.4941 | 14.4064 | 0.0877 |
| rec_yd | base | 2023 | pure | SCORED_DESCRIPTIVE | pooled | 6090 / 285 / 22 | 14.4941 | 16.4333 | -1.9392 |
| rec_yd | base | 2023 | pure | SCORED_DESCRIPTIVE | recent | 6090 / 285 / 22 | 14.4941 | 17.1359 | -2.6418 |
| rec_yd | context | 2023 | pure | SCORED_DESCRIPTIVE | old_cdf | 6090 / 285 / 22 | 14.5016 | 14.4149 | 0.0866 |
| rec_yd | context | 2023 | pure | SCORED_DESCRIPTIVE | pooled | 6090 / 285 / 22 | 14.5016 | 16.4333 | -1.9317 |
| rec_yd | context | 2023 | pure | SCORED_DESCRIPTIVE | recent | 6090 / 285 / 22 | 14.5016 | 17.1359 | -2.6343 |
| rush_rec_yd | base | 2023 | pure | SCORED_DESCRIPTIVE | old_cdf | 6090 / 285 / 22 | 19.3999 | 19.3544 | 0.0456 |
| rush_rec_yd | base | 2023 | pure | SCORED_DESCRIPTIVE | pooled | 6090 / 285 / 22 | 19.3999 | 22.0038 | -2.6038 |
| rush_rec_yd | base | 2023 | pure | SCORED_DESCRIPTIVE | recent | 6090 / 285 / 22 | 19.3999 | 22.9603 | -3.5603 |
| rush_rec_yd | context | 2023 | pure | SCORED_DESCRIPTIVE | old_cdf | 6090 / 285 / 22 | 19.3805 | 19.3532 | 0.0273 |
| rush_rec_yd | context | 2023 | pure | SCORED_DESCRIPTIVE | pooled | 6090 / 285 / 22 | 19.3805 | 22.0038 | -2.6233 |
| rush_rec_yd | context | 2023 | pure | SCORED_DESCRIPTIVE | recent | 6090 / 285 / 22 | 19.3805 | 22.9603 | -3.5798 |
| fantasy_ppr | base | 2023 | pure | BLOCKED_CATEGORY_CONTRACT | — | — / — / — | — | — | — |
| fantasy_ppr | context | 2023 | pure | BLOCKED_CATEGORY_CONTRACT | — | — / — / — | — | — | — |
| anytime_td | base | 2023 | pure | SCORED_DESCRIPTIVE | old_cdf | 6090 / 285 / 22 | 0.1362 | 0.1361 | 0.0001 |
| anytime_td | base | 2023 | pure | SCORED_DESCRIPTIVE | pooled | 6090 / 285 / 22 | 0.1362 | 0.1390 | -0.0028 |
| anytime_td | base | 2023 | pure | SCORED_DESCRIPTIVE | recent | 6090 / 285 / 22 | 0.1362 | 0.1444 | -0.0082 |
| anytime_td | context | 2023 | pure | SCORED_DESCRIPTIVE | old_cdf | 6090 / 285 / 22 | 0.1355 | 0.1361 | -0.0006 |
| anytime_td | context | 2023 | pure | SCORED_DESCRIPTIVE | pooled | 6090 / 285 / 22 | 0.1355 | 0.1390 | -0.0035 |
| anytime_td | context | 2023 | pure | SCORED_DESCRIPTIVE | recent | 6090 / 285 / 22 | 0.1355 | 0.1444 | -0.0089 |
| pass_yd | base | 2024 | pure | SCORED_DESCRIPTIVE | old_cdf | 6101 / 285 / 22 | 7.6515 | 7.7096 | -0.0581 |
| pass_yd | base | 2024 | pure | SCORED_DESCRIPTIVE | pooled | 6101 / 285 / 22 | 7.6515 | 8.7039 | -1.0524 |
| pass_yd | base | 2024 | pure | SCORED_DESCRIPTIVE | recent | 6101 / 285 / 22 | 7.6515 | 9.0001 | -1.3486 |
| pass_yd | context | 2024 | pure | SCORED_DESCRIPTIVE | old_cdf | 6101 / 285 / 22 | 7.6524 | 7.6219 | 0.0306 |
| pass_yd | context | 2024 | pure | SCORED_DESCRIPTIVE | pooled | 6101 / 285 / 22 | 7.6524 | 8.7039 | -1.0515 |
| pass_yd | context | 2024 | pure | SCORED_DESCRIPTIVE | recent | 6101 / 285 / 22 | 7.6524 | 9.0001 | -1.3477 |
| pass_td | base | 2024 | pure | SCORED_DESCRIPTIVE | old_cdf | 6101 / 285 / 22 | 0.0949 | 0.0897 | 0.0052 |
| pass_td | base | 2024 | pure | SCORED_DESCRIPTIVE | pooled | 6101 / 285 / 22 | 0.0949 | 0.1056 | -0.0107 |
| pass_td | base | 2024 | pure | SCORED_DESCRIPTIVE | recent | 6101 / 285 / 22 | 0.0949 | 0.1086 | -0.0137 |
| pass_td | context | 2024 | pure | SCORED_DESCRIPTIVE | old_cdf | 6101 / 285 / 22 | 0.0947 | 0.0903 | 0.0044 |
| pass_td | context | 2024 | pure | SCORED_DESCRIPTIVE | pooled | 6101 / 285 / 22 | 0.0947 | 0.1056 | -0.0109 |
| pass_td | context | 2024 | pure | SCORED_DESCRIPTIVE | recent | 6101 / 285 / 22 | 0.0947 | 0.1086 | -0.0138 |
| pass_cmp | base | 2024 | pure | SCORED_DESCRIPTIVE | old_cdf | 6101 / 285 / 22 | 0.6370 | 0.6399 | -0.0028 |
| pass_cmp | base | 2024 | pure | SCORED_DESCRIPTIVE | pooled | 6101 / 285 / 22 | 0.6370 | 0.7299 | -0.0928 |
| pass_cmp | base | 2024 | pure | SCORED_DESCRIPTIVE | recent | 6101 / 285 / 22 | 0.6370 | 0.7475 | -0.1104 |
| pass_cmp | context | 2024 | pure | SCORED_DESCRIPTIVE | old_cdf | 6101 / 285 / 22 | 0.6399 | 0.6383 | 0.0017 |
| pass_cmp | context | 2024 | pure | SCORED_DESCRIPTIVE | pooled | 6101 / 285 / 22 | 0.6399 | 0.7299 | -0.0900 |
| pass_cmp | context | 2024 | pure | SCORED_DESCRIPTIVE | recent | 6101 / 285 / 22 | 0.6399 | 0.7475 | -0.1075 |
| pass_att | base | 2024 | pure | SCORED_DESCRIPTIVE | old_cdf | 6101 / 285 / 22 | 0.9634 | 0.9523 | 0.0111 |
| pass_att | base | 2024 | pure | SCORED_DESCRIPTIVE | pooled | 6101 / 285 / 22 | 0.9634 | 1.0820 | -0.1186 |
| pass_att | base | 2024 | pure | SCORED_DESCRIPTIVE | recent | 6101 / 285 / 22 | 0.9634 | 1.1041 | -0.1407 |
| pass_att | context | 2024 | pure | SCORED_DESCRIPTIVE | old_cdf | 6101 / 285 / 22 | 0.9599 | 0.9430 | 0.0169 |
| pass_att | context | 2024 | pure | SCORED_DESCRIPTIVE | pooled | 6101 / 285 / 22 | 0.9599 | 1.0820 | -0.1221 |
| pass_att | context | 2024 | pure | SCORED_DESCRIPTIVE | recent | 6101 / 285 / 22 | 0.9599 | 1.1041 | -0.1442 |
| pass_int | base | 2024 | pure | SCORED_DESCRIPTIVE | old_cdf | 6101 / 285 / 22 | 0.0665 | 0.0662 | 0.0003 |
| pass_int | base | 2024 | pure | SCORED_DESCRIPTIVE | pooled | 6101 / 285 / 22 | 0.0665 | 0.0807 | -0.0141 |
| pass_int | base | 2024 | pure | SCORED_DESCRIPTIVE | recent | 6101 / 285 / 22 | 0.0665 | 0.0815 | -0.0149 |
| pass_int | context | 2024 | pure | SCORED_DESCRIPTIVE | old_cdf | 6101 / 285 / 22 | 0.0665 | 0.0636 | 0.0030 |
| pass_int | context | 2024 | pure | SCORED_DESCRIPTIVE | pooled | 6101 / 285 / 22 | 0.0665 | 0.0807 | -0.0141 |
| pass_int | context | 2024 | pure | SCORED_DESCRIPTIVE | recent | 6101 / 285 / 22 | 0.0665 | 0.0815 | -0.0149 |
| rush_yd | base | 2024 | pure | SCORED_DESCRIPTIVE | old_cdf | 6101 / 285 / 22 | 10.7972 | 7.0461 | 3.7511 |
| rush_yd | base | 2024 | pure | SCORED_DESCRIPTIVE | pooled | 6101 / 285 / 22 | 10.7972 | 8.3405 | 2.4567 |
| rush_yd | base | 2024 | pure | SCORED_DESCRIPTIVE | recent | 6101 / 285 / 22 | 10.7972 | 8.6505 | 2.1467 |
| rush_yd | context | 2024 | pure | SCORED_DESCRIPTIVE | old_cdf | 6101 / 285 / 22 | 10.7895 | 7.0261 | 3.7634 |
| rush_yd | context | 2024 | pure | SCORED_DESCRIPTIVE | pooled | 6101 / 285 / 22 | 10.7895 | 8.3405 | 2.4490 |
| rush_yd | context | 2024 | pure | SCORED_DESCRIPTIVE | recent | 6101 / 285 / 22 | 10.7895 | 8.6505 | 2.1390 |
| rush_att | base | 2024 | pure | SCORED_DESCRIPTIVE | old_cdf | 6101 / 285 / 22 | 2.5293 | 1.1942 | 1.3350 |
| rush_att | base | 2024 | pure | SCORED_DESCRIPTIVE | pooled | 6101 / 285 / 22 | 2.5293 | 1.4567 | 1.0726 |
| rush_att | base | 2024 | pure | SCORED_DESCRIPTIVE | recent | 6101 / 285 / 22 | 2.5293 | 1.5278 | 1.0015 |
| rush_att | context | 2024 | pure | SCORED_DESCRIPTIVE | old_cdf | 6101 / 285 / 22 | 2.5293 | 1.1898 | 1.3395 |
| rush_att | context | 2024 | pure | SCORED_DESCRIPTIVE | pooled | 6101 / 285 / 22 | 2.5293 | 1.4567 | 1.0726 |
| rush_att | context | 2024 | pure | SCORED_DESCRIPTIVE | recent | 6101 / 285 / 22 | 2.5293 | 1.5278 | 1.0015 |
| rec | base | 2024 | pure | SCORED_DESCRIPTIVE | old_cdf | 6101 / 285 / 22 | 1.1383 | 1.1001 | 0.0382 |
| rec | base | 2024 | pure | SCORED_DESCRIPTIVE | pooled | 6101 / 285 / 22 | 1.1383 | 1.2714 | -0.1331 |
| rec | base | 2024 | pure | SCORED_DESCRIPTIVE | recent | 6101 / 285 / 22 | 1.1383 | 1.3164 | -0.1781 |
| rec | context | 2024 | pure | SCORED_DESCRIPTIVE | old_cdf | 6101 / 285 / 22 | 1.1381 | 1.0969 | 0.0412 |
| rec | context | 2024 | pure | SCORED_DESCRIPTIVE | pooled | 6101 / 285 / 22 | 1.1381 | 1.2714 | -0.1334 |
| rec | context | 2024 | pure | SCORED_DESCRIPTIVE | recent | 6101 / 285 / 22 | 1.1381 | 1.3164 | -0.1783 |
| rec_yd | base | 2024 | pure | SCORED_DESCRIPTIVE | old_cdf | 6101 / 285 / 22 | 14.1892 | 14.0667 | 0.1225 |
| rec_yd | base | 2024 | pure | SCORED_DESCRIPTIVE | pooled | 6101 / 285 / 22 | 14.1892 | 16.2079 | -2.0186 |
| rec_yd | base | 2024 | pure | SCORED_DESCRIPTIVE | recent | 6101 / 285 / 22 | 14.1892 | 16.7493 | -2.5601 |
| rec_yd | context | 2024 | pure | SCORED_DESCRIPTIVE | old_cdf | 6101 / 285 / 22 | 14.1989 | 14.0677 | 0.1312 |
| rec_yd | context | 2024 | pure | SCORED_DESCRIPTIVE | pooled | 6101 / 285 / 22 | 14.1989 | 16.2079 | -2.0090 |
| rec_yd | context | 2024 | pure | SCORED_DESCRIPTIVE | recent | 6101 / 285 / 22 | 14.1989 | 16.7493 | -2.5504 |
| rush_rec_yd | base | 2024 | pure | SCORED_DESCRIPTIVE | old_cdf | 6101 / 285 / 22 | 19.4662 | 19.3711 | 0.0952 |
| rush_rec_yd | base | 2024 | pure | SCORED_DESCRIPTIVE | pooled | 6101 / 285 / 22 | 19.4662 | 22.2317 | -2.7655 |
| rush_rec_yd | base | 2024 | pure | SCORED_DESCRIPTIVE | recent | 6101 / 285 / 22 | 19.4662 | 23.0465 | -3.5802 |
| rush_rec_yd | context | 2024 | pure | SCORED_DESCRIPTIVE | old_cdf | 6101 / 285 / 22 | 19.4699 | 19.4303 | 0.0397 |
| rush_rec_yd | context | 2024 | pure | SCORED_DESCRIPTIVE | pooled | 6101 / 285 / 22 | 19.4699 | 22.2317 | -2.7618 |
| rush_rec_yd | context | 2024 | pure | SCORED_DESCRIPTIVE | recent | 6101 / 285 / 22 | 19.4699 | 23.0465 | -3.5766 |
| fantasy_ppr | base | 2024 | pure | BLOCKED_CATEGORY_CONTRACT | — | — / — / — | — | — | — |
| fantasy_ppr | context | 2024 | pure | BLOCKED_CATEGORY_CONTRACT | — | — / — / — | — | — | — |
| anytime_td | base | 2024 | pure | SCORED_DESCRIPTIVE | old_cdf | 6101 / 285 / 22 | 0.1404 | 0.1402 | 0.0002 |
| anytime_td | base | 2024 | pure | SCORED_DESCRIPTIVE | pooled | 6101 / 285 / 22 | 0.1404 | 0.1440 | -0.0036 |
| anytime_td | base | 2024 | pure | SCORED_DESCRIPTIVE | recent | 6101 / 285 / 22 | 0.1404 | 0.1472 | -0.0068 |
| anytime_td | context | 2024 | pure | SCORED_DESCRIPTIVE | old_cdf | 6101 / 285 / 22 | 0.1407 | 0.1403 | 0.0004 |
| anytime_td | context | 2024 | pure | SCORED_DESCRIPTIVE | pooled | 6101 / 285 / 22 | 0.1407 | 0.1440 | -0.0032 |
| anytime_td | context | 2024 | pure | SCORED_DESCRIPTIVE | recent | 6101 / 285 / 22 | 0.1407 | 0.1472 | -0.0065 |
| pass_yd | base | website_week6 | pure | SCORED_DESCRIPTIVE | old_cdf | 27 / 13 / 1 | 52.0177 | 51.7407 | 0.2770 |
| pass_yd | base | website_week6 | pure | SCORED_DESCRIPTIVE | raw | 27 / 13 / 1 | 52.0177 | 51.4470 | 0.5707 |
| pass_yd | base | website_week6 | pure | SCORED_DESCRIPTIVE | simple | 27 / 13 / 1 | 52.0177 | 55.2789 | -3.2612 |
| pass_yd | base | website_week6 | pure | SCORED_DESCRIPTIVE | website | 27 / 13 / 1 | 52.0177 | 56.6230 | -4.6052 |
| pass_yd | base | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | old_cdf | 27 / 13 / 1 | 52.4428 | 51.7407 | 0.7020 |
| pass_yd | base | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | raw | 27 / 13 / 1 | 52.4428 | 51.4470 | 0.9957 |
| pass_yd | base | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | simple | 27 / 13 / 1 | 52.4428 | 55.2789 | -2.8361 |
| pass_yd | base | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | website | 27 / 13 / 1 | 52.4428 | 56.6230 | -4.1802 |
| pass_yd | context | website_week6 | pure | SCORED_DESCRIPTIVE | old_cdf | 27 / 13 / 1 | 51.1582 | 48.7778 | 2.3805 |
| pass_yd | context | website_week6 | pure | SCORED_DESCRIPTIVE | raw | 27 / 13 / 1 | 51.1582 | 51.4470 | -0.2888 |
| pass_yd | context | website_week6 | pure | SCORED_DESCRIPTIVE | simple | 27 / 13 / 1 | 51.1582 | 55.2789 | -4.1206 |
| pass_yd | context | website_week6 | pure | SCORED_DESCRIPTIVE | website | 27 / 13 / 1 | 51.1582 | 56.6230 | -5.4647 |
| pass_yd | context | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | old_cdf | 27 / 13 / 1 | 52.0522 | 48.7778 | 3.2744 |
| pass_yd | context | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | raw | 27 / 13 / 1 | 52.0522 | 51.4470 | 0.6052 |
| pass_yd | context | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | simple | 27 / 13 / 1 | 52.0522 | 55.2789 | -3.2267 |
| pass_yd | context | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | website | 27 / 13 / 1 | 52.0522 | 56.6230 | -4.5707 |
| pass_td | base | website_week6 | pure | SCORED_DESCRIPTIVE | old_cdf | 27 / 13 / 1 | 0.8427 | 0.7037 | 0.1390 |
| pass_td | base | website_week6 | pure | SCORED_DESCRIPTIVE | raw | 27 / 13 / 1 | 0.8427 | 0.8141 | 0.0287 |
| pass_td | base | website_week6 | pure | SCORED_DESCRIPTIVE | simple | 27 / 13 / 1 | 0.8427 | 0.9427 | -0.1000 |
| pass_td | base | website_week6 | pure | SCORED_DESCRIPTIVE | website | 27 / 13 / 1 | 0.8427 | 0.8444 | -0.0017 |
| pass_td | base | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | old_cdf | 27 / 13 / 1 | 0.8077 | 0.7037 | 0.1039 |
| pass_td | base | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | raw | 27 / 13 / 1 | 0.8077 | 0.8141 | -0.0064 |
| pass_td | base | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | simple | 27 / 13 / 1 | 0.8077 | 0.9427 | -0.1351 |
| pass_td | base | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | website | 27 / 13 / 1 | 0.8077 | 0.8444 | -0.0368 |
| pass_td | context | website_week6 | pure | SCORED_DESCRIPTIVE | old_cdf | 27 / 13 / 1 | 0.8427 | 0.8519 | -0.0091 |
| pass_td | context | website_week6 | pure | SCORED_DESCRIPTIVE | raw | 27 / 13 / 1 | 0.8427 | 0.8141 | 0.0287 |
| pass_td | context | website_week6 | pure | SCORED_DESCRIPTIVE | simple | 27 / 13 / 1 | 0.8427 | 0.9427 | -0.1000 |
| pass_td | context | website_week6 | pure | SCORED_DESCRIPTIVE | website | 27 / 13 / 1 | 0.8427 | 0.8444 | -0.0017 |
| pass_td | context | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | old_cdf | 27 / 13 / 1 | 0.8077 | 0.8519 | -0.0442 |
| pass_td | context | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | raw | 27 / 13 / 1 | 0.8077 | 0.8141 | -0.0064 |
| pass_td | context | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | simple | 27 / 13 / 1 | 0.8077 | 0.9427 | -0.1351 |
| pass_td | context | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | website | 27 / 13 / 1 | 0.8077 | 0.8444 | -0.0368 |
| pass_cmp | base | website_week6 | pure | SCORED_DESCRIPTIVE | old_cdf | 27 / 13 / 1 | 4.8562 | 4.8148 | 0.0414 |
| pass_cmp | base | website_week6 | pure | SCORED_DESCRIPTIVE | raw | 27 / 13 / 1 | 4.8562 | 4.6030 | 0.2532 |
| pass_cmp | base | website_week6 | pure | SCORED_DESCRIPTIVE | simple | 27 / 13 / 1 | 4.8562 | 5.2049 | -0.3487 |
| pass_cmp | base | website_week6 | pure | SCORED_DESCRIPTIVE | website | 27 / 13 / 1 | 4.8562 | 4.5637 | 0.2925 |
| pass_cmp | base | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | old_cdf | 27 / 13 / 1 | 4.6077 | 4.8148 | -0.2071 |
| pass_cmp | base | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | raw | 27 / 13 / 1 | 4.6077 | 4.6030 | 0.0047 |
| pass_cmp | base | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | simple | 27 / 13 / 1 | 4.6077 | 5.2049 | -0.5973 |
| pass_cmp | base | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | website | 27 / 13 / 1 | 4.6077 | 4.5637 | 0.0440 |
| pass_cmp | context | website_week6 | pure | SCORED_DESCRIPTIVE | old_cdf | 27 / 13 / 1 | 4.4790 | 4.5556 | -0.0765 |
| pass_cmp | context | website_week6 | pure | SCORED_DESCRIPTIVE | raw | 27 / 13 / 1 | 4.4790 | 4.6030 | -0.1240 |
| pass_cmp | context | website_week6 | pure | SCORED_DESCRIPTIVE | simple | 27 / 13 / 1 | 4.4790 | 5.2049 | -0.7259 |
| pass_cmp | context | website_week6 | pure | SCORED_DESCRIPTIVE | website | 27 / 13 / 1 | 4.4790 | 4.5637 | -0.0847 |
| pass_cmp | context | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | old_cdf | 27 / 13 / 1 | 4.4215 | 4.5556 | -0.1340 |
| pass_cmp | context | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | raw | 27 / 13 / 1 | 4.4215 | 4.6030 | -0.1815 |
| pass_cmp | context | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | simple | 27 / 13 / 1 | 4.4215 | 5.2049 | -0.7834 |
| pass_cmp | context | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | website | 27 / 13 / 1 | 4.4215 | 4.5637 | -0.1422 |
| pass_att | base | website_week6 | pure | SCORED_DESCRIPTIVE | old_cdf | 27 / 13 / 1 | 7.7309 | 7.3704 | 0.3605 |
| pass_att | base | website_week6 | pure | SCORED_DESCRIPTIVE | raw | 27 / 13 / 1 | 7.7309 | 7.0941 | 0.6368 |
| pass_att | base | website_week6 | pure | SCORED_DESCRIPTIVE | simple | 27 / 13 / 1 | 7.7309 | 7.5026 | 0.2283 |
| pass_att | base | website_week6 | pure | SCORED_DESCRIPTIVE | website | 27 / 13 / 1 | 7.7309 | 7.1459 | 0.5850 |
| pass_att | base | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | old_cdf | 27 / 13 / 1 | 7.3462 | 7.3704 | -0.0242 |
| pass_att | base | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | raw | 27 / 13 / 1 | 7.3462 | 7.0941 | 0.2521 |
| pass_att | base | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | simple | 27 / 13 / 1 | 7.3462 | 7.5026 | -0.1564 |
| pass_att | base | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | website | 27 / 13 / 1 | 7.3462 | 7.1459 | 0.2003 |
| pass_att | context | website_week6 | pure | SCORED_DESCRIPTIVE | old_cdf | 27 / 13 / 1 | 7.1183 | 7.2222 | -0.1039 |
| pass_att | context | website_week6 | pure | SCORED_DESCRIPTIVE | raw | 27 / 13 / 1 | 7.1183 | 7.0941 | 0.0242 |
| pass_att | context | website_week6 | pure | SCORED_DESCRIPTIVE | simple | 27 / 13 / 1 | 7.1183 | 7.5026 | -0.3843 |
| pass_att | context | website_week6 | pure | SCORED_DESCRIPTIVE | website | 27 / 13 / 1 | 7.1183 | 7.1459 | -0.0276 |
| pass_att | context | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | old_cdf | 27 / 13 / 1 | 7.0478 | 7.2222 | -0.1744 |
| pass_att | context | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | raw | 27 / 13 / 1 | 7.0478 | 7.0941 | -0.0463 |
| pass_att | context | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | simple | 27 / 13 / 1 | 7.0478 | 7.5026 | -0.4548 |
| pass_att | context | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | website | 27 / 13 / 1 | 7.0478 | 7.1459 | -0.0981 |
| pass_int | base | website_week6 | pure | SCORED_DESCRIPTIVE | old_cdf | 27 / 13 / 1 | 0.7037 | 0.7037 | 0.0000 |
| pass_int | base | website_week6 | pure | SCORED_DESCRIPTIVE | raw | 27 / 13 / 1 | 0.7037 | 0.6404 | 0.0633 |
| pass_int | base | website_week6 | pure | SCORED_DESCRIPTIVE | simple | 27 / 13 / 1 | 0.7037 | 0.6582 | 0.0455 |
| pass_int | base | website_week6 | pure | SCORED_DESCRIPTIVE | website | 27 / 13 / 1 | 0.7037 | 0.6637 | 0.0400 |
| pass_int | base | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | old_cdf | 27 / 13 / 1 | 0.6833 | 0.7037 | -0.0204 |
| pass_int | base | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | raw | 27 / 13 / 1 | 0.6833 | 0.6404 | 0.0430 |
| pass_int | base | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | simple | 27 / 13 / 1 | 0.6833 | 0.6582 | 0.0251 |
| pass_int | base | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | website | 27 / 13 / 1 | 0.6833 | 0.6637 | 0.0196 |
| pass_int | context | website_week6 | pure | SCORED_DESCRIPTIVE | old_cdf | 27 / 13 / 1 | 0.7037 | 0.5556 | 0.1481 |
| pass_int | context | website_week6 | pure | SCORED_DESCRIPTIVE | raw | 27 / 13 / 1 | 0.7037 | 0.6404 | 0.0633 |
| pass_int | context | website_week6 | pure | SCORED_DESCRIPTIVE | simple | 27 / 13 / 1 | 0.7037 | 0.6582 | 0.0455 |
| pass_int | context | website_week6 | pure | SCORED_DESCRIPTIVE | website | 27 / 13 / 1 | 0.7037 | 0.6637 | 0.0400 |
| pass_int | context | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | old_cdf | 27 / 13 / 1 | 0.6833 | 0.5556 | 0.1278 |
| pass_int | context | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | raw | 27 / 13 / 1 | 0.6833 | 0.6404 | 0.0430 |
| pass_int | context | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | simple | 27 / 13 / 1 | 0.6833 | 0.6582 | 0.0251 |
| pass_int | context | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | website | 27 / 13 / 1 | 0.6833 | 0.6637 | 0.0196 |
| rush_yd | base | website_week6 | pure | SCORED_DESCRIPTIVE | old_cdf | 96 / 13 / 1 | 14.9984 | 14.8229 | 0.1755 |
| rush_yd | base | website_week6 | pure | SCORED_DESCRIPTIVE | raw | 94 / 13 / 1 | 15.2813 | 16.6109 | -1.3296 |
| rush_yd | base | website_week6 | pure | SCORED_DESCRIPTIVE | simple | 96 / 13 / 1 | 14.9984 | 17.0852 | -2.0868 |
| rush_yd | base | website_week6 | pure | SCORED_DESCRIPTIVE | website | 96 / 13 / 1 | 14.9984 | 16.5449 | -1.5465 |
| rush_yd | base | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | old_cdf | 96 / 13 / 1 | 14.7184 | 14.8229 | -0.1045 |
| rush_yd | base | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | raw | 94 / 13 / 1 | 14.9970 | 16.6109 | -1.6139 |
| rush_yd | base | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | simple | 96 / 13 / 1 | 14.7184 | 17.0852 | -2.3668 |
| rush_yd | base | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | website | 96 / 13 / 1 | 14.7184 | 16.5449 | -1.8265 |
| rush_yd | context | website_week6 | pure | SCORED_DESCRIPTIVE | old_cdf | 96 / 13 / 1 | 14.9841 | 14.8125 | 0.1716 |
| rush_yd | context | website_week6 | pure | SCORED_DESCRIPTIVE | raw | 94 / 13 / 1 | 15.2635 | 16.6109 | -1.3473 |
| rush_yd | context | website_week6 | pure | SCORED_DESCRIPTIVE | simple | 96 / 13 / 1 | 14.9841 | 17.0852 | -2.1011 |
| rush_yd | context | website_week6 | pure | SCORED_DESCRIPTIVE | website | 96 / 13 / 1 | 14.9841 | 16.5449 | -1.5608 |
| rush_yd | context | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | old_cdf | 96 / 13 / 1 | 14.7029 | 14.8125 | -0.1096 |
| rush_yd | context | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | raw | 94 / 13 / 1 | 14.9796 | 16.6109 | -1.6313 |
| rush_yd | context | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | simple | 96 / 13 / 1 | 14.7029 | 17.0852 | -2.3823 |
| rush_yd | context | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | website | 96 / 13 / 1 | 14.7029 | 16.5449 | -1.8420 |
| rush_att | base | website_week6 | pure | SCORED_DESCRIPTIVE | old_cdf | 69 / 13 / 1 | 8.0435 | 3.7246 | 4.3188 |
| rush_att | base | website_week6 | pure | SCORED_DESCRIPTIVE | raw | 67 / 13 / 1 | 8.2239 | 3.3549 | 4.8690 |
| rush_att | base | website_week6 | pure | SCORED_DESCRIPTIVE | simple | 69 / 13 / 1 | 8.0435 | 4.4463 | 3.5972 |
| rush_att | base | website_week6 | pure | SCORED_DESCRIPTIVE | website | 69 / 13 / 1 | 8.0435 | 3.4257 | 4.6178 |
| rush_att | base | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | old_cdf | 69 / 13 / 1 | 4.6060 | 3.7246 | 0.8814 |
| rush_att | base | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | raw | 67 / 13 / 1 | 4.7088 | 3.3549 | 1.3539 |
| rush_att | base | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | simple | 69 / 13 / 1 | 4.6060 | 4.4463 | 0.1597 |
| rush_att | base | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | website | 69 / 13 / 1 | 4.6060 | 3.4257 | 1.1804 |
| rush_att | context | website_week6 | pure | SCORED_DESCRIPTIVE | old_cdf | 69 / 13 / 1 | 8.0435 | 3.8116 | 4.2319 |
| rush_att | context | website_week6 | pure | SCORED_DESCRIPTIVE | raw | 67 / 13 / 1 | 8.2239 | 3.3549 | 4.8690 |
| rush_att | context | website_week6 | pure | SCORED_DESCRIPTIVE | simple | 69 / 13 / 1 | 8.0435 | 4.4463 | 3.5972 |
| rush_att | context | website_week6 | pure | SCORED_DESCRIPTIVE | website | 69 / 13 / 1 | 8.0435 | 3.4257 | 4.6178 |
| rush_att | context | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | old_cdf | 69 / 13 / 1 | 4.6060 | 3.8116 | 0.7944 |
| rush_att | context | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | raw | 67 / 13 / 1 | 4.7088 | 3.3549 | 1.3539 |
| rush_att | context | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | simple | 69 / 13 / 1 | 4.6060 | 4.4463 | 0.1597 |
| rush_att | context | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | website | 69 / 13 / 1 | 4.6060 | 3.4257 | 1.1804 |
| rec | base | website_week6 | pure | SCORED_DESCRIPTIVE | old_cdf | 252 / 13 / 1 | 1.3325 | 1.2778 | 0.0547 |
| rec | base | website_week6 | pure | SCORED_DESCRIPTIVE | raw | 243 / 13 / 1 | 1.3764 | 1.3170 | 0.0593 |
| rec | base | website_week6 | pure | SCORED_DESCRIPTIVE | simple | 252 / 13 / 1 | 1.3325 | 1.4719 | -0.1394 |
| rec | base | website_week6 | pure | SCORED_DESCRIPTIVE | website | 252 / 13 / 1 | 1.3325 | 1.2822 | 0.0503 |
| rec | base | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | old_cdf | 252 / 13 / 1 | 1.2864 | 1.2778 | 0.0087 |
| rec | base | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | raw | 243 / 13 / 1 | 1.3271 | 1.3170 | 0.0101 |
| rec | base | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | simple | 252 / 13 / 1 | 1.2864 | 1.4719 | -0.1855 |
| rec | base | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | website | 252 / 13 / 1 | 1.2864 | 1.2822 | 0.0043 |
| rec | context | website_week6 | pure | SCORED_DESCRIPTIVE | old_cdf | 252 / 13 / 1 | 1.3331 | 1.2698 | 0.0632 |
| rec | context | website_week6 | pure | SCORED_DESCRIPTIVE | raw | 243 / 13 / 1 | 1.3770 | 1.3170 | 0.0599 |
| rec | context | website_week6 | pure | SCORED_DESCRIPTIVE | simple | 252 / 13 / 1 | 1.3331 | 1.4719 | -0.1388 |
| rec | context | website_week6 | pure | SCORED_DESCRIPTIVE | website | 252 / 13 / 1 | 1.3331 | 1.2822 | 0.0509 |
| rec | context | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | old_cdf | 252 / 13 / 1 | 1.2868 | 1.2698 | 0.0169 |
| rec | context | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | raw | 243 / 13 / 1 | 1.3275 | 1.3170 | 0.0105 |
| rec | context | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | simple | 252 / 13 / 1 | 1.2868 | 1.4719 | -0.1851 |
| rec | context | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | website | 252 / 13 / 1 | 1.2868 | 1.2822 | 0.0046 |
| rec_yd | base | website_week6 | pure | SCORED_DESCRIPTIVE | old_cdf | 252 / 13 / 1 | 15.6949 | 15.5595 | 0.1354 |
| rec_yd | base | website_week6 | pure | SCORED_DESCRIPTIVE | raw | 243 / 13 / 1 | 16.2117 | 15.7426 | 0.4692 |
| rec_yd | base | website_week6 | pure | SCORED_DESCRIPTIVE | simple | 252 / 13 / 1 | 15.6949 | 16.3959 | -0.7009 |
| rec_yd | base | website_week6 | pure | SCORED_DESCRIPTIVE | website | 252 / 13 / 1 | 15.6949 | 15.3407 | 0.3543 |
| rec_yd | base | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | old_cdf | 252 / 13 / 1 | 14.9560 | 15.5595 | -0.6035 |
| rec_yd | base | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | raw | 243 / 13 / 1 | 15.4546 | 15.7426 | -0.2879 |
| rec_yd | base | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | simple | 252 / 13 / 1 | 14.9560 | 16.3959 | -1.4398 |
| rec_yd | base | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | website | 252 / 13 / 1 | 14.9560 | 15.3407 | -0.3846 |
| rec_yd | context | website_week6 | pure | SCORED_DESCRIPTIVE | old_cdf | 252 / 13 / 1 | 15.6837 | 15.5675 | 0.1162 |
| rec_yd | context | website_week6 | pure | SCORED_DESCRIPTIVE | raw | 243 / 13 / 1 | 16.1965 | 15.7426 | 0.4539 |
| rec_yd | context | website_week6 | pure | SCORED_DESCRIPTIVE | simple | 252 / 13 / 1 | 15.6837 | 16.3959 | -0.7122 |
| rec_yd | context | website_week6 | pure | SCORED_DESCRIPTIVE | website | 252 / 13 / 1 | 15.6837 | 15.3407 | 0.3430 |
| rec_yd | context | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | old_cdf | 252 / 13 / 1 | 14.9586 | 15.5675 | -0.6089 |
| rec_yd | context | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | raw | 243 / 13 / 1 | 15.4555 | 15.7426 | -0.2870 |
| rec_yd | context | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | simple | 252 / 13 / 1 | 14.9586 | 16.3959 | -1.4373 |
| rec_yd | context | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | website | 252 / 13 / 1 | 14.9586 | 15.3407 | -0.3821 |
| rush_rec_yd | base | website_week6 | pure | SCORED_DESCRIPTIVE | old_cdf | 189 / 13 / 1 | 20.6289 | 20.6296 | -0.0007 |
| rush_rec_yd | base | website_week6 | pure | SCORED_DESCRIPTIVE | raw | 184 / 13 / 1 | 21.1201 | 20.0888 | 1.0313 |
| rush_rec_yd | base | website_week6 | pure | SCORED_DESCRIPTIVE | simple | 189 / 13 / 1 | 20.6289 | 19.9976 | 0.6313 |
| rush_rec_yd | base | website_week6 | pure | SCORED_DESCRIPTIVE | website | 189 / 13 / 1 | 20.6289 | 19.8680 | 0.7609 |
| rush_rec_yd | base | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | old_cdf | 189 / 13 / 1 | 19.5254 | 20.6296 | -1.1043 |
| rush_rec_yd | base | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | raw | 184 / 13 / 1 | 19.9929 | 20.0888 | -0.0959 |
| rush_rec_yd | base | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | simple | 189 / 13 / 1 | 19.5254 | 19.9976 | -0.4722 |
| rush_rec_yd | base | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | website | 189 / 13 / 1 | 19.5254 | 19.8680 | -0.3426 |
| rush_rec_yd | context | website_week6 | pure | SCORED_DESCRIPTIVE | old_cdf | 189 / 13 / 1 | 20.6213 | 20.5397 | 0.0816 |
| rush_rec_yd | context | website_week6 | pure | SCORED_DESCRIPTIVE | raw | 184 / 13 / 1 | 21.1132 | 20.0888 | 1.0244 |
| rush_rec_yd | context | website_week6 | pure | SCORED_DESCRIPTIVE | simple | 189 / 13 / 1 | 20.6213 | 19.9976 | 0.6237 |
| rush_rec_yd | context | website_week6 | pure | SCORED_DESCRIPTIVE | website | 189 / 13 / 1 | 20.6213 | 19.8680 | 0.7533 |
| rush_rec_yd | context | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | old_cdf | 189 / 13 / 1 | 19.4936 | 20.5397 | -1.0461 |
| rush_rec_yd | context | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | raw | 184 / 13 / 1 | 19.9607 | 20.0888 | -0.1281 |
| rush_rec_yd | context | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | simple | 189 / 13 / 1 | 19.4936 | 19.9976 | -0.5040 |
| rush_rec_yd | context | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | website | 189 / 13 / 1 | 19.4936 | 19.8680 | -0.3744 |
| fantasy_ppr | base | website_week6 | pure | BLOCKED_CATEGORY_CONTRACT | — | — / — / — | — | — | — |
| fantasy_ppr | base | website_week6 | website_equalweight_secondary | BLOCKED_CATEGORY_CONTRACT | — | — / — / — | — | — | — |
| fantasy_ppr | context | website_week6 | pure | BLOCKED_CATEGORY_CONTRACT | — | — / — / — | — | — | — |
| fantasy_ppr | context | website_week6 | website_equalweight_secondary | BLOCKED_CATEGORY_CONTRACT | — | — / — / — | — | — | — |
| anytime_td | base | website_week6 | pure | SCORED_DESCRIPTIVE | old_cdf | 243 / 13 / 1 | 0.1414 | 0.1399 | 0.0015 |
| anytime_td | base | website_week6 | pure | SCORED_DESCRIPTIVE | raw | 0 / 0 / 0 | — | — | — |
| anytime_td | base | website_week6 | pure | SCORED_DESCRIPTIVE | simple | 243 / 13 / 1 | 0.1414 | 0.1521 | -0.0108 |
| anytime_td | base | website_week6 | pure | SCORED_DESCRIPTIVE | website | 243 / 13 / 1 | 0.1414 | 0.1459 | -0.0045 |
| anytime_td | base | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | old_cdf | 243 / 13 / 1 | 0.1420 | 0.1399 | 0.0020 |
| anytime_td | base | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | raw | 0 / 0 / 0 | — | — | — |
| anytime_td | base | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | simple | 243 / 13 / 1 | 0.1420 | 0.1521 | -0.0102 |
| anytime_td | base | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | website | 243 / 13 / 1 | 0.1420 | 0.1459 | -0.0039 |
| anytime_td | context | website_week6 | pure | SCORED_DESCRIPTIVE | old_cdf | 243 / 13 / 1 | 0.1424 | 0.1410 | 0.0015 |
| anytime_td | context | website_week6 | pure | SCORED_DESCRIPTIVE | raw | 0 / 0 / 0 | — | — | — |
| anytime_td | context | website_week6 | pure | SCORED_DESCRIPTIVE | simple | 243 / 13 / 1 | 0.1424 | 0.1521 | -0.0097 |
| anytime_td | context | website_week6 | pure | SCORED_DESCRIPTIVE | website | 243 / 13 / 1 | 0.1424 | 0.1459 | -0.0034 |
| anytime_td | context | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | old_cdf | 243 / 13 / 1 | 0.1422 | 0.1410 | 0.0012 |
| anytime_td | context | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | raw | 0 / 0 / 0 | — | — | — |
| anytime_td | context | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | simple | 243 / 13 / 1 | 0.1422 | 0.1521 | -0.0099 |
| anytime_td | context | website_week6 | website_equalweight_secondary | SCORED_DESCRIPTIVE | website | 243 / 13 / 1 | 0.1422 | 0.1459 | -0.0036 |

## Primary paired point diagnostics

| Category | Panel | Period | Candidate RMSE / bias / p90 AE / p95 AE / max AE | Control RMSE / bias / p90 AE / p95 AE / max AE |
|---|---|---|---:|---:|
| pass_yd | base | pooled2022-2024 | 28.4085 / 0.0634 / 12.2249 / 61.0789 / 367.4056 | 29.0747 / -0.0158 / 12.8000 / 61.0000 / 355.0000 |
| pass_yd | base | website_week6 | 67.0593 / -20.9587 / 117.1522 / 125.2311 / 143.5102 | 73.7983 / -19.0815 / 99.9200 / 119.4010 / 241.0200 |
| pass_yd | context | pooled2022-2024 | 28.0707 / 0.0910 / 12.1080 / 61.5757 / 354.8281 | 28.5589 / -0.2637 / 13.0000 / 60.0000 / 355.0000 |
| pass_yd | context | website_week6 | 63.0475 / -21.5648 / 102.9908 / 115.2807 / 141.5894 | 73.7983 / -19.0815 / 99.9200 / 119.4010 / 241.0200 |
| pass_td | base | pooled2022-2024 | 0.3694 / -0.0252 / 0.0000 / 1.0000 / 5.0000 | 0.3649 / -0.0193 / 0.0000 / 1.0000 / 5.0000 |
| pass_td | base | website_week6 | 1.1198 / -0.5279 / 1.9700 / 2.0000 / 2.0005 | 1.1112 / -0.1570 / 1.7500 / 2.1470 / 2.6600 |
| pass_td | context | pooled2022-2024 | 0.3627 / -0.0167 / 0.0004 / 0.9995 / 4.9916 | 0.3632 / -0.0219 / 0.0000 / 1.0000 / 5.0000 |
| pass_td | context | website_week6 | 1.1198 / -0.5279 / 1.9700 / 2.0000 / 2.0005 | 1.1112 / -0.1570 / 1.7500 / 2.1470 / 2.6600 |
| pass_cmp | base | pooled2022-2024 | 2.4366 / 0.0005 / 1.0000 / 5.2036 / 26.0418 | 2.4949 / -0.0406 / 1.0000 / 5.0000 / 32.0000 |
| pass_cmp | base | website_week6 | 6.5136 / -2.4447 / 11.2754 / 12.7589 / 16.3265 | 5.7934 / -2.6837 / 10.1180 / 11.2400 / 12.4000 |
| pass_cmp | context | pooled2022-2024 | 2.4057 / 0.0302 / 1.0000 / 5.2213 / 25.0000 | 2.4642 / -0.0439 / 1.0000 / 5.0000 / 30.0000 |
| pass_cmp | context | website_week6 | 6.0577 / -2.4754 / 10.9934 / 12.1341 / 14.6402 | 5.7934 / -2.6837 / 10.1180 / 11.2400 / 12.4000 |
| pass_att | base | pooled2022-2024 | 3.6722 / 0.0134 / 1.3033 / 7.4454 / 45.5135 | 3.7358 / -0.0332 / 1.0000 / 7.0000 / 50.0000 |
| pass_att | base | website_week6 | 10.0836 / -5.3427 / 14.7593 / 18.5915 / 28.5806 | 9.3864 / -5.3919 / 17.0920 / 18.7790 / 20.6800 |
| pass_att | context | pooled2022-2024 | 3.6217 / 0.0345 / 1.4459 / 7.3732 / 42.4235 | 3.6786 / -0.0456 / 1.0000 / 7.0000 / 49.0000 |
| pass_att | context | website_week6 | 9.3817 / -5.0035 / 13.6877 / 18.1991 / 25.2659 | 9.3864 / -5.3919 / 17.0920 / 18.7790 / 20.6800 |
| pass_int | base | pooled2022-2024 | 0.3488 / -0.0692 / 0.0000 / 0.0000 / 5.0000 | 0.3377 / -0.0526 / 0.0000 / 1.0000 / 5.0000 |
| pass_int | base | website_week6 | 1.0000 / -0.7037 / 2.0000 / 2.0000 / 2.0000 | 0.7693 / -0.1096 / 1.3060 / 1.4600 / 1.6300 |
| pass_int | context | pooled2022-2024 | 0.3488 / -0.0692 / 0.0000 / 0.0000 / 5.0000 | 0.3284 / -0.0399 / 0.0000 / 1.0000 / 5.0000 |
| pass_int | context | website_week6 | 1.0000 / -0.7037 / 2.0000 / 2.0000 / 2.0000 | 0.7693 / -0.1096 / 1.3060 / 1.4600 / 1.6300 |
| rush_yd | base | pooled2022-2024 | 26.0654 / -9.6555 / 37.8198 / 64.0000 / 255.0000 | 16.4762 / -2.9568 / 23.0000 / 37.0000 / 196.0000 |
| rush_yd | base | website_week6 | 20.9426 / -4.6957 / 31.9808 / 49.2514 / 67.6457 | 21.3169 / 4.4366 / 33.8150 / 45.0075 / 57.3000 |
| rush_yd | context | pooled2022-2024 | 26.0515 / -9.6060 / 37.0533 / 64.0000 / 255.0000 | 16.3929 / -2.9314 / 23.0000 / 36.0000 / 196.0000 |
| rush_yd | context | website_week6 | 20.9703 / -4.7865 / 32.2080 / 49.9831 / 67.5398 | 21.3169 / 4.4366 / 33.8150 / 45.0075 / 57.3000 |
| rush_att | base | pooled2022-2024 | 5.5799 / -2.4977 / 9.0000 / 14.0000 / 37.0000 | 2.6887 / -0.3938 / 4.0000 / 6.0000 / 27.0000 |
| rush_att | base | website_week6 | 10.5494 / -8.0435 / 18.2000 / 19.6000 / 28.0000 | 4.3898 / -0.0103 / 7.2380 / 8.1300 / 11.1700 |
| rush_att | context | pooled2022-2024 | 5.5799 / -2.4977 / 9.0000 / 14.0000 / 37.0000 | 2.6711 / -0.3835 / 4.0000 / 6.0000 / 27.0000 |
| rush_att | context | website_week6 | 10.5494 / -8.0435 / 18.2000 / 19.6000 / 28.0000 | 4.3898 / -0.0103 / 7.2380 / 8.1300 / 11.1700 |
| rec | base | pooled2022-2024 | 1.7207 / -0.2747 / 2.8984 / 3.7994 / 13.0000 | 1.7301 / -0.3122 / 3.0000 / 4.0000 / 13.0000 |
| rec | base | website_week6 | 1.9117 / -0.4610 / 3.0620 / 3.9208 / 8.9940 | 1.7674 / -0.3209 / 2.9340 / 3.5970 / 7.3500 |
| rec | context | pooled2022-2024 | 1.7218 / -0.2778 / 2.8966 / 3.8185 / 13.0000 | 1.7268 / -0.3126 / 3.0000 / 4.0000 / 13.0000 |
| rec | context | website_week6 | 1.9122 / -0.4604 / 3.0620 / 3.9231 / 8.9956 | 1.7674 / -0.3209 / 2.9340 / 3.5970 / 7.3500 |
| rec_yd | base | pooled2022-2024 | 23.5025 / -4.9294 / 37.0220 / 51.3553 / 213.5597 | 23.4714 / -5.3239 / 37.0000 / 51.0000 / 210.0000 |
| rec_yd | base | website_week6 | 23.8386 / -6.8617 / 42.2638 / 52.8147 / 113.7942 | 22.4382 / -2.2849 / 35.5720 / 45.9825 / 99.4600 |
| rec_yd | context | pooled2022-2024 | 23.5538 / -5.0310 / 37.0119 / 51.3247 / 213.9219 | 23.4984 / -5.4490 / 37.0000 / 51.0000 / 212.0000 |
| rec_yd | context | website_week6 | 23.8431 / -6.9037 / 42.3057 / 52.8438 / 113.8470 | 22.4382 / -2.2849 / 35.5720 / 45.9825 / 99.4600 |
| rush_rec_yd | base | pooled2022-2024 | 28.9158 / -5.6490 / 46.0758 / 61.3991 / 223.9037 | 28.9600 / -6.6727 / 46.0000 / 62.0000 / 219.0000 |
| rush_rec_yd | base | website_week6 | 29.3199 / -8.0724 / 48.3349 / 65.2931 / 111.6973 | 27.7236 / -0.9318 / 43.9680 / 60.3160 / 99.4700 |
| rush_rec_yd | context | pooled2022-2024 | 28.9116 / -5.7006 / 46.0000 / 61.6845 / 224.3897 | 29.0277 / -6.8163 / 47.0000 / 62.0000 / 222.0000 |
| rush_rec_yd | context | website_week6 | 29.3985 / -8.3429 / 48.2976 / 65.4451 / 112.2080 | 27.7236 / -0.9318 / 43.9680 / 60.3160 / 99.4700 |
| anytime_td | base | pooled2022-2024 | 0.3741 / 0.0170 / 0.7385 / 0.8363 / 0.9707 | 0.3717 / 0.0089 / 0.7399 / 0.8410 / 0.9763 |
| anytime_td | base | website_week6 | 0.3760 / 0.0008 / 0.7549 / 0.8413 / 0.9390 | 0.3819 / 0.0011 / 0.7330 / 0.8673 / 0.9700 |
| anytime_td | context | pooled2022-2024 | 0.3728 / 0.0107 / 0.7453 / 0.8414 / 0.9723 | 0.3716 / 0.0068 / 0.7414 / 0.8435 / 0.9779 |
| anytime_td | context | website_week6 | 0.3774 / -0.0098 / 0.7624 / 0.8489 / 0.9494 | 0.3819 / 0.0011 / 0.7330 / 0.8673 / 0.9700 |

## Source and evidence limits

- This is a joint learner and source reconstruction candidate. Model inputs use the separately approved NFL-statistics and eligible-roster packet; inherited PFR-dependent models are retained as frozen comparators only. No universal source-rights grant is claimed.
- All retained years and Week6 are exposed. Current revisions, postgame source qualification and the assumed seven-day historical label lag do not authenticate historical publication, pregame availability or contemporaneous improvement.
- Historical primary errors pool the2022–2024 paired rows before calculation. They are not averages of annual MAEs. Both fixed panels, every category, all losses and all failures remain visible.
- The48 primary slots include4 blocked exact-PPR slots. The96 planned target/panel/period attempts include8 blocked PPR slots and at most88 fits. The24 fixed website-blend slots are secondary, including2 blocked PPR slots.
- Each comparator has its own exact supported-played, finite-point paired cohort. Source changes can alter qualified outcomes and denominators. Common, candidate-only and control-only counts, participation changes, missingness and quarantined contradictions are retained. Losses on different cohorts are not interchangeable.
- Numeric outputs are MAE-objective point heuristics, not a forecast mean, integer-law median or distribution. Counts have the declared max(0,prediction) transform and can be fractional; signed yards are not clamped. Only anytime TD supplies a genuine probability, without clipping.
- Historical week/game intervals use the saved500-draw fixed-seed evaluator and are nominal95%, unadjusted and descriptive. Week6 has no intervals. No untouched confirmation, significance, selected winner, qualification or promotion follows.
- The website blend is only the predeclared secondary50/50 website/candidate point or probability, with no extra fit or weight search. Missing site points remain abstentions. DNP, unknown participation, played missing, played zero and quarantines remain distinct.
- The exporter copies saved aggregates and metadata only. It does not read player/game rows, training labels or fitted model bytes, and performs no fit, forecast, scoring, resampling or technical replay.

Exact saved intervals, tail errors, fallback/outcome/source-lineage counts, probability log losses and reliability deciles, all attempt statuses and private-artifact hashes are retained in aggregate-report.json. No player/game rows or fitted values are published.
