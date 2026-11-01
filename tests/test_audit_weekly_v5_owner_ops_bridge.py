"""Offline V5 first-Owner bridge through complete fictional archive recovery.

The archive and native/source/clock fixture boundaries are explicitly synthetic.
The real controller, template, discovery, retained and restoration code runs;
no network, providers, models, capture, native qualification or publication.
"""
import base64
from copy import deepcopy
from datetime import datetime,timezone
import gzip
import json
from pathlib import Path
import pickle
import socket
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from nfl_lab import audit_weekly_controller_v1 as c
from nfl_lab import audit_weekly_controller_bootstrap_v1 as bootstrap
from nfl_lab import audit_weekly_discovery_v1 as discovery
from nfl_lab import audit_weekly_grade_history_v1 as history
from nfl_lab import audit_weekly_retained_v1 as retained
from nfl_lab import audit_weekly_template_v1 as template
from nfl_lab import weekly_mae_display_profile_v1 as profile
from nfl_lab import private_draft_store as store
import test_audit_weekly_operations_restore_v1 as old

ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.setattr(socket.socket,"connect",lambda *_:pytest.fail("REAL_NETWORK_FORBIDDEN"))


def _fixture_profile(root,source_root):
    """Only the existing incomplete-Root source/native fixture boundary.

    Exact byte/profile qualification has its own real validator controls in
    test_audit_weekly_v5_admission_metadata. No runtime grant is returned here.
    """
    assert root["schema_version"]==template.ROOT_V5
    assert set(root["mae_helper_pins"])==set(profile.HELPERS)
    return {"mae_runtime_pin_profile":{"changed_paths":{}}}


def make_seed(case):
    import test_audit_weekly_operations_worker_v1 as fixture
    seed=old._source_history_seed(case,actor="owner");root=deepcopy(seed["go"])
    x=case.q.x;value=case.old["receipt"];readiness=x.p["readiness"]
    raw=store.canonical(value);encoded=gzip.compress(raw,mtime=0)
    readiness.update(source_sha=value["source_sha"],branch=root["workflow_ref"].split("@refs/heads/",1)[1],
        run_id=value["run_id"],workflow_sha256=value["workflow_sha256"],jobs=deepcopy(value["jobs"]),
        receipt_sha256=store.sha(encoded),receipt_body_sha256=store.sha(raw),
        receipt_bindings={k:value[k] for k in c.RECEIPT_HASH_KEYS})
    x.original_receipt=raw
    x.api.data[c.contents_url(c.receipt_path(x.p),"lab-state")]=fixture.original.content(c.receipt_path(x.p),encoded)
    root["schema_version"]=template.ROOT_V5
    root["mae_helper_pins"]={name:store.sha(("FICTIONAL_HELPER:"+name).encode()) for name in profile.HELPERS}
    for name in bootstrap.PARENT_MAE_METADATA_PINS:
        body=(ROOT/name).read_bytes();path=x.parent_source/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body)
        x.p["parent"]["code_pins"][name]=root["mae_helper_pins"][name]=store.sha(body)
    root["mae_registration"]=dict(path=profile.REGISTRATION_PATH,bytes=len((ROOT/profile.REGISTRATION_PATH).read_bytes()),
        sha256=root["mae_helper_pins"][profile.REGISTRATION_PATH])
    body=history._source_history_unwrap(root["source_history_binding"])
    body.update(schema_version=history.SOURCE_HISTORY_BINDING_V2,predecessor_root_schema=history.ROOT_V4,
        predecessor_source_history_sha256=store.sha(b"FICTIONAL_ORIGINAL_HISTORY_BINDING"))
    root["source_history_binding"]=history.source_history_envelope(body)
    # An explicit synthetic closed authority accompanies invented archive bytes.
    # Production's exact34743 constant is tested separately without replacement.
    authority=deepcopy(c.V5_HISTORICAL_AUTHORITY)
    authority.update({k:value[k] for k in ("source_sha","run_id","root_go_sha256","workflow_sha256","jobs")})
    authority.update(branch=readiness["branch"],receipt_sha256=store.sha(encoded),receipt_body_sha256=store.sha(raw),
        root_static_sha256=body["predecessor"]["root_static_sha256"],
        code_pins_sha256=body["predecessor"]["code_pins_sha256"],
        source_history_binding_sha256=body["predecessor_source_history_sha256"])
    for api in (case.old["api"],x.api.data):
        url=c.run_url(value["run_id"])
        if url in api:api[url].update(actor=deepcopy(c.BOT),triggering_actor=deepcopy(c.BOT))
    with patch.object(c,"V5_HISTORICAL_AUTHORITY",authority),patch.object(profile,"validate_metadata",_fixture_profile):
        x.p=c.historical_v5_registration(root,x.p);x.reg=store.canonical(x.p);x.seal=store.sha(x.reg)
        x.native.update(registration_sha256=x.seal,code_pins_sha256=store.sha(store.canonical(root["code_pins"])))
        x.claim["registration_sha256"]=x.seal
        seed=old._dual_runtime_seed(case,root_override=root)
    seed.update(source_history=True,actor="owner",fictional_authority=authority,v5_fixture=True)
    return seed


@pytest.fixture
def bridge_seed(tmp_path,monkeypatch):
    case=old.operational_case.__wrapped__(tmp_path,monkeypatch,SimpleNamespace(param="source-history"))
    return make_seed(case)


def _native_v5(seed,damage=None):
    checked=[];real_bind=retained.bind_v5_source_history
    def check_bind(p,authority,**kwargs):
        proof=kwargs["bootstrap_proof"];grant=kwargs["discovery_grant"];at=retained.now()
        original=store.canonical(p)
        mutations=[
            ("source",("reader_handoff","archive","source_sha"),"0"*40),
            ("run",("reader_handoff","archive","run_id"),"9999999"),
            ("root",("reader_handoff","archive","root_go_sha256"),"0"*64),
            ("produce-api",("reader_handoff","archive","producer","api_job_id"),999999),
            ("restore-api",("reader_handoff","restorer","api_job_id"),999999),
            ("export-api",("exporter_api_job_id",),999999),
            ("index",("reader_handoff","archive","index_descriptor","entry","payload","sha256"),"0"*64),
            ("files",("reader_handoff","archive","files_sha256"),"0"*64),
            ("witness",("reader_handoff","witness_descriptor","entry","payload","sha256"),"0"*64),
            ("workflow",("reader_handoff","archive","producer","workflow_ref"),store.REPO+"/.github/workflows/lab.yml@refs/heads/main"),
            ("old-code",("historical_source_sha256","nfl_lab/audit_weekly_archive_v1.py"),"0"*64),
            ("package",("qualified_runtime","runtime_id"),"0"*32),
        ]
        for name,path,value in mutations:
            bad=deepcopy(p);part=bad
            for key in path[:-1]:part=part[key]
            part[path[-1]]=value
            with pytest.raises(store.StoreError,match="V5_RETAINED_EXACT_ORIGINAL_ARCHIVE_SOURCE_PACKAGE"):
                retained._v5_historical_scope(bad,authority,proof,grant,at)
            checked.append(name)
        with pytest.raises(store.StoreError,match="V5_SAME_CURRENT_OWNER_AND_DISCOVERY_GRANT_REQUIRED"):
            retained._v5_historical_scope(p,authority,{"actor":c.BOT},grant,at)
        with pytest.raises(store.StoreError,match="V5_SAME_CURRENT_OWNER_AND_DISCOVERY_GRANT_REQUIRED"):
            retained._v5_historical_scope(p,authority,proof,deepcopy(grant.document),at)
        checked.extend(["current-child-type","JSON-discovery-grant"])
        root=grant._source_history_root;value=grant._value;binding=grant.document["binding"]
        # These checks run before any discovery private GET. The exact full
        # static Root, rather than a caller-provided Root hash, is authenticated.
        bad=deepcopy(root);bad["mae_helper_pins"]["nfl_lab/weekly_mae_display_runtime_v1.py"]="0"*64
        altered=dict(binding,current_root_go_sha256=store.sha(store.canonical(bad)))
        with pytest.raises(store.StoreError,match="SOURCE_HISTORY_DISCOVERY_STATIC_ROOT_MUST_MATCH_NATIVE_SEAL"):
            discovery._source_history_contract(bad,value,grant.document["scope"],altered,proof)
        bad=deepcopy(root);bad["effective_epoch"]["previous_checkpoint"]=None
        with pytest.raises(store.StoreError,match="V5_OLD_OPS_HISTORY_LOCATOR_REQUIRED_NO_NULL_CHECKPOINT"):
            discovery._v5_owner_history(bad,value,proof)
        bad=deepcopy(root);bad["schema_version"]=template.ROOT_V4
        with pytest.raises(store.StoreError,match="EXPLICIT_V5_OWNER_OPS_TRANSITION_REQUIRED"):
            discovery._v5_owner_history(bad,value,proof)
        for key in ("policy_sha256","root_go_sha256","source_sha","run_id"):
            bad=deepcopy(value);bad[key]="0"*(40 if key=="source_sha" else 64) if key!="run_id" else "999999"
            with pytest.raises(store.StoreError,match="EXACT_V5_NATIVE_34743_PUBLIC_RECEIPT_REQUIRED"):
                discovery._v5_owner_history(root,bad,proof)
        checked.extend(["full-static-seal","nonnull-old-checkpoint","no-V4-relabel","old-policy","old-root","old-source","old-receipt-run"])
        result=real_bind(p,authority,**kwargs);at=retained.now()
        assert result.document["scope"]["approved_source_sha"]==seed["go"]["source_sha"]
        assert result.document["scope"]["current_actor"]==c.OWNER
        assert result.document["v5_historical_scope"]["public_policy_sha256"]==value["policy_sha256"]
        assert result.document["v5_historical_scope"]["public_policy_sha256"]!=result.document["scope"]["public_policy_sha256"]
        with pytest.raises(store.StoreError,match="HISTORICAL_SOURCE_GRANT_CANNOT_BE_SERIALIZED"):pickle.dumps(result)
        with pytest.raises(store.StoreError,match="LIVE_HISTORICAL_SOURCE_GRANT_REQUIRED"):
            retained.authenticate_origin(None,p,authority,historical_grant=deepcopy(result.document))
        with pytest.raises(store.StoreError,match="LIVE_HISTORICAL_SOURCE_GRANT_REQUIRED"):
            retained.HistoricalSourceGrant(result.document,proof,kwargs["authenticate"],object())
        # Even a same-process document mutation with its public digest updated
        # cannot substitute the current publication policy for original policy.
        saved=deepcopy(result.document);saved_sha=result.sha256
        try:
            result.document["v5_historical_scope"]["public_policy_sha256"]=result.document["scope"]["public_policy_sha256"]
            result.sha256=store.sha(store.canonical(result.document))
            with pytest.raises(store.StoreError,match="V5_HISTORICAL_SCOPE_CHANGED_OR_UNBOUND"):
                result.verify(p,authority,at)
        finally:result.document=saved;result.sha256=saved_sha
        result.verify(p,authority,at)
        assert store.canonical(p)==original
        checked.extend(["nonserializable","JSON-retained-grant","private-constructor-key","original-policy-not-current-policy"])
        return result
    with patch.object(c,"V5_HISTORICAL_AUTHORITY",seed["fictional_authority"]),\
         patch.object(profile,"validate_metadata",_fixture_profile),\
         patch.object(retained,"bind_v5_source_history",check_bind):
        if damage is not None:
            url=c.run_url(seed["old"]["receipt"]["run_id"]);run=seed["api"][url]
            if damage=="historical-owner":run["actor"]=deepcopy(c.OWNER)
            elif damage=="historical-trigger-owner":run["triggering_actor"]=deepcopy(c.OWNER)
            elif damage=="historical-source":run["head_sha"]="0"*40
            elif damage=="historical-job-failed":seed["api"][c.jobs_url(seed["old"]["receipt"]["run_id"])]["jobs"][0]["conclusion"]="failure"
            elif damage=="current-bot":
                seed["env"].update(GITHUB_ACTOR=c.BOT["login"],GITHUB_ACTOR_ID=str(c.BOT["id"]))
                seed["api"][c.run_url(seed["env"]["GITHUB_RUN_ID"])]["actor"]=deepcopy(c.BOT)
            else:raise AssertionError(damage)
        result=old._native(seed);result["closed_V5_binding_controls"]=checked
        return result


def run_seed(seed,tmp_path,damage=None):
    path=tmp_path/"v5-invented-native-seed.json";path.write_bytes(store.canonical(seed))
    script='''
import json,socket,sys
from pathlib import Path
from tools.private_draft_store_v2 import limits
limits()
sys.path.insert(0,str(Path.cwd()/'tests'))
import test_audit_weekly_v5_owner_ops_bridge as probe
socket.socket.connect=lambda *_:(_ for _ in ()).throw(AssertionError('REAL_NETWORK_FORBIDDEN'))
seed=json.loads(Path(sys.argv[1]).read_bytes())
try:
 result=probe._native_v5(seed,None if sys.argv[2]=='NONE' else sys.argv[2])
except Exception as error:
 if sys.argv[2]=='NONE':raise
 print(json.dumps({'rejected':type(error).__name__,'reason':str(error)}))
else:
 if sys.argv[2]!='NONE':raise AssertionError('DAMAGED_BRIDGE_ACCEPTED')
 print(json.dumps(result,sort_keys=True))
'''
    numerical=json.loads((ROOT/"config/audit-weekly-numerical-runtime-v1.json").read_bytes())["environment"]
    result=subprocess.run([sys.executable,"-B","-c",script,str(path),damage or "NONE"],cwd=ROOT,
        env={"PYTHONDONTWRITEBYTECODE":"1",**numerical},capture_output=True,text=True,timeout=185)
    assert result.returncode==0,result.stderr
    return json.loads(result.stdout)


def test_v5_manual_owner_restores_complete_old_bot_archive_with_two_policy_scopes(bridge_seed,tmp_path,record_property):
    value=run_seed(bridge_seed,tmp_path)
    assert value["state"]=="PASS_FICTIONAL_NATIVE_DISCOVERY_AND_FULL_RECOVERY"
    assert value["restored_original_bytes"] is value["pending_journal_preserved"] is True
    assert value["fits"]==value["model_decodes"]==value["outcome_decodes"]==value["remote_writes"]==0
    assert value["genuine_Actions_evidence"] is value["public_release"] is False
    assert value["root_bytes"]<=60<<10 and value["pins"]==128 and value["HTTP_calls"]<=640
    assert len(value["closed_V5_binding_controls"])==25
    assert value["grant_kinds"]==["BIND_SEALED_DISCOVERY_SOURCE","LIVE_DISCOVERY_METADATA_BEFORE_PRIVATE_GET",
        "BIND_SEALED_HISTORICAL_SOURCE","LIVE_HISTORICAL_METADATA_BEFORE_PRIVATE_GET"]
    record_property("fictional_v5_complete_restoration",json.dumps(value,sort_keys=True))


@pytest.mark.parametrize("damage",["historical-owner","historical-trigger-owner","historical-source","historical-job-failed","current-bot"])
def test_v5_live_original_bot_jobs_and_current_owner_remain_strict(bridge_seed,tmp_path,damage):
    result=run_seed(bridge_seed,tmp_path,damage)
    assert result["rejected"] in {"StoreError","BootstrapError","ControllerError"}
    assert result["reason"] not in {"DAMAGED_BRIDGE_ACCEPTED","REAL_NETWORK_FORBIDDEN"}

