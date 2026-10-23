# NFL forecasting research lab

This repository runs NFL research and pregame shadow forecasts. Its candidates
are unqualified until the registered validation and later confirmation gates
pass. The production website is a pinned read-only reference; its owner decides
integration. No paid feeds, odds keys, LLM API calls or website writes are used.

Read [START_HERE.md](START_HERE.md), [EXECUTION_SPEC.md](EXECUTION_SPEC.md),
[the registration](config/research.json), and [the execution ledger](execution/ledger.jsonl).
The attached review package and raw source bodies are kept outside public Git.

For the full recorded research history, formulas, data versions, gains, losses
and missing/private artifacts, start with the [research index](reports/RESEARCH_INDEX.md).

The owner adopted the [ongoing operating goal](RESEARCH_GOAL.txt) on 2026-10-23.
It covers cross-season learning, qualified news, bounded recovery and per-category
release readiness. The longer [goal proposal](GOAL_PROPOSAL_2026-10-23.txt) remains
background rationale; frozen registrations and website release ownership remain in force.

Latest bounded research: [role and count comparison](reports/role-count-boosting-v1/README.md) completes 136 estimator fits, 88 supported forecast packages and all 48 primary slots, including four exact-PPR blocks. Both prespecified arms improve five Week 6 primary errors and worsen six against the saved website. Historical carry improvements repair an earlier failed model but still lose stronger controls. The original reporting failure and separate zero-fit recovery remain recorded. [Current twelve-category state](reports/role-count-boosting-v1/category-status.json). No candidate is promoted.

Earlier bounded research: [recorded player-prop threshold comparison](reports/recorded-thresholds-v1/README.md) reuses thirteen fixed point variants on585 supported rows from604 original provider-fed lines. All twelve categories remain explicit and unqualified; directions are descriptive and numeric over/under probabilities remain unavailable.

Current implementation packet: [H3 point recording contract](reports/h3-recording-contract-v1/README.md) addresses accurate forecast semantics through the existing lab writer. Current website main still uses the original comparison's source formulas. This packet adds no football observations, live hook, activation or qualified replacement.

Earlier bounded research: [fixed boosting and permitted-source comparison](reports/median-boosting-v1/README.md) completes88 fits across eleven supported categories, retains exact PPR as blocked, and preserves every mixed or failed result. No candidate is promoted; numeric stat-total error does not establish over/under probability accuracy.

Earlier bounded research: [direct original-website CDF comparison](reports/website-direct-leaf-cdf-v1/README.md) covers all twelve categories, with eleven scored and exact PPR blocked. Both fixed panels and website blends are retained. The exposed single-week gains are descriptive; no replacement is promoted.

Current evidence: [category status](reports/lab-status.json),
[historical comparisons](reports/initial-campaign/README.md), and
[hosted verification](reports/hosted-verification.json). Hosted capture, retries
and bounded training have succeeded. An actual delayed scheduled delivery safely
skipped issuance; on-time morning delivery remains unverified. No future
confirmation outcome or qualified winner is claimed.

The [matched website comparison](reports/archive-source-coverage-v1/README.md)
has mixed results after expanded verified outcome coverage: four category losses
improve and six worsen. This exposed single-week study is descriptive and has a
retained cold-context protocol deviation. The separate
[public scheme ablation](reports/public-scheme-study/README.md) worsened every
tested primary loss and remains inactive. New website comparisons use
[hash-bound pregame capture](docs/website-baseline-comparisons.md), without
backfilling old forecasts.

The [resumed methods work](reports/methods-resumption-20261022/README.md) adds
a bounded historical passing-efficiency comparison and a portable
[opt-in passing-yard adapter](docs/research-passing.md). It matches the prior
37 saved opportunity points technically, including fallbacks. The larger
historical comparison favors the pooled-yard control over both efficiency
variants. Neither result changes a default or qualifies a website replacement.

The [archived website scorecard](reports/methods-resumption-20261022/website-comparison.md)
shows six lower and five higher primary errors across the fixed indexed
candidates; exact PPR lacks a qualified outcome comparison. A subsequent
[RB rushing-efficiency test](reports/rushing-efficiency-v1/README.md) scores
4,591 appearances across 54 season-weeks: H8 gains 0.82% against the pooled
control, with worse bias and uncertainty spanning zero. It adds no new
website-relative gain or default replacement.

```sh
python -m venv .venv
.venv/bin/python -m pip install -r requirements.lock -e '.[test]'
.venv/bin/python -m pytest -q
.venv/bin/python -m nfl_lab.cli acquire
.venv/bin/python -m nfl_lab.cli experiment
.venv/bin/python -m nfl_lab.cli daily
.venv/bin/python -m nfl_lab.cli replay
```

One loader and feature builder serve all twelve targets. Player identities use
GSIS; unlinked live players retain an explicit Sleeper namespace and cold-start
fallback rather than disappearing. Historical population uses weekly skill
rosters plus observed participants; missing box scores do not establish DNP.
Scores distinguish played zero, missing statistics, DNP, and unknown participation.

The historical campaign uses expanding-season fits, development2022–23 and
validation2024. Features use earlier available observations; the assumed seven-day
historical availability lag is not proof of authentic pregame data.2025 is
already exposed. New confirmation is prospective only,2026 Week8 onward; the
frozen receptions experiment keeps its separate original Weeks7–14 window.
No tiny-sample result or replay qualifies a model for promotion.

The single [Actions workflow](.github/workflows/lab.yml) targets08:36 Chicago,
with a Sunday bounded training campaign. Standard public-repository runners
provide the intended no-additional-cost execution. Jobs do not call the website
updater. Actual schedule execution, hosted runs, publication and future grading
have separate evidence states in the ledger; installed YAML alone proves none.
Delays outside the morning window skip issuance, and every forecast is checked
against its actual kickoff. No historical forecast is backdated.

Only this lab's derived forecasts, correction observations, hashes and publication
receipts enter the `lab-state` branch. Raw input caches and detailed historical
rows remain ignored locally. Health artifacts expire after14 days. Derived state
has a200MiB cap that stops writes while preserving evidence; jobs have bounded
HTTP retries, timeouts, compute and one writer. An owner storage decision is
needed if evidence reaches that cap. No separate ChatGPT scheduler is installed.

To stop new lab issuance, disable this repository's `NFL research lab` workflow.
To roll back code, revert the relevant lab commit and rerun acceptance tests.
Retain `lab-state` and all old experiment IDs; do not reset or edit frozen records.
Restore a prior candidate config only under a new model version. No production
website rollback is needed because this lab never deploys it. A read-only lookup
found the old external NFL research task already disabled; this lab did not change
it. Frozen experiment ownership is preserved separately.

The interface exports player/game/team/opponent/target, full-game period and
scoring identity, model/config/code/input hashes, kickoff and issue clocks,
conditional played mean/distribution, participation probability, and fallback.
Recorded source publication clocks remain unknown where the provider does not
supply them. Compatible component means add; quantiles require joint samples.
New scalar shadow comparisons include development-selected challengers beside
recent/pooled controls. Model artifacts are immutable finite JSON with learned
parameters, full trees, environment/code hashes, replay and local rollback; see
[the consumer contract](docs/passing-and-model-engine.md). Exact PPR remains
unsupported where components are missing. Marginal passing coherence failures
are retained in [the initial results](reports/initial-campaign/README.md);
those packages are not ready for joint integration. No candidate is promoted.

Integer push mass needs an actual saved line; absent odds never block football
forecasts, and this lab makes no EV or financial settlement claims.

## Empirical distribution research

The [twelve-category leaf-CDF study](reports/all12-leaf-cdf-v1/README.md)
completed 66 fixed historical fits across eleven supported targets. Exact PPR
retains its blocked scoring-source contract. Both player-history and context
panels, their mean/median errors, proper scores, adverse findings and coverage
are retained. The new gains compare against saved pooled-history controls;
they are separate from the one-week website scorecard and are not untouched
confirmation. [Inference and recovery contracts](docs/EMPIRICAL_CDF_RESEARCH.md)
describe explicit research use outside the operational registry. No new default,
recorder or scheduler is activated.
