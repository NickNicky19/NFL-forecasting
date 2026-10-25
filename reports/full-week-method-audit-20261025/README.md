# Full-week NFL forecasting-method audit

## What this audit can establish

This is an audit of the week's retained research, implementations, configurations and published aggregate results. New experiments were paused at the owner's request. No model was trained, NFL outcome row was opened, forecast was issued, or website was changed for this audit.

**There is no evidence-qualified universal winner for every category. There are identifiable lowest observed losses within specific tested populations and forecast products.** Those rankings are the useful result below. They do not establish that a selected historical minimum will have the lowest future error.

The current website's “selected forecasts — provisional” label describes its operational selection. “New forecasts: biggest gap” orders the difference between a point projection and a displayed line. Neither label is proof of superior accuracy, a calibrated chance of beating the line, or a complete search of forecasting methods.

## Main comparable historical panel

The principal source-matched panel is regular-season **2022–2024, 815 games and 54 season-week blocks**. Models train on earlier seasons starting in 2019, with earlier-only preprocessing and source-availability checks. All evaluation periods have been exposed to research. Historical contemporaneous SITE/R0/raw-provider forecasts are unavailable for this panel.

| Population | Offered player-games | Supported scored outcomes | Unknown participation | Played, label missing |
|---|---:|---:|---:|---:|
| QB passing targets | 4,091 | 1,960 | 2,131 | 0 |
| RB rushing targets | 6,235 | 4,558 | 1,665 | 12 |
| RB/WR/TE receiving, combined and TD | 21,504 | 15,251 | 6,229 | 24 |

These populations overlap. Do not add category or method rows as independent football observations. The later 2023–2024 TD/joint panels, all-role panels, postseason panels and original 2026 Week 6 comparisons retain separate denominators.

## Lowest observed point losses: named comparable set

Counts follow the website's intended **mean/MSE** product; signed yards use **point MAE**; anytime TD uses **Brier** for an actual played-conditional probability. Arithmetic blends are identified explicitly. A point with a lower MAE is not automatically the median of a valid full forecast law.

| Category | Lowest fixed method with the stated current product | Historical loss | Lower recorded blend/policy/legacy point, where applicable |
|---|---|---:|---|
| Passing yards | Empirical leaf-CDF lower median | MAE **66.16173469 yd** | P4 point blend **66.12044852**; no mixture-median claim |
| Passing TDs | CDF-response forest mean | MSE **1.061974501** | None lower in the named set |
| Completions | Empirical leaf-CDF mean | MSE **51.37535676** | None lower in the named set |
| Passing attempts | CDF-response forest mean | MSE **113.90073106** | P4 mean-objective blend **113.87577075**; original member fallback semantics retained |
| Interceptions thrown | CDF-response forest mean | MSE **0.677566428** | None lower in the named set; full-law CRPS favors the leaf CDF |
| Rushing yards | Empirical leaf-CDF lower median | MAE **19.71895568 yd** | None lower in the named set |
| Rushing attempts | CatBoost medium intended mean | MSE **24.04640959** | P4 legacy point blend **23.94856377**; old Count A **24.02464184** |
| Receptions | Count A with corrected mean fallback | MSE **3.254146452** | Old Count A point **3.243919170**; different fallback procedure |
| Receiving yards | CatBoost medium median-objective point | MAE **16.34339800 yd** | P4 point blend **16.34294697**; no mixture-median claim |
| Rushing + receiving yards | CatBoost medium direct-total point | MAE **20.98392514 yd** | P4 point blend **20.96611282**; no mixture-median claim |
| Exact website offensive PPR | No qualified broad label panel | **N/A** | No invented proxy winner |
| Anytime rushing-or-receiving TD | Equal CDF/CatBoost probability blend, P4 family | Brier **0.140647014** | Same family as the current startup blend, not a new alternative |

“Lowest” is conditional on the named inspected set and the exact panel/product. It is not a claim of statistical separation from every alternative, a new selection decision, or a live-website win. Corrected mean versions and legacy point recipes remain separately ranked; the old count fallback defect is not repaired retrospectively.

## What the leading methods actually do

### Empirical leaf CDF

The model partitions earlier player-games with **32 ExtraTrees, depth 8, minimum leaf 30, seed 1701**. It retains the observed outcome distribution in each selected leaf and averages across trees. The resulting law is mixed with **5% training-only position/global support prior**:

`F(y | x) = 0.95 × average_tree_leaf_CDF(y | x) + 0.05 × F_prior(y)`.

The yardage output is the lower median of that law; count means are calculated separately. The priors preserve nonnegative integer count support, signed integer yardage and actual Bernoulli events. The strong results are observed comparisons, not proof that a particular feature caused the advantage.

### CDF-response forest

This uses the same fixed 32-tree/depth-8/minimum-leaf-30 topology, but changes splitting responses to a fixed weighted vector of `1[outcome <= threshold]`. Leaves retain actual outcome values and the same support prior. It is a distribution-sensitive approximation, **not the exact DRF/MMD library**.

It has the lowest inspected passing-TD/interception fixed mean MSE and passing-attempt fixed mean MSE. Gains are small. For example, passing-TD MSE improves **0.58668% versus CDF**, but only **0.03538% versus the stronger context correction**, with worse bias and intervals including zero against that stronger control. Interception mean MSE improves while its full-distribution CRPS slightly worsens.

### CatBoost medium

The fixed recipe uses **128 iterations, depth 5, learning rate 0.05, L2 10, seed 1753**, CPU, no bootstrap, no early stopping or evaluation-year tuning. Signed-yard points use the 0.5 quantile objective; count points use the Poisson objective; touchdown probabilities use binary log loss. A Poisson training objective does not authenticate a Poisson predictive law.

Its direct receiving and combined-yard points are strong fixed references. Its carry mean is below corrected Count A's mean on the named panel. This does not convert that comparison into a win against the exact old Count A forecasts currently served.

### Count A and the fallback correction

Count A uses a Poisson-objective histogram booster: **150 iterations, learning rate 0.05, depth 3, maximum 15 leaves, minimum leaf 30, L2 10, seed 1702**. The fallback correction uses the stored training prior **mean**, rather than its median, for the expected-mean product. Original frozen points and their errors remain intact.

V2 separately refitted eighteen Count A calls under the same registered estimator specification. It did not edit or reuse frozen fitted weights to manufacture a corrected historical result.

Legacy and corrected results differ. Carry MSE changes **24.02464184 → 24.29695554**; reception MSE changes **3.243919170 → 3.254146452**. Thus a correctness repair is not automatically an accuracy improvement. Among the inspected fixed corrected mean procedures, CatBoost medium leads carries and Count A leads receptions.

### P4 blends and weekly selectors

P4 freezes equal weights over the registered shortlist, with reference fallback for missing members. It is not an after-the-fact weekly oracle. Arithmetic count means can be combined as mean-objective points; arithmetic yard medians are point heuristics, not the median of the full-CDF mixture.

For anytime TD the shortlist is exactly CDF and CatBoost medium, so `p = 0.5*pCDF + 0.5*pCat` is the same procedure family as the website's startup blend. The 2022–2024 P4 result cannot be compared with a 2023–2024 half-blend result as if they were competing models.

P1 chooses the previous eligible week's winner; P2 uses cumulative earlier evidence; P3 chooses recency settings only in earlier inner folds. Their complete historical sequences are retained. Lower observed loss after comparing policies is subject to selection uncertainty.

## Data, information and preprocessing

The later permitted-source studies rebuild from retained NFL statistics, weekly rosters, schedules and identity metadata. The shared matrix has 97 feature columns; each category uses its declared base subset, rather than necessarily all 97. Features include prior three/eight-slot production and exposure summaries, support counts and pooled efficiency ratios. Training-only imputation, missing indicators and position encoding are frozen with the model.

Some separate context experiments also use earlier team/opponent statistics, schedule rest and opponent-adjusted residual summaries. The base-panel winning results do not establish incremental value for those context inputs. The broader NGS ablation produced three small gains and eight losses; the scheme/pace block worsened all eleven supported targets.

The permitted operational lane excludes unresolved PFR snap-derived data. Snap summaries are missing/disabled, and the unqualified participation-rate feature is masked. Positive physical-event evidence can establish participation, but does not recover every genuine zero-touch appearance. Unknown participation and missing fields remain unknown.

Historical availability is a disclosed **kickoff plus seven days reconstruction**, unless an actual clock is supported. The chronology repair admits records by availability and then orders games by game time. It does not authenticate publication times or eliminate the seven-day assumption. Current-vintage revisions and reconstructed rosters remain limitations.

These winning historical recipes are **not demonstrated news-reading, injury-adapting or weather-aware systems**. Factual context intake and FTN/NGS/weather proposals remain distinct from measured incremental forecasting gains.

## Earlier findings remain separate

- The SITE-held H3 passing-yard reconstruction is `original_SITE_attempts × sum(H3 passing_yards)/sum(H3 attempts)`, with exactly three qualified prior appearances and unchanged website fallback. Its original-week MAE was **45.2056 versus old SITE 56.6230**, but underprediction worsened. Original executable/history/row recovery is incomplete; no original reproduction or new current-site confirmation is claimed.
- H3 completions, original passing-attempt fits, receiving-yard target×YPT reconstruction and the combined component-sum test retain their mixed results and exact denominators. Improvements do not transfer between targets.
- The registered `rec-half-adjustment-v1` remains `raw + 0.5*(adjusted-raw)` in its original Weeks 7–14 window. It is not the anytime-TD blend and has no recovered prospective win here.
- The original five-prior-season RB carry-share proposal remains distinct from the generic dynamic workload study. The latter's final carry/reception/receiving-yard comparisons lost their CDF controls; auxiliary target improvement did not transfer to those props.
- The independent and Gaussian-copula combined-yard sum laws lost direct CDF distribution scores and the stronger CatBoost point reference. Simulated draws add no NFL observations.
- Four fixed calibration recipes on two TD bases all worsened pooled Brier. The separate conformal interval study selected zero widening throughout; it changed neither point forecasts nor full probability accuracy.
- NGBoost has **zero completed NFL fits** in the retained record. Native synthetic cases and law checks are software evidence. The new six-fit preparation was paused and remains inert. Exact DRF/MMD, XGBoostLSS, broad learned full-CDF stacking, AdaBoost and qualified role/news/market additions are not completed gains.

## What is actually best supported for release

The website's startup families are CDF for the five passing categories/rushing yards; Count A for carries/receptions; CatBoost medium for receiving/combined yards; and equal CDF/CatBoost for anytime TD. Exact PPR retains its reference.

Some alternatives have smaller historical losses. They have not all completed current-source future inference, artifact restoration, capture and consumer checks. The served Count A version and the later corrected producer must retain different identities. A successful producer export is not proof that its forecasts reached the website.

This audit does not select, promote or deploy a replacement. It does not impose an old eight-week gate on provisional releases. Original scientific registrations keep their original requirements. New experiments remain paused for the owner's review of this audit.

## Limits of the audit

The original public reports contain detailed aggregate results, formulas, parameter settings, source identities and failures. Their private NFL rows, trained artifacts and full source history were not re-read or re-trained for this audit. Aggregate agreement does not recreate missing originals, authenticate upstream publication times, prove complete participation coverage or establish future superiority.

The full-week index and per-category supporting tables accompany this report. Any lowest-error claim must retain its output, population, source version, period, fallback and comparator. No category is called globally optimal, scientifically confirmed or guaranteed to beat the next game's result.

These are marginal forecasts. Choosing separate category champions does not by itself create a coherent joint game, combined-yard or PPR distribution. Means add under compatible definitions; medians generally do not. A point-error improvement also does not establish better over/under probabilities.

## Complete audit materials

- [Machine-readable twelve-category ranking](CATEGORY_RANKINGS.json).
- [Forty-one method families, recipes, statuses and exact native settings](METHOD_INVENTORY.json).
- [Five passing-category review and all named settings](PASSING.md).
- [Five rushing/receiving/combined-category review](SKILL.md).
- [Anytime-TD probability and exact-PPR review](PROBABILITY_PPR.md).
- [Source hashes and compressed evidence bundle identities](SOURCE_MANIFEST.json).
- Detailed published metric cells and paired comparisons remain available in the original reports identified by the [source manifest](SOURCE_MANIFEST.json) and the [complete research index](../RESEARCH_INDEX.md). The collated compressed audit bundles are retained locally and are **not included in this public publication**. Public plain-text reports preserve all headline findings and exact method settings. Learned bodies and private source locators are omitted; nonfinite losses retain explicit infinity states.

The category owners inspected published aggregates and source/configuration files. Their work does not replace independent replay from the private original NFL inputs and fitted artifacts. Those original inputs, weights and protected outcomes are not redistributed here.
