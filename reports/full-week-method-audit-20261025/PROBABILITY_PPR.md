**Audit navigation:** [main conclusions](README.md) · [original public evidence sources](SOURCE_MANIFEST.json). Collated compressed audit bundles and internal intermediate files are retained locally and are not included in this public publication. Named source-file and bundle-part references in the narrative describe those retained records; original public reports provide the underlying published evidence.

# Full-week TD probability and exact-PPR audit

Date:2026-10-25. Independent aggregate/code/config audit; actual backend **UNATTESTED**. No NFL rows, protected outcomes, source values, model bodies, fitting, row scoring, HTTP, CAS writes, activation or ledger changes. All numerical statements below come from already published aggregates. This is an evidence/identity audit, not independent numerical reproduction.

## Conclusions

1. **Current equal CDF/Cat TD is already the historical P4 family.** P4's TD shortlist is exactly `LAB_CDF,CatMedium`; equal weights mean `.5*pCDF+.5*pCat`. Count A is included only for six count targets. The current startup name `TD_EQUAL_CDF_CAT`, the three-year P4 replay and the later fixed-half experiment are aliases of the same procedure family, with their own training/source/artifact vintage and period. P4 Brier0.140647 over2022–24 is not a new competitor beating fixed-half0.140753 over2023–24. Current freshly trained forecasts have no measured future/live loss here.
2. On the exact2023–24 primary-role blend/calibration panel, **learned shrunk weight is the lowest observed pooled Brier and NLL among those methods**, by a very small margin versus fixed half. Both blends have false advancement flags. Both worsen absolute bias versus CatMedium, lose2024 Brier to it, and their Cat paired intervals crosszero. This is not a replacement champion or prospective win.
3. The strongest fixed source-matched2022–24 TD pipeline is **CatBoost medium**, ahead of old/source-corrected leaf CDF, native HGB, role split, small/medium LightGBM/XGBoost, recent/pooled and the conservative offset corrections on pooled primary-role Brier and published NLL. P4/fixed-half has lower three-year Brier than either component. The P4 packet does not publish its NLL; its NLL must remain unavailable, rather than borrowing a different period or deriving it from Brier.
4. **All eight calibration/base combinations worsen pooled Brier and2024 Brier.** Fresh-CDF Platt/beta slightly improve pooled NLL versus their own CDF but still lose CatMedium. Fresh-CDF isotonic has **two genuine infinite log losses**, retained rather than clipped or dropped.
5. **Exact PPR has no qualified predictive winner.** The strict eighteen-component source contract qualifies zero complete labels in the published broad studies and Week6 bridge. The315 retained arithmetic checks test projection-component parity, not outcomes or forecast accuracy. Neither generic provider PPR, event-free subsets, sparse missing-as-zero, nor a linear sum of expected components supplies the missing proof.
6. Actual NFL NGBoost remains **0 fits/predictions/scores**. The paused sixfit preparation exceeded its elapsed cap928.976>900; its failure and old consumed runtime variants are retained. Synthetic NGBoost law checks are software evidence, not lost or measured NFL forecasts.

## Matched-panel rankings

Lower is better. Brier is squared probability error; NLL is natural-log loss. No cross-row/period/source-vintage minimum is called an overall champion. Complete annual tables, all losses, fallbacks and reliability bins are in `TD_TABLES.json`/CSV and `TD_DIAGNOSTICS.json`.

| Exact panel | Scored / offered | Lowest observed Brier | Lowest published NLL | Interpretation |
|---|---:|---|---|---|
| Source-matched REG2022–24, RB/WR/TE |15,251 /21,504|P4 equal CDF/Cat **0.14064701358764026**|CatMedium **0.4449614032367473** among methods with published NLL; P4 unavailable|Same current equal-blend family; no independent future qualification|
| Same panel, fixed individual models only |15,251 /21,504|CatMedium **0.14076308980223012**|CatMedium **0.4449614032367473**|Strongest fixed component/control|
| Same source, all offered roles REG2022–24 |17,478 /25,872|CatMedium **0.13759452454094528**|CatMedium **0.43831868729707973**|Different role population; no equal-half/P4 all-role score claimed|
| Blend/calibration REG2023–24, RB/WR/TE |10,157 /14,282|Shrunk blend **0.1407477673135858**|Shrunk blend **0.4444027028819286**|Current fixed-half0.14075272099675418 /0.4444184887625955; false advance|
| Same blend/calibration panel2023 only |5,062 /7,134|Fixed half **0.1386649426752947**|Fresh-CDF Platt **0.4399597680979197**|Annual best need not be pooled best|
| Same blend/calibration panel2024 only |5,095 /7,148|CatMedium **0.14279876741629124**|Shrunk blend **0.44833239990403767**|No metric switching: registered primary is Brier|
| Corrected V2 distribution experiment only, REG2022–24 RB/WR/TE |15,251 /21,504|LeafCDF/response-CDF alias **0.14096923634165753**|Same aliases **0.4456797468720882**|Threshold HGB loses0.1412265406915601 /0.44651911716151665|
| Original Week6 website/CDF panel |249 /288|Pure baseCDF **0.13675043594241**|Fixed SITE/baseCDF half **0.4327918684946487**|SITE Brier0.14240161044176705; one exposed week13games|
| Participation-requalified Week6 HGB/role/control panel |243 /288|Rematched old baseCDF **0.13992630975214546**|SameCDF **0.4413824273580256**|SITE0.1458637160493827 /0.46245612232807665; not the249-row panel|
| Permitted-source REG+POST2022–24, all roles |18,303 /27,128|Rematched old contextCDF **0.138095686255381**|SameCDF **0.43892752310520694**|Old HGB/role source repair comparisons;854games/66blocks|
| Same permitted-source panel, original primary roles |15,975 paired|Rematched old contextCDF **0.14118476090887017**|SameCDF **0.44529872508450224**|Full planned-offer count in original paired export is not primary-role n|
| Earlier original CDF REG+POST2022–24, all roles |18,585 /27,128|ContextCDF **0.13618571376884747**|SameCDF **0.43388439549960206**|Earlier participation/source rules; do not transfer wins to repaired source|
| Same original CDF panel, RB/WR/TE |16,246 /22,538|ContextCDF **0.1390386378559122**|SameCDF **0.4396727059678542**|Separate from18,303/15,975 and REG15,251 panels|
| Initial campaign development2022–23, REG+POST allskill |12,371 /18,128|Tree **0.13387364802403953**|Tree **0.42774466085216173**|Exposed development selection; not original website comparison|
| Initial campaign2024 validation, REG+POST allskill |6,214 /9,000|Tree **0.13611905337722574**|Tree **0.4307077438393224**|2024 is now exposed; old validation label does not restore untouched status|
| NGS/scheme ablation2023 allskill |6,173 /9,020|Base logistic **0.13216844363277802**|Base logistic **0.4230152205095557**|Both28-feature NGS and47-feature scheme TD arms worsen Brier/NLL|

Annual source-matched fixed-model minima:2022 CatMedium Brier0.14064812897967854/NLL0.4455236819335499;2023 HGB/CountA alias0.13870446459777808/0.4403166430321767;2024 CatMedium0.14279876741629124/0.44848513152039543. These annual fixed ranks exclude new OOF blend/calibration arms; the table above labels those separately. Weighted recomposition of complete public2023/24 fixed annual means reproduces CatMedium0.1408207456484522/0.4446794058279148, exactly its published two-year control. This recomposition opens no rows and creates no new scoring observations; cross-study identity rests on the published accepted query/control/source chain, not equal n alone.

## Current family, calibration and adverse diagnostics

The equal family has two components and no learned parameter. Current startup policy is the equal blend, while the separate P2 selector may later choose using eligible earlier graded evidence. This audit does not inspect live forecasts/grades or assert today's private selection. The root-supplied objective is beating the current selected product; comparison only against a weak pooled rate would not satisfy it.

For2023–24, CDF/Cat/fixed/learned respectively have probability-minus-event biases `.0072459151,.0040246173,.0056352662,.0055064055`; p95 absolute errors `.8189046948,.8265071832,.8219711170,.8218580225`. Thus mixtures improve the Cat tail while worsening its absolute bias. P4's three-year bias improves versusCDF `.0127810949→.010706`, but p95 worsens `.8174045775→.820439`. Neither secondary diagnostic is silently exchanged for Brier.

Fixed-minus-Cat pooled Brier95%CIs: week[-.0002523348823,.0001468442102], game[-.0002764701546,.0001267784244]. Learned-minus-Cat: week[-.0002429085045,.0001272396638], game[-.0002655738048,.0001088723775].500whole-cluster PCG64 replicates, seeds1931/1932, nominal linear percentiles; no refits, no selection-adjusted proof. Three-year P4-versusP0 CIs excludezero, week[-.0005292620242,-.0001316708592], game[-.0005331968221,-.0001023097343]; those are **versusCDF**, not versus the equal current family or strongest retrospectively selected control. P1–P3 intervals versusCDF crosszero. Replayseed1703,500replicates conditions on the frozen sequence.

Two-year offers/scored14,282/10,157 retain4,101unknowns,24played-missing,0DNP/invalid and366base-fallback offers.171fallback outcomes have identical Brier≈.1118070713 across both bases/both blends;9,986nonfallback rows contain gains and bias regression. All actual masks match; unequal forecast masks reject comparison rather than shrinking to a favorable intersection. Conditional-on-playing accuracy does not establish unconditional all-player probability or complete appearance coverage.

Fixed-tenth reliability is retained in the JSON. Low-probability tail counts(CDF/Cat/fixed/learned) are1,403/1,970/1,641/1,671; all have zero high-tail≥.9 rows. No empirical high-probability calibration claim is possible. Their discrete central80% coverages are.992517/.987004/.990844/.990647, with mean widths.861869/.806045/.838437/.835483. Bernoulli quantiles can overcover;≈99% coverage does not establish well-calibrated80% intervals. The Beta(1,1) rate's100% coverage/width1 is also not superior calibration.

### All fixed calibrators, pooled2023–24

| Base/method | Brier | NLL |
|---|---:|---:|
|CDF unchanged|.1410210129387159|.4451926082876003|
|CDF intercept|.14143708525332105|.4456044428406175|
|CDF Platt|.14113431916709832|.4448630425597884|
|CDF beta|.1411521588794799|.4448977852040011|
|CDF isotonic|.1414261642124032|**+infinity,2contrary outcomes**|
|Cat unchanged|.1408207456484522|.4446794058279148|
|Cat intercept|.14109417026779258|.4450659612914781|
|Cat Platt|.14102814459229784|.4449100977178659|
|Cat beta|.14102694883925135|.44490165764768996|
|Cat isotonic|.1411689364372822|.44568372731210837|
|Earlier-only Beta(1,1) rate|.1558285276544535|.49075734226452783|

There were16charged/calibrators fits, no basefit, no retry/tuning, no calibration fallback. The2019-based component forecasts are OOF by evaluation year.2022OOF labels fit2023;2022+23OOF fit2024. Supported played calibration labels require known availability strictly before first evaluation cutoff;200rows/30positives/30negatives otherwise unchanged-base fallback. All16models/allfuture forecasts freeze before evaluation scoring. Manifest hashes and paired adverse diagnostics are preserved in the `TD_DIAGNOSTICS.json` part. Learned coefficient/isotonic-knot bodies are omitted from this public bundle; the original source reports remain hash-bound.

## Exact formulas, features and source identity

`FORMULAS_AND_METHODS.json` contains exact native binary parameters for all six direct pipelines, all four calibration methods, all eighteen PPR inputs, and34base/56context TD feature names. The shared97-feature universe is not97features used by each TD learner.

- Original SITE: lambda is raw projected rushTD+recTD, rounded2dp; `p=round(1-exp(-max(lambda,0)),3)`. This is an assumed Poisson conversion. Native raw-provider event probability is unavailable; an expected count is not renamed a probability. The research adapter rejects missing/nonfinite/negative raw projected totals even though original presentation uses `projection or0`.
- Initial binary logistic:C=1/32,maxiter150,tol1e-5,seed1701; tree24ExtraTrees/depth6/minleaf30/maxfeatures.8. Training-only scaling/imputation/categories/missing flags. Original distributional/ridge labels can resolve to the same logistic binary family; workload→recent fallback is not another distinct mechanism.
- Recent3 and pooled8 are player-window event-rate controls shrunk toward training role/global rates with strengths3/5. They differ from the later global Beta(1,1) training-event control.
- LeafCDF32ExtraTrees/depth8/minleaf30/seed1701 uses actual0/1 leaf frequencies plus5%training role/global Beta(1,1) prior. FixedDesign training medians, explicit missing flags and roleonehots; cold/unseen/no-fit uses exact trainingprior. Binary HGB150 uses logloss,depth3,15leaves,minleaf30,L2=10,lr.05,seed1702,earlystopfalse. CountA TD is a byte alias; roleB fits separate fixed RB/WR/TE binary estimators.
- Direct CatMedium128trees/depth5/lr.05/L2=10/seed1753/Plain/No bootstrap/zero randomstrength/2threads; native Logloss. Small64/depth3. LGB small64/depth3/7leaves,medium128/depth5/31leaves,minchild30,L2=10,seed1752. XGB same64/128/depth3/5,minchildweight30,L2=10,seed1751,hist,binary:logistic,2threads. No earlystop/search. Six original XGB probability-validation failures and zero-fit canonicalization/reports remain separately named.
- New thresholdCDF binary arm is one native HGB60 classifier peryear,minleaf40,15leaves,L2=10,lr.05,seed1911 plus5%prior, not threshold-expanded count fitting. Distribution-response TD is exact leaf alias. Both are distinct from the150iteration HGB.
- Baseline offsets use `logit(newp)=logit(CDFp)+Xβ`,meanNLL+.5||β||² INCLUDING intercept,lambda1,oneL-BFGS-B100 attempt;2022 unchangedstartup,strictboundary0/1 fallback unchanged. Context uses fixed standardized opportunity trend/history/team opportunity+missingflags. It is not the later intercept-unpenalized calibration recipe.
- Calibration:intercept `c+logit(p)`;Platt `c+s logit(p),s≥0`;beta `c+a log(p)-b log(1-p),a,b≥0`;meanNLL+.01/2 slope distance fromidentity,interceptunpenalized,max200L-BFGS-B oneattempt. Logistic exactp0/1 invariance; contradictory training endpoints produce chargedfailure+basefallback. Isotonic uses all endpoints/PAVA; `out_of_bounds=clip` means constant monotone endpoint extension, not hidden probability clipping. Future contrary0/1 events have infinite logloss.
- Learned blend `w=clip((mean((y-pCat)*(pCDF-pCat))+.001*.5)/(mean((pCDF-pCat)^2)+.001),0,1)`;p=w pCDF+(1-w)pCat. No weight search. Only two scalarfits; values not re-estimated by this audit.

Source-matched methods use permitted NFL stats/rosters/schedules/identity, positive attributed physical events for supported participation, with snap means/play-rate unavailable under the source policy. PrimaryrolesRB/WR/TE are predeclared, not chosen by outcome. Training2019..year-1; known label availability strictly before first evaluation cutoff; recent features by game chronology. Current-vintage kickoff+7day availability is an assumption, not original upstream publication. CorrectedV2 excludes explicitly unknown availability, orders recency by kickoff, and masks `f_player_play_rate8` unavailable; approved97-column equality is separately recorded. Old unmasked output/source failures remain failed. Historical rawSleeper/SITE/R0 do not exist for the2022–24panel and are not reconstructed as authentic past live forecasts.

Weekly P0–P4 use week-choice before first kickoff−6h; replay label availability kickoff+48h and finality lastkickoff+12h are explicit additional reconstruction assumptions. They do not repair original weekly-publication/finality evidence. All2022–24andWeek6source lanes are exposed; none supplies new untouched confirmation or2025+protected outcomes.

## Exact PPR: function, coverage and blockers

Let g(C)=round2[.04passyd+4passTD−passINT+2pass2pt+.1rushyd+6rushTD+2rush2pt+rec+.1recyd+6recTD+2rec2pt−2fumlost+6STTD+STfumrec+STFF+6fumrecTD+2blockedkick−I(idpfumrec>0)*6fumrecTD]. `idp_fum_rec` is the eighteenth component, not an additive point term. Pinned original scoringSHA31672c10d526d591db8951157b0ecd669b4d02b412a75deec337618bff18dab2. HalfPPR subtracts.5receptions under its separately labeled product; missing-half display fixes do not qualify fullPPRlabels.

The research scorer requires all18valid explicit components with exactplayer/game/source identity. Signedyards allowed; observed event counts integer/nonnegative; no boolean/nonfinite inputs. Original website sparse defaults reproduce its function but do not prove omitted statistical events are zero. Generic `pts_ppr`/`fantasy_points_ppr` cannot bypass the requested g. The exception is nonlinear: score each joint draw then average. Two complete outcomes can score6and0(mean3), while scoring their meancomponents can yield0; no PPR mean/law is inferred from unrelated marginal means.

| Public source/measurement | Coverage | Exact qualified labels / scored predictions |
|---|---|---:|
|Modern2023weekly NFLverse offensive skillstat audit|6,173rows;12explicit common component mappings|0 /0|
|SavedWeek6Sleeper playedskill audit|369players;rare fields sparse;zero explicit-zero counts for each18component|0 /0|
|OriginalPPRoffer probe|396offers;364savedSleeper contexts;285exactweeklyidentity/team/opponent bindings|0 /0|
|Retained original projection parity|315/315arithmeticchecks|Not labels;0newpredictive scores|
|Broad exactPPR benchmark/booster/correction/replay|Original slots explicitlyblocked|0 /0|

Six unresolved rare bridges: STTD,STfumble recovery,STforcedfumble,fumble recoveryTD,blockedkick and defensivefumble-credit discriminator. All-phase fumbleloss deductions, lateral credited recipients, provider's individual-versus-team/defensive taxonomy and complete event inventory/sparse-zero convention are not established. PBP positive-event agreement/source schema does not prove exhaustive zero semantics; opponent recovery or playerposition does not authenticate the defensive-credit flag. The2023PBP coverage has49,665rows/285games and useful attribution checks; the later2026Week6probe2,538rows/14games does not add forecast validation or qualification. Current cached2022–24PBP acquisition/schema metadata elsewhere does not itself close GSIS/participant/credit/availability joins. No new acquisition was made in this audit.

The generator followup retained its own12requests/601,427bytes and191.93s bookkeeping breach of180s; source accessibility is not completed PPR research. Original exactPPRmodel attempts remain blocked rather than relabeled as tests. A complete provider credit/zero/identity bridge and predeclared eligible fullpopulation comparison are needed before claims; no favorable event-free subset or simplified proxy winner is nominated. PPR's R0 retention is a product boundary, not evidence that R0 is measured strongest.

## Captured lines, market work and remaining hypotheses

The saved threshold study has604provider-fed **numeric** thresholds(590DraftKings/ESPN,14SleeperPicks),585supported rows across13games/oneexposedweek. The288TD0.5references are internal event thresholds, not matched sportsbookquotes. TD/PPR each have zero captured marketthreshold comparisons. Original post-cutoff/upstream quote timestamps remain unverified. Point-over-line directions, prices/returns, Bernoulli event probabilities and expected TD counts are different products; no wagering/calibration edge follows.

No actual NGBoost NFL run, new calibration variants, market-informedTD, complete unconditional participation law, or exactPPRlearner/joint-law study is filled in as tested. Conformalnumeric80%study did not target binaryTD and blockedPPR. Hypothesis ideas are not observations. Families/aliases/repairs/failures, repeated annual outputs, bootstrapreplicates and future-training fits are not summed as independent NFL games. This audit does not activate or replace any method.

## Evidence files and limits

- `TD_TABLES.json`/CSV:351published/recomposed method-panel incidences, including losses; duplicate aliases retained as provenance, not new trials.
- `TD_RANKINGS.json`:separate panel minima; `PUBLIC_ANNUAL_RECOMPOSED` explicitly identifies aggregate-only arithmetic.
- `TD_DIAGNOSTICS.json`:published CIs/reliability/fallback/annual/adverse metrics; learned calibrator coefficient bodies omitted, original source reports retained; no private records.
- `FORMULAS_AND_METHODS.json`:exact formulas/nativeparameters/features/sourceversions/unrunstatus.
- `PPR_AUDIT.json`:18componentcontract, sourceaggregatecoverage andremainingbridges.
- `SOURCE_HASHES.json`:exact bodies read for source evidence. Public worktreeHEAD1cd36bea89c3b5284244c77910c303dd88c225b1 contained pre-existing staged publication changes; this audit did not edit it. Evidence is bound to individualfilehashes, not a falsely claimed cleanHEAD.

The audit did not independently replay private trained parameters, row identities, private labels or production issuance. That deliberate read boundary prevents declaring numerical implementation/actual backend attestation. Public metadata and narrative inconsistencies are recorded without altering old evidence. In particular, the blend README's old dynamic-V9/V10 checkpoint is stale and is not adopted as current campaign status. The main weekly/index snapshots predate the latest threshold/calibration/blend additions and cannot be treated as one uniformly current study census.
