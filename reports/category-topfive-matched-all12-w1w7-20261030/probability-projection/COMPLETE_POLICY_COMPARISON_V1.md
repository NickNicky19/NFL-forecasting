## Complete selection policies: P1 points versus P2 probabilities

This is a pure projection of completed exposed 2026 Weeks 1–7 aggregates, not a new forecast, scored experiment or deployed strategy. P1 and P2 use the full recorded board intersected with their registered roster queries, including offered role exceptions. This differs from the numerical-MAE primary-position population and the new flat control’s separately reported primary-role subset.

The equal-capacity table groups by category, policy, original full-board pool, the seven weekly selection counts, decisive count, pushes and unresolved outcomes. Equal capacity does **not** mean identical selected players; the conditional percentages are descriptive, not a new paired accuracy test. Existing source comparisons/uncertainty remain available. Partial Depth-CDF Weeks 1–6 is excluded from full-seven-week leaders.

| Category | Highest observed full-coverage policy (including always-side controls) | Correct / decided | Own Over | Own Under |
|---|---|---:|---:|---:|
| pass_att | CONTROL ALWAYS_OVER CONSTANT_SIDE_NO_PROBABILITY | 76/143 | 76/143 | 0/0 |
| pass_cmp | CONTROL ALWAYS_OVER CONSTANT_SIDE_NO_PROBABILITY | 82/144 | 82/144 | 0/0 |
| pass_int | P1_POINT_GAP LEAF_CDF mean | 83/143 | 75/133 | 8/10 |
| pass_td | P1_POINT_GAP COUNT_A_MEAN mean_objective_point | 87/142 | 43/74 | 44/68 |
| pass_yd | P1_POINT_GAP HGB_MAE_DIRECT mae_objective_point | 78/143 | 41/70 | 37/73 |
| rec | P1_POINT_GAP LEAF_CDF median | 521/917 | 157/260 | 364/657 |
| rec_yd | P1_POINT_GAP RESPONSE_CDF mean | 499/929 | 298/566 | 201/363 |
| rush_att | P1_POINT_GAP BACKFIELD_CDF mean | 174/327 | 70/130 | 104/197 |
| rush_rec_yd | P1_POINT_GAP RESPONSE_CDF mean | 247/468 | 117/230 | 130/238 |
| rush_yd | P1_POINT_GAP LEAF_CDF median | 260/443 | 58/110 | 202/333 |

[Every observed leader within equal capacity](COMPLETE_POLICY_CAPACITY_LEADERS_V1.csv.gz) separates full board, Top 6, Top 10, Top 20 and the P2 0.55 abstaining rule. P1 ranks unrounded absolute point gap; P2 ranks frozen decisive-side probability. These ranking mechanisms remain different. A P1 0.55 probability rule is unsupported; points do not imply probabilities. The earlier IQR abstention input was unavailable, so no substitute was fabricated.

[Full-coverage leaders and the complete always-Over/always-Under controls](COMPLETE_POLICY_FULL_COVERAGE_AND_CONTROLS_V1.csv.gz) show every denominator. Full coverage here means all registered offered opportunities selected, with the same decisive count as the always-side controls; policies with abstention are preserved in their separate capacity groups, not discarded. Models may still use registered fallbacks.

The maximum is selected descriptively after examining this development panel. It is not an earlier-trained selector, is not a proposal to stitch the best Over and Under models together, and is not a production policy decision. Ties and small samples remain visible. No venue settlement, prices, paper return or profitability is inferred. Anytime TD has a separate binary event contract; chart-PPR and targets have no compatible ordinary offered board. Their statistical/probability research remains separate.

All complete policy records and their weekly counts remain in the immutable source aggregates. No original forecasts, lines, selected sides, model identities or rules changed.
