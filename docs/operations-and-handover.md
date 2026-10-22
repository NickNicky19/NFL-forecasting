# Operation, consumer acceptance and handover

The lab is an operational **shadow research** system. No model is scientifically
qualified or deployed to the website. `execution/ledger.jsonl` is the execution
ledger; immutable state receipts are evidence, not a second task ledger.

## Run the same bounded pipeline

Use the locked environment documented in the README. The CLI accepts `--root`,
`--cache` and `--state`, so a technical integration fixture can use isolated
state without becoming a second official forecast recorder.

| Command | Purpose | Evidence |
| --- | --- | --- |
| `python -m nfl_lab.cli acquire` | Cached, versioned permitted history and features | Source receipts and feature-file SHA |
| `python -m nfl_lab.cli experiment` | Fixed, finite registered comparisons | Unique attempt, all trial states, local row files and aggregate reports |
| `python -m nfl_lab.cli daily` | Freeze eligible future opportunities; grade supported completed games | Forecast, persistence, source-manifest, model and health records |
| `python -m nfl_lab.cli replay` | Validate immutable records and score available outcomes | Integrity result, pending and conflict counts, separate confirmation cohort |

The hosted workflow restores `lab-state` before it runs. It persists derived
state through a single writer and verifies remote readback after publication.
GitHub's queue is bounded; an older pending job can be superseded. A delayed
scheduled job outside the Chicago morning window is skipped. Neither case
creates a backdated forecast. Manual recovery uses the existing workflow and
the same frozen-opportunity rules.

Every invocation with a valid cadence decision also persists a small operations
receipt, including skipped slots and failed training steps. It binds the GitHub
run ID/attempt, event, source commit, observed decision and step outcomes. These
are workflow attestations; the Actions API independently establishes the run
identity/conclusion. A future scheduled event can therefore leave durable proof
without an always-running assistant or another scheduler.

The initial hosted capture and retries succeeded. A manual hosted training run
completed within its 1,200-second budget, evaluating 426 of 432 registered trials
and explicitly skipping six when the fit budget expired. The earlier timeout
remains recorded. The Checks API independently confirms training run
`39791493637` and capture run `39795596765` succeeded; the Actions run listing
temporarily returned stale queued/in-progress states. See
`reports/hosted-verification.json` for the bound state commit and receipts.
Neither the expected October 22 morning scheduled delivery nor a subsequent
scheduled event has been observed. This is an unverified scheduler delivery,
not proof of a specific account setting. Reading administrative Actions settings
returned HTTP 403; no access restriction was bypassed.

Raw HTTP bodies are cached once per source within an execution workspace and
versions are retained locally. Standard hosted runners are ephemeral: a later
runner may need to download them again. The lab does not publish raw bodies in
Git, Actions artifacts or caches to obtain cross-run persistence. Detailed
historical rows remain in the ignored research workspace; hosted durable
training receipts bind their hashes and retain trial parameters and summaries.
Those receipts alone cannot restore an unavailable historical raw snapshot.

## State and resource limits

The single workflow has a 40-minute job limit, a 15-minute daily command limit,
a 5-minute acquisition limit and a 20-minute experiment limit. Fits use at most
two threads. HTTP acquisition has bounded sizes/retries. Health artifacts expire
after 14 days. Derived state has a 200 MiB write cap; evidence is not deleted to
make a new run pass. Fitting stops before that cap is reached.

Forecasts keep their first player/game/target/model opportunity. Retries do not
fit those opportunities again. An exact source identity crosswalk may support
new opportunities, while existing identities stay frozen. Played zero, missing
statistics, DNP and unknown participation are separate. Source observations
append; conflicting numeric corrections without an authoritative publication
order are quarantined rather than silently replacing an outcome.

## Read-only website consumer

Reference: `NickNicky19/nicks-expert-nfl-picks` at
`c8120e3cb26a908b8d5a99329b0f28ae49473ea1`. The exact offensive PPR scoring
contract is pinned in `docs/skill-categories.md`. The lab has never dispatched
that repository's workflows, changed its files or deployed to it.

1. Read a hash-verified forecast batch and its persistence/publication receipts.
2. Use `nfl_lab.consumer.consumer_forecast` to validate a copy against
   `schemas/forecast-v1.json`. Legacy clock formatting is normalized only in
   that copy, with a digest binding the untouched original row.
3. Require the expected player/game/team/opponent, full-game target/scoring
   identity, source/cutoff clocks and compatible model version. An unsupported
   PPR component, absent source binding, late issuance or invalid schema means
   abstention or the consumer's explicitly pinned baseline fallback.
4. For fitted inference, restore the artifact's exact code/environment and use
   `nfl_lab.model_artifacts.predict_artifact`; it never refits. Required features
   and source availability must be independently qualified by the caller.
5. Treat scalar conditional-on-playing marginals and participation estimates
   separately. Do not combine unrelated quantiles or assume independently
   selected passing models satisfy completions <= attempts. Joint integration
   remains unqualified where those checks fail.

The schema, cold-start/failure fallbacks, immutable artifact replay and verified
local active/previous rollback are tested. The website owner decides whether to
integrate any package after reviewing its scientific and technical states.
Consumer readiness does not establish a future accuracy gain.

## Rollback and external research ownership

Disable this lab's workflow to stop new lab issuance. Revert a faulty lab code
commit and restore the recorded inference environment; retain all frozen state
and failed trials. `rollback_artifact` verifies a previous immutable artifact
before moving the local active pointer. Never reset evidence or reuse an old
model identity for changed forecasts.

The original `rec-half-adjustment-v1` recorder and its Weeks 7–14 window retain
their registered ownership. This lab does not create another official recorder,
backfill its missed weeks or restart it. A read-only task lookup on October 22
found the previous `NFL Forecast Research` automation already disabled, with no
next run and a completed last run. This lab did not disable or edit that task.
The lookup establishes its observed inactive state, without claiming recovery
of its private sandbox files or changing the frozen experiment's ownership.

## Scientific limits that remain explicit

The original pooled-YPA challenger runner, bound inputs and row outputs remain
unrecovered. Its reported n=27/13-game gain and worse bias remain retrospective.
Exact PPR scoring works, but a complete authentic component crosswalk is missing
for the campaign, so those forecasts abstain. Historical data are current-vintage
reconstructions; source hashes do not establish original publication clocks.
Public NGS was tested separately and remains inactive. Historical injury/news,
forecast-weather, routes and detailed coaching/personnel inputs without qualified
snapshots do not become invented numerical features. Missing saved lines mean
no selected-line or EV claims. Prospective outcomes and later confirmation are
pending, and no qualified winner is required to operate the lab honestly.
