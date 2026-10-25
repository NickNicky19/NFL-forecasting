# 484d retained replay: focused owner handoff

**Confirmed current-caller defect.** Both original positive cases reproduce the CI error; a three-line candidate in an isolated scratch copy makes all six affected, unchanged test methods pass. The actual website checkout and writer lease were untouched. No local replay remains running.

Source head: `484dbeff5c3fb34673380bf52b0f30ee0354a521`; tree: `c204f48961749715301a5133b2518ee8e8c829fb`. Original failed [CI run 40215159984 / job 121234602816](https://github.com/NickNicky19/nicks-expert-nfl-picks/actions/runs/40215159984/job/121234602816) checked out synthetic merge `886a1253d982a2608a7727b2ff7469a9782b17c1`, with that same tree. Its failure remains the hosted result.

## Exact mismatch

`tools/selection_strategies.py:121 _retained_call()` clears `GITHUB_SHA`. Its exported retained source uses a read-only `.git` pointer to the current repository. Frozen `data_integrity_v2.read_bundle():890` reconstructs rows with `reliability.make_payload():238`, which calls `recording_source()` without a commit. That lookup resolves current HEAD, rather than the authenticated retained source.

For **both** fictional fixtures, the saved observation `source_sha`, input `code_commit`, and native `code_commit` agree with their exact retained family:

| Family | Saved source / frozen reader | Actual implicit request |
|---|---|---|
| e2d | `e2dd96a31690baad04c8660302933f45f77d72e7` | `484dbeff5c3fb34673380bf52b0f30ee0354a521` |
| 045 | `04519b54dfb76dcca7916fe6bf75d7e1711793b6` | `484dbeff5c3fb34673380bf52b0f30ee0354a521` |

The first rejection is `pull/build.py`:

| Bytes | SHA-256 / exact public code preimage |
|---|---|
| Expected retained, 41,074 bytes | [`d8a1094af872c84e0fe092662a1241afc0eceaca8c27f7bea687e6a1be2f576c`](phase2-484d-retained-replay/preimages/d8a1094af872c84e0fe092662a1241afc0eceaca8c27f7bea687e6a1be2f576c.py) |
| Requested current, 41,802 bytes | [`726378a2ae5f7a1cedb1bd1538d49e77a5a6bbf9805c07eb89fc9fd4bdd92cbf`](phase2-484d-retained-replay/preimages/726378a2ae5f7a1cedb1bd1538d49e77a5a6bbf9805c07eb89fc9fd4bdd92cbf.py) |

Full observed call stacks: [e2d](phase2-484d-retained-replay/e2d-source-mismatch.json), [045](phase2-484d-retained-replay/045-source-mismatch.json). [Case evidence](phase2-484d-retained-replay/case-evidence.json) records exact fictional receipt paths, compressed/body hashes, and matching source fields. This is a coherent retained fixture, not a missing-reader or crossed-fixture problem.

## Candidate and actual checks

[Focused patch](phase2-484d-retained-replay/patch/retained-source-context.patch): inside the existing authenticated `_retained_source(source_sha)` context, bind the read child's `GITHUB_SHA` to that closed retained source. This supplies the source context needed by frozen row reconstruction. Existing commit/tree/blob, eight-file engine, helper, evidence, clock, and source-admission checks remain intact.

- Patch SHA-256: `1cd0e8e54fcf150ea418cdb59c4a2d649a1649c3d37521d28e88ea807e8ea78e`.
- Exact caller preimage: `f47a811dbcc1419167d1a826d16d062f907941a5b0177b25ffe2f8bb6af26162`; candidate: `7156c3f7d73e7ee8c106f3b5edde57338620f3969d297dcd3e1f7c229b1e66f9`.
- Before: each original positive case raises `Retained ranked validation rejected: Corrected recording source differs from closed engine`.
- After: **6/6 pass**, using each once-built original fictional lineage. Each family's 284 preserved evidence files remain unchanged. Positive cases include the independent cold process and rejection of new recording under old source bytes.

The unchanged methods from `tests/test_phase2_e2e.py` were:

- `RetainedRankedSourcePipelineTests.test_closed_original_source_and_pinned_ledger_replay_and_cold_process`.
- `Retained045RankedSourcePipelineTests.test_actual045_saved_observation_ledger_and_independent_cold_replay`.
- Both classes' `test_retained_failure_markers_and_same_size_corruption_are_not_cached` and `test_unknown_source_and_unknown_ledger_helpers_fail_without_fallback`.

[e2d results](phase2-484d-retained-replay/e2d-after-cases.json) and [045 results](phase2-484d-retained-replay/045-after-cases.json) contain all six exact IDs. Completed after-run sessions: `46025` and `9026`, both exit 0. Original attempt logs are retained beside these results. Scratch work area: `/tmp/phase2-484d-retained-g7ve7qyj`; source exports and fictional fixtures remain available there.

## Integration boundary

The patch changes only the current caller in the second scratch copy. All 118 exported source/test files were compared with 484d: every test and all eight engine files are unchanged; all eight old-family pins still match both retained fixtures. Frozen readers, historical registrations and expected-error assertions were not edited. Exact patch applicability and Python syntax checks pass. See [source invariants](phase2-484d-retained-replay/source-invariants.json).

The unchanged current website policy pins the caller's original `f47a…` hash. Its actual `code_review()` passes for original 484d and correctly rejects the candidate with `WEBSITE_CODE_NOT_REGISTERED`; [metadata evidence](phase2-484d-retained-replay/current-policy-gate.json). Owner integration therefore needs the normal current-code registration for the new caller hash, preserving old registrations and all eight engine hashes. No policy edit or registration action is included.

No full backend rerun, actual provider/network call, fit, protected real-2026 outcome read, Root action, external-job cancellation, source/branch/lease mutation, remote action or deployment occurred. These local results resolve the six retained cases in the prior classification; they do not claim a new hosted CI pass or qualify a release. Current-production COUNT7 remains a separate release decision for the sole integrator.

Artifact hashes are indexed in [SHA256SUMS.json](phase2-484d-retained-replay/SHA256SUMS.json).
