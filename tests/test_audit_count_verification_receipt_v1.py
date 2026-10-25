"""Invented owned controls + separately injected Actions context/HTTP only.

These fixtures do not establish genuine Actions provenance or publish anything.
No original models, NFL data, outcomes, fits, secrets or remote writes are used.
"""
from contextlib import redirect_stdout
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import io
import json
from pathlib import Path
from urllib.error import URLError

import pytest

from nfl_lab import audit_count_checkpoint_v1 as checkpoint, gha_private_checkpoint as cp, private_draft_store as store
from nfl_lab.operational_storage import OperationalStorage
from tools import audit_count_verification_receipt_v1 as tool
from test_private_draft_store_v2 import RUN, SOURCE, Server, Response

ROOT = Path(__file__).resolve().parents[1]


class FictionalHTTP:
    def __init__(self, restored, started, completed):
        self.restored, self.started, self.completed = restored, started, completed
        self.calls, self.created = [], None
        self.bad_source = False
        self.step_success = True
        self.writer_success = True
        self.ambiguous = False
        self.post_status = 201
        self.bad_post = False
        self.bad_readback = False
        self.redirect = False

    def __call__(self, request, timeout):
        self.calls.append(request)
        assert request.get_header("Authorization") == "Bearer ghs_FICTIONAL"
        if request.full_url == store.API + "/actions/runs/" + RUN:
            return Response(dict(id=int(RUN), head_sha="b"*40 if self.bad_source else SOURCE, event="workflow_dispatch",
                run_attempt=1, status="in_progress", path=".github/workflows/lab.yml",
                repository=dict(full_name=store.REPO), head_repository=dict(full_name=store.REPO)))
        if request.full_url == store.API + "/actions/runs/" + RUN + "/jobs?per_page=100&page=1":
            jobs = [dict(id=777, name=checkpoint.WRITER_JOB, run_id=int(RUN), head_sha=SOURCE,
                status="completed", conclusion="success" if self.writer_success else "failure",
                started_at=(self.started-timedelta(minutes=3)).isoformat(), completed_at=(self.started-timedelta(minutes=1)).isoformat()),
                dict(id=778, name=checkpoint.READER_JOB, run_id=int(RUN), head_sha=SOURCE, status="in_progress",
                    started_at=self.started.isoformat(), steps=[dict(name=tool.RESTORE_STEP, status="completed",
                    conclusion="success" if self.step_success else "failure", started_at=self.started.isoformat(),
                    completed_at=self.completed.isoformat())])]
            return Response(dict(total_count=len(jobs), jobs=jobs))
        if request.full_url == tool.ENDPOINT and request.method == "POST":
            assert len(request.data) <= 24 << 10
            payload = json.loads(request.data)
            self.created = dict(payload, id=919, url=tool.ENDPOINT+"/919")
            if self.ambiguous:
                raise URLError("PRIVATE token/path/URL NEVER_LOG")
            if self.redirect:
                return Response(status=302, headers={"Location":"https://forbidden.invalid/PRIVATE"})
            if self.bad_post:
                self.created["head_sha"] = "b"*40
            return Response(self.created, self.post_status)
        if request.full_url == tool.ENDPOINT+"/919" and request.method == "GET":
            result = deepcopy(self.created)
            if self.bad_readback:
                result["output"]["summary"] += " "
            return Response(result)
        raise AssertionError("unexpected fictional endpoint or method")

    def posts(self):
        return [request for request in self.calls if request.method == "POST"]


@pytest.fixture
def fictional_packet(tmp_path):
    checkout = tmp_path/"fictional-checkout"
    path = checkout/tool.SELF_PIN
    path.parent.mkdir(parents=True)
    path.write_bytes(b"FICTIONAL reviewed receipt source")
    policy_body = (ROOT/"config/operational-source-policy-v2.json").read_bytes()
    (checkout/"config").mkdir()
    (checkout/"config/operational-source-policy-v2.json").write_bytes(policy_body)
    initial = tmp_path/"initial-journal"
    initial.mkdir(mode=0o700)
    binding = store.initialize(store.Client("ghs_FICTIONAL", RUN, journal=initial, source_sha=SOURCE,
                              transport=Server(), process="e"*64), "c"*32)
    archived = checkout/"reports/private-draft-canary-v2/ACTUAL_HOSTED_RESULT.json"
    archived.parent.mkdir(parents=True)
    archived.write_bytes(store.canonical(dict(binding=binding)))
    runner = tmp_path/"runner"
    root = runner/(tool.audit.VERSION+"-"+RUN)
    storage = OperationalStorage(root/"cache", json.loads(policy_body), state=root/"state")
    storage.register_root(root)
    journal = root/"private-journal"
    journal.mkdir(mode=0o700)
    now = datetime.now(timezone.utc)
    started, completed = now-timedelta(minutes=3), now-timedelta(minutes=1)
    workflow = tool.hosted.WORKFLOW_REF
    job = dict(execution_lane="github_actions", workflow_ref=workflow, workflow_sha=SOURCE,
        job_id=checkpoint.READER_JOB, permission="write", event_name="workflow_dispatch", api_job_id=778, run_authenticated=True)
    previous = store.Client("ghs_FICTIONAL", RUN, journal=journal, source_sha=SOURCE, transport=Server(),
                            process="5"*64, job=job, operation="restore")
    previous.bind(binding)
    reader = cp.client_identity(previous)
    producer = dict(reader, job_id=checkpoint.WRITER_JOB, api_job_id=777, process_identity="4"*64)
    proofs = []
    for digest in ("d"*64, "f"*64):
        previous.calls, previous.transferred = 12, 1000
        proof = store.receipt(previous, "restore", exact_readback=True, separate_process=True,
                              draft_before_after=True, payload_sha256=digest, bytes=150)
        proof.update(started_at_utc=(started+timedelta(seconds=5)).isoformat(),
                     created_at_utc=(completed-timedelta(seconds=10)).isoformat())
        proofs.append(proof)
    slots, models = [], []
    for index,(target,family,method) in enumerate(cp.JOBS):
        manifest_sha = store.sha(("FICTIONAL manifest "+str(index)).encode())
        count = family == "count_A"
        slots.append(dict(target=target, family=family, method_id=method, procedure_version="a"*64,
            model_sha256="b"*64, manifest_sha256=manifest_sha, transport_manifest_sha256="c"*64,
            warm_rows=1, warm_bits_identical=True, fallback_rows=1, fallback_oracle_applicable=count,
            fallback_oracle_passed=True if count else None))
        models.append(dict(path="/PRIVATE/NEVER_LOG/manifest-"+str(index), bytes=100, sha256=manifest_sha))
    catalog = dict(schema_version=checkpoint.VERSION+"-replay-catalog", repository=store.REPO, source_sha=SOURCE,
        run_id=RUN, slots=slots, fits=0, model_pairs=18, scientific_qualification=False, public_release=False)
    catalog_body = checkpoint.safe_replay_catalog(catalog)
    root_go = dict(expires_at_utc=(now+timedelta(minutes=20)).isoformat(),
                   helper_sha256={tool.SELF_PIN:store.sha(path.read_bytes())})
    root_body = store.canonical(root_go)
    root_sha = store.sha(root_body)
    restored = dict(schema_version=checkpoint.VERSION+"-restore", state="EFFECTIVE18_RESTORED_AND_LOADER_REPLAYED",
        root_go_sha256=root_sha, original_producer=producer, reader=reader, models=models, files=38, model_pairs=18,
        proofs=proofs, index_sha256="d"*64, group_sha256=["f"*64], fits=0, fresh_process_replay=True,
        model_artifact_durability=True, replay_catalog=catalog, replay_catalog_sha256=store.sha(catalog_body),
        successful_forecast=False, public_release=False, scientific_qualification=False, private_durability_qualified=False,
        actual_completed_at=(completed-timedelta(seconds=5)).isoformat(), private_only_control="PRIVATE NEVER_LOG /tmp/secret")
    base = root/"effective-checkpoint-restore"
    storage.write_bytes(base/"REPLAY_CATALOG.json", catalog_body)
    storage.write_bytes(base/"RESTORED.json", store.canonical(restored))
    env = dict(AUDIT_COUNT_ROOT_GO_JSON=root_body.decode(), AUDIT_COUNT_ROOT_GO_SHA256=root_sha,
        GITHUB_JOB=checkpoint.READER_JOB, GITHUB_RUN_ID=RUN, GITHUB_SHA=SOURCE, GITHUB_TOKEN="ghs_FICTIONAL",
        RUNNER_TEMP=str(runner), GITHUB_WORKFLOW_REF=workflow)
    return dict(checkout=checkout, root=root, storage=storage, base=base, env=env, root_go=root_go, job=job,
        catalog=catalog, restored=restored, http=FictionalHTTP(restored, started, completed), binding=binding)


@pytest.fixture
def fictional_context(fictional_packet, monkeypatch):
    """Authority/checkout fixture is separate from the HTTP identity fixture."""
    packet = fictional_packet
    monkeypatch.setattr(tool, "ROOT", packet["checkout"])
    seen = []
    def approved_context(body, digest, env):
        assert body == packet["env"]["AUDIT_COUNT_ROOT_GO_JSON"].encode()
        assert digest == packet["env"]["AUDIT_COUNT_ROOT_GO_SHA256"]
        seen.append("owner-sealed-fictional-context")
        return packet["root_go"]
    monkeypatch.setattr(tool.hosted, "checked_root", approved_context)
    monkeypatch.setattr(tool, "actions_context", lambda env, permission:dict(packet["job"], api_job_id=0, run_authenticated=False))
    packet["context_calls"] = seen
    return packet


def assert_no_public_private_bytes(body):
    for marker in (b"PRIVATE", b"NEVER_LOG", b"/tmp/", b"/workspace/", b"/home/", b"ghs_", b"fixture", b"float64_hex", b"content_b64"):
        assert marker not in body


def test_one_exact_check_POST_and_exact_remote_readback_only(fictional_context):
    p = fictional_context
    result = tool.run(p["env"], transport=p["http"])
    assert set(result) == {"check_run_id", "body_sha256"}
    assert result["check_run_id"] == 919
    posts = p["http"].posts()
    assert len(posts) == 1 and posts[0].full_url == tool.ENDPOINT
    payload = json.loads(posts[0].data)
    assert result["body_sha256"] == store.sha(posts[0].data)
    assert len(posts[0].data) <= 24 << 10
    assert set(payload) == {"name","head_sha","status","conclusion","external_id","output"}
    assert payload["name"] == "Effective model restoration"
    assert payload["head_sha"] == SOURCE and payload["external_id"] == RUN+":1"
    public = json.loads(payload["output"]["summary"])
    assert set(public) == tool.PUBLIC_KEYS
    assert public["replay_catalog"] == p["catalog"]
    assert len(public["replay_catalog"]["slots"]) == public["model_pairs"] == 18
    assert public["model_artifact_durability"] is True
    assert public["successful_forecast"] is public["scientific_qualification"] is public["public_release"] is False
    assert_no_public_private_bytes(posts[0].data)
    output = p["base"]/tool.VERSION
    assert (output/"POST_INTENT.json").exists() and (output/"READBACK_VERIFIED.json").exists()
    assert p["http"].calls[-1].full_url == tool.ENDPOINT+"/919"


def test_deterministic_payload_and_immutable_intent_before_transport(fictional_context, monkeypatch):
    p = fictional_context
    original_http = p["http"]
    def inspect(req, timeout):
        if req.method == "POST":
            path = p["base"]/tool.VERSION/"POST_INTENT.json"
            intent = json.loads(path.read_bytes())
            assert intent["body_sha256"] == store.sha(req.data)
            assert intent["bytes"] == len(req.data)
            assert p["storage"].validate_reference(path)["sha256"] == store.sha(path.read_bytes())
            assert list((p["root"]/"private-journal").glob("*.reservation.json"))
        return original_http(req, timeout)
    result = tool.run(p["env"], transport=inspect)
    saved = (p["base"]/tool.VERSION/"PAYLOAD.json").read_bytes()
    assert saved == original_http.posts()[0].data
    assert json.dumps(json.loads(saved),sort_keys=True,separators=(',',':'),allow_nan=False).encode() == saved
    assert result["body_sha256"] == store.sha(saved)


@pytest.mark.parametrize("field,value",[("model_pairs",17),("fits",1),("model_artifact_durability",False),
    ("fresh_process_replay",False),("successful_forecast",True),("public_release",True),("scientific_qualification",True),
    ("root_go_sha256","0"*64)])
def test_incomplete_or_ineligible_controls_never_POST(fictional_context, field, value):
    p = fictional_context
    bad = deepcopy(p["restored"])
    bad[field] = value
    # Corruption is injected at the decoded metadata seam, never by weakening
    # original CAS or changing an existing retained control.
    original = tool.owned_json
    def read(storage, path, cap):
        doc, body, reference = original(storage, path, cap)
        return (bad, body, reference) if Path(path).name == "RESTORED.json" else (doc, body, reference)
    from unittest.mock import patch
    with patch.object(tool, "owned_json", side_effect=read), pytest.raises(store.StoreError):
        tool.run(p["env"], transport=p["http"])
    assert not p["http"].posts()


def test_actual_Actions_identity_precedes_private_control_reads(fictional_context, monkeypatch):
    p = fictional_context
    p["http"].bad_source = True
    monkeypatch.setattr(tool, "owned_json", lambda *a:pytest.fail("private control before Actions authentication"))
    with pytest.raises(store.StoreError, match="ACTIONS_API_IDENTITY"):
        tool.run(p["env"], transport=p["http"])
    assert not p["http"].posts()


@pytest.mark.parametrize("attribute",["step_success","writer_success"])
def test_actual_failed_step_or_producer_cannot_publish_success(fictional_context, attribute):
    p = fictional_context
    setattr(p["http"], attribute, False)
    with pytest.raises(store.StoreError):
        tool.run(p["env"], transport=p["http"])
    assert not p["http"].posts()


def test_wrong_restore_proof_source_rejected_before_POST(fictional_context, monkeypatch):
    p = fictional_context
    bad = deepcopy(p["restored"])
    bad["proofs"][0]["source_sha"] = "b"*40
    original = tool.owned_json
    def read(storage, path, cap):
        doc, body, reference = original(storage, path, cap)
        return (bad, body, reference) if Path(path).name == "RESTORED.json" else (doc, body, reference)
    monkeypatch.setattr(tool, "owned_json", read)
    with pytest.raises(store.StoreError):
        tool.run(p["env"], transport=p["http"])
    assert not p["http"].posts()


def test_unowned_catalog_rejected(fictional_context):
    p = fictional_context
    from unittest.mock import patch
    with patch.object(p["storage"].__class__, "validate_reference", side_effect=ValueError("PRIVATE unowned control")), pytest.raises(ValueError):
        tool.run(p["env"], transport=p["http"])
    assert not p["http"].posts()


@pytest.mark.parametrize("attribute",["ambiguous","bad_post","bad_readback","redirect"])
def test_ambiguous_or_mismatched_POST_has_marker_and_no_retry(fictional_context, attribute):
    p = fictional_context
    setattr(p["http"], attribute, True)
    with pytest.raises(store.StoreError):
        tool.run(p["env"], transport=p["http"])
    output = p["base"]/tool.VERSION
    assert (output/"POST_INTENT.json").exists() and (output/"POST_FAILED_OR_AMBIGUOUS.json").exists()
    assert not (output/"READBACK_VERIFIED.json").exists()
    assert len(p["http"].posts()) == 1
    with pytest.raises(store.StoreError, match="ALREADY_ATTEMPTED_NO_RETRY"):
        tool.run(p["env"], transport=p["http"])
    assert len(p["http"].posts()) == 1


def test_duplicate_completed_receipt_never_posts_twice(fictional_context):
    p = fictional_context
    tool.run(p["env"], transport=p["http"])
    with pytest.raises(store.StoreError, match="ALREADY_ATTEMPTED_NO_RETRY"):
        tool.run(p["env"], transport=p["http"])
    assert len(p["http"].posts()) == 1


@pytest.mark.parametrize("status", [403, 429, 500])
def test_permission_rate_or_server_failure_is_not_retried(fictional_context, status):
    p = fictional_context
    p["http"].post_status = status
    with pytest.raises(store.StoreError, match="VERIFICATION_HTTP_OR_RATE_AMBIGUITY"):
        tool.run(p["env"], transport=p["http"])
    assert len(p["http"].posts()) == 1
    assert (p["base"]/tool.VERSION/"POST_FAILED_OR_AMBIGUOUS.json").exists()


def test_unknown_catalog_row_fields_never_reach_public_summary(fictional_context, monkeypatch):
    p = fictional_context
    bad = deepcopy(p["catalog"])
    bad["slots"][0]["player_id"] = "PRIVATE_NEVER_LOG"
    original = tool.owned_json
    def read(storage, path, cap):
        doc, body, reference = original(storage, path, cap)
        return (bad, body, reference) if Path(path).name == "REPLAY_CATALOG.json" else (doc, body, reference)
    monkeypatch.setattr(tool, "owned_json", read)
    with pytest.raises(store.StoreError):
        tool.run(p["env"], transport=p["http"])
    assert not p["http"].posts()


def test_encoded_payload_cap_is_checked_before_intent_or_POST(fictional_context, monkeypatch):
    p = fictional_context
    monkeypatch.setattr(tool, "BODY_CAP", 1)
    with pytest.raises(store.StoreError, match="VERIFICATION_PAYLOAD_24K_CAP"):
        tool.run(p["env"], transport=p["http"])
    assert not p["http"].posts()
    assert not (p["base"]/tool.VERSION/"POST_INTENT.json").exists()


def test_unpinned_new_helper_cannot_publish_under_old_root_scope(fictional_context):
    p = fictional_context
    p["root_go"]["helper_sha256"].clear()
    with pytest.raises(store.StoreError, match="HELPER_MUST_BE_OWNER_PINNED"):
        tool.run(p["env"], transport=p["http"])
    assert not p["http"].calls


def test_cli_emits_only_id_and_hash_never_raw_error(fictional_context, monkeypatch):
    p = fictional_context
    monkeypatch.setattr(tool, "limits", lambda:None)
    out = io.StringIO()
    with redirect_stdout(out):
        code = tool.main(["--execute"], environ=p["env"], transport=p["http"])
    assert code == 0 and set(json.loads(out.getvalue())) == {"check_run_id","body_sha256"}
    assert_no_public_private_bytes(out.getvalue().encode())
    out = io.StringIO()
    with redirect_stdout(out):
        code = tool.main(["--execute"], environ=p["env"], transport=p["http"])
    assert code == 1 and json.loads(out.getvalue()) == dict(check_run_id=None,body_sha256=None)
    assert_no_public_private_bytes(out.getvalue().encode())


def test_preparation_never_reads_environment_or_HTTP():
    class NoEnvironment:
        def get(self,*args):
            raise AssertionError("environment discovery")
    out = io.StringIO()
    with redirect_stdout(out):
        assert tool.main([],environ=NoEnvironment()) == 2
    assert json.loads(out.getvalue()) == dict(check_run_id=None,body_sha256=None)


def test_real_shared_root_rejects_wrong_hash_before_token_or_HTTP(monkeypatch):
    class NoToken(dict):
        def get(self,key,default=None):
            if key == "GITHUB_TOKEN":
                raise AssertionError("credential read before owner approval")
            return super().get(key,default)
    env = NoToken(AUDIT_COUNT_ROOT_GO_JSON='{"fictional":true}',AUDIT_COUNT_ROOT_GO_SHA256="0"*64)
    with pytest.raises(tool.audit.AuditGuardError, match="ROOT_GO_HASH"):
        tool.run(env,transport=lambda *args:pytest.fail("unexpected HTTP"))
