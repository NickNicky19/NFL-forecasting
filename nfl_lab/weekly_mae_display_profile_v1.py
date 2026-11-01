"""Stdlib-only RootV5 display source/profile checks; no private/model imports.

Metadata jobs authenticate fixed public source bytes. Numerical admission stays
inside the native runtime helper after unchanged owner/API/source validation.
"""
from pathlib import Path
import hashlib
import json
import re

REVIEWED_MODEL_PINS = {'weekly_future_inference.py': 'd84a4de76737252a910ed01b626e17403290277feb894621e625ae0791ccef42', 'cdf_engine.py': '6a963111f4173a88affe90ca1ce17532cd5eb690a1f28b284e9fa4145eecb214', 'role_boosting.py': '294e7e588215e7b7e98d6f1fb251eed31420921dff9a59e88434913133dbdf93', 'direct_boosters.py': '475e6aaca01790c896a81e51d911f5f48e4116b95383536501799c4242701e3f', 'median_boosting.py': 'c5bf8ef481c05027a2a1d4e1d19764920c0820f0614f60736826c17526e7799d', 'baseline_correction.py': '077ff69ea3e9ab3183b588accd4972baaeb1fd47f0af4c56411ef4875db68ba2'}

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()

def sha(body): return hashlib.sha256(body).hexdigest()
def h(value): return type(value) is str and re.fullmatch("[a-f0-9]{64}",value) is not None

def bounded_read(path, limit):
    with Path(path).open("rb") as stream: body=stream.read(limit+1)
    if not 0 < len(body) <= limit: raise ValueError("BOUNDED_PUBLIC_MAE_SOURCE_REQUIRED")
    return body

def file_sha(path): return sha(bounded_read(path,2 << 20))

def strict_json(body):
    def pairs(items):
        result={}
        for key,value in items:
            if key in result: raise ValueError("DUPLICATE_JSON_KEY")
            result[key]=value
        return result
    def invalid(_): raise ValueError("NONFINITE_JSON")
    return json.loads(body,object_pairs_hook=pairs,parse_constant=invalid)

ROOT_V5 = "audit-weekly-hosted-v5-root-GO"
REQUEST_V2 = "audit-weekly-runtime-v2-display-request"
REGISTRATION_PATH = "config/weekly-mae-display-core3-v1.json"
TARGETS = ("pass_yd", "pass_int", "rush_rec_yd")
HELPERS = ("nfl_lab/weekly_mae_display_runtime_v1.py", "nfl_lab/weekly_mae_display_profile_v1.py", "nfl_lab/weekly_mae_point_inference_v2_1.py",
           "nfl_lab/stat_point_mae_public_v2_2.py", "nfl_lab/next_checkpoint_median_policy_v2_view.py",
           "nfl_lab/weekly_mae_display_archive_v1.py", "nfl_lab/stat-point-mae-public-v2-2.js", "tools/persist_state.py",
           REGISTRATION_PATH)
CONFIG_KEYS = {"schema_version", "scope", "selection_product", "selection_metric", "targets",
    "source_evidence", "categories", "new_fits", "probability_policy_change", "ranking_policy_change", "public_export_authorized",
    "mae_runtime_pin_profile"}
CHANGED_LEGACY_PATHS = frozenset({
    'nfl_lab/audit_weekly_operations_restore_v1.py',
    'nfl_lab/audit_weekly_discovery_v1.py',
    'nfl_lab/audit_weekly_retained_v1.py',
    'tests/test_audit_weekly_operations_restore_v1.py',
    'nfl_lab/audit_weekly_controller_v1.py',
    'nfl_lab/audit_weekly_archive_v1.py',
    'nfl_lab/audit_weekly_controller_bootstrap_v1.py',
    'nfl_lab/audit_weekly_controller_registration_v1.py',
    'nfl_lab/audit_weekly_delivery_v1.py',
    'nfl_lab/audit_weekly_grade_history_v1.py',
    'nfl_lab/audit_weekly_hosted_v1.py',
    'nfl_lab/audit_weekly_runtime_v1.py',
    'nfl_lab/audit_weekly_template_v1.py',
    'tests/test_audit_weekly_archive_v1.py',
    'tests/test_audit_weekly_controller_bootstrap_v1.py',
    'tests/test_audit_weekly_grade_checkpoint_v1.py',
    'tests/test_audit_weekly_grade_history_v1.py',
    'tests/test_audit_weekly_hosted_v1.py',
    'tools/audit_weekly_archive_v1.py',
    'tools/audit_weekly_runtime_v1.py',
})

CATEGORY_KEYS = {"effective_model_sha256", "effective_base_procedure_version", "effective_transport_manifest_sha256",
    "effective_verified_reader_manifest_sha256", "target", "family", "base_learner_id", "support", "modeled_roles", "public_roles",
    "original_manifest_sha256", "original_model_sha256", "original_procedure_version", "training_frame_sha256",
    "training_cutoff_utc", "training_max_available_utc", "source_contract", "features"}


def require(ok, code):
    if not ok:
        raise ValueError(code)


def pins(source_root):
    return {p: file_sha(Path(source_root)/p) for p in HELPERS}


def validate_metadata(root, source_root):
    require(root.get("schema_version") == ROOT_V5 and set(root.get("mae_helper_pins", {})) == set(HELPERS)
        and all(h(v) for v in root["mae_helper_pins"].values()), "EXACT_ROOT_V5_MAE_HELPER_PINS")
    ref = root["mae_registration"]
    require(type(ref) is dict and set(ref) == {"path", "bytes", "sha256"}
        and ref["path"] == REGISTRATION_PATH and type(ref["bytes"]) is int and 0 < ref["bytes"] <= 60 << 10
        and ref["sha256"] == root["mae_helper_pins"][REGISTRATION_PATH], "EXACT_PUBLIC_MAE_REGISTRATION_REFERENCE")
    body = bounded_read(Path(source_root)/REGISTRATION_PATH, 60 << 10)
    require(len(body) == ref["bytes"] and sha(body) == ref["sha256"], "EXACT_PUBLIC_MAE_REGISTRATION_BYTES")
    cfg = strict_json(body)
    require(type(cfg) is dict and set(cfg) == CONFIG_KEYS
        and cfg["schema_version"] == "weekly-mae-display-core3-source-registration-v1"
        and cfg["scope"] == "DISPLAY_ONLY_INCUMBENT_RANKING_UNCHANGED"
        and cfg["selection_product"] == "stat_point_mae_v2" and cfg["selection_metric"] == "MAE"
        and cfg["targets"] == list(TARGETS) and cfg["new_fits"] == 0
        and cfg["probability_policy_change"] is cfg["ranking_policy_change"] is cfg["public_export_authorized"] is False,
        "CLOSED_CORE3_DISPLAY_REGISTRATION")
    require([c["target"] for c in cfg["categories"]] == list(TARGETS)
        and all(type(c) is dict and set(c) == CATEGORY_KEYS for c in cfg["categories"]), "EXACT_THREE_CORE_CATEGORIES")
    profile = cfg["mae_runtime_pin_profile"]
    require(type(profile) is dict and set(profile) == {"schema_version", "scope", "reviewed_before_inventory_sha256",
        "reviewed_after_inventory_sha256", "legacy_pin_count", "changed_paths", "model_pins", "extra_traversal_debit"}
        and profile["schema_version"] == "weekly-mae-display-runtime-pin-profile-v1"
        and profile["scope"] == "ROOT_V5_DISPLAY_ONLY_NOT_V1_HISTORY_OVERRIDE"
        and profile["legacy_pin_count"] == len(root["code_pins"]) == 128
        and profile["model_pins"] == REVIEWED_MODEL_PINS
        and set(profile["changed_paths"]) == CHANGED_LEGACY_PATHS
        and sha(canonical(root["code_pins"])) == profile["reviewed_after_inventory_sha256"]
        and profile["extra_traversal_debit"] == dict(per_model_query_rows=2,targets=list(TARGETS),
            total_prediction_row_cap=18000,fits=0), "CLOSED_MAE_ONLY_RUNTIME_PIN_PROFILE")
    before = dict(root["code_pins"])
    for name, delta in profile["changed_paths"].items():
        require(type(delta) is dict and set(delta) == {"before_sha256","after_sha256"}
            and h(delta["before_sha256"]) and h(delta["after_sha256"])
            and delta["before_sha256"] != delta["after_sha256"]
            and root["code_pins"][name] == delta["after_sha256"],
            "EXACT_REVIEWED_MAE_RUNTIME_PIN_DIFFERENCE")
        before[name] = delta["before_sha256"]
    require(sha(canonical(before)) == profile["reviewed_before_inventory_sha256"],
        "UNCHANGED_OTHER_LEGACY_PINS_REQUIRED")
    return cfg



def validate_root_extension(root, source_root):
    """Producer-only fresh actual-byte qualification, never a Parent shortcut."""
    require(type(root.get("code_pins")) is dict and len(REVIEWED_MODEL_PINS)==6
        and all(root["code_pins"].get("nfl_lab/"+name)==digest for name,digest in REVIEWED_MODEL_PINS.items()),
        "EXACT_ORIGINAL_SIX_MODEL_CODE_ROOT_PINS")
    cfg=validate_metadata(root,source_root)
    require(root["mae_helper_pins"]==pins(source_root),"EXACT_ACTUAL_PRODUCER_MAE_HELPER_BYTES")
    for name,delta in cfg["mae_runtime_pin_profile"]["changed_paths"].items():
        require(file_sha(Path(source_root)/name)==delta["after_sha256"],"EXACT_ACTUAL_PRODUCER_MAE_LEGACY_BYTES")
    return cfg


def prior_extension_metadata(root):
    """Shape only, after an independently authenticated native Root preimage.

    This never verifies current source, admits a model, or grants execution.
    The old source/config/helper hashes remain their original commitments.
    """
    require(root.get("schema_version")==ROOT_V5 and type(root.get("mae_helper_pins")) is dict
        and set(root["mae_helper_pins"])==set(HELPERS) and all(h(v) for v in root["mae_helper_pins"].values()),
        "CLOSED_ORIGINAL_MAE_HELPER_COMMITMENTS")
    ref=root.get("mae_registration")
    require(type(ref) is dict and set(ref)=={"path","bytes","sha256"} and ref["path"]==REGISTRATION_PATH
        and type(ref["bytes"]) is int and 0<ref["bytes"]<=60<<10
        and ref["sha256"]==root["mae_helper_pins"][REGISTRATION_PATH],"CLOSED_ORIGINAL_MAE_REGISTRATION_COMMITMENT")

# One source-reviewed no-write case. This is not a generic failure/reason rule.
_NO_WRITE_CASE = {'branch': 'research/weekly-storage-probe-v1',
 'canonical_log_sha256': '70468e2376c912f2c4bf5e738ae887ef283bdc4d2b9e08598c6e947119dbfd91',
 'diagnostic': {'diagnostic': {'error_type': 'StoreError',
                               'source_frames': [{'file': 'tools/audit_weekly_hosted_v1.py', 'line': 46},
                                                 {'file': 'nfl_lab/audit_weekly_hosted_v1.py', 'line': 1764},
                                                 {'file': 'nfl_lab/audit_weekly_hosted_v1.py', 'line': 455},
                                                 {'file': 'nfl_lab/audit_weekly_hosted_v1.py', 'line': 606},
                                                 {'file': 'nfl_lab/audit_weekly_hosted_v1.py', 'line': 114}]},
                'fits': 0,
                'public_release': False,
                'reason': 'UNRECOVERED_PRIOR_FAILED_DISPATCH_NO_WRITE',
                'state': 'FAILED_RETAINED',
                'successful_forecast': False},
 'job_api_id': 124701874519,
 'jobs_projection_sha256': 'd802209e61538845eb6a4af24555806266d410f8fd2eb95aeade0c7422405070',
 'namespace_origin_run_id': '41246356215',
 'run_id': '41256899348',
 'source_sha': 'b4ef09b5f4e09d5c861d55507952579379c87f9a',
 'sources': {'.github/workflows/lab.yml': {'bytes': 69727,
                                           'sha256': '2e29390bb8bfc4ca9919618d9a1facd094e70496c58c09103f626bd38a850384'},
             'nfl_lab/audit_weekly_hosted_v1.py': {'bytes': 130824,
                                                   'sha256': 'ab0f6a3b1968bb3a305797d954f765c194b2096619b7a60fa9b0daf784effc0f'},
             'tools/audit_weekly_hosted_v1.py': {'bytes': 2949,
                                                 'sha256': '09e1c8746c3b117a55bcec6faae3e3da9b42a4196a3db57dae317edb5bf923eb'}}}


def _nw_need(ok, code):
    if not ok:
        from .private_draft_store import StoreError
        raise StoreError(code)


def _nw_canonical_log(body):
    try: text=body.decode('utf-8-sig').replace('\r\n','\n')
    except UnicodeError:
        _nw_need(False,'NO_WRITE_LOG_UTF8')
    _nw_need('\r' not in text,'NO_WRITE_LOG_BARE_CR')
    lines=text.split('\n')
    while lines and not lines[-1].strip(' \t'):lines.pop()
    return ('\n'.join(lines)+'\n').encode()


def _nw_jobs(value):
    fields=('id','run_id','head_sha','name','status','conclusion','started_at','completed_at')
    step=('number','name','status','conclusion','started_at','completed_at')
    _nw_need(type(value) is dict and type(value.get('jobs')) is list
        and type(value.get('total_count')) is int and value['total_count']==len(value['jobs'])==20,
        'NO_WRITE_COMPLETE_ORIGINAL_JOB_LIST')
    _nw_need(all(type(j) is dict and type(j.get('id')) is int and type(j.get('steps',[])) is list
        and all(type(s) is dict for s in j.get('steps',[])) for j in value['jobs']),
        'NO_WRITE_ORIGINAL_JOB_SHAPE')
    return dict(total_count=value['total_count'],jobs=sorted([
        dict(**{k:j.get(k) for k in fields},steps=[{k:s.get(k) for k in step} for s in j.get('steps',[])])
        for j in value['jobs']],key=lambda j:j['id']))


def _nw_json(client,url,evidence,cap=256<<10):
    # Only callers below can choose these fixed subject/source routes.
    client.allowed.add(url)
    status,headers,body=client.request(url,cap=cap)
    _nw_need(status==200 and headers.get('x-ratelimit-remaining')!='0'
        and 'retry-after' not in headers,'NO_WRITE_ACTUAL_METADATA_RESPONSE')
    try:value=strict_json(body)
    except (ValueError,TypeError,RecursionError):
        _nw_need(False,'NO_WRITE_STRICT_METADATA_JSON')
    evidence.setdefault(url,[]).append(dict(sha256=sha(body),bytes=len(body)))
    return value


def _nw_log(client,url):
    # GitHub's one-use log redirect is fetched without any GitHub credential.
    # Count the anonymous hop in the SAME existing40-call/40MiB/180s scope.
    from urllib.parse import urlsplit,parse_qs
    from urllib.request import Request
    from . import private_draft_store as store
    client.allowed.add(url)
    status,headers,body=client.request(url,cap=128<<10)
    if status==200:return body
    _nw_need(status==302,'NO_WRITE_LOG_API_STATUS')
    target=headers.get('location','')
    try:parts=urlsplit(target);port=parts.port;query=parse_qs(parts.query)
    except ValueError:_nw_need(False,'NO_WRITE_LOG_REDIRECT_SCOPE')
    _nw_need(parts.scheme=='https' and not parts.username and not parts.password and not port
        and not parts.fragment and re.fullmatch(r'productionresultssa[0-9]+\.blob\.core\.windows\.net',parts.hostname or '')
        and parts.path.startswith('/actions-results/') and parts.path.endswith('/job-logs.txt')
        and query.get('sig'),'NO_WRITE_LOG_REDIRECT_SCOPE')
    _nw_need(client.calls<store.MAX_CALLS==40 and client.clock()-client.started<=180,
        'NO_WRITE_LOG_CALL_OR_TIME_CAP')
    client.calls+=1
    try:
        with store.exchange_deadline(client.real):
            # No Authorization, Cookie, source token or forwarded API headers.
            response=client.transport(Request(target,headers={'Accept':'text/plain',
                'User-Agent':'weekly-private-draft-store-v2'},method='GET'),
                min(20.,max(.001,180-(client.clock()-client.started))))
            with response:
                status=response.status;headers={k.lower():v for k,v in response.headers.items()}
                length=headers.get('content-length')
                _nw_need(length is None or length.isdigit() and int(length)<=128<<10,'NO_WRITE_LOG_RESPONSE_CAP')
                body=response.read(min((128<<10)+1,store.TRANSFER_CAP-client.transferred+1))
    except store.StoreError:raise
    except Exception:
        _nw_need(False,'NO_WRITE_LOG_TRANSPORT_FAILED')
    client.transferred+=len(body)
    _nw_need(status==200 and len(body)<=128<<10 and client.transferred<=store.TRANSFER_CAP
        and client.clock()-client.started<=180,'NO_WRITE_LOG_RESPONSE_OR_TRANSFER_CAP')
    return body


def no_write_failures(runner,unknown):
    """Fresh exact-case proof only; every other unknown failure stays unknown."""
    from datetime import datetime,timezone,timedelta
    from pathlib import Path
    import base64
    from . import audit_weekly_hosted_v1 as hosted,private_draft_store as store,audit_weekly_template_v1 as template
    from . import audit_weekly_controller_v1 as controller
    a=_NO_WRITE_CASE
    if runner.go.get('schema_version')!=ROOT_V5 or len(unknown)!=1 or unknown[0].get('id')!=int(a['run_id']):return unknown
    _nw_need(type(runner) is hosted.Runner and (runner.go.get('effective_epoch') or {}).get('schema_version')
        in {template.RECURRING_V5,template.REGISTRATION_RECOVERY},
        'NO_WRITE_V5_NATIVE_SCOPE_REQUIRED')
    _nw_need(runner.go['qualified_runtime']['binding']['origin_run_id']==a['namespace_origin_run_id'],
        'NO_WRITE_EXACT_ORIGINAL_NAMESPACE_CENSUS')
    client=runner.pending_metadata_client()
    _nw_need(client.operation=='metadata' and client.job.get('run_authenticated') is True and not client.posts,
        'NO_WRITE_CURRENT_GET_ONLY_QUALIFIED_SCOPE')
    initial=(client.calls,client.transferred);evidence={}
    base=store.API+'/actions/runs/'+a['run_id'];jobs_url=base+'/jobs?per_page=100&page=1'
    run=_nw_json(client,base,evidence);jobs=_nw_jobs(_nw_json(client,jobs_url,evidence))
    _nw_need(run.get('id')==int(a['run_id']) and run.get('head_sha')==a['source_sha']
        and run.get('head_branch')==a['branch'] and run.get('repository',{}).get('full_name')==store.REPO
        and run.get('head_repository',{}).get('full_name')==store.REPO and run.get('path')==controller.WORKFLOW
        and run.get('event')=='workflow_dispatch' and type(run.get('run_attempt')) is int and run['run_attempt']==1
        and run.get('status')=='completed' and run.get('conclusion')=='failure'
        and controller.actor(run.get('actor'),controller.OWNER)
        and controller.actor(run.get('triggering_actor'),controller.OWNER),'NO_WRITE_EXACT_FINISHED_GHA_OWNER_RUN')
    _nw_need(sha(canonical(jobs))==a['jobs_projection_sha256'],'NO_WRITE_EXACT_ALL_JOBS_AND_STEPS')
    active=[j for j in jobs['jobs'] if j['id']==a['job_api_id']]
    _nw_need(len(active)==1 and active[0]['name']=='audit-weekly-produce-v1'
        and active[0]['status']=='completed' and active[0]['conclusion']=='failure'
        and all(j['status']=='completed' and j['conclusion']=='skipped' for j in jobs['jobs'] if j['id']!=a['job_api_id']),
        'NO_WRITE_ALL_OTHER_JOBS_MUST_BE_SKIPPED')
    job=active[0]
    _nw_need(controller.utc(job['started_at'])<=controller.utc(job['completed_at'])
        <=controller.utc(run['updated_at'])<controller.utc(runner.go['issued_at_utc']),
        'NO_WRITE_FINISHED_BEFORE_NEW_OWNER_ROOT')
    for path,expected in a['sources'].items():
        url=store.API+'/contents/'+path+'?ref='+a['source_sha'];value=_nw_json(client,url,evidence)
        _nw_need(type(value) is dict and value.get('type')=='file' and value.get('path')==path
            and value.get('encoding')=='base64' and type(value.get('size')) is int
            and value['size']==expected['bytes']<=128<<10,'NO_WRITE_EXACT_FROZEN_SOURCE_METADATA')
        try:body=base64.b64decode(value['content'].replace('\n',''),validate=True)
        except (ValueError,TypeError):_nw_need(False,'NO_WRITE_SOURCE_BASE64')
        _nw_need(len(body)==value['size'] and sha(body)==expected['sha256']
            and controller.blob_sha(body)==value.get('sha'),'NO_WRITE_FRESH_FROZEN_SOURCE_BYTES')
    raw=_nw_log(client,store.API+'/actions/jobs/'+str(a['job_api_id'])+'/logs')
    log=_nw_canonical_log(raw)
    _nw_need(sha(log)==a['canonical_log_sha256'],'NO_WRITE_EXACT_CANONICAL_COMPLETE_LOG')
    diagnostics=[]
    for line in log.decode().splitlines():
        if ' {"diagnostic":' in line:
            stamp,doc=line.split(' ',1)
            try:value=strict_json(doc)
            except (ValueError,TypeError):_nw_need(False,'NO_WRITE_LOG_DIAGNOSTIC_JSON')
            diagnostics.append((controller.utc(stamp),value))
    _nw_need(len(diagnostics)==2 and all(v==a['diagnostic'] for _,v in diagnostics),
        'NO_WRITE_BOTH_ORIGINAL_CONSTRUCTOR_FAILURES_REQUIRED')
    for (stamp,_),number in zip(diagnostics,(7,8)):
        steps=[s for s in job['steps'] if s['number']==number]
        _nw_need(len(steps)==1 and steps[0]['conclusion']=='failure'
            and controller.utc(steps[0]['started_at'])<=stamp<controller.utc(steps[0]['completed_at'])+timedelta(seconds=1),
            'NO_WRITE_PRODUCE_AND_PRESERVE_STEP_CLOCKS')
    fresh_run=_nw_json(client,base,evidence);fresh_jobs=_nw_jobs(_nw_json(client,jobs_url,evidence))
    controller.stable(run,fresh_run)
    _nw_need(jobs==fresh_jobs and not client.posts and client.calls<=store.MAX_CALLS==40
        and client.transferred<=store.TRANSFER_CAP and client.clock()-client.started<=180,
        'NO_WRITE_IMMUTABLE_FINISHED_METADATA')
    proof=dict(schema_version='weekly-mae-exact-no-write-receipt-v1',subject_run_id=a['run_id'],subject_job_id=a['job_api_id'],
        source_sha=a['source_sha'],raw_log_sha256=sha(raw),raw_log_bytes=len(raw),canonical_log_sha256=sha(log),
        canonical_log_bytes=len(log),jobs_projection_sha256=sha(canonical(jobs)),metadata=evidence,
        private_POSTs=0,produce_and_preserve_rejected_before_action=True,unknown_other_failures_waived=False,
        scope_calls=client.calls,scope_bytes=client.transferred,proof_calls=client.calls-initial[0],proof_bytes=client.transferred-initial[1],
        actual_verified_at=datetime.now(timezone.utc).isoformat())
    # Fresh readback receipt only; no local file or JSON PASS can admit reuse.
    ref=hosted.write(runner.storage,Path(runner.root)/'metadata'/('NO_WRITE_'+a['run_id']+'_'+client.process+'.json'),proof)
    runner.no_write_receipts=[ref]
    return []
