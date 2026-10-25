"""Fictional genuine-mode bridge: no HTTP, NFL data, fitting or remote writes."""
from contextlib import ExitStack, redirect_stdout
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import io
import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

from nfl_lab import audit_count_requalify_v1 as audit, operational_failure_v1 as failure, private_draft_store as store
from nfl_lab.operational_storage import OperationalStorage
from tools import audit_count_failure_v1 as bridge
from test_private_draft_store_v2 import Server, Response, RUN, SOURCE
from test_owner_private_bootstrap import qualification

ROOT = Path(__file__).resolve().parents[1]
PINS = ["tools/audit_count_hosted_v1.py", "tools/audit_count_requalify_v1.py",
        "nfl_lab/audit_count_requalify_v1.py", "nfl_lab/weekly_future_inference.py", ".github/workflows/lab.yml",
        "nfl_lab/audit_count_checkpoint_v1.py", "tools/audit_count_checkpoint_v1.py", "tools/audit_count_failure_v1.py",
        "nfl_lab/operational_failure_v1.py", "tools/operational_failure_v1.py",
        "tools/audit_count_verification_receipt_v1.py"]


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.checkout = self.base / "fictional-checkout"
        self.runner = self.base / "runner"
        self.runner.mkdir()
        self.server = Server()
        self.phase = "record"
        self.bad_steps = False
        self.checkpoint_failed = False
        self.base_client = store.Client
        initial_journal = self.base / "initial-journal"
        initial_journal.mkdir(mode=0o700)
        initial = self.base_client("ghs_FICTIONAL", RUN, journal=initial_journal, source_sha=SOURCE,
                                   transport=self.server, process="9" * 64)
        self.binding = store.initialize(initial, "c" * 32)
        self.qualification = qualification(self.binding)
        self.server.calls.clear()
        self.policy_body = (ROOT / "config/operational-source-policy-v2.json").read_bytes()
        for name in PINS:
            path = self.checkout / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(("FICTIONAL REVIEWED SOURCE " + name).encode())
        self.write("config/operational-source-policy-v2.json", self.policy_body)
        self.pending = dict(schema_version="weekly-private-POST-reservation-v2", key="asset:manifest-" + "d"*64 + ".json",
            bytes=100, sha256="d"*64, name="manifest-" + "d"*64 + ".json")
        self.write("config/gha-private-checkpoint-v3.json", store.canonical(dict(
            canary_report="reports/private-draft-canary-v2/ACTUAL_HOSTED_RESULT.json", source_policy_sha256=bridge.checkpoint.POLICY_SHA,
            binding_sha256=store.sha(store.canonical(self.binding)), qualification_sha256=store.sha(store.canonical(self.qualification)),
            canary_source_sha=SOURCE, external_pending_reservations=[self.pending])))
        self.write("reports/private-draft-canary-v2/ACTUAL_HOSTED_RESULT.json", store.canonical(dict(
            binding=self.binding, qualification=self.qualification, source_sha=SOURCE)))
        self.original = self.runner / (audit.VERSION + "-" + RUN)
        self.storage = OperationalStorage(self.original / "cache", json.loads(self.policy_body), state=self.original / "state")
        self.storage.register_root(self.original)
        now = datetime.now(timezone.utc)
        self.started = now - timedelta(minutes=2)
        self.completed = now - timedelta(minutes=1)
        self.writer_done = self.completed + timedelta(seconds=2)
        event = self.base / "event.json"
        event.write_bytes(store.canonical(dict(repository=dict(full_name=store.REPO), inputs=dict(mode=audit.MODE))))
        output = self.base / "github-output"
        output.touch(mode=0o600)
        self.env = dict(GITHUB_ACTIONS="true", GITHUB_REPOSITORY=store.REPO, GITHUB_EVENT_NAME="workflow_dispatch",
            GITHUB_RUN_ATTEMPT="1", STORE_PERMISSION="write", GITHUB_RUN_ID=RUN, GITHUB_SHA=SOURCE,
            GITHUB_JOB=audit.RESTORE_JOB, GITHUB_ACTOR="NickNicky19", GITHUB_ACTOR_ID="208912933",
            GITHUB_WORKFLOW_REF=bridge.hosted.WORKFLOW_REF,
            GITHUB_EVENT_PATH=str(event), GITHUB_TOKEN="ghs_FICTIONAL", RUNNER_TEMP=str(self.runner),
            GITHUB_OUTPUT=str(output), AUDIT_COUNT_WRITER_OUTCOME="failure", AUDIT_COUNT_STARTED_AT_UTC=self.started.isoformat())
        self.root_go = dict(schema_version="audit-count-root-GO-v1", approved=True, repository=store.REPO,
            source_sha=SOURCE, workflow_ref=self.env["GITHUB_WORKFLOW_REF"], job_id=audit.RESTORE_JOB,
            single_writer_group="nfl-lab-single-writer", issued_at_utc=(now-timedelta(minutes=5)).isoformat(),
            expires_at_utc=(now+timedelta(minutes=20)).isoformat(), operation=bridge.hosted.OPERATION,
            maximum_new_fits=0, protected_outcome_reads=0, publication=False,
            helper_sha256={name:store.sha((self.checkout/name).read_bytes()) for name in PINS},
            owner_authorization="OWNER_NFL_AUDIT_CONTINUATION_20261025")
        self.seal()

    def tearDown(self):
        self.temp.cleanup()

    def write(self, name, body):
        path = self.checkout / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)

    def seal(self):
        body = store.canonical(self.root_go)
        self.env.update(AUDIT_COUNT_ROOT_GO_JSON=body.decode(), AUDIT_COUNT_ROOT_GO_SHA256=store.sha(body))
        event_path = Path(self.env["GITHUB_EVENT_PATH"])
        event = json.loads(event_path.read_bytes())
        event["inputs"].update(inference_builder_go_json=body.decode(), inference_builder_go_sha256=store.sha(body))
        event_path.write_bytes(store.canonical(event))

    def job_context(self, env, permission):
        return dict(execution_lane="github_actions", workflow_ref=env["GITHUB_WORKFLOW_REF"], workflow_sha=env["GITHUB_SHA"],
            job_id=env["GITHUB_JOB"], permission=permission, event_name="workflow_dispatch", api_job_id=0, run_authenticated=False)

    def api(self, req, timeout):
        if "/jobs?per_page=100&page=1" not in req.full_url:
            return self.server(req, timeout)
        self.server.calls.append(req)
        writer = dict(id=777, name=audit.RESTORE_JOB, run_id=int(RUN), head_sha=SOURCE,
            status="in_progress" if self.phase == "record" else "completed", conclusion=None if self.phase == "record" else "failure",
            started_at=(self.started-timedelta(seconds=2)).isoformat(), completed_at=self.writer_done.isoformat(),
            steps=[] if self.bad_steps else [dict(number=6, name=bridge.CHECKPOINT_STEP if self.checkpoint_failed else bridge.WRITER_STEP,
                status="completed", conclusion="failure",
                started_at=min(self.started+timedelta(seconds=1), self.completed).isoformat(), completed_at=self.completed.isoformat())])
        jobs = [writer]
        if self.phase == "restore":
            jobs.append(dict(id=778, name=bridge.hosted.READER_JOB, run_id=int(RUN), head_sha=SOURCE, status="in_progress"))
        return Response(dict(total_count=len(jobs), jobs=jobs))

    def execute(self, phase="record", env=None, *, alias=False):
        env = self.env if env is None else env
        self.phase = phase
        def client(*args, **kwargs):
            kwargs.update(transport=self.api, process="4"*64 if phase == "record" else "5"*64)
            return self.base_client(*args, **kwargs)
        output = io.StringIO()
        with ExitStack() as stack:
            stack.enter_context(patch.object(bridge, "ROOT", self.checkout))
            stack.enter_context(patch.object(bridge.hosted, "ROOT", self.checkout))
            def git_metadata(command, **unused):
                if command[:3] == ["git", "rev-parse", "HEAD"]:
                    return SOURCE+"\n"
                if command[:2] == ["git", "status"]:
                    return ""
                raise AssertionError("unexpected fictional metadata command")
            stack.enter_context(patch.object(bridge.hosted.subprocess, "check_output", side_effect=git_metadata))
            stack.enter_context(patch.object(bridge, "actions_context", side_effect=self.job_context))
            stack.enter_context(patch.object(bridge, "limits"))
            stack.enter_context(patch.object(bridge.store, "Client", side_effect=client))
            stack.enter_context(redirect_stdout(output))
            code = bridge.main(["append" if alias else phase, "--execute"], environ=env)
        if phase == "record":
            self.writer_done = datetime.now(timezone.utc)
        return code, json.loads(output.getvalue()), output.getvalue()

    def result_handoff(self):
        pairs = dict(line.split("=",1) for line in Path(self.env["GITHUB_OUTPUT"]).read_text().splitlines())
        self.assertEqual(pairs["failure_appended"], "true")
        self.assertEqual(store.sha(pairs["failure_handoff_json"].encode()), pairs["failure_handoff_sha256"])
        self.assertLessEqual(len(pairs["failure_handoff_json"].encode()), bridge.HANDOFF_CAP)
        return pairs

    def posts(self):
        return [r for r in self.server.calls if r.method == "POST"]

    def unpack_count(self):
        path = self.runner/(bridge.VERSION+"-"+RUN)/"evidence/FAILURE.json.gz"
        request, values = failure.unpack(path.read_bytes())
        by_label = dict(zip((item["label"] for item in request["attachments"]), values))
        status = json.loads(by_label.pop(bridge.COUNT_FAILURE_CONTRACT["status_label"]))
        self.assertEqual(len(status["controls"]), 10)
        return request, list(by_label.values()), status

    def test_empty_original_control_set_still_appends_and_restores_failed_evidence(self):
        code, status, _ = self.execute()
        self.assertEqual(code, 0, status)
        self.assertEqual(status["original_state"], "FAILED")
        self.assertFalse(status["failure_evidence_durable"])
        pairs = self.result_handoff()
        self.assertEqual(len(self.posts()), 2)
        request, bodies, controls = self.unpack_count()
        self.assertEqual(bodies, [])
        self.assertTrue(all(row["state"] == "ABSENT" for row in controls["controls"]))
        self.assertIsNone(request["failure"]["exit_code"])
        self.assertEqual(request["clocks"]["started_at_utc"], self.env["AUDIT_COUNT_STARTED_AT_UTC"])
        reader = dict(self.env, GITHUB_JOB=bridge.hosted.READER_JOB,
            AUDIT_COUNT_FAILURE_HANDOFF_JSON=pairs["failure_handoff_json"],
            AUDIT_COUNT_FAILURE_HANDOFF_SHA256=pairs["failure_handoff_sha256"])
        code, status, _ = self.execute("restore", reader)
        self.assertEqual(code, 0, status)
        self.assertTrue(status["failure_evidence_durable"])
        self.assertEqual(status["original_state"], "FAILED")
        self.assertFalse(any(status[k] for k in failure.NEGATIVE_GATES))
        self.assertEqual(len(self.posts()), 2)

    def test_owned_original_failure_is_opaque_and_partial_can_never_qualify(self):
        opaque = b'PRIVATE original exception https://private.invalid/secret token=DO_NOT_PRINT'
        self.storage.write_bytes(self.original/"REQUALIFICATION_FINISHED.json", opaque)
        self.env["AUDIT_COUNT_WRITER_EXIT_CODE"] = "1"
        code, status, text = self.execute()
        self.assertEqual(code, 0, status)
        self.assertEqual(status["original_state"], "PARTIAL")
        request, bodies, _ = self.unpack_count()
        self.assertEqual(bodies, [opaque])
        self.assertEqual(request["failure"]["exit_code"], 1)
        self.assertNotIn("DO_NOT_PRINT", text)
        self.assertFalse(any(status[k] for k in failure.NEGATIVE_GATES))
        self.assertNotIn("DO_NOT_PRINT", self.result_handoff()["failure_handoff_json"])
        self.assertEqual(self.env["AUDIT_COUNT_WRITER_OUTCOME"], "failure")

    def test_unowned_original_partial_file_is_retained_with_empty_attachments(self):
        path = self.original/"REQUALIFICATION_FINISHED.json"
        path.write_bytes(b"FICTIONAL interrupted not-yet-owned control")
        code, status, _ = self.execute()
        self.assertEqual(code, 0, status)
        self.assertEqual(path.read_bytes(), b"FICTIONAL interrupted not-yet-owned control")
        request, bodies, controls = self.unpack_count()
        self.assertEqual(request["state"], "FAILED")
        self.assertEqual(bodies, [])
        original = next(row for row in controls["controls"] if row["label"] == "requalification_finished-json")
        self.assertEqual(original["state"], "UNOWNED")
        self.assertEqual(original["sha256"], store.sha(path.read_bytes()))

    def test_false_outcome_or_unmatched_start_cannot_fabricate_failure(self):
        self.env["AUDIT_COUNT_WRITER_OUTCOME"] = "success"
        code, status, _ = self.execute()
        self.assertEqual(code, 1)
        self.assertEqual(status["reason"], "ORIGINAL_FAILED_STEP_REQUIRED")
        self.assertFalse(self.server.calls)

    def test_actual_step_API_metadata_is_required_no_retry_on_missing_step(self):
        self.bad_steps = True
        code, status, _ = self.execute()
        self.assertEqual(code, 1)
        self.assertEqual(status["reason"], "UNAMBIGUOUS_ACTUAL_FAILED_STEP_REQUIRED")
        self.assertFalse(self.posts())
        code, status, _ = self.execute()
        self.assertEqual(status["reason"], "ONE_FAILURE_BRIDGE_INVOCATION_NO_RETRY")

    def test_ambiguous_POST_retains_private_reservation_without_public_handoff_or_retry(self):
        self.server.ambiguous = True
        code, status, text = self.execute()
        self.assertEqual(code, 1)
        self.assertEqual(len(self.posts()), 1)
        self.assertEqual(Path(self.env["GITHUB_OUTPUT"]).read_text(), "")
        root = self.runner/(bridge.VERSION+"-"+RUN)
        self.assertTrue((root/"evidence/APPEND_FAILED.json").exists())
        self.assertGreaterEqual(len(list((root/"journal").glob("*.reservation.json"))), 2)
        code, status, _ = self.execute()
        self.assertEqual(len(self.posts()), 1)
        self.assertEqual(status["reason"], "ONE_FAILURE_BRIDGE_INVOCATION_NO_RETRY")
        self.assertNotIn("secret URL/token", text)

    def test_root_helper_pin_expiry_and_owner_identity_remain_strict(self):
        for mutation in (lambda g:g["helper_sha256"].update({"tools/audit_count_failure_v1.py":"0"*64}),
                         lambda g:g.update(approved=False), lambda g:g.update(extra=True),
                         lambda g:g.update(expires_at_utc=g["issued_at_utc"])):
            original = deepcopy(self.root_go)
            mutation(self.root_go)
            self.seal()
            code, status, _ = self.execute()
            self.assertEqual(code, 1)
            self.assertFalse(self.server.calls)
            self.root_go = original
        self.seal()
        self.env["GITHUB_ACTOR_ID"] = "1"
        code, status, _ = self.execute()
        self.assertEqual(code, 1)
        self.assertEqual(status["reason"], "EXACT_OWNER_SOURCE_CONTEXT")

    def test_archived_qualification_and_pending_reservations_are_bound(self):
        wrong = json.loads((self.checkout/"reports/private-draft-canary-v2/ACTUAL_HOSTED_RESULT.json").read_bytes())
        wrong["qualification"]["engineering_boundary_v2"] = False
        self.write("reports/private-draft-canary-v2/ACTUAL_HOSTED_RESULT.json", store.canonical(wrong))
        code, status, _ = self.execute()
        self.assertEqual(code, 1)
        self.assertEqual(status["reason"], "EXACT_ARCHIVED_QUALIFIED_RUNTIME")
        self.assertFalse(self.server.calls)

    def test_tampered_handoff_fails_before_any_reader_HTTP(self):
        code, status, _ = self.execute()
        self.assertEqual(code, 0, status)
        pairs = self.result_handoff()
        calls = len(self.server.calls)
        reader = dict(self.env, GITHUB_JOB=bridge.hosted.READER_JOB,
            AUDIT_COUNT_FAILURE_HANDOFF_JSON=pairs["failure_handoff_json"]+" ",
            AUDIT_COUNT_FAILURE_HANDOFF_SHA256=pairs["failure_handoff_sha256"])
        code, status, _ = self.execute("restore", reader)
        self.assertEqual(code, 1)
        self.assertEqual(status["reason"], "EXACT_SAFE_FAILURE_HANDOFF_HASH")
        self.assertEqual(len(self.server.calls), calls)

    def test_checkpoint_failure_imports_original_actual_pending_journal_and_accepts_append_alias(self):
        self.checkpoint_failed = True
        self.env.update(AUDIT_COUNT_WRITER_OUTCOME="success", AUDIT_COUNT_CHECKPOINT_OUTCOME="failure",
                        AUDIT_COUNT_CHECKPOINT_EXIT_CODE="1")
        self.storage.write_bytes(self.original/"REQUALIFICATION_FINISHED.json", b"FICTIONAL effective result; private only")
        journal = self.original/"private-journal"
        journal.mkdir(mode=0o700)
        pending = dict(schema_version="weekly-private-POST-reservation-v2", key="asset:blob-"+"e"*64+".bin",
                       bytes=1000, sha256="e"*64, name="blob-"+"e"*64+".bin")
        bridge.checkpoint.seed_pending(journal, [pending])
        code, status, _ = self.execute(alias=True)
        self.assertEqual(code, 0, status)
        self.assertEqual(status["original_state"], "PARTIAL")
        self.assertFalse(status["successful_forecast"])
        pairs = self.result_handoff()
        self.assertIn(pending, json.loads(pairs["failure_handoff_json"])["pending_reservations"])
        original, _ = failure.unpack((self.runner/(bridge.VERSION+"-"+RUN)/"evidence/FAILURE.json.gz").read_bytes())
        self.assertEqual(original["failure"]["exit_code"], 1)
        self.assertEqual(self.env["AUDIT_COUNT_CHECKPOINT_OUTCOME"], "failure")

    def test_runtime_quota_failure_keeps_original_envelope_and_never_POSTs(self):
        for i in range(4):
            self.server.add("fictional-unknown-"+str(i), size=store.ASSET_CAP if i < 3 else store.ASSET_CAP-117-1024)
        code, status, _ = self.execute()
        self.assertEqual(code, 1)
        self.assertEqual(status["reason"], "FAILURE_COMPLETE_APPEND_REMOTE_CAP")
        self.assertFalse(self.posts())
        self.assertEqual(Path(self.env["GITHUB_OUTPUT"]).read_text(), "")
        self.assertTrue((self.runner/(bridge.VERSION+"-"+RUN)/"evidence/FAILURE.json.gz").exists())

    def test_environment_root_GO_must_equal_actual_dispatch_input(self):
        event_path = Path(self.env["GITHUB_EVENT_PATH"])
        event = json.loads(event_path.read_bytes())
        event["inputs"]["inference_builder_go_sha256"] = "0"*64
        event_path.write_bytes(store.canonical(event))
        code, status, _ = self.execute()
        self.assertEqual(code, 1)
        self.assertEqual(status["reason"], "EXACT_NEW_ACTIONS_MODE")
        self.assertFalse(self.server.calls)

    def test_original_microsecond_start_is_not_rounded_to_API_second_precision(self):
        # GitHub can report completion at the same integer second in which the
        # preceding start step emitted a later fractional timestamp.
        self.started = datetime.now(timezone.utc).replace(microsecond=600000) - timedelta(seconds=3)
        self.completed = self.started.replace(microsecond=0)
        self.env["AUDIT_COUNT_STARTED_AT_UTC"] = self.started.isoformat()
        code, status, _ = self.execute()
        self.assertEqual(code, 0, status)
        request, _ = failure.unpack((self.runner/(bridge.VERSION+"-"+RUN)/"evidence/FAILURE.json.gz").read_bytes())
        self.assertEqual(request["clocks"]["started_at_utc"], self.started.isoformat())
        self.assertEqual(request["clocks"]["original"]["github_step_completed_at_utc"], self.completed.isoformat())
        self.assertGreater(store.utc(request["clocks"]["observed_at_utc"]), self.started)

    def test_exact_private_child_status_and_stderr_survive_without_public_errors(self):
        package = self.runner/("audit-count-package-"+RUN)
        package.mkdir(mode=0o700)
        original = b'{"state":"FAILED_RETAINED","reason":"FICTIONAL_ORIGINAL_FAILURE"}'
        errors = b"FICTIONAL private exception /tmp/private-path token=NEVER_LOG"
        (package/"restore-STATUS.json").write_bytes(original)
        (package/"restore-STATUS.stderr").write_bytes(errors)
        code, status, output = self.execute()
        self.assertEqual(code, 0, status)
        request, bodies, _ = self.unpack_count()
        self.assertEqual(bodies, [original, errors])
        self.assertEqual(request["state"], "FAILED")
        self.assertEqual((package/"restore-STATUS.json").read_bytes(), original)
        self.assertEqual((package/"restore-STATUS.stderr").read_bytes(), errors)
        self.assertNotIn("NEVER_LOG", output)
        self.assertNotIn("FICTIONAL_ORIGINAL_FAILURE", self.result_handoff()["failure_handoff_json"])

    def test_COUNT_reserve_is_shared_and_general_SYS006_caps_are_unchanged(self):
        shared = bridge.count_checkpoint
        self.assertIs(bridge.COUNT_FAILURE_CONTRACT, shared.COUNT_FAILURE_CONTRACT)
        self.assertEqual(bridge.COUNT_FAILURE_CONTRACT_SHA256, shared.COUNT_FAILURE_CONTRACT_SHA256)
        self.assertEqual(bridge.COUNT_FAILURE_CONTRACT["original_controls_bytes"], 512 << 10)
        self.assertEqual(bridge.COUNT_FAILURE_PACKAGE_CAP, 1 << 20)
        self.assertEqual(bridge.COUNT_FAILURE_RESERVE_BYTES, (1 << 20) + (16 << 10))
        self.assertEqual(bridge.COUNT_FAILURE_RESERVE_SLOTS, 2)
        self.assertEqual(failure.ATTACHMENTS_CAP, 4 << 20)
        self.assertGreater(failure.PACKAGE_CAP, bridge.COUNT_FAILURE_PACKAGE_CAP)

    def test_all_ten_original_controls_at512KiB_are_full_and_envelope_fits_reserve_before_POST(self):
        generator = random.Random(193)
        cap = bridge.COUNT_FAILURE_CONTRACT["original_controls_bytes"]
        sizes = [cap//10]*9 + [cap-9*(cap//10)]
        package = self.runner/("audit-count-package-"+RUN)
        package.mkdir(mode=0o700)
        originals = []
        for index, name in enumerate(bridge.CONTROLS + bridge.PHASE_CONTROLS):
            body = generator.randbytes(sizes[index])
            originals.append(body)
            if index < len(bridge.CONTROLS):
                self.storage.write_bytes(self.original/name, body)
            else:
                (package/name).write_bytes(body)
        # Metadata represents24MiB retained plus5.2MiB new effective models.
        total = (24 << 20) + int(5.2*(1 << 20))
        remaining = total-117
        for index in range(4):
            size = min(store.ASSET_CAP, remaining)
            if size:
                self.server.add("fictional-existing-"+str(index), size=size)
            remaining -= size
        actual_api = self.api
        posted_sizes = []
        def verify_before_POST(req, timeout):
            if req.method == "POST" and "name=blob-" in req.full_url:
                self.assertLessEqual(len(req.data), bridge.COUNT_FAILURE_PACKAGE_CAP)
                request, values = failure.unpack(req.data)
                status_bytes = dict(zip((a["label"] for a in request["attachments"]), values))[bridge.COUNT_FAILURE_CONTRACT["status_label"]]
                bridge.count_checkpoint.validate_count_failure_variant(request, json.loads(status_bytes), req.data)
                posted_sizes.append(len(req.data))
            return actual_api(req, timeout)
        with patch.object(self, "api", side_effect=verify_before_POST):
            code, status, _ = self.execute()
        self.assertEqual(code, 0, status)
        self.assertEqual(status["archived_original_control_bytes"], cap)
        self.assertTrue(status["original_control_bodies_complete"])
        self.assertFalse(status["control_bound_exceeded"])
        self.assertEqual(len(posted_sizes), 1)
        request, values, controls = self.unpack_count()
        self.assertEqual(values, originals)
        self.assertTrue(all(row["state"] == "ATTACHED" for row in controls["controls"]))
        self.assertEqual(sum(a["reference"]["bytes"] for a in request["attachments"] if a["kind"] == "original_failure"), cap)

    def test_aggregate_required_controls_over_bound_preserve_full_hash_census_and_original_failure(self):
        bodies = [b"FICTIONAL_A"*(30000), b"FICTIONAL_B"*(30000)]
        for name, value in zip(("RESTORE_RECEIPT.json", "REQUALIFICATION_FINISHED.json"), bodies):
            self.storage.write_bytes(self.original/name, value)
        self.env["AUDIT_COUNT_WRITER_EXIT_CODE"] = "1"
        code, status, _ = self.execute()
        self.assertEqual(code, 0, status)
        self.assertTrue(status["control_bound_exceeded"])
        self.assertFalse(status["original_control_bodies_complete"])
        self.assertEqual(status["archived_original_control_bytes"], 0)
        self.assertLessEqual(status["failure_package_bytes"], bridge.COUNT_FAILURE_PACKAGE_CAP)
        request, values, controls = self.unpack_count()
        self.assertEqual(values, [])  # No success-only subset or truncation.
        self.assertEqual(request["failure"]["code"], "ORIGINAL_HOSTED_COUNT_STEP_FAILED")
        self.assertEqual(request["failure"]["exit_code"], 1)
        rows = [row for row in controls["controls"] if row["state"] == "BOUND_EXCEEDED"]
        self.assertEqual(len(rows), 2)
        self.assertEqual({(row["bytes"], row["sha256"]) for row in rows}, {(len(value), store.sha(value)) for value in bodies})
        for name, value in zip(("RESTORE_RECEIPT.json", "REQUALIFICATION_FINISHED.json"), bodies):
            self.assertEqual((self.original/name).read_bytes(), value)
        pairs = self.result_handoff()
        reader = dict(self.env, GITHUB_JOB=bridge.hosted.READER_JOB,
            AUDIT_COUNT_FAILURE_HANDOFF_JSON=pairs["failure_handoff_json"],
            AUDIT_COUNT_FAILURE_HANDOFF_SHA256=pairs["failure_handoff_sha256"])
        code, restored, _ = self.execute("restore", reader)
        self.assertEqual(code, 0, restored)
        self.assertTrue(restored["failure_evidence_durable"])
        self.assertTrue(restored["control_bound_exceeded"])
        self.assertFalse(restored["original_control_bodies_complete"])
        self.assertFalse(any(restored[k] for k in failure.NEGATIVE_GATES))

    def test_one_oversized_private_control_is_hashed_whole_and_explicitly_guarded(self):
        package = self.runner/("audit-count-package-"+RUN)
        package.mkdir(mode=0o700)
        value = random.Random(51).randbytes((1 << 20)+17)
        original = package/"restore-STATUS.stderr"
        original.write_bytes(value)
        code, status, output = self.execute()
        self.assertEqual(code, 0, status)
        self.assertTrue(status["control_bound_exceeded"])
        request, values, controls = self.unpack_count()
        self.assertEqual(values, [])
        row = next(row for row in controls["controls"] if row["label"] == "phase-restore-status-stderr")
        self.assertEqual(row, dict(label="phase-restore-status-stderr", state="BOUND_EXCEEDED", bytes=len(value), sha256=store.sha(value)))
        self.assertEqual(original.read_bytes(), value)
        self.assertFalse(status["successful_forecast"])
        self.assertNotIn(str(original), output)

    def test_actual_oversized_encoded_package_guard_runs_before_any_POST(self):
        validate = bridge.count_checkpoint.validate_count_failure_variant
        def reject_encoded(request, status, body=None):
            if body is not None:
                raise store.StoreError("COUNT_FAILURE_ENCODED_PAYLOAD_CAP")
            return validate(request, status, body)
        with patch.object(bridge.count_checkpoint, "validate_count_failure_variant", side_effect=reject_encoded):
            code, status, _ = self.execute()
        self.assertEqual(code, 1)
        self.assertEqual(status["reason"], "COUNT_FAILURE_ENCODED_PAYLOAD_CAP")
        self.assertFalse(self.posts())
        self.assertTrue((self.runner/(bridge.VERSION+"-"+RUN)/"evidence/ATTEMPT.json").exists())

    def test_preparation_reads_neither_environment_nor_credentials(self):
        class NoEnvironment:
            def get(self, *args):
                raise AssertionError("environment accessed")
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(bridge.main([], environ=NoEnvironment()), 2)
        self.assertEqual(json.loads(output.getvalue())["state"], "PREPARATION_ONLY_NO_IO")


if __name__ == "__main__":
    unittest.main()
