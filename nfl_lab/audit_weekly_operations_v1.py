"""Closed metadata composition for the existing weekly writer.

This module never acquires a source, loads a model, reads outcome bodies, posts,
dispatches or publishes. The current hosted parent authenticates each input and
supplies the live grading callback. Repeated refreshes retain their original
primary assignment instead of creating additional football observations.
"""
from __future__ import annotations

from copy import deepcopy
import csv
from datetime import datetime, timedelta, timezone
import io
from pathlib import Path
import re
from zoneinfo import ZoneInfo

from . import audit_weekly_archive_v1 as archive, audit_weekly_epoch_v1 as epoch
from . import audit_weekly_grade_v1 as grade, audit_weekly_resume_v1 as resume
from . import gha_private_checkpoint as cp, private_draft_store as store
from . import state
from .owned_reference_batch import validate_owned_references

VERSION = "audit-weekly-operations-v1"
CONTEXT_SCHEMA = "audit-weekly-recurring-v1-context"
CONTEXT_KEYS = {"schema_version", "controller_context", "previous_capture"}
CONTEXT_V2 = "audit-weekly-recurring-v2-context"
CONTEXT_V3 = "audit-weekly-recurring-v3-context"
CONTEXT_V4 = "audit-weekly-recurring-v4-context"
CONTEXT_V5 = "audit-weekly-recurring-v5-context"
FILES = ("nfl_lab/audit_weekly_operations_v1.py", "tests/test_audit_weekly_operations_v1.py")
STREAM = "weekly-corrected-primary-player-game-v1"
_FIRST_PRIMARY_KEY = object()
_RECOVERY_KEY = object()
PLAN_KEYS = {"schema_version", "kind", "reason", "epoch_sha256", "canonical_choice_sha256",
    "target_choice_sha256", "season", "week", "planned_at", "history_sha256", "future_game_ids",
    "capture_allowed", "publication_allowed", "current_values_used", "fits"}


class OperationsError(ValueError):
    pass


def require(value, code):
    if not value:
        raise OperationsError(code)


def context(value):
    require(type(value) is dict and value.get("schema_version") in {CONTEXT_SCHEMA,CONTEXT_V2,CONTEXT_V3,CONTEXT_V4,CONTEXT_V5}
        and set(value)==(CONTEXT_KEYS if value["schema_version"]==CONTEXT_SCHEMA
            else CONTEXT_KEYS|{"previous_checkpoint"}|({"plan"} if value["schema_version"] in {CONTEXT_V3,CONTEXT_V4,CONTEXT_V5} else set())
                | ({"pending_post_recovery"} if value["schema_version"]==CONTEXT_V5 else set())),
        "CLOSED_RECURRING_CONTEXT_REQUIRED")
    previous = value["previous_capture"]
    require(type(previous) is dict and set(previous) == {"feed_sha256", "receipt_sha256"}
        and all(type(v) is str and store.HASH.fullmatch(v) for v in previous.values()),
        "EXACT_PRIOR_SUCCESSFUL_CAPTURE_LOCATOR_REQUIRED")
    require(value["controller_context"] is None or type(value["controller_context"]) is dict,
        "EXPLICIT_OWNER_OR_SEALED_CONTROLLER_CONTEXT")
    if value["schema_version"] in {CONTEXT_V2,CONTEXT_V3,CONTEXT_V4,CONTEXT_V5}:
        checkpoint=value["previous_checkpoint"]
        modern=value["schema_version"] in {CONTEXT_V4,CONTEXT_V5} and type(checkpoint) is dict and checkpoint.get("schema_version") is not None
        if modern:
            from .audit_weekly_grade_history_v1 import locator_reference
            locator_reference(checkpoint)
        require(modern or checkpoint is None or type(checkpoint) is dict and set(checkpoint)=={"sha256"}
            and type(checkpoint["sha256"]) is str and store.HASH.fullmatch(checkpoint["sha256"]),
            "EXACT_REGISTERED_PREVIOUS_GRADING_SIDECAR_HASH")
    if value["schema_version"] in {CONTEXT_V4,CONTEXT_V5}:
        from .audit_weekly_grade_history_v1 import validate_root_plan
        validate_root_plan(value["plan"])
    if value["schema_version"]==CONTEXT_V5:
        from .audit_weekly_template_v1 import validate_pending_recovery, first_primary_context, failed_first_recovery_context
        validate_pending_recovery(value['pending_post_recovery'])
        first_primary_context(value)
        failed_first_recovery_context(value)
    if value["schema_version"] == CONTEXT_V3:
        plan = value["plan"]
        require(type(plan) is dict and set(plan) == {"kind", "season", "week"}
            and plan["kind"] in {"GRADE_ONLY", "FUTURE_CAPABLE"}
            and type(plan["season"]) is int and 2019 <= plan["season"] <= 2100
            and type(plan["week"]) is int and 1 <= plan["week"] <= 18,
            "CLOSED_ROOT_RECURRING_PLAN_REQUIRED")
    return deepcopy(value)


class FirstPrimaryAbsence:
    """Current-process actual GET evidence, never a supplied empty-history flag."""
    def __init__(self, document, root, client, authenticate, clock, key, *, recovery=False):
        require(key is _FIRST_PRIMARY_KEY, 'LIVE_FIRST_PRIMARY_ABSENCE_REQUIRED')
        self.document=deepcopy(document);self._sha=state.digest(self.document)
        self.root_sha256=state.digest(root);self.client=client
        self.identity=cp.client_identity(client);self.process=store.process_identity()
        self.authenticate,self.clock=authenticate,clock
        self.recovery=recovery

    def verify(self, root):
        from . import audit_weekly_template_v1 as template
        require(state.digest(self.document)==self._sha and state.digest(root)==self.root_sha256
            and self.process==store.process_identity() and self.identity==cp.client_identity(self.client),
            'FIRST_PRIMARY_ABSENCE_INTEGRITY')
        scope=template.failed_first_recovery_root(root) if self.recovery else template.first_primary_root(root)
        require(scope is not None
            and self.document['schema_version']==(template.FAILED_FIRST_RECOVERY if self.recovery else template.FIRST_PRIMARY)+'-absence'
            and self.client.binding==root['qualified_runtime']['binding']
            and self.client.source_sha==root['source_sha']
            and state.utc(root['issued_at_utc'])<=state.utc(self.document['observed_at'])
            <=state.utc(self.clock())<min(state.utc(root['expires_at_utc']),state.utc(root['effective_epoch']['plan']['deadline_utc']))
            and self.authenticate() is None, 'LIVE_OWNER_FIRST_PRIMARY_ABSENCE_REQUIRED')
        return self

    def __reduce__(self):
        raise OperationsError('FIRST_PRIMARY_ABSENCE_CANNOT_BE_SERIALIZED')


def first_primary_absence(client, root, *, authenticate, clock=state.now_utc):
    return _primary_absence(client,root,authenticate=authenticate,clock=clock)


def _primary_absence(client, root, *, authenticate, clock, recovery=False):
    """Six bounded GETs: immutable path absence, no deleted history, stable head.

    Only metadata is read. Neither an empty local snapshot nor a 404 without
    an authenticated existing state commit establishes an empty primary lane.
    The caller enforces the live OWNER proof before every exchange.
    """
    from . import audit_weekly_template_v1 as template
    scope=template.failed_first_recovery_root(root) if recovery else template.first_primary_root(root)
    require(scope is not None and callable(authenticate),
        'EXPLICIT_OWNER_FIRST_PRIMARY_REQUIRED')
    require(client.binding==root['qualified_runtime']['binding'] and client.source_sha==root['source_sha']
        and client.job.get('run_authenticated') is True and client.job.get('execution_lane')=='github_actions',
        'FIRST_PRIMARY_ACTUAL_CURRENT_CLIENT_REQUIRED')
    observations=[]
    def get(path, status=200):
        require(authenticate() is None and state.utc(root['issued_at_utc'])<=state.utc(clock())
            <min(state.utc(root['expires_at_utc']),state.utc(root['effective_epoch']['plan']['deadline_utc'])),
            'LIVE_OWNER_FIRST_PRIMARY_ABSENCE_REQUIRED')
        url=store.API+path;client.allowed.add(url)
        observed,headers,body=client.request(url,method='GET',cap=store.META_CAP)
        require(observed==status and headers.get('x-ratelimit-remaining')!='0'
            and 'retry-after' not in headers, 'FIRST_PRIMARY_METADATA_ABSENCE_OR_RATE_FAILED')
        value=cp.strict_json(body)
        observations.append(dict(path=path,status=observed,sha256=store.sha(body)))
        return value
    def head():
        value=get('/git/ref/heads/lab-state')
        require(type(value) is dict and value.get('ref')=='refs/heads/lab-state'
            and type(value.get('object')) is dict and value['object'].get('type')=='commit'
            and type(value['object'].get('sha')) is str and re.fullmatch(r'[a-f0-9]{40}',value['object']['sha']),
            'ACTUAL_FIRST_PRIMARY_STATE_COMMIT_REQUIRED')
        return value['object']['sha']
    initial=head()
    for path in ('state/controller-v1/grade-checkpoints','state/controller-v1/history-v2'):
        absent=get('/contents/'+path+'?ref='+initial,404)
        require(type(absent) is dict and absent.get('message')=='Not Found',
            'ACTUAL_FIRST_PRIMARY_PATH_ABSENCE_REQUIRED')
        census=get('/commits?sha='+initial+'&path='+path+'&per_page=1&page=1')
        require(type(census) is list and not census, 'PRIOR_PRIMARY_HISTORY_MAY_NOT_BE_RESET')
    require(head()==initial, 'FIRST_PRIMARY_STATE_CHANGED_NO_WRITE')
    version=template.FAILED_FIRST_RECOVERY if recovery else template.FIRST_PRIMARY
    proof=FirstPrimaryAbsence(dict(schema_version=version+'-absence',state_head=initial,
        observations=observations,observed_at=state.utc(clock()).isoformat()),root,client,authenticate,clock,_FIRST_PRIMARY_KEY,
        recovery=recovery)
    return proof.verify(root)


def first_future_plan(registered, original, full_schedule, root, absence, *, authenticate,
        cutoff_lead_seconds, relocated_replays=(), clock=state.now_utc):
    return _future_startup_plan(registered,original,full_schedule,root,absence,authenticate=authenticate,
        cutoff_lead_seconds=cutoff_lead_seconds,relocated_replays=relocated_replays,clock=clock)


def _future_startup_plan(registered, original, full_schedule, root, absence, *, authenticate,
        cutoff_lead_seconds, relocated_replays=(), clock=state.now_utc, recovery=None):
    """Manual first full Week8 primary, preserving the exact existing epoch.

    This entry point is separate from recurring_plan's unchanged durable-week
    guard. Absence is actual GET evidence, not a synthetic DurableHistory.
    """
    from . import audit_weekly_template_v1 as template, weekly_generic_producer as generic
    spec=template.failed_first_recovery_root(root) if recovery is not None else template.first_primary_root(root)
    at=state.utc(clock())
    if recovery is not None:
        require(type(recovery) is FailedFirstRecovery,'LIVE_FAILED_FIRST_RECOVERY_REQUIRED')
        recovery.verify(root)
    require(spec is not None and type(absence) is FirstPrimaryAbsence and absence.recovery is (recovery is not None),
        'LIVE_FIRST_PRIMARY_ABSENCE_REQUIRED')
    absence.verify(root)
    require(type(registered) is epoch.RegisteredEpoch and type(original) is epoch.EpochChoice
        and registered.epoch.sha256==spec['retained_epoch_sha256']
        and original.sha256==spec['retained_choice_sha256']
        and (original.document['slate']['season'],original.document['slate']['week'])==(2026,7),
        'EXACT_RETAINED_COUNT7_EPOCH_AND_CHOICE_REQUIRED')
    original.verify(registered,at);resume._calendar_fields(full_schedule)
    plan=root['effective_epoch']['plan']
    require(all((r['season'],r['week'],r['game_type'])==(2026,8,'REG') for r in full_schedule)
        and type(cutoff_lead_seconds) is int and 0<cutoff_lead_seconds<=86400,
        'FIRST_PRIMARY_FULL_FUTURE_WEEK8_REQUIRED')
    cutoffs={r['game_id']:(state.utc(r['kickoff_utc'])-timedelta(seconds=cutoff_lead_seconds)).isoformat() for r in full_schedule}
    slate=generic.prepare_slate(full_schedule,season=2026,week=8,game_cutoffs=cutoffs,now=at)
    require(state.digest(full_schedule)==plan['calendar_sha256'] and cutoffs==plan['game_cutoffs']
        and at<state.utc(plan['deadline_utc'])==min(map(state.utc,cutoffs.values()))
        and at<state.utc(slate['weekly_deadline_utc'])
        and slate['elapsed_games']==0, 'FIRST_PRIMARY_ACTUAL_FULL_WEEK_DEADLINE_REQUIRED')
    grade._authenticate(authenticate,'NEXT_FULL_WEEK_SLATE_BEFORE_VALUES',dict(slate=slate,full_schedule=full_schedule),at)
    empty=dict(schema_version=epoch.VERSION+'-history',epoch_sha256=registered.epoch.sha256,
        legacy_history_binding=deepcopy(registered.epoch.origin['history_binding']),
        bundle=dict(schema_version=grade.selector.VERSION,offers=[],forecasts=[],outcomes=[],decisions=[],weeks=[]))
    choice=epoch.select_next_week(registered,empty,slate,original,relocated_replays=relocated_replays,clock=lambda:at)
    if recovery is not None:
        projection=lambda c:[(s['policy'],s['primary_metric'],s['members']) for s in c.document['choice']['selections']]
        require(projection(choice)==projection(original),'RECOVERY_EXACT_ORIGINAL_STARTUP_METHODS_REQUIRED')
    execution=dict(schema_version=VERSION+'-execution-plan',kind='FUTURE_CAPTURE',
        reason='OWNER_FAILED_FIRST_RECOVERY_NEW_FUTURE_ISSUE' if recovery is not None else 'OWNER_FIRST_FUTURE_PRIMARY_BEFORE_VALUES',epoch_sha256=registered.epoch.sha256,
        canonical_choice_sha256=original.sha256,target_choice_sha256=choice.sha256,season=2026,week=8,
        planned_at=at.isoformat(),history_sha256=None,future_game_ids=sorted(cutoffs),
        capture_allowed=True,publication_allowed=True,current_values_used=False,fits=0)
    require(set(execution)==PLAN_KEYS, 'CLOSED_RECURRING_EXECUTION_PLAN')
    return choice,execution


class FailedFirstRecovery:
    """Current-process GET evidence; saved diagnostics cannot grant recovery."""
    def __init__(self,document,root,client,authenticate,clock,key,*,claim_reader):
        require(key is _RECOVERY_KEY,'LIVE_FAILED_FIRST_RECOVERY_REQUIRED')
        self.document=deepcopy(document);self._sha=state.digest(document)
        self.root_sha256=state.digest(root);self.client=client;self.identity=cp.client_identity(client)
        self.process=store.process_identity();self.authenticate=authenticate;self.clock=clock
        self.clients=(client,claim_reader)

    def verify(self,root):
        from . import audit_weekly_template_v1 as template
        spec=template.failed_first_recovery_root(root)
        require(spec is not None and state.digest(root)==self.root_sha256
            and state.digest(self.document)==self._sha and self.process==store.process_identity()
            and self.identity==cp.client_identity(self.client) and self.client.source_sha==root['source_sha']
            and self.client.binding==root['qualified_runtime']['binding']
            and len(self.clients)==2 and self.clients[0] is not self.clients[1]
            and all(cp.client_identity(c)==self.identity and c.binding==self.client.binding for c in self.clients)
            and self.document['failed_root_go_sha256']==spec['failed_root_go_sha256']
            and state.utc(root['issued_at_utc'])<=state.utc(self.document['verified_at'])<=state.utc(self.clock())
            <min(state.utc(root['expires_at_utc']),state.utc(root['effective_epoch']['plan']['deadline_utc']))
            and self.authenticate() is None,'LIVE_FAILED_FIRST_RECOVERY_INTEGRITY')
        return self

    def __reduce__(self):
        raise OperationsError('FAILED_FIRST_RECOVERY_CANNOT_BE_SERIALIZED')


def authenticate_failed_first_recovery(client,root,*,authenticate,claim_reader,clock=state.now_utc):
    """GET only: original Core, native claim bytes/manifest, journals and jobs.

    The pending handoff selects the Core. Its authenticated attachments supply
    the old Root and parent identity, so the new Root carries no duplicate Root
    or native artifact descriptors. No forecast, outcome or model is opened.
    """
    import base64
    from . import audit_weekly_template_v1 as template,audit_weekly_hosted_v1 as hosted
    spec=template.failed_first_recovery_root(root)
    require(spec is not None and callable(authenticate) and authenticate() is None
        and client.binding==root['qualified_runtime']['binding'] and client.source_sha==root['source_sha']
        and client.job.get('run_authenticated') is True,'LIVE_OWNER_RECOVERY_METADATA_CLIENT_REQUIRED')
    pending=template.pending_recovery(root)
    handoff=next(h for h in pending['handoffs'] if h['root_go_sha256']==spec['failed_root_go_sha256'])
    assets,_=client.inventory();evidence={}
    records=hosted.authenticated_pending_records(client,handoff,assets,before=root['issued_at_utc'],_evidence=evidence)
    require(all(r in pending['pending_reservations'] for r in records),'RECOVERY_COMPLETE_ORIGINAL_POST_ACCOUNTING')
    old=evidence['root'];original=template.first_primary_root(old)
    keys={'retained_epoch_sha256','retained_choice_sha256','retained_root_go_sha256','claim_binding_sha256'}
    require(original is not None and all(original[k]==spec[k] for k in keys)
        and old['effective_epoch']['plan']==root['effective_epoch']['plan']
        and old['effective_epoch']['previous_capture']==root['effective_epoch']['previous_capture']
        and old.get('cutoff_lead_seconds',900)==root.get('cutoff_lead_seconds',900)
        and state.utc(old['issued_at_utc'])<state.utc(root['issued_at_utc'])
        and (evidence['run'].get('actor',{}).get('login'),evidence['run'].get('actor',{}).get('id'))==('NickNicky19',208912933),
        'EXACT_FAILED_FIRST_OWNER_ROOT_STARTUP_AND_CUTOFFS')
    failed=evidence['failed_job'];readers=[j for j in evidence['jobs'] if j.get('name')==old['jobs']['restore']]
    require(len(readers)==1,'UNIQUE_INDEPENDENT_CORE_READER_REQUIRED');reader=readers[0]
    require(reader.get('id')!=failed.get('id') and reader.get('run_id')==failed.get('run_id')
        and reader.get('head_sha')==old['source_sha'] and reader.get('status')=='completed'
        and reader.get('conclusion')=='success'
        and state.utc(failed['completed_at'])<=state.utc(reader['started_at'])<=state.utc(reader['completed_at'])
        <=state.utc(root['issued_at_utc']),'ACTUAL_INDEPENDENT_FAILED_CORE_READER_REQUIRED')
    controls=evidence['controls']
    required={'file-graph','secondary-preservation-failure','complete-auxiliary-controls',
        'phase-02','phase-06','phase-07','phase-08','phase-09'}
    require(required<=set(controls),'COMPLETE_ORIGINAL_ARCHIVE_FAILURE_CONTROLS_REQUIRED')
    def control(label):return cp.strict_json(controls[label][1])
    for label,expected in [('phase-02','FIRST_FUTURE_PRIMARY_PREVALUE_METADATA_READY_LOCAL'),
            ('phase-06','PRIVATE_CURRENT_EPOCH_CAPTURE_COMPLETE'),('phase-07','ORIGINAL_R0_CAPTURE_COMPLETE_PRIVATE')]:
        d=control(label)
        require(d.get('exit_code')==0 and d.get('status',{}).get('state')==expected
            and d['status'].get('fits')==0 and d['status'].get('public_release') is False,
            'ORIGINAL_PREVALUE_CAPTURE_R0_SUCCESS_CONTROLS_REQUIRED')
    for label in ('phase-08','phase-09','secondary-preservation-failure'):
        d=control(label);s=d.get('status',d)
        require(s.get('reason')=='SINGLE_FILE_BUNDLE_CAP' and s.get('successful_forecast') is False
            and s.get('public_release') is False,'ORIGINAL_FAILED_ARCHIVE_GAP_REQUIRED')
    secondary=control('secondary-preservation-failure')
    require(secondary.get('original_failure_replaced') is False
        and secondary.get('partial_forecast_durability_established') is False,'FAILED_FORECAST_BODIES_STAY_MISSING')
    auxiliary=control('complete-auxiliary-controls')
    require(auxiliary.get('schema_version')==hosted.VERSION+'-complete-auxiliary-controls'
        and type(auxiliary.get('files')) is list,'ORIGINAL_PARENT_CONTROL_REQUIRED')
    parents=[v for v in auxiliary['files'] if v.get('relative_path')=='PARENT_STARTED.json']
    require(len(parents)==1,'UNIQUE_ORIGINAL_PARENT_CONTROL_REQUIRED');parent=parents[0]
    raw=base64.b64decode(parent['body_base64'],validate=True)
    require(len(raw)==parent['bytes']<=64<<10 and store.sha(raw)==parent['sha256'],'EXACT_ORIGINAL_PARENT_CONTROL_BYTES')
    start=cp.strict_json(raw);identity=start.get('actual_identity',{})
    require(identity.get('run_id')==str(failed['run_id']) and identity.get('source_sha')==old['source_sha']
        and identity.get('api_job_id')==failed['id'] and identity.get('job_id')==old['jobs']['produce']
        and identity.get('workflow_ref')==old['workflow_ref'] and identity.get('repository')==store.REPO
        and identity.get('run_attempt')==1 and store.HASH.fullmatch(str(identity.get('process_identity')))
        and state.utc(old['issued_at_utc'])<=state.utc(start['actual_started_at'])<=state.utc(failed['completed_at']),
        'ACTUAL_ORIGINAL_CLAIM_PRODUCER_PROCESS_REQUIRED')
    require(callable(claim_reader) and authenticate() is None,'FRESH_RECOVERY_CLAIM_READER_REQUIRED')
    claims=claim_reader()
    require(claims is not client and cp.client_identity(claims)==cp.client_identity(client)
        and claims.binding==client.binding and claims.job.get('run_authenticated') is True,
        'DISTINCT_CURRENT_RECOVERY_CLAIM_READER_REQUIRED')
    claims.draft();assets,_=claims.inventory()
    claim=store.canonical(template.first_primary_claim(old));claim_sha=store.sha(claim)
    payload=dict(schema_version='weekly-private-payload-v2',payload_kind='runtime_manifest',format='json',
        bytes=len(claim),sha256=claim_sha,source_policy_sha256=cp.POLICY_SHA)
    def asset(name,size,digest):
        found=[a for a in assets if a.get('name')==name]
        require(len(found)==1 and found[0].get('size')==size and found[0].get('state')=='uploaded'
            and found[0].get('digest')=='sha256:'+digest,'EXACT_ORIGINAL_CLAIM_ASSET_MEMBERSHIP')
        return found[0]
    blob=asset('blob-'+claim_sha+'.bin',len(claim),claim_sha)
    entry=dict(schema_version='weekly-private-restore-manifest-v2',payload=payload,payload_asset_id=blob['id'],
        payload_name=blob['name'],producer_process=identity['process_identity'],
        binding_sha256=state.digest(client.binding),writer_run_id=identity['run_id'])
    encoded=store.canonical(entry);manifest_sha=store.sha(encoded)
    manifest=asset('manifest-'+manifest_sha+'.json',len(encoded),manifest_sha)
    for a,digest in ((blob,claim_sha),(manifest,manifest_sha)):
        require(any(r['key']=='asset:'+a['name'] and r['bytes']==a['size'] and r['sha256']==digest for r in records),
            'ORIGINAL_CLAIM_POST_PAIR_REQUIRED')
    require(claims.read_asset(blob['id'],blob['name'],blob['size'],claim_sha)==claim
        and claims.read_asset(manifest['id'],manifest['name'],manifest['size'],manifest_sha)==encoded,
        'EXACT_ORIGINAL_FIRST_CLAIM_NATIVE_BYTES')
    claims.draft()
    graph=control('file-graph')
    require(graph.get('schema_version')==hosted.VERSION+'-failed-file-graph' and type(graph.get('files')) is list
        and len(graph['files'])<=1024,'ORIGINAL_FAILED_FILE_GRAPH_REQUIRED')
    choices=[f['reference'] for f in graph['files'] if f.get('relative_path')=='runtime/WEEKLY_CHOICE.json']
    require(len(choices)==1 and set(choices[0])=={'path','bytes','sha256'}
        and type(choices[0]['bytes']) is int and 0<choices[0]['bytes']<=epoch.CAP
        and store.HASH.fullmatch(str(choices[0]['sha256'])),'ORIGINAL_CHOICE_HASH_ONLY_GAP_REQUIRED')
    document=dict(schema_version=template.FAILED_FIRST_RECOVERY+'-verified',
        current_root_go_sha256=state.digest(root),
        failed_root_go_sha256=spec['failed_root_go_sha256'],failed_source_sha=old['source_sha'],
        original_claim_payload_sha256=claim_sha,original_claim_manifest_sha256=manifest_sha,
        original_core_payload_sha256=handoff['descriptor']['entry']['payload']['sha256'],
        original_controls_sha256={k:controls[k][0]['reference']['sha256'] for k in sorted(required)},
        original_week8_choice_commitment={k:choices[0][k] for k in ('bytes','sha256')},
        old_week8_choice_body_missing=True,old_forecast_bodies_missing=True,failed_capture_qualified=False,
        old_capture_state='FAILED',
        original_first_claim_retained=True,original_failed_job_id=failed['id'],original_reader_job_id=reader['id'],
        current=cp.client_identity(client),verified_at=state.utc(clock()).isoformat(),fits=0,public_release=False)
    return FailedFirstRecovery(document,root,client,authenticate,clock,_RECOVERY_KEY,claim_reader=claims).verify(root)


def failed_first_absence(client,root,recovery,*,authenticate,clock=state.now_utc):
    require(type(recovery) is FailedFirstRecovery,'LIVE_FAILED_FIRST_RECOVERY_REQUIRED')
    recovery.verify(root)
    return _primary_absence(client,root,authenticate=authenticate,clock=clock,recovery=True)


def failed_first_future_plan(registered,original,full_schedule,root,absence,recovery,**kwargs):
    return _future_startup_plan(registered,original,full_schedule,root,absence,recovery=recovery,**kwargs)


def validate_failed_first_gap(value, *, choice, epoch_sha256, root_go_sha256=None, producer=None):
    """Typed archived gap metadata; never a forecast or history observation."""
    from . import audit_weekly_template_v1 as template,weekly_durable_acceptance as acceptance
    keys={'schema_version','current_root_go_sha256','failed_root_go_sha256','failed_source_sha',
        'original_claim_payload_sha256','original_claim_manifest_sha256','original_core_payload_sha256',
        'original_controls_sha256','original_week8_choice_commitment','old_week8_choice_body_missing',
        'old_forecast_bodies_missing','failed_capture_qualified','old_capture_state','original_first_claim_retained',
        'original_failed_job_id','original_reader_job_id','current','verified_at','fits','public_release',
        'new_choice_sha256','new_capture_id','new_choice_actual_frozen_at','startup_COUNT7_choice_sha256',
        'scope','old_forecast_bodies_recovered','new_issue_only'}
    require(type(value) is dict and set(value)==keys and len(store.canonical(value))<=32<<10
        and value['schema_version']==template.FAILED_FIRST_RECOVERY+'-gap'
        and value['old_week8_choice_body_missing'] is value['old_forecast_bodies_missing'] is True
        and value['original_first_claim_retained'] is value['new_issue_only'] is True
        and value['failed_capture_qualified'] is value['old_forecast_bodies_recovered'] is value['public_release'] is False
        and value['old_capture_state']=='FAILED' and type(value['fits']) is int and value['fits']==0,
        'CLOSED_FAILED_FIRST_GAP_METADATA')
    for k in ('current_root_go_sha256','failed_root_go_sha256','original_claim_payload_sha256',
            'original_claim_manifest_sha256','original_core_payload_sha256','new_choice_sha256','new_capture_id',
            'startup_COUNT7_choice_sha256'):
        require(type(value[k]) is str and store.HASH.fullmatch(value[k]),'FAILED_FIRST_GAP_HASH_BINDINGS')
    require(type(value['failed_source_sha']) is str and re.fullmatch(r'[a-f0-9]{40}',value['failed_source_sha'])
        and all(type(value[k]) is int and 0<value[k]<10**20 for k in ('original_failed_job_id','original_reader_job_id'))
        and value['original_failed_job_id']!=value['original_reader_job_id'],'FAILED_FIRST_GAP_NATIVE_IDENTITIES')
    old=value['original_week8_choice_commitment'];controls=value['original_controls_sha256']
    require(type(old) is dict and set(old)=={'bytes','sha256'} and type(old['bytes']) is int
        and 0<old['bytes']<=epoch.CAP and type(old['sha256']) is str and store.HASH.fullmatch(old['sha256'])
        and type(controls) is dict and set(controls)=={'file-graph','secondary-preservation-failure','complete-auxiliary-controls',
            'phase-02','phase-06','phase-07','phase-08','phase-09'}
        and all(type(h) is str and store.HASH.fullmatch(h) for h in controls.values()),'FAILED_FIRST_GAP_CONTROL_COMMITMENTS')
    context=dict(schema_version=template.RECURRING_V5,previous_checkpoint=None,
        plan=dict(kind='FUTURE_CAPABLE',season=choice['slate']['season'],week=choice['slate']['week'],
            game_cutoffs=choice['slate']['game_cutoffs']),controller_context=value['scope'])
    scope=template.failed_first_recovery_context(context)
    require(scope is not None and scope['failed_root_go_sha256']==value['failed_root_go_sha256']
        and scope['retained_epoch_sha256']==epoch_sha256==choice['epoch_sha256']
        and scope['retained_choice_sha256']==value['startup_COUNT7_choice_sha256']
        and value['new_choice_sha256']==state.digest(choice)
        and state.utc(value['verified_at'])<=state.utc(value['new_choice_actual_frozen_at'])
        ==state.utc(choice['choice']['actual_frozen_at'])<min(map(state.utc,choice['slate']['game_cutoffs'].values())),
        'FAILED_FIRST_GAP_EXACT_NEW_PREVALUE_CHOICE')
    identity=acceptance.identity(value['current'])
    require(identity['execution_lane']=='github_actions' and identity['permission']=='write'
        and (root_go_sha256 is None or value['current_root_go_sha256']==root_go_sha256)
        and (producer is None or all(identity[k]==producer[k] for k in
            ('repository','run_id','run_attempt','source_sha','workflow_ref','job_id','api_job_id'))),
        'FAILED_FIRST_GAP_CURRENT_CAPTURE_IDENTITY')
    return deepcopy(value)


def roles_from_manifests(storage, restored_ref, *, authenticate):
    """Only qualified manifest metadata; the caller authenticates restoration."""
    require(callable(authenticate) and authenticate(dict(schema_version=VERSION+"-authentication-request",
        kind="QUALIFIED_CURRENT_MODEL_MANIFEST_METADATA", binding=deepcopy(restored_ref))) is True,
        "LIVE_CURRENT_MODEL_RESTORATION_AUTHENTICATION_REQUIRED")
    restored = archive.read_owned(storage, restored_ref)
    require(type(restored) is dict and set(restored) == resume.MODEL_KEYS
        and restored["state"] == "CROSS_RUN_EFFECTIVE18_RESTORED_AND_REPLAYED_PRIVATE"
        and restored["model_pairs"] == 18 and restored["fits"] == 0
        and restored["current_loader_replay"] is restored["model_artifact_durability"] is True,
        "QUALIFIED_CURRENT_EFFECTIVE18_METADATA_REQUIRED")
    refs = restored["models"]
    require(type(refs) is list and len(refs) == len(cp.JOBS), "EXACT18_MANIFEST_ROLE_CENSUS")
    validate_owned_references(storage, {ref["path"]:ref["sha256"] for ref in refs})
    result = {}
    for ref, (target, family, method) in zip(refs, cp.JOBS):
        manifest = cp.strict_json(cp.read_ref(ref, 256 << 10))
        require((manifest["category"]["target"], manifest["family"], manifest["method_id"])
            == (target, family, method), "EXACT_RETAINED_MANIFEST_ROLE_IDENTITY")
        category = manifest["category"]
        roles = {k:deepcopy(category[k]) for k in ("modeled_roles", "primary_roles")}
        require(all(type(v) is list and v and len(set(v)) == len(v)
            and all(type(r) is str and r in {"QB", "RB", "FB", "WR", "TE"} for r in v)
            for v in roles.values()) and set(roles["primary_roles"]) <= set(roles["modeled_roles"]),
            "ORIGINAL_MODELED_AND_PRIMARY_ROLES_REQUIRED")
        require(target not in result or result[target] == roles, "CANDIDATES_MUST_SHARE_REGISTERED_CATEGORY_ROLES")
        result[target] = roles
    require(set(result) == set(cp.TARGETS), "ALL_ELEVEN_ROLE_CONTRACTS_REQUIRED")
    return result


def calendar(raw, *, season, week):
    """Full calendar identities only; no score/workload/result field is used."""
    import pandas as pd
    from . import data, weekly_current_query as query
    require(type(raw) is bytes and 0 < len(raw) <= 8 << 20
        and type(season) is int and type(week) is int and 1 <= week <= 18,
        "BOUNDED_FULL_CURRENT_WEEK_CALENDAR_REQUIRED")
    zone = ZoneInfo("America/New_York")
    result = []
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    require(reader.fieldnames is not None and {"season", "week", "game_type", "game_id", "gameday", "gametime",
        "espn", "home_team", "away_team"} <= set(reader.fieldnames), "COMPLETE_CALENDAR_METADATA_COLUMNS_REQUIRED")
    for row in reader:
        if int(row["season"]) != season or int(row["week"]) != week or row["game_type"] != "REG":
            continue
        try:
            naive = datetime.fromisoformat(row["gameday"] + "T" + row["gametime"])
            require(naive.tzinfo is None, "LOCAL_SCHEDULE_CLOCK_REQUIRED")
            a, b = naive.replace(tzinfo=zone, fold=0), naive.replace(tzinfo=zone, fold=1)
            require(a.utcoffset() == b.utcoffset()
                and a.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None) == naive,
                "UNKNOWN_AMBIGUOUS_OR_NONEXISTENT_KICKOFF_FORBIDDEN")
            kickoff = a.astimezone(timezone.utc).isoformat()
        except (ValueError, TypeError):
            raise OperationsError("QUALIFIED_KICKOFF_CLOCK_REQUIRED") from None
        website_id = query._sleeper(row["espn"])
        home, away = data._team(pd.Series([row["home_team"], row["away_team"]], dtype=str)).tolist()
        require(type(row["game_id"]) is str and row["game_id"]
            and website_id is not None and re.fullmatch(r"[1-9][0-9]*", website_id)
            and type(home) is str and type(away) is str and home != away,
            "EXACT_CANONICAL_GAME_TEAMS_AND_ESPN_ID_REQUIRED")
        result.append(dict(season=season, week=week, game_type="REG", game_id=row["game_id"],
            website_game_id=website_id, kickoff_utc=kickoff, home=home, away=away))
    require(0 < len(result) <= 32 and len({r["game_id"] for r in result}) == len(result)
        and len({r["website_game_id"] for r in result}) == len(result),
        "COMPLETE_UNIQUE_FULL_WEEK_CALENDAR_REQUIRED")
    return sorted(result, key=lambda r:(r["kickoff_utc"], r["game_id"]))


def primary_population(registered, choice, roles, *, capture_id, authenticate,
        previous=None, clock=state.now_utc):
    """Register before values; an already assigned game stays with its capture."""
    at = clock()
    require(type(registered) is epoch.RegisteredEpoch and type(choice) is epoch.EpochChoice
        and type(capture_id) is str and store.HASH.fullmatch(capture_id), "CURRENT_TYPED_PRIMARY_POPULATION_REQUIRED")
    choice.verify(registered, at)
    require(set(roles) == set(cp.TARGETS), "EXACT_REGISTERED_ROLE_CATALOG_REQUIRED")
    old = {}
    if previous is not None:
        require(type(previous) in {grade.Snapshot, grade.DurableHistory}, "TYPED_PRIOR_GRADING_STATE_REQUIRED")
        previous.verify()
        require(previous.document["epoch_sha256"] == registered.epoch.sha256,
            "NO_PRIMARY_ASSIGNMENT_ACROSS_DIFFERENT_EPOCHS")
        for capture in previous.document["captures"]:
            pop = capture["population"]
            require(pop["role_catalog_sha256"] == state.digest(roles) and pop["stream_id"] == STREAM,
                "ORIGINAL_PRIMARY_ROLE_STREAM_MUST_REMAIN_FIXED")
            for gid, assigned in pop["assignments"].items():
                require(gid not in old or old[gid] == assigned, "NO_CONFLICTING_PRIMARY_CAPTURE_ASSIGNMENTS")
                old[gid] = assigned
    document = grade.population_template(registered, choice)
    document.update(state="ROOT_REGISTERED", stream_id=STREAM, registered_at=state.utc(at).isoformat(),
        role_catalog_sha256=state.digest(roles), assignments={gid:old.get(gid, capture_id)
            for gid in document["assignments"]})
    new = [gid for gid, assigned in document["assignments"].items() if assigned == capture_id]
    require(not new or len(new) == len(document["assignments"]),
        "MIXED_PRIMARY_AND_REFRESH_SCOPE_REQUIRES_EXPLICIT_RECONCILIATION")
    population = grade.bind_population(document, registered, choice, authenticate=authenticate, at=at)
    return population, dict(schema_version=VERSION+"-assignment", capture_id=capture_id,
        state="FIRST_PREVALUE_PRIMARY_CAPTURE" if new else "REFRESH_NOT_ANOTHER_PRIMARY_OBSERVATION",
        primary_game_ids=sorted(new), preserved_assignment_game_ids=sorted(set(document["assignments"])-set(new)),
        population_sha256=population.sha256, current_values_used=False, fits=0)


def recurring_plan(registered, original, full_schedule, *, authenticate, durable=None,
        cutoff_lead_seconds, relocated_replays=(), clock=state.now_utc):
    """Choose a closed execution path from authenticated calendar metadata.

    A grade-only plan carries the original choice unchanged and creates no
    issuance population. A later-week choice requires actual durable resolved
    history; an absent history never falls back to the legacy research anchor.
    The caller separately authenticates/restores original capture bytes.
    """
    at = state.utc(clock())
    require(type(registered) is epoch.RegisteredEpoch and type(original) is epoch.EpochChoice,
        "TYPED_RECURRING_EPOCH_AND_CANONICAL_CHOICE_REQUIRED")
    original.verify(registered, at)
    resume._calendar_fields(full_schedule)
    weeks = {(r["season"], r["week"]) for r in full_schedule}
    require(len(weeks) == 1 and type(cutoff_lead_seconds) is int and 0 < cutoff_lead_seconds <= 86400,
        "EXACT_ONE_REG_WEEK_AND_REGISTERED_CUTOFF_LEAD")
    season, week = next(iter(weeks)); old = original.document["slate"]
    require(season == old["season"] and old["week"] <= week <= 18, "CURRENT_OR_LATER_SAME_SEASON_REG_WEEK")
    grade._authenticate(authenticate, "RECURRING_EXECUTION_PLAN_BEFORE_VALUES",
        dict(original_choice_sha256=original.sha256, full_schedule=full_schedule,
            cutoff_lead_seconds=cutoff_lead_seconds), at)
    choice = original; history_sha = None
    if week == old["week"]:
        identity = state.digest(sorted((r["game_id"], state.utc(r["kickoff_utc"]).isoformat()) for r in full_schedule))
        require(identity == old["schedule_identity_sha256"] and len(full_schedule) == old["scheduled_games"],
            "CHANGED_OR_INCOMPLETE_FULL_CALENDAR_REJECTED")
        future = {r["game_id"]: r for r in full_schedule if state.utc(r["kickoff_utc"]) > at}
        require(set(future) <= set(old["game_cutoffs"]), "ALL_FUTURE_GAMES_MUST_HAVE_ORIGINAL_CUTOFFS")
        available = bool(future) and all(at < state.utc(old["game_cutoffs"][g]) < state.utc(r["kickoff_utc"])
            for g, r in future.items())
        reason = "ORIGINAL_SAME_WEEK_CAPTURE_WINDOW" if available else "FROZEN_CAPTURE_WINDOW_ELAPSED_GRADE_ORIGINALS_ONLY"
        if available:
            resume._calendar(full_schedule, original, at)  # Unchanged future-only validation.
    else:
        require(type(durable) is grade.DurableHistory, "DURABLE_CAUSAL_HISTORY_REQUIRED_NO_FALLBACK")
        durable.verify()
        require(state.utc(durable.document["actual_completed_at"]) < at
            and all(state.utc(t["known_by_at"]) < at for k in ("known_versions", "known_weeks") for t in durable.document[k].values()),
            "HISTORY_MUST_BE_DURABLE_BEFORE_ACTUAL_DECISION")
        require(durable.document["epoch_sha256"] == registered.epoch.sha256
            and any(w["season"] == season and registered.epoch.origin["slate"]["week"] <= w["week"] < week
                for w in durable.document["weeks"]),
            "COMPLETE_PRIOR_CURRENT_EPOCH_WEEK_REQUIRED")
        from . import weekly_generic_producer as generic
        cutoffs = {r["game_id"]:(state.utc(r["kickoff_utc"])-timedelta(seconds=cutoff_lead_seconds)).isoformat()
            for r in full_schedule}
        slate = generic.prepare_slate(full_schedule, season=season, week=week, game_cutoffs=cutoffs, now=at)
        require(at < state.utc(slate["weekly_deadline_utc"]) and slate["elapsed_games"] == 0,
            "NEW_WEEK_DECISION_DEADLINE_ALREADY_ELAPSED")
        choice = grade.select_next(registered, durable, slate, original, full_schedule=full_schedule,
            authenticate=authenticate, relocated_replays=relocated_replays, clock=lambda:at)
        history_sha = durable.sha256; available = True; future = cutoffs
        reason = "NEW_WEEK_P2_FROM_PRIOR_DURABLE_RESOLVED_HISTORY"
    plan = dict(schema_version=VERSION+"-execution-plan", kind="FUTURE_CAPTURE" if available else "GRADE_ONLY",
        reason=reason, epoch_sha256=registered.epoch.sha256, canonical_choice_sha256=original.sha256,
        target_choice_sha256=choice.sha256, season=season, week=week, planned_at=at.isoformat(),
        history_sha256=history_sha, future_game_ids=sorted(future) if available else [],
        capture_allowed=bool(available), publication_allowed=bool(available), current_values_used=False, fits=0)
    require(set(plan) == PLAN_KEYS, "CLOSED_RECURRING_EXECUTION_PLAN")
    return choice, plan


def planning_seed(registered, choice, full_schedule, raw_calendar, receipt, *, cutoff_lead_seconds):
    """Project calendar-only data before values; reader later adds causal weeks."""
    from . import audit_weekly_grade_history_v1 as history
    slate=choice.document["slate"]
    current=dict(season=slate["season"],week=slate["week"],schedule=deepcopy(full_schedule),
        game_cutoffs=deepcopy(slate["game_cutoffs"]),canonical_choice_sha256=choice.sha256)
    later=None
    if slate["week"]<18:
        # Test presence using metadata columns only. Malformed present rows go
        # through the same strict complete-calendar parser, never get ignored.
        present=any(int(r["season"])==slate["season"] and int(r["week"])==slate["week"]+1 and r["game_type"]=="REG"
            for r in csv.DictReader(io.StringIO(raw_calendar.decode("utf-8-sig"))))
        if present:
            rows=calendar(raw_calendar,season=slate["season"],week=slate["week"]+1)
            projected=[{k:r[k] for k in ("season","week","game_type","game_id","kickoff_utc")} for r in rows]
            later=dict(season=slate["season"],week=slate["week"]+1,schedule=projected,
                game_cutoffs={r["game_id"]:(state.utc(r["kickoff_utc"])-timedelta(seconds=cutoff_lead_seconds)).isoformat() for r in rows})
    value=dict(schema_version=history.LOCATOR_VERSION+"-planning",epoch_sha256=registered.epoch.sha256,
        current=current,next=later,resolved_weeks=[],known_by_at=receipt["retrieved_utc"],
        calendar={k:receipt[k] for k in ("url","sha256","bytes","retrieved_utc")})
    return history.validate_planning(value)
