"""Fictional API/native metadata only; no secrets, providers, private stores or Git."""
import base64
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import importlib.util
import io
import gzip
import hashlib
import json
from pathlib import Path
import pickle
import socket
from types import SimpleNamespace
import zipfile

import pytest

from nfl_lab import audit_weekly_controller_v1 as c
from nfl_lab import audit_weekly_controller_bootstrap_v1 as b
from tools import audit_weekly_controller_bootstrap_v1 as cli

spec = importlib.util.spec_from_file_location("fictional_controller_fixture", Path(__file__).with_name("test_audit_weekly_controller_v1.py"))
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)


def fictional_runtime_metadata(package, census, number=2):
    """New fictional qualification metadata, never actual hosted evidence."""
    from nfl_lab import audit_weekly_template_v1 as t,private_draft_store as s
    result=deepcopy(package); binding=result['binding']; q=result['qualification']
    runtime=format(number,'032x'); run=str(int(binding['origin_run_id'])+number)
    binding.update(runtime_id=runtime,origin_run_id=run,release_id=binding['release_id']+1000*number,
        tag_name='weekly-private-runtime-v2-'+runtime,browser_tag='weekly-private-runtime-v2-'+runtime,
        canary_asset_id=binding['canary_asset_id']+10000*number)
    body=s.probe.fixture(run);binding.update(canary_sha256=s.sha(body),canary_name='canary-'+s.sha(body)+'.txt')
    for i,proof in enumerate((q['before_proof'],q['read_proof'],q)):
        proof.update(run_id=run,binding_sha256=t.digest(binding),process_identity=s.sha(str([number,i]).encode()))
        proof['job']['api_job_id']+=10000*number
    before,read=q['before_proof'],q['read_proof']
    read['before_sha256']=t.digest(before)
    q.update(before_sha256=t.digest(before),read_sha256=t.digest(read),
        before_process_identity=before['process_identity'],read_process_identity=read['process_identity'])
    result.update(runtime_id=runtime,run_id=run)
    quota=result['quota_reservation'];count=quota['existing_draft_runtimes']+1
    quota.update(existing_draft_runtimes=count,reserved_before_bytes=(count+quota['pending_unlocated_runtimes'])*(32<<20),
        reserved_after_bytes=(count+quota['pending_unlocated_runtimes']+1)*(32<<20),new_runtime_id=runtime,
        pending_census_sha256=t.digest(census),pending_records=len(census['reservations']))
    if 'root_go_sha256' in result:result['root_go_sha256']=s.sha(('fictional rotation '+str(number)).encode())
    return result


def dual_runtime_root(root, package, census, anchor, *, original_root=None):
    from nfl_lab import audit_weekly_template_v1 as t
    result=deepcopy(root);result['schema_version']=t.ROOT_V3
    result['qualified_runtime']=fictional_runtime_metadata(package,census)
    result['pending_census']=deepcopy(census)
    result['prior_capture_qualified_runtime']=dict(schema_version=t.PRIOR_RUNTIME,purpose='PRIOR_CAPTURE_QUALIFIED_RUNTIME',
        anchor=deepcopy(anchor),qualified_runtime=deepcopy(package),pending_census=deepcopy(census),
        root_static_sha256=None if original_root is None else t.static_root_sha256(original_root))
    return result


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.setattr(socket.socket, "connect", lambda *_: pytest.fail("REAL_NETWORK_FORBIDDEN"))


@pytest.fixture
def system(tmp_path):
    x = old.system.__wrapped__(tmp_path)
    x.calls = []
    x.hooks = {}
    x.workflow = old.wf().replace(b"  audit-weekly-restore-v1:\n", b"  audit-weekly-restore-v1:\n    needs: audit-weekly-produce-v1\n").replace(
        b"  audit-weekly-export-v1:\n", b"  audit-weekly-export-v1:\n    needs: [audit-weekly-produce-v1, audit-weekly-restore-v1]\n")
    for label, source in (("parent", old.A), ("child", old.B)):
        root = getattr(x, label + "_source")
        pins = x.p["parent" if label == "parent" else "producer"]["code_pins"]
        for name in (b.MODULE, b.TOOL, b.TEST):
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            body = ("FICTIONAL bootstrap " + name).encode()
            path.write_bytes(body)
            pins[name] = c.sha(body)
        (root / c.WORKFLOW).write_bytes(x.workflow)
        pins[c.WORKFLOW] = c.sha(x.workflow)
        x.p["parent" if label == "parent" else "producer"]["workflow_sha256"] = c.sha(x.workflow)
        x.api.data[c.contents_url(c.WORKFLOW, source)] = old.content(c.WORKFLOW, x.workflow)
    x.reg = c.canonical(x.p)
    x.seal = c.sha(x.reg)
    x.go["code_pins"] = deepcopy(x.p["producer"]["code_pins"])
    ctx = x.go["effective_epoch"]["controller_context"]
    ctx["registration_sha256"] = x.seal
    ctx["scheduled_parent"]["workflow_sha256"] = c.sha(x.workflow)
    x.bind_root()
    x.claim.update(registration_sha256=x.seal, root_go_sha256=c.sha(x.raw))
    x.api.data[c.contents_url(x.claim_path, old.D)] = old.content(x.claim_path, c.canonical(x.claim))
    x.api.data[c.API + "/commits/" + old.D]["files"][0]["sha"] = c.blob_sha(c.canonical(x.claim))
    x.template = c.canonical(dict(approved_private_metadata="fictional" * 6500))
    assert 16 << 10 < len(x.template) < 60 << 10
    x.private_descriptor = b'{"fictional_descriptor":"no real location"}'
    x.binding = b'{"fictional_storage_binding":true}'
    x.descriptor = dict(schema_version=b.VERSION + "-private-template-descriptor",
        template_sha256=c.sha(x.template), template_bytes=len(x.template),
        private_descriptor_sha256=c.sha(x.private_descriptor), storage_binding_sha256=c.sha(x.binding))
    native = {}
    for role, number, start, end in (("write", 41, "12:00:01", "12:00:20"), ("read", 42, "12:01:01", "12:01:20")):
        native[role] = dict({k: v for k, v in x.descriptor.items() if k != "schema_version"},
            job_id=b.JOBS[role], api_job_id=number, process_identity=old.h(role + " process"),
            started_at_utc="2026-10-25T" + start + "Z", completed_at_utc="2026-10-25T" + end + "Z",
            receipt_sha256=old.h(role + " actual native receipt"),
            operation={"write": "CREATE_PRIVATE_TEMPLATE_ONCE", "read": "FRESH_PRIVATE_TEMPLATE_READ"}[role],
            successful_private_creates=1 if role == "write" else 0)
    # Registration must precede the genuine writer. The old 3-job readiness
    # finished 10:30; owner registration completes 12:02; schedule starts 13:36.
    x.p["registered_at_utc"] = "2026-10-25T11:00:00Z"
    x.reg = c.canonical(x.p)
    x.seal = c.sha(x.reg)
    ctx["registration_sha256"] = x.seal
    x.go["operation"] = "RECURRING_CAPTURE"
    x.go["effective_epoch"].update(schema_version="audit-weekly-recurring-v1-context", previous_capture=dict(
        feed_sha256=x.p["readiness"]["receipt_bindings"]["feed_sha256"], receipt_sha256=x.p["readiness"]["receipt_sha256"]))
    x.static_policy = c.canonical(dict(source_sha=old.B, registered_at_utc="2026-10-25T11:00:00Z", fictional_static_contract=True))
    x.go["publication_registration"] = dict(policy_sha256=c.sha(x.static_policy))
    x.bind_root()
    x.claim.update(registration_sha256=x.seal, root_go_sha256=c.sha(x.raw))
    x.api.data[c.contents_url(x.claim_path, old.D)] = old.content(x.claim_path, c.canonical(x.claim))
    x.api.data[c.API + "/commits/" + old.D]["files"][0]["sha"] = c.blob_sha(c.canonical(x.claim))
    x.native = dict(schema_version=b.VERSION + "-native-safe-seal", repository=c.REPO, run_id="400", source_sha=old.B,
        branch=x.p["producer"]["branch"], workflow_sha256=c.sha(x.workflow),
        code_pins_sha256=c.digest(x.p["producer"]["code_pins"]), registration_sha256=x.seal,
        registered_at_utc=x.p["registered_at_utc"], template_descriptor=deepcopy(x.descriptor),
        writer=native["write"], reader=native["read"],
        sealer=dict(job_id=b.JOBS["seal"], api_job_id=43, process_identity=old.h("sealer process"),
            started_at_utc="2026-10-25T12:02:01Z", completed_at_utc="2026-10-25T12:02:20Z"),
        static_public_policy_sha256=c.sha(x.static_policy),
        created_at_utc="2026-10-25T12:02:21Z", public_root=False, fits=0)
    d = x.api.data
    d[c.run_url("400")] = old.run("400", old.B, x.p["producer"]["branch"], c.OWNER, updated="2026-10-25T12:03:00Z")
    d[c.jobs_url("400")] = dict(total_count=3, jobs=[
        old.job("400", old.B, b.JOBS["write"], 41, "2026-10-25T12:00:00Z", "2026-10-25T12:00:30Z"),
        old.job("400", old.B, b.JOBS["read"], 42, "2026-10-25T12:01:00Z", "2026-10-25T12:01:40Z"),
        old.job("400", old.B, b.JOBS["seal"], 43, "2026-10-25T12:02:00Z", "2026-10-25T12:02:40Z")])
    x.public_commit = "f" * 40
    d[b.history_url()] = [dict(sha=x.public_commit)]
    x.artifact_url = c.API + "/actions/artifacts/51"
    d[x.artifact_url] = dict(id=51, name="controller-root-safe-seal-v1-400", expired=False,
        workflow_run=dict(id=400, head_sha=old.B, repository_id=123, head_repository_id=123),
        created_at="2026-10-25T12:02:22Z", updated_at="2026-10-25T12:02:23Z")

    def publish(*, artifact=True, extra_zip=None):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("SAFE_SEAL.json", c.canonical(x.native))
            if extra_zip:
                archive.writestr(*extra_zip)
        x.packed = stream.getvalue()
        x.record = dict(schema_version=b.VERSION + "-public-seal", repository=c.REPO,
            registration_base64=base64.b64encode(x.reg).decode(), native_artifact_zip_base64=base64.b64encode(x.packed).decode(), artifact_id=51)
        x.record_raw = c.canonical(x.record)
        d[c.contents_url(b.REGISTRY_PATH, x.public_commit)] = old.content(b.REGISTRY_PATH, x.record_raw)
        d[c.API + "/commits/" + x.public_commit] = dict(sha=x.public_commit, parents=[dict(sha="e" * 40)],
            committer=deepcopy(c.BOT), files=[dict(filename=b.REGISTRY_PATH, status="added", sha=c.blob_sha(x.record_raw))])
        if artifact:
            d[x.artifact_url].update(digest="sha256:" + c.sha(x.packed), size_in_bytes=len(x.packed))
    x.publish = publish
    publish()

    def get(url, cap):
        x.calls.append((url, cap))
        assert b.fixed_route(url), "UNREGISTERED_ROUTE"
        assert url in d, "UNEXPECTED_METADATA_GET"
        value = deepcopy(d[url])
        if url in x.hooks:
            value = x.hooks[url](value, sum(u == url for u, _ in x.calls))
        return c.Reply(200, c.canonical(value))
    x.get = get
    x.load = lambda: b.load_seal(x.env, x.child_source, metadata_get=get, clock=lambda: old.AT, read_head=x.read_head)
    x.verify = lambda: b.authorize_child(x.env, x.child_source, x.raw, metadata_get=get,
        event_bytes=x.event, clock=lambda: old.AT, read_head=x.read_head)
    return x


def test_full_live_bootstrap_frozen_child_thirty_GETs_no_faked_owner(system):
    x = system
    proof = x.verify()
    assert type(proof) is c.Proof and len(x.calls) == 30
    assert proof.document["actor"] == c.BOT and proof.document["parent_actor"] == c.OWNER
    assert proof.verify(registration_sha256=x.seal, run_id="300", job_id=x.env["GITHUB_JOB"], root_sha256=c.sha(x.raw)) is proof
    with pytest.raises(c.ControllerError):
        pickle.dumps(proof)
    assert all("/releases/" not in u and "/dispatches" not in u for u, _ in x.calls)


def test_private_55k_template_bound_exactly_not_16k_inline_or_public(system):
    x = system
    seal = x.load()
    assert len(x.calls) == 10
    assert b.verify_private_template(seal, x.template, x.private_descriptor, x.binding) == c.decode(x.template)
    assert x.template not in x.record_raw
    assert seal.document["private_reads"] == 0 and seal.document["activation_authorized"] is False
    with pytest.raises(b.BootstrapError):
        b.verify_private_template(seal, x.template + b" ", x.private_descriptor, x.binding)
    with pytest.raises(b.BootstrapError):
        pickle.dumps(seal)


@pytest.mark.parametrize("which", ["template", "descriptor", "binding"])
def test_private_template_or_storage_locator_tamper(system, which):
    x = system
    values = [x.template, x.private_descriptor, x.binding]
    values[["template", "descriptor", "binding"].index(which)] += b"x"
    with pytest.raises(b.BootstrapError):
        b.verify_private_template(x.load(), *values)


def test_JSON_flags_cannot_authenticate_forged_native_receipts(system):
    x = system
    x.native["writer"]["receipt_sha256"] = old.h("invented all green")
    x.publish(artifact=False)
    with pytest.raises(b.BootstrapError, match="GENUINE_OWNER_RUN_NATIVE_ARTIFACT_DIGEST_REQUIRED"):
        x.verify()


@pytest.mark.parametrize("change", [dict(status="in_progress", conclusion=None), dict(actor=c.BOT),
    dict(triggering_actor=c.BOT), dict(head_sha=old.A), dict(event="schedule"), dict(run_attempt=2), dict(conclusion="failure")])
def test_actual_owner_registration_run_required(system, change):
    x = system
    x.api.data[c.run_url("400")].update(deepcopy(change))
    with pytest.raises(c.ControllerError):
        x.verify()


@pytest.mark.parametrize("change", [dict(expired=True), dict(digest="sha256:" + "0" * 64), dict(size_in_bytes=1),
    dict(name="self-asserted"), dict(workflow_run=dict(id=999, head_sha=old.B, repository_id=123, head_repository_id=123))])
def test_native_artifact_metadata_source_and_physical_digest_required(system, change):
    x = system
    x.api.data[x.artifact_url].update(change)
    with pytest.raises(b.BootstrapError):
        x.verify()


@pytest.mark.parametrize("fixture_name", ["system", "locator_system"])
def test_fractional_native_seal_same_second_artifact_preserves_exact_ZIP_and_clocks(request, fixture_name):
    x = request.getfixturevalue(fixture_name)
    x.native["created_at_utc"] = "2026-10-25T12:02:21.008169+00:00"
    x.api.data[x.artifact_url].update(created_at="2026-10-25T12:02:21Z", updated_at="2026-10-25T12:02:21Z")
    if fixture_name == "system":
        x.publish(); record = x.record; load = x.load
    else:
        x.publish_locator(); record = x.locator_record; load = x.load_locator
    native = c.canonical(x.native)
    packed = base64.b64decode(record["native_artifact_zip_base64"], validate=True)
    seal = load()
    assert seal.document["artifact_sha256"] == c.sha(packed)
    assert c.canonical(x.native) == native
    assert b.safe_seal(packed, registry_version=seal.registry_version)["created_at_utc"] == x.native["created_at_utc"]
    assert len(x.calls) == 10


@pytest.mark.parametrize("native,created,accepted", [
    ("2026-10-26T06:19:56.008169+00:00", "2026-10-26T06:19:56Z", True),
    ("2026-10-26T06:19:56.999999+00:00", "2026-10-26T06:19:56Z", True),
    ("2026-10-26T06:19:57.000000+00:00", "2026-10-26T06:19:56Z", False),
    ("2026-10-26T06:19:56.008169+00:00", "2026-10-26T06:19:55Z", False),
    ("2026-10-26T06:19:56.008169+00:00", "2026-10-26T06:19:57Z", True),
    ("2026-10-26T06:19:56.008169+00:00", "2026-10-26T06:19:56.001Z", False),
    ("2026-10-26T06:19:56.008169+00:00", "2026-10-26T06:19:56.008168Z", False),
    ("2026-10-26T06:19:56.008169+00:00", "2026-10-26T06:19:56.008169Z", True),
    ("2026-10-26T06:19:56.008169+00:00", "2026-10-26T06:19:56.000000Z", False),
    ("2026-10-26T06:19:56.008169+00:00", "2026-10-26T06:19:56+00:00", False),
])
def test_actual_native15_precision_boundary_without_rewriting_native_clock(native, created, accepted):
    # Literal owner-reported native15 counterexample. This is timestamp
    # compatibility testing, not a new claim of actual artifact qualification.
    before = native
    if accepted:
        b.verify_artifact_upload_clock(native, created, created, "2026-10-26T06:19:59Z")
    else:
        with pytest.raises(b.BootstrapError, match="NATIVE_SEAL_UPLOAD_INSIDE_THIRD_JOB"):
            b.verify_artifact_upload_clock(native, created, created, "2026-10-26T06:19:59Z")
    assert native == before


@pytest.mark.parametrize("updated,completed", [
    ("2026-10-26T06:19:55Z", "2026-10-26T06:19:59Z"),
    ("2026-10-26T06:20:00Z", "2026-10-26T06:19:59Z"),
])
def test_whole_second_compatibility_keeps_strict_API_updated_and_job_order(updated, completed):
    with pytest.raises(b.BootstrapError, match="NATIVE_SEAL_UPLOAD_INSIDE_THIRD_JOB"):
        b.verify_artifact_upload_clock("2026-10-26T06:19:56.008169+00:00", "2026-10-26T06:19:56Z", updated, completed)


@pytest.mark.parametrize("updated,accepted", [
    ("2026-10-26T06:19:56.008168Z", False),
    ("2026-10-26T06:19:56.008169Z", True),
    ("2026-10-26T06:19:56.008170Z", True),
    ("2026-10-26T06:19:56.000000Z", False),
])
def test_fractional_update_keeps_native_precision_after_coarse_creation(updated, accepted):
    args = ("2026-10-26T06:19:56.008169+00:00", "2026-10-26T06:19:56Z", updated,
        "2026-10-26T06:19:59Z")
    if accepted:
        b.verify_artifact_upload_clock(*args)
    else:
        with pytest.raises(b.BootstrapError, match="NATIVE_SEAL_UPLOAD_INSIDE_THIRD_JOB"):
            b.verify_artifact_upload_clock(*args)


@pytest.mark.parametrize("fixture_name", ["system", "locator_system"])
def test_same_second_creation_cannot_hide_fractional_update_before_native(request, fixture_name):
    x = request.getfixturevalue(fixture_name)
    x.native["created_at_utc"] = "2026-10-25T12:02:21.008169+00:00"
    x.api.data[x.artifact_url].update(created_at="2026-10-25T12:02:21Z",
        updated_at="2026-10-25T12:02:21.008168Z")
    if fixture_name == "system":
        x.publish(); load = x.load
    else:
        x.publish_locator(); load = x.load_locator
    with pytest.raises(b.BootstrapError, match="NATIVE_SEAL_UPLOAD_INSIDE_THIRD_JOB"):
        load()


@pytest.mark.parametrize("fixture_name", ["system", "locator_system"])
@pytest.mark.parametrize("damage", ["digest", "run", "source", "current_clock", "job_completion"])
def test_same_second_compatibility_cannot_replace_artifact_identity_or_native_freshness(request, fixture_name, damage):
    x = request.getfixturevalue(fixture_name)
    x.native["created_at_utc"] = "2026-10-25T12:02:21.008169+00:00"
    x.api.data[x.artifact_url].update(created_at="2026-10-25T12:02:21Z", updated_at="2026-10-25T12:02:21Z")
    version = 1 if fixture_name == "system" else 2
    (x.publish if version == 1 else x.publish_locator)()
    artifact = x.api.data[x.artifact_url]
    at = old.AT
    if damage == "digest": artifact["digest"] = "sha256:" + "0" * 64
    elif damage == "run": artifact["workflow_run"]["id"] = 999
    elif damage == "source": artifact["workflow_run"]["head_sha"] = old.A
    elif damage == "current_clock": at = c.utc("2026-10-25T12:02:21.008168+00:00")
    else: x.api.data[c.jobs_url("400")]["jobs"][2]["completed_at"] = "2026-10-25T12:02:21Z"
    with pytest.raises(c.ControllerError):
        b.load_seal(x.env, x.child_source, metadata_get=x.get, clock=lambda:at,
            read_head=x.read_head, registry_version=version)


@pytest.mark.parametrize("field,value", [("successful_private_creates", 2), ("successful_private_creates", True),
    ("template_bytes", 0), ("operation", "ALREADY_EXISTED_REUSED"), ("private_descriptor_sha256", "0" * 64)])
def test_one_native_create_closed_receipt_not_JSON_success_flags(system, field, value):
    x = system
    x.native["writer"][field] = value
    x.publish()
    with pytest.raises(b.BootstrapError):
        x.verify()


def test_reader_must_be_distinct_process_and_actual_separate_job(system):
    x = system
    x.native["reader"]["process_identity"] = x.native["writer"]["process_identity"]
    x.publish()
    with pytest.raises(b.BootstrapError):
        x.verify()


@pytest.mark.parametrize("value", ["2026-10-25T11:59:59Z", "2026-10-25T12:01:41Z"])
def test_native_receipt_cannot_be_backdated_or_outlive_its_job(system, value):
    x = system
    x.native["reader"]["started_at_utc"] = value
    x.publish()
    with pytest.raises(b.BootstrapError):
        x.verify()


def test_owner_registration_finished_before_parent_is_required(system):
    x = system
    x.api.data[c.run_url("400")]["updated_at"] = "2026-10-25T13:36:06Z"
    with pytest.raises(b.BootstrapError, match="OWNER_REGISTRATION_MUST_COMPLETE_BEFORE_SCHEDULED_PARENT"):
        x.verify()


def test_current_source_bytes_cannot_be_replaced_by_seal_codepin_flags(system):
    x = system
    (x.child_source / b.MODULE).write_bytes(b"FICTIONAL changed executable")
    with pytest.raises(c.ControllerError):
        x.verify()


def test_registration_digest_inside_ROOT_never_selects_or_authenticates_registry(system):
    x = system
    x.go["effective_epoch"]["controller_context"]["registration_sha256"] = "0" * 64
    x.bind_root()
    with pytest.raises(c.ControllerError):
        x.verify()
    assert x.calls[0][0] == b.history_url()


@pytest.mark.parametrize("mutation", ["overwrite", "modified", "extra-file", "wrong-blob"])
def test_fixed_registry_create_only_complete_filegraph(system, mutation):
    x = system
    if mutation == "overwrite":
        x.api.data[b.history_url()].append(dict(sha=old.D))
    else:
        files = x.api.data[c.API + "/commits/" + x.public_commit]["files"]
        if mutation == "modified":
            files[0]["status"] = "modified"
        elif mutation == "extra-file":
            files.append(dict(filename="unreviewed.txt", status="added", sha="a" * 40))
        else:
            files[0]["sha"] = "0" * 40
    with pytest.raises(b.BootstrapError):
        x.verify()


@pytest.mark.parametrize("target", ["owner-run", "owner-job", "registry"])
def test_bootstrap_live_rechecks_reject_restart_or_rewrite(system, target):
    x = system
    if target == "owner-run":
        x.hooks[c.run_url("400")] = lambda v, n: dict(v, run_attempt=2) if n > 1 else v
    elif target == "owner-job":
        def change(value, n):
            if n > 1:
                value["jobs"][1]["id"] = 999
            return value
        x.hooks[c.jobs_url("400")] = change
    else:
        x.hooks[b.history_url()] = lambda v, n: [dict(sha=old.D)] if n > 1 else v
    with pytest.raises(c.ControllerError):
        x.verify()


def test_closed_SAFE_SEAL_rejects_private_unknown_fields_and_extra_ZIP_files(system):
    x = system
    x.native["private_root"] = "not permitted"
    x.publish()
    with pytest.raises(b.BootstrapError):
        x.verify()
    del x.native["private_root"]
    x.publish(extra_zip=("raw-request.json", "fictional blocked"))
    with pytest.raises(b.BootstrapError):
        x.verify()


def test_native_schedule_parent_not_workflow_dispatch_and_does_not_wait(system):
    x = system
    x.api.data[c.run_url("100")].update(status="in_progress", conclusion=None, updated_at=old.PVERIFIED)
    x.api.data[c.jobs_url("100")]["jobs"][0].update(status="in_progress", conclusion=None, completed_at=None)
    env = dict(x.env, GITHUB_RUN_ID="100", GITHUB_EVENT_NAME="schedule", GITHUB_SHA=old.A, GITHUB_WORKFLOW_SHA=old.A,
        GITHUB_WORKFLOW_REF=c.REPO + "/" + c.WORKFLOW + "@refs/heads/main", GITHUB_JOB="lab",
        GITHUB_ACTOR=c.OWNER["login"], GITHUB_ACTOR_ID=str(c.OWNER["id"]))
    event = c.canonical(dict(repository=dict(full_name=c.REPO), schedule=c.CADENCE["cron"]))
    result = b.authorize_parent(env, x.parent_source, metadata_get=x.get, event_bytes=event,
        clock=lambda: c.utc(old.PVERIFIED), read_head=x.read_head)
    assert result.proof.document["scheduled_parent"]["event"] == "schedule"
    assert result.proof.document["next_action"] == c.RETURN_RULE
    assert not any("/300" in u or "dispatches" in u for u, _ in x.calls)
    assert len(x.calls) <= 32


def test_current_client_proof_cannot_authorize_old_or_different_client(system):
    x = system
    proof = x.verify()
    client = SimpleNamespace(run_id="300", source_sha=old.B, job=dict(api_job_id=31, job_id=x.env["GITHUB_JOB"],
        execution_lane="github_actions", run_authenticated=True, event_name="workflow_dispatch", workflow_sha=old.B,
        workflow_ref=x.env["GITHUB_WORKFLOW_REF"]))
    assert b.authorize_client(proof, client, x.env, x.raw) is proof
    for field, value in (("run_id", "400"), ("source_sha", old.A)):
        broken = deepcopy(client)
        setattr(broken, field, value)
        with pytest.raises(b.BootstrapError):
            b.authorize_client(proof, broken, x.env, x.raw)
    with pytest.raises(b.BootstrapError):
        b.authorize_client(proof.document, client, x.env, x.raw)


def test_shared_GET_cap_includes_failed_attempts_and_no_secret_read_for_injected_IO():
    class Env:
        def get(self, name):
            pytest.fail("NO_CREDENTIAL_READ_WITH_INJECTED_TRANSPORT")
    client = b.Metadata(Env(), lambda *_: c.Reply(500, b"fictional"))
    for _ in range(32):
        with pytest.raises(b.BootstrapError):
            client(b.history_url(), 1024)
    assert len(client.calls) == 32
    with pytest.raises(b.BootstrapError):
        client(b.history_url(), 1024)


@pytest.mark.parametrize("url", [c.API + "/releases/1", c.API + "/actions/workflows/lab.yml/dispatches",
    "https://example.invalid/", c.API + "/contents/state/controller-v1/../secret?ref=lab-state"])
def test_no_private_provider_POST_arbitrary_or_traversal_route(url):
    api = b.Metadata({}, lambda *_: pytest.fail("ROUTE_MUST_FAIL_BEFORE_IO"))
    with pytest.raises(b.BootstrapError):
        api(url, 100)


@pytest.mark.parametrize("literal", [
    "state/controller-v1/bootstrap-v2-20261026-discovery.json",
    "state/controller-v1/bootstrap-v2-20261026-retained-epoch.json",
    "state/controller-v1/bootstrap-v2-20261027-pending-posts.json",
    "state/controller-v1/bootstrap-v2-20261027-first-primary.json",
    "state/controller-v1/bootstrap-v2-20261027-fresh-first-primary.json",
    "state/controller-v1/bootstrap-v2-20261027-metadata-phases.json",
    "state/controller-v1/bootstrap-v2-20261027-archive-recovery.json",
    "state/controller-v1/bootstrap-v2-20261028-history-runtime.json",
    "state/controller-v1/bootstrap-v2-20261028-prior-pending-read.json",
    "state/controller-v1/bootstrap-v2-20261031-mae-display-read.json",
    "state/controller-v1/bootstrap-v2-20261101-mae-history-read.json",
    "state/controller-v1/bootstrap-v2-20261101-mae-pinned-history.json",
    "state/controller-v1/bootstrap-v2-20261101-mae-capacity-phase.json",
])
def test_issued_registration_routes_are_literal_and_commit_bound(literal):
    calls = []
    def get(url, cap):
        calls.append((url, cap))
        return c.Reply(200, b"[]")
    api = b.Metadata({}, get)
    assert api.get(c.contents_url(literal, old.A), 17) == []
    assert len(calls) == 1
    for path, ref in ((literal, "lab-state"),
            (literal.replace("20261026", "20261025").replace("20261027", "20261025").replace("20261028", "20261025").replace("20261031", "20261025").replace("20261101", "20261025"), old.A),
            (literal.replace(".json", "-extra.json"), old.A),
            (literal.replace("bootstrap-v2", "../bootstrap-v2"), old.A)):
        with pytest.raises(b.BootstrapError, match="BOOTSTRAP_FIXED_GET_ROUTE_OR_SHARED_CAP"):
            api(c.contents_url(path, ref), 17)
    assert len(calls) == 1


@pytest.fixture
def large_pending_metadata(locator_system):
    from nfl_lab import audit_weekly_template_v1 as t
    records=[]
    for n in range(16):
        digest=hashlib.sha256(('independent-pending-'+str(n)).encode()).hexdigest()
        records.append(dict(schema_version='weekly-private-POST-reservation-v2',key='asset:blob-'+digest+'.bin',
            bytes=n+1,sha256=digest,name='blob-'+digest+'.bin'))
    x=locator_system
    return dict(schema_version=t.PENDING_RECOVERY,pending_reservations=sorted(records,key=lambda r:r['key']),
        handoffs=[dict(schema_version='audit-weekly-hosted-v2-failure-handoff',binding=deepcopy(x.package['binding']),
            descriptor=deepcopy(x.template_seal['descriptor']),root_go_sha256='a'*64)])


def test_large_pending_metadata_transport_preserves_original_bytes_and_records(large_pending_metadata):
    from nfl_lab import audit_weekly_template_v1 as t
    value=large_pending_metadata
    original=json.dumps(value,sort_keys=True,separators=(',',':')).encode()
    packed=t.pending_recovery_envelope(value)
    assert packed['schema_version']==t.PENDING_RECOVERY_ENVELOPE
    assert packed['body_bytes']==len(original) and packed['body_sha256']==hashlib.sha256(original).hexdigest()
    assert gzip.decompress(base64.b64decode(packed['gzip_base64']))==original
    assert t.validate_pending_recovery(packed)==value and t.validate_pending_recovery(value)==value
    assert len(c.canonical(packed))<len(original)
    assert json.dumps(value,sort_keys=True,separators=(',',':')).encode()==original
    assert t.pending_recovery_envelope(dict(schema_version=t.PENDING_RECOVERY,handoffs=[],pending_reservations=[]))==dict(
        schema_version=t.PENDING_RECOVERY,handoffs=[],pending_reservations=[])


@pytest.mark.parametrize('damage',['digest','boolean_bytes','truncated','trailing_member','extra','nested','noncanonical','unknown_plain_field'])
def test_pending_metadata_transport_rejects_corruption_or_hidden_scope(large_pending_metadata,damage):
    from nfl_lab import audit_weekly_template_v1 as t
    encoded=t.pending_recovery_envelope(large_pending_metadata)
    if damage=='digest':encoded['body_sha256']='0'*64
    elif damage=='boolean_bytes':encoded['body_bytes']=True
    elif damage=='truncated':encoded['gzip_base64']=base64.b64encode(base64.b64decode(encoded['gzip_base64'])[:-1]).decode()
    elif damage=='trailing_member':encoded['gzip_base64']=base64.b64encode(base64.b64decode(encoded['gzip_base64'])+gzip.compress(b'',mtime=0)).decode()
    elif damage=='extra':encoded['hidden_scope']=True
    else:
        value=encoded if damage=='nested' else deepcopy(large_pending_metadata)
        if damage=='unknown_plain_field':value['forecast_rows']=[{'never_allowed':True}]
        raw=json.dumps(value,sort_keys=True,separators=(',',':')).encode()+(b'\n' if damage=='noncanonical' else b'')
        encoded=dict(schema_version=t.PENDING_RECOVERY_ENVELOPE,body_sha256=hashlib.sha256(raw).hexdigest(),
            body_bytes=len(raw),gzip_base64=base64.b64encode(gzip.compress(raw,mtime=0)).decode())
    with pytest.raises(t.TemplateError):t.validate_pending_recovery(encoded)


def test_actual_network_adapter_timeout_no_redirect_and_bounded_read(monkeypatch):
    observed = {}
    class Response:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *_): return None
        def read(self, amount):
            observed["amount"] = amount
            return b"[]"
    class Opener:
        def open(self, request, *, timeout):
            observed.update(timeout=timeout, method=request.method, url=request.full_url)
            return Response()
    monkeypatch.setattr(b, "build_opener", lambda handler: Opener())
    api = b.Metadata(dict(GITHUB_TOKEN="ghs_FICTIONAL"))
    assert api.get(b.history_url(), 17) == []
    assert 0 < observed["timeout"] <= 10 and observed["amount"] == 18 and observed["method"] == "GET"
    with pytest.raises(b.BootstrapError):
        b._NoRedirect().redirect_request(None)


def test_tool_is_offline_explicitly_unregistered_not_activation(capsys):
    assert cli.main(["template"]) == 0
    document = c.decode(capsys.readouterr().out.encode())
    assert document["state"] == "UNREGISTERED_PARENT_WIRING_REQUIRED"
    assert document["limits"]["HTTP_calls"] == 32 and document["activation_authorized"] is False
    assert cli.main(["execute"]) == 2


def test_static_policy_original_clock_exact_bytes_authenticated_before_extension(system):
    x = system
    proof = x.verify()
    result = b.authorize_policy(proof, x.raw, x.static_policy)
    assert result["registered_at_utc"] == "2026-10-25T11:00:00Z"
    assert c.utc(result["registered_at_utc"]) < c.utc(x.go["issued_at_utc"])
    with pytest.raises(b.BootstrapError):
        b.authorize_policy(proof, x.raw, x.static_policy + b" ")
    with pytest.raises(b.BootstrapError):
        b.authorize_policy(proof.document, x.raw, x.static_policy)


def test_static_policy_cannot_use_frozen_child_proof_without_live_bootstrap(system):
    x = system
    proof = c.verify_child(x.reg, sealed_sha256=x.seal, root_bytes=x.raw, event_bytes=x.event,
        env=x.env, source_root=x.child_source, metadata_get=x.api, clock=lambda: old.AT, read_head=x.read_head)
    with pytest.raises(b.BootstrapError, match="EXTERNALLY_VERIFIED_BOOTSTRAP_POLICY_BINDING_REQUIRED"):
        b.authorize_policy(proof, x.raw, x.static_policy)


def owner(x):
    x.go["effective_epoch"]["controller_context"] = None
    x.bind_root()
    x.env.update(GITHUB_ACTOR=c.OWNER["login"], GITHUB_ACTOR_ID=str(c.OWNER["id"]))
    x.api.data[c.run_url("300")].update(actor=deepcopy(c.OWNER), triggering_actor=deepcopy(c.OWNER))
    return b.authorize_owner(x.env, x.child_source, x.raw, metadata_get=x.get, event_bytes=x.event,
        clock=lambda: old.AT, read_head=x.read_head)


def test_genuine_manual_owner_recurring_smoke_uses_prior_capture_no_fake_parent(system):
    x = system
    proof = owner(x)
    assert type(proof) is b.Owner and proof.document["actor"] == c.OWNER
    assert proof.document["scheduled_parent"] is None
    assert not any("/100" in u or "dispatches" in u for u, _ in x.calls)
    assert b.authorize_policy(proof, x.raw, x.static_policy)["policy_sha256"] == c.sha(x.static_policy)
    with pytest.raises(b.BootstrapError):
        pickle.dumps(proof)


def test_versioned_first_future_marker_uses_actual_owner_bootstrap_without_parent(locator_system):
    from nfl_lab import audit_weekly_template_v1 as template
    x=locator_system
    x.go['qualified_runtime']=deepcopy(x.package)
    x.go['effective_epoch'].update(schema_version=template.RECURRING_V5,previous_checkpoint=None,
        pending_post_recovery=dict(schema_version=template.PENDING_RECOVERY,handoffs=[],pending_reservations=[]),
        plan=dict(kind='FUTURE_CAPABLE',season=2026,week=8,deadline_utc='2026-10-29T18:15:00Z',
            calendar_sha256='a'*64,game_cutoffs={'fictional-week8':'2026-10-29T18:15:00Z'}),
        controller_context=dict(schema_version=template.FIRST_PRIMARY,retained_epoch_sha256='1'*64,
            retained_choice_sha256='2'*64,retained_root_go_sha256='3'*64,
            claim_binding_sha256=template.digest(x.go['qualified_runtime']['binding'])))
    x.bind_root()
    x.env.update(GITHUB_ACTOR=c.OWNER['login'],GITHUB_ACTOR_ID=str(c.OWNER['id']))
    x.api.data[c.run_url('300')].update(actor=deepcopy(c.OWNER),triggering_actor=deepcopy(c.OWNER))
    proof=b.authorize_owner(x.env,x.child_source,x.raw,metadata_get=x.get,event_bytes=x.event,
        clock=lambda:old.AT,read_head=x.read_head,registry_version=2)
    assert type(proof) is b.Owner and proof.document['scheduled_parent'] is None
    with pytest.raises(b.BootstrapError,match='OWNER_FIRST_PRIMARY_CANNOT_BE_SCHEDULED'):
        b._recurring(x.raw,bot=True)


def test_failed_first_recovery_uses_genuine_manual_owner_bootstrap_only(locator_system):
    from nfl_lab import audit_weekly_template_v1 as t
    x=locator_system;x.go['qualified_runtime']=deepcopy(x.package)
    binding=x.go['qualified_runtime']['binding']
    payload=dict(schema_version='weekly-private-payload-v2',payload_kind='runtime_manifest',format='gzip',
        bytes=3,sha256='8'*64,source_policy_sha256=t.POLICY_SHA)
    entry=dict(schema_version='weekly-private-restore-manifest-v2',payload=payload,payload_asset_id=51,
        payload_name='blob-'+'8'*64+'.bin',producer_process='9'*64,binding_sha256=t.digest(binding),writer_run_id='200')
    handoff=dict(schema_version='audit-weekly-hosted-v2-failure-handoff',binding=binding,root_go_sha256='0'*64,
        descriptor=dict(entry=entry,manifest_asset_id=52,manifest_sha256=t.digest(entry),manifest_bytes=len(c.canonical(entry))))
    x.go['effective_epoch'].update(schema_version=t.RECURRING_V5,previous_checkpoint=None,
        pending_post_recovery=dict(schema_version=t.PENDING_RECOVERY,handoffs=[handoff],pending_reservations=[]),
        plan=dict(kind='FUTURE_CAPABLE',season=2026,week=8,deadline_utc='2026-10-29T18:15:00Z',calendar_sha256='a'*64,
            game_cutoffs={f'fictional-{n}':'2026-10-29T18:15:00Z' for n in range(14)}),
        controller_context=dict(schema_version=t.FAILED_FIRST_RECOVERY,retained_epoch_sha256='1'*64,
            retained_choice_sha256='2'*64,retained_root_go_sha256='3'*64,claim_binding_sha256=t.digest(binding),
            failed_root_go_sha256='0'*64,old_week8_choice_body_missing=True,old_forecast_bodies_missing=True))
    x.bind_root();x.env.update(GITHUB_ACTOR=c.OWNER['login'],GITHUB_ACTOR_ID=str(c.OWNER['id']))
    x.api.data[c.run_url('300')].update(actor=deepcopy(c.OWNER),triggering_actor=deepcopy(c.OWNER))
    proof=b.authorize_owner(x.env,x.child_source,x.raw,metadata_get=x.get,event_bytes=x.event,
        clock=lambda:old.AT,read_head=x.read_head,registry_version=2)
    assert type(proof) is b.Owner and proof.document['scheduled_parent'] is None
    with pytest.raises(b.BootstrapError,match='CANNOT_BE_SCHEDULED'):b._recurring(x.raw,bot=True)
    assert b.LOCATOR_REGISTRY_PATH=='state/controller-v1/bootstrap-v2-20261101-mae-capacity-phase.json'


def test_first_future_marker_does_not_make_an_unversioned_manual_context_valid(system):
    x=system;x.go['effective_epoch']['controller_context']={'schema_version':'UNREGISTERED_STARTUP'}
    x.bind_root()
    with pytest.raises(b.BootstrapError,match='RECURRING_CONTEXT_AND_PRIOR_CAPTURE_LOCATOR'):
        b._recurring(x.raw,bot=False)


@pytest.mark.parametrize("field", ["feed_sha256", "receipt_sha256"])
def test_owner_smoke_cannot_self_assert_unqualified_prior_capture(system, field):
    x = system
    x.go["effective_epoch"]["previous_capture"][field] = "0" * 64
    with pytest.raises(b.BootstrapError, match="OWNER_SMOKE_REQUIRES_EXACT_SEALED_QUALIFIED_PRIOR_CAPTURE"):
        owner(x)


def test_manual_owner_proof_rejects_actual_bot_or_pending_native_registration(system):
    x = system
    x.hooks[c.run_url("300")] = lambda value, _: dict(value, actor=deepcopy(c.BOT))
    with pytest.raises(c.ControllerError):
        owner(x)


def test_initial_NONE_branch_is_never_silently_converted_to_recurring(system):
    x = system
    x.go["effective_epoch"] = None
    x.bind_root()
    with pytest.raises(b.BootstrapError):
        x.verify()


@pytest.mark.parametrize("side", ["prefix", "suffix"])
def test_public_SAFE_SEAL_cannot_carry_unparsed_opaque_private_payload(system, side):
    x = system
    hidden = b"FICTIONAL unqualified request corpus"
    packed = hidden + x.packed if side == "prefix" else x.packed + hidden
    with pytest.raises(b.BootstrapError):
        b.safe_seal(packed)


def test_shared_native_wall_budget_failure_precedes_callback(monkeypatch):
    api = b.Metadata({}, lambda *_: pytest.fail("EXPIRED_METADATA_CALLBACK_FORBIDDEN"))
    monkeypatch.setattr(b.time, "monotonic", lambda: api.started + 181)
    with pytest.raises(b.BootstrapError, match="BOOTSTRAP_SHARED_NATIVE_BUDGET"):
        api(b.history_url(), 100)


def test_fresh_import_is_cold_no_numerics_credential_or_network_IO(tmp_path):
    import subprocess
    import sys
    root = str(Path(__file__).resolve().parents[1])
    script = """import os, socket, sys
sys.path.insert(0, sys.argv[1])
def forbidden(*a, **kw): raise AssertionError('UNAUTHORIZED_IMPORT_IO')
os.getenv = forbidden
socket.socket.connect = forbidden
from nfl_lab import audit_weekly_controller_bootstrap_v1 as b
assert 'numpy' not in sys.modules and 'scipy' not in sys.modules
assert b.integration_contract()['activation_authorized'] is False
"""
    result = subprocess.run([sys.executable, "-B", "-c", script, root], capture_output=True, text=True, timeout=10,
        env={"PYTHONDONTWRITEBYTECODE": "1"}, cwd=tmp_path)
    assert result.returncode == 0, result.stderr


@pytest.fixture
def locator_system(system):
    """Actual native metadata schemas; fictional IDs/bodies, no private IO."""
    from nfl_lab import audit_weekly_template_v1 as t, private_draft_store as s
    from test_owner_private_bootstrap import qualification
    x = system
    for role, root in (("parent", x.parent_source), ("producer", x.child_source)):
        required = b.PARENT_EXECUTABLE_PINS if role == "parent" else b.SHARED_EXECUTABLE_PINS
        for name in sorted(required):
            path = root / name; path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                path.write_bytes(("FICTIONAL pinned shared helper " + name).encode())
            x.p[role]["code_pins"][name] = c.sha(path.read_bytes())
    x.p["registered_at_utc"] = "2026-10-25T12:02:15Z"
    x.reg = c.canonical(x.p); x.seal = c.sha(x.reg)
    x.go["code_pins"] = deepcopy(x.p["producer"]["code_pins"])
    x.go["effective_epoch"]["controller_context"]["registration_sha256"] = x.seal
    x.bind_root()
    x.claim.update(registration_sha256=x.seal, root_go_sha256=c.sha(x.raw))
    x.api.data[c.contents_url(x.claim_path, old.D)] = old.content(x.claim_path, c.canonical(x.claim))
    x.api.data[c.API + "/commits/" + old.D]["files"][0]["sha"] = c.blob_sha(c.canonical(x.claim))
    binding = dict(schema_version="weekly-private-draft-binding-v2", repository=c.REPO, runtime_id="c" * 32,
        origin_run_id="40000000001", release_id=91, tag_name="weekly-private-runtime-v2-" + "c" * 32,
        canary_asset_id=100, canary_name="canary-" + s.sha(s.probe.fixture("40000000001")) + ".txt",
        canary_sha256=s.sha(s.probe.fixture("40000000001")), canary_bytes=117,
        browser_tag="untagged-" + "b" * 20, config_sha256=s.config_sha())
    q = qualification(binding)
    before, read = q["before_proof"], q["read_proof"]
    stamp = datetime(2020, 1, 1, tzinfo=timezone.utc)
    for i, proof in enumerate((before, read, q)):
        proof["started_at_utc"] = (stamp + timedelta(minutes=i * 2)).isoformat()
        proof["created_at_utc"] = (stamp + timedelta(minutes=i * 2, seconds=30)).isoformat()
    read["before_sha256"] = s.sha(s.canonical(before))
    q.update(before_sha256=s.sha(s.canonical(before)), read_sha256=s.sha(s.canonical(read)),
        before_completed_at_utc=before["created_at_utc"], read_completed_at_utc=read["created_at_utc"])
    quota = dict(schema_version="audit-private-rotation-v1-quota-reservation", global_cap_bytes=512 << 20,
        reserved_before_bytes=32 << 20, new_runtime_reserved_bytes=32 << 20, reserved_after_bytes=64 << 20,
        existing_draft_runtimes=1, pending_unlocated_runtimes=0, pending_records=0, charged_existing_bytes=117,
        charged_existing_assets=1, inventory_sha256=old.h("original quota inventory"),
        pending_census_sha256=s.sha(s.canonical(dict(reservations=[]))), new_runtime_id=binding["runtime_id"],
        old_assets_deleted=0, metadata_only=True)
    x.package = dict(schema_version="audit-private-rotation-v1-qualified-runtime", run_id=q["run_id"], source_sha=q["source_sha"],
        runtime_id=binding["runtime_id"], binding=binding, qualification=q, quota_reservation=quota, runtime_reserved_bytes=32 << 20,
        root_go_sha256=old.h("original rotation Root"), private_payload_bytes=0, private_durability_qualified=False,
        strict_v1_unchanged="INCONCLUSIVE")
    root = {key: None for key in t.ROOT_KEYS}
    slots = [dict(target=target, family=family, method_id=method, procedure_version="1" * 64, model_sha256="2" * 64,
        manifest_sha256="3" * 64, transport_manifest_sha256="4" * 64) for target, family, method in t.JOBS]
    root.update(schema_version="audit-weekly-hosted-v2-root-GO", approved=False, repository=c.REPO, mode=c.MODE,
        source_sha=old.B, code_pins=deepcopy(x.p["producer"]["code_pins"]), single_writer_group=c.GROUP,
        workflow_ref=x.go["workflow_ref"], retained_registration=dict(schema_version="audit-count-retained-v1-registration",
            approved=True, maximum_new_fits=0, public_release=False, origin=dict(replay_catalog=dict(slots=slots))))
    x.prepared = t.prepare(dict(schema_version=t.VERSION + "-static", source_sha=old.B,
        code_pins=deepcopy(x.p["producer"]["code_pins"]), readiness=deepcopy(x.p["readiness"]), root_template=root))
    payload = dict(schema_version="weekly-private-payload-v2", payload_kind="runtime_manifest", format="gzip",
        bytes=len(x.prepared.body), sha256=s.sha(x.prepared.body), source_policy_sha256=t.POLICY_SHA)
    entry = dict(schema_version="weekly-private-restore-manifest-v2", payload=payload, payload_asset_id=701,
        payload_name="blob-" + payload["sha256"] + ".bin", producer_process=x.native["writer"]["process_identity"],
        binding_sha256=s.sha(s.canonical(binding)), writer_run_id="400")
    descriptor = dict(entry=entry, manifest_asset_id=702, manifest_sha256=s.sha(s.canonical(entry)), manifest_bytes=len(s.canonical(entry)))
    def identity(which):
        n = x.native[which]
        return dict(execution_lane="github_actions", repository=c.REPO, source_sha=old.B, run_id="400", run_attempt=1,
            process_identity=n["process_identity"], job_id=n["job_id"], api_job_id=n["api_job_id"], permission="write",
            workflow_ref=x.go["workflow_ref"])
    owner_root = old.h("EXACT ORIGINAL owner registration Root input")
    original = dict(schema_version=t.VERSION + "-appended", repository=c.REPO, binding=binding, descriptor=descriptor,
        template_sha256=s.sha(x.prepared.plain), template_bytes=len(x.prepared.plain), writer=identity("writer"),
        root_go_sha256=owner_root, appended_at_utc="2026-10-25T12:00:10Z")
    x.template_seal = dict(original, schema_version=t.VERSION + "-seal", reader=identity("reader"),
        reader_proof_sha256=old.h("original unmodified native reader receipt"), verified_at_utc="2026-10-25T12:01:10Z")
    x.locators = dict(schema_version=b.LOCATOR_VERSION + "-locator-registration", repository=c.REPO,
        registered_at_utc=x.p["registered_at_utc"], owner_root_go_sha256=owner_root,
        owner_root_issued_at_utc="2026-10-25T11:00:00Z", template_seal=x.template_seal, qualified_runtime_package=x.package)
    summary = dict(schema_version=b.LOCATOR_VERSION + "-private-template-descriptor", template_sha256=s.sha(x.prepared.plain),
        template_bytes=len(x.prepared.plain), private_descriptor_sha256=s.sha(s.canonical(descriptor)),
        storage_binding_sha256=s.sha(s.canonical(binding)))
    x.native.update(schema_version=b.LOCATOR_VERSION + "-native-safe-seal", registration_sha256=x.seal,
        registered_at_utc=x.p["registered_at_utc"], template_descriptor=summary, owner_root_go_sha256=owner_root,
        owner_root_issued_at_utc=x.locators["owner_root_issued_at_utc"], code_pins_sha256=c.digest(x.p["producer"]["code_pins"]))
    for which in ("writer", "reader"):
        x.native[which].update({key: value for key, value in summary.items() if key != "schema_version"})
    x.native["writer"]["receipt_sha256"] = s.sha(s.canonical(original))
    x.native["reader"]["receipt_sha256"] = x.template_seal["reader_proof_sha256"]
    x.api.data[x.artifact_url]["name"] = "controller-root-safe-seal-v2-400"
    def publish(*, bind_locator=True, artifact=True):
        if bind_locator:
            x.native["locator_registration_sha256"] = c.digest(x.locators)
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("SAFE_SEAL.json", c.canonical(x.native))
        packed = stream.getvalue()
        x.locator_record = dict(schema_version=b.LOCATOR_VERSION + "-public-seal", repository=c.REPO,
            registration_base64=base64.b64encode(x.reg).decode(), native_artifact_zip_base64=base64.b64encode(packed).decode(),
            artifact_id=51, locator_registration=deepcopy(x.locators))
        body = c.canonical(x.locator_record)
        d = x.api.data
        d[b.history_url(registry_version=2)] = [dict(sha=x.public_commit)]
        d[c.contents_url(b.LOCATOR_REGISTRY_PATH, x.public_commit)] = old.content(b.LOCATOR_REGISTRY_PATH, body)
        d[c.API + "/commits/" + x.public_commit] = dict(sha=x.public_commit, parents=[dict(sha="e" * 40)],
            committer=deepcopy(c.BOT), files=[dict(filename=b.LOCATOR_REGISTRY_PATH, status="added", sha=c.blob_sha(body))])
        if artifact:
            d[x.artifact_url].update(digest="sha256:" + c.sha(packed), size_in_bytes=len(packed))
    x.publish_locator = publish; publish()
    x.load_locator = lambda: b.load_seal(x.env, x.child_source, metadata_get=x.get, clock=lambda:old.AT,
        read_head=x.read_head, registry_version=2)
    x.verify_locator = lambda: b.authorize_child(x.env, x.child_source, x.raw, metadata_get=x.get,
        event_bytes=x.event, clock=lambda:old.AT, read_head=x.read_head, registry_version=2)
    return x


def test_v2_owner_cleared_exact_locators_after_minting_not_backdated(locator_system):
    x = locator_system; seal = x.load_locator()
    loc = seal.locators
    assert len(x.calls) == 10 and seal.registry_version == 2
    assert loc == x.locators and loc["template_seal"]["descriptor"]["manifest_asset_id"] == 702
    assert c.utc(loc["registered_at_utc"]) > c.utc(x.native["reader"]["completed_at_utc"])
    assert seal.document["owner_root_go_sha256"] == x.template_seal["root_go_sha256"]
    assert seal.document["original_owner_root_issued_at_utc"] == "2026-10-25T11:00:00Z"
    assert loc["qualified_runtime_package"]["source_sha"] == old.A
    assert x.prepared.plain not in c.canonical(x.locator_record)
    assert b.verify_locator_registration(seal, seal.locator_registration_bytes) == x.locators
    assert b.verify_template_payload(seal, x.prepared.body).document == x.prepared.document
    assert seal.document["private_reads"] == 0


def test_v2_child_unchanged_strict_controller_full_thirty_GETs(locator_system):
    x = locator_system; proof = x.verify_locator()
    assert type(proof) is c.Proof and len(x.calls) == 30
    assert proof.bootstrap_seal.locators == x.locators
    assert proof.document["actor"] == c.BOT and proof.document["parent_actor"] == c.OWNER


def test_old_v1_cannot_silently_acquire_v2_locator_authority(system):
    seal = system.load()
    with pytest.raises(b.BootstrapError, match="LIVE_EXPLICIT_V2_LOCATOR_SEAL_REQUIRED"):
        _ = seal.locators


@pytest.mark.parametrize("version", [None, "2", True, 0, 3])
def test_registry_version_is_closed_and_explicit(version):
    with pytest.raises(b.BootstrapError): b.history_url(registry_version=version)


def test_locator_changed_without_real_SAFE_artifact_binding_rejected(locator_system):
    x = locator_system
    x.locators["template_seal"]["descriptor"]["manifest_asset_id"] += 1
    x.publish_locator(bind_locator=False)
    with pytest.raises(b.BootstrapError, match="EXACT_FINAL_OWNER_CLEARED_LOCATOR_REGISTRATION"):
        x.load_locator()


@pytest.mark.parametrize("where,field,value", [("root", "token", "FICTIONAL secret denied"),
    ("root", "root_template", {}), ("package", "forecast_rows", []), ("descriptor", "body_base64", "e30="),
    ("binding", "private_path", "/fictional/forbidden"), ("proof", "outcomes", [])])
def test_v2_closed_public_metadata_refuses_any_bodies_paths_or_unknown_fields(locator_system, where, field, value):
    from nfl_lab import audit_weekly_template_v1 as t, private_draft_store as s
    x = locator_system
    targets = dict(root=x.locators, package=x.package, descriptor=x.template_seal["descriptor"],
        binding=x.template_seal["binding"], proof=x.package["qualification"])
    targets[where][field] = value; x.publish_locator()
    with pytest.raises((b.BootstrapError, t.TemplateError, s.StoreError)): x.load_locator()


def test_rehashed_native_descriptor_does_not_rewrite_original_writer_proof(locator_system):
    x = locator_system
    x.template_seal["descriptor"]["manifest_asset_id"] += 1
    from nfl_lab import private_draft_store as s
    x.native["template_descriptor"]["private_descriptor_sha256"] = s.sha(s.canonical(x.template_seal["descriptor"]))
    for which in ("writer", "reader"):
        x.native[which]["private_descriptor_sha256"] = x.native["template_descriptor"]["private_descriptor_sha256"]
    x.publish_locator()
    with pytest.raises(b.BootstrapError, match="UNCHANGED_ORIGINAL_WRITER_AND_READER_PROOFS_BEFORE_FINAL_SEAL"):
        x.load_locator()


def test_sealer_cannot_pretend_original_reader_knew_future_root_or_ids(locator_system):
    x = locator_system
    x.locators["owner_root_go_sha256"] = old.h("rewritten original Root")
    x.native["owner_root_go_sha256"] = x.locators["owner_root_go_sha256"]
    x.publish_locator()
    with pytest.raises(b.BootstrapError, match="ORIGINAL_TEMPLATE_OWNER_ROOT_AND_LITERAL_SOURCE"):
        x.load_locator()


@pytest.mark.parametrize("clock", ["2026-10-25T11:00:00Z", "2026-10-25T12:03:00Z"])
def test_final_registration_clock_is_inside_real_sealer_stage(locator_system, clock):
    x = locator_system
    x.native["registered_at_utc"] = clock
    # Rebuild the controller bytes as well: a self-consistent backdated clock
    # still cannot become an authentic final sealing clock.
    x.p["registered_at_utc"] = clock; x.reg = c.canonical(x.p)
    x.native["registration_sha256"] = c.sha(x.reg); x.locators["registered_at_utc"] = clock
    x.publish_locator()
    with pytest.raises(b.BootstrapError, match="ACTUAL_FINAL_SEALER_REGISTRATION_CLOCK_REQUIRED"):
        x.load_locator()


def test_returned_locator_copies_cannot_mutate_live_seal(locator_system):
    seal = locator_system.load_locator()
    copy = seal.locators; copy["template_seal"]["descriptor"]["manifest_asset_id"] = 999
    assert seal.locators["template_seal"]["descriptor"]["manifest_asset_id"] == 702
    with pytest.raises(b.BootstrapError): b.verify_locator_registration(seal, seal.locator_registration_bytes + b" ")
    with pytest.raises(b.BootstrapError): b.verify_template_payload(seal, locator_system.prepared.body + b" ")
    with pytest.raises(b.BootstrapError): pickle.dumps(seal)


def test_existing_native_schedule_ParentGETClient_receives_live_parent_not_fake_dispatch(locator_system, tmp_path, monkeypatch):
    from nfl_lab import audit_weekly_template_v1 as t
    x = locator_system
    x.api.data[c.run_url("100")].update(status="in_progress", conclusion=None, updated_at=old.PVERIFIED)
    x.api.data[c.jobs_url("100")]["jobs"][0].update(status="in_progress", conclusion=None, completed_at=None)
    env = dict(x.env, GITHUB_RUN_ID="100", GITHUB_EVENT_NAME="schedule", GITHUB_SHA=old.A, GITHUB_WORKFLOW_SHA=old.A,
        GITHUB_WORKFLOW_REF=c.REPO + "/" + c.WORKFLOW + "@refs/heads/main", GITHUB_JOB="lab",
        GITHUB_ACTOR=c.OWNER["login"], GITHUB_ACTOR_ID=str(c.OWNER["id"]))
    clock = lambda:c.utc(old.PVERIFIED)
    event = c.canonical(dict(repository=dict(full_name=c.REPO), schedule=c.CADENCE["cron"]))
    parent = b.authorize_parent(env, x.parent_source, metadata_get=x.get, event_bytes=event,
        clock=clock, read_head=x.read_head, registry_version=2)
    journal = tmp_path / "private-parent-journal"; journal.mkdir(mode=0o700)
    client = t.ParentGETClient("ghs_FICTIONAL", seal_sha256=c.digest(parent.locators["template_seal"]),
        registration_sha256=parent.seal.registration_sha256, parent_run_id="100", parent_job_id="lab",
        authenticate=lambda sha:b.authorize_parent_get_client(parent, client, sha, clock=clock),
        journal=journal, transport=lambda *_:pytest.fail("PURE_BRIDGE_DOES_NOT_READ_PRIVATE_BYTES"))
    monkeypatch.setattr(t, "now", clock)
    client.guard()
    assert client.calls == 0 and client.authentication_calls == 1
    assert parent.proof.document["scheduled_parent"]["event"] == "schedule"
    assert not hasattr(client, "job")
    with pytest.raises(b.BootstrapError): b.authorize_parent_get_client(parent, client, "0" * 64, clock=clock)
    with pytest.raises(b.BootstrapError):
        b.authorize_parent_get_client(parent, client, client.seal_sha256, clock=lambda:c.utc("2026-10-25T13:40:00Z"))


@pytest.mark.parametrize("change", [dict(expired=True), dict(digest="sha256:" + "0" * 64)])
def test_v2_locators_still_require_unexpired_actual_owner_artifact(locator_system, change):
    x = locator_system; x.api.data[x.artifact_url].update(change)
    with pytest.raises(b.BootstrapError): x.load_locator()


def test_locator_contract_is_explicit_metadata_only():
    value = b.locator_contract()
    assert value["registry_path"] != b.REGISTRY_PATH and value["registry_version"] == 2
    assert value["private_reads"] == value["POSTs"] == value["fits"] == 0
    assert value["activation_authorized"] is value["public_root"] is False


@pytest.mark.parametrize('tail',[
    'contents/state/controller-v1/bootstrap-v2-20261030-mae-display-read.json?ref='+'a'*40,
    'contents/state/controller-v1/bootstrap-v2-20261031-MAE-display-read.json?ref='+'a'*40,
    'contents/state/controller-v1/bootstrap-v2-20261031-mae-display-read.JSON?ref='+'a'*40,
    'contents/state/controller-v1/bootstrap-v2-20261031-mae-display-read-extra.json?ref='+'a'*40,
    'contents/state/controller-v1/bootstrap-v2-20261031-mae-display-read.json?ref=main',
    'contents/state/controller-v1/bootstrap-v2-20261031-mae-display-read.json?ref=lab-state',
    'contents/state/controller-v1/bootstrap-v2-20261031-mae-display-read.json?ref='+'A'*40,
    'contents/state/controller-v1/bootstrap-v2-20261031-mae-display-read.json?ref='+'a'*39,
    'contents/state/controller-v1/bootstrap-v2-20261031-mae-display-read.json?ref='+'a'*41,
    'contents/state/controller-v1/bootstrap-v2-20261031-mae-display-read.json?Ref='+'a'*40,
    'contents/state/controller-v1/bootstrap-v2-20261031-mae-display-read.json?ref='+'a'*40+'&page=1',
    'contents/state/controller-v1/bootstrap-v2-20261031-mae-display-read.json?ref='+'a'*40+'&ref='+'b'*40,
    'contents/state/controller-v1/bootstrap-v2-20261031-mae-display-read.json?ref='+'a'*40+'#fragment',
    'contents/state/controller-v1/bootstrap-v2-20261031-mae-display-read.json?extra=x&ref='+'a'*40,
])
def test_mae_registry_route_rejects_similar_case_ref_and_query_before_io(tail):
    api=b.Metadata({},lambda *_:pytest.fail('UNDECLARED_MAE_REGISTRY_ROUTE_REACHED_IO'))
    assert not b.fixed_route(c.API+'/'+tail)
    with pytest.raises(b.BootstrapError,match='BOOTSTRAP_FIXED_GET_ROUTE_OR_SHARED_CAP'):
        api(c.API+'/'+tail,64)
    assert api.calls==[]


@pytest.mark.parametrize('tail',[
    'contents/state/controller-v1/bootstrap-v2-20261101-MAE-history-read.json?ref='+'a'*40,
    'contents/state/controller-v1/bootstrap-v2-20261101-mae-history-read.JSON?ref='+'a'*40,
    'contents/state/controller-v1/bootstrap-v2-20261101-mae-history-read-extra.json?ref='+'a'*40,
    'contents/state/controller-v1/bootstrap-v2-20261101-mae-history-read.json?ref=main',
    'contents/state/controller-v1/bootstrap-v2-20261101-mae-history-read.json?ref=lab-state',
    'contents/state/controller-v1/bootstrap-v2-20261101-mae-history-read.json?ref='+'A'*40,
    'contents/state/controller-v1/bootstrap-v2-20261101-mae-history-read.json?ref='+'a'*39,
    'contents/state/controller-v1/bootstrap-v2-20261101-mae-history-read.json?ref='+'a'*41,
    'contents/state/controller-v1/bootstrap-v2-20261101-mae-history-read.json?Ref='+'a'*40,
    'contents/state/controller-v1/bootstrap-v2-20261101-mae-history-read.json?ref='+'a'*40+'&page=1',
    'contents/state/controller-v1/bootstrap-v2-20261101-mae-history-read.json?ref='+'a'*40+'&ref='+'b'*40,
    'contents/state/controller-v1/bootstrap-v2-20261101-mae-history-read.json?ref='+'a'*40+'#fragment',
])
def test_history_mae_registry_new_literal_remains_fixed_before_io(tail):
    api=b.Metadata({},lambda *_:pytest.fail('UNDECLARED_HISTORY_MAE_REGISTRY_ROUTE_REACHED_IO'))
    assert not b.fixed_route(c.API+'/'+tail)
    with pytest.raises(b.BootstrapError,match='BOOTSTRAP_FIXED_GET_ROUTE_OR_SHARED_CAP'):
        api(c.API+'/'+tail,64)
    assert api.calls==[]


def test_new_default_registry_does_not_reclassify_the_previous_native_seal():
    assert b.LOCATOR_REGISTRY_PATH=='state/controller-v1/bootstrap-v2-20261101-mae-capacity-phase.json'
    assert b.LOCATOR_REGISTRY_PATH!='state/controller-v1/bootstrap-v2-20261031-mae-display-read.json'
    assert b.fixed_route(c.contents_url('state/controller-v1/bootstrap-v2-20261031-mae-display-read.json','a'*40))
    assert b.REGISTRY_PATH=='state/controller-v1/bootstrap-v1.json'


def test_pinned_history_registry_preserves_all_prior_literal_seals():
    assert b.LOCATOR_REGISTRY_PATH == "state/controller-v1/bootstrap-v2-20261101-mae-capacity-phase.json"
    for previous in ("state/controller-v1/bootstrap-v2-20261031-mae-display-read.json",
                     "state/controller-v1/bootstrap-v2-20261101-mae-history-read.json",
                     "state/controller-v1/bootstrap-v2-20261101-mae-pinned-history.json"):
        assert previous != b.LOCATOR_REGISTRY_PATH
        assert b.fixed_route(c.contents_url(previous, "a" * 40))
    url = c.contents_url(b.LOCATOR_REGISTRY_PATH, "a" * 40)
    assert b.fixed_route(url)
    for bad in (url.replace("20261101", "20261102"),
                url.replace(".json?", ".JSON?"), url.replace(".json?", "-extra.json?"),
                url.replace("?ref=", "?Ref="), url + "&page=1", url + "#fragment",
                url.rsplit("?ref=", 1)[0] + "?ref=main",
                url.rsplit("?ref=", 1)[0] + "?ref=lab-state"):
        assert bad != url
        assert not b.fixed_route(bad)
