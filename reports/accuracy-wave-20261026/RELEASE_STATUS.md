# Actual production release status — October 26, 2026

## Verified live state

A separate read-only check at **17:46:43–45 UTC** found the served index,
application, overlay JavaScript, health and overlay pointer identical to website
Main **`453e7e6e843b0cb1ae611b0925063e0f96c70196`**. Application SHA-256:
`409dcb4830cf91b08c2202232e392cae3e0ef02c2f9e72c94e27af2ff0e594ec`.
The overlay remains
`3691be0265c1d4e4f1a7ee0631168337c49f66ce80abd6005a5dc4fd4ccfc267`;
served health generation remains October 25 at 10:15:15 UTC.

**No model, ranking, policy or correctness-package deployment occurred in this
accuracy wave.** Existing provisionally selected forecasts remain live. A
published research report is not a website release.

The last demonstrated deployment is [run 40183962653](https://github.com/NickNicky19/nicks-expert-nfl-picks/actions/runs/40183962653),
source `0f03af20226c17c54f27f930eccea162ab331c4c`, producing data Main `453e7e6`.
Deployment and post-deployment fencing completed there. Later
[run 40214438233](https://github.com/NickNicky19/nicks-expert-nfl-picks/actions/runs/40214438233)
failed overlay preparation; commit, upload and deployment were skipped.

## Existing production owner and remaining action

The production coordination ref
`3f108dc5ecdaac7fe4a77423dff1e9011e97ee60`, revision **168**, still assigns
`NFL-WEB-PRODUCTION-REPORT-INTEGRATION-20261025-122500Z` to NickNicky19 at source
`484dbeff5c3fb34673380bf52b0f30ee0354a521`. PR #1 is open and unmerged.
This research run has not claimed, reassigned or released that writer's lease.

The owner's [previous result](https://github.com/NickNicky19/nicks-expert-nfl-picks/pull/1#issuecomment-6400694306)
described pending CI. Both Reliability runs associated with development head
`484dbeff5c3fb34673380bf52b0f30ee0354a521` subsequently failed in
the retained-baseline and Phase 2 regression suites:
[PR run 40215159984](https://github.com/NickNicky19/nicks-expert-nfl-picks/actions/runs/40215159984)
and [push run 40215154808](https://github.com/NickNicky19/nicks-expert-nfl-picks/actions/runs/40215154808).
The push checked out that source head; the PR checked out synthetic merge
`886a1253d982a2608a7727b2ff7469a9782b17c1`. Each ran 1,337 tests and ended with
12 failures and 18 errors. These were completed regression failures, not a
timeout. Later checks and source sealing were skipped. Software-test counts
are not NFL prediction observations.

The [reviewed 13-path Main package](https://github.com/NickNicky19/NFL-forecasting/blob/23e471d/reports/main-count7-strict-props-release-20261026/README.md)
remains a prepared alternative: base `453e7e6`, reviewed head
`74dc2573ca1d34311482f918f25c084ca14a446b`, patch SHA-256
`ceb7f8dcc7fd588d12a0d6e74f574d9183f9104727843445ee6f8f14a821bcda`.
It must not be stacked onto the separate Phase 2 alternative.

The existing integrator must reconcile the applicable alternative and its scope,
address applicable failures, obtain passing hosted checks on the chosen integrated
source, integrate through the normal repository workflow,
and verify the deployed build and selected-feed consumption. Four prepared paths
are outside its presently bound ordinary scope:

- `.github/workflows/hourly.yml`
- `config/weekly-derived-selected-policy-v4.json`
- `tools/weekly_public_feed_v4.py`
- `tests/test_weekly_public_feed_v4.py`

Those are concrete production dependencies. Historical percentage improvements
do not finish them, and the research session must not create a competing writer.
The existing owner was already informed through
[coordination comment 6417942181](https://github.com/NickNicky19/nicks-expert-nfl-picks/pull/1#issuecomment-6417942181).

## Capture, expiry and next decision

Genuine COUNT7 producer `c74812b`, [run 40203512153](https://github.com/NickNicky19/NFL-forecasting/actions/runs/40203512153),
feed `214b3983f6fc6cbf2907afa1ef4ae0bd002179fdf99c78b9bc739b1f8431dd4c`,
expires **October 27 at 00:15 UTC**. This expiry is immutable. Later usable
issuance requires genuine fresh evidence, never a changed expiry or backdate.

The unchanged website schedule is daily **08:06 America/Chicago**; the next
configured occurrence is **October 27 at 13:06 UTC**, after that expiry. No newer
Main run than the failed October 25 run appeared in the refreshed run list.
This is a configured schedule, not evidence that the next run will succeed.

The research controller's separate registered weekly decision remains
**October 29 at 18:15 UTC**, subject to actual schedule and runtime qualification.
Its configured 12:36/13:36/14:36 UTC slots are not the website's daily schedule.
No additional scheduler was installed. The existing controller records and the
canonical execution ledger must record actual capture, grading, selection and
publication; future runs and Monday's unplayed outcomes remain pending.

The read-only check accessed software/deployment evidence only, not new football
outcomes, odds, credentials or protected confirmation data. Requested agent
settings were GPT-6.1 Sol/xhigh; actual backend attestation is unavailable.
