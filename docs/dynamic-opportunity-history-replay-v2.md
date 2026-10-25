# Dynamic opportunity historical replay v2

This new entry addresses the original historical query contract: retained
historical cutoffs can equal kickoff. Frozen V1 requires a strictly earlier
cutoff, while the unchanged math core already accepts equality. V1's strict
gate, core, eighteen original definitions and FAILED terminal/worker-PASS
evidence remain byte-frozen. No timestamps or epsilon offsets are changed.

## Explicit new interface

`nfl_lab.dynamic_opportunity_history_replay_v2`:

```python
build_historical_offer_windows(
    offers, calendar, membership_rows, qualified_player_rows, proxy_panel,
    *, task, source_binding, replay_policy,
)
```

`VERSION = dynamic-opportunity-history-replay-v2-20261023`.
`build_recorded_proxy_panel` is reexported unchanged from V1; its schema, all-
position recorded proxy semantics and strict original seven-day availability
remain V1. The new window body reuses frozen V1 source/calendar/support helpers.
It is explicit source code because the frozen V1 function has no configurable
cutoff gate; no runtime source replacement, monkeypatch or query-clock edit is
used. The only window eligibility change is the declared historical query
condition `cutoff <= kickoff`, plus new version/evidence/policy metadata.

The required `replay_policy` has exactly these fields:

```json
{
  "schema_version": "dynamic-opportunity-history-replay-v2-20261023-policy",
  "execution_lane": "EXPOSED_HISTORICAL_REPLAY",
  "source_policy_sha256": "<same exact pinned original source-policy SHA as source_binding>",
  "query_cutoff_rule": "cutoff_utc_at_or_before_kickoff_utc",
  "source_availability_rule": "kickoff_plus_7_days_strictly_before_cutoff_utc",
  "original_clocks": "PRESERVE_NO_EDITS_OR_EPSILON",
  "prospective_issuance": "FORBIDDEN"
}
```

No absent/default/prospective policy is accepted. Source-policy identity must
match the original binding. The normal V1 source validation still rejects a
prospective source-availability lane. Policy authority and actual acquisition/
study permission remain the integrator's separately frozen contracts; merely
passing this dictionary authenticates neither inputs nor a past issue time.

## Timing and unchanged safeguards

- Query cutoff may precede or equal kickoff only in this exposed replay lane.
  A later cutoff remains an original-reference fallback.
- Source availability remains exactly prior kickoff plus seven days, strictly
  **less than** cutoff. A source available exactly at cutoff does not update
  counts; its elapsed slot remains present and unknown.
- All original offers, identities, cutoff strings, roles, membership/spell
  requirements, latest-eight missing/DNP/unknown slots, partial proxy receipts,
  unchanged carry volume and exact matched-static information remain the same.
- Membership ambiguity and invalid counts still fall back without seeking
  older games. Exact week/REG/source-hash/two-calendar-side checks remain.
- New packet and each result carry V2, `EXPOSED_HISTORICAL_REPLAY`, canonical
  `digest(replay_policy)`, `query_clock_edits=0` and
  `AFTER_GAME_RECONSTRUCTION_NOT_ORIGINAL_ISSUANCE`.

This does not repair historical publication uncertainty, prove participation
or true-zero completeness, or turn any exposed year into confirmation. It is
not the separate prospective capture adapter. Real future issuance still needs
actual capture/calculation/persistence before cutoff **and** cutoff strictly
before kickoff, plus its own source/model/registration and durable-storage
contracts. Old rec-half and RB windows are unchanged.

## New software packet — eight checks passed

The separately authorized packet completed once: eight new fictional methods,
zero failures, errors or skips. Wall time was 0.218001373 seconds and combined
CPU 0.288009 seconds. The [execution receipts](../reports/dynamic-opportunity-replay-v2/README.md)
retain the exact freeze, independent PREEXEC and root GO. This verifies software
timing contracts only; no NFL data, forecasts, scores or confirmation were added.

Eight new fictional timing/compatibility methods: equal-kickoff explicit replay;
earlier/later cutoffs; rejecting implicit/prospective policies; strict source
clock equality; unchanged ambiguous/nonmodeled fallbacks; exact source-policy/
lane compatibility; equal information under earlier V1-compatible cutoffs; and
unchanged identity/no-issuance claims. They import no old test module, call no
filter/prior fit, create no numerical forecast and score no NFL game. Two
focused new timing cases call the frozen V1 function to verify its strict gate
and identical common request information; the old eighteen-method suite is not
run.

Executed ceiling: one guarded invocation, eight new methods, 120 wall/CPU
seconds, 512 MiB, two threads, zero worker children/NFL/source/model/network/
CAS/fits/filters/forecasts/scoring/old-suite reruns. It uses the separately
accepted owned-child termination helper, preserving live missing-counter
failure, exact PID/startticks and mandatory full post-reap resource charge.
Original V1 FAILED and separate six-contract guard-only PASS receipts are bound
unchanged. Independent exact PREEXEC and root ledger GO precede any invocation.

No actual source-bound producer run, 54-package numerical experiment, live
capture, model default or website change is authorized by this implementation.
