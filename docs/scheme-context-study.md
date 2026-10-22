# Public scheme and pace development study

This is one fixed input ablation on already exposed 2023 development outcomes.
The frozen 97-feature baseline and its original 2023 ridge predictions are
reused. One new 47-feature group is added to the shared ridge/logistic engine,
with its existing penalty, preprocessing and seeds. Training uses 2019–2022;
there is one new fit for each of 11 supported targets, at most 300 seconds and
two threads. Exact website PPR is excluded because its historical crosswalk is
incomplete. Model selection, promotion and prospective activation are disabled.

`config/scheme-study.json` was committed at
`b27d03aa1b8f41479ffac7c28787bf065c91680e` before any new fit. The implementation
and focused tests were committed separately before the registered run. The
runner rejects an uncommitted registration, a changed base feature SHA, a changed
baseline population/outcome, a different feature width or an exhausted attempt.
A durable budget marker prevents rerunning completed or failed fits on restart.

## Source and football meaning

The common public nflverse schedule/identity adapter binds cached 2022 and 2023
PBP game/team/opponent identities. Source bodies and receipts are hashed. The
2023 asset is reused; the only new acquisition is the 20,426,548-byte public
2022 asset through the existing bounded downloader. Upstream source attribution
and license receipt are preserved in the manifest. No raw play or player/game
data is included in published results.

The group has offensive team tendencies and the target opponent's defensive
exposures. It pools supported dropback, neutral early-down dropback, shotgun,
no-huddle, red-zone dropback and red-zone exposure numerators/denominators over
three prior game slots. It also adds scrimmage play volume and game-clock runoff
between adjacent same-possession/drive/quarter competitive plays. Runoff is a
public tempo proxy; it is not a measured snap timestamp or complete pace model.
Kneels, spikes and special teams are excluded. Unknown source flags do not
become zeros, and missing games consume slots rather than triggering a search
for older favorable history.

Neutral plays are defined before fitting as first/second down in quarters 1–3,
pre-play score difference within seven points and more than two minutes left in
the half. These states belong to earlier games. No target-game score, play mix,
yardage, formations or weather is used. For opponent adjustment, each prior
game's neutral dropback rate and play volume are compared with the earlier
opponent's own previous offensive/defensive exposures, using the same cutoff
and three-game rules. The adapter does not normalize against later opponents.

Schedule dates supply days since the last strictly earlier scheduled kickoff.
That is a date-derived quantity and does not assert participation or completion
of the earlier game. The lagged coach flag compares the two most recent
eligible historical coaches. It does not claim knowledge of the upcoming coach
or a private game plan.

The target's scheduled stadium identity selects earlier observations of that
venue. Only old closed/dome-roof and surface observations enter numerical
features. The target's realized roof, surface and weather are ignored. Supported
surface names map to artificial (`fieldturf`, `a_turf`, `astroturf`, `astroplay`,
`sportturf`, `matrixturf`) or predominantly natural (`grass`, `dessograss`);
other strings remain missing. These rates describe historical venue context,
not a forecast of weather or whether a retractable roof will be closed.

## Timing, coverage and limits

PBP, coach and historical venue observations require source kickoff plus seven
days to be strictly earlier than the target cutoff, and must be at most 60 days
old. Team/opponent/venue windows retain three eligible game slots, including
unsupported values. No base column or offered player row is changed. The model
engine retains its original player/position/team/opponent fallbacks and explicit
missing-feature indicators.

All data are current-vintage reconstruction. Download clocks and GitHub asset
updates do not establish the original historical publication time. The original
schedule publication, schedule changes, roster revisions and retrospective
coach/venue corrections are not authenticated. These limitations preclude a
prospective advantage claim. Public PBP covers 2022–2023 here; the 2019–2021
training rows retain missing PBP features. That limited training support and
its missingness pattern are reported rather than concealed.

Authentic historical forecast weather, route/personnel/coverage counts, private
gameplans and authenticated injury/news snapshots are unavailable in these
inputs. Actual target-game weather is not a substitute. Additional authentic
sources would require their own versioned contract and finite new study.

## Outputs and checks

The reusable modules are `scheme_context.py` and `scheme_study.py`; base
features, loader, shared models and evaluator are unchanged. The runner reads
the pinned feature cache with a parquet season filter through 2023, so it does
not evaluate 2024, 2025 or new 2026 outcomes. Local row files and trials remain
in ignored `runs/`; only reviewed aggregates, manifests and hashes are published.
Every target's MAE/Brier, RMSE, bias, coverage, warnings, failures and paired week
interval is retained. Intervals are exploratory and cannot promote a candidate.

Focused tests cover pooled rates, missing and unfavorable intervening games,
source/target identity, zero versus unknown flags, target outcome/coach/roof
mutations, strict cutoff/lag boundaries, cold starts, stale seasons, unchanged
base columns/population and recognition by the shared engine. Existing common
schema, leakage, model, evaluator, replay and scheduler tests are also run.
