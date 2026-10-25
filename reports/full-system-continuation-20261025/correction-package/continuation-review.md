**Independent continuation review and integration handoff — 2026-10-25**

The concrete correction package is [current-production-corrections](/workspace/nfl-system-audit/current-production-corrections/README.md), revision 2, based on **89512ed952308dacc1f6a930915ddbcdccd460d9**, whose application source includes release **a2047854bece90ba354f7e379846cafc499fa7d6**. The refreshed combined source passes **129 Python tests**, the **47-check** mathematical oracle, **75 full-application Chromium checks**, and the **53-check** selected-ranking contract/browser run. These are actual source executions using fictional inputs and blocked networking. They do not constitute hosted CI, a real first production build, a model registration, or deployment acceptance.

Use [combined-89512ed.patch](/workspace/nfl-system-audit/current-production-corrections/combined-89512ed.patch), the eight exact replacement/addition files under [files](/workspace/nfl-system-audit/current-production-corrections/files), and [manifest.json](/workspace/nfl-system-audit/current-production-corrections/manifest.json). The combined diff applies to the exact pinned preimages with **zero fuzz and zero offsets**; every resulting file matches the tested full-source copy. The earlier prepared finality patch's two-line offsets during assembly were eliminated by regenerating this final combined diff. Revision 1 evidence remains under `evidence/revision-1`; its pre-cache-version diff is superseded.

All website source/worktrees, Git metadata, remotes and writer/lease state were left untouched. The user-reported active Phase 2 owner remains `NFL-WEB-RANKINGS-PHASE2-20261025-003000Z`, coordination prefix `5f7510a`; this review neither authenticated a fresh remote lease nor claimed ownership. All mutations occurred in this audit package or disposable copies without shared `.git` metadata. No provider acquisition, paid service, protected outcome inspection, message, commit, push, workflow dispatch, or deployment occurred. Parent owns external integration after its handoff.

**What is implemented in the tested main correction**

| Exact file | Corrected behavior |
| --- | --- |
| `pull/scoring.py` | Retains the provider's `fgm` total without adding it to fantasy scoring weights. |
| `pull/build.py` | Uses the explicit `stat-keys-fgm-v1` normalized-stats cache; preserves prior issued classic reports; retains completion evidence and requires confirmed past finals at all three final-selection sites. |
| `pull/grade.py` | Rejects contradictory player/game/team/opponent statistics in Top and lean/PPR grading; issues `statistical-v3-identity-20261025`; preserves previous exact report bytes in content-addressed `grading-history`. |
| `output/app.js` | Makes missing current-week half-PPR headlines/averages and fantasy-point props unavailable; retains valid zero and only known half-PPR history. |
| `tools/weekly_selected_rankings.py` | Rejects a valid over moved into the under container, and vice versa. |
| `tests/test_fgm_cache_contract.py` | Six meaningful first-use/current/history/cache-failure regressions. |
| `tests/test_grading_identity_v3.py` | Nine identity/version/prior-publication/interrupted-write regressions from the retained proposal. |
| `tests/test_weekly_selected_rankings.py` | Adds the wrong-side container regression. |

The current app preimage is SHA-256 `b86c5bc0580611d6f8bcd18dff75b5ca3db663dcc625fbc6a29ce135ac5f5704`; corrected app SHA-256 is `76cc66917e1c8f5f61d1d0169001bd09bc76c2a6439b2ec32c89619c9484bbd7`. The entire app outside `projPts`, `avgPts`, `pv`, `propChip`, and `catCard` is byte-identical. The new My Picks caption, reversible live grading, selected ranking/forecast functions, index, helper, browser contract test, policies and workflows are preserved exactly. The full app browser checks exercise the actual scoring buttons, collapsed/expanded missing states, known half zero/history, K/DEF controls, PPR return, actual My Picks caption, downward live correction, selected sort options and layout at 320/390/1280 pixels. No page exceptions occurred.

**Cache prerequisite and actual-function FG traces**

The original FG-only proposal did not repair historical normalized caches. This continuation adds the smallest explicit correction: `STATS_CACHE_VERSION = "stat-keys-fgm-v1"`; the corrected `week_stats` uses `data/cache/stat-keys-fgm-v1/stats_{season}_{week:02d}.json`. Original R0 continues to use its preserved `data/cache/stats_{season}_{week:02d}.json`. There is no copying, relabeling, deletion or fallback from the old cache. A missing versioned cache requires the ordinary source call even when `refresh=False`. A warm versioned cache can be reused, and forced refresh updates only that versioned lane.

[fgm-cache-trace.json](/workspace/nfl-system-audit/current-production-corrections/evidence/fgm-cache-trace.json) records the actual `week_stats`, `trim_stats`, `load_stats_through`, `projections`, `gamemodel.rollup`, and `gamemodel.finish` executions with fictional source rows:

| Trace | Observed result |
| --- | --- |
| Current actual stats and projections, independently normalized | Both retain FG totals **3 and 1**, yielding raw team points **23–24** and projection spread **+1.0** at league mean 22. |
| First historical read with only an old cache missing FG totals | Makes one source call despite `refresh=False`; writes the new cache; old bytes unchanged. Diagnostic rollup changes from **14–21 / +8.8** to **23–24 / +1.0**. |
| Actual historical loader across prior/current seasons | All four fixture periods, including nominally unrefreshed old periods, obtain the new normalization; all original cache bytes remain unchanged. |
| New cache warm read and forced refresh | Warm read performs no source call; forced refresh changes only the new cache. |
| Source unavailable, old cache present | Raises the source failure; does not consume old normalized values or create a purported corrected cache. |
| Source omits `fgm` | Neither stats nor projections reconstruct it. Diagnostic rollup remains **14–21**. Retention cannot establish an absent upstream total. |

This is source-function evidence, not a measurement of actual provider FG availability. No old cache is claimed repaired and no archived prediction was rewritten. Production `gamemodel.rollup` consumes current projections; the historical-cache rollup above is an explicitly labeled diagnostic. Actual league-score scaling uses completed scoreboard scores, rather than summing historical normalized player stats. Legacy `tools/verify.py` and `tools/compare_lines.py` still read original cache paths; their historical diagnostic scope was not broadly rewritten. The parent must account for initial cache-miss source work and bind the new cache lane in applicable capture/recovery contracts during its separate first-release acceptance.

**Engine/model identity required before integration can publish**

[engine-pins.json](/workspace/nfl-system-audit/current-production-corrections/engine-pins.json) supplies the complete seven-file corrected engine map, the classic grader hash, the 14-file website inventory, and every changed preimage/postimage. In the untouched main V2 policy, `engine_sha256` equals `website_code_sha256` for `ENGINE_FILES`, and the original R0 freeze binds that original map. The current main policy's physical SHA is `e8e037a00a22d3e0e07e41ed5816f2374e8f162a7fa78ea8cc45888ed2e2f094`, with R0 identity `a21ccd21ad395da3487c5e084ab2865c54a357a191419cc4da9ce31c19f83660`.

The corrected execution is **not registered**. Updating the two inventories under that old R0 identity is insufficient and invalidates the freeze relationship. The parent's analogous V3 transition must preserve the historical policy/freeze and separately bind a new corrected classic execution/model, these actual code bytes, and the cache contract. It must retain an original-engine fresh-input R0 shadow on the same newly captured raw inputs, with the original normalization and original identity; corrected FG normalization cannot be labeled that original shadow. Historical archives and prior issued reports keep their original identities. No lab authority, experiment registration or promotion gate is changed here.

| Changed engine/grader | Exact tested postimage SHA-256 |
| --- | --- |
| `pull/build.py` | `1d1646ef67469c3ec45227b9fcb053c4e229362a07bca092a5602a1a1442c1e1` |
| `pull/scoring.py` | `58c1f57fb0404f8bb6d1568d51791c97cdf0bb941c57117b703c6a24534980db` |
| `pull/grade.py` | `739df92bf9a04ef5f9974e4213bb7fda98b29be84c30654c2095003fbb974354` |

The current website inventory digest is `27b9cdedd97e451ac6506734cd508e6d705502d9c476b5596881d377e6826588`. Grading version is explicitly `statistical-v3-identity-20261025`. The new model version needs a distinct registration; **do not reuse** Phase 2's `sleeper-matchup-data-integrity-v2`, whose closed source contract describes different presence-aware engine bytes. Parent is independently handling this transition; this package does not edit a policy, workflow, source gate or frozen receipt to pass a changed engine.

**Qualification retained against the refreshed combined source**

| Check | Result |
| --- | --- |
| Untouched caption snapshot, complete Python discovery | **113 passed**, no failures/errors/skips or network attempts. |
| Corrected full current source, complete Python discovery | **129 passed**, no failures/errors/skips or network attempts; 113 originals + 9 identity/history + 1 side guard + 6 cache tests. |
| Independent math oracle | Baseline **43** explicit observed-behavior assertions; corrected **47** assertions, including actual `build.run → grade_all` cancellation control and all 12 category arithmetic. |
| Wrong-side regression on the exact original source | Expected failure: **ValueError not raised**. Corrected Python and actual JS validate the side boundary. |
| Python compile and three actual JS syntax checks | Passed. |
| Required current Node contracts | UI **8 + 19**; overlay **27**; selected ranking **37**; primary-forecast Chromium render **100** at three widths; caption **3** cases. All passed. |
| Selected-ranking browser-enabled run | **53 checks**, passed, zero HTTP. Includes the 37 contract checks; do not add the two runs as independent evidence. |
| Entire HTML/CSS/app Chromium route regression | **75 checks**, passed at three widths; every request intercepted; external requests aborted, only fictional responses/source assets fulfilled. |
| Exact combined patch and file-byte comparison | Passed, zero offsets/fuzz; whitespace checks clean. |
| Source preservation | All **64** non-data tracked caption files still match the pinned archive; five critical pending Phase 2 source/workflow files still match e415912 objects. |

See [qualification.json](/workspace/nfl-system-audit/current-production-corrections/evidence/qualification.json), [combined-python.log](/workspace/nfl-system-audit/current-production-corrections/evidence/combined-python.log), [full-app-browser.log](/workspace/nfl-system-audit/current-production-corrections/evidence/full-app-browser.log), and [preservation.json](/workspace/nfl-system-audit/current-production-corrections/evidence/preservation.json). The legacy `test-presentation-browser.cjs` is not attributed to this run: it opens real saved boards and assumes older ordering. Its file is unchanged. Current actual-source browser contracts plus the new entire-app fictional route checks provide the focused regression evidence above. No test assertion was weakened to obtain a pass. An initial test-harness mismatch expected an em dash where the existing formatter deliberately renders `-`; that harness-only expectation and original failure log are retained.

Main's broader legacy missing/explicit-null/count assumptions remain visible in the mathematical oracle. The half-PPR correction is the prepared current-week headline/average/prop scope; the separate pre-existing ROS `futureRows` full-PPR fallback remains unchanged. No claim is made that the whole Phase 2 missingness/finality/reporting system has been integrated into main.

The negative-count patch is isolated under [phase2/optional-negative-count](/workspace/nfl-system-audit/current-production-corrections/phase2/optional-negative-count/qualification.json). It passes **53** focused domain checks only on exact presence-aware predecessor SHA `473e8fa2601d75eab8a223edda53555c51ce145c6426e570df9ae918c3f9eee0`, `nfl-data-presence-v2`. Its applicability check refuses main, which lacks that prerequisite. It preserves fractional nonnegative expectations, signed yards, negative fantasy points, zero and unknowns. It is not part of the main diff and does not establish a universal malformed-count contract for the raw game rollup or TD helper.

**Pending Phase 2 assembly reconstruction, independent of main correction**

The pending checkout is still e415912b9c3d3ff52e8f435517af02e794d97fa4. Exact missing retained source is recovered under [phase2/recovered-files](/workspace/nfl-system-audit/current-production-corrections/phase2/recovered-files), from **315be5e86a1a3a93022b68c453739076487e2077**. This is a separate proposed assembly input, never installed into the active writer's checkout.

| Missing source path | Exact recovered SHA-256 |
| --- | --- |
| `config/weekly-derived-selected-policy-v2.json` | `45e51a07a077ce0aedede608fcef2ddb3592828a0734843d37a3991e6673a546` |
| `output/weekly-adaptive-overlay.js` | `d6657e82639aa001f64701672e25cc72bd6e55142127669a59396f9efe485a68` |
| `schemas/weekly-derived-selected-feed-v2.json` | `68709b6cb3d9a420835fcd74ee5dd5392ae83c36f54cce985fcd0fa47c372db5` |
| `schemas/weekly-derived-selected-feed-v1.json` | `831604c59ab80d979620b935ab50496d6f28ff989849141749b31a6a788c20f8` |
| `config/weekly-derived-selected-policy-v1.json` | `0bcdf8505d2f0d268ea97e5c17c26f2a8d7cb91ef2e089cd9e410f27eb36f1ae` |

The V1 schema is an additional exposed prerequisite: once the missing V2 schema is restored, its actual retained test reads V1 to check row-contract preservation. The V1 policy is supplied as the retained historical companion, without claiming it caused the previously observed failures. **Do not substitute main's newer e8e037 policy for Phase 2's immutable 45e51 policy.** They are different exact registrations.

On the disposable reconstructed source, the actual 33 retained Phase 2 integration/publication tests report **26 passed, 7 failures, 0 errors**. All **12 V3 binding/static tests pass**. The seven remaining failures all retain the exact `CurrentStaticPortChecks.metadata()` assertion requiring one hourly `--feed-policy-sha256` invocation; the installed Phase 2 workflow has zero. The initial three-file reconstruction exposed the missing V1 schema as one error; restoring its exact retained bytes removes that error without changing assertions. This is not the 1,180-test Phase 2 suite or a green release assembly. See [phase2-reconstructed-static.log](/workspace/nfl-system-audit/current-production-corrections/evidence/phase2-reconstructed-static.log).

The installed `.github/workflows/prepare-diagnostic-seed.yml` contains the **30,854-byte** raw controller SHA `2ee6d870c3bb6c8e667eae3a49cadf22220d6ab21d0c990c8035332d1deadfaf`. The retained source and saved CODEX_RESULT comments require these **uninstalled** proposal identities:

| Exact absent proposal | Required SHA-256 |
| --- | --- |
| Full `.github/workflows/hourly.yml` | `c06a283d1e48414129c0e57adeaf0ea718d47d203aefabee5652e1e084adfbd3` |
| Full `.github/workflows/prepare-diagnostic-seed.yml` | `78ada1900f8147d3a9d2a3d6c9ec46d40a302946f00082cc614dafa1544f0da8` |
| Its **35,468-byte** raw inline controller | `2f4d7f7eac10c4c82a56762929e5d3d8f853493f5b01edbee2925adf158b501e` |

Read-only search covered **33 retained workflow-changing commits / 30 distinct workflow bodies**, including extraction/hashing of their inline controllers, plus local source exports and retained PR comments. No target matched. Comments 6391031941 and 6391181916 assert that their prior actor could reconstruct the complete workflows from retained inputs; the available exports contain the target digests/status, not those workflow bodies or a complete deterministic recipe. The unavoidable absent input here is **the exact two proposed workflow bodies, or the complete authenticated recipe plus its retained base inputs**. A SHA cannot reconstruct those absent bytes. Do not publish a guessed controller, relax its 35,468-byte/hash assertions, or treat the legacy controller as the modern proposal.

The website-only V3 policy is constructible from its immutable historical policy plus a final integrated code map and recognized current-execution contract, as the passing actual V3 tests demonstrate. The exact prior physical candidate body/digest is absent here; a newly derived policy must be labeled and bound to the parent's final integrated source. It cannot be copied from e415912 onto the different main correction. [phase2/reconstruction.json](/workspace/nfl-system-audit/current-production-corrections/phase2/reconstruction.json) preserves the exact source/target identities and search scope.

Main correction integration does not depend on completing all Phase 2 assembly or operating acceptance. Its remaining publication prerequisite is the parent's distinct execution/R0/cache binding and final-source acceptance. Verify the package with `python3 -B current-production-corrections/verification/verify_manifest.py`. If the active writer produces another source preimage, regenerate/reconcile these corrections against that actual head and rerun the relevant combined-source checks; this 89512ed evidence does not certify different bytes.
