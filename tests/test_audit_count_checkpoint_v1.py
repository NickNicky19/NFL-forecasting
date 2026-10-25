"""Effective success transport with fictional trained state and injected HTTP."""
from copy import deepcopy
from datetime import timedelta
import base64
import gzip
import json
from pathlib import Path

import pytest

from nfl_lab import audit_count_checkpoint_v1 as effective, audit_count_requalify_v1 as audit
from nfl_lab import gha_private_checkpoint as cp, private_draft_store as store
from nfl_lab.operational_storage import OperationalStorage
from nfl_lab import operational_failure_v1 as failure
from test_audit_count_requalify_v1 import ROOT, legacy_module, retained
from test_private_draft_store_v2 import Server, Response, RUN, SOURCE
from test_owner_private_bootstrap import qualification
from tools import audit_count_checkpoint_v1 as cli


@pytest.fixture(scope="module")
def effective_packet(tmp_path_factory):
    root = tmp_path_factory.mktemp("fictional-effective18")
    policy = json.loads((ROOT / "config/operational-source-policy-v2.json").read_text())
    storage = OperationalStorage(root / "cache", policy, state=root / "state")
    owned = root / "owned"
    storage.register_root(owned)
    original = legacy_module(root)
    proof = dict(schema_version=audit.VERSION + "-restore", state="QUALIFIED_ROUTE_RESTORED_OPAQUE",
        current_source_sha=SOURCE, current_run_id=RUN, fits=0, model_decodes=0)
    storage.write_bytes(owned / "RESTORE_RECEIPT.json", audit.canonical(proof))
    proof_ref = cp.binding(owned / "RESTORE_RECEIPT.json")
    artifacts = []
    for target, family, method in cp.JOBS:
        _, _, _, manifest, model, _ = retained(root, original, target=target, family=family,
            storage=storage, root=owned / "originals" / target / family)
        artifacts.append(audit.requalify_one(manifest, model, storage=storage,
            destination=owned / "effective-models" / target / family, original_module=original,
            plan_sha256="b" * 64, restore_receipt=proof_ref, expected_slot=(target, family, method)))
    result = dict(schema_version=audit.VERSION + "-result", state="ZERO_FIT_REQUALIFIED_PRIVATE_PENDING_INTEGRATION",
        current_source_sha=SOURCE, current_run_id=RUN, model_pairs=18, artifacts=artifacts,
        fits=0, original_models_preserved=True, remote_writes=0, protected_outcome_reads=0, scientific_qualification=False)
    storage.write_bytes(owned / "REQUALIFICATION_FINISHED.json", audit.canonical(result))
    files = effective.collect(cp.binding(owned / "REQUALIFICATION_FINISHED.json"), proof_ref, storage, source_sha=SOURCE, run_id=RUN)
    return root, policy, storage, files, artifacts


class Service:
    def __init__(self, root):
        self.server = Server()
        journal = root / "initialize"
        journal.mkdir(mode=0o700)
        self.runtime = store.initialize(store.Client("ghs_FICTIONAL", RUN, journal=journal, source_sha=SOURCE,
            transport=self.server, process="e" * 64), "c" * 32)
        self.q = qualification(self.runtime)
        self.reader_active = False
        self.writer_success = True
        self.requests = []
        self.writer_started = audit.now() - timedelta(minutes=1)
        self.writer_completed = None

    def transport(self, request, timeout):
        self.requests.append(request)
        url = request.full_url
        if url.startswith(store.API + "/actions/runs/"):
            if "/jobs?" in url:
                writer = dict(id=777, name=effective.WRITER_JOB, run_id=int(RUN), head_sha=SOURCE,
                    status="completed" if self.reader_active else "in_progress", conclusion="success" if self.writer_success else "failure",
                    started_at=self.writer_started.isoformat(), completed_at=(self.writer_completed or audit.now()).isoformat())
                jobs = [writer]
                if self.reader_active:
                    jobs.append(dict(id=778, name=effective.READER_JOB, run_id=int(RUN), head_sha=SOURCE,
                        status="in_progress", started_at=self.reader_started.isoformat()))
                return Response(dict(total_count=len(jobs), jobs=jobs))
            return Response(dict(id=int(RUN), head_sha=SOURCE, event="workflow_dispatch", run_attempt=1, status="in_progress",
                path=".github/workflows/lab.yml", repository={"full_name": store.REPO}, head_repository={"full_name": store.REPO}))
        return self.server(request, timeout)

    def factory(self, journal, *, reader=False, process=None):
        clients = []
        def create(operation):
            label = effective.READER_JOB if reader else effective.WRITER_JOB
            job = dict(execution_lane="github_actions", workflow_ref=store.REPO + "/.github/workflows/lab.yml@refs/heads/fictional",
                workflow_sha=SOURCE, job_id=label, permission="write", event_name="workflow_dispatch", api_job_id=0, run_authenticated=False)
            c = store.Client("ghs_FICTIONAL", RUN, journal=journal, source_sha=SOURCE, transport=self.transport,
                process=process or ("5" * 64 if reader else "4" * 64), job=job, operation=operation)
            c.bind(self.runtime)
            clients.append(c)
            return c
        return create


def produce(packet, tmp_path):
    _, _, storage, files, _ = packet
    service = Service(tmp_path)
    journal = tmp_path / "journal"
    journal.mkdir(mode=0o700)
    storage.register_root(tmp_path)
    handoff = effective.produce(deepcopy(files), service.factory(journal), service.q,
        storage=storage, output=tmp_path / "success", root_go_sha256="d" * 64, pending=[])
    return service, handoff


def test_all18_requalification_and_closed38_collect(effective_packet):
    _, _, _, files, artifacts = effective_packet
    assert len(files) == 38 and len(artifacts) == 18
    assert all(a["fits"] == 0 and a["current_loader_replay_passed"] for a in artifacts)
    for artifact in artifacts:
        assert artifact["comparison"]["warm_bits_identical"]
        if artifact["family"] == "count_A":
            assert artifact["comparison"]["warm_rows"] > 0
            assert artifact["comparison"]["independent_stored_q_mean_verified"]
    assert not any(f["kind"] in {"source_raw", "feature", "query", "forecast"} for f in files)


def test_real_append_restore_codec_relocation_and_loader_replay(effective_packet, tmp_path):
    service, handoff = produce(effective_packet, tmp_path)
    safe = effective.safe_handoff(handoff)
    assert len(safe) <= 16384
    assert all(marker not in safe for marker in (b"/tmp/", b"/workspace/", b"float64_hex", b"content_b64"))
    service.writer_completed = audit.now()
    service.reader_started = audit.now()
    service.reader_active = True
    fresh = tmp_path / "fresh"
    # Separate quota owner is a sibling of the writer's registered scope.
    fresh = tmp_path.parent / (tmp_path.name + "-fresh-reader")
    fresh.mkdir()
    storage = OperationalStorage(fresh / "cache", effective_packet[1], state=fresh / "state")
    storage.register_root(fresh)
    journal = fresh / "journal"
    journal.mkdir(mode=0o700)
    start = len(service.requests)
    result = effective.restore(handoff, service.factory(journal, reader=True), storage=storage,
        output=fresh / "restore", root_go_sha256="d" * 64)
    assert result["model_pairs"] == 18 and result["files"] == 38
    assert result["fits"] == 0 and result["fresh_process_replay"] is True
    assert result["model_artifact_durability"] is True
    assert result["public_release"] is result["private_durability_qualified"] is False
    assert all(r.method == "GET" for r in service.requests[start:])
    assert all(p["schema_version"] == "weekly-private-proof-v2.1" for p in result["proofs"])
    assert len(result["models"]) == 18
    catalog = result["replay_catalog"]
    safe_catalog = effective.safe_replay_catalog(catalog)
    assert len(safe_catalog) <= 16384
    assert len(catalog["slots"]) == 18
    assert all(marker not in safe_catalog for marker in (b"/tmp/", b"/workspace/", b"player_id", b"forecast_value", b"float64_hex"))
    for slot in catalog["slots"]:
        assert slot["warm_bits_identical"] is True
        if slot["family"] == "count_A":
            assert slot["warm_rows"] > 0 and slot["fallback_oracle_passed"] is True
        else:
            assert slot["fallback_oracle_applicable"] is False and slot["fallback_oracle_passed"] is None
    leaked = deepcopy(catalog)
    leaked["slots"][0]["player_id"] = "must-never-export"
    with pytest.raises(store.StoreError, match="CLOSED_PUBLIC_SAFE_REPLAY_SLOT"):
        effective.safe_replay_catalog(leaked)
    verifier = service.factory(journal, reader=True, process="6" * 64)("restore")
    verified = effective.verify_proofs(verifier, result, handoff)
    assert verified["state"] == "EFFECTIVE18_RESTORE_PROOFS_VERIFIED"


def test_full_failure_reserve_blocks_before_any_post(effective_packet, tmp_path):
    _, _, storage, files, _ = effective_packet
    service = Service(tmp_path)
    # Charge unknown bytes under the fixed8MiB per-asset limit.
    for i in range(3):
        service.server.add("unknown-" + str(i), size=8 << 20)
    service.server.add("unknown-last", size=7 << 20)
    service.requests.clear()
    journal = tmp_path / "journal"
    journal.mkdir(mode=0o700)
    storage.register_root(tmp_path)
    with pytest.raises(store.StoreError, match="SUCCESS_AND_FAILURE_REMOTE_RESERVE_REQUIRED"):
        effective.produce(deepcopy(files), service.factory(journal), service.q, storage=storage,
            output=tmp_path / "success", root_go_sha256="d" * 64, pending=[])
    assert not any(r.method == "POST" for r in service.requests)


def test_all_groups_authenticate_before_first_post(effective_packet, tmp_path):
    _, _, storage, files, _ = effective_packet
    bad = deepcopy(files)
    bad[-1]["sha256"] = "0" * 64
    bad[-1]["origin"]["source_sha256"] = "0" * 64
    calls = []
    with pytest.raises(ValueError):
        effective.produce(bad, lambda *args: calls.append(args), {}, storage=storage,
            output=tmp_path / "success", root_go_sha256="d" * 64, pending=[])
    assert calls == []


def test_raw_file_or_missing_model_is_rejected_before_transport(effective_packet):
    files = deepcopy(effective_packet[3])
    files.pop()
    with pytest.raises(store.StoreError, match="EXACT_EFFECTIVE38_FILES"):
        effective.check_files(files)
    files = deepcopy(effective_packet[3])
    files[0]["logical_path"] = "source-cache/raw/schedules.csv"
    with pytest.raises(store.StoreError, match="EXACT_EFFECTIVE38_FILES"):
        effective.check_files(files)


def test_failed_completed_writer_cannot_restore_success(effective_packet, tmp_path):
    service, handoff = produce(effective_packet, tmp_path)
    service.writer_completed = audit.now()
    service.reader_started = audit.now()
    service.reader_active = True
    service.writer_success = False
    journal = tmp_path / "reader-journal"
    journal.mkdir(mode=0o700)
    service.requests.clear()
    with pytest.raises(store.StoreError, match="COMPLETED_SUCCESSFUL_EFFECTIVE_WRITER"):
        effective.restore(handoff, service.factory(journal, reader=True), storage=effective_packet[2],
            output=tmp_path / "failed-reader", root_go_sha256="d" * 64)
    assert not any("/releases/assets/" in r.full_url for r in service.requests)


def test_cli_preparation_reads_no_context_or_token(capsys):
    class NoEnvironment:
        def get(self, *args):
            pytest.fail("credential/context accessed without --execute")
    assert cli.main(["produce"], environ=NoEnvironment()) == 2
    assert "PREPARATION_ONLY_NO_IO" in capsys.readouterr().out


def count_failure_request():
    status = dict(schema_version=effective.COUNT_FAILURE_CONTRACT["schema_version"] + "-status",
        contract_sha256=effective.COUNT_FAILURE_CONTRACT_SHA256,
        controls=[dict(label=label, state="ABSENT", bytes=None, sha256=None) for label in effective.COUNT_CONTROL_LABELS])
    status_body = store.canonical(status)
    request = dict(schema_version=failure.VERSION + "-request",
        attempt=dict(repository=store.REPO, run_id=RUN, run_attempt=1, source_sha=SOURCE,
            job_id=effective.WRITER_JOB, workflow_ref=store.REPO + "/.github/workflows/lab.yml@refs/heads/fictional"),
        operation="checkpoint", state="FAILED", input_contract_sha256="d" * 64,
        failure=dict(kind="EXCEPTION", code="FICTIONAL_COUNT_FAILURE", exit_code=1),
        clocks=dict(started_at_utc=audit.now().isoformat(), observed_at_utc=audit.now().isoformat(), original={}),
        attachments=[dict(label="count-control-status", kind="control", reference=dict(
            path="/fictional/owned/status.json", bytes=len(status_body), sha256=store.sha(status_body)))])
    return request, status


def test_count_specific_failure_reserve_and_actual_encoded_body_cap():
    request, status = count_failure_request()
    envelope = dict(schema_version=failure.VERSION + "-envelope", classification="FAILURE_EVIDENCE_ONLY",
        request=request, attachments=[dict(label="count-control-status", base64=base64.b64encode(store.canonical(status)).decode())],
        gates=failure.NEGATIVE_GATES)
    body = gzip.compress(store.canonical(envelope), mtime=0)
    checked = effective.validate_count_failure_variant(request, status, body)
    assert checked["attached_controls"] == 0
    assert checked["payload_cap_bytes"] == 1 << 20
    assert effective.FAILURE_RESERVE_BYTES == (1 << 20) + (16 << 10)
    assert failure.PACKAGE_CAP > 1 << 20  # Original general failure cap unchanged.
    with pytest.raises(store.StoreError, match="COUNT_FAILURE_ENCODED_PAYLOAD_CAP"):
        effective.validate_count_failure_variant(request, status, b"x" * ((1 << 20) + 1))


def test_count_variant_never_silently_omits_eligible_controls():
    request, status = count_failure_request()
    status["controls"][0].update(state="ATTACHED", bytes=100, sha256="e" * 64)
    with pytest.raises(store.StoreError, match="FULL_COUNT_CONTROL_ATTACHMENT_REQUIRED"):
        effective.validate_count_failure_variant(request, status)
    request, status = count_failure_request()
    status["controls"].pop()
    with pytest.raises(store.StoreError, match="CLOSED_COUNT_FAILURE_CONTROL_STATUS"):
        effective.validate_count_failure_variant(request, status)


def test_count_variant_rejects_complete_controls_over_512k():
    request, status = count_failure_request()
    for i, record in enumerate(status["controls"][:2]):
        record.update(state="ATTACHED", bytes=300 << 10, sha256=str(i + 1) * 64)
        request["attachments"].append(dict(label=record["label"], kind="control", reference=dict(
            path=f"/fictional/owned/control-{i}.json", bytes=record["bytes"], sha256=record["sha256"])))
    with pytest.raises(store.StoreError, match="COUNT_COMPLETE_CONTROL_BYTES_CAP"):
        effective.validate_count_failure_variant(request, status)


def test_second_group_encoding_failure_precedes_every_post(effective_packet, tmp_path, monkeypatch):
    _, _, storage, files, _ = effective_packet
    service = Service(tmp_path)
    journal = tmp_path / "journal"
    journal.mkdir(mode=0o700)
    storage.register_root(tmp_path)
    monkeypatch.setattr(effective.codec, "groups", lambda _: [files[:19], files[19:]])
    original_encode = effective.codec.encode
    encoded = []
    def fail_second(members):
        encoded.append(members)
        if len(encoded) == 2:
            raise store.StoreError("FICTIONAL_SECOND_GROUP_ENCODING_STOP")
        return original_encode(members)
    monkeypatch.setattr(effective.codec, "encode", fail_second)
    with pytest.raises(store.StoreError, match="SECOND_GROUP_ENCODING"):
        effective.produce(files, service.factory(journal), service.q, storage=storage,
            output=tmp_path / "success", root_go_sha256="d" * 64, pending=[])
    assert len(encoded) == 2
    assert not any(r.method == "POST" for r in service.requests)


def test_ambiguous_post_is_retained_and_cannot_retry(effective_packet, tmp_path):
    _, _, storage, files, _ = effective_packet
    service = Service(tmp_path)
    service.server.ambiguous = True
    journal = tmp_path / "journal"
    journal.mkdir(mode=0o700)
    storage.register_root(tmp_path)
    with pytest.raises(store.StoreError):
        effective.produce(files, service.factory(journal), service.q, storage=storage,
            output=tmp_path / "success", root_go_sha256="d" * 64, pending=[])
    assert (tmp_path / "success/APPEND_CONSUMED.json").is_file()
    assert list(journal.glob("*.reservation.json"))
    assert not (tmp_path / "success/APPENDED.json").exists()
    calls = len(service.requests)
    with pytest.raises(store.StoreError, match="FRESH_EFFECTIVE_APPEND_NO_RETRY"):
        effective.produce(files, service.factory(journal), service.q, storage=storage,
            output=tmp_path / "success", root_go_sha256="d" * 64, pending=[])
    assert len(service.requests) == calls


def test_corrupt_group_rejected_before_any_loader_decode(effective_packet, tmp_path, monkeypatch):
    service, handoff = produce(effective_packet, tmp_path)
    first_group = next(a for a in service.server.assets if a["name"].startswith("blob-"))
    first_group["body"] = b"x" * len(first_group["body"])
    service.writer_completed = audit.now()
    service.reader_started = audit.now()
    service.reader_active = True
    journal = tmp_path / "reader-journal"
    journal.mkdir(mode=0o700)
    from nfl_lab.weekly_future_inference import FutureInferenceSession
    monkeypatch.setattr(FutureInferenceSession, "prepare", lambda *args: pytest.fail("decode before body hash"))
    with pytest.raises(store.StoreError):
        effective.restore(handoff, service.factory(journal, reader=True), storage=effective_packet[2],
            output=tmp_path / "corrupt-restore", root_go_sha256="d" * 64)
