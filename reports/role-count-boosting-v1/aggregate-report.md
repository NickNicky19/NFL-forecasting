# Role and count reporting repair

Exposed role/count research aggregates from a separately registered zero-fit reporting repair; original reporting failure retained

Original attempt: INCOMPLETE_RETAINED_NO_RESTART; 136 consumed fits; reporting failed.
Repair: COMPLETED_REPORTING_REPAIR_DESCRIPTIVE; 0 new fits; 0 predictions; 0 independent observations.
Consumed reporting/scoring phases: 1 failed original + 1 repair = 2 cumulative phases. Original registered score passes: 1.

Historical primary: unchanged primary roles versus old HGB. Week6 primary: all original offers versus SITE. Numeric loss is MAE; anytime TD loss is Brier.

| Category | Variant | Period | State | Comparator | Pairs / games / weeks | Candidate | Control | Delta |
|---|---|---|---|---|---:|---:|---:|---:|
| pass_yd | A | pooled2022-2024 | SCORED_DESCRIPTIVE | old_hgb | 2049 / 854 / 66 | 66.645 | 66.645 | 0 |
| pass_yd | A | website_week6 | SCORED_DESCRIPTIVE | website | 27 / 13 / 1 | 52.018 | 56.623 | -4.6052 |
| pass_yd | B | pooled2022-2024 | SCORED_DESCRIPTIVE | old_hgb | 2049 / 854 / 66 | 66.645 | 66.645 | 0 |
| pass_yd | B | website_week6 | SCORED_DESCRIPTIVE | website | 27 / 13 / 1 | 52.018 | 56.623 | -4.6052 |
| pass_td | A | pooled2022-2024 | SCORED_DESCRIPTIVE | old_hgb | 2049 / 854 / 66 | 0.83471 | 0.79424 | 0.040466 |
| pass_td | A | website_week6 | SCORED_DESCRIPTIVE | website | 27 / 13 / 1 | 0.7746 | 0.84444 | -0.069847 |
| pass_td | B | pooled2022-2024 | SCORED_DESCRIPTIVE | old_hgb | 2049 / 854 / 66 | 0.83471 | 0.79424 | 0.040466 |
| pass_td | B | website_week6 | SCORED_DESCRIPTIVE | website | 27 / 13 / 1 | 0.7746 | 0.84444 | -0.069847 |
| pass_cmp | A | pooled2022-2024 | SCORED_DESCRIPTIVE | old_hgb | 2049 / 854 / 66 | 5.7331 | 5.6619 | 0.071197 |
| pass_cmp | A | website_week6 | SCORED_DESCRIPTIVE | website | 27 / 13 / 1 | 4.8755 | 4.5637 | 0.31183 |
| pass_cmp | B | pooled2022-2024 | SCORED_DESCRIPTIVE | old_hgb | 2049 / 854 / 66 | 5.7331 | 5.6619 | 0.071197 |
| pass_cmp | B | website_week6 | SCORED_DESCRIPTIVE | website | 27 / 13 / 1 | 4.8755 | 4.5637 | 0.31183 |
| pass_att | A | pooled2022-2024 | SCORED_DESCRIPTIVE | old_hgb | 2049 / 854 / 66 | 8.4898 | 8.3809 | 0.10893 |
| pass_att | A | website_week6 | SCORED_DESCRIPTIVE | website | 27 / 13 / 1 | 7.8493 | 7.1459 | 0.70333 |
| pass_att | B | pooled2022-2024 | SCORED_DESCRIPTIVE | old_hgb | 2049 / 854 / 66 | 8.4898 | 8.3809 | 0.10893 |
| pass_att | B | website_week6 | SCORED_DESCRIPTIVE | website | 27 / 13 / 1 | 7.8493 | 7.1459 | 0.70333 |
| pass_int | A | pooled2022-2024 | SCORED_DESCRIPTIVE | old_hgb | 2049 / 854 / 66 | 0.68473 | 0.62323 | 0.061503 |
| pass_int | A | website_week6 | SCORED_DESCRIPTIVE | website | 27 / 13 / 1 | 0.61074 | 0.6637 | -0.052965 |
| pass_int | B | pooled2022-2024 | SCORED_DESCRIPTIVE | old_hgb | 2049 / 854 / 66 | 0.68473 | 0.62323 | 0.061503 |
| pass_int | B | website_week6 | SCORED_DESCRIPTIVE | website | 27 / 13 / 1 | 0.61074 | 0.6637 | -0.052965 |
| rush_yd | A | pooled2022-2024 | SCORED_DESCRIPTIVE | old_hgb | 4766 / 854 / 66 | 33.536 | 33.536 | 0 |
| rush_yd | A | website_week6 | SCORED_DESCRIPTIVE | website | 96 / 13 / 1 | 14.998 | 16.545 | -1.5465 |
| rush_yd | B | pooled2022-2024 | SCORED_DESCRIPTIVE | old_hgb | 4766 / 854 / 66 | 19.671 | 33.536 | -13.865 |
| rush_yd | B | website_week6 | SCORED_DESCRIPTIVE | website | 96 / 13 / 1 | 14.901 | 16.545 | -1.6435 |
| rush_att | A | pooled2022-2024 | SCORED_DESCRIPTIVE | old_hgb | 4766 / 854 / 66 | 3.6725 | 7.7415 | -4.069 |
| rush_att | A | website_week6 | SCORED_DESCRIPTIVE | website | 69 / 13 / 1 | 3.7734 | 3.4257 | 0.34775 |
| rush_att | B | pooled2022-2024 | SCORED_DESCRIPTIVE | old_hgb | 4766 / 854 / 66 | 3.6684 | 7.7415 | -4.0731 |
| rush_att | B | website_week6 | SCORED_DESCRIPTIVE | website | 69 / 13 / 1 | 3.7766 | 3.4257 | 0.35091 |
| rec | A | pooled2022-2024 | SCORED_DESCRIPTIVE | old_hgb | 15975 / 854 / 66 | 1.3406 | 1.3009 | 0.039746 |
| rec | A | website_week6 | SCORED_DESCRIPTIVE | website | 252 / 13 / 1 | 1.3459 | 1.2822 | 0.063746 |
| rec | B | pooled2022-2024 | SCORED_DESCRIPTIVE | old_hgb | 15975 / 854 / 66 | 1.345 | 1.3009 | 0.044127 |
| rec | B | website_week6 | SCORED_DESCRIPTIVE | website | 252 / 13 / 1 | 1.3355 | 1.2822 | 0.053302 |
| rec_yd | A | pooled2022-2024 | SCORED_DESCRIPTIVE | old_hgb | 15975 / 854 / 66 | 16.381 | 16.381 | 0 |
| rec_yd | A | website_week6 | SCORED_DESCRIPTIVE | website | 252 / 13 / 1 | 15.695 | 15.341 | 0.35427 |
| rec_yd | B | pooled2022-2024 | SCORED_DESCRIPTIVE | old_hgb | 15975 / 854 / 66 | 16.384 | 16.381 | 0.0027749 |
| rec_yd | B | website_week6 | SCORED_DESCRIPTIVE | website | 252 / 13 / 1 | 15.646 | 15.341 | 0.30501 |
| rush_rec_yd | A | pooled2022-2024 | SCORED_DESCRIPTIVE | old_hgb | 15975 / 854 / 66 | 20.918 | 20.918 | 0 |
| rush_rec_yd | A | website_week6 | SCORED_DESCRIPTIVE | website | 189 / 13 / 1 | 20.629 | 19.868 | 0.76092 |
| rush_rec_yd | B | pooled2022-2024 | SCORED_DESCRIPTIVE | old_hgb | 15975 / 854 / 66 | 20.939 | 20.918 | 0.020627 |
| rush_rec_yd | B | website_week6 | SCORED_DESCRIPTIVE | website | 189 / 13 / 1 | 20.525 | 19.868 | 0.65706 |
| fantasy_ppr | A | pooled2022-2024 | BLOCKED_CATEGORY_CONTRACT | — | — / — / — | — | — | — |
| fantasy_ppr | A | website_week6 | BLOCKED_CATEGORY_CONTRACT | — | — / — / — | — | — | — |
| fantasy_ppr | B | pooled2022-2024 | BLOCKED_CATEGORY_CONTRACT | — | — / — / — | — | — | — |
| fantasy_ppr | B | website_week6 | BLOCKED_CATEGORY_CONTRACT | — | — / — / — | — | — | — |
| anytime_td | A | pooled2022-2024 | SCORED_DESCRIPTIVE | old_hgb | 15975 / 854 / 66 | 0.14334 | 0.14334 | 0 |
| anytime_td | A | website_week6 | SCORED_DESCRIPTIVE | website | 243 / 13 / 1 | 0.14139 | 0.14586 | -0.0044709 |
| anytime_td | B | pooled2022-2024 | SCORED_DESCRIPTIVE | old_hgb | 15975 / 854 / 66 | 0.14327 | 0.14334 | -6.8048e-05 |
| anytime_td | B | website_week6 | SCORED_DESCRIPTIVE | website | 243 / 13 / 1 | 0.1415 | 0.14586 | -0.0043636 |

## Coverage and secondary comparisons

JSON retains all96 package statuses, all saved comparator-specific losses, primary-role and all-offered views, common-all-controls diagnostics, MSE/RMSE/bias/p95 tails, coarse groups and coherence summaries. Aliases are reused forecasts; blocked PPR and failures remain visible.

- The new learner procedures use exactly the parent HGB NFL-only source packet. Older CDF/recent/pooled comparators retain separate source-change qualification and contradiction quarantines.
- All 2019-2025 and 2026 Week6 periods and source coverage are exposed. Current-vintage postgame reconstruction and assumed seven-day availability do not authenticate original publication, correction order or original SITE input vintage.
- Historical primary losses pool exact 2022-2024 paired rows in unchanged category primary_roles against frozen old HGB base. The mandatory all-offered view is secondary. Week6 primary is all original offers against literal SITE. Each comparator keeps its own exact cohort; common-all-controls diagnostics are separate.
- All 96 packages remain: 48 new model packages, 40 byte aliases and 8 blocked exact-PPR packages. At most136 new estimator attempts are permitted. Aliases are reused forecasts and are not new fits or independent validation. No context panel, blend, new feature or winning variant is selected.
- A changes six counts from L1/identity/clamp to Poisson loss/log link together. B versus A changes role partitioning including training medians and vocabulary. Passing yards A/B are unchanged old HGB forecast bytes and contribute zero new research gain. Full-training role/global priors and cold/nonmodeled routing remain fixed. All-zero counts and single-class binary groups use priors without pseudolabels.
- Numeric outputs remain point heuristics without a numeric predictive-law or conditional-mean accuracy claim. Only anytimeTD supplies a genuine event probability; logloss is not clipped. Unknown participation, played zeros, played missing statistics and all blocked offers remain explicit.
- Saved historical week/game intervals use500 fixed-seed replicates and are nominal95%, unadjusted and descriptive. Week6 has no intervals. No significance, untouched confirmation, prospective qualification or promotion follows.
- Coherence diagnostics use only common available completion/attempt or direct-combined/component forecasts. They do not create a summed candidate, new outcome score, joint law or borrowed performance gain.
- This exporter copies explicitly allowlisted aggregate metadata only. It does not import estimators, open row or model artifacts, fit, forecast, score, resample, replay or select results. Existing rec-half/H3/RB evidence and spent budgets remain unchanged.

The original study remains INCOMPLETE_RETAINED_NO_RESTART after 136 fits and one failed, consumed reporting phase. Its registry, forecast freeze and failed completion remain pinned.
A separately registered repair reuses the original frozen forecasts and report definitions. It consumes one additional reporting/scoring phase: two cumulative phases, zero new fits, predictions or independent observations. Successful repair reporting does not make the original attempt successful.
Original registered budgets below are historical settings, including one original score pass. They do not replace the cumulative two consumed reporting/scoring phases.
