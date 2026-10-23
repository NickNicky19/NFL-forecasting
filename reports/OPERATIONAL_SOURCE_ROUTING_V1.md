# Permitted operational routing v1

Current operational CLI commands require the explicit frozen policy:

```sh
python -m nfl_lab.cli daily --source-policy config/operational-source-policy-v1.json
python -m nfl_lab.cli acquire --source-policy config/operational-source-policy-v1.json
python -m nfl_lab.cli experiment --source-policy config/operational-source-policy-v1.json
python -m nfl_lab.cli grade --source-policy config/operational-source-policy-v1.json
```

The existing workflow retains one cadence and writer. Its grading and replay
steps also run after acquisition, daily, or weekly failures. Acquisition uses
the provider's active NFL season, including January rollover, and persists
isolated immutable features beneath `data/processed/operational-source-v1`.
The legacy processed feature file and historical study functions remain frozen.

The operational experiment path refreshes only the fixed recent and pooled
references, at most 22 supported target/method packages. It performs no new
search, accuracy scoring, challenger selection, or promotion. Exact PPR is
blocked. Participation probability is unavailable because sufficient positive
events do not supply a complete nonappearance denominator.

Each new input and artifact binds the frozen policy, adapter and shared code,
source snapshot, qualified training view, actual training features, and exact
query. Artifacts use a new namespace. Replays reject changed bindings or query
values, and retries can replay an identical immutable package. Forecast model
IDs bind the stable policy/code reference version, so a refreshed source
snapshot cannot issue another forecast for an already frozen opportunity.

Permitted source failures abstain from affected issuance without invoking the
legacy loader. Frozen forecasts are retained and grading is attempted. The
saved Sleeper final/correction contract is unchanged. Cache supplementation is
read only and uses a verified permitted snapshot; an absent cache is an
explicit gap. A postcapture operational failure reports its actual new row
count rather than claiming that no issuance occurred.

This packet contains code and fictional software checks. Hosted activation and
real reference fitting require the separately frozen exact input/code/runtime
budget and artifact content review. Do not dispatch or merge the workflow
before that gate. Fitted parameters are not included in this zero-fit packet.
Actions artifacts or caches in a public repository are not private storage.
Any later publication of derived reference parameters requires its separately
approved publication scope. Source/player rows and raw feeds remain excluded.

Software acceptance is not predictive validation or prospective evidence.

The 40 minute hosted job keeps stricter command ceilings of 540 seconds daily,
180 acquisition, 720 reference learning and 180 grading. The remainder covers
setup, checks, replay, persistence and failure handling. The integration checks
one combined 512 MiB ceiling across operational sources, isolated features and
new models before and after operations. The frozen downloader checks storage
after bounded writes; a source acquisition can temporarily exceed the combined
ceiling before the outer guard detects it and abstains. Existing evidence is
retained. A shared reservation mechanism would be needed to prevent transient
overshoot, and this packet makes no such claim.
