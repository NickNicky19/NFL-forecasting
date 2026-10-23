# Dynamic opportunity screen v1 — implementation draft, unregistered

This is a static design packet, not an acquisition, experiment registration,
fit, forecast, score or activation. Code/schema contracts were inspected at
`06e3f37e1eb25095bde93ae9fe51797270152dc6`. No football values, source bodies,
models or CAS objects were read/written; no tests or installs were run.

## What current inputs support

| Existing contract | Usable now | Limit retained |
| --- | --- | --- |
| `features.py:_lookup_windows` | Prior mean3/mean8 and valid-value counts; strict earlier availability | Slots are roster-eligible games, unknowns consume slots; current player grouping crosses team/season boundaries |
| `data.py:load_history`, `features.py:_team_table` | Recorded all-position rushing/pass totals aggregated before skill-position filtering | Recorded totals are not an independently certified complete team-credit panel |
| `features.py:build_features` | Player target/catch/carry histories, team recorded carry/pass mean3 | Team credited-target total is absent; attempts+carries is the disclosed proxy named `offense_plays`, not total plays/dropbacks |
| `permitted_source_features.py:qualify_history` | Physical-event-supported playing, explicit supported zeros and signed yards | ACT/INA, row existence and zero-only rows do not prove playing; unknowns remain; no complete played/DNP denominator |
| `operational-source-policy-v2.json` | Exact retained NFL statistics/roster/calendar source versions, identities and clock gates | Seven-day publication lag is reconstructed; news/injuries/routes/weather/NGS are outside this variant |
| Frozen source-matched CDF | Same-row count means, signed-yard medians, event probabilities; strong direct controls | No saved historical `rec_tgt` CDF; no authentic historical SITE/Sleeper panel |

Do not derive a team target total by adding the currently offered receivers,
normalize targets to attempts, or normalize conditional-on-playing CDF means
into a team allocation. Those means condition on different player events and do
not generally sum to an unconditional team workload.

## Smallest useful same-source experiment

First compare **conditional marginal share dynamics** with static shares and the
CDF. This can be implemented from the existing permitted packet after a finite
registration. It can discover a better conditional point forecast; it cannot
certify full participation, verified role changes or a coherent joint game law.
The original RB five-prior-season protocol and rec-half registration remain
untouched. This is a new recipe with its own version and exposure record.

### Population, source adapter and fixed volumes

- Keep every original offered player-game. Model official carries for RBs and
  auxiliary credited targets for RB/WR/TE; other roles retain their exact CDF
  category reference. Do not select only positive-touch or complete cases.
- Bind exact player/game/team/opponent/REG+OT identities and all original query
  cutoffs. Start a new team/season spell on an authenticated membership change.
  Ambiguous membership/identity quarantines the affected update; no current-team
  inference, name matching, injury or starter inference.
- A small separately versioned adapter builds **paired** `C_ig,T_g` records from
  qualified history, before position filtering. Carry `T_g` is the existing
  recorded all-position carry total. Target `T_g` must be newly derived from
  the same retained official all-position target credits, with explicit
  missingness, source coverage, duplicate/orphan and reconciliation receipts.
  This is a new feature version, not an already-existing team-target feature.
- If team-total completeness cannot be established, a recorded-credit proxy may
  be studied only under that explicit name. It cannot support an exhaustive
  NFL allocation claim. Nonfinite, negative, fractional or incompatible
  `C_ig > T_g` exposure blocks that update; never repair it by clipping.
- Hold volume fixed: `tau_rush` is the existing same-cutoff team carry mean3;
  `tau_target` is the separately derived recorded-target-total mean3. Missing
  volume falls back; supported zero stays zero. No new volume learner in this
  experiment. Target totals never equal attempts by construction.
- Use the latest eight eligible same-team/season **team-game slots**, bounded by
  cutoff. Unknown participation/count/total is a missing observation, not zero;
  it consumes time and propagates state uncertainty without a likelihood
  update. Do not seek older convenient nonzero games. A genuine short/cold
  history starts at the training-only role prior. Record every missing slot.

### Two process families, six fixed settings

For role `r`, estimate the earlier-training individual-player prior
`p0_r = sum(C_ig)/sum(T_g)` on the *same supported played player-games*.
Repeated team denominators define an individual-player share prior, not total
RB team share or independent team games. Missing/invalid global priors mean
CDF fallback. Beta components require an interior prior; an exact boundary
prior uses the declared CDF fallback, never an epsilon repair. All
priors/preprocessing use earlier data only.

The static control uses the same eight slots and candidate's strength `kappa`:
`p_static=(kappa*p0 + sum C)/(kappa + sum T)`. This keeps prior strength from
masquerading as a dynamic-model benefit.

**Smooth filter:** initialize `alpha=kappa*p0`, `beta=kappa*(1-p0)`. Before each
elapsed team-game slot decay deviations toward that prior with
`lambda=2^(-1/H)`. On a supported played paired observation update
`alpha+=C`, `beta+=T-C`; on missing observation do not update counts. Predict
`p=alpha/(alpha+beta)`. Exact zero team exposure adds no rate information and
remains a recorded valid zero-exposure observation.

**Change-point filter:** over the same eight slots, retain a Bayesian run-length
mixture. Before a slot, split each component into continuation mass `1-q` and
reset-to-prior mass `q`; continuing components apply the same H=8 decay
toward their prior. For a supported `C,T`, update weights with the exact
beta-binomial predictive mass and update component sufficient counts; for a
missing observation propagate/reset without a likelihood. Predict the mixture
mean share. At most nine run-length components exist; recompute from the fixed
eight-slot boundary rather than merge or optimize an unbounded history.

The finite settings are:

| Family | H | kappa | q |
| --- | --- | --- | --- |
| Smooth | 2 or 8 | 25 or 100 | 0 (four combinations) |
| Change-point | 8 | 100 | 1/16 or 1/4 (two combinations) |

Select one setting per workload task using only the declared earlier
chronological development losses. The change hazard is selected from earlier
data; posterior mixture weights come from the likelihood. They are **not**
verified injury probabilities, probabilities of playing, or labels such as
"replacement starter." Publish no unvalidated role-probability claim.

The point is `mu_C=tau*p`. It is a conditional expected-count model hypothesis.
A beta-binomial update is not proof of a calibrated full-game count law; do not
attach a numeric CDF or generate independent player counts claiming coherence.

### Separate opportunity and efficiency updates

The first comparison changes shares only; volume is identical across each
candidate/static pair. Auxiliary target error is scored separately.

For a bounded propagation check, hold efficiency fixed across the target
candidate and its matched static control: training-only role priors plus
pooled paired catches/targets and signed receiving-yards/targets from the
last eight same-spell slots, shrinkage strength 100 target exposures. Define
`catch_rate=(100*c0+sum catches)/(100+sum targets)` and
`YPT=(100*y0+sum signed receiving yards)/(100+sum targets)`; use only explicitly
supported compatible paired fields, and retain missing slots/counts in audit.
A supported zero-target prior with lateral receiving yards remains legal.
Catch-rate incompatibility blocks that rate adapter; signed yardage is not
clamped. No efficiency decay/window search or efficiency learner is fitted.

Compare `mu_rec=mu_target*catch_rate` as a count-mean hypothesis and
`point_rec_yd=mu_target*YPT` as a **prespecified MAE point heuristic**, not an
exact conditional median or football accounting identity. The latter preserves
signed output. Missing required identities, rates or volume retains the exact
original category CDF point, with a reason. Missing auxiliary-target baseline
is an auxiliary abstention, not an invented CDF forecast.

Report canonical receptions and receiving-yards errors directly on common
eligible rows. Better auxiliary target error does not establish either gain.
Later efficiency changes require a separate experiment holding opportunity
fixed; combining both improvements is another version.

## Chronology, finite budgets and comparisons

Proposed development: train only 2019, predict 2020; train 2019–2020, predict
2021. Six settings x two workload tasks x two blocks = **24 development cells**.
Select once per task by pooled MSE; ties: smooth before change-point, larger H,
then larger kappa, then smaller q. These are deliberate conservative tie rules,
not a post-result choice. Source predicates must exclude all other outcome
seasons before decoding statistics.

Freeze both selected recipes, then use fixed forward 2022/2023/2024 blocks,
with earlier-only annually refreshed priors and no reselection. Freeze all
same-year outputs before its labels can enter the next year's training; global
2022–2024 forecast freeze precedes evaluation losses. All these seasons are
already exposed research. This is new development reconstruction, never fresh
confirmation or original historical issuance. Do not read 2025/2026 here.

Proposed first-run ceiling: **600 wall/CPU seconds, 1 GiB combined RSS, two
threads, 600,000 forecast-row incidences, 32 MiB new retained CAS content under
the unchanged 512 MiB global cap, one actual invocation, no retries/HTTP/GPU**.
At most 24 development candidate cells, twelve final candidate packages
(carry, auxiliary targets, receptions, receiving yards x three years), twelve
matched static final controls and six auxiliary simple final controls: 54 new
forecast-package evaluations total. At most sixteen separately recorded
training-prior vector formations (all role estimates for a task/year together),
no gradient optimizer or further search. All new control/alias rows also count
against the forecast-row ceiling.
Per-package 20 wall/CPU ceilings and existing explicit-PID/PDEATHSIG/native-call
supervisor apply. If bounded admission/readiness fails, preserve the failure
and fallback; do not expand budgets after results. One future fictional new-
adapter/filter packet may be registered at 120 wall/CPU seconds, 512 MiB and
two threads; none has run. Exact code/data/environment and unused budget must
be registered and independently reviewed before any execution.

For each canonical target compare the frozen CDF appropriate point, count_A,
role_B, recent, pooled and matched static-share control on the exact same
population/cutoff. Auxiliary targets have recent/pooled and static controls;
its CDF/SITE/Sleeper comparator is N/A. Count primaries: MSE; receiving yards:
MAE point objective. Report MAE/RMSE/bias/p95/tails/coverage, informed and whole-
population results, every fallback, player/team/opponent slices, and supported
zeros/DNP/unknown separately. Reuse the existing shared scorer/paired reports,
with 500 PCG64 seed1703 whole-game/week **nominal development** diagnostics.
The retained CDF has its original feature representation; this screen does
not pretend to refit it with new sequence/share features. Matched static-share
controls isolate dynamics on the same paired information. A later bounded
CDF-with/without-new-features comparison separates representation from learner
changes before claiming that the structural learner is stronger.

No numeric CRPS/probability scores without a tested law. No row-independent
bootstrap, simulation-as-evidence, or pooled mixed-unit accuracy.

Suggested development-advance rule, to be fixed by the integrator before data:
>=2% primary gain against CDF and matched static control, equal all-offered
coverage, no >2% absolute-bias/p95 regression and no >5% annual primary
regression. Auxiliary-target advance uses both simple controls and cannot
promote canonical categories. A passing screen only nominates later research;
original category-specific confirmation/promotion gates remain unchanged.
A separately frozen future sample and operational qualification are still
required. Do not force either process family to win.

## Genuinely finite team allocation — separately gated extension

A real finite allocator needs certified all-position team credit totals,
complete cutoff-qualified membership with unresolved/outside-offer categories,
and an appropriate participation/role contract. The current sufficient-positive
panel does not identify unconditional participation or complete played zeros.
Independent per-player conditional means cannot supply that missing joint law.

After those contracts qualify, forecast one team count `N`; form nonnegative
shares with a softmax including **other/unresolved**; generate one shared
Dirichlet-multinomial allocation vector. Train concentration/share dynamics on
earlier complete or explicitly censored aggregate observations. Unknown
individual credits go into a documented unresolved aggregate only when the
certified residual is known; never turn an unknown into an individual zero.
Rushing includes all positions; credited targets use their own total, with
separate throws-without-credited-target handling if later coupled to attempts.
Do not sample independent player counts and call them a team allocation.

Participation mixtures must distinguish unconditional allocation from the
conditional-on-playing score population and apply the actual DNP/void contract.
Verified news can influence later learned transitions only after its timestamp,
identity and extraction/source contract qualifies. This packet invents no
injuries, starters, role labels, game scripts or private playbooks.

## All twelve downstream contracts

| Category | Consequence / next distinct test |
| --- | --- |
| pass_yd | Retain direct CDF/H3 references; later shared attempts/completions and signed credited gains need their own qualified process. No carry/target gain transfers. |
| pass_td | Later scoring-opportunity/conversion process and shared TD-completion events; goal-line primitives not supplied by this feature variant. |
| pass_cmp | Earlier count/rate labels permit a separate fixed-attempt rate test; a full mutually exclusive pass-event model needs joint opportunities. |
| pass_att | Recorded team attempts exist, but attempts+carries is not plays/dropbacks; QB availability/exposure allocation remains separate. |
| pass_int | Keep marginal count/probability evidence distinct; turnover-risk charting requires separate source/availability qualification. |
| rush_yd | Later carry-only versus efficiency-only signed-yard tests; retain lateral/zero-carry credit exceptions and score directly. |
| rush_att | Direct first modeled target is RB carries; other roles stay retained references. Original full RB protocol remains unchanged. |
| rec | Score target-volume propagation with fixed catch conversion; rec-half registration/window stays untouched. |
| rec_yd | Score fixed-YPT propagation separately as a point heuristic; source/history adapter and rare credit semantics still apply. |
| rush_rec_yd | Retain direct total control; later shared-role dependence test scores the sum itself. Component gains imply no combined gain. |
| exact PPR | Full versioned rare-component/conditional scoring labels remain required. A newly qualified subset may enable later direct/joint scoring; never fill unknowns to manufacture it. |
| anytime TD | Needs separately tested scoring opportunities or calibrated binary correction; these shares are not TD probabilities. Played-conditioning and participation remain distinct. |

## Dependencies recorded once

1. Existing same-source paired history and newly derived team-target feature
   need a versioned completeness/missingness/orphan adapter before the numerical
   screen. This is permitted implementation/qualification work after finite
   registration, not a request for paid data or new credentials.
2. The current panel does not close independent appearance, true-zero or full
   team/population participation. An FTN appearance witness plus absent raw
   statistics is **not zero**. A later exhaustive-event/PBP aggregate could
   establish narrow count-zero subsets only after complete-play, exact-crediting,
   identity, source-rights and availability qualification under its own source
   contract. Neither the current zero audit nor this draft authorizes that read.
3. Genuine joint allocation, verified-news transitions and live independent
   confirmation require their separate source/population/operational contracts.
   They do not block the clearly labelled same-source marginal screen or other
   independent categories. This design does not repeat the private-durability
   owner decision already documented by the integrator.
