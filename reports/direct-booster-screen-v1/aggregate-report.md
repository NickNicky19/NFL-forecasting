# Six direct booster pipelines: exposed historical development

Same permitted features, populations and cutoffs as the source-matched controls.
Historical raw Sleeper and SITE forecasts are unavailable for this panel.
Positive improvement means lower error; it is not a change in hit rate.
The displayed minimum is selected from this screen, not independent confirmation.

| Target | Primary loss | Paired n / games / weeks | Lowest new loss (method) | CDF loss | Change vs CDF | Change vs role B |
|---|---|---|---|---|---|---|
| anytime_td | Brier | 15251 / 815 / 54 | 0.140763 (direct_catboost_medium) | 0.140969 | +0.15% | +0.57% |
| fantasy_ppr | Blocked exact labels | 0 | N/A | N/A | N/A | N/A |
| pass_att | MSE | 1960 / 815 / 54 | 115.625081 (direct_catboost_medium) | 114.206938 | -1.24% | +0.85% |
| pass_cmp | MSE | 1960 / 815 / 54 | 52.140033 (direct_lightgbm_medium) | 51.375357 | -1.49% | +0.39% |
| pass_int | MSE | 1960 / 815 / 54 | 0.679346 (direct_catboost_small) | 0.679066 | -0.04% | +1.82% |
| pass_td | MSE | 1960 / 815 / 54 | 1.071384 (direct_lightgbm_medium) | 1.068242 | -0.29% | +0.42% |
| pass_yd | MAE | 1960 / 815 / 54 | 66.602627 (direct_catboost_small) | 66.161735 | -0.67% | +0.91% |
| rec | MSE | 15251 / 815 / 54 | 3.267280 (direct_catboost_medium) | 3.268201 | +0.03% | +1.27% |
| rec_yd | MAE | 15251 / 815 / 54 | 16.343398 (direct_catboost_medium) | 16.372435 | +0.18% | +0.36% |
| rush_att | MSE | 4558 / 815 / 54 | 24.046410 (direct_catboost_medium) | 24.292747 | +1.01% | -0.04% |
| rush_rec_yd | MAE | 15251 / 815 / 54 | 20.983925 (direct_catboost_medium) | 21.025703 | +0.20% | +0.19% |
| rush_yd | MAE | 4558 / 815 / 54 | 19.826424 (direct_catboost_medium) | 19.718956 | -0.55% | +0.07% |

## All settings, including adverse results

Each row is pooled primary-role development on the exact paired cohort.
Count means use MSE and the CDF mean; signed-yard points use MAE and the CDF median; TD uses Brier.
The full JSON preserves annual/all-offered comparisons, secondary errors, bias, tails, fallback coverage, nominal uncertainty and every nomination failure.

| Target | Method | Candidate primary | CDF primary | Change vs CDF | Change vs role B | Research nomination |
|---|---|---|---|---|---|---|
| anytime_td | direct_lightgbm_small | 0.141080 | 0.140969 | -0.08% | +0.34% | NOT_NOMINATED |
| anytime_td | direct_lightgbm_medium | 0.141556 | 0.140969 | -0.42% | +0.01% | NOT_NOMINATED |
| anytime_td | direct_catboost_small | 0.141257 | 0.140969 | -0.20% | +0.22% | NOT_NOMINATED |
| anytime_td | direct_catboost_medium | 0.140763 | 0.140969 | +0.15% | +0.57% | NOT_NOMINATED |
| pass_att | direct_xgboost_small | 117.509428 | 114.206938 | -2.89% | -0.77% | NOT_NOMINATED |
| pass_att | direct_xgboost_medium | 117.584760 | 114.206938 | -2.96% | -0.83% | NOT_NOMINATED |
| pass_att | direct_lightgbm_small | 117.875303 | 114.206938 | -3.21% | -1.08% | NOT_NOMINATED |
| pass_att | direct_lightgbm_medium | 116.021324 | 114.206938 | -1.59% | +0.51% | NOT_NOMINATED |
| pass_att | direct_catboost_small | 124.661866 | 114.206938 | -9.15% | -6.90% | NOT_NOMINATED |
| pass_att | direct_catboost_medium | 115.625081 | 114.206938 | -1.24% | +0.85% | NOT_NOMINATED |
| pass_cmp | direct_xgboost_small | 53.319559 | 51.375357 | -3.78% | -1.87% | NOT_NOMINATED |
| pass_cmp | direct_xgboost_medium | 52.804827 | 51.375357 | -2.78% | -0.88% | NOT_NOMINATED |
| pass_cmp | direct_lightgbm_small | 53.312578 | 51.375357 | -3.77% | -1.85% | NOT_NOMINATED |
| pass_cmp | direct_lightgbm_medium | 52.140033 | 51.375357 | -1.49% | +0.39% | NOT_NOMINATED |
| pass_cmp | direct_catboost_small | 55.579189 | 51.375357 | -8.18% | -6.19% | NOT_NOMINATED |
| pass_cmp | direct_catboost_medium | 52.713483 | 51.375357 | -2.60% | -0.71% | NOT_NOMINATED |
| pass_int | direct_xgboost_small | 0.679743 | 0.679066 | -0.10% | +1.76% | NOT_NOMINATED |
| pass_int | direct_xgboost_medium | 0.691974 | 0.679066 | -1.90% | -0.01% | NOT_NOMINATED |
| pass_int | direct_lightgbm_small | 0.679930 | 0.679066 | -0.13% | +1.73% | NOT_NOMINATED |
| pass_int | direct_lightgbm_medium | 0.692501 | 0.679066 | -1.98% | -0.08% | NOT_NOMINATED |
| pass_int | direct_catboost_small | 0.679346 | 0.679066 | -0.04% | +1.82% | NOT_NOMINATED |
| pass_int | direct_catboost_medium | 0.701302 | 0.679066 | -3.27% | -1.35% | NOT_NOMINATED |
| pass_td | direct_xgboost_small | 1.082086 | 1.068242 | -1.30% | -0.58% | NOT_NOMINATED |
| pass_td | direct_xgboost_medium | 1.072022 | 1.068242 | -0.35% | +0.36% | NOT_NOMINATED |
| pass_td | direct_lightgbm_small | 1.082327 | 1.068242 | -1.32% | -0.60% | NOT_NOMINATED |
| pass_td | direct_lightgbm_medium | 1.071384 | 1.068242 | -0.29% | +0.42% | NOT_NOMINATED |
| pass_td | direct_catboost_small | 1.074031 | 1.068242 | -0.54% | +0.17% | NOT_NOMINATED |
| pass_td | direct_catboost_medium | 1.097868 | 1.068242 | -2.77% | -2.04% | NOT_NOMINATED |
| pass_yd | direct_xgboost_small | 71.032983 | 66.161735 | -7.36% | -5.68% | NOT_NOMINATED |
| pass_yd | direct_xgboost_medium | 68.013540 | 66.161735 | -2.80% | -1.19% | NOT_NOMINATED |
| pass_yd | direct_lightgbm_small | 66.651006 | 66.161735 | -0.74% | +0.84% | NOT_NOMINATED |
| pass_yd | direct_lightgbm_medium | 67.452809 | 66.161735 | -1.95% | -0.36% | NOT_NOMINATED |
| pass_yd | direct_catboost_small | 66.602627 | 66.161735 | -0.67% | +0.91% | NOT_NOMINATED |
| pass_yd | direct_catboost_medium | 66.624242 | 66.161735 | -0.70% | +0.87% | NOT_NOMINATED |
| rec | direct_xgboost_small | 3.401112 | 3.268201 | -4.07% | -2.77% | NOT_NOMINATED |
| rec | direct_xgboost_medium | 3.270269 | 3.268201 | -0.06% | +1.18% | NOT_NOMINATED |
| rec | direct_lightgbm_small | 3.401463 | 3.268201 | -4.08% | -2.79% | NOT_NOMINATED |
| rec | direct_lightgbm_medium | 3.270995 | 3.268201 | -0.09% | +1.16% | NOT_NOMINATED |
| rec | direct_catboost_small | 3.283222 | 3.268201 | -0.46% | +0.79% | NOT_NOMINATED |
| rec | direct_catboost_medium | 3.267280 | 3.268201 | +0.03% | +1.27% | NOT_NOMINATED |
| rec_yd | direct_xgboost_small | 17.887076 | 16.372435 | -9.25% | -9.06% | NOT_NOMINATED |
| rec_yd | direct_xgboost_medium | 16.850273 | 16.372435 | -2.92% | -2.73% | NOT_NOMINATED |
| rec_yd | direct_lightgbm_small | 16.548474 | 16.372435 | -1.08% | -0.89% | NOT_NOMINATED |
| rec_yd | direct_lightgbm_medium | 16.353213 | 16.372435 | +0.12% | +0.30% | NOT_NOMINATED |
| rec_yd | direct_catboost_small | 16.571636 | 16.372435 | -1.22% | -1.04% | NOT_NOMINATED |
| rec_yd | direct_catboost_medium | 16.343398 | 16.372435 | +0.18% | +0.36% | NOT_NOMINATED |
| rush_att | direct_xgboost_small | 28.445671 | 24.292747 | -17.10% | -18.34% | NOT_NOMINATED |
| rush_att | direct_xgboost_medium | 24.460642 | 24.292747 | -0.69% | -1.76% | NOT_NOMINATED |
| rush_att | direct_lightgbm_small | 27.033230 | 24.292747 | -11.28% | -12.47% | NOT_NOMINATED |
| rush_att | direct_lightgbm_medium | 24.286560 | 24.292747 | +0.03% | -1.04% | NOT_NOMINATED |
| rush_att | direct_catboost_small | 25.081258 | 24.292747 | -3.25% | -4.35% | NOT_NOMINATED |
| rush_att | direct_catboost_medium | 24.046410 | 24.292747 | +1.01% | -0.04% | NOT_NOMINATED |
| rush_rec_yd | direct_xgboost_small | 23.119308 | 21.025703 | -9.96% | -9.97% | NOT_NOMINATED |
| rush_rec_yd | direct_xgboost_medium | 21.527848 | 21.025703 | -2.39% | -2.40% | NOT_NOMINATED |
| rush_rec_yd | direct_lightgbm_small | 21.163628 | 21.025703 | -0.66% | -0.66% | NOT_NOMINATED |
| rush_rec_yd | direct_lightgbm_medium | 21.043062 | 21.025703 | -0.08% | -0.09% | NOT_NOMINATED |
| rush_rec_yd | direct_catboost_small | 21.247182 | 21.025703 | -1.05% | -1.06% | NOT_NOMINATED |
| rush_rec_yd | direct_catboost_medium | 20.983925 | 21.025703 | +0.20% | +0.19% | NOT_NOMINATED |
| rush_yd | direct_xgboost_small | 24.189541 | 19.718956 | -22.67% | -21.93% | NOT_NOMINATED |
| rush_yd | direct_xgboost_medium | 21.717077 | 19.718956 | -10.13% | -9.46% | NOT_NOMINATED |
| rush_yd | direct_lightgbm_small | 19.941910 | 19.718956 | -1.13% | -0.52% | NOT_NOMINATED |
| rush_yd | direct_lightgbm_medium | 19.830782 | 19.718956 | -0.57% | +0.04% | NOT_NOMINATED |
| rush_yd | direct_catboost_small | 19.969813 | 19.718956 | -1.27% | -0.66% | NOT_NOMINATED |
| rush_yd | direct_catboost_medium | 19.826424 | 19.718956 | -0.55% | +0.07% | NOT_NOMINATED |
