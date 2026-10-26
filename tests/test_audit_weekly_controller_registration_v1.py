"""Fictional Actions/API only; real append/restore/CAS/closed V2 validators.

The hosted gate and process identities are explicit composition seams. None of
these cases is hosted execution evidence. Every socket connect is forbidden.
The isolated native envelope test uses the actual OS limits and wall timer.
"""
import base64
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import gzip
import io
import json
from pathlib import Path
import pickle
import socket
import subprocess
import sys
from types import SimpleNamespace
import zipfile

import pytest

import nfl_lab
from nfl_lab import audit_weekly_controller_registration_v1 as w
from nfl_lab import audit_weekly_controller_v1 as c
from nfl_lab import audit_weekly_controller_bootstrap_v1 as b
from nfl_lab import audit_weekly_template_v1 as t, private_draft_store as s
from nfl_lab.operational_storage import OperationalStorage
from tools import audit_weekly_controller_registration_v1 as cli
import test_audit_weekly_controller_v1 as old
from test_audit_weekly_controller_v1 import system as controller_system
from test_private_draft_store_v2 import Server, Response
from test_owner_private_bootstrap import qualification, RUN as QRUN

ROOT = Path(__file__).resolve().parents[1]
RUN = "40000000009"
PHASES = tuple(w.PHASES)
API_IDS = dict(zip(PHASES, (801, 802, 803)))


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*_args, **_kwargs):
        pytest.fail("REAL_NETWORK_FORBIDDEN")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)


class Service(Server):
    def __init__(self, data):
        super().__init__()
        self.data, self.q, self.hooks = data, None, {}
        self.gated = False

    def __call__(self, request, timeout):
        url = request.full_url
        if url in self.data:
            assert self.gated, "HOSTED_GATE_MUST_PRECEDE_HTTP"
            self.calls.append(request)
            value = deepcopy(self.data[url])
            if url in self.hooks:
                value = self.hooks[url](value)
            assert request.method == "GET" and request.get_header("Authorization") == "Bearer ghs_FICTIONAL"
            return Response(c.canonical(value))
        if self.q is not None and url == c.run_url(QRUN):
            self.calls.append(request)
            return Response(old.run(QRUN, self.q["source_sha"], "fictional", c.OWNER))
        if self.q is not None and url == c.jobs_url(QRUN):
            self.calls.append(request)
            return Response(dict(total_count=3, jobs=[old.job(QRUN, self.q["source_sha"], p["job"]["job_id"],
                p["job"]["api_job_id"], p["started_at_utc"], p["created_at_utc"])
                for p in (self.q["before_proof"], self.q["read_proof"], self.q)]))
        return super().__call__(request, timeout)


@pytest.fixture
def case(controller_system, tmp_path, monkeypatch):
    x = controller_system
    at = datetime.now(timezone.utc)
    source = tmp_path / "registration-source"
    source.mkdir()
    workflow = old.wf().replace(b"  audit-weekly-restore-v1:\n", b"  audit-weekly-restore-v1:\n    needs: audit-weekly-produce-v1\n").replace(
        b"  audit-weekly-export-v1:\n", b"  audit-weekly-export-v1:\n    needs: [audit-weekly-produce-v1, audit-weekly-restore-v1]\n")
    pins = {}
    for name in sorted(w.REQUIRED_PINS | b.PARENT_EXECUTABLE_PINS):
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        body = workflow if name == c.WORKFLOW else (ROOT / name).read_bytes() if name.startswith("config/") else ("FICTIONAL immutable " + name).encode()
        path.write_bytes(body)
        pins[name] = s.sha(body)
    receipt = c.decode(x.original_receipt)
    receipt.update(policy_registered_at_utc=(at - timedelta(minutes=90)).isoformat(),
        verified_at=(at - timedelta(minutes=45)).isoformat(), created_at=(at - timedelta(minutes=44)).isoformat())
    raw_receipt = c.canonical(receipt)
    compressed = gzip.compress(raw_receipt, mtime=0)
    readiness = deepcopy(x.p["readiness"])
    readiness.update(receipt_sha256=c.sha(compressed), receipt_body_sha256=c.sha(raw_receipt))
    data = x.api.data
    data[c.contents_url(c.receipt_path(x.p), "lab-state")] = old.content(c.receipt_path(x.p), compressed)
    for job, (start, end) in zip(data[c.jobs_url("200")]["jobs"], ((65, 60), (59, 50), (49, 40))):
        job.update(started_at=(at - timedelta(minutes=start)).isoformat(), completed_at=(at - timedelta(minutes=end)).isoformat())
    data[c.run_url("200")]["updated_at"] = (at - timedelta(minutes=39)).isoformat()
    for number, sha in enumerate((old.A, old.B), 1):
        tree = str(number) * 40
        data[c.API + "/git/commits/" + sha] = dict(sha=sha, tree=dict(sha=tree))
        data[c.API + "/git/trees/" + tree + "?recursive=1"] = dict(sha=tree, truncated=False,
            tree=[dict(path=name, mode="100644", type="blob", sha=c.blob_sha((source / name).read_bytes())) for name in pins])
        data[c.contents_url(c.WORKFLOW, sha)] = old.content(c.WORKFLOW, workflow)
    server = Service(data)
    journal = tmp_path / "qualification-journal"
    journal.mkdir(mode=0o700)
    initial = s.Client("ghs_FICTIONAL", QRUN, journal=journal, source_sha=old.A, transport=server, process="9" * 64)
    binding = s.initialize(initial, "d" * 32)
    q = qualification(binding)
    server.q = q
    quota = dict(schema_version="audit-private-rotation-v1-quota-reservation", global_cap_bytes=512 << 20,
        reserved_before_bytes=32 << 20, new_runtime_reserved_bytes=32 << 20, reserved_after_bytes=64 << 20,
        existing_draft_runtimes=1, pending_unlocated_runtimes=0, pending_records=0, charged_existing_bytes=117,
        charged_existing_assets=1, inventory_sha256="8" * 64, pending_census_sha256="9" * 64,
        new_runtime_id=binding["runtime_id"], old_assets_deleted=0, metadata_only=True)
    package = dict(schema_version="audit-private-rotation-v1-qualified-runtime", run_id=QRUN, source_sha=old.A,
        runtime_id=binding["runtime_id"], binding=binding, qualification=q, quota_reservation=quota, runtime_reserved_bytes=32 << 20)
    policy = dict(source_sha=old.B, workflow_sha256=pins[c.WORKFLOW], registered_at_utc=(at - timedelta(minutes=5)).isoformat(),
        fixture="PREVALUE_POLICY_METADATA")
    policy_body = s.canonical(policy)
    root = {key: None for key in t.ROOT_KEYS}
    slots = [dict(target=a, family=f, method_id=m, procedure_version="1" * 64, model_sha256="2" * 64,
        manifest_sha256="3" * 64, transport_manifest_sha256="4" * 64) for a, f, m in t.JOBS]
    root.update(schema_version="audit-weekly-hosted-v2-root-GO", approved=True, repository=c.REPO, mode=c.MODE,
        operation="CONTROLLER_REGISTRATION", source_sha=old.B,
        workflow_ref=c.REPO + "/" + c.WORKFLOW + "@refs/heads/" + w.BRANCH,
        owner_authorization="OWNER_NFL_AUDIT_CONTINUATION_20261025", issued_at_utc=policy["registered_at_utc"],
        expires_at_utc=(at + timedelta(minutes=30)).isoformat(), single_writer_group=c.GROUP, code_pins=pins,
        limits=dict(fits=0), jobs={role: b.JOBS[other] for role, other in zip(c.ROLES, ("write", "read", "seal"))},
        failure_restorer="audit-weekly-failure-restore-v1", qualified_runtime=package,
        retained_registration=dict(schema_version="audit-count-retained-v1-registration", approved=True, maximum_new_fits=0,
            public_release=False, origin=dict(replay_catalog=dict(slots=slots))), source_config=dict(purpose="CURRENT_OPERATIONAL_INFERENCE"),
        publication=True, publication_registration=dict(policy_gzip_base64=base64.b64encode(gzip.compress(policy_body, mtime=0)).decode(),
            policy_sha256=s.sha(policy_body), r0=dict(fixture="ORIGINAL_R0"), rights_authority=dict(fixture="ORIGINAL_RIGHTS")),
        effective_epoch=dict(schema_version=w.VERSION + "-context", parent_source_sha=old.A,
            previous_capture=dict(feed_sha256=receipt["feed_sha256"], receipt_sha256=c.sha(compressed))))
    data[c.run_url(RUN)] = old.run(RUN, old.B, w.BRANCH, c.OWNER, status="in_progress", updated=at.isoformat())
    data[c.jobs_url(RUN)] = dict(total_count=3, jobs=[dict(id=API_IDS[p], name=root["jobs"][w.PHASES[p][0]],
        run_id=int(RUN), head_sha=old.B, status="queued", conclusion=None, started_at=None, completed_at=None) for p in PHASES])
    state = SimpleNamespace(process=s.sha(b"fictional inactive process"), gates=[])
    host = SimpleNamespace(VERSION="audit-weekly-hosted-v2", OPERATIONS_PHASES=deepcopy(w.PHASES),
        NATIVE_KEYS={"schema_version", "phase", "request_sha256", "owner_root_go_sha256", "repository", "source_sha",
            "run_id", "run_attempt", "job_id", "workflow_ref", "api_job_id", "issued_at_utc", "expires_at_utc",
            "actual_actions_api_authenticated", "owner_root_checked", "fits", "public_release"})

    def child_context(args, env, phase):
        # Explicit hosted composition seam. Production calls the parent's full
        # existing gate, including event, source HEAD/cleanliness and ROOT checks.
        state.gates.append(phase)
        server.gated = True
        raw = s.read_local(args.request, 512 << 10)
        assert s.sha(raw) == args.request_sha256
        request = c.decode(raw)
        authority = c.decode(env["AUDIT_WEEKLY_NATIVE_AUTHORITY_JSON"])
        go = c.decode(env["AUDIT_WEEKLY_ROOT_GO_JSON"])
        job = dict(execution_lane="github_actions", workflow_ref=go["workflow_ref"], workflow_sha=go["source_sha"],
            job_id=env["GITHUB_JOB"], permission="write", event_name="workflow_dispatch", api_job_id=0, run_authenticated=False)
        return request, authority, job, go
    host.child_context = child_context
    monkeypatch.setitem(sys.modules, "nfl_lab.audit_weekly_hosted_v1", host)
    monkeypatch.setattr(nfl_lab, "audit_weekly_hosted_v1", host, raising=False)
    monkeypatch.setattr(w, "ROOT", source)
    monkeypatch.setattr(c, "git_head", lambda _root: old.B)
    monkeypatch.setattr(w, "native_envelope", lambda: None)
    monkeypatch.setattr(s, "process_identity", lambda: state.process)

    def job_for(phase):
        return data[c.jobs_url(RUN)]["jobs"][PHASES.index(phase)]

    def start(phase, inputs=None, *, env_change=None, request_change=None):
        state.process = s.sha(("FICTIONAL composition process " + phase).encode())
        job_for(phase).update(status="in_progress", conclusion=None, started_at=datetime.now(timezone.utc).isoformat(), completed_at=None)
        base = tmp_path / phase
        journal = base / "journal"
        journal.mkdir(mode=0o700, parents=True)
        storage = OperationalStorage(base / "cache", ROOT / "config/operational-source-policy-v2.json", state=base / "state")
        storage.register_root(base)
        owned = {}
        if inputs:
            for name, value in inputs.items():
                body = s.canonical(value)
                path = base / "inputs" / (name + ".json")
                storage.write_bytes(path, body)
                owned[name] = dict(path=str(path), bytes=len(body), sha256=s.sha(body))
        request = w.build_request(phase, code_pins=pins, cache=base / "cache", state_root=base / "state", output=base / phase,
            inputs={"readiness": None} if phase == PHASES[0] else owned)
        if request_change:
            request_change(request)
        body = s.canonical(request)
        path = base / "requests" / "registration.json"
        storage.write_bytes(path, body)
        raw_root = s.canonical(root)
        native = dict(schema_version=host.VERSION + "-native-authority", phase=phase, request_sha256=s.sha(body),
            owner_root_go_sha256=s.sha(raw_root), repository=c.REPO, source_sha=root["source_sha"], run_id=RUN, run_attempt=1,
            job_id=root["jobs"][w.PHASES[phase][0]], workflow_ref=root["workflow_ref"], api_job_id=API_IDS[phase],
            issued_at_utc=root["issued_at_utc"], expires_at_utc=root["expires_at_utc"], actual_actions_api_authenticated=True,
            owner_root_checked=True, fits=0, public_release=False)
        env = dict(GITHUB_ACTIONS="true", CI="true", GITHUB_REPOSITORY=c.REPO, GITHUB_RUN_ATTEMPT="1", GITHUB_RUN_ID=RUN,
            GITHUB_EVENT_NAME="workflow_dispatch", GITHUB_SHA=old.B, GITHUB_WORKFLOW_SHA=old.B, GITHUB_WORKFLOW_REF=root["workflow_ref"],
            GITHUB_JOB=native["job_id"], GITHUB_ACTOR=c.OWNER["login"], GITHUB_ACTOR_ID=str(c.OWNER["id"]), STORE_PERMISSION="write",
            GITHUB_TOKEN="ghs_FICTIONAL", AUDIT_WEEKLY_ROOT_GO_JSON=raw_root.decode(), AUDIT_WEEKLY_ROOT_GO_SHA256=s.sha(raw_root),
            AUDIT_WEEKLY_NATIVE_AUTHORITY_JSON=s.canonical(native).decode(), AUDIT_WEEKLY_NATIVE_AUTHORITY_SHA256=s.sha(s.canonical(native)))
        if env_change:
            env_change(env)
        args = SimpleNamespace(phase=phase, request=str(path), request_sha256=s.sha(body))
        return SimpleNamespace(args=args, env=env, request=request, storage=storage, base=base)

    def execute(phase, inputs=None):
        call = start(phase, inputs)
        result = w.run(call.args, call.env, transport=server)
        docs = {name: c.decode(s.read_local(ref["path"], 64 << 10)) for name, ref in result["artifacts"].items()}
        return SimpleNamespace(call=call, result=result, docs=docs)

    def finish(phase):
        job_for(phase).update(status="completed", conclusion="success", completed_at=datetime.now(timezone.utc).isoformat())

    server.calls.clear()
    return SimpleNamespace(x=x, root=root, pins=pins, data=data, readiness=readiness, server=server, host=host,
        state=state, source=source, start=start, execute=execute, finish=finish, job=job_for)


def writer_reader(case):
    write = case.execute(PHASES[0])
    case.finish(PHASES[0])
    read = case.execute(PHASES[1], {"template_handoff": write.docs["template_handoff"]})
    case.finish(PHASES[1])
    return write, read, dict(write.docs, **read.docs)


def test_real_native_helpers_and_exact_closed_v2_outputs(case):
    write, read, inputs = writer_reader(case)
    before = datetime.now(timezone.utc)
    sealed = case.execute(PHASES[2], inputs)
    assert case.job(PHASES[2])["status"] == "in_progress" and case.job(PHASES[2])["completed_at"] is None
    native, registration, locators = (sealed.docs[name] for name in ("safe_seal", "registration", "locator_registration"))
    reg_raw = Path(sealed.result["artifacts"]["registration"]["path"]).read_bytes()
    assert c.registration(reg_raw, sealed_sha256=c.sha(reg_raw), at=c.now()) == registration
    assert b._validate_locator_registration(c.canonical(locators), native, registration) == locators
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("SAFE_SEAL.json", s.canonical(native))
    assert b.safe_seal(stream.getvalue(), registry_version=2) == native
    assert registration["parent"]["source_sha"] == old.A and registration["producer"]["source_sha"] == old.B
    assert registration["parent"]["code_pins"] == registration["producer"]["code_pins"] == case.pins
    assert registration["readiness"] == case.readiness
    assert before <= c.utc(registration["registered_at_utc"]) <= datetime.now(timezone.utc)
    assert native["owner_root_issued_at_utc"] == case.root["issued_at_utc"]
    assert native["static_public_policy_sha256"] == case.root["publication_registration"]["policy_sha256"]
    assert locators["template_seal"] == read.docs["template_seal"]
    assert locators["qualified_runtime_package"] == case.root["qualified_runtime"]
    assert native["writer"] == write.docs["writer_native"]
    assert native["reader"] == read.docs["reader_native"]["receipt"]
    assert native["writer"]["receipt_sha256"] == s.sha(s.canonical(write.docs["template_handoff"]))
    proof = read.docs["reader_native"]["proof"]
    assert native["reader"]["receipt_sha256"] == s.sha(s.canonical(proof))
    assert proof["process_identity"] == native["reader"]["process_identity"]
    assert native["writer"]["successful_private_creates"] == 1 and native["reader"]["successful_private_creates"] == 0
    assert len({native[k]["process_identity"] for k in ("writer", "reader", "sealer")}) == 3
    for stage in (write, read, sealed):
        output = Path(stage.call.request["output"])
        assert {p.name for p in output.iterdir()} == set(w.OUTPUT_FILES[stage.call.args.phase].values())
        assert stage.result["registration_run_completed"] is stage.result["registry_created"] is stage.result["public_root"] is False
        for ref in stage.result["artifacts"].values():
            raw = Path(ref["path"]).read_bytes()
            assert s.sha(raw) == ref["sha256"] and len(raw) == ref["bytes"]
            assert b'"root_template"' not in raw and b"PREVALUE_POLICY_METADATA" not in raw and b"ghs_" not in raw
    assert len([r for r in case.server.calls if r.method == "POST"]) == 2  # actual payload and manifest only
    assert all("/dispatches" not in r.full_url and "/contents/state/controller" not in r.full_url for r in case.server.calls)


def test_static_template_is_full_root_with_only_five_placeholders_cleared(case):
    prepared = w.prepare_template(case.root, case.readiness)
    expected = deepcopy(case.root)
    expected["approved"] = False
    for name in ("issued_at_utc", "expires_at_utc", "operation", "effective_epoch"):
        expected[name] = None
    assert prepared.document["root_template"] == expected
    assert case.root["approved"] is True and case.root["operation"] == "CONTROLLER_REGISTRATION"
    assert prepared.document["code_pins"] == case.pins and not case.server.calls
    assert prepared.document["root_template"]["publication_registration"] == case.root["publication_registration"]


def test_generated_documents_pass_unchanged_bootstrap_after_actual_completed_three_job_chain(case):
    _, _, inputs = writer_reader(case)
    sealed = case.execute(PHASES[2], inputs)
    packed_stream = io.BytesIO()
    with zipfile.ZipFile(packed_stream, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("SAFE_SEAL.json", Path(sealed.result["artifacts"]["safe_seal"]["path"]).read_bytes())
    packed = packed_stream.getvalue()
    reg_raw = Path(sealed.result["artifacts"]["registration"]["path"]).read_bytes()
    public = dict(schema_version=b.LOCATOR_VERSION + "-public-seal", repository=c.REPO,
        registration_base64=base64.b64encode(reg_raw).decode(), native_artifact_zip_base64=base64.b64encode(packed).decode(),
        artifact_id=901, locator_registration=sealed.docs["locator_registration"])
    public_raw = c.canonical(public)
    commit = "f" * 40
    case.data[b.history_url(registry_version=2)] = [dict(sha=commit)]
    case.data[c.API + "/commits/" + commit] = dict(sha=commit, parents=[dict(sha="e" * 40)], committer=deepcopy(c.OWNER),
        files=[dict(filename=b.LOCATOR_REGISTRY_PATH, status="added", sha=c.blob_sha(public_raw))])
    case.data[c.contents_url(b.LOCATOR_REGISTRY_PATH, commit)] = old.content(b.LOCATOR_REGISTRY_PATH, public_raw)
    uploaded = c.now().isoformat()
    case.data[c.API + "/actions/artifacts/901"] = dict(id=901, name="controller-root-safe-seal-v2-" + RUN,
        expired=False, digest="sha256:" + c.sha(packed), size_in_bytes=len(packed), created_at=uploaded, updated_at=uploaded,
        workflow_run=dict(id=int(RUN), head_sha=old.B, repository_id=123, head_repository_id=123))
    def metadata(url, cap):
        assert b.fixed_route(url)
        raw = c.canonical(case.data[url])
        assert len(raw) <= cap
        return c.Reply(200, raw)
    env = dict(sealed.call.env, GITHUB_RUN_ID="500")
    with pytest.raises(c.ControllerError):
        b.load_seal(env, case.source, metadata_get=metadata, read_head=c.git_head, registry_version=2)
    case.finish(PHASES[2])
    case.data[c.run_url(RUN)].update(status="completed", conclusion="success", updated_at=c.now().isoformat())
    loaded = b.load_seal(env, case.source, metadata_get=metadata, read_head=c.git_head, registry_version=2)
    assert loaded.verify().locators == sealed.docs["locator_registration"]
    assert loaded.registration_bytes == reg_raw
    assert loaded.template_descriptor == sealed.docs["safe_seal"]["template_descriptor"]


def test_create_once_rejects_payload_that_races_the_template_preflight(case, monkeypatch):
    upload = w._CreateOnceClient.upload
    def race(client, name, body, **kwargs):
        if name.startswith("blob-"):
            case.server.add(name, body)
        return upload(client, name, body, **kwargs)
    monkeypatch.setattr(w._CreateOnceClient, "upload", race)
    call = case.start(PHASES[0])
    with pytest.raises(s.StoreError, match="APPEND_ONLY_NAME_EXISTS"):
        w.run(call.args, call.env, transport=case.server)
    assert not Path(call.request["output"]).exists()
    assert not any(r.method == "POST" for r in case.server.calls)


def test_maximum_inventory_and_full_root_byte_budget_are_checked_without_io(case):
    go = deepcopy(case.root)
    for number in range(128 - len(go["code_pins"])):
        go["code_pins"]["nfl_lab/fictional_extra_%03d.py" % number] = "1" * 64
    prepared = w.prepare_template(go, case.readiness)
    assert len(go["code_pins"]) == 128 and len(s.canonical(go)) <= 60 << 10
    assert len(prepared.plain) <= 128 << 10
    go["source_config"]["fixture_padding"] = "x" * (60 << 10)
    with pytest.raises(w.RegistrationError, match="BOUNDED_FULL_REGISTRATION_ROOT"):
        w.prepare_template(go, case.readiness)
    assert not case.server.calls


@pytest.mark.parametrize("mutation", ["env_source", "root_hash", "api_source", "actor", "trigger_actor", "api_job", "partial_jobs",
    "parent_pin", "producer_pin", "truncated_tree", "commit_source", "workflow", "wrong_policy_source", "policy_after_root", "native_schema"])
def test_wrong_source_root_owner_job_and_prevalue_guards_precede_private_io(case, mutation):
    if mutation in {"wrong_policy_source", "policy_after_root"}:
        registration = case.root["publication_registration"]
        policy = c.decode(gzip.decompress(base64.b64decode(registration["policy_gzip_base64"])))
        policy["source_sha" if mutation == "wrong_policy_source" else "registered_at_utc"] = old.A if mutation == "wrong_policy_source" else c.now().isoformat()
        body = s.canonical(policy)
        registration.update(policy_gzip_base64=base64.b64encode(gzip.compress(body, mtime=0)).decode(), policy_sha256=s.sha(body))
    env_change = None
    if mutation == "env_source": env_change = lambda env: env.update(GITHUB_SHA=old.A)
    if mutation == "root_hash": env_change = lambda env: env.update(AUDIT_WEEKLY_ROOT_GO_SHA256="0" * 64)
    if mutation == "api_source": case.data[c.run_url(RUN)]["head_sha"] = old.A
    if mutation == "actor": case.data[c.run_url(RUN)]["actor"] = deepcopy(c.BOT)
    if mutation == "trigger_actor": case.data[c.run_url(RUN)]["triggering_actor"] = deepcopy(c.BOT)
    if mutation == "api_job": case.job(PHASES[0])["id"] = 999
    if mutation == "partial_jobs": case.data[c.jobs_url(RUN)]["total_count"] = 4
    if mutation in {"parent_pin", "producer_pin", "truncated_tree"}:
        tree = case.data[c.API + "/git/trees/" + ("1" if mutation == "parent_pin" else "2") * 40 + "?recursive=1"]
        if mutation == "truncated_tree": tree["truncated"] = True
        else: tree["tree"][0]["sha"] = "0" * 40
    if mutation == "commit_source": case.data[c.API + "/git/commits/" + old.A]["sha"] = old.B
    if mutation == "workflow": case.data[c.contents_url(c.WORKFLOW, old.A)] = old.content(c.WORKFLOW, old.wf())
    call = case.start(PHASES[0], env_change=env_change)
    if mutation == "native_schema":
        native = c.decode(call.env["AUDIT_WEEKLY_NATIVE_AUTHORITY_JSON"])
        native["schema_version"] = w.VERSION + "-native-authority"
        call.env["AUDIT_WEEKLY_NATIVE_AUTHORITY_JSON"] = s.canonical(native).decode()
    with pytest.raises((w.RegistrationError, c.ControllerError, t.TemplateError, s.StoreError)):
        w.run(call.args, call.env, transport=case.server)
    assert not Path(call.request["output"]).exists()
    assert not any(r.method == "POST" or "/releases/" in r.full_url for r in case.server.calls)


@pytest.mark.parametrize("mutation", ["receipt_digest", "receipt_body", "failed_run", "failed_job", "wrong_job_source", "out_of_order", "after_root", "wrong_workflow"])
def test_readiness_is_actual_prior_count7_receipt_and_successful_chain(case, mutation):
    if mutation == "receipt_digest": case.root["effective_epoch"]["previous_capture"]["receipt_sha256"] = "0" * 64
    if mutation == "receipt_body":
        path = c.receipt_path(case.x.p)
        case.data[c.contents_url(path, "lab-state")] = old.content(path, gzip.compress(b"{}", mtime=0))
    if mutation == "failed_run": case.data[c.run_url("200")]["conclusion"] = "failure"
    if mutation == "failed_job": case.data[c.jobs_url("200")]["jobs"][1]["conclusion"] = "failure"
    if mutation == "wrong_job_source": case.data[c.jobs_url("200")]["jobs"][1]["head_sha"] = old.A
    if mutation == "out_of_order": case.data[c.jobs_url("200")]["jobs"][1]["started_at"] = case.data[c.jobs_url("200")]["jobs"][0]["started_at"]
    if mutation == "after_root": case.data[c.jobs_url("200")]["jobs"][2]["completed_at"] = c.now().isoformat()
    if mutation == "wrong_workflow": case.data[c.contents_url(c.WORKFLOW, old.C)] = old.content(c.WORKFLOW, b"fictional modified workflow")
    call = case.start(PHASES[0])
    with pytest.raises((w.RegistrationError, c.ControllerError, t.TemplateError, s.StoreError)):
        w.run(call.args, call.env, transport=case.server)
    assert not any("/releases/" in r.full_url or r.method == "POST" for r in case.server.calls)


@pytest.mark.parametrize("mutation", ["root", "source", "job", "descriptor", "same_process", "writer_running"])
def test_reader_requires_exact_handoff_separate_process_and_completed_writer(case, mutation):
    write = case.execute(PHASES[0])
    case.finish(PHASES[0])
    handoff = deepcopy(write.docs["template_handoff"])
    if mutation == "root": handoff["root_go_sha256"] = "0" * 64
    if mutation == "source": handoff["writer"]["source_sha"] = old.A
    if mutation == "job": handoff["writer"]["job_id"] = b.JOBS["seal"]
    if mutation == "descriptor": handoff["descriptor"]["manifest_sha256"] = "0" * 64
    call = case.start(PHASES[1], {"template_handoff": handoff})
    if mutation == "same_process": case.state.process = handoff["writer"]["process_identity"]
    if mutation == "writer_running": case.job(PHASES[0]).update(status="in_progress", conclusion=None, completed_at=None)
    case.server.calls.clear()
    with pytest.raises((w.RegistrationError, c.ControllerError, t.TemplateError, s.StoreError)):
        w.run(call.args, call.env, transport=case.server)
    assert not any("/releases/" in r.full_url for r in case.server.calls)


@pytest.mark.parametrize("mutation", ["writer_receipt", "reader_receipt", "reader_proof", "descriptor", "writer_clock", "reader_clock",
    "reader_running", "reader_failed", "reader_source", "premature_sealer", "completed_sealer", "same_process"])
def test_sealer_never_accepts_fictional_receipts_clocks_or_premature_jobs(case, mutation):
    write, read, inputs = writer_reader(case)
    inputs = deepcopy(inputs)
    if mutation == "writer_receipt": inputs["writer_native"]["receipt_sha256"] = "0" * 64
    if mutation == "reader_receipt": inputs["reader_native"]["receipt"]["receipt_sha256"] = "0" * 64
    if mutation == "reader_proof":
        inputs["reader_native"]["proof"]["exact_readback"] = False
        forged_sha = s.sha(s.canonical(inputs["reader_native"]["proof"]))
        inputs["reader_native"]["receipt"]["receipt_sha256"] = forged_sha
        inputs["template_seal"]["reader_proof_sha256"] = forged_sha
    if mutation == "descriptor": inputs["template_seal"]["descriptor"]["manifest_asset_id"] += 1
    if mutation == "writer_clock": inputs["writer_native"]["started_at_utc"] = (c.utc(case.root["issued_at_utc"]) - timedelta(seconds=1)).isoformat()
    if mutation == "reader_clock": inputs["reader_native"]["receipt"]["completed_at_utc"] = case.root["issued_at_utc"]
    call = case.start(PHASES[2], inputs)
    if mutation == "reader_running": case.job(PHASES[1]).update(status="in_progress", conclusion=None, completed_at=None)
    if mutation == "reader_failed": case.job(PHASES[1])["conclusion"] = "failure"
    if mutation == "reader_source": case.job(PHASES[1])["head_sha"] = old.A
    if mutation == "premature_sealer": case.job(PHASES[2])["started_at"] = case.job(PHASES[1])["started_at"]
    if mutation == "completed_sealer": case.finish(PHASES[2])
    if mutation == "same_process": case.state.process = read.docs["template_seal"]["reader"]["process_identity"]
    case.server.calls.clear()
    with pytest.raises((w.RegistrationError, c.ControllerError, t.TemplateError, s.StoreError)):
        w.run(call.args, call.env, transport=case.server)
    assert not Path(call.request["output"]).exists()
    assert not any(r.method != "GET" for r in case.server.calls)


def test_sealer_checks_physical_native_bytes_not_only_saved_proof_flags(case):
    _, _, inputs = writer_reader(case)
    blob = next(asset for asset in case.server.assets if asset["name"].startswith("blob-"))
    blob["body"] += b"CORRUPT_FICTIONAL_BYTES"
    call = case.start(PHASES[2], inputs)
    with pytest.raises(s.StoreError):
        w.run(call.args, call.env, transport=case.server)
    assert not Path(call.request["output"]).exists()


def test_hosted_gate_and_source_callback_are_live_and_process_bound(case):
    call = case.start(PHASES[0])
    live = w.authenticate_child(call.args, call.env, transport=case.server)
    with pytest.raises(w.RegistrationError): pickle.dumps(live)
    def reject(*_args, **_kwargs):
        raise w.RegistrationError("FICTIONAL_HOSTED_GATE_REJECTED")
    case.host.child_context = reject
    case.server.calls.clear()
    with pytest.raises(w.RegistrationError, match="FICTIONAL_HOSTED_GATE_REJECTED"):
        live.client("append")
    assert not case.server.calls


def test_source_bytes_are_rechecked_by_native_callback(case):
    call = case.start(PHASES[0])
    live = w.authenticate_child(call.args, call.env, transport=case.server)
    path = case.source / w.FILES[0]
    path.write_bytes(b"FICTIONAL changed after initial guard")
    case.server.calls.clear()
    with pytest.raises(c.ControllerError, match="CURRENT_CODE_INVENTORY_MISMATCH"):
        live.client("append")
    assert not case.server.calls


def test_worker_never_enumerates_environment_or_reads_unrelated_credentials(case):
    call = case.start(PHASES[0])
    class Environment:
        def get(self, name, default=None):
            assert name in call.env, "UNRELATED_ENVIRONMENT_READ_FORBIDDEN"
            return call.env.get(name, default)
        def __getitem__(self, name):
            return self.get(name)
        def __iter__(self):
            pytest.fail("ENVIRONMENT_ENUMERATION_FORBIDDEN")
    result = w.run(call.args, Environment(), transport=case.server)
    assert result["phase"] == PHASES[0]


@pytest.mark.parametrize("change", [dict(actor=c.BOT), dict(triggering_actor=c.BOT), dict(head_sha=old.B),
    dict(head_branch="wrong-qualification"), dict(status="in_progress", conclusion=None), dict(conclusion="failure")])
def test_original_runtime_requires_actual_successful_owner_run_before_native_transport(case, change):
    q = case.root["qualified_runtime"]["qualification"]
    run = old.run(QRUN, q["source_sha"], "fictional", c.OWNER)
    run.update(deepcopy(change))
    case.data[c.run_url(QRUN)] = run
    call = case.start(PHASES[0])
    with pytest.raises(c.ControllerError):
        w.run(call.args, call.env, transport=case.server)
    assert not any("/releases/" in r.full_url or r.method == "POST" for r in case.server.calls)
    assert not Path(call.request["output"]).exists()


def test_prep_contract_and_closed_request_do_not_read_files_or_credentials(monkeypatch, capsys):
    def forbidden(*_args, **_kwargs):
        pytest.fail("PREPARATION_IO_FORBIDDEN")
    monkeypatch.setattr(s, "read_local", forbidden)
    monkeypatch.setattr(s, "Client", forbidden)
    request = w.build_request(PHASES[0], code_pins={name: "1" * 64 for name in w.REQUIRED_PINS},
        cache="/tmp/fictional/cache", state_root="/tmp/fictional/state", output="/tmp/fictional/" + PHASES[0], inputs={"readiness": None})
    assert w.validate_request(request, PHASES[0]) == request
    assert cli.main(["contract"]) == 0
    assert json.loads(capsys.readouterr().out)["authority_namespace"] == "AUDIT_WEEKLY_NATIVE_AUTHORITY"
    assert cli.main([PHASES[0], "--request", "/PRIVATE_NEVER_READ", "--request-sha256", "PRIVATE_NEVER_PRINT"]) == 2
    assert "PRIVATE_NEVER" not in capsys.readouterr().out
    for replacement in ({"readiness": {"authenticated": True}}, {"readiness": None, "approved": True}):
        bad = deepcopy(request)
        bad["inputs"] = replacement
        with pytest.raises(w.RegistrationError): w.validate_request(bad, PHASES[0])
    bad = deepcopy(request)
    bad["code_pins"].update({"nfl_lab/fictional_%03d.py" % n: "1" * 64 for n in range(129)})
    with pytest.raises(w.RegistrationError): w.validate_request(bad, PHASES[0])


@pytest.mark.parametrize("change", [{"parent_source_sha": "0" * 39}, {"approved": True}, {"controller_context": {}}, {"schema_version": "other"}])
def test_root_registration_context_is_closed_without_json_authority(change):
    value = dict(schema_version=w.VERSION + "-context", parent_source_sha=old.A,
        previous_capture=dict(feed_sha256="1" * 64, receipt_sha256="2" * 64))
    value.update(change)
    with pytest.raises(w.RegistrationError): w.context(value)


def test_actual_os_cpu_address_space_wall_guard_and_safe_cli_failure():
    script = """
import json, socket, sys
sys.path.insert(0, sys.argv[1])
from nfl_lab import audit_weekly_controller_registration_v1 as w
try:
    w.native_envelope()
except w.RegistrationError:
    pass
else:
    raise AssertionError('UNBOUNDED_NATIVE_ENVELOPE_ACCEPTED')
from tools.private_draft_store_v2 import limits
limits()
w.native_envelope()
import signal
signal.alarm(0)
try:
    w.native_envelope()
except w.RegistrationError:
    pass
else:
    raise AssertionError('MISSING_NATIVE_WALL_TIMER_ACCEPTED')
socket.socket.connect = lambda *_: (_ for _ in ()).throw(AssertionError('REAL_NETWORK_FORBIDDEN'))
from tools import audit_weekly_controller_registration_v1 as cli
assert cli.main(['controller-template-write', '--execute', '--request', '/PRIVATE_NEVER_READ', '--request-sha256', '0'*64], environ={}) == 1
"""
    run = subprocess.run([sys.executable, "-I", "-B", "-c", script, str(ROOT)], capture_output=True, text=True, timeout=30)
    assert run.returncode == 0, run.stderr
    result = json.loads(run.stdout)
    assert result["state"] == "FAILED_LOCAL" and result["registration_run_completed"] is False
    assert "PRIVATE_NEVER_READ" not in run.stdout


def test_the_actual_complete_producer_inventory_passes_registration_path_admission():
    from nfl_lab import audit_weekly_hosted_v1 as hosted
    actual = hosted.pins()
    assert len(actual) <= w.LIMITS["source_pins"]
    assert "reports/private-draft-canary-v2/ACTUAL_HOSTED_RESULT.json" in actual
    w._pins(actual)
