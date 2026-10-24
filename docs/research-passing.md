# Selectable pooled-H3 passing-yard research point

This implements the strongest named Week 6 lead as a portable, explicit research
adapter. It does not activate a new default, add a scheduler, capture a registered
forecast, change website source or reproduce the missing original executable.

The separate prior retrospective reconstruction had 27 matched player-games in
13 games/one exposed week: website MAE 56.622963 versus 45.205603, +20.16%.
Bias worsened from −19.081481 to −24.072824. That limited result is not independent
confirmation or proof of a generally better model. The longitudinal historical
efficiency-window study is a different experiment with a different held workload,
history gate and source lane; it cannot inherit the website-relative gain.

The portable adapter matches all 37 prior saved opportunity points in a private
consumer replay, including fallbacks. That is technical parity only: the replay's
calendar clock uses an original generation/version-time availability proxy,
not an independently established local capture time. It does not establish
source-qualified as-of forecasts or recover the original runner.

## Run explicitly

```sh
python -m nfl_lab.research_passing \
  --method website-held-attempts-h3-ypa-research-v1 \
  --bundle examples/research_passing/bundle.json \
  --pins examples/research_passing/pins.json \
  --output /tmp/passing-research-point.json
```

The included example is entirely fictional. Its past dates deliberately produce
`RETROSPECTIVE_ARITHMETIC`; no NFL player or provider data is redistributed.
Output creation refuses an existing file. Omitting `--output` prints JSON without
writing state. No network, account, key, fitting or model selection is involved.

The Python API is `nfl_lab.research_passing.evaluate(context, opportunities=...,
statistics=..., projection=..., trusted_hashes=...)`. `ResearchPoint.to_dict()`
matches [the separate research schema](../schemas/research-point-v1.json).
`pooled_point(held_attempts, selected)` is arithmetic only; the caller must qualify
history before using that lower-level function.

## Input contract

Every document uses the existing `SourceDocument(reference, payload_bytes,
observed_at, time_basis='pre_cutoff_capture')`. Pins must come from a separately
trusted extraction manifest; a digest supplied with arbitrary data does not prove
its provenance. The JSON CLI represents payload bytes as literal UTF-8 strings
and reads expected reference→SHA256 pins from a separate file.

Context identifies player/game/team/opponent, season, `season_type='REG'`, week,
`period='full_game_with_ot'`, original cutoff/kickoff/capture clocks, website yards
and held website attempts, projection source reference and baseline receipt digest.
The projection document repeats those bindings and declares
`attempts_origin='same_receipt_unchanged_website'`. The upstream extractor is
responsible for recovering that exact pair from the original trusted receipt;
an attempts challenger or a newly computed point is not interchangeable.
The thin projection's `baseline_receipt_sha256` is a caller-declared pointer:
this adapter does not itself open/authenticate the original receipt, input board
or engine. That upstream extraction must verify the receipt/board/engine hashes
and exact original two points before supplying this bundle.

Opportunity and statistics documents identify the same player, season/type and
period. Opportunities contain every prior week 1..target_week−1 with explicit
game, bye or not-rostered state and team. A completed game identifies opponent,
kickoff and the time its final state was locally observed. Statistics identify
that same game/team/opponent/week, participation, explicit passing yards/attempts,
source pointer and statistics observation clock. A final-state observation is
not the game's actual end time: independently polled status can be observed after
an already retained full-game statistics snapshot. Each observation must be after
the prior kickoff and by the original cutoff; the upstream extractor remains
responsible for qualifying that full-game statistics source/version. Neither document can be observed after the
original cutoff or in the actual future. Publication time remains unverified.

Scan newest first. A different team, not-rostered gap, unknown participation,
missing/ambiguous record or invalid selected field stops the scan. A verified
bye or same-team DNP can skip. A played-zero appearance stays. Stop immediately
after exactly three valid appearances; older statistical uncertainty is not used.
Attempts must be explicit finite nonnegative integers. Signed yards and
fractional held attempts remain legal. A zero-attempt/nonzero-yard prior is
invalid under this passing recipe. Pooled attempts must be positive.

## Output and failure behavior

The point is exactly held website attempts × pooled H3 yards/attempts. There is
no fitted offset, rounding change, efficiency cap, nonnegative-yard floor or
workload substitution. Unsupported history returns the unchanged original site
yard point and a reason. An untrusted original projection/identity/cutoff or
missing original yard point abstains; it does not invent a fallback.

Output binds input/code/source digests, original context, selected game IDs and
the actual calculation clock. It uses `point`, never a fabricated conditional
mean or probability. Distribution/uncertainty is null. The result always says
`qualified_for_default=false`, `recorded_pregame=false` and
`original_runner_reproduced=false`. Even a pregame calculation is unrecorded
arithmetic; this API cannot assert publication or persistence before kickoff.

## Operational isolation and recovery

This method is outside `models.METHODS`, the daily/experiment CLI and promotion
registries. Existing model defaults, rec-half registration and original windows
are unchanged. Stop invoking this explicit method to return to the original
site reference. No website/default change requires rollback.

Publishing package changes to the lab's main branch currently triggers its
existing capture workflow. Review that event consequence before publication;
this implementation adds no workflow and performs no dispatch or activation.
