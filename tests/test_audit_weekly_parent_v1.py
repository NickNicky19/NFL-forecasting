"""Fictional HTTP only; real V2 bootstrap, parent proof, native GET and claims.

No fixture is genuine hosted evidence. Private bytes are static metadata, every
socket is denied, and all apparent Git mutations occur in the in-memory API.
The shared sidecar validator checks fictional metadata, never grading bodies.
"""
import base64
from copy import deepcopy
from datetime import timedelta
import gzip
import json
from pathlib import Path
import pickle
import socket
import subprocess
import sys
from types import SimpleNamespace
from urllib.error import URLError
from urllib.parse import urlsplit

import pytest

from nfl_lab import audit_weekly_parent_v1 as w
from nfl_lab import audit_weekly_controller_v1 as c, audit_weekly_controller_bootstrap_v1 as b
from nfl_lab import audit_weekly_template_v1 as t, private_draft_store as s
from nfl_lab import audit_weekly_grade_history_v1 as history
from tools import audit_weekly_parent_v1 as cli
from test_audit_weekly_controller_bootstrap_v1 import system, locator_system
import test_audit_weekly_controller_v1 as old
from test_private_draft_store_v2 import Server, Response

ROOT = Path(__file__).resolve().parents[1]
STATE = "4" * 40
TREE = "5" * 40
NEW_TREE = "6" * 40
COMMIT = "7" * 40


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*_args, **_kwargs):
        pytest.fail("REAL_NETWORK_FORBIDDEN")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)


class Service(Server):
    def __init__(self, x):
        super().__init__()
        self.x, self.data, self.q = x, x.api.data, x.package["qualification"]
        self.tag = x.package["binding"]["tag_name"]
        self.head, self.state_reads, self.hooks = STATE, 0, {}
        self.blobs, self.claim_path, self.claim_body, self.committed = {}, None, None, False
        self.parent_verified, self.dispatch_body, self.dispatch_status = False, None, 204
        self.duplicate, self.old_history, self.stale_at, self.patch_conflict = False, False, None, False
        self.bad_readback, self.extra_diff, self.lost_post, self.dispatch_failure = False, False, None, False

    def add_exact(self, name, body, asset_id):
        asset = self.add(name, body)
        asset.update(id=asset_id, url=s.API + "/releases/assets/" + str(asset_id))

    def __call__(self, request, timeout):
        url, method = request.full_url, request.get_method()
        assert 0 < timeout <= 10
        if url == w.STATE_REF_URL:
            self.calls.append(request)
            self.state_reads += 1
            if self.stale_at == self.state_reads: self.head = "8" * 40
            return Response(dict(ref="refs/heads/lab-state", object=dict(type="commit", sha=self.head)))
        if method == "GET" and "/contents/state/controller-v1/claims/" in url:
            self.calls.append(request)
            if self.duplicate: return Response(old.content(url.split("/contents/")[1].split("?", 1)[0], b"EXISTS"))
            if self.committed and "?ref=" + COMMIT in url:
                body = self.claim_body + b"CORRUPT" if self.bad_readback else self.claim_body
                return Response(old.content(self.claim_path, body))
            return Response(b'{"message":"Not Found"}', 404)
        if method == "GET" and "/commits?sha=lab-state&path=state/controller-v1/claims/" in url:
            self.calls.append(request)
            return Response([dict(sha=COMMIT, commit=dict(message="actual API extra fields"))] if self.committed or self.old_history else [])
        if url == c.API + "/git/commits/" + STATE:
            self.calls.append(request)
            return Response(dict(sha=STATE, tree=dict(sha=TREE), parents=[dict(sha="3" * 40)]))
        if method in {"POST", "PATCH"}:
            self.calls.append(request)
            assert self.parent_verified and request.get_header("Authorization") == "Bearer ghs_FICTIONAL"
            body = c.decode(request.data)
            if self.lost_post == url: raise URLError("PRIVATE_VALUE_NEVER_LOG")
            if url == c.API + "/git/blobs":
                assert set(body) == {"content", "encoding"} and body["encoding"] == "base64"
                claim = base64.b64decode(body["content"], validate=True)
                doc = c.decode(claim)
                assert set(doc) == c.CLAIM_KEYS and b'"root_template"' not in claim
                self.blobs[c.blob_sha(claim)] = claim
                return Response(dict(sha=c.blob_sha(claim)), 201)
            if url == c.API + "/git/trees":
                assert body["base_tree"] == TREE and len(body["tree"]) == 1
                entry = body["tree"][0]
                assert set(entry) == {"path", "mode", "type", "sha"} and entry["mode"] == "100644" and entry["type"] == "blob"
                self.claim_path, self.claim_body = entry["path"], self.blobs[entry["sha"]]
                assert self.claim_path == c.claim_path(c.decode(self.claim_body)["claim_id"])
                return Response(dict(sha=NEW_TREE, tree=body["tree"]), 201)
            if url == c.API + "/git/commits":
                assert body["parents"] == [STATE] and body["tree"] == NEW_TREE
                assert body["author"]["name"] == body["committer"]["name"] == c.BOT["login"]
                return Response(dict(sha=COMMIT, tree=dict(sha=NEW_TREE), parents=[dict(sha=STATE, url="https://api.github.com/fictional")]), 201)
            if url == w.STATE_UPDATE_URL:
                assert method == "PATCH" and body == dict(sha=COMMIT, force=False)
                if self.patch_conflict: return Response(dict(message="Not a fast forward"), 422)
                assert self.head == STATE
                self.head, self.committed = COMMIT, True
                return Response(dict(ref="refs/heads/lab-state", object=dict(type="commit", sha=COMMIT)))
            if url == w.DISPATCH_URL:
                assert method == "POST" and self.committed
                assert set(body) == {"ref", "inputs"} and body["ref"] == self.x.p["producer"]["branch"]
                assert set(body["inputs"]) == {"mode", "inference_builder_go_json", "inference_builder_go_sha256"}
                assert body["inputs"]["mode"] == c.MODE
                assert c.sha(body["inputs"]["inference_builder_go_json"].encode()) == body["inputs"]["inference_builder_go_sha256"]
                self.dispatch_body = body
                if self.dispatch_failure: raise URLError("PRIVATE_ROOT_NEVER_LOG")
                return Response(b"", self.dispatch_status)
            pytest.fail("UNEXPECTED_FICTIONAL_MUTATION_ROUTE")
        if url == c.API + "/commits/" + COMMIT:
            self.calls.append(request)
            files = [dict(filename=self.claim_path, status="added", sha=c.blob_sha(self.claim_body))]
            if self.extra_diff: files.append(dict(filename="FORBIDDEN_OTHER_FILE", status="modified"))
            return Response(dict(sha=COMMIT, parents=[dict(sha=STATE, html_url="https://github.com/fictional")], committer=deepcopy(c.BOT), files=files))
        if url in self.data:
            self.calls.append(request)
            value = deepcopy(self.data[url])
            if url in self.hooks:
                value = self.hooks[url](value, sum(r.full_url == url for r in self.calls))
            return Response(c.canonical(value))
        qrun = self.q["run_id"]
        if url == c.run_url(qrun):
            self.calls.append(request)
            return Response(old.run(qrun, self.q["source_sha"], "fictional", c.OWNER))
        if url == c.jobs_url(qrun):
            self.calls.append(request)
            return Response(dict(total_count=3, jobs=[old.job(qrun, self.q["source_sha"], p["job"]["job_id"],
                p["job"]["api_job_id"], p["started_at_utc"], p["created_at_utc"])
                for p in (self.q["before_proof"], self.q["read_proof"], self.q)]))
        if "/releases/" in url:
            assert self.parent_verified, "LIVE_SOURCE_AND_PARENT_PROOF_MUST_PRECEDE_PRIVATE_GET"
        return super().__call__(request, timeout)


def directory(path, names):
    return [dict(name=name, path=path + "/" + name, type=kind, sha=old.h(name)[:40], size=size)
        for name, kind, size in names]


def ops_sidecar(receipt, package, pins, branch):
    """Fictional closed descriptors/proofs only; no snapshot or grade body."""
    binding_sha = c.digest(package["binding"])
    grade_pins = {name:pins[name] for name in history._GRADE_PIN_PATHS}
    checkpoint_pins = {name:pins[name] for name in history._CHECKPOINT_PIN_PATHS}
    def identity(role):
        return dict(execution_lane="github_actions", repository=c.REPO, run_id=receipt["run_id"], run_attempt=1,
            source_sha=receipt["source_sha"], process_identity=old.h([receipt["run_id"],role]),
            job_id=receipt["jobs"][role]["job_id"], api_job_id=receipt["jobs"][role]["api_job_id"], permission="write",
            workflow_ref=c.REPO + "/" + c.WORKFLOW + "@refs/heads/" + branch)
    writer, reader = identity("restore"), identity("consume")
    body_sha = old.h([receipt["run_id"],"opaque checkpoint hash only"])
    def descriptor(producer, payload_sha, payload_id, manifest_id):
        entry = dict(schema_version="weekly-private-restore-manifest-v2", producer_process=producer["process_identity"],
            binding_sha256=binding_sha, writer_run_id=receipt["run_id"], payload_asset_id=payload_id,
            payload_name="blob-" + payload_sha + ".bin", payload=dict(schema_version="weekly-private-payload-v2",
                payload_kind="runtime_manifest", format="gzip", bytes=200, sha256=payload_sha, source_policy_sha256=t.POLICY_SHA))
        return dict(entry=entry, manifest_asset_id=manifest_id, manifest_sha256=c.digest(entry), manifest_bytes=len(s.canonical(entry)))
    native = descriptor(writer, body_sha, 801, 802)
    append = dict(schema_version="audit-weekly-grade-checkpoint-v1-native-append", current_root_go_sha256=receipt["root_go_sha256"],
        producer=writer, epoch_sha256=receipt["epoch_sha256"], snapshot_sha256=old.h([receipt["run_id"],"snapshot hash only"]),
        body_sha256=body_sha, body_bytes=200, descriptor_sha256=c.digest(native), qualification_sha256=c.digest(package["qualification"]),
        api_evidence_sha256=old.h("fictional completed native append API metadata"), started_at_utc="2026-10-25T12:18:00Z",
        completed_at_utc="2026-10-25T12:19:00Z", HTTP_calls=20, transfer_bytes=2000)
    handoff = dict(schema_version="audit-weekly-grade-checkpoint-v1-handoff", repository=c.REPO,
        current_root_go_sha256=receipt["root_go_sha256"], epoch_sha256=receipt["epoch_sha256"], snapshot_sha256=append["snapshot_sha256"],
        body_sha256=body_sha, body_bytes=200, snapshot_completed_at="2026-10-25T12:17:00Z", producer=writer,
        runtime_binding_sha256=binding_sha, qualified_package_sha256=c.digest(package), grade_code_pins_sha256=c.digest(grade_pins),
        helper_sha256=checkpoint_pins, descriptor=native, append_proof=append, append_proof_sha256=c.digest(append),
        successful_forecast=False, public_release=False, fits=0)
    proof = dict(schema_version="audit-weekly-grade-v1-durability", snapshot_sha256=handoff["snapshot_sha256"],
        restored_body_sha256=body_sha, known_by_at="2026-10-25T12:23:00Z", producer=writer, reader=reader,
        proof_sha256=old.h([receipt["run_id"],"original native read proof hash only"]))
    return dict(schema_version=history.VERSION + "-sidecar", repository=c.REPO,
        **{name:receipt[name] for name in ("feed_sha256","source_sha","run_id","root_go_sha256","workflow_sha256","epoch_sha256")},
        workflow_ref=writer["workflow_ref"], checkpoint_handoff=handoff, grade_read_proof=proof,
        grade_code_pins=grade_pins, checkpoint_helper_sha256=checkpoint_pins,
        evidence_descriptor=descriptor(reader, old.h([receipt["run_id"],"envelope hash only"]), 803, 804), evidence_producer=reader)


@pytest.fixture
def case(locator_system, tmp_path, monkeypatch):
    x = locator_system
    x.p["cadence"] = deepcopy(c.PARENT_CADENCE)
    x.workflow = x.workflow.replace(c.CADENCE["cron"].encode(), c.PARENT_CADENCE["cron"].encode())
    for role, source, sha in (("parent",x.parent_source,old.A),("producer",x.child_source,old.B)):
        (source/c.WORKFLOW).write_bytes(x.workflow)
        x.p[role]["workflow_sha256"] = c.sha(x.workflow)
        x.api.data[c.contents_url(c.WORKFLOW,sha)] = old.content(c.WORKFLOW,x.workflow)
    x.native["workflow_sha256"] = c.sha(x.workflow)
    x.package = {name:deepcopy(x.package[name]) for name in b.PACKAGE_KEYS}
    x.locators["qualified_runtime_package"] = x.package
    for role, source in (("parent", x.parent_source), ("producer", x.child_source)):
        pins = x.p[role]["code_pins"]
        for name in sorted(w.REQUIRED_PINS | set(history.FILES) | history._GRADE_PIN_PATHS | history._CHECKPOINT_PIN_PATHS | history.LOCATOR_HELPERS):
            path = source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            if name == "config/operational-source-policy-v2.json": body = (ROOT / name).read_bytes()
            elif path.exists(): body = path.read_bytes()
            else: body = ("FICTIONAL reviewed parent code " + name).encode()
            path.write_bytes(body)
            pins[name] = c.sha(body)
    root = deepcopy(x.prepared.document["root_template"])
    root.update(code_pins=deepcopy(x.p["producer"]["code_pins"]), qualified_runtime=deepcopy(x.package),
        publication=True, source_config=dict(purpose="CURRENT_OPERATIONAL_INFERENCE", fixture_same_week="UNCHANGED"),
        owner_authorization="OWNER_NFL_AUDIT_CONTINUATION_20261025", jobs={r:x.p["producer"]["jobs"][r] for r in c.ROLES},
        failure_restorer=x.p["producer"]["jobs"]["evidence"])
    policy = dict(schema_version="audit-weekly-derived-policy-v3", state="ROOT_REGISTERED", source_sha=old.B,
        source_branch=x.p["producer"]["branch"], workflow_sha256=x.p["producer"]["workflow_sha256"],
        producer_policy_sha256=old.h("same source recipe"), registered_at_utc="2026-10-25T11:00:00Z")
    body = s.canonical(policy)
    root["publication_registration"] = dict(policy_gzip_base64=base64.b64encode(gzip.compress(body, mtime=0)).decode(),
        policy_sha256=s.sha(body), rights_authority=dict(fixture="UNCHANGED_RIGHTS"), r0=dict(fixture="UNCHANGED_R0"))

    def reseal():
        x.prepared = t.prepare(dict(schema_version=getattr(x,"template_schema",t.VERSION + "-static"), source_sha=old.B,
            code_pins=deepcopy(x.p["producer"]["code_pins"]), readiness=deepcopy(x.p["readiness"]), root_template=deepcopy(root)))
        ts = x.template_seal
        entry = ts["descriptor"]["entry"]
        entry["payload"].update(bytes=len(x.prepared.body), sha256=s.sha(x.prepared.body))
        entry["payload_name"] = "blob-" + s.sha(x.prepared.body) + ".bin"
        ts["descriptor"].update(manifest_sha256=s.sha(s.canonical(entry)), manifest_bytes=len(s.canonical(entry)))
        ts.update(template_sha256=s.sha(x.prepared.plain), template_bytes=len(x.prepared.plain))
        summary = dict(schema_version=b.LOCATOR_VERSION + "-private-template-descriptor", template_sha256=s.sha(x.prepared.plain),
            template_bytes=len(x.prepared.plain), private_descriptor_sha256=s.sha(s.canonical(ts["descriptor"])),
            storage_binding_sha256=s.sha(s.canonical(ts["binding"])))
        x.reg = c.canonical(x.p)
        x.native.update(registration_sha256=c.sha(x.reg), template_descriptor=summary,
            static_public_policy_sha256=root["publication_registration"]["policy_sha256"], code_pins_sha256=c.digest(x.p["producer"]["code_pins"]))
        for which in ("writer", "reader"):
            x.native[which].update({k:v for k,v in summary.items() if k != "schema_version"})
        original = {k:deepcopy(ts[k]) for k in t.HANDOFF_KEYS}
        original["schema_version"] = t.VERSION + "-appended"
        x.native["writer"]["receipt_sha256"] = s.sha(s.canonical(original))
        x.publish_locator()
    reseal()
    x.api.data[c.run_url("100")].update(status="in_progress", conclusion=None, updated_at="2026-10-25T12:36:10Z")
    x.api.data[c.jobs_url("100")]["jobs"][0].update(status="in_progress", conclusion=None, completed_at=None,started_at="2026-10-25T12:36:05Z")
    service = Service(x)
    binding = x.package["binding"]
    service.add_exact(binding["canary_name"], s.probe.fixture(binding["origin_run_id"]), binding["canary_asset_id"])
    service.add_exact(x.template_seal["descriptor"]["entry"]["payload_name"], x.prepared.body, 701)
    service.add_exact("manifest-" + x.template_seal["descriptor"]["manifest_sha256"] + ".json", s.canonical(x.template_seal["descriptor"]["entry"]), 702)
    receipt_path = c.receipt_path(x.p)
    compressed = base64.b64decode(x.api.data[c.contents_url(receipt_path, "lab-state")]["content"])
    ready_doc = c.decode(gzip.decompress(compressed))
    stamp = c.utc(ready_doc["created_at"]).strftime("%Y%m%dT%H%M%S.%fZ")
    anchor_name = stamp + "--" + ready_doc["feed_sha256"] + ".json"
    week_path = w.PUBLIC_ROOT + "/2026-W08"
    x.api.data[c.contents_url(w.PUBLIC_ROOT, STATE)] = directory(w.PUBLIC_ROOT, [("2026-W08", "dir", 0), ("receipts", "dir", 0)])
    x.api.data[c.contents_url(week_path, STATE)] = directory(week_path, [(anchor_name, "file", ready_doc["feed_bytes"])])
    x.api.data[c.contents_url(receipt_path, STATE)] = old.content(receipt_path, compressed)
    event_path = tmp_path / "actual-parent-event.json"
    event_path.write_bytes(c.canonical(dict(repository=dict(full_name=c.REPO), schedule=c.PARENT_CADENCE["cron"])))
    env = dict(x.env, GITHUB_RUN_ID="100", GITHUB_EVENT_NAME="schedule", GITHUB_SHA=old.A, GITHUB_WORKFLOW_SHA=old.A,
        GITHUB_WORKFLOW_REF=c.REPO + "/" + c.WORKFLOW + "@refs/heads/main", GITHUB_JOB="lab", GITHUB_TOKEN="ghs_FICTIONAL",
        GITHUB_ACTOR=c.OWNER["login"], GITHUB_ACTOR_ID=str(c.OWNER["id"]), GITHUB_EVENT_PATH=str(event_path), RUNNER_TEMP=str(tmp_path))
    observed = SimpleNamespace(at=c.utc("2026-10-25T12:36:10Z"))
    clock = lambda: observed.at
    monkeypatch.setattr(w, "native_envelope", lambda:None)  # composition seam only; subprocess below uses real OS guard
    monkeypatch.setattr(t, "now", clock)
    verify_parent = c.verify_parent
    def verified(*args, **kwargs):
        proof = verify_parent(*args, **kwargs)
        service.parent_verified = True
        return proof
    monkeypatch.setattr(c, "verify_parent", verified)

    def execute(**kwargs):
        return w.run(env, source_root=x.parent_source, transport=service, clock=clock, read_head=x.read_head, **kwargs)

    issued = []
    def newer(*, source=old.B, week="2026-W08", policy_sha=None, recipe_sha=None, sidecar=True):
        index = len(issued)
        run_id = str(600 + index)
        doc = deepcopy(ready_doc)
        doc.update(source_sha=source, run_id=run_id, policy_sha256=policy_sha or root["publication_registration"]["policy_sha256"],
            policy_registered_at_utc=policy["registered_at_utc"], workflow_sha256=x.p["producer"]["workflow_sha256"],
            recipe_registration_sha256=recipe_sha or policy["producer_policy_sha256"], root_go_sha256=old.h([run_id,"Ops Root"]),
            created_at=(c.utc("2026-10-25T12:26:00Z") + timedelta(minutes=index)).isoformat(),
            verified_at="2026-10-25T12:25:00Z", feed_sha256=old.h([run_id,"new Ops feed"]))
        doc["jobs"] = {role:dict(job_id=x.p["producer"]["jobs"][role], api_job_id=601 + 10*index + i) for i,role in enumerate(c.ROLES)}
        packed = gzip.compress(c.canonical(doc), mtime=0)
        x.api.data[c.run_url(run_id)] = old.run(run_id, source, x.p["producer"]["branch"], c.OWNER,
            updated=(c.utc(doc["created_at"]) + timedelta(minutes=5)).isoformat())
        x.api.data[c.jobs_url(run_id)] = dict(total_count=3, jobs=[old.job(run_id, source, doc["jobs"][role]["job_id"],
            doc["jobs"][role]["api_job_id"], "2026-10-25T12:" + start + ":00Z", "2026-10-25T" + end + ":00Z")
            for role,start,end in (("produce","10","12:15"),("restore","16","12:20"),("consume","21","12:30"))])
        target = w.PUBLIC_ROOT + "/" + week
        if week != "2026-W08":
            x.api.data[c.contents_url(w.PUBLIC_ROOT, STATE)].append(directory(w.PUBLIC_ROOT, [(week,"dir",0)])[0])
            x.api.data[c.contents_url(target, STATE)] = []
        stamp = c.utc(doc["created_at"]).strftime("%Y%m%dT%H%M%S.%fZ")
        name = stamp + "--" + doc["feed_sha256"] + ".json"
        x.api.data[c.contents_url(target, STATE)].extend(directory(target, [(name,"file",doc["feed_bytes"])]))
        path = w.PUBLIC_ROOT + "/receipts/" + doc["feed_sha256"] + ".json.gz"
        x.api.data[c.contents_url(path, STATE)] = old.content(path, packed)
        if sidecar:
            metadata = ops_sidecar(doc, x.package, x.p["producer"]["code_pins"], x.p["producer"]["branch"])
            sidecar_body = gzip.compress(s.canonical(metadata), mtime=0)
            sidecar_path = "state/controller-v1/grade-checkpoints/" + doc["feed_sha256"] + ".json.gz"
            x.api.data[c.contents_url(sidecar_path, STATE)] = old.content(sidecar_path, sidecar_body)
        issued.append(doc)
        return doc, packed
    ops, ops_packed = newer()
    def initial_only():
        x.api.data[c.contents_url(week_path, STATE)] = directory(week_path, [(anchor_name, "file", ready_doc["feed_bytes"])])
    sidecar_path = "state/controller-v1/grade-checkpoints/" + ops["feed_sha256"] + ".json.gz"
    sidecar_body = base64.b64decode(x.api.data[c.contents_url(sidecar_path, STATE)]["content"])
    return SimpleNamespace(x=x, env=env, root=root, policy=policy, service=service, clock=clock, observed=observed,
        execute=execute, newer=newer, ready=ready_doc, compressed=compressed, event=event_path, reseal=reseal, base=tmp_path,
        ops=ops, ops_packed=ops_packed, sidecar_path=sidecar_path, sidecar_body=sidecar_body, initial_only=initial_only)


def test_real_parent_bootstrap_private_get_claim_and_exact_once_exit(case):
    result = case.execute()
    assert result["state"] == "ENQUEUE_ONCE_AND_EXIT" and result["dispatches"] == 1 and result["dispatch_http_status"] == 204
    assert result["child_completion_claimed"] is result["activation_authorized"] is result["public_root"] is False
    requests = case.service.calls
    assert result["HTTP_calls"] == len(requests) == sum(result["HTTP_by_lane"].values()) <= 140
    assert requests[-1].full_url == w.DISPATCH_URL and requests[-1].get_method() == "POST"
    assert len([r for r in requests if r.full_url == w.DISPATCH_URL]) == 1
    assert len([r for r in requests if r.get_method() == "POST"]) == 4  # blob, tree, commit, dispatch
    assert len([r for r in requests if r.get_method() == "PATCH"]) == 1
    root = c.decode(case.service.dispatch_body["inputs"]["inference_builder_go_json"])
    assert root["approved"] is True and root["operation"] == "RECURRING_CAPTURE"
    assert c.utc(root["expires_at_utc"]) - c.utc(root["issued_at_utc"]) == timedelta(hours=1)
    assert len(c.canonical(root)) <= 60 << 10 and len(root["code_pins"]) <= 128
    for name in set(root) - w.DYNAMIC_FIELDS:
        assert root[name] == case.root[name]
    ctx = root["effective_epoch"]
    assert set(ctx) == {"schema_version", "controller_context", "previous_capture", "previous_checkpoint"}
    assert ctx["schema_version"] == w.CONTEXT_SCHEMA and ctx["previous_checkpoint"] == dict(sha256=c.sha(case.sidecar_body))
    assert ctx["previous_capture"] == dict(feed_sha256=case.ops["feed_sha256"], receipt_sha256=c.sha(case.ops_packed))
    assert case.ops["source_sha"] == case.x.p["producer"]["source_sha"]
    assert case.x.api.data[c.run_url(case.ops["run_id"])]["actor"] == c.OWNER
    assert ctx["controller_context"]["scheduled_parent"]["actor"] == c.OWNER
    claim = c.decode(case.service.claim_body)
    assert set(claim) == c.CLAIM_KEYS and claim["root_go_sha256"] == c.sha(c.canonical(root)) == result["root_go_sha256"]
    assert claim["claim_id"] == ctx["controller_context"]["claim_id"] == result["claim_id"]
    assert claim["parent_source_sha"] == old.A and claim["producer_source_sha"] == old.B and claim["parent_api_job_id"] == 11
    assert b'"source_config"' not in case.service.claim_body and b'"root_template"' not in case.service.claim_body
    assert not any("--" + case.ready["feed_sha256"] + ".json?" in r.full_url for r in requests)
    for intent in (case.base / (w.VERSION + "-100-1") / "journal").glob("*.intent.json"):
        assert b"inference_builder_go_json" not in intent.read_bytes() and b"ghs_" not in intent.read_bytes()
    assert b'"root_template"' not in c.canonical(result)


@pytest.mark.parametrize("mutation", ["env_actor", "api_actor", "api_source", "api_job", "source_bytes", "producer_head", "expired_artifact", "seal_digest"])
def test_wrong_live_actor_source_job_or_seal_blocks_before_private_root_and_posts(case, mutation):
    x = case.x
    if mutation == "env_actor": case.env["GITHUB_ACTOR"] = c.BOT["login"]
    if mutation == "api_actor": x.api.data[c.run_url("100")]["actor"] = deepcopy(c.BOT)
    if mutation == "api_source": x.api.data[c.run_url("100")]["head_sha"] = old.B
    if mutation == "api_job": x.api.data[c.jobs_url("100")]["jobs"][0]["name"] = "wrong-current-job"
    if mutation == "source_bytes": (x.parent_source / w.FILES[0]).write_bytes(b"FICTIONAL changed code")
    if mutation == "producer_head": x.api.data[c.head_url(x.p)]["object"]["sha"] = old.C
    if mutation == "expired_artifact": x.api.data[x.artifact_url]["expired"] = True
    if mutation == "seal_digest": x.api.data[x.artifact_url]["digest"] = "sha256:" + "0" * 64
    with pytest.raises((w.ParentError, b.BootstrapError, c.ControllerError, t.TemplateError, s.StoreError)):
        case.execute()
    assert all(r.get_method() == "GET" for r in case.service.calls)
    assert not any("/releases/" in r.full_url for r in case.service.calls)


@pytest.mark.parametrize("mutation", ["compressed_receipt", "filename_hash", "filename_clock", "job_failure", "job_source", "partial_jobs", "run_changed", "directory_escape"])
def test_actual_dated_metadata_receipt_and_stable_successful_jobs_are_required(case, mutation):
    x = case.x
    path = w.PUBLIC_ROOT + "/receipts/" + case.ops["feed_sha256"] + ".json.gz"
    if mutation == "compressed_receipt": x.api.data[c.contents_url(path, STATE)] = old.content(path, gzip.compress(b"{}", mtime=0))
    if mutation == "filename_hash": x.api.data[c.contents_url(w.PUBLIC_ROOT + "/2026-W08", STATE)][1]["name"] = "20261025T130000.000000Z--" + "0" * 64 + ".json"
    if mutation == "filename_clock":
        row = x.api.data[c.contents_url(w.PUBLIC_ROOT + "/2026-W08", STATE)][1]
        row["name"] = "20261025T130100.000000Z--" + case.ops["feed_sha256"] + ".json"
        row["path"] = w.PUBLIC_ROOT + "/2026-W08/" + row["name"]
    if mutation == "job_failure": x.api.data[c.jobs_url(case.ops["run_id"])]["jobs"][1]["conclusion"] = "failure"
    if mutation == "job_source": x.api.data[c.jobs_url(case.ops["run_id"])]["jobs"][1]["head_sha"] = old.A
    if mutation == "partial_jobs": x.api.data[c.jobs_url(case.ops["run_id"])]["total_count"] = 4
    if mutation == "run_changed":
        def changed(value, n):
            if n >= 2: value["updated_at"] = old.PSTART
            return value
        case.service.hooks[c.run_url(case.ops["run_id"])] = changed
    if mutation == "directory_escape": x.api.data[c.contents_url(w.PUBLIC_ROOT, STATE)][0]["path"] = "state/private/FORBIDDEN"
    with pytest.raises((w.ParentError, b.BootstrapError, c.ControllerError, t.TemplateError, s.StoreError)):
        case.execute()
    assert all(r.get_method() == "GET" for r in case.service.calls)


@pytest.mark.parametrize("kind", ["source", "policy", "recipe"])
def test_unregistered_newer_feed_does_not_override_qualified_ops_capture(case, kind):
    kwargs = {"source": old.C} if kind == "source" else {"policy_sha": "0" * 64} if kind == "policy" else {"recipe_sha": "0" * 64}
    case.newer(**kwargs)
    result = case.execute()
    assert result["previous_capture"]["feed_sha256"] == case.ops["feed_sha256"]
    assert result["previous_checkpoint"] == dict(sha256=c.sha(case.sidecar_body))


@pytest.mark.parametrize("manual", [False, True])
def test_initial_count7_foundation_alone_never_claims_or_enqueues_bot(case, manual):
    case.initial_only()
    if manual: manual_outside_window(case)
    with pytest.raises(w.ParentError, match="SAME_SOURCE_OPS_CAPTURE_AND_CHECKPOINT_REQUIRED"):
        case.execute()
    assert case.service.parent_verified  # actual verifier accepted the foundation
    assert all(r.get_method() == "GET" for r in case.service.calls)
    assert case.service.claim_body is case.service.dispatch_body is None and case.service.committed is False
    assert not list((case.base / (w.VERSION + "-100-1") / "journal").glob("*.intent.json"))


@pytest.mark.parametrize("kind", ["source", "policy", "recipe"])
def test_mismatched_ops_feed_cannot_fall_back_to_count7_for_bot(case, kind):
    case.initial_only()
    kwargs = {"source": old.C} if kind == "source" else {"policy_sha": "0" * 64} if kind == "policy" else {"recipe_sha": "0" * 64}
    case.newer(**kwargs)
    with pytest.raises(w.ParentError, match="SAME_SOURCE_OPS_CAPTURE_AND_CHECKPOINT_REQUIRED"):
        case.execute()
    assert all(r.get_method() == "GET" for r in case.service.calls)
    assert case.service.dispatch_body is case.service.claim_body is None


@pytest.mark.parametrize("damage", ["missing", "known_by", "reader_source", "descriptor", "code_pins", "unknown_body"])
def test_ops_feed_requires_qualified_sidecar_before_claim_or_dispatch(case, damage):
    url = c.contents_url(case.sidecar_path, STATE)
    if damage == "missing":
        case.service.hooks[url] = lambda _value, _n:dict(type="file", path=case.sidecar_path, encoding="base64", content="", size=0, sha="0"*40)
    else:
        value = c.decode(gzip.decompress(case.sidecar_body))
        if damage == "known_by": value["grade_read_proof"]["known_by_at"] = "2026-10-25T13:20:00Z"
        if damage == "reader_source": value["grade_read_proof"]["reader"]["source_sha"] = old.C
        if damage == "descriptor": value["evidence_descriptor"]["manifest_sha256"] = "0" * 64
        if damage == "code_pins": value["grade_code_pins"]["nfl_lab/audit_weekly_grade_v1.py"] = "0" * 64
        if damage == "unknown_body": value["outcomes"] = []
        case.x.api.data[url] = old.content(case.sidecar_path, gzip.compress(c.canonical(value), mtime=0))
    with pytest.raises((w.ParentError, c.ControllerError, history.HistoryError)):
        case.execute()
    assert all(r.get_method() == "GET" for r in case.service.calls)
    assert case.service.claim_body is case.service.dispatch_body is None


def test_new_week_matching_source_requires_explicit_rollover_before_any_claim(case):
    case.newer(week="2026-W09")
    with pytest.raises(w.ParentError, match="NEW_WEEK_SELECTION_AND_ROLLOVER_NOT_WIRED"):
        case.execute()
    assert all(r.get_method() == "GET" for r in case.service.calls)


def test_latest_current_source_checkpoint_cannot_be_replaced_by_json_flags(case, monkeypatch):
    from nfl_lab import audit_weekly_grade_history_v1 as history
    receipt, _ = case.newer()
    path = "state/controller-v1/grade-checkpoints/" + receipt["feed_sha256"] + ".json.gz"
    value = {key:None for key in history.SIDECAR_KEYS}
    value.update(repository=c.REPO, **{key:receipt[key] for key in ("feed_sha256", "source_sha", "run_id", "root_go_sha256", "workflow_sha256", "epoch_sha256")})
    packed = gzip.compress(c.canonical(value), mtime=0)
    case.x.api.data[c.contents_url(path, STATE)] = old.content(path, packed)
    monkeypatch.setattr(history, "validate_parent_sidecar", None, raising=False)
    with pytest.raises(w.ParentError, match="PARENT_HISTORY_METADATA_VALIDATOR_UNAVAILABLE"):
        case.execute()
    assert all(r.get_method() == "GET" for r in case.service.calls)
    monkeypatch.setattr(history, "validate_parent_sidecar", lambda *_args, **_kwargs:True)
    with pytest.raises(w.ParentError, match="EXACT_VALIDATED_PARENT_HISTORY_SIDECAR_BYTES"):
        w._checkpoint_metadata(packed, receipt=receipt, qualified_runtime=case.x.package,
            code_pins=case.x.p["producer"]["code_pins"], jobs={}, at=case.clock())


@pytest.mark.parametrize("case_name", ["duplicate", "deleted_history", "stale_before", "stale_after", "patch_conflict", "readback", "diff"])
def test_create_only_claim_expected_head_and_readback_fail_closed(case, case_name):
    service = case.service
    if case_name == "duplicate": service.duplicate = True
    if case_name == "deleted_history": service.old_history = True
    if case_name == "stale_before": service.stale_at = 2
    if case_name == "stale_after": service.stale_at = 3
    if case_name == "patch_conflict": service.patch_conflict = True
    if case_name == "readback": service.bad_readback = True
    if case_name == "diff": service.extra_diff = True
    with pytest.raises(w.ParentError): case.execute()
    assert service.dispatch_body is None
    if case_name in {"duplicate", "deleted_history", "stale_before"}:
        assert all(r.get_method() == "GET" for r in service.calls)
    for url in (c.API + "/git/blobs", c.API + "/git/trees", c.API + "/git/commits", w.STATE_UPDATE_URL):
        assert sum(r.full_url == url and r.get_method() != "GET" for r in service.calls) <= 1


@pytest.mark.parametrize("endpoint", ["/git/blobs", "/git/trees", "/git/commits"])
def test_ambiguous_git_post_is_reserved_and_never_retried(case, endpoint):
    case.service.lost_post = c.API + endpoint
    with pytest.raises(w.ParentError, match="PARENT_HTTP_ATTEMPT_FAILED_NO_RETRY"):
        case.execute()
    assert sum(r.full_url == case.service.lost_post for r in case.service.calls) == 1
    assert case.service.dispatch_body is None
    count = len(case.service.calls)
    with pytest.raises(w.ParentError, match="FRESH_PRIVATE_PARENT_WORKSPACE_REQUIRED"):
        case.execute()
    assert all(r.get_method() == "GET" for r in case.service.calls[count:])


@pytest.mark.parametrize("status", [200, 202, 403, 422, 500])
def test_dispatch_requires_actual_204_and_leaves_claim_without_retry(case, status):
    case.service.dispatch_status = status
    with pytest.raises(w.ParentError, match="DISPATCH_POST_UNCONFIRMED_NO_RETRY"):
        case.execute()
    assert case.service.committed
    assert sum(r.full_url == w.DISPATCH_URL for r in case.service.calls) == 1
    assert case.service.calls[-1].full_url == w.DISPATCH_URL


def test_ambiguous_dispatch_is_not_retried_or_reported_as_completed(case):
    case.service.dispatch_failure = True
    with pytest.raises(w.ParentError, match="PARENT_HTTP_ATTEMPT_FAILED_NO_RETRY"):
        case.execute()
    assert case.service.committed and sum(r.full_url == w.DISPATCH_URL for r in case.service.calls) == 1


def test_same_daily_claim_id_is_independent_of_parent_run_and_root(case):
    digest = w.daily_claim_id(c.sha(case.x.reg), old.B, case.clock())
    assert digest == w.daily_claim_id(c.sha(case.x.reg), old.B, case.clock() + timedelta(minutes=1))
    assert digest != w.daily_claim_id(c.sha(case.x.reg), old.B, case.clock() + timedelta(days=1))


def manual_outside_window(case):
    """Fictional raw event/API clocks only; production keeps its real clock."""
    case.observed.at = c.utc("2026-10-25T14:42:00Z")
    case.env["GITHUB_EVENT_NAME"] = "workflow_dispatch"
    case.event.write_bytes(c.canonical(dict(repository=dict(full_name=c.REPO), inputs=dict(mode="daily"))))
    case.x.api.data[c.run_url("100")].update(event="workflow_dispatch", updated_at="2026-10-25T14:42:00Z")
    case.x.api.data[c.jobs_url("100")]["jobs"][0]["started_at"] = "2026-10-25T14:41:55Z"


def test_actual_owner_manual_daily_outside_auto_window_keeps_full_proofs(case):
    manual_outside_window(case)
    result = case.execute()
    root = c.decode(case.service.dispatch_body["inputs"]["inference_builder_go_json"])
    scheduled = root["effective_epoch"]["controller_context"]["scheduled_parent"]
    assert scheduled["event"] == "workflow_dispatch" and scheduled["actor"] == c.OWNER
    assert scheduled["source_sha"] == case.x.p["parent"]["source_sha"] == old.A
    assert root["issued_at_utc"] == "2026-10-25T14:42:00+00:00"
    assert result["state"] == "ENQUEUE_ONCE_AND_EXIT" and result["dispatch_http_status"] == 204
    assert result["child_completion_claimed"] is False
    assert c.decode(case.service.claim_body)["root_go_sha256"] == result["root_go_sha256"]


@pytest.mark.parametrize("mutation", ["mode", "actor", "source", "job", "actual_event", "actual_status"])
def test_manual_outside_auto_window_never_waives_owner_source_mode_event_or_api(case, mutation):
    manual_outside_window(case)
    if mutation == "mode": case.event.write_bytes(c.canonical(dict(repository=dict(full_name=c.REPO), inputs=dict(mode="train"))))
    if mutation == "actor": case.x.api.data[c.run_url("100")]["actor"] = deepcopy(c.BOT)
    if mutation == "source": case.env["GITHUB_WORKFLOW_SHA"] = old.B
    if mutation == "job": case.x.api.data[c.jobs_url("100")]["jobs"][0]["name"] = "not-the-parent-job"
    if mutation == "actual_event": case.x.api.data[c.run_url("100")]["event"] = "schedule"
    if mutation == "actual_status": case.x.api.data[c.run_url("100")].update(status="completed", conclusion="success")
    with pytest.raises(c.ControllerError): case.execute()
    assert all(r.get_method() == "GET" for r in case.service.calls)
    assert not any("/releases/" in r.full_url for r in case.service.calls)


@pytest.mark.parametrize("late_start", [False, True])
def test_auto_schedule_still_rejects_current_clock_or_job_start_outside_registered_window(case, late_start):
    case.observed.at = c.utc("2026-10-25T14:42:00Z")
    if late_start:
        case.x.api.data[c.jobs_url("100")]["jobs"][0]["started_at"] = "2026-10-25T14:41:55Z"
    with pytest.raises(c.ControllerError, match="MISSED_DAILY_WINDOW_NO_BACKFILL"):
        case.execute()
    assert all(r.get_method() == "GET" for r in case.service.calls)
    assert not any("/releases/" in r.full_url for r in case.service.calls)


def test_current_parent_api_job_id_is_derived_from_actual_api_not_an_old_id(case):
    case.x.api.data[c.jobs_url("100")]["jobs"][0]["id"] = 999
    case.execute()
    claim = c.decode(case.service.claim_body)
    root = c.decode(case.service.dispatch_body["inputs"]["inference_builder_go_json"])
    assert claim["parent_api_job_id"] == root["effective_epoch"]["controller_context"]["scheduled_parent"]["api_job_id"] == 999


def test_a_different_parent_run_same_day_cannot_enqueue_the_same_daily_key(case):
    first = case.execute()
    for url, value in list(case.x.api.data.items()):
        if url.endswith("?ref=" + STATE):
            case.x.api.data[url[:-40] + COMMIT] = deepcopy(value)
    case.env["GITHUB_RUN_ID"] = "101"
    case.x.api.data[c.run_url("101")] = old.run("101", old.A, "main", c.OWNER, event="schedule", status="in_progress", updated="2026-10-25T12:36:10Z")
    case.x.api.data[c.jobs_url("101")] = dict(total_count=1, jobs=[old.job("101", old.A, "lab", 12, "2026-10-25T12:36:05Z")])
    boundary = len(case.service.calls)
    with pytest.raises(w.ParentError, match="DAILY_DISPATCH_CLAIM_ALREADY_EXISTS_OR_AMBIGUOUS"):
        case.execute()
    assert all(r.get_method() == "GET" for r in case.service.calls[boundary:])
    assert sum(r.full_url == w.DISPATCH_URL for r in case.service.calls) == 1
    assert c.decode(case.service.claim_body)["claim_id"] == first["claim_id"]


@pytest.mark.parametrize("asset_id", [701, 702])
def test_private_template_and_native_descriptor_must_match_original_physical_bytes(case, asset_id):
    asset = next(a for a in case.service.assets if a["id"] == asset_id)
    asset["body"] += b"CORRUPT_FICTIONAL_BYTES"
    with pytest.raises(s.StoreError): case.execute()
    assert all(r.get_method() == "GET" for r in case.service.calls)


def test_source_is_rechecked_between_private_transfers_before_root_payload(case):
    q = case.x.package["qualification"]
    url = c.run_url(q["run_id"])
    case.x.api.data[url] = old.run(q["run_id"], q["source_sha"], "fictional", c.OWNER)
    def change_code(value, _n):
        (case.x.parent_source / w.FILES[0]).write_bytes(b"FICTIONAL changed during private metadata GET")
        return value
    case.service.hooks[url] = change_code
    with pytest.raises(c.ControllerError, match="CURRENT_CODE_INVENTORY_MISMATCH"):
        case.execute()
    assert not any(r.full_url.endswith("/releases/assets/701") for r in case.service.calls)
    assert all(r.get_method() == "GET" for r in case.service.calls)


def test_root_over_60_kib_fails_before_any_public_mutation(case):
    case.root["source_config"]["fixture_padding"] = "x" * (60 << 10)
    case.reseal()
    for asset in case.service.assets:
        if asset["id"] == 701:
            body = case.x.prepared.body
            name = case.x.template_seal["descriptor"]["entry"]["payload_name"]
        elif asset["id"] == 702:
            body = s.canonical(case.x.template_seal["descriptor"]["entry"])
            name = "manifest-" + case.x.template_seal["descriptor"]["manifest_sha256"] + ".json"
        else: continue
        asset.update(body=body, name=name, size=len(body), digest="sha256:" + s.sha(body))
    with pytest.raises(w.ParentError, match="BOUNDED_DUAL_CANONICAL_PRIVATE_ROOT"):
        case.execute()
    assert all(r.get_method() == "GET" for r in case.service.calls)


def test_wrapper_files_must_be_literal_parent_source_pins(case):
    for role in ("parent", "producer"):
        case.x.p[role]["code_pins"].pop(w.FILES[0])
    case.root["code_pins"] = deepcopy(case.x.p["producer"]["code_pins"])
    case.reseal()
    with pytest.raises(b.BootstrapError, match="COMPLETE_PARENT_EXECUTABLE_SOURCE_PINS"):
        case.execute()
    assert not any("/releases/" in r.full_url for r in case.service.calls)
    assert all(r.get_method() == "GET" for r in case.service.calls)


@pytest.mark.parametrize("name", ["nfl_lab/cadence.py", "tests/test_cadence.py", "tests/test_audit_weekly_parent_workflow_v1.py"])
def test_explicit_parent_cadence_and_workflow_checks_must_be_pinned_before_private_io(case,name):
    for role in ("parent","producer"):case.x.p[role]["code_pins"].pop(name)
    case.root["code_pins"]=deepcopy(case.x.p["producer"]["code_pins"])
    case.reseal()
    code = "BOUNDED_ROLE_LOCAL_SOURCE_INVENTORY" if name == "nfl_lab/cadence.py" else "COMPLETE_PARENT_EXECUTABLE_SOURCE_PINS"
    with pytest.raises(b.BootstrapError,match=code):case.execute()
    assert not any("/releases/" in r.full_url for r in case.service.calls)
    assert all(r.get_method()=="GET" for r in case.service.calls)


def test_old_0836_seal_is_never_reinterpreted_as_new_0736_parent_authority(case):
    case.x.p["cadence"]=deepcopy(c.CADENCE)
    case.x.workflow=case.x.workflow.replace(c.PARENT_CADENCE["cron"].encode(),c.CADENCE["cron"].encode())
    for role,source,sha in (("parent",case.x.parent_source,old.A),("producer",case.x.child_source,old.B)):
        (source/c.WORKFLOW).write_bytes(case.x.workflow)
        case.x.p[role]["workflow_sha256"]=case.x.p[role]["code_pins"][c.WORKFLOW]=c.sha(case.x.workflow)
        case.x.api.data[c.contents_url(c.WORKFLOW,sha)]=old.content(c.WORKFLOW,case.x.workflow)
    case.x.native["workflow_sha256"]=c.sha(case.x.workflow)
    case.root["code_pins"]=deepcopy(case.x.p["producer"]["code_pins"])
    case.reseal()
    manual_outside_window(case)
    with pytest.raises(w.ParentError,match="EXPLICIT_PARENT_0736_REGISTRATION_REQUIRED"):case.execute()
    assert not any("/releases/" in r.full_url for r in case.service.calls)
    assert all(r.get_method()=="GET" for r in case.service.calls)


def test_private_redirect_is_counted_and_never_receives_parent_token(case):
    calls = case.service.calls
    def transport(request, timeout):
        if request.full_url == s.API + "/releases/assets/701" and request.get_header("Accept") == "application/octet-stream":
            calls.append(request)
            return Response(b"", 302, {"location":"https://objects.githubusercontent.com/fictional?PRIVATE_NEVER_LOG"})
        if urlsplit(request.full_url).hostname == "objects.githubusercontent.com":
            calls.append(request)
            assert request.get_header("Authorization") is request.get_header("Cookie") is None
            return Response(case.x.prepared.body)
        return case.service(request, timeout)
    result = w.run(case.env, source_root=case.x.parent_source, transport=transport, clock=case.clock, read_head=case.x.read_head)
    assert result["state"] == "ENQUEUE_ONCE_AND_EXIT" and result["HTTP_calls"] == len(calls)
    assert "PRIVATE_NEVER_LOG" not in json.dumps(result)


def test_default_and_contract_do_not_read_credentials_files_or_network(monkeypatch, capsys):
    def forbidden(*_args, **_kwargs): pytest.fail("PREPARATION_IO_FORBIDDEN")
    monkeypatch.setattr(s, "read_local", forbidden)
    monkeypatch.setattr(b, "authorize_parent", forbidden)
    assert cli.main([], environ={}) == 2
    assert json.loads(capsys.readouterr().out)["POSTs"] == 0
    assert cli.main(["--contract"], environ={}) == 0
    contract = json.loads(capsys.readouterr().out)
    assert contract["registry_version"] == 2 and contract["limits"]["HTTP_calls"] == 140
    assert contract["child_completion_claimed"] is False


def test_concrete_workflow_contract_versions_parent_clock_and_blocks_premature_activation():
    plan = w.workflow_contract()
    assert plan["job_id"] == "lab" and plan["workflow"] == c.WORKFLOW
    assert plan["cadence"] == c.PARENT_CADENCE and plan["concurrency"] == c.CONCURRENCY
    assert plan["required_job_permissions"] == dict(contents="write", actions="write")
    assert plan["step"]["env"] == dict(GITHUB_TOKEN="${{ github.token }}")
    assert plan["step"]["run"].endswith("tools/audit_weekly_parent_v1.py --execute > controller-parent-result.json")
    assert "steps.parent_cadence.outputs.due == 'true'" in plan["step"]["if"]
    assert "steps.cadence.outputs.mode" not in plan["step"]["if"]  # Sunday old train label never enables a fit.
    assert plan["requires_accepted_versioned_readiness_guard"] is plan["legacy_routes_remain_guarded"] is True
    assert plan["clock_dependency"]["research_chicago"] == "07:36"
    assert plan["clock_dependency"]["website_chicago"] == "08:06"
    assert plan["clock_dependency"]["scheduled_tick_before_website"] is True
    assert plan["clock_dependency"]["legacy_research_chicago"] == "08:36"
    assert plan["clock_dependency"]["additional_scheduler"] is False
    assert plan["root_inputs_or_job_environment"] is False
    assert w.contract()["manual_daily_uses_same_chicago_window"] is False
    assert w.contract()["manual_daily_policy"] == "EXISTING_OWNER_SOURCE_DAILY_EVENT_AND_LIVE_API_PROOF"
    assert w.contract()["sealed_initial_readiness_permits_parent_enqueue"] is False
    assert w.contract()["parent_previous_checkpoint_required"] is True
    assert "VERIFY_SAME_SOURCE_OPS_FEED_AND_QUALIFIED_GRADE_SIDECAR" in plan["bootstrap_order"]


def test_absent_seal_and_nonautomatic_credentials_never_reach_post(case):
    for token in (None, "ghp_FICTIONAL", "github_pat_FICTIONAL"):
        case.env["GITHUB_TOKEN"] = token
        with pytest.raises(w.ParentError, match="FRESH_AUTOMATIC_GITHUB_TOKEN_REQUIRED"): case.execute()
    assert not case.service.calls
    case.env["GITHUB_TOKEN"] = "ghs_FICTIONAL"
    case.x.api.data[b.history_url(registry_version=2)] = []
    with pytest.raises(b.BootstrapError): case.execute()
    assert all(r.get_method() == "GET" for r in case.service.calls)


def test_local_parent_suite_needs_no_producer_history_or_numerical_files(case):
    x = case.x
    assert w.HISTORY_TEST == w.FILES[2] in w.REQUIRED_PINS
    assert w.HISTORY_TEST in b.PARENT_EXECUTABLE_PINS
    assert history.FILES[0] in b.SHARED_EXECUTABLE_PINS
    assert history.FILES[1] not in b.PARENT_EXECUTABLE_PINS
    producer_pins = deepcopy(x.p["producer"]["code_pins"])
    assert history.FILES[1] in producer_pins
    parent_pins = {name: x.p["parent"]["code_pins"][name] for name in b.PARENT_EXECUTABLE_PINS}
    for name in set(x.p["parent"]["code_pins"]) - set(parent_pins):
        (x.parent_source / name).unlink()  # Fictional temporary source files only.
    x.p["parent"]["code_pins"] = parent_pins
    case.reseal()
    result = case.execute()
    dispatched = c.decode(case.service.dispatch_body["inputs"]["inference_builder_go_json"])
    assert result["state"] == "ENQUEUE_ONCE_AND_EXIT" and result["dispatches"] == 1
    assert dispatched["code_pins"] == producer_pins
    assert not (x.parent_source / history.FILES[1]).exists()
    assert not (x.parent_source / "nfl_lab/audit_weekly_grade_v1.py").exists()
    assert result["child_completion_claimed"] is result["activation_authorized"] is False


def test_metadata_validator_still_requires_full_producer_history_protocol_test(case):
    pins = deepcopy(case.x.p["producer"]["code_pins"])
    pins.pop(history.FILES[1])
    listing = case.x.api.data[c.jobs_url(case.ops["run_id"])]["jobs"]
    jobs = {role: next(j for j in listing if j["name"] == case.ops["jobs"][role]["job_id"]) for role in c.ROLES}
    with pytest.raises(w.ParentError, match="^SOURCE_PINNED_PARENT_HISTORY_HELPER_REQUIRED$"):
        w._checkpoint_metadata(case.sidecar_body, receipt=case.ops, qualified_runtime=case.x.package,
            code_pins=pins, jobs=jobs, at=case.clock())


def test_current_source_or_actor_race_before_dispatch_keeps_claim_but_never_enqueues(case):
    def changed(value, _n):
        if case.service.committed: value["actor"] = deepcopy(c.BOT)
        return value
    case.service.hooks[c.run_url("100")] = changed
    with pytest.raises(c.ControllerError): case.execute()
    assert case.service.committed and case.service.dispatch_body is None


def test_all_exchanges_share_finite_budget_and_no_post_occurs_after_budget_failure(case, monkeypatch):
    monkeypatch.setitem(w.LIMITS, "authority_calls", 24)
    with pytest.raises(w.ParentError, match="PARENT_SHARED_HTTP_ATTEMPT_CAP"): case.execute()
    assert all(r.get_method() == "GET" for r in case.service.calls)


def test_native_envelope_and_actual_cli_fail_closed_without_token():
    script = """
import json, socket, sys
sys.path.insert(0, sys.argv[1])
from nfl_lab import audit_weekly_parent_v1 as parent
try:
    parent.native_envelope()
except parent.ParentError:
    pass
else:
    raise AssertionError('UNBOUNDED_PARENT_ACCEPTED')
from tools.private_draft_store_v2 import limits
limits()
parent.native_envelope()
socket.socket.connect = lambda *_: (_ for _ in ()).throw(AssertionError('REAL_NETWORK_FORBIDDEN'))
from tools import audit_weekly_parent_v1 as cli
assert cli.main(['--execute'], environ={}) == 1
"""
    result = subprocess.run([sys.executable, "-I", "-B", "-c", script, str(ROOT)], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    status = json.loads(result.stdout)
    assert status["state"] == "PARENT_BLOCKED" and status["child_completion_claimed"] is False


@pytest.mark.parametrize('kind,week',[('GRADE_ONLY',7),('FUTURE_CAPABLE',8)])
def test_actual_parent_root_can_bind_explicit_v3_plan_without_changing_static_template(case,monkeypatch,kind,week):
    actual=w._build_root
    plan=dict(kind=kind,season=2026,week=week)
    def planned(*args,**kwargs):return actual(*args,**kwargs,plan=plan)
    monkeypatch.setattr(w,'_build_root',planned)
    result=case.execute()
    assert result['state']=='ENQUEUE_ONCE_AND_EXIT'
    root=c.decode(case.service.dispatch_body['inputs']['inference_builder_go_json'])
    assert root['effective_epoch']['schema_version']=='audit-weekly-recurring-v3-context'
    assert root['effective_epoch']['plan']==plan
    assert len(root['code_pins'])<=128 and len(c.canonical(root))<=60 << 10
    assert all(root[k]==case.root[k] for k in set(root)-w.DYNAMIC_FIELDS)


@pytest.fixture
def history_case(case):
    """Self-contained Main metadata; native bytes are explicitly fictional.

    The real Parent/GET/CAS pipeline is used. No Producer grader, numerical
    worker, snapshot body, provider, or forecast rows are imported or decoded.
    """
    x=case.x;x.template_schema=t.STATIC_V3 if case.root['schema_version']==t.ROOT_V3 else t.VERSION+"-static-v2";case.reseal()
    case.service.assets[:]=[a for a in case.service.assets if a["id"] not in {701,702}]
    case.service.add_exact(x.template_seal["descriptor"]["entry"]["payload_name"],x.prepared.body,701)
    case.service.add_exact("manifest-"+x.template_seal["descriptor"]["manifest_sha256"]+".json",s.canonical(x.template_seal["descriptor"]["entry"]),702)
    current=dict(season=2026,week=8,schedule=[dict(season=2026,week=8,game_type="REG",game_id="fictional-current",kickoff_utc="2026-10-25T12:00:00Z")],
        game_cutoffs={"fictional-current":"2026-10-25T10:30:00Z"},canonical_choice_sha256=old.h("canonical choice, immutable"))
    later=dict(season=2026,week=9,schedule=[dict(season=2026,week=9,game_type="REG",game_id="fictional-next",kickoff_utc="2026-11-01T18:00:00Z")],
        game_cutoffs={"fictional-next":"2026-11-01T16:30:00Z"})
    planning=dict(schema_version=history.LOCATOR_VERSION+"-planning",epoch_sha256=case.ops["epoch_sha256"],current=current,next=later,
        resolved_weeks=[],known_by_at="2026-10-25T12:34:10Z",calendar=dict(url="https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv",
            sha256=old.h("calendar bytes, no outcome columns read"),bytes=321,retrieved_utc="2026-10-25T12:31:10Z"))
    prior=dict(feed_sha256=case.ops["feed_sha256"],receipt_sha256=s.sha(case.ops_packed))
    original_root=deepcopy(case.root)
    original_root.update(approved=True,operation="RECURRING_CAPTURE",issued_at_utc="2026-10-25T12:30:45Z",expires_at_utc="2026-10-25T13:30:45Z",
        effective_epoch=dict(schema_version=history.CONTEXT_V4,controller_context=None,previous_capture=prior,
            previous_checkpoint=dict(schema_version=history.LOCATOR_REF,path="20261025T122300.000000Z--600--"+"a"*64+".json.gz",sha256="b"*64),
            plan=dict(kind="GRADE_ONLY",season=2026,week=8,deadline_utc=None,calendar_sha256=c.digest(current["schedule"]),game_cutoffs={})))
    if getattr(case,'pending_recovery_spec',None) is not None:
        original_root['effective_epoch'].update(schema_version=history.CONTEXT_V5,
            pending_post_recovery=deepcopy(case.pending_recovery_spec))
    cohort=dict(schema_version=history.LOCATOR_VERSION+"-cohort",kind="GRADING_ONLY",repository=c.REPO,source_sha=old.B,run_id="700",
        root_go_sha256=c.digest(original_root),workflow_sha256=x.p["producer"]["workflow_sha256"],epoch_sha256=case.ops["epoch_sha256"],
        feed_sha256=case.ops["feed_sha256"],jobs={role:dict(job_id=x.p["producer"]["jobs"][role],api_job_id=701+i) for i,role in enumerate(c.ROLES)},
        root_issued_at_utc=original_root["issued_at_utc"],verified_at=planning["known_by_at"],created_at="2026-10-25T12:34:30Z",
        fits=0,public_release=False,successful_forecast=False)
    core=ops_sidecar(cohort,x.package,x.p["producer"]["code_pins"],x.p["producer"]["branch"])
    handoff=core["checkpoint_handoff"];proof=core["grade_read_proof"];append=handoff["append_proof"]
    handoff["snapshot_completed_at"]="2026-10-25T12:33:00Z"
    append.update(started_at_utc="2026-10-25T12:33:10Z",completed_at_utc="2026-10-25T12:33:20Z")
    handoff["append_proof_sha256"]=c.digest(append);proof["known_by_at"]=planning["known_by_at"]
    reader=proof["reader"]
    native=dict(schema_version="weekly-private-proof-v2.1",phase="restore",operation="restore",repository=c.REPO,run_id=cohort["run_id"],run_attempt=1,
        started_at_utc="2026-10-25T12:34:01Z",created_at_utc="2026-10-25T12:34:05Z",source_sha=old.B,binding_sha256=c.digest(x.package["binding"]),
        config_sha256=s.CONFIG_SHA256,process_identity=reader["process_identity"],HTTP_calls=10,transfer_bytes=2000,
        job=dict(execution_lane="github_actions",workflow_ref=reader["workflow_ref"],workflow_sha=old.B,job_id=reader["job_id"],permission="write",
            event_name="workflow_dispatch",api_job_id=reader["api_job_id"],run_authenticated=True),
        exact_readback=True,payload_sha256=handoff["body_sha256"],bytes=handoff["body_bytes"],separate_process=True,draft_before_after=True)
    apis=dict(run_sha256=old.h("actual fictional run response"),jobs_sha256=old.h("actual fictional jobs response"))
    body=dict(schema_version="audit-weekly-grade-checkpoint-v1-fresh-reader-native-evidence",known_by_at=proof["known_by_at"],native_restore_proof=native,
        restored_binding=dict(path="/FICTIONAL/owned/GRADING_SNAPSHOT.json.gz",bytes=handoff["body_bytes"],sha256=handoff["body_sha256"]),
        context=dict(current_root_go_sha256=cohort["root_go_sha256"],handoff_sha256=c.digest(handoff),handoff=deepcopy(handoff),reader=deepcopy(reader),
            api_evidence=apis,final_api_evidence=apis))
    proof["proof_sha256"]=c.digest(body)
    envelope=dict(schema_version=history.LOCATOR_VERSION+"-evidence-envelope",handoff_sha256=c.digest(handoff),grade_read_proof=deepcopy(proof),
        native_read_evidence=body,durable_sha256=old.h("opaque durable digest only"),grade_code_pins=core["grade_code_pins"],
        checkpoint_helper_sha256=core["checkpoint_helper_sha256"],planning=planning,root_go=original_root)
    locator=dict(schema_version=history.LOCATOR_VERSION,repository=c.REPO,anchor=prior,cohort=cohort,sidecar=core,planning=planning,
        helper_sha256={n:x.p["producer"]["code_pins"][n] for n in history.LOCATOR_HELPERS})
    x.api.data[c.run_url("700")]=old.run("700",old.B,x.p["producer"]["branch"],c.OWNER,updated="2026-10-25T12:35:10Z")
    x.api.data[c.jobs_url("700")]=dict(total_count=3,jobs=[old.job("700",old.B,cohort["jobs"][role]["job_id"],cohort["jobs"][role]["api_job_id"],a,b)
        for role,a,b in (("produce","2026-10-25T12:31:00Z","2026-10-25T12:32:00Z"),
            ("restore","2026-10-25T12:32:10Z","2026-10-25T12:33:30Z"),("consume","2026-10-25T12:34:00Z","2026-10-25T12:35:00Z"))])
    for path in set(core["grade_code_pins"])|set(core["checkpoint_helper_sha256"])|history.LOCATOR_HELPERS:
        x.api.data[c.contents_url(path,old.B)]=old.content(path,(x.child_source/path).read_bytes())
    def publish():
        packed=gzip.compress(s.canonical(envelope),mtime=0)
        descriptor=core["evidence_descriptor"];entry=descriptor["entry"]
        entry["payload"].update(sha256=s.sha(packed),bytes=len(packed));entry["payload_name"]="blob-"+s.sha(packed)+".bin"
        descriptor.update(manifest_sha256=c.digest(entry),manifest_bytes=len(s.canonical(entry)))
        case.service.assets[:]=[a for a in case.service.assets if a["id"] not in {entry["payload_asset_id"],descriptor["manifest_asset_id"]}]
        case.service.add_exact(entry["payload_name"],packed,entry["payload_asset_id"])
        case.service.add_exact("manifest-"+descriptor["manifest_sha256"]+".json",s.canonical(entry),descriptor["manifest_asset_id"])
        raw=gzip.compress(s.canonical(locator),mtime=0);name=history.locator_filename(locator)
        x.api.data[c.contents_url(history.LOCATOR_ROOT,STATE)]=directory(history.LOCATOR_ROOT,[(name,"file",len(raw))])
        x.api.data[c.contents_url(history.LOCATOR_ROOT+"/"+name,STATE)]=old.content(history.LOCATOR_ROOT+"/"+name,raw)
        return raw
    publish()
    return SimpleNamespace(case=case,locator=locator,envelope=envelope,publish=publish)


def test_v3_parent_routes_current_checkpoint_with_separate_sealed_old_capture_runtime(case,record_property):
    """Actual typed Parent, native template GET, CAS and dispatch; fake HTTP."""
    from test_audit_weekly_controller_bootstrap_v1 import fictional_runtime_metadata
    x=case.x
    census=dict(schema_version='audit-private-rotation-v1-pending-census',complete=True,
        as_of_utc=x.package['qualification']['before_proof']['started_at_utc'],owner_evidence_sha256='a'*64,reservations=[])
    x.package['quota_reservation'].update(pending_census_sha256=c.digest(census),pending_records=0)
    x.locators['qualified_runtime_package']=deepcopy(x.package)
    case.root.update(schema_version=t.ROOT_V3,qualified_runtime=deepcopy(x.package),pending_census=deepcopy(census),
        prior_capture_qualified_runtime=dict(schema_version=t.PRIOR_RUNTIME,purpose='PRIOR_CAPTURE_QUALIFIED_RUNTIME',
            anchor=dict(feed_sha256='1'*64,receipt_sha256='2'*64),
            qualified_runtime=fictional_runtime_metadata(x.package,census),pending_census=deepcopy(census),root_static_sha256=None))
    x.template_schema=t.STATIC_V3
    h=history_case.__wrapped__(case)
    result=case.execute()
    root=c.decode(case.service.dispatch_body['inputs']['inference_builder_go_json'])
    assert root['schema_version']==t.ROOT_V3
    assert root['effective_epoch']['schema_version']==history.CONTEXT_V5
    assert root['effective_epoch']['pending_post_recovery']==dict(schema_version=t.PENDING_RECOVERY,handoffs=[],pending_reservations=[])
    assert root['effective_epoch']['previous_capture']==h.locator['anchor']
    assert root['prior_capture_qualified_runtime']==case.root['prior_capture_qualified_runtime']
    assert root['qualified_runtime']==x.package
    assert result['state']=='ENQUEUE_ONCE_AND_EXIT' and result['dispatches']==1
    assert result['HTTP_calls']==len(case.service.calls)<=140
    assert result['HTTP_by_lane']['private']<=40
    assert len(c.canonical(root))<=60<<10
    assert len(c.canonical(case.service.dispatch_body))<=65535
    record_property('v3_current_history_HTTP_calls',result['HTTP_calls'])


def test_v3_parent_reads_old_checkpoint_using_separately_bound_GET_only_client(case,monkeypatch,record_property):
    from test_audit_weekly_controller_bootstrap_v1 import dual_runtime_root
    x=case.x;old_package=deepcopy(x.package)
    census=dict(schema_version='audit-private-rotation-v1-pending-census',complete=True,
        as_of_utc=old_package['qualification']['before_proof']['started_at_utc'],owner_evidence_sha256='a'*64,reservations=[])
    old_package['quota_reservation'].update(pending_census_sha256=c.digest(census),pending_records=0)
    x.package=old_package;x.locators['qualified_runtime_package']=deepcopy(old_package)
    case.root.update(qualified_runtime=deepcopy(old_package),pending_census=deepcopy(census))
    h=history_case.__wrapped__(case)
    old_assets=deepcopy(case.service.assets)
    value=dual_runtime_root(case.root,old_package,census,h.locator['anchor'],original_root=h.envelope['root_go'])
    case.root.clear();case.root.update(value)
    x.package=deepcopy(value['qualified_runtime']);current=x.package['binding'];old_binding=old_package['binding']
    x.locators['qualified_runtime_package']=deepcopy(x.package)
    x.template_seal['binding']=deepcopy(current)
    x.template_seal['descriptor']['entry']['binding_sha256']=c.digest(current)
    x.template_schema=t.STATIC_V3;case.reseal()
    case.service.tag=current['tag_name'];case.service.q=x.package['qualification'];case.service.assets=[]
    case.service.add_exact(current['canary_name'],s.probe.fixture(current['origin_run_id']),current['canary_asset_id'])
    descriptor=x.template_seal['descriptor']
    case.service.add_exact(descriptor['entry']['payload_name'],x.prepared.body,descriptor['entry']['payload_asset_id'])
    case.service.add_exact('manifest-'+descriptor['manifest_sha256']+'.json',s.canonical(descriptor['entry']),descriptor['manifest_asset_id'])
    # The old store retains its canary and reader evidence; the current store
    # contains the genuinely distinct static template, not old asset IDs.
    old_assets=[a for a in old_assets if a['id'] not in {701,702}]
    q=old_package['qualification'];rid=q['run_id']
    x.api.data[c.run_url(rid)]=old.run(rid,q['source_sha'],'fictional',c.OWNER)
    x.api.data[c.jobs_url(rid)]=dict(total_count=3,jobs=[old.job(rid,q['source_sha'],p['job']['job_id'],
        p['job']['api_job_id'],p['started_at_utc'],p['created_at_utc']) for p in (q['before_proof'],q['read_proof'],q)])
    original_call=Service.__call__
    def two_stores(service,request,timeout):
        url=request.full_url
        if service is case.service and '/releases/' in url:
            assert request.get_method()=='GET' and request.data is None
            assert service.parent_verified
            service.calls.append(request)
            for binding,assets in ((old_binding,old_assets),(current,service.assets)):
                release=s.API+'/releases/'+str(binding['release_id'])
                if url==release:return Response(dict(id=binding['release_id'],draft=True,published_at=None,
                    tag_name=binding['tag_name'],url=release,assets=[service.metadata(a) for a in assets]))
                if url==release+'/assets?per_page=100&page=1':return Response([service.metadata(a) for a in assets])
            asset_id=int(url.rsplit('/',1)[-1]);matches=[a for a in old_assets+service.assets if a['id']==asset_id]
            assert len(matches)==1
            return Response(matches[0]['body'] if request.get_header('Accept')=='application/octet-stream' else service.metadata(matches[0]))
        return original_call(service,request,timeout)
    monkeypatch.setattr(Service,'__call__',two_stores)
    result=case.execute()
    root=c.decode(case.service.dispatch_body['inputs']['inference_builder_go_json'])
    assert result['state']=='ENQUEUE_ONCE_AND_EXIT' and result['dispatches']==1
    assert root['qualified_runtime']==x.package
    assert root['prior_capture_qualified_runtime']['qualified_runtime']==old_package
    assert root['effective_epoch']['previous_checkpoint']['sha256']==s.sha(gzip.compress(s.canonical(h.locator),mtime=0))
    assert root['effective_epoch']['previous_capture']==h.locator['anchor']
    assert root['effective_epoch']['previous_checkpoint']['path']==history.locator_filename(h.locator)
    assert result['HTTP_calls']==len(case.service.calls)<=140
    assert result['HTTP_by_lane']['private']<=40
    assert all(r.get_method()=='GET' for r in case.service.calls if '/releases/' in r.full_url)
    for binding in (old_binding,current):
        assert any(r.full_url==s.API+'/releases/'+str(binding['release_id']) for r in case.service.calls)
    record_property('v3_prior_history_HTTP_calls',result['HTTP_calls'])
    record_property('v3_prior_history_private_GETs',result['HTTP_by_lane']['private'])


@pytest.mark.parametrize("resolved,expected,week",[(False,"GRADE_ONLY",8),(True,"FUTURE_CAPABLE",9)])
def test_new_parent_discovers_grade_only_without_new_feed_and_routes_once(history_case,resolved,expected,week,record_property):
    h=history_case;case=h.case;original=bytes(case.ops_packed)
    if resolved:h.locator["planning"]["resolved_weeks"]=[8];h.publish()
    result=case.execute()
    root=c.decode(case.service.dispatch_body["inputs"]["inference_builder_go_json"])
    ctx=root["effective_epoch"]
    assert ctx["schema_version"]==history.CONTEXT_V5 and ctx["plan"]["kind"]==expected and ctx["plan"]["week"]==week
    assert ctx["pending_post_recovery"]==dict(schema_version=t.PENDING_RECOVERY,handoffs=[],pending_reservations=[])
    assert ctx["previous_capture"]==h.locator["anchor"]
    assert ctx["previous_checkpoint"]["path"]==history.locator_filename(h.locator)
    assert result["HTTP_calls"]==len(case.service.calls)<=140 and result["HTTP_by_lane"]["private"]<=40
    record_property("HTTP_calls",result["HTTP_calls"])
    record_property("HTTP_by_lane",json.dumps(result["HTTP_by_lane"],sort_keys=True))
    assert case.service.calls[-1].full_url==w.DISPATCH_URL and result["dispatches"]==1
    assert case.ops_packed==original and h.locator["cohort"]["successful_forecast"] is False
    assert h.locator["cohort"]["run_id"]!=case.ops["run_id"]
    assert not any("/contents/"+w.PUBLIC_ROOT+"/2026-W" in r.full_url for r in case.service.calls)
    assert not any("/releases/assets/801" in r.full_url or "/releases/assets/802" in r.full_url for r in case.service.calls)


@pytest.mark.parametrize("damage",["private_planning","private_native","root_preimage","source_blob","helper_pin","incomplete_job","late_history","newest_failed","state_race"])
def test_new_history_discovery_authenticates_before_any_claim_or_enqueue(history_case,damage):
    h=history_case;case=h.case
    if damage=="private_planning":h.envelope["planning"]=deepcopy(h.envelope["planning"]);h.envelope["planning"]["resolved_weeks"]=[8]
    elif damage=="private_native":h.envelope["native_read_evidence"]["native_restore_proof"]["exact_readback"]=False
    elif damage=="root_preimage":h.envelope["root_go"]["cutoff_lead_seconds"]=99999
    elif damage=="source_blob":
        path=sorted(history.LOCATOR_HELPERS)[0];case.x.api.data[c.contents_url(path,old.B)]=old.content(path,b"CHANGED_LITERAL_COMMIT_BYTES")
    elif damage=="helper_pin":h.locator["helper_sha256"][sorted(history.LOCATOR_HELPERS)[0]]="0"*64
    elif damage=="incomplete_job":case.x.api.data[c.jobs_url("700")]["jobs"][-1].update(status="in_progress",conclusion=None,completed_at=None)
    elif damage=="late_history":h.locator["sidecar"]["grade_read_proof"]["known_by_at"]="2026-10-25T12:40:00Z"
    elif damage=="newest_failed":case.x.api.data[c.run_url("700")]["conclusion"]="failure"
    elif damage=="state_race":case.service.stale_at=2
    h.publish()
    with pytest.raises((w.ParentError,c.ControllerError,history.HistoryError,t.TemplateError,s.StoreError)):
        case.execute()
    assert not any(r.get_method() in {"POST","PATCH"} for r in case.service.calls)
    assert case.service.dispatch_body is None
    if damage in {"source_blob","helper_pin","incomplete_job","late_history","newest_failed"}:
        assert not any("/releases/assets/803" in r.full_url or "/releases/assets/804" in r.full_url for r in case.service.calls)


def test_old_parent_sidecar_reader_rejects_new_nonforecast_locator(history_case):
    h=history_case;case=h.case
    data=dict(receipt=case.ops,qualified_runtime=case.x.package,code_pins=case.x.p["producer"]["code_pins"],
        jobs={r:j for r,j in zip(c.ROLES,case.x.api.data[c.jobs_url("700")]["jobs"])},at=case.clock())
    with pytest.raises(history.HistoryError):history.validate_parent_sidecar(h.publish(),**data)
    with pytest.raises(history.HistoryError):history.validate_parent_sidecar(gzip.compress(s.canonical(h.locator["sidecar"]),mtime=0),
        **dict(data,receipt=h.locator["cohort"]))


def test_new_locator_metadata_cold_import_does_not_need_producer_numerical_code(history_case,tmp_path):
    h=history_case;case=h.case
    payload=dict(packed=base64.b64encode(h.publish()).decode(),receipt=case.ops,qualified_runtime=case.x.package,
        code_pins=case.x.p["producer"]["code_pins"],jobs=dict(zip(c.ROLES,case.x.api.data[c.jobs_url("700")]["jobs"])),at=case.clock().isoformat())
    path=tmp_path/"closed-fictional-history.json";path.write_bytes(c.canonical(payload))
    script='''import sys,json,base64,socket
from pathlib import Path
from unittest.mock import patch
from nfl_lab import audit_weekly_grade_history_v1 as h,private_draft_store as store
v=json.loads(Path(sys.argv[1]).read_bytes());v['packed']=base64.b64decode(v['packed'])
def forbidden(*args,**kwargs):raise AssertionError('METADATA_IO_FORBIDDEN')
with patch.object(store,'read_local',forbidden),patch.object(Path,'read_bytes',forbidden),patch('builtins.open',forbidden),patch.object(socket.socket,'connect',forbidden):
    result=h.locator_metadata(**v)
assert result['cohort']['kind']=='GRADING_ONLY'
assert not any(n in sys.modules for n in ('nfl_lab.audit_weekly_grade_v1','nfl_lab.audit_weekly_grade_checkpoint_v1','numpy','scipy','pandas','sklearn','pyarrow'))
print('COLD_LOCATOR_METADATA_OK')
'''
    result=subprocess.run([sys.executable,"-B","-c",script,str(path)],cwd=ROOT,capture_output=True,text=True,timeout=15)
    assert result.returncode==0,result.stderr
    assert result.stdout.strip()=="COLD_LOCATOR_METADATA_OK"


def test_routing_preserves_same_week_canonical_cutoffs_and_honest_missed_deadline(history_case):
    p=deepcopy(history_case.locator['planning']);at=history_case.case.clock()
    p['current']['schedule'][0]['kickoff_utc']='2026-10-26T18:00:00Z'
    p['current']['game_cutoffs']={'fictional-current':'2026-10-26T16:30:00Z'}
    plan=history.next_plan(p,at=at)
    assert plan['kind']=='FUTURE_CAPABLE' and plan['week']==8 and plan['game_cutoffs']==p['current']['game_cutoffs']
    assert plan['deadline_utc']=='2026-10-26T16:30:00Z'
    assert history.next_plan(p,at='2026-10-26T16:30:00Z')['kind']=='GRADE_ONLY'
    p['resolved_weeks']=[8]
    assert history.next_plan(p,at='2026-11-01T16:30:00Z')['kind']=='GRADE_ONLY'
    with pytest.raises(history.HistoryError):history.next_plan(p,at=p['known_by_at'])
    bad=deepcopy(p);bad['current']['schedule'][0]['outcome']=1
    with pytest.raises(history.HistoryError):history.validate_planning(bad)


def test_newer_or_ambiguous_locator_fails_before_any_new_decision(history_case):
    from types import SimpleNamespace
    ref=dict(schema_version=history.LOCATOR_REF,path=history.locator_filename(history_case.locator),sha256='a'*64)
    newer=ref['path'].replace('20261025T123410.000000Z','20261025T123411.000000Z')
    rows=directory(history.LOCATOR_ROOT,[(ref['path'],'file',100),(newer,'file',100)])
    client=SimpleNamespace(allowed=set(),json=lambda _:rows)
    with pytest.raises(history.HistoryError,match='NEWER_KNOWN_HISTORY'):history.require_latest(client,ref)
    tied=ref['path'].replace('--700--','--701--')
    with pytest.raises(history.HistoryError,match='AMBIGUOUS_FRESHEST'):
        history.latest_locator(directory(history.LOCATOR_ROOT,[(ref['path'],'file',100),(tied,'file',100)]))


@pytest.fixture
def multipart_history_case(history_case):
    """Private metadata only; no logical snapshot or part is decoded on Main."""
    h=history_case;v=h.locator;handoff=v['sidecar']['checkpoint_handoff'];writer=handoff['producer']
    handoff['schema_version']=history.CHECKPOINT_V2+'-handoff'
    outer=handoff['append_proof'];outer['schema_version']=history.CHECKPOINT_V2+'-native-append'
    outer.update(HTTP_calls=38,transfer_bytes=20000)
    def descriptor(index,sha,size):
        d=deepcopy(handoff['descriptor']);e=d['entry']
        e.update(payload_asset_id=901+2*index,payload_name='blob-'+sha+'.bin')
        e['payload'].update(sha256=sha,bytes=size)
        d.update(manifest_asset_id=902+2*index,manifest_sha256=c.digest(e),manifest_bytes=len(s.canonical(e)))
        return d
    parts=[dict(index=i,name=f'GRADING_PART_{i:02d}_{old.h([i,"part"])}.json.gz',bytes=20,
        sha256=old.h([i,'part']),decoded_bytes=1,decoded_sha256=old.h([i,'decoded'])) for i in range(2)]
    manifest=dict(schema_version='audit-weekly-grade-snapshot-v2',logical_sha256=handoff['snapshot_sha256'],logical_bytes=2,parts=parts)
    local_sha=s.sha(gzip.compress(s.canonical(manifest),mtime=0));records=[]
    for p in parts:
        d=descriptor(p['index'],p['sha256'],p['bytes'])
        proof=dict(schema_version=history.CHECKPOINT_V2+'-part-append',index=p['index'],local_manifest_sha256=local_sha,
            body_sha256=p['sha256'],body_bytes=p['bytes'],descriptor_sha256=c.digest(d),producer=writer,
            current_root_go_sha256=handoff['current_root_go_sha256'],qualification_sha256=outer['qualification_sha256'],
            started_at_utc=outer['started_at_utc'],completed_at_utc=outer['completed_at_utc'],HTTP_calls=15+5*p['index'],transfer_bytes=1000+1000*p['index'])
        records.append(dict(index=p['index'],descriptor=d,append_proof=proof))
    root=dict(schema_version=history.CHECKPOINT_V2+'-root',snapshot_manifest=manifest,snapshot_body_sha256=local_sha,parts=records)
    packed=gzip.compress(s.canonical(root),mtime=0)
    handoff.update(body_sha256=s.sha(packed),body_bytes=len(packed))
    d=handoff['descriptor'];e=d['entry'];e['payload'].update(sha256=s.sha(packed),bytes=len(packed));e['payload_name']='blob-'+s.sha(packed)+'.bin'
    d.update(manifest_sha256=c.digest(e),manifest_bytes=len(s.canonical(e)))
    outer.update(body_sha256=handoff['body_sha256'],body_bytes=handoff['body_bytes'],descriptor_sha256=c.digest(d))
    handoff['append_proof_sha256']=c.digest(outer)
    proof=v['sidecar']['grade_read_proof'];proof['restored_body_sha256']=handoff['body_sha256']
    body=h.envelope['native_read_evidence'];body['schema_version']=history.CHECKPOINT_V2+'-fresh-reader-native-evidence'
    native=body['native_restore_proof'];native.update(payload_sha256=handoff['body_sha256'],bytes=handoff['body_bytes'],transfer_bytes=3000)
    body['restored_binding'].update(sha256=handoff['body_sha256'],bytes=handoff['body_bytes'])
    body['context'].update(handoff=deepcopy(handoff),handoff_sha256=c.digest(handoff))
    reads=[]
    for p,r in zip(parts,records):
        reads.append(dict(schema_version=history.CHECKPOINT_V2+'-part-native-read',index=p['index'],descriptor_sha256=c.digest(r['descriptor']),
            root_native_proof_sha256=c.digest(native),root_body_sha256=handoff['body_sha256'],payload_sha256=p['sha256'],bytes=p['bytes'],
            reader=proof['reader'],inventory_canonical_sha256=old.h('one actual inventory'),manifest_api_sha256=old.h([p['index'],'manifest API']),
            payload_api_sha256=old.h([p['index'],'payload API']),started_at_utc=f"2026-10-25T12:34:0{5+p['index']}Z",completed_at_utc=f"2026-10-25T12:34:0{6+p['index']}Z",
            HTTP_calls=15+4*p['index'],transfer_bytes=5000+1000*p['index']))
    body['context']['multipart_readback']=dict(schema_version=history.CHECKPOINT_V2+'-complete-part-read',parts=reads,
        completed_at_utc='2026-10-25T12:34:08Z',HTTP_calls=20,transfer_bytes=7000)
    proof['proof_sha256']=c.digest(body)
    h.envelope.update(grade_read_proof=deepcopy(proof),handoff_sha256=c.digest(handoff))
    h.case.service.add_exact(e['payload_name'],packed,e['payload_asset_id'])
    h.case.service.add_exact('manifest-'+d['manifest_sha256']+'.json',s.canonical(e),d['manifest_asset_id'])
    h.publish();h.private_root=packed
    return h


def test_parent_multipart_metadata_fetches_private_root_and_all_proofs_within_original_caps(multipart_history_case,record_property):
    h=multipart_history_case;result=h.case.execute()
    assert result['state']=='ENQUEUE_ONCE_AND_EXIT'
    assert result['HTTP_calls']<=140 and result['HTTP_by_lane']['authority']<=80 and result['HTTP_by_lane']['private']<=40
    assert h.case.service.calls[-1].full_url==w.DISPATCH_URL
    assert any('/releases/assets/801' in r.full_url for r in h.case.service.calls)
    assert not any('/releases/assets/901' in r.full_url for r in h.case.service.calls)
    record_property('HTTP_calls',result['HTTP_calls']);record_property('HTTP_by_lane',json.dumps(result['HTTP_by_lane'],sort_keys=True))


@pytest.mark.parametrize('damage',['missing_last','part_order','root_proof','descriptor','payload','known_before_last','empty','extra_field'])
def test_parent_multipart_rejects_incomplete_or_unbound_part_evidence_before_claim(multipart_history_case,damage):
    h=multipart_history_case;body=h.envelope['native_read_evidence'];reads=body['context']['multipart_readback']
    if damage=='missing_last':reads['parts'].pop()
    elif damage=='part_order':reads['parts'].reverse()
    elif damage=='root_proof':reads['parts'][0]['root_native_proof_sha256']='0'*64
    elif damage=='descriptor':reads['parts'][0]['descriptor_sha256']='0'*64
    elif damage=='payload':reads['parts'][0]['payload_sha256']='0'*64
    elif damage=='known_before_last':reads['completed_at_utc']='2026-10-25T12:34:11Z'
    elif damage=='empty':reads['parts']=[]
    else:reads['qualified']=True
    digest=c.digest(body);h.locator['sidecar']['grade_read_proof']['proof_sha256']=digest;h.envelope['grade_read_proof']['proof_sha256']=digest
    h.publish()
    with pytest.raises(history.HistoryError):h.case.execute()
    assert not any(r.get_method() in {'POST','PATCH'} for r in h.case.service.calls)


@pytest.mark.parametrize('records_count',[1,16])
def test_parent_preserves_nonempty_pending_evidence_from_authenticated_history(case,records_count):
    """Fictional metadata propagation, not a native core-failure qualification."""
    x=case.x;digest=s.sha(b'abc')
    record=dict(schema_version='weekly-private-POST-reservation-v2',key='asset:blob-'+digest+'.bin',
        bytes=3,sha256=digest,name='blob-'+digest+'.bin')
    case.pending_recovery_spec=dict(schema_version=t.PENDING_RECOVERY,pending_reservations=[record],
        handoffs=[dict(schema_version='audit-weekly-hosted-v2-failure-handoff',binding=deepcopy(x.package['binding']),
            descriptor=deepcopy(x.template_seal['descriptor']),root_go_sha256='a'*64)])
    if records_count>1:
        records=[]
        for n in range(records_count):
            digest=s.sha(('preserved-pending-'+str(n)).encode())
            records.append(dict(record,key='asset:blob-'+digest+'.bin',sha256=digest,name='blob-'+digest+'.bin'))
        case.pending_recovery_spec['pending_reservations']=sorted(records,key=lambda r:r['key'])
    history_case.__wrapped__(case)
    result=case.execute()
    root=c.decode(case.service.dispatch_body['inputs']['inference_builder_go_json'])
    assert root['effective_epoch']['schema_version']==history.CONTEXT_V5
    assert t.pending_recovery(root)==case.pending_recovery_spec
    if records_count==1:assert root['effective_epoch']['pending_post_recovery']==case.pending_recovery_spec
    else:assert root['effective_epoch']['pending_post_recovery']['schema_version']==t.PENDING_RECOVERY_ENVELOPE
    assert result['dispatches']==1 and result['HTTP_by_lane']['private']<=40 and result['HTTP_calls']<=140
