# Cached point-control comparison — October 25, 2026

Completed 132 pooled contrasts and 396 annual diagnostics over exposed REG 2022–2024. All comparisons retain the same primary-role offers, cutoffs, supported outcomes and forecast masks; every offered row has a finite forecast. No training, model decoding, inference or HTTP occurred. Exact PPR remains label-blocked.

Count products use mean-point MSE, signed yardage uses law-median versus direct median-objective point MAE, and anytime TD uses genuine probability Brier. Lower is better. Positive gain means lower error than the strongest of the six fixed direct settings; the control minimum is descriptive after inspecting this exposed panel.

| Target | Metric | Strongest fixed direct setting | Control loss | Monotone loss | Gain % | CDF-response loss | Gain % | Scored / offered |
|---|---|---|---:|---:|---:|---:|---:|---:|
| pass_yd | MAE | catboost_small | 66.602626936 | 66.951530612 | -0.5239 | 66.203061224 | +0.5999 | 1,960 / 4,091 |
| pass_td | MSE | lightgbm_medium | 1.071383549 | 1.078178688 | -0.6342 | 1.061974501 | +0.8782 | 1,960 / 4,091 |
| pass_cmp | MSE | lightgbm_medium | 52.140032615 | 53.378627249 | -2.3755 | 51.540210185 | +1.1504 | 1,960 / 4,091 |
| pass_att | MSE | catboost_medium | 115.625081415 | 116.878997784 | -1.0845 | 113.900731060 | +1.4913 | 1,960 / 4,091 |
| pass_int | MSE | catboost_small | 0.679346162 | 0.684108678 | -0.7010 | 0.677566428 | +0.2620 | 1,960 / 4,091 |
| rush_yd | MAE | catboost_medium | 19.826424397 | 20.403466433 | -2.9105 | 19.755375165 | +0.3584 | 4,558 / 6,235 |
| rush_att | MSE | catboost_medium | 24.046409593 | 25.197748399 | -4.7880 | 24.231383465 | -0.7692 | 4,558 / 6,235 |
| rec | MSE | catboost_medium | 3.267280487 | 3.343831564 | -2.3430 | 3.264021762 | +0.0997 | 15,251 / 21,504 |
| rec_yd | MAE | catboost_medium | 16.343397995 | 16.541538260 | -1.2124 | 16.357025769 | -0.0834 | 15,251 / 21,504 |
| rush_rec_yd | MAE | catboost_medium | 20.983925135 | 21.483509278 | -2.3808 | 21.009442004 | -0.1216 | 15,251 / 21,504 |
| anytime_td | brier | catboost_medium | 0.140763090 | 0.141226541 | -0.3292 | 0.140969236 | -0.1464 | 15,251 / 21,504 |

The CDF-response anytime-TD row is an exact fresh-CDF alias, not a newly fitted response model. The two recovered XGBoost TD procedures are explicitly named canonical-v2 derivatives in the full table; their original failed screen slots remain failed.

The monotone family is adverse against the strongest fixed direct setting in all eleven categories. Across all six settings it has 29 lower-loss and 37 adverse contrasts. The CDF-response family has seven lower-loss and four adverse strongest-control comparisons (including its unchanged TD alias); across all six settings it has 61 lower-loss and five adverse contrasts. No settings or annual cells were dropped.

Most nominal whole-week and whole-game intervals cross zero. CDF-response passing-TD MSE is 0.8782% lower than LightGBM medium; its week interval is below zero, but its game interval crosses zero and its absolute bias is worse. The seven lower point errors do not establish seven scientific wins. Reception MSE 3.264021762 beats the direct minimum 3.267280487 but remains worse than the already completed V2 corrected-mean Count A 3.254146452. The older Count A point result 3.24391917 retains its original procedure and is not substituted for the corrected-mean comparator.

The original V1 report invocation remains failed with zero completed contrasts and 2.517020678 CPU seconds consumed. This V2 technical continuation completed in 32.902081890 CPU seconds / 21.858440330 wall seconds; conservative combined RSS bound 241,897,472 bytes and retained payload 3,210,917 bytes. No budget was refunded.

These are exposed historical, paired point/probability comparisons. They establish no SITE/R0-relative gain, independent confirmation, deployment change or calibrated numeric law for direct point controls.

The full table preserves all 132 pooled comparisons, all three annual supporting losses per comparison, both paired interval views, bias, tails, fallback counts, source-procedure identity and coverage. The JSON aggregate retains all 396 annual diagnostic records.

Using the already reported V2 fresh CDF and corrected-mean Count A summaries as additional descriptive context, the CDF-response point loss is below every fixed reference in this combined set only for passing TDs, passing attempts and thrown interceptions. Passing-yard and completion/rushing-yard direct-booster gains still lose the stronger fresh CDF point; carries lose CatBoost medium; receptions lose corrected-mean Count A; receiving/combined yards and the unchanged TD alias lose CatBoost medium. This context adds no new paired test or confirmation.
