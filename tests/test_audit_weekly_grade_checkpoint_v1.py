"""Fictional native service bytecode + live digest-bound caller; zero NFL reads."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import pickle
import socket
import subprocess
import sys

import pytest

from nfl_lab import audit_weekly_grade_checkpoint_v1 as k
from nfl_lab import audit_weekly_grade_v1 as g, private_draft_store as s, state
from tools import audit_weekly_grade_checkpoint_v1 as cli
from test_audit_weekly_grade_v1 import packet as grade_packet, grade as local_grade, qualify, GRADE
from test_audit_weekly_archive_v1 import Service as ArchiveService
from test_private_draft_store_v2 import Response, RUN, SOURCE

ROOT = Path(__file__).resolve().parents[1]
ROOT_SHA = "d" * 64


@pytest.fixture(scope="module")
def packet(tmp_path_factory):
    root = tmp_path_factory.mktemp("fictional-grade-checkpoint")
    q = grade_packet.__wrapped__(root)
    q["snapshot"] = local_grade(q, root / "grade")
    return q


class Service(ArchiveService):
    def __init__(self, path):
        super().__init__(path)
        self.now = GRADE + timedelta(minutes=1)
        self.writer_done = None
        self.bad_writer = False
        self.bad_source = False
        self.same_api_id = False
        self.run_attempt = 1
    def transport(self, request, timeout):
        if "/actions/runs/" + RUN in request.full_url:
            self.calls.append(request)
            if "/jobs?" not in request.full_url:
                return Response(dict(id=int(RUN), head_sha="b" * 40 if self.bad_source else SOURCE,
                    event="workflow_dispatch", run_attempt=self.run_attempt, status="in_progress", conclusion=None,
                    path=".github/workflows/lab.yml", head_branch="fictional", actor=dict(login="NickNicky19", id=208912933),
                    triggering_actor=dict(login="NickNicky19", id=208912933), repository=dict(full_name=s.REPO), head_repository=dict(full_name=s.REPO)))
            jobs = [dict(id=778, name=k.JOBS["writer"], run_id=int(RUN), head_sha=SOURCE,
                status="completed" if self.writer_done else "in_progress",
                conclusion=("failure" if self.bad_writer else "success") if self.writer_done else None,
                started_at=(GRADE - timedelta(minutes=1)).isoformat(), completed_at=self.writer_done)]
            if self.writer_done:
                jobs.append(dict(id=778 if self.same_api_id else 779, name=k.JOBS["reader"], run_id=int(RUN), head_sha=SOURCE,
                    status="in_progress", conclusion=None,
                    started_at=(state.utc(self.writer_done) + timedelta(seconds=50)).isoformat(), completed_at=None))
            return Response(dict(total_count=len(jobs), jobs=jobs))
        return super().transport(request, timeout)


class Parent:
    def __init__(self, q, service):
        self.q, self.service = q, service
        self.accept = True
        self.calls = []
        self.handoff = None
        self.context = None
        self.native = None
    def __call__(self, request):
        self.calls.append(deepcopy(request))
        if not self.accept:
            return False
        if request["schema_version"] == k.VERSION + "-authentication-request":
            inputs = request["inputs"]
            assert request["inputs_sha256"] == state.digest(inputs)
            if "current_root_go_sha256" in inputs:
                assert inputs["current_root_go_sha256"] == ROOT_SHA
            if request["kind"] == "CHECKPOINT_APPEND_CURRENT_ROOT":
                assert inputs["snapshot_sha256"] == self.q["snapshot"].sha256
                assert inputs["body_sha256"] == self.q["snapshot"].binding["sha256"]
            elif request["kind"] == "CHECKPOINT_APPEND_NATIVE_HANDOFF":
                self.handoff = deepcopy(inputs["handoff"])
                assert inputs["handoff_sha256"] == state.digest(self.handoff)
            elif request["kind"] == "CHECKPOINT_RESTORE_CURRENT_ROOT_AND_ORIGINAL_HANDOFF":
                assert inputs["handoff"] == self.handoff
                assert inputs["handoff_sha256"] == state.digest(self.handoff)
                self.context = deepcopy(inputs)
            elif request["kind"] == "CHECKPOINT_NATIVE_RESTORED_BODY":
                assert {key: inputs[key] for key in self.context} == self.context
                assert inputs["native_restore_proof"]["payload_sha256"] == self.handoff["body_sha256"]
                self.context = {key: deepcopy(value) for key, value in inputs.items()
                    if key not in {"native_restore_proof", "restored_binding"}}
                self.native = deepcopy(inputs)
            else:
                raise AssertionError("UNKNOWN_CALLER_AUTH_KIND")
            return True
        assert self.native is not None
        if request["kind"] == "QUALIFIED_PREVIOUS_GRADING_SNAPSHOT":
            expected = dict(binding=self.native["restored_binding"], epoch_sha256=self.q["r"].epoch.sha256)
        else:
            assert request["kind"] == "FRESH_READER_GRADING_DURABILITY"
            known = self.service.now.isoformat()
            body = dict(schema_version=k.VERSION + "-fresh-reader-native-evidence", context=self.context,
                native_restore_proof=self.native["native_restore_proof"], restored_binding=self.native["restored_binding"], known_by_at=known)
            expected = dict(schema_version=g.VERSION + "-durability", snapshot_sha256=self.q["snapshot"].sha256,
                restored_body_sha256=self.handoff["body_sha256"], known_by_at=known, producer=self.handoff["producer"],
                reader=self.context["reader"], proof_sha256=state.digest(body))
        assert request["inputs_sha256"] == state.digest(expected)
        return True


@pytest.fixture
def case(packet, tmp_path, monkeypatch):
    monkeypatch.setattr(socket.socket, "connect", lambda *_: pytest.fail("REAL_NETWORK_FORBIDDEN"))
    # Core service tests emulate native syscalls only; separate fresh processes
    # below exercise the ACTUAL hard envelope before/after limits installation.
    monkeypatch.setattr(k, "native_envelope", lambda: None)
    packet = dict(packet)
    packet["storage"].register_root(tmp_path)
    service = Service(tmp_path)
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return service.now if tz else service.now.replace(tzinfo=None)
    monkeypatch.setattr(s, "datetime", Clock)
    parent = Parent(packet, service)
    counter = [0]
    def client(role):
        counter[0] += 1
        journal = tmp_path / (role + "-journal-" + str(counter[0]));journal.mkdir(mode=0o700)
        c = k.archive.Client("ghs_FICTIONAL", RUN, journal=journal, source_sha=SOURCE, transport=service.transport,
            job=dict(execution_lane="github_actions", workflow_ref=s.REPO + "/.github/workflows/lab.yml@refs/heads/fictional",
                workflow_sha=SOURCE, job_id=k.JOBS[role], permission="write", event_name="workflow_dispatch", api_job_id=0, run_authenticated=False),
            operation="append" if role == "writer" else "restore", qualification=service.q, readonly=role == "reader",
            process=s.sha((role + str(counter[0])).encode()))
        c.bind(service.binding)
        return c
    def append():
        c = client("writer")
        value = k.append(packet["snapshot"], c, service.package, storage=packet["storage"], output=tmp_path / "append",
            current_root_go_sha256=ROOT_SHA, authenticate=parent, pending_census=service.census, clock=lambda:service.now)
        service.writer_done = (service.now + timedelta(seconds=10)).isoformat()
        service.now += timedelta(minutes=2)
        return value, c
    def restore(handoff, **updates):
        c = client("reader")
        kwargs = dict(storage=packet["storage"], output=tmp_path / "restore", current_root_go_sha256=ROOT_SHA,
            authenticate=parent, pending_census=service.census, clock=lambda:service.now)
        kwargs.update(updates)
        return k.restore(handoff, c, service.package, packet["r"], **kwargs), c
    return dict(q=packet, service=service, parent=parent, client=client, append=append, restore=restore, root=tmp_path)


def test_actual_native_bytecode_fresh_reader_returns_typed_history_not_public_success(case):
    h, writer = case["append"]()
    assert h["successful_forecast"] is h["public_release"] is False
    assert not isinstance(h, g.DurableHistory)
    result, reader = case["restore"](h)
    assert result.verify() is result and type(result.durable) is g.DurableHistory
    assert result.report["public_release"] is result.report["scientific_qualification"] is False
    assert result.proof["producer"]["job_id"] == k.JOBS["writer"] and result.proof["reader"]["job_id"] == k.JOBS["reader"]
    assert writer.calls <= 40 and reader.calls <= 40
    assert result.durable.document["week_revisions"] == case["q"]["snapshot"].document["week_revisions"]
    assert result.durable.document["legacy_history_binding"] == case["q"]["snapshot"].document["legacy_history_binding"]
    assert all(v["known_by_at"] == case["service"].now.isoformat() for v in result.durable.document["known_versions"].values())
    assert len([r for r in case["service"].calls if r.method == "POST"]) == 2
    with pytest.raises(k.CheckpointError):pickle.dumps(result)


def test_restore_caller_denial_precedes_payload_HTTP(case):
    h, _ = case["append"]()
    case["parent"].accept = False
    before = len(case["service"].server.calls)
    with pytest.raises(k.CheckpointError):case["restore"](h)
    assert not any(r.get_header("Accept") == "application/octet-stream" and "/releases/assets/" in r.full_url
        and r.full_url.endswith(str(h["descriptor"]["entry"]["payload_asset_id"])) for r in case["service"].server.calls[before:])


def test_append_caller_denial_before_any_POST(case):
    case["parent"].accept = False
    before = len(case["service"].posts())
    with pytest.raises(k.CheckpointError):case["append"]()
    assert len(case["service"].posts()) == before


@pytest.mark.parametrize("field,value", [("current_root_go_sha256", "e" * 64), ("epoch_sha256", "f" * 64),
    ("body_bytes", (8 << 20) + 1), ("body_sha256", "0" * 64), ("snapshot_sha256", "0" * 64)])
def test_handoff_current_root_epoch_body_and_snapshot_not_relabelled(case, field, value):
    h, _ = case["append"]()
    h[field] = value
    with pytest.raises((k.CheckpointError, s.StoreError)):case["restore"](h)


@pytest.mark.parametrize("attribute,value", [("bad_writer", True), ("bad_source", True), ("same_api_id", True), ("run_attempt", 2)])
def test_actual_API_failure_source_identity_or_restart_rejected(case, attribute, value):
    h, _ = case["append"]()
    setattr(case["service"], attribute, value)
    with pytest.raises((k.CheckpointError, s.StoreError)):case["restore"](h)


def test_corrupt_native_payload_no_DurableHistory(case):
    h, _ = case["append"]()
    asset = next(a for a in case["service"].server.assets if a["id"] == h["descriptor"]["entry"]["payload_asset_id"])
    asset["body"] = b"FICTIONAL corrupt native body"
    with pytest.raises(s.StoreError):case["restore"](h)


def test_saved_snapshot_JSON_is_not_typed_append_authority(case):
    q = case["q"]
    with pytest.raises(k.CheckpointError):
        k.append(q["snapshot"].document, case["client"]("writer"), case["service"].package,
            storage=q["storage"], output=case["root"] / "bad", current_root_go_sha256=ROOT_SHA,
            authenticate=case["parent"], pending_census=case["service"].census, clock=lambda:case["service"].now)


def test_native_receipt_is_not_relabelled_or_rehydrated(case, monkeypatch):
    h, _ = case["append"]()
    original = s.restore
    def wrong_receipt(*args, **kwargs):
        receipt = original(*args, **kwargs)
        receipt["process_identity"] = "0" * 64
        return receipt
    monkeypatch.setattr(s, "restore", wrong_receipt)
    with pytest.raises(k.CheckpointError, match="CLOSED_UNCHANGED_CURRENT_NATIVE_RESTORE_RECEIPT"):
        case["restore"](h)


def test_rehashed_forged_handoff_still_needs_live_caller_original_digest(case):
    h, _ = case["append"]()
    h["append_proof"]["api_evidence_sha256"] = "0" * 64
    h["append_proof_sha256"] = state.digest(h["append_proof"])
    with pytest.raises(AssertionError):case["restore"](h)


def test_no_retry_after_ambiguous_native_POST(case):
    service = case["service"]
    service.server.ambiguous = True
    with pytest.raises(s.StoreError):case["append"]()
    before = len(service.posts())
    assert before == 1 and list(case["root"].glob("writer-journal-*/*.reservation.json"))
    with pytest.raises(k.CheckpointError, match="FRESH_GRADING_CHECKPOINT_OPERATION_NO_RETRY"):
        case["append"]()
    assert len(service.posts()) == before


def test_same_process_reader_cannot_qualify_private_checkpoint(case):
    h, _ = case["append"]()
    reader = case["client"]("reader")
    reader.process = h["producer"]["process_identity"]
    with pytest.raises(k.CheckpointError, match="DISTINCT_SAME_RUN_GRADING_EXPORT_READER_REQUIRED"):
        k.restore(h, reader, case["service"].package, case["q"]["r"], storage=case["q"]["storage"],
            output=case["root"] / "bad-reader", current_root_go_sha256=ROOT_SHA,
            authenticate=case["parent"], pending_census=case["service"].census, clock=lambda:case["service"].now)


def test_previous_known_clocks_and_week_revisions_survive_real_grade_and_checkpoint(case):
    q = case["q"]
    previous = qualify(q, q["snapshot"])
    old_clocks = deepcopy(previous.document["known_versions"])
    old_weeks = deepcopy(previous.document["week_revisions"])
    assert old_clocks and old_weeks
    q["snapshot"] = local_grade(q, case["root"] / "new-local-grade", previous=previous,
        at=GRADE + timedelta(minutes=4))
    case["service"].now = GRADE + timedelta(minutes=5)
    h, _ = case["append"]()
    result, _ = case["restore"](h)
    assert all(result.durable.document["known_versions"][key] == value for key, value in old_clocks.items())
    assert result.durable.document["week_revisions"][:len(old_weeks)] == old_weeks
    assert result.report["all_negative_weeks_retained"] is True


def test_unqualified_historical_storage_package_never_POSTs(case):
    case["service"].bad_qualifier = True
    before = len(case["service"].posts())
    with pytest.raises(s.StoreError):case["append"]()
    assert len(case["service"].posts()) == before


def test_native_hard_envelope_actual_fresh_process():
    script = '''
from nfl_lab import audit_weekly_grade_checkpoint_v1 as k
try:k.native_envelope()
except k.CheckpointError:pass
else:raise AssertionError('UNBOUNDED_WORKER_ACCEPTED')
from tools.private_draft_store_v2 import limits
limits()
k.native_envelope()
print('PASS_NATIVE_180_120_512')
'''
    r = subprocess.run([sys.executable, "-B", "-c", script], cwd=ROOT, env={"PYTHONDONTWRITEBYTECODE": "1"}, capture_output=True, text=True, timeout=10)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "PASS_NATIVE_180_120_512"


def test_fictional_full_checkpoint_roundtrip_under_actual_native_envelope(packet, tmp_path):
    # Build the Arrow-based capture fixture OUTSIDE the fresh checkpoint worker.
    # The worker reconstructs typed epoch/Snapshot through the public validators,
    # with a fresh live authenticator. Existing grading may import NumPy;
    # that is distinct from restoring or executing a forecast model.
    f = packet["f"]
    seed = dict(binding=packet["snapshot"].binding, cache=str(packet["storage"].cache),
        state_root=str(packet["storage"].state_root), epoch=packet["r"].epoch.document,
        completion=packet["r"].completion, original_choice=f["raw"].decode(),
        original_completion=f["completion"], slate=f["slate"], catalog=f["catalog"], policy=f["policy"],
        history_binding=f["history_binding"], output=str(tmp_path / "native-worker"))
    path = tmp_path / "fictional-native-seed.json"
    path.write_bytes(s.canonical(seed))
    script = r'''
import ast,json,sys,socket
from pathlib import Path
from datetime import datetime,timedelta,timezone
from copy import deepcopy
sys.path.insert(0,str(Path.cwd()/"tests"))
import pytest
from tools.private_draft_store_v2 import limits
limits()
from nfl_lab import audit_weekly_grade_checkpoint_v1 as k, audit_weekly_grade_v1 as g
from nfl_lab import audit_weekly_epoch_v1 as epoch, audit_private_rotation_v1 as rotation
from nfl_lab import state, private_draft_store as s
from nfl_lab.operational_storage import OperationalStorage
from test_private_draft_store_v2 import Server,Response,RUN,SOURCE
from test_owner_private_bootstrap import qualification
seed=json.loads(Path(sys.argv[1]).read_bytes())
GRADE=state.utc("2026-10-28T08:00:00Z")
ROOT_SHA="d"*64
ROOT=Path.cwd()
e=epoch.restore_epoch(seed["epoch"],seed["original_choice"].encode(),seed["original_completion"],
 seed["slate"],seed["catalog"],seed["policy"],history_binding=seed["history_binding"],now=GRADE)
r=epoch.bind_registration(e,seed["completion"],now=GRADE)
storage=OperationalStorage(seed["cache"],ROOT/"config/operational-source-policy-v2.json",state=seed["state_root"])
def authenticate_seed(request):
 expected=state.digest(dict(binding=seed["binding"],epoch_sha256=e.sha256))
 return request["kind"]=="QUALIFIED_PREVIOUS_GRADING_SNAPSHOT" and request["inputs_sha256"]==expected
snapshot=g.restore_snapshot(storage,seed["binding"],r,authenticate=authenticate_seed,at=GRADE)
q=dict(storage=storage,snapshot=snapshot,r=r)
# Reuse the exact fictional service/caller fixture function bodies without
# importing their unrelated Arrow capture-construction fixtures.
ns=globals()
for filename,names in (("test_audit_weekly_archive_v1.py",{"Service"}),
 ("test_audit_weekly_grade_checkpoint_v1.py",{"Service","Parent","case"})):
 tree=ast.parse((ROOT/"tests"/filename).read_text())
 selected=[n for n in tree.body if isinstance(n,(ast.ClassDef,ast.FunctionDef)) and n.name in names]
 code=ast.Module(body=selected,type_ignores=[]);ast.fix_missing_locations(code)
 exec(compile(code,filename,"exec"),ns)
 if filename=="test_audit_weekly_archive_v1.py":ns["ArchiveService"]=ns["Service"]
ns["ROLES"]=dict(produce="fictional_capture_writer",restore="fictional_capture_reader",consume="fictional_capture_exporter")
path=Path(seed["output"]);path.mkdir(mode=0o700)
patch=pytest.MonkeyPatch();actual=k.native_envelope
operation=ns["case"].__wrapped__(q,path,patch)
patch.setattr(k,"native_envelope",actual)
h,_=operation["append"]()
result,_=operation["restore"](h)
assert result.verify() is result and result.report["public_release"] is False
assert result.durable.document["week_revisions"]==snapshot.document["week_revisions"]
assert "catboost" not in sys.modules
k.native_envelope()
print("PASS_FICTIONAL_ROUNDTRIP_NATIVE_180_120_512")
'''
    env = dict(PYTHONDONTWRITEBYTECODE="1", OMP_NUM_THREADS="2", OPENBLAS_NUM_THREADS="2", MKL_NUM_THREADS="2",
        NUMEXPR_NUM_THREADS="2", ARROW_IO_THREADS="2", ARROW_DEFAULT_MEMORY_POOL="system", MALLOC_ARENA_MAX="2")
    result = subprocess.run([sys.executable, "-B", "-c", script, str(path)], cwd=ROOT, env=env,
        capture_output=True, text=True, timeout=45)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "PASS_FICTIONAL_ROUNDTRIP_NATIVE_180_120_512"


def test_contract_no_implicit_execution_or_posthoc_capture5_grading(capsys):
    assert cli.main(["contract"]) == 0
    document = json.loads(capsys.readouterr().out)
    assert document["requires_prevalue_population"] is True
    assert document["capture5_without_population_is_primary_grade_candidate"] is False
    assert document["local_append_is_durable"] is document["public_release"] is False
    assert cli.main(["execute"]) == 2
