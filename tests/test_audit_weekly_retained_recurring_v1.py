"""Fictional native transport and live bootstrap fixtures; no real services/data."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import base64
from pathlib import Path
import pickle
import socket
from types import SimpleNamespace

import pytest

from nfl_lab import audit_weekly_retained_v1 as r, audit_weekly_archive_v1 as archive
from nfl_lab import audit_weekly_controller_v1 as controller
from nfl_lab import private_draft_store as store, gha_private_checkpoint as cp
from test_audit_weekly_retained_v1 import saved, chain, execute, ROOT, RUN, SOURCE
from test_private_draft_store_v2 import Response
import test_audit_weekly_controller_bootstrap_v1 as bootstrap_fixture


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.setattr(socket.socket, "connect", lambda *_: pytest.fail("REAL_NETWORK_FORBIDDEN"))


def test_retained_batches_all_original_files_and_explicit_empty_files(chain, monkeypatch):
    groups, empty, scans = [], [], []
    original_group, original_publish = archive._extract_owned_group, archive._publish_owned_files
    scan = chain.p.storage._scan
    def counted():
        scans.append(1)
        return scan()
    monkeypatch.setattr(chain.p.storage, "_scan", counted)
    def group(body, record, storage, destination):
        before = len(scans)
        result = original_group(body, record, storage, destination)
        groups.append((deepcopy(record), len(scans) - before))
        return result
    def publish(storage, files, destination):
        if all(not body for _, body in files): empty.extend(name for name, _ in files)
        return original_publish(storage, files, destination)
    monkeypatch.setattr(archive, "_extract_owned_group", group)
    monkeypatch.setattr(archive, "_publish_owned_files", publish)
    monkeypatch.setattr(r.codec, "extract_owned", lambda *_: pytest.fail("LEGACY_PER_FILE_EXTRACTION"))
    result = execute(chain)
    assert groups and all(count == 2 for _, count in groups)
    assert {f["logical_path"] for record, _ in groups for f in record["files"]} == {
        f["logical_path"] for f in chain.snapshot["files"] if f["bytes"]}
    assert set(empty) == {f["logical_path"] for f in chain.snapshot["files"] if not f["bytes"]}
    assert len(result["aliases"]) == len(chain.snapshot["files"])
    for f in chain.snapshot["files"]:
        ref = result["aliases"][f["logical_path"]]
        if ref["bytes"]: assert cp.read_ref(ref, ref["bytes"]) == chain.old_raw[f["path"]]
        else: assert Path(ref["path"]).read_bytes() == b""
        assert Path(f["path"]).read_bytes() == chain.old_raw[f["path"]]
    assert result["public_release"] is result["model_replay_performed"] is False
    assert result["remote_writes"] == result["model_decodes"] == result["protected_outcome_reads"] == 0
    assert all(c.calls <= 40 for c in chain.factory.clients) and len(chain.factory.clients) <= 11
    assert all(q.method == "GET" for q in chain.history.calls[chain.calls_before:])


def test_retained_corrupt_group_is_rejected_before_any_group_alias(chain, monkeypatch):
    original = archive._extract_owned_group
    def corrupt(body, record, storage, destination):
        damaged = body[:-1] + bytes([body[-1] ^ 1])
        return original(damaged, record, storage, destination)
    monkeypatch.setattr(archive, "_extract_owned_group", corrupt)
    with pytest.raises(store.StoreError, match="BUNDLE_HASH"):
        execute(chain)
    output = Path(chain.request["output"])
    assert not (output / "files").exists()
    assert (output / "owned-downloads/index.gz").is_file()
    assert not (output / "RETAINED_RESULT.json").exists()
    assert all(q.method == "GET" for q in chain.history.calls[chain.calls_before:])


@pytest.fixture
def operational(chain, tmp_path, monkeypatch):
    # The actual bootstrap verifier consumes raw injected API bodies and the
    # original once-claim fixture. This is a FICTIONAL live proof, never Actions.
    root = tmp_path / "fictional-bootstrap"; root.mkdir()
    system = bootstrap_fixture.system.__wrapped__(root)
    proof = system.verify()
    p = deepcopy(chain.request); h = p["reader_handoff"]["archive"]
    spec = system.p["producer"]
    h["source_sha"] = spec["source_sha"]
    h["jobs"] = {role: spec["jobs"][role] for role in ("produce", "restore", "consume")}
    workflow_ref = system.env["GITHUB_WORKFLOW_REF"]
    h["producer"].update(source_sha=spec["source_sha"], job_id=h["jobs"]["produce"], workflow_ref=workflow_ref)
    p["reader_handoff"]["restorer"].update(source_sha=spec["source_sha"], job_id=h["jobs"]["restore"], workflow_ref=workflow_ref)
    codes = dict(chain.history.codes); codes[".github/workflows/lab.yml"] = system.workflow
    p["historical_source_sha256"] = {name: store.sha(body) for name, body in codes.items()}
    stamp = max(datetime.now(timezone.utc), store.utc(proof.bootstrap_seal.document["owner_registration_completed_at"]) + timedelta(seconds=1))
    monkeypatch.setattr(r, "now", lambda: stamp)
    authority = dict(chain.authority, source_sha=spec["source_sha"], run_id=proof.document["run_id"], job_id=proof.document["job_id"],
        api_job_id=proof.document["api_job_id"], workflow_ref=workflow_ref, owner_root_go_sha256=controller.sha(system.raw),
        request_sha256=store.sha(store.canonical(p)), issued_at_utc=stamp.isoformat(), expires_at_utc=(stamp + timedelta(minutes=15)).isoformat())
    jobs = {}
    for n, role in enumerate(("produce", "restore", "consume")):
        start, end = chain.history.times[role]
        jobs[role] = dict(repository=store.REPO, run_id=h["run_id"], source_sha=h["source_sha"], workflow_ref=workflow_ref,
            api_job_id=777 + n, job_id=h["jobs"][role], status="completed", conclusion="success",
            started_at=start.isoformat(), completed_at=end.isoformat(), verified_permissions=dict(contents="write", actions="read"))
    calls, callbacks = [], []
    x = SimpleNamespace(chain=chain, system=system, p=p, authority=authority, jobs=jobs, proof=proof, stamp=stamp,
        actor=dict(controller.BOT), codes=codes, calls=calls, callbacks=callbacks, allow_live=True)
    def transport(request, timeout):
        calls.append(request)
        url = request.full_url
        if url == store.API + "/actions/runs/" + authority["run_id"]:
            return Response(dict(id=int(authority["run_id"]), head_sha=authority["source_sha"], event="workflow_dispatch", run_attempt=1,
                status="in_progress", path=".github/workflows/lab.yml", head_branch=spec["branch"], actor=dict(controller.BOT),
                repository=dict(full_name=store.REPO), head_repository=dict(full_name=store.REPO)))
        if url == store.API + "/actions/runs/" + authority["run_id"] + "/jobs?per_page=100&page=1":
            return Response(dict(total_count=1,jobs=[dict(id=authority["api_job_id"],name=authority["job_id"],
                run_id=int(authority["run_id"]),head_sha=authority["source_sha"],status="in_progress")]))
        if url == store.API + "/actions/runs/" + h["run_id"]:
            return Response(dict(id=int(h["run_id"]), head_sha=h["source_sha"], event="workflow_dispatch", run_attempt=1, status="completed", conclusion="success",
                path=".github/workflows/lab.yml", head_branch=spec["branch"], actor=x.actor,
                repository=dict(full_name=store.REPO), head_repository=dict(full_name=store.REPO)))
        if url == store.API + "/actions/runs/" + h["run_id"] + "/jobs?per_page=100&page=1":
            return Response(dict(total_count=3, jobs=[dict(id=j["api_job_id"], name=j["job_id"], run_id=int(j["run_id"]), head_sha=j["source_sha"],
                status=j["status"], conclusion=j["conclusion"], started_at=j["started_at"], completed_at=j["completed_at"]) for j in jobs.values()]))
        if "/contents/" in url:
            name = url.split("/contents/", 1)[1].split("?ref=", 1)[0]
            assert url.endswith("?ref=" + h["source_sha"])
            body = codes[name]
            return Response(dict(type="file", path=name, encoding="base64", size=len(body), content=base64.b64encode(body).decode()))
        return chain.history.transport(request, timeout)
    def authenticate(request):
        callbacks.append(deepcopy(request))
        assert request["inputs_sha256"] == store.sha(store.canonical(request["inputs"]))
        assert request["kind"] in {"BIND_SEALED_HISTORICAL_SOURCE", "LIVE_HISTORICAL_METADATA_BEFORE_PRIVATE_GET"}
        return request["kind"] == "BIND_SEALED_HISTORICAL_SOURCE" or x.allow_live
    x.authenticate = authenticate
    def mint(**kwargs):
        values = dict(bootstrap_proof=proof, public_policy_sha256=proof.bootstrap_seal.document["static_public_policy_sha256"],
            historical_jobs=jobs, authenticate=authenticate, root=ROOT, clock=lambda: stamp)
        values.update(kwargs)
        return r.bind_historical_source(p, authority, **values)
    x.mint = mint
    def client():
        job = dict(execution_lane="github_actions", workflow_ref=workflow_ref, workflow_sha=authority["source_sha"], job_id=authority["job_id"],
            permission="write", event_name="workflow_dispatch", api_job_id=0, run_authenticated=False)
        c = r.ReadClient("ghs_FICTIONAL", authority["run_id"], journal=chain.p.base / "new-journal",
            source_sha=authority["source_sha"], job=job, operation="restore", transport=transport, extra_routes=r.routes(p))
        c.authenticate_actions_job()
        c.bind(chain.history.old.binding)
        return c
    x.client = client
    return x


def test_only_live_sealed_source_grant_accepts_same_source_prior_bot_metadata(operational):
    x = operational; grant = x.mint()
    evidence = r.authenticate_origin(x.client(), x.p, x.authority, historical_grant=grant)
    assert evidence == x.jobs
    assert x.p["reader_handoff"]["archive"]["source_sha"] == x.authority["source_sha"]
    assert [r["kind"] for r in x.callbacks] == ["BIND_SEALED_HISTORICAL_SOURCE", "LIVE_HISTORICAL_METADATA_BEFORE_PRIVATE_GET"]
    assert all(q.method == "GET" for q in x.calls)
    # Only metadata/canary reads: the old fixture payloads deliberately do NOT
    # claim this new source and are never read or qualified by this test.
    canary = str(x.chain.history.old.binding["canary_asset_id"])
    assert all("/releases/assets/" not in q.full_url or q.full_url.endswith("/" + canary) for q in x.calls)
    with pytest.raises(store.StoreError, match="CANNOT_BE_SERIALIZED"): pickle.dumps(grant)
    with pytest.raises(store.StoreError, match="LIVE_HISTORICAL_SOURCE_GRANT"):
        r.authenticate_origin(x.client(), x.p, x.authority, historical_grant=grant.document)


@pytest.mark.parametrize("failure", ["policy", "incomplete_jobs", "saved_proof", "changed_grant", "live_rejected", "unapproved_source"])
def test_bot_grant_failures_stop_before_private_asset_reads(operational, failure):
    x = operational
    if failure in {"policy", "incomplete_jobs", "saved_proof"}:
        kw = dict(public_policy_sha256="0" * 64) if failure == "policy" else dict(historical_jobs={}) if failure == "incomplete_jobs" else dict(bootstrap_proof=x.proof.document)
        with pytest.raises((store.StoreError, controller.ControllerError)): x.mint(**kw)
    else:
        if failure == "unapproved_source":
            h = x.p["reader_handoff"]["archive"]; h["source_sha"] = SOURCE
            h["producer"]["source_sha"] = SOURCE; x.p["reader_handoff"]["restorer"]["source_sha"] = SOURCE
            for j in x.jobs.values(): j["source_sha"] = SOURCE
            x.authority["request_sha256"] = store.sha(store.canonical(x.p))
        grant = x.mint()
        if failure == "changed_grant": grant.document["scope"]["approved_source_sha"] = "d" * 40
        if failure == "live_rejected": x.allow_live = False
        with pytest.raises(store.StoreError): r.authenticate_origin(x.client(), x.p, x.authority, historical_grant=grant)
    assert not any("/releases/assets/" in q.full_url for q in x.calls)


def test_bot_never_accepted_by_legacy_owner_path(operational):
    x = operational
    with pytest.raises(store.StoreError, match="ACTUAL_NEW_RETAINED_BRANCH_OWNER"):
        r.authenticate_origin(x.client(), x.p, x.authority)
    assert not any("/releases/assets/" in q.full_url for q in x.calls)


def test_original_Nick_historical_actor_remains_supported_with_live_current_bot(operational):
    x=operational;x.actor=dict(controller.OWNER)
    grant=x.mint()
    assert r.authenticate_origin(x.client(),x.p,x.authority,historical_grant=grant)==x.jobs
    assert x.actor==controller.OWNER
