"""Root-sealed derived export; optional control API, no NFL acquisition/model/scoring."""
import argparse
import gzip
import io
import json
from pathlib import Path
import resource
import re
import signal
import sys
from datetime import datetime,timezone

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from nfl_lab import weekly_public_feed as feed
from nfl_lab import weekly_durable_acceptance as acceptance
from nfl_lab.private_draft_store import read_local,create_local,parents_safe


def read_ref(ref,cap):
    body=read_local(ref["path"],cap)
    feed.require(len(body)==ref["bytes"] and feed.sha(body)==ref["sha256"],"EXACT_EXPORT_INPUT")
    return body


def pre_value_catalog(plan,bundle,policy):
    """Authenticate the original catalog before opening selected forecast values."""
    if policy['schema_version']!=getattr(feed,'POLICY_V2',None):return {}
    ref=bundle['terminal'].get('selected_version_catalog')
    fresh=plan['selected_version_catalog'];body=read_ref(fresh,256<<10)
    feed.require(type(ref) is dict and set(ref)=={'path','bytes','sha256'}
        and type(ref['bytes']) is int and 0<ref['bytes']<=256<<10
        and len(body)==ref['bytes']==fresh['bytes']
        and feed.sha(body)==ref['sha256']==fresh['sha256'],'EXACT_OWNED_PRE_VALUE_VERSION_CATALOG_BODY_REQUIRED')
    catalog=feed.strict_public_json(body)
    feed.require(body==feed.canonical(catalog)+b'\n','REGISTERED_CATALOG_SERIALIZATION_REQUIRED')
    feed.catalog_policy_v2(policy,catalog)
    return {'version_catalog_body':body}


def publish_files(document,state,policy,*,write=create_local):
    """Exact reviewed file map for UNCHANGED persist_state.py v2; no Git calls."""
    body=feed.canonical(document);name=feed.utc(document["created_at"]).strftime("%Y%m%dT%H%M%S.%fZ")+"--"+feed.sha(body)+".json"
    relative=f"public/weekly-adaptive-v1/{document['season']}-W{document['week']:02d}/"+name
    receipt=dict(schema_version="weekly-derived-export-receipt-v1",authority_kind="AUTOMATED_REGISTERED_DERIVED_POLICY",human_approval=False,
        policy_sha256=feed.digest(policy),feed_sha256=feed.sha(body),feed_bytes=len(body),rows=len(document["rows"]),created_at=document["created_at"],public_fields=policy["public_fields"])
    receipt_body=gzip.compress(feed.canonical(receipt),mtime=0);receipt_path="public/weekly-adaptive-v1/receipts/"+feed.sha(receipt_body)+".json.gz"
    files={relative:body,receipt_path:receipt_body}
    for path,payload in files.items():
        target=parents_safe(Path(state)/path);target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():feed.require(read_local(target,feed.MAX_BYTES)==payload,"IMMUTABLE_EXPORT_COLLISION")
        else:write(target,payload)
    return dict(schema_version="operational-publication-review-v2",review_state="ACCEPTED",policy_sha256=policy["source_policy_sha256"],
        files={name:feed.sha(payload) for name,payload in files.items()})


def persist_live_acceptance(plan,policy,record):
    """Keep the live API receipt immutable within the existing quota owner."""
    from nfl_lab.frozen_source_policy import load_frozen_source_policy
    from nfl_lab.operational_storage import OperationalStorage
    read_ref(plan['source_policy'],1<<20)
    source=load_frozen_source_policy(Path(plan['source_policy']['path']))
    feed.require(source['_policy_sha256']==policy['source_policy_sha256'],'ACCEPTANCE_SOURCE_POLICY')
    cache=Path(plan['cache_root'])
    feed.require((cache/'operational-storage-v2/registry.json').is_file(),'EXISTING_ACCEPTANCE_QUOTA_OWNER_REQUIRED')
    storage=OperationalStorage(cache,source,state=plan['state_root'])
    destination=parents_safe(plan['durability_acceptance_output'])
    feed.require(not destination.exists(),'IMMUTABLE_LIVE_ACCEPTANCE_EXISTS')
    storage.write_bytes(destination,acceptance.canonical(record),replace=False)


def automatic_acceptance(plan,bundle,policy,now):
    """Future separate export job only; registration checked before token access."""
    import os
    from tools.private_draft_store_v2 import actions_context
    from nfl_lab import private_draft_store as store
    procedures=[p for p in policy.get('durability_verifier_procedures',[]) if acceptance.digest(p)==plan.get('verifier_procedure_sha256')]
    feed.require(len(procedures)==1,'REGISTERED_VERIFIER_REQUIRED');procedure=procedures[0]
    feed.require(procedure['verifier_sha256']==feed.sha(Path(acceptance.__file__).read_bytes()),'REGISTERED_VERIFIER_CODE_REQUIRED')
    env=os.environ
    feed.require(env.get('GITHUB_ACTIONS')=='true' and env.get('GITHUB_REPOSITORY')==store.REPO and env.get('GITHUB_EVENT_NAME')=='workflow_dispatch'
        and env.get('GITHUB_RUN_ATTEMPT')=='1' and env.get('GITHUB_SHA')==procedure['source_sha']
        and env.get('GITHUB_JOB')==procedure['export_job'] and env.get('STORE_PERMISSION')=='write','ACTUAL_EXPORT_ACTIONS_CONTEXT_REQUIRED')
    job=actions_context(env,'write')
    client=store.Client(env.get('GITHUB_TOKEN'),env.get('GITHUB_RUN_ID'),journal=plan['acceptance_journal'],source_sha=procedure['source_sha'],job=job,operation='export_acceptance')
    client.bind(bundle['durability']['runtime_binding'])
    live=acceptance.verify_current_actions(client,procedure,bundle,policy,bundle['canary_acceptance'],now=now)
    live.control_API_calls=client.calls  # In-memory counter; closed proof schema unchanged.
    persist_live_acceptance(plan,policy,live.record)
    return live


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--plan",type=Path,required=True);parser.add_argument("--plan-sha256",required=True);args=parser.parse_args(argv)
    raw=read_local(args.plan,1<<20);feed.require(feed.sha(raw)==args.plan_sha256,"EXACT_EXPORT_PLAN")
    plan=json.loads(raw)
    feed.require(plan.get("schema_version")=="weekly-public-feed-export-plan-v1" and plan.get("execution_authorized") is True
        and plan.get("authority_kind")=="AUTOMATED_REGISTERED_DERIVED_POLICY"
        and plan.get("registration_policy_sha256")==plan.get("policy",{}).get("sha256"),"UNSEALED_EXPORT_NO_VALUES")
    resource.setrlimit(resource.RLIMIT_CPU,(30,30));resource.setrlimit(resource.RLIMIT_AS,(512<<20,512<<20));signal.alarm(45)
    policy=json.loads(read_ref(plan["policy"],1<<20));feed.policy_check(policy);bundle={}
    feed.require(plan.get('durability_authority') in {'ROOT_VERIFIED','ROOT_APPROVED_PROCEDURE_VERIFIED'},'EXPLICIT_DURABILITY_AUTHORITY_REQUIRED')
    for key in ["terminal","completion","decision","parent_capture","bridge","rights","r0","durability","producer_proof"]:
        body=read_ref(plan[key],2<<20);bundle[key]=json.loads(body)
        if key=="decision":bundle["decision_body_sha256"]=feed.sha(body)
        if key=="parent_capture":bundle["parent_capture_body_sha256"]=feed.sha(body)
        if key=="terminal":bundle['terminal_body_sha256']=feed.sha(body)
    if bundle['producer_proof']['schema_version']=='weekly-selected-packager-provenance-v2':
        body=read_ref(plan['inference_consumed'],1<<20);bundle.update(inference_consumed=json.loads(body),inference_consumed_body_sha256=feed.sha(body),inference_consumed_body_bytes=len(body))
    now=datetime.now(timezone.utc).isoformat();live=None
    if plan['durability_authority']=='ROOT_VERIFIED':bundle['durability_acceptance']=json.loads(read_ref(plan['durability_acceptance'],2<<20))
    else:
        bundle['canary_acceptance']=json.loads(read_ref(plan['canary_acceptance'],1<<20))
        live=automatic_acceptance(plan,bundle,policy,now)
        now=datetime.now(timezone.utc).isoformat()
    _,accepted=feed.private_gates(bundle,policy,now=now,durable_acceptance=live)
    version_kwargs=pre_value_catalog(plan,bundle,policy)
    # No private values are decoded until all actual rights/durability/R0 gates pass.
    body=read_ref(plan["selected"],8<<20)
    if plan.get('selected_relocation') is None:
        feed.require(bundle["completion"]["binding"]==plan["selected"],"SELECTED_BODY_BINDING")
    else:
        from nfl_lab import selected_private_snapshot as snapshot
        from nfl_lab.operational_storage import OperationalStorage
        feed.require(plan['source_policy']['sha256']==policy['source_policy_sha256'],'RELOCATION_SOURCE_POLICY_REQUIRED')
        source_policy=json.loads(read_ref(plan['source_policy'],1<<20));storage=OperationalStorage(plan['cache_root'],source_policy,state=plan['state_root'])
        snapshot.verify_relocation(json.loads(read_ref(plan['selected_relocation'],1<<20)),bundle,plan['selected'],storage,accepted,plan['selected_snapshot_index'])
    rows=[];inflated=0
    with gzip.GzipFile(fileobj=io.BytesIO(body)) as stream:
        while True:
            line=stream.readline(32769)
            if not line:break
            inflated+=len(line);feed.require(len(line)<=32768 and line.endswith(b'\n') and inflated<=64<<20 and len(rows)<5000,"SELECTED_DECODE_BOUND")
            rows.append(json.loads(line))
    board=json.loads(read_ref(plan["board"],16<<20));document=feed.export_rows(rows,bundle,policy,board,now=now,durable_acceptance=live,**version_kwargs)
    from nfl_lab.frozen_source_policy import load_frozen_source_policy as load_source_policy
    from nfl_lab.operational_storage import OperationalStorage
    read_ref(plan["source_policy"],1<<20)
    source_policy=load_source_policy(Path(plan["source_policy"]["path"]))
    feed.require(source_policy["_policy_sha256"]==policy["source_policy_sha256"],"PUBLICATION_SOURCE_POLICY")
    storage=OperationalStorage(plan["cache_root"],source_policy,state=plan["state_root"])
    storage.register_root(Path(plan["publication_manifest"]).parent)
    manifest=publish_files(document,plan["state_root"],policy,write=lambda p,b:storage.write_bytes(p,b,replace=False))
    storage.write_bytes(plan["publication_manifest"],feed.canonical(manifest),replace=False)
    print(json.dumps(dict(state="DERIVED_EXPORT_PREPARED_NOT_PUBLISHED",rows=len(document["rows"]),feed_sha256=feed.digest(document),control_API_calls=getattr(live,'control_API_calls',0),NFL_HTTP=0,models_decoded=0,public_raw_or_model_fields=0),sort_keys=True));return 0


if __name__=="__main__":
    try:status=main()
    except Exception as error:
        # Public job logs receive a finite reason, never a private input path/body.
        reason=str(error) if isinstance(error,feed.FeedError) and re.fullmatch(r'[A-Z0-9_]+',str(error)) else 'EXPORT_INPUT_OR_EXECUTION_REJECTED'
        print(json.dumps(dict(state='DERIVED_EXPORT_BLOCKED',reason=reason,published=False),sort_keys=True),file=sys.stderr);status=1
    raise SystemExit(status)
