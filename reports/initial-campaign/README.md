# Initial historical campaign

Exploratory current-vintage reconstruction. Development2022–23; validation2024. All supplied offensive skill player-games, including postseason; separate role/player/team/opponent metrics are retained locally. Later confirmation is pending. No model is promoted.

| Target | Development-selected method | Validation primary gain vs recent | Bias gate |
|---|---|---:|---|
| anytime_td | tree | 6.05% | pass |
| fantasy_ppr | unsupported | unavailable | fail/unavailable |
| pass_att | tree | 10.40% | pass |
| pass_cmp | tree | 11.11% | pass |
| pass_int | tree | 3.81% | fail/unavailable |
| pass_td | tree | 8.25% | pass |
| pass_yd | tree | 13.00% | pass |
| rec | ridge_without_opponent | 13.25% | pass |
| rec_yd | ridge_without_team | 12.37% | pass |
| rush_att | tree | 16.18% | pass |
| rush_rec_yd | ridge_without_opponent | 14.48% | pass |
| rush_yd | tree | 11.92% | fail/unavailable |

The11 supported targets each have6,214 paired played observations across22 validation weeks. These are broad all-skill cohorts with many zero passing outcomes for non-QBs, not the original27-row passing study. The QB-specific passing-yard MAE is77.6729 for recent and67.5532 for tree (n697). The exact PPR crosswalk remains unsupported; no generic provider total was substituted.

Ridge/tree/workload marginal completions can exceed their corresponding attempts. Their frozen results remain visible, and they do not qualify as coherent joint exports. Default new daily issuance uses recent and pooled controls; structural tests do not confer scientific qualification.

The original passing-yard challenger remains unrecovered. Its reported n27/13-game gain and worse bias are preserved in execution/evidence-inventory.json. The recovered baseline plus current-vintage outcomes supplies a separate newly labeled replay; strict missing-field semantics reduce coverage for some categories. Baseline summaries show both total and matched populations. No TD probability is invented from an unbound expected count.

All432 configured season/target/method trials completed. Iteration-limit warnings were retained. The first reporting loop was interrupted after fits because repeated subgroup probability scores were expensive; reports were regenerated from the identical3,906,432 saved forecast rows in66.58 seconds. No fit was repeated to choose a favorable result.

Raw source bodies and historical row tables remain ignored locally. Public files contain derived aggregate metrics and hashes. Source: nflverse/nfldata and nflverse/nflverse-data (CC-BY-4.0 hosting license; upstream source rights remain separate), public Sleeper statistics, and ESPN final statuses. Historic publication clocks are not authenticated; a seven-day lag is an explicit assumption.
