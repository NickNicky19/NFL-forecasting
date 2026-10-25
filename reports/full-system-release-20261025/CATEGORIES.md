# Current category contract and release boundary

The current website still uses the older1,754-row selected feed from producer93e2019/run40135574441, with explicit R0 fallbacks. Corrected producer c748/run40203512153 has published1,620derived rows but is not installed on the website. This table identifies the original weekly selected choices retained by the correction, not a new football model search. All supported outputs remain provisional, not scientifically promoted.

| Category | Unit and target | Intended point functional / wire product | Selected procedure | New public rows |
|---|---|---|---|---:|
| Passing yards | Official credited passing yards; signed values allowed | Median / point_median | LAB_CDF | 33 |
| Passing TDs | Official passing-TD count | Mean / point_mean | LAB_CDF | 33 |
| Completions | Official completed-pass count | Mean / point_mean | LAB_CDF | 33 |
| Passing attempts | Official pass-attempt count, excluding sacks | Mean / point_mean | LAB_CDF | 33 |
| Interceptions | Official intercepted-pass count | Mean / point_mean | LAB_CDF | 33 |
| Rushing yards | Official rushing yards; signed values allowed | Median / point_median | LAB_CDF | 92 |
| Rushing attempts | Official rushing-attempt count | Mean / point_mean | COUNT_A, corrected mean-v2 fallback | 92 |
| Receptions | Official reception count | Mean / point_mean | COUNT_A, corrected mean-v2 fallback | 335 |
| Receiving yards | Official receiving yards; signed values allowed | Median / point_median | CATBOOST_MEDIUM | 335 |
| Rushing + receiving yards | Sum of the two official player-game yardage outcomes | Direct combined median / point_median | CATBOOST_MEDIUM | 241 |
| Exact website PPR | Exact enabled website fantasy scoring, including rare components/conditions | Label-blocked; explicit fallback | No selected exact-PPR model installed | 0 |
| Anytime rushing/receiving TD | Probability of at least one credited rushing or receiving TD; passing/return TDs do not establish the event | Probability in[0,1] / binary_probability | Fixed .5LAB_CDF + .5CATBOOST_MEDIUM probability blend | 360 |

Wire functional names are `intended_median`, `expected_mean` and `event_probability`. They identify the forecast product. A point training loss or an intended label alone does not establish a complete calibrated predictive distribution. MAE, squared error/RMSE and proper probability/distribution scores remain different contracts. A prop line alone is not a probability distribution, and combined medians are not added from marginal medians.

The declared target populations, modeled/primary roles, participation rules, game identity, original fixedR0 identity and source policy remain frozen in the qualified manifests/epoch. Known played zero, known DNP, unknown participation and missing labels remain distinct. Exact fantasy components that are not supported stay unavailable. Frozen started-game website rows retain their original issue; a later installation cannot rewrite them with a new forecast.

The new public feed's coverage is2,605private selected rows =1,620public rows +981outside-board R0 +4private-ineligible R0. The website must additionally apply its own exact identity, started-game, expiry, missing/duplicate offer and product rules. Those producer counters are not a claim about the website's eventual fallback counts. Actual new-feed display and grading traces remain pending integration; the earlier live old-feed/browser/94arithmetic/62settlement evidence is retained separately.

The COUNT correction uses the independently derived geometric prior mean. ForP(N=n)=(1-q)q^n on nonnegative integers, E[N]=q/(1-q). Atq=.4, the mean is2/3 while the smallest median is0; atq=.75, the mean is3 while that median is2. Returning the median from a mean product was incorrect. The repair changes the fallback calculation and effective manifests, retains original trained warm predictions bit for bit, and passed14independent fallback probes without fitting new NFL models.

Anonymous TLS checks on the actual corrected public body verify finite values, nonnegative count means, bounded probabilities, all11wire contracts, and33paired passing opportunities with completion mean≤attempt mean, TD mean≤completion mean and completion mean+interception mean≤attempt mean. Passing TDs are not added again to completions. No simplified rushing/QB/team scoring identity is imposed across official statistical-crediting exceptions. These finite constraints do not prove a calibrated joint passing law, tail accuracy, dependence, an optimal predictor, protected-outcome accuracy or an actual website installation.

Full historical private prediction/OOF/calibration/label panels needed to reproduce every published accuracy claim are not in the recovered model/capture scope. Public aggregate consistency and software tests do not replace those panels. Protected confirmation outcomes were not opened for tuning, no historical website forecasts were invented, and no accuracy gain is claimed.
