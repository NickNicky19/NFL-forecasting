"""SYS006 fictionals: opaque bytes, invented clocks and in-memory HTTP only."""
import base64
from contextlib import redirect_stdout
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import gzip
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from nfl_lab import operational_failure_v1 as f, private_draft_store as s
from nfl_lab.operational_storage import OperationalStorage, StorageQuotaError, StorageIntegrityError
from tools import operational_failure_v1 as cli
from test_private_draft_store_v2 import Server, Response, RUN, SOURCE
from test_owner_private_bootstrap import qualification

ROOT = Path(__file__).resolve().parents[1]
WRITER, READER = "fictional_failure_writer", "fictional_failure_reader"


class FailureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.policy = json.loads((ROOT / "config/operational-source-policy-v2.json").read_bytes())
        self.storage = OperationalStorage(self.base / "cache", self.policy, state=self.base / "state")
        self.storage.register_root(self.base)
        self.journal = self.base / "journal"
        self.journal.mkdir(mode=0o700)
        self.server = Server()
        initial = s.Client("ghs_FICTIONAL", RUN, journal=self.journal, source_sha=SOURCE,
                           transport=self.server, process="9" * 64)
        self.binding = s.initialize(initial, "c" * 32)
        self.qualification = qualification(self.binding)
        self.server.calls.clear()
        self.completed = False
        self.started = datetime.now(timezone.utc) - timedelta(minutes=3)
        self.observed = self.started + timedelta(seconds=30)
        self.output = self.base / "failure"

    def tearDown(self):
        self.temp.cleanup()

    def client(self, name=WRITER, process="4" * 64, operation="append", transport=None):
        job = dict(execution_lane="github_actions", workflow_ref=s.REPO + "/.github/workflows/lab.yml@refs/heads/fictional",
                   workflow_sha=SOURCE, job_id=name, permission="write", event_name="workflow_dispatch",
                   api_job_id=0, run_authenticated=False)
        def api(req, timeout):
            if "/jobs?per_page=100&page=1" in req.full_url:
                self.server.calls.append(req)
                jobs = [dict(id=777 if name == WRITER else 778 if name == READER else 779,
                             name=name, status="in_progress", run_id=int(RUN), head_sha=SOURCE)]
                if self.completed:
                    jobs.append(dict(id=777, name=WRITER, status="completed", conclusion="failure",
                        run_id=int(RUN), head_sha=SOURCE, started_at=(self.started - timedelta(seconds=1)).isoformat(),
                        completed_at=(self.observed + timedelta(seconds=1)).isoformat()))
                return Response(dict(total_count=len(jobs), jobs=jobs))
            return (transport or self.server)(req, timeout)
        return s.Client("ghs_FICTIONAL", RUN, journal=self.journal, source_sha=SOURCE,
                        transport=api, process=process, job=job, operation=operation)

    def request(self, state="FAILED", kind="INTERRUPTION", body=b"FICTIONAL original SIGKILL and opaque partial bytes\x00\xff"):
        path = self.base / "original.bin"
        self.storage.write_bytes(path, body)
        ref = dict(path=str(path), bytes=len(body), sha256=s.sha(body))
        return dict(schema_version=f.VERSION + "-request", attempt=dict(repository=s.REPO, run_id=RUN, run_attempt=1,
            source_sha=SOURCE, job_id=WRITER, workflow_ref=s.REPO + "/.github/workflows/lab.yml@refs/heads/fictional"),
            operation="producer", state=state, input_contract_sha256="d" * 64,
            failure=dict(kind=kind, code="ORIGINAL_PROCESS_INTERRUPTED", exit_code=137),
            clocks=dict(started_at_utc=self.started.isoformat(), observed_at_utc=self.observed.isoformat(),
                original=dict(training_cutoff_utc="2026-08-01T00:00:00Z", input_cutoff_utc="2026-10-25T00:00:00Z",
                    weekly_decision_cutoff_utc="2026-10-24T00:00:00+00:00")),
            attachments=[dict(label="original-failure", kind="original_failure", reference=ref)])

    def record(self, **kw):
        request = self.request(**kw)
        result = f.record_failure(request, self.storage, self.output)
        return request, result

    def go(self, client, operation="append", descriptor=None):
        inputs = dict(binding=s.canonical(self.binding))
        if operation == "append":
            inputs.update(payload_manifest=s.read_local(self.output / "PAYLOAD.json", f.METADATA_CAP),
                          qualification=s.canonical(self.qualification))
        else:
            inputs["descriptor"] = s.canonical(descriptor)
        go = dict(schema_version="weekly-private-operation-GO-v2.1", approved=True, operation=operation,
            repository=s.REPO, run_id=RUN, source_sha=SOURCE, config_sha256=s.config_sha(),
            scope_manifest_sha256=s.sha(s.canonical(f.document(inputs["payload_manifest"]))) if operation == "append" else None,
            qualification_sha256=s.sha(s.canonical(self.qualification)) if operation == "append" else None,
            single_writer_group="nfl-lab-single-writer", runtime_id=self.binding["runtime_id"],
            input_sha256={k:s.sha(v) for k,v in inputs.items()}, job_id=client.job["job_id"], workflow_ref=client.job["workflow_ref"])
        body = s.canonical(go)
        return dict(authorization=body, authorization_sha256=s.sha(body), inputs=inputs)

    def append(self, client=None):
        client = client or self.client()
        return f.append_failure(client, self.storage, self.output, **self.go(client))

    def restore(self, appended, *, process="5" * 64, transport=None):
        self.completed = True
        client = self.client(READER, process, "restore", transport=transport)
        result = f.restore_failure(client, self.storage, self.base / "restored",
            **self.go(client, "restore", appended["descriptor"]))
        return result, client

    def posts(self):
        return [r for r in self.server.calls if r.method == "POST"]

    def test_interruption_preserves_exact_original_failure_and_clocks(self):
        request, status = self.record()
        original, attachments = f.unpack((self.output / "FAILURE.json.gz").read_bytes())
        self.assertEqual(original, request)
        self.assertEqual(attachments, [(self.base / "original.bin").read_bytes()])
        self.assertEqual(status["original_state"], "FAILED")
        self.assertFalse(status["failure_evidence_durable"])
        self.assertFalse(any(status[k] for k in f.NEGATIVE_GATES))
        self.assertFalse(self.server.calls)

    def test_empty_or_partial_evidence_is_never_a_successful_forecast(self):
        request = self.request(state="PARTIAL")
        request["attachments"] = []
        result = f.record_failure(request, self.storage, self.output)
        self.assertEqual(f.unpack((self.output / "FAILURE.json.gz").read_bytes()), (request, []))
        self.assertEqual(result["original_state"], "PARTIAL")
        for stage in ("LOCAL_FAILURE_RECORDED", "PRIVATE_APPEND_RESTORE_REQUIRED", "PRIVATE_FAILURE_RESTORED"):
            self.assertFalse(any(f.safe_status(stage, "PARTIAL")[k] for k in f.NEGATIVE_GATES))

    def test_duplicate_local_attempt_refuses_overwrite_and_never_reruns(self):
        request, _ = self.record()
        before = (self.output / "ATTEMPT.json").read_bytes()
        with self.assertRaisesRegex(s.StoreError, "ALREADY_RECORDED_NO_RETRY"):
            f.record_failure(request, self.storage, self.output)
        self.assertEqual((self.output / "ATTEMPT.json").read_bytes(), before)
        self.assertFalse(self.posts())

    def test_real_store_append_then_independent_restore_then_third_process_proof(self):
        request, _ = self.record(state="PARTIAL")
        appended = self.append()
        self.assertFalse(appended["status"]["failure_evidence_durable"])
        restored, reader = self.restore(appended)
        self.assertEqual(len(self.posts()), 2)
        self.assertEqual(restored["attempt"], request["attempt"])
        self.assertTrue(restored["status"]["failure_evidence_durable"])
        self.assertFalse(any(restored["status"][k] for k in f.NEGATIVE_GATES))
        package = (self.base / "restored/FAILURE.json.gz").read_bytes()
        verifier = self.client("fictional_verifier", "6" * 64, "restore")
        verifier.authenticate_actions_job()
        verifier.bind(self.binding)
        status = f.verify_restore(verifier, restored, appended["descriptor"], package)
        self.assertEqual(status["original_state"], "PARTIAL")
        self.assertLessEqual(reader.calls, s.MAX_CALLS)
        for item, value in zip(restored["attachments"], f.unpack(package)[1]):
            self.assertEqual(Path(item["path"]).read_bytes(), value)
        self.assertEqual(f.unpack(package)[0]["clocks"], request["clocks"])

    def test_quota_failure_keeps_original_and_attempt_before_package_write(self):
        policy = deepcopy(self.policy)
        policy["storage"]["limit_bytes"] = 10000
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            storage = OperationalStorage(base / "cache", policy, state=base / "state")
            storage.register_root(base)
            opaque = b"".join(bytes.fromhex(s.sha(str(i).encode())) for i in range(128))
            storage.write_bytes(base / "opaque.bin", opaque)
            request = self.request(kind="QUOTA")
            request["attachments"][0]["reference"] = dict(path=str(base / "opaque.bin"), bytes=len(opaque), sha256=s.sha(opaque))
            with self.assertRaises(StorageQuotaError):
                f.record_failure(request, storage, base / "failure")
            self.assertEqual((base / "opaque.bin").read_bytes(), opaque)
            self.assertTrue((base / "failure/ATTEMPT.json").exists())
            self.assertFalse((base / "failure/FAILURE.json.gz").exists())
        self.assertFalse(self.posts())

    def test_remote_quota_counts_unknown_assets_and_stops_before_POST(self):
        self.record(kind="QUOTA")
        for i in range(4):
            size = s.ASSET_CAP if i < 3 else s.ASSET_CAP - 117 - 1024
            self.server.add("unknown-" + str(i), size=size)
        with self.assertRaisesRegex(s.StoreError, "COMPLETE_APPEND_REMOTE_CAP"):
            self.append()
        self.assertFalse(self.posts())
        self.assertTrue((self.output / "APPEND_FAILED.json").exists())
        self.assertTrue((self.output / "ATTEMPT.json").exists())

    def test_ambiguous_payload_POST_is_original_evidence_with_no_retry(self):
        request, _ = self.record(kind="AMBIGUOUS_POST")
        self.server.ambiguous = True
        with self.assertRaisesRegex(s.StoreError, "TRANSPORT_FAILURE_NO_RETRY"):
            self.append()
        self.assertEqual(len(self.posts()), 1)
        self.assertTrue(list(self.journal.glob("*.reservation.json")))
        self.assertFalse((self.output / "APPENDED.json").exists())
        with self.assertRaisesRegex(s.StoreError, "APPEND_ALREADY_RESERVED_NO_RETRY"):
            self.append()
        self.assertEqual(len(self.posts()), 1)
        self.assertEqual(f.unpack((self.output / "FAILURE.json.gz").read_bytes())[0], request)

    def test_ambiguous_manifest_POST_never_becomes_an_append_receipt(self):
        self.record()
        def ambiguous_manifest(req, timeout):
            if req.method == "POST" and "name=manifest-" in req.full_url:
                self.server.ambiguous = True
            return self.server(req, timeout)
        with self.assertRaisesRegex(s.StoreError, "TRANSPORT_FAILURE_NO_RETRY"):
            self.append(self.client(transport=ambiguous_manifest))
        self.assertEqual(len(self.posts()), 2)
        self.assertFalse((self.output / "APPENDED.json").exists())
        self.assertTrue((self.output / "APPEND_FAILED.json").exists())

    def test_interrupted_POST_leaves_intent_and_original_failure(self):
        self.record()
        def interrupt(req, timeout):
            if req.method == "POST":
                raise KeyboardInterrupt()
            return self.server(req, timeout)
        with self.assertRaises(KeyboardInterrupt):
            self.append(self.client(transport=interrupt))
        self.assertTrue((self.output / "APPEND_FAILED.json").exists())
        self.assertTrue((self.output / "ATTEMPT.json").exists())
        self.assertGreater(len(list(self.journal.glob("*.reservation.json"))), 2)
        with self.assertRaisesRegex(s.StoreError, "APPEND_ALREADY_RESERVED_NO_RETRY"):
            self.append()
        self.assertFalse((self.output / "APPENDED.json").exists())

    def test_completed_duplicate_append_has_no_second_POST_or_success_reclassification(self):
        self.record()
        first = self.append()
        with self.assertRaisesRegex(s.StoreError, "APPEND_ALREADY_RESERVED_NO_RETRY"):
            self.append()
        self.assertEqual(len(self.posts()), 2)
        self.assertFalse(first["status"]["successful_forecast"])

    def test_remote_orphan_prevents_duplicate_POST_even_in_another_local_root(self):
        request, _ = self.record()
        self.server.ambiguous = True
        with self.assertRaises(s.StoreError):
            self.append()
        other = self.base / "another-failure-root"
        f.record_failure(request, self.storage, other)
        client = self.client(process="7" * 64)
        with self.assertRaisesRegex(s.StoreError, "REMOTE_ATTEMPT_ALREADY_PRESENT_NO_RETRY"):
            f.append_failure(client, self.storage, other, **self.go(client))
        self.assertEqual(len(self.posts()), 1)

    def test_source_run_and_job_GO_mismatches_stop_before_any_HTTP(self):
        self.record()
        for key, value in (("source_sha", "b" * 40), ("run_id", "40099999999"), ("job_id", "another_job"),
                           ("single_writer_group", "another_writer"), ("approved", False), ("extra", True)):
            client = self.client()
            args = self.go(client)
            go = f.document(args["authorization"])
            go[key] = value
            args.update(authorization=s.canonical(go), authorization_sha256=s.sha(s.canonical(go)))
            with self.subTest(key=key), self.assertRaises(s.StoreError):
                f.append_failure(client, self.storage, self.output, **args)
            self.assertFalse((self.output / "APPEND_INTENT.json").exists())
        self.assertFalse(self.server.calls)

    def test_actual_API_authentication_is_required_even_with_a_valid_GO(self):
        self.record()
        def wrong_run(req, timeout):
            if "/actions/runs/" in req.full_url:
                return Response(dict(id=int(RUN), head_sha="b" * 40))
            return self.server(req, timeout)
        with self.assertRaisesRegex(s.StoreError, "ACTIONS_API_IDENTITY"):
            self.append(self.client(transport=wrong_run))
        self.assertFalse(self.posts())
        self.assertTrue((self.output / "APPEND_FAILED.json").exists())

    def test_envelope_cannot_rebind_a_different_actual_attempt(self):
        request = self.request()
        request["attempt"]["source_sha"] = "b" * 40
        f.record_failure(request, self.storage, self.output)
        with self.assertRaisesRegex(s.StoreError, "ACTUAL_FAILED_ATTEMPT_IDENTITY"):
            self.append()
        self.assertFalse(self.posts())

    def test_input_hash_and_qualification_remain_strict(self):
        self.record()
        client = self.client()
        args = self.go(client)
        args["inputs"]["payload_manifest"] += b"\n"
        with self.assertRaisesRegex(s.StoreError, "PHASE_INPUT_HASH"):
            f.append_failure(client, self.storage, self.output, **args)
        self.assertFalse(self.server.calls)
        self.qualification["engineering_boundary_v2"] = False
        with self.assertRaises(s.StoreError):
            self.append()
        self.assertFalse(self.posts())

    def test_same_process_and_unfinished_writer_cannot_prove_restore(self):
        self.record()
        appended = self.append()
        with self.assertRaisesRegex(s.StoreError, "SEPARATE_PROCESS_REQUIRED"):
            self.restore(appended, process="4" * 64)
        self.assertFalse((self.base / "restored/RESTORED.json").exists())
        self.assertTrue((self.base / "restored/RESTORE_INTENT.json").exists())

    def test_corrupt_remote_package_never_yields_a_restore_receipt(self):
        self.record()
        appended = self.append()
        payload_id = appended["descriptor"]["entry"]["payload_asset_id"]
        next(a for a in self.server.assets if a["id"] == payload_id)["body"] += b"CORRUPT"
        with self.assertRaises(s.StoreError):
            self.restore(appended)
        self.assertFalse((self.base / "restored/RESTORED.json").exists())

    def test_malformed_envelopes_inflation_duplicates_and_success_are_rejected(self):
        self.record()
        body = (self.output / "FAILURE.json.gz").read_bytes()
        envelope = json.loads(gzip.decompress(body))
        mutations = [lambda d:d.update(classification="FORECAST"), lambda d:d["request"].update(state="SUCCESS"),
                     lambda d:d["gates"].update(successful_forecast=True), lambda d:d["attachments"][0].update(base64="AAAA"),
                     lambda d:d.update(unknown="unexpected")]
        for change in mutations:
            doc = deepcopy(envelope)
            change(doc)
            with self.assertRaises(s.StoreError):
                f.unpack(gzip.compress(s.canonical(doc), mtime=0))
        with self.assertRaises(s.StoreError):
            f.unpack(gzip.compress(b"x" * (f.PLAIN_CAP + 1), mtime=0))
        with self.assertRaisesRegex(s.StoreError, "DUPLICATE_PRIVATE_JSON"):
            f.document(b'{"state":"FAILED","state":"PARTIAL"}')

    def test_attachment_bound_symlink_hash_and_unknown_fields_fail_closed(self):
        request = self.request()
        for mutate in (lambda r:r["attachments"][0]["reference"].update(bytes=f.ATTACHMENT_CAP+1),
                       lambda r:r["attachments"].extend(deepcopy(r["attachments"])),
                       lambda r:r["attempt"].update(run_attempt=2), lambda r:r.update(unknown=True)):
            candidate = deepcopy(request)
            mutate(candidate)
            with self.assertRaises(s.StoreError):
                f.check_request(candidate)
        request["attachments"][0]["reference"]["sha256"] = "0" * 64
        with self.assertRaises(StorageIntegrityError):
            f.record_failure(request, self.storage, self.output)
        self.assertTrue((self.output / "ATTEMPT.json").exists())
        self.assertFalse((self.output / "FAILURE.json.gz").exists())

    def test_public_status_has_no_original_message_paths_rows_or_private_receipts(self):
        self.record()
        status = self.append()["status"]
        encoded = s.canonical(status)
        for marker in (b"FICTIONAL original", b"/tmp/", b"https://", b"descriptor", b"proof", b"attachments", b"ghs_"):
            self.assertNotIn(marker, encoded)
        self.assertEqual(status["public_payload_bytes"], 0)

    def test_preparation_and_invalid_job_do_not_discover_credentials(self):
        class NoEnvironment:
            def get(self, name, default=None):
                if name == "GITHUB_TOKEN":
                    raise AssertionError("credential discovery")
                return default
        with redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(["append"], environ=NoEnvironment()), 2)
        self.record()
        client = self.client()
        args = self.go(client)
        go_path = self.base / "GO.json"
        go_path.write_bytes(args["authorization"])
        binding_path = self.base / "BINDING.json"
        binding_path.write_bytes(args["inputs"]["binding"])
        output = io.StringIO()
        with redirect_stdout(output):
            result = cli.main(["append", "--execute", "--cache", str(self.base / "cache"), "--state-root", str(self.base / "state"),
                "--output-root", str(self.output), "--authorization", str(go_path), "--authorization-sha256", args["authorization_sha256"],
                "--binding", str(binding_path), "--journal", str(self.journal)], environ=NoEnvironment())
        self.assertEqual(result, 1)
        self.assertEqual(json.loads(output.getvalue())["reason"], "GENUINE_FAILURE_JOB_CONTEXT")
        self.assertFalse(self.server.calls)

    def test_CLI_records_fictional_request_and_prints_only_negative_status(self):
        request = self.request()
        path = self.base / "REQUEST.json"
        path.write_bytes(s.canonical(request))
        output = io.StringIO()
        with redirect_stdout(output):
            result = cli.main(["record", "--execute", "--cache", str(self.base / "cache"),
                "--state-root", str(self.base / "state"), "--output-root", str(self.output),
                "--request", str(path), "--request-sha256", s.sha(path.read_bytes())])
        self.assertEqual(result, 0)
        self.assertEqual(json.loads(output.getvalue())["state"], "LOCAL_FAILURE_RECORDED")
        self.assertNotIn("FICTIONAL original", output.getvalue())
        self.assertFalse(self.server.calls)

    def test_CLI_append_uses_shared_checkout_gate_and_actual_API_with_fictional_transport(self):
        self.record()
        fake = self.client()
        args = self.go(fake)
        paths = {}
        for name, body in dict(args["inputs"], authorization=args["authorization"]).items():
            path = self.base / (name + ".json")
            path.write_bytes(body)
            paths[name] = path
        env = dict(GITHUB_ACTIONS="true", GITHUB_REPOSITORY=s.REPO, GITHUB_EVENT_NAME="workflow_dispatch",
                   GITHUB_RUN_ATTEMPT="1", STORE_PERMISSION="write", GITHUB_RUN_ID=RUN,
                   GITHUB_SHA=SOURCE, GITHUB_TOKEN="ghs_FICTIONAL")
        output = io.StringIO()
        from tools import private_draft_store_v2 as shared
        with patch.object(shared, "actions_context", return_value=fake.job) as gate, patch.object(shared, "limits"), redirect_stdout(output):
            result = cli.main(["append", "--execute", "--cache", str(self.base / "cache"),
                "--state-root", str(self.base / "state"), "--output-root", str(self.output),
                "--authorization", str(paths["authorization"]), "--authorization-sha256", args["authorization_sha256"],
                "--binding", str(paths["binding"]), "--qualification", str(paths["qualification"]),
                "--journal", str(self.journal)], environ=env, transport=fake.transport)
        self.assertEqual(result, 0, output.getvalue())
        gate.assert_called_once_with(env, "write")
        self.assertEqual(len(self.posts()), 2)
        self.assertFalse(json.loads(output.getvalue())["failure_evidence_durable"])

    def test_actual_fresh_Python_restores_opaque_failure_without_ML_imports(self):
        self.record(state="PARTIAL")
        appended = self.append()
        fixture = self.base / "fictional-service.json"
        fixture.write_bytes(s.canonical(dict(binding=self.binding, appended=appended, policy=self.policy,
            started=self.started.isoformat(), observed=self.observed.isoformat(), tag=self.server.tag,
            assets=[dict(a, body=base64.b64encode(a["body"]).decode()) for a in self.server.assets])))
        program = '''import base64,json,sys
from datetime import datetime
from pathlib import Path
sys.path.insert(0,sys.argv[1]);sys.path.insert(0,str(Path(sys.argv[1])/'tests'))
from test_operational_failure_v1 import FailureTests,Server,READER
from nfl_lab import operational_failure_v1 as f,private_draft_store as s
from nfl_lab.operational_storage import OperationalStorage
d=json.loads(Path(sys.argv[2]).read_bytes());t=FailureTests();t.base=Path(sys.argv[3]);t.base.mkdir()
t.policy=d['policy'];t.storage=OperationalStorage(t.base/'cache',t.policy,state=t.base/'state');t.storage.register_root(t.base)
t.journal=t.base/'journal';t.journal.mkdir(mode=0o700);t.binding=d['binding'];t.server=Server();t.server.tag=d['tag']
t.server.assets=[dict(a,body=base64.b64decode(a['body'])) for a in d['assets']]
t.started=datetime.fromisoformat(d['started']);t.observed=datetime.fromisoformat(d['observed']);t.completed=True
c=t.client(READER,s.process_identity(),'restore');r=f.restore_failure(c,t.storage,t.base/'restored',**t.go(c,'restore',d['appended']['descriptor']))
assert not any(x in sys.modules for x in ('sklearn','joblib','catboost','torch'))
print(json.dumps(r['status']))
'''
        with tempfile.TemporaryDirectory() as fresh:
            result = subprocess.run([sys.executable, "-I", "-B", "-c", program, str(ROOT), str(fixture), str(Path(fresh) / "reader")],
                                    check=False, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        status = json.loads(result.stdout)
        self.assertEqual(status["state"], "PRIVATE_FAILURE_RESTORED")
        self.assertEqual(status["original_state"], "PARTIAL")
        self.assertFalse(status["successful_forecast"])

    def test_unfinished_writer_cannot_be_a_restored_producer(self):
        self.record()
        appended = self.append()
        client = self.client(READER, "5" * 64, "restore")
        with self.assertRaisesRegex(s.StoreError, "ACTUAL_FAILURE_PRODUCER_REQUIRED"):
            f.restore_failure(client, self.storage, self.base / "restored", **self.go(client, "restore", appended["descriptor"]))
        self.assertFalse((self.base / "restored/RESTORED.json").exists())

    def test_symlink_attachment_is_rejected_by_original_storage(self):
        request = self.request()
        alias = self.base / "symlink.bin"
        alias.symlink_to(self.base / "original.bin")
        request["attachments"][0]["reference"]["path"] = str(alias)
        with self.assertRaises(StorageIntegrityError):
            f.record_failure(request, self.storage, self.base / "rejected-link")
        self.assertFalse(self.posts())

    def test_tampered_restore_receipt_is_rejected(self):
        f.record_failure(self.request(), self.storage, self.output)
        appended = self.append()
        restored, _ = self.restore(appended)
        verifier = self.client("fictional_verifier", "6" * 64, "restore")
        verifier.authenticate_actions_job()
        verifier.bind(self.binding)
        package = (self.base / "restored/FAILURE.json.gz").read_bytes()
        for mutate in (lambda r:r["status"].update(successful_forecast=True),
                       lambda r:r.update(request_sha256="0" * 64),
                       lambda r:r["attempt"].update(source_sha="b" * 40),
                       lambda r:r["attachments"][0].update(sha256="0" * 64)):
            candidate = deepcopy(restored)
            mutate(candidate)
            with self.assertRaises(s.StoreError):
                f.verify_restore(verifier, candidate, appended["descriptor"], package)


if __name__ == "__main__":
    unittest.main()
