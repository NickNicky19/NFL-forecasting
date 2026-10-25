"""Fictional metadata/opaque bytes and injected service only; no real HTTP/ML."""
from copy import deepcopy
from contextlib import redirect_stdout
from datetime import timedelta
import base64
import gzip
import io
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from nfl_lab import audit_weekly_origin_v1 as o, private_draft_store as s
from nfl_lab import selected_private_snapshot as snap, weekly_generic_producer as generic, weekly_adaptive as selector
from nfl_lab.operational_storage import OperationalStorage
from tools import audit_weekly_origin_v1 as cli
from test_audit_weekly_epoch_v1 import fixture as choice_fixture

ROOT=Path(__file__).resolve().parents[1]
WORKFLOW=s.REPO+"/.github/workflows/lab.yml@refs/heads/research/weekly-storage-probe-v1"
CURRENT_RUN="49900000000"
CURRENT_SOURCE="b"*40
ISSUED="2026-10-25T00:10:00Z"
CREATED="2026-10-25T00:10:07Z"
CHECKED=s.utc("2026-10-25T00:12:00Z")


def ref(raw,name):
    return dict(path="/fictional/original/"+name,bytes=len(raw),sha256=s.sha(raw))


def binding():
    runtime="c"*32;sha="d"*64
    return dict(schema_version="weekly-private-draft-binding-v2",repository=s.REPO,runtime_id=runtime,origin_run_id="40000000001",
        release_id=91,tag_name="weekly-private-runtime-v2-"+runtime,canary_asset_id=92,canary_name="canary-"+sha+".txt",
        canary_sha256=sha,canary_bytes=117,browser_tag="untagged-"+"b"*20,config_sha256=s.config_sha())


def descriptor(raw,kind="runtime_manifest",process="4"*64):
    p=snap.manifest(raw,kind)
    e=dict(schema_version="weekly-private-restore-manifest-v2",payload=p,payload_asset_id=101,payload_name="blob-"+p["sha256"]+".bin",
        producer_process=process,binding_sha256=s.sha(s.canonical(binding())),writer_run_id=o.SELECTED_RUN)
    return dict(entry=e,manifest_asset_id=102,manifest_sha256=s.sha(s.canonical(e)),manifest_bytes=len(s.canonical(e)))


def authority():
    return dict(schema_version=o.VERSION+"-native-authority",phase="origin",request_sha256="e"*64,repository=s.REPO,
        owner_root_go_sha256=s.sha(b'{"FICTIONAL_ROOT":true}'),owner_root_checked=True,actual_actions_api_authenticated=True,
        api_job_id=999,source_sha=CURRENT_SOURCE,run_id=CURRENT_RUN,run_attempt=1,job_id="audit-weekly-origin-v1",workflow_ref=WORKFLOW,
        issued_at_utc=ISSUED,expires_at_utc="2026-10-25T00:25:00Z",fits=0,remote_writes=0,protected_outcome_reads=0,public_release=False)


def proof(*,current=False):
    source=CURRENT_SOURCE if current else o.SELECTED_SOURCE;run=CURRENT_RUN if current else o.SELECTED_RUN
    return dict(schema_version="weekly-private-proof-v2.1",phase="restore",operation="restore",repository=s.REPO,run_id=run,run_attempt=1,
        source_sha=source,binding_sha256=s.sha(s.canonical(binding())),config_sha256=s.config_sha(),process_identity=("6" if current else "5")*64,
        started_at_utc="2026-10-25T00:10:01Z" if current else "2026-10-24T21:47:30Z",
        created_at_utc="2026-10-25T00:10:06Z" if current else "2026-10-24T21:47:50Z",
        job=dict(execution_lane="github_actions",workflow_ref=WORKFLOW,workflow_sha=source,job_id="audit-weekly-origin-v1" if current else o.SELECTED_JOBS["reader"][0],
            permission="write",event_name="workflow_dispatch",api_job_id=999 if current else o.SELECTED_JOBS["reader"][1],run_authenticated=True),
        HTTP_calls=10,transfer_bytes=1000,exact_readback=True,payload_sha256=s.sha(b"FICTIONAL_OPAQUE_SELECTED"),bytes=len(b"FICTIONAL_OPAQUE_SELECTED"),
        separate_process=True,draft_before_after=True)


def evidence():
    clocks={"producer":("2026-10-24T21:44:58Z","2026-10-24T21:47:23Z"),
        "reader":("2026-10-24T21:47:25Z","2026-10-24T21:47:58Z"),"exporter":("2026-10-24T21:48:10Z","2026-10-24T21:48:53Z")}
    return {role:dict(repository=s.REPO,run_id=o.SELECTED_RUN,source_sha=o.SELECTED_SOURCE,job_id=job,api_job_id=api,
        status="completed",conclusion="success",run_attempt=1,run_status="completed",run_conclusion="success",workflow_ref=WORKFLOW,
        started_at=clocks[role][0],completed_at=clocks[role][1]) for role,(job,api) in o.SELECTED_JOBS.items()}


def fixture(*,persisted="2026-10-24T21:45:01Z",frozen="2026-10-24T21:45:00Z"):
    catalog=choice_fixture()["catalog"]
    policy_bytes=(ROOT/"config/weekly-provisional-live-policy-v1.json").read_bytes();policy=json.loads(policy_bytes)
    for c in policy["categories"]:
        if c["category"] not in catalog["categories"]:
            spec=deepcopy(catalog["categories"]["rush_att"])
            spec.update(state="BLOCKED_LABEL_CONTRACT" if c["category"] == "fantasy_ppr" else "BLOCKED",eligible_methods=[],shortlist=[])
            catalog["categories"][c["category"]]=spec
    contract=dict(schema_version="FICTIONAL_TYPED_ORIGINAL_SLATE",remaining_game_ids=["fictional-game-"+str(n) for n in range(13)],
        elapsed_game_ids=["fictional-elapsed"])
    slate=dict(season=2026,week=7,season_type="REG",slate_id="fictional-week-7",scheduled_first_kickoff_utc="2026-10-25T13:30:00Z",
        weekly_deadline_utc="2026-10-25T07:30:00Z",game_cutoffs={n:"2026-10-25T00:00:00Z" for n in contract["remaining_game_ids"]},
        schedule_identity_sha256="a"*64,scheduled_games=14,elapsed_games=1,slate_contract=contract)
    choice=generic.freeze_choices(selector,dict(schema_version=selector.VERSION,offers=[],forecasts=[],outcomes=[],decisions=[],weeks=[]),
        catalog,policy,slate,actual_choice_at=s.utc(frozen))
    raw_choice=(json.dumps(choice,sort_keys=True,indent=1)+"\n").encode();choice_ref=ref(raw_choice,"WEEKLY_CHOICE.json")
    catalog_bytes=(json.dumps(catalog,sort_keys=True,indent=2)+"\n").encode()
    refs={k:ref(s.canonical(dict(FICTIONAL_ROLE=k)),k) for k in snap.META+("inference_consumed","original_handoff")}
    refs.update(decision=choice_ref,startup_policy=ref(policy_bytes,"POLICY.json"),procedure_catalog=ref(catalog_bytes,"CATALOG.json"))
    terminal=dict(schema_version=generic.VERSION,state="LOCAL_FUTURE_SLATE_CAPTURED",fatal=None,weekly_choice=choice_ref,decision=choice_ref,
        decision_persist_completed_at=persisted,actual_completed_at="2026-10-24T21:46:40Z",slate_contract=contract,startup_policy=refs["startup_policy"])
    terminal_bytes=(json.dumps(terminal,sort_keys=True,indent=2)+"\n").encode();refs["terminal"]=ref(terminal_bytes,"FINISHED.json")
    identity=dict(execution_lane="github_actions",repository=s.REPO,run_id=o.SELECTED_RUN,run_attempt=1,source_sha=o.SELECTED_SOURCE,
        process_identity="4"*64,job_id=o.SELECTED_JOBS["producer"][0],api_job_id=o.SELECTED_JOBS["producer"][1],permission="write",workflow_ref=WORKFLOW)
    selected=b"FICTIONAL_OPAQUE_SELECTED"
    producer=dict(schema_version="weekly-selected-packager-provenance-v2",identity=identity,terminal_sha256=refs["terminal"]["sha256"],
        selected_sha256=s.sha(selected),bytes=len(selected),producer_policy_sha256=s.sha(policy_bytes),source_policy_sha256=o.cp.POLICY_SHA,
        started_at_utc="2026-10-24T21:46:50Z",created_at_utc="2026-10-24T21:47:00Z",inference_consumed_ref=refs["inference_consumed"],inference_consumed_at="2026-10-24T21:45:02Z")
    candidates=[dict(target=t,method_id=m,body=ref(b"FICTIONAL_OPAQUE_CANDIDATE",str(n)+"-body"),
        completion=ref(b"FICTIONAL_COMPLETION",str(n)+"-completion"),rows=1,failure=None) for n,(t,_,m) in enumerate(o.cp.JOBS)]
    expected=snap.required_files(refs,producer,candidates)
    files=[dict(logical_path=name,sha256=h,bytes=size,required=True,origin=dict(source_policy_sha256=o.cp.POLICY_SHA)) for name,(h,size) in expected.items()]
    group_body=b"FICTIONAL_OPAQUE_GROUP"
    index=dict(schema_version=snap.VERSION,procedure_sha256=o.SELECTED_CONFIG_SHA,source_policy_sha256=o.cp.POLICY_SHA,producer=identity,
        producer_proof=producer,original_selected=ref(selected,"selected.jsonl.gz"),selected_descriptor=descriptor(selected,"forecast_batch"),
        metadata_refs=refs,groups=[dict(index=0,bytes=len(group_body),sha256=s.sha(group_body),inflated_bytes=1000,files=files,descriptor=descriptor(group_body))],
        candidates=candidates,created_at="2026-10-24T21:47:01Z")
    index_bytes=gzip.compress(s.canonical(index),mtime=0);old=proof();current=proof(current=True)
    past=gzip.compress(s.canonical(dict(schema_version=snap.VERSION+"-witness",index_sha256=s.sha(index_bytes),producer_proof_sha256=s.sha(s.canonical(producer)),restore_proof=old)),mtime=0)
    handoff=dict(schema_version=snap.VERSION+"-handoff",runtime_binding=binding(),source_sha=o.SELECTED_SOURCE,run_id=o.SELECTED_RUN,
        procedure_sha256=o.SELECTED_CONFIG_SHA,index_descriptor=descriptor(index_bytes),witness_descriptor=descriptor(past,process="5"*64))
    restored_choice=dict(choice_ref,path="/fictional/new/WEEKLY_CHOICE.json");restored_terminal=dict(refs["terminal"],path="/fictional/new/FINISHED.json")
    witness=o.terminal_witness(choice_ref,restored_choice,refs["terminal"],restored_terminal,terminal,choice,evidence(),producer,old,current,authority(),
        created_at=CREATED,terminal_bytes=terminal_bytes,index_bytes=index_bytes,handoff=handoff,policy_bytes=policy_bytes,catalog_bytes=catalog_bytes,past_witness_bytes=past)
    return dict(witness=witness,raw_choice=raw_choice,slate=o.original_slate(choice,terminal,{"input_cutoff_utc":"2026-10-25T00:00:00Z"}),
        catalog=catalog,policy=policy,handoff=handoff,index=index,terminal=terminal)


def validate(f):
    return o.validate_terminal_witness(f["witness"],f["raw_choice"],f["slate"],f["catalog"],f["policy"],CHECKED)


def test_validator_returns_sourced_old_write_clock_and_labels_missing_receipt_and_derived_slate():
    f=fixture();w=f["witness"]
    assert validate(f) == s.utc("2026-10-24T21:45:01Z")
    assert s.utc(w["created_at_utc"]) > validate(f)
    assert w["original_completion_file_retained"] is w["fabricated_original_receipt"] is False
    assert f["slate"]["origin_derivation"] == o.SLATE_DERIVATION
    assert f["slate"]["raw_original_slate_file_retained"] is False
    assert "persisted_completed_at" not in w and "choice_binding" not in w


@pytest.mark.parametrize("field,value",[("original_completion_file_retained",True),("fabricated_original_receipt",True),
    ("created_at_utc","2026-10-24T21:47:00Z"),("actual_decision_persist_completed_at","2026-10-24T21:46:00Z"),
    ("original_source_sha",CURRENT_SOURCE),("current_physical_restore_proof_sha256","f"*64),
    ("historical_authentication_scope","ROOT_CLAIM_ONLY"),("raw_original_slate_file_retained",True),
    ("metadata_proof_scope","ORIGINAL_GENERIC_COMPLETION"),("unexpected",None)])
def test_witness_cannot_change_missing_receipt_clock_scope_or_closed_fields(field,value):
    f=fixture();f["witness"][field]=value
    with pytest.raises(s.StoreError):validate(f)


@pytest.mark.parametrize("field",["terminal_body_utf8","startup_policy_body_utf8","procedure_catalog_body_utf8"])
def test_actual_raw_metadata_bytes_must_hash_before_parse_or_projection(field):
    f=fixture();f["witness"][field]+="\n"
    with pytest.raises(s.StoreError,match="EXACT_BOUNDED_ORIGINAL_METADATA_BYTES"):validate(f)


@pytest.mark.parametrize("field",["snapshot_index_gzip_base64","historical_witness_gzip_base64"])
def test_exact_compressed_index_and_past_witness_are_independent_anchors(field):
    f=fixture();raw=base64.b64decode(f["witness"][field]);f["witness"][field]=base64.b64encode(raw+b"x").decode()
    with pytest.raises(s.StoreError,match="EXACT_SOURCE_BOUND"):validate(f)


@pytest.mark.parametrize("role",["producer","reader","exporter"])
@pytest.mark.parametrize("field,value",[("source_sha",CURRENT_SOURCE),("conclusion","failure"),("api_job_id",998),("run_status","in_progress")])
def test_all_three_original_api_identities_are_checked_independently(role,field,value):
    f=fixture();f["witness"]["historical_job_api_evidence"][role][field]=value
    with pytest.raises(s.StoreError):validate(f)


def test_current_proof_cannot_be_the_old_reader_or_an_unrelated_body_proof():
    for change in ("old","unrelated","library_shape"):
        f=fixture();w=f["witness"]
        if change == "old":w["current_physical_restore_proof"]=deepcopy(w["historical_reader_restore_proof"])
        elif change == "unrelated":w["current_physical_restore_proof"]["payload_sha256"]="e"*64
        else:w["current_physical_restore_proof"]["arbitrary"]="private library text"
        with pytest.raises(s.StoreError):validate(f)


@pytest.mark.parametrize("field,value",[("weekly_deadline_utc","2026-10-26T07:30:00Z"),("schedule_identity_sha256","f"*64),
    ("origin_derivation","RETAINED_RAW"),("raw_original_slate_file_retained",True)])
def test_reconstructed_slate_and_original_deadline_cannot_be_rebound(field,value):
    f=fixture();f["slate"][field]=value
    with pytest.raises(s.StoreError):validate(f)


@pytest.mark.parametrize("persisted,frozen",[("2026-10-24T21:44:59Z","2026-10-24T21:45:00Z"),
    ("2026-10-25T07:30:00Z","2026-10-24T21:45:00Z"),("2026-10-25T08:00:00Z","2026-10-24T21:45:00Z")])
def test_frozen_existing_choice_does_not_excuse_a_late_or_earlier_write(persisted,frozen):
    with pytest.raises(s.StoreError,match="CAUSAL_ORIGINAL_TERMINAL"):fixture(persisted=persisted,frozen=frozen)


def test_validator_performs_no_private_reads_transport_deserialization_or_acquisition():
    f=fixture()
    with patch.object(o.cp,"read_ref",side_effect=AssertionError("private read")),patch.object(s,"network",side_effect=AssertionError("HTTP")):
        assert validate(f) < CHECKED


def test_prepare_request_authenticates_old_code_at_old_source_and_leaves_execution_unapproved(tmp_path):
    f=fixture();p=o.prepare_request(ROOT,f["handoff"],cache=tmp_path/"cache",state_root=tmp_path/"state",output=tmp_path/"output")
    assert p["approved"] is False and len(p["input_plan"]["logical_allowlist"]) == 78
    assert p["input_plan"]["parent"]["run_id"] == "40129209279"
    assert p["historical_code_sha256"]["nfl_lab/selected_private_snapshot.py"] == "6080ccd28f03a33298aeffb525cc7414f6a5482a542923542cb3e7105d346af4"
    p["approved"]=True;assert o.validate_request(p,ROOT)["input_cutoff_utc"] == "2026-10-25T00:00:00Z"
    p["selected_handoff"].pop("witness_descriptor")
    with pytest.raises(s.StoreError,match="PAST_WITNESS_DESCRIPTOR_REQUIRED"):o.validate_request(p,ROOT)


def environment(tmp_path):
    event=tmp_path/"event.json"
    event.write_bytes(s.canonical(dict(inputs=dict(mode=o.MODE,inference_builder_go_json='{"FICTIONAL_ROOT":true}',
        inference_builder_go_sha256=authority()["owner_root_go_sha256"]),repository=dict(full_name=s.REPO))))
    return dict(GITHUB_ACTIONS="true",GITHUB_REPOSITORY=s.REPO,GITHUB_EVENT_NAME="workflow_dispatch",GITHUB_RUN_ATTEMPT="1",
        GITHUB_ACTOR="NickNicky19",GITHUB_ACTOR_ID="208912933",STORE_PERMISSION="write",GITHUB_EVENT_PATH=str(event),GITHUB_SHA=CURRENT_SOURCE,
        GITHUB_WORKFLOW_SHA=CURRENT_SOURCE,GITHUB_RUN_ID=CURRENT_RUN,GITHUB_JOB="audit-weekly-origin-v1",GITHUB_WORKFLOW_REF=WORKFLOW)


def check_authority(a,env):
    body=s.canonical(a)
    with patch.object(o,"now",return_value=CHECKED),patch.object(o.subprocess,"check_output",side_effect=[a["source_sha"]+"\n",""]):
        return o.checked_authority(body,s.sha(body),"e"*64,env,ROOT)


def test_current_native_authority_is_bound_only_to_actual_new_inference_root_event(tmp_path):
    env=environment(tmp_path);a=authority();assert check_authority(a,env) == a
    event=json.loads(Path(env["GITHUB_EVENT_PATH"]).read_bytes());event["inputs"]["bootstrap_locators_json"]=event["inputs"].pop("inference_builder_go_json")
    Path(env["GITHUB_EVENT_PATH"]).write_bytes(s.canonical(event))
    with pytest.raises(s.StoreError,match="REAL_NEW_WEEKLY_ROOT_EVENT"):check_authority(a,env)


@pytest.mark.parametrize("field,value",[("run_id",o.SELECTED_RUN),("source_sha",o.SELECTED_SOURCE),("run_attempt",2),
    ("issued_at_utc","2026-10-24T00:00:00Z"),("actual_actions_api_authenticated",False),("remote_writes",1),("request_sha256","f"*64)])
def test_historical_identity_expired_registration_or_changed_permission_is_not_new_authority(tmp_path,field,value):
    env=environment(tmp_path);a=authority();a[field]=value
    if field == "run_id":env["GITHUB_RUN_ID"]=value
    if field == "source_sha":env["GITHUB_SHA"]=env["GITHUB_WORKFLOW_SHA"]=value
    with pytest.raises(s.StoreError):check_authority(a,env)


def test_authenticate_three_actual_historical_api_jobs_separately():
    origin=dict(run_id=o.SELECTED_RUN,source_sha=o.SELECTED_SOURCE,workflow_ref=WORKFLOW,jobs={r:dict(job_id=j,api_job_id=a) for r,(j,a) in o.SELECTED_JOBS.items()})
    run=dict(id=int(o.SELECTED_RUN),head_sha=o.SELECTED_SOURCE,status="completed",conclusion="success",event="workflow_dispatch",run_attempt=1,
        path=".github/workflows/lab.yml",repository=dict(full_name=s.REPO),head_repository=dict(full_name=s.REPO))
    rows=[dict(id=v["api_job_id"],name=v["job_id"],head_sha=v["source_sha"],run_id=int(v["run_id"]),status=v["status"],conclusion=v["conclusion"],
        started_at=v["started_at"],completed_at=v["completed_at"]) for v in evidence().values()]
    for bad in (None,"reader","exporter","producer"):
        jobs=deepcopy(rows)
        if bad:jobs[list(o.SELECTED_JOBS).index(bad)]["head_sha"]=CURRENT_SOURCE
        docs=iter([run,dict(total_count=len(jobs),jobs=jobs)])
        client=SimpleNamespace(allowed=set(),json=lambda _:next(docs))
        if bad:
            with pytest.raises(s.StoreError,match="ACTUAL_ORIGINAL_SELECTED_JOB"):o.authenticate_selected_jobs(client,origin,ISSUED)
        else:assert o.authenticate_selected_jobs(client,origin,ISSUED) == evidence()


@pytest.mark.parametrize("valid_receipts",[True,False])
def test_source_pairs_are_exact19_opaque_originals_and15_historical_owned_pairs(tmp_path,valid_receipts):
    plan=o.input_plan(ROOT);storage=OperationalStorage(tmp_path/"cache",ROOT/"config/operational-source-policy-v2.json",state=tmp_path/"state")
    raw=tmp_path/"owned/raw";storage.register_root(raw);mapping={};bodies={}
    for name,url in plan["checkpoint_config"]["source_names"].items():
        body=b"FICTIONAL_OPAQUE_RAW\x00"+name.encode();p=raw/name;storage.write_bytes(p,body);b=o.cp.binding(p);bodies[name]=body
        rp=raw/(name+".receipt.json");size=b["bytes"]+(not valid_receipts and name == "schedules.csv")
        storage.write_bytes(rp,s.canonical(dict(url=url,sha256=b["sha256"],bytes=size,status="acquired")))
        mapping["old-body-"+name]=b;mapping["old-receipt-"+name]=o.cp.binding(rp)
    checkpoint=dict(files=78,model_decodes=0,path_mapping=mapping,source_cache=str(raw.parent))
    if not valid_receipts:
        with pytest.raises(s.StoreError,match="ORIGINAL_SOURCE_RECEIPT_HASH"):o.source_pairs(plan,checkpoint,storage)
        return
    all_pairs,historical=o.source_pairs(plan,checkpoint,storage)
    assert len(all_pairs) == 19 and len(historical) == 15
    assert all(Path(p["body"]["path"]).read_bytes() == bodies[n] for n,p in all_pairs.items())
    assert {n for n in all_pairs if n not in historical} == {"players.parquet","schedules.csv","stats_player_week_2026.parquet","roster_weekly_2026.parquet"}


def test_cli_preparation_has_no_authority_or_network_and_error_text_is_closed():
    child=subprocess.run(["python",str(ROOT/"tools/audit_weekly_origin_v1.py"),"recover"],capture_output=True,text=True,check=False)
    assert child.returncode == 2 and json.loads(child.stdout)["state"] == "ORIGIN_PREPARATION_ONLY_NO_IO"
    for error,expected in [(s.StoreError("EXPLICIT_ORIGIN_BLOCKER"),"EXPLICIT_ORIGIN_BLOCKER"),
            (s.StoreError("private arbitrary text"),"ORIGIN_RECOVERY_GUARD"),(RuntimeError("PRIVATE_LIBRARY_VALUE"),"ORIGIN_RECOVERY_GUARD")]:
        stream=io.StringIO()
        with patch.object(cli.resource,"setrlimit"),patch.object(cli.signal,"signal"),patch.object(cli.signal,"alarm"),\
                patch.object(o,"checked_authority",side_effect=error),redirect_stdout(stream):
            assert cli.main(["recover","--execute"]) == 1
        payload=json.loads(stream.getvalue());assert payload["reason"] == expected
        assert "private arbitrary" not in stream.getvalue() and "PRIVATE_LIBRARY_VALUE" not in stream.getvalue()
