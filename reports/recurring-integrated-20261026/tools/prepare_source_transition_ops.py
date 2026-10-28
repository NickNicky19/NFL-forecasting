"""Prepare one honest current-clock continuation from retained capture28.

GET and local metadata only. Actual native jobs must restore all original
evidence. No first-primary claim, failed26 successor or old issue is retried.
"""
import argparse,base64,gzip,json,os,re,subprocess,sys
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from pathlib import Path
from urllib.request import Request,urlopen

BASE=Path('/workspace/nfl-system-audit/continuation')
PRIVATE=BASE/'private'
GH='/workspace/nfl-system-audit/bin/gh'
REPO='NickNicky19/NFL-forecasting'
def require(value,code):
    if not value:raise ValueError(code)
def api(path):return json.loads(subprocess.check_output([GH,'api','repos/'+REPO+'/'+path]))
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--registration-root',type=Path,required=True)
    parser.add_argument('--attempt',type=int,required=True)
    args=parser.parse_args();require(args.attempt>29,'NEW_CURRENT_CLOCK_CONTINUATION_ONLY')
    sys.path.insert(0,str(Path.cwd()))
    from nfl_lab import audit_weekly_hosted_v1 as hosted,audit_weekly_controller_bootstrap_v1 as bootstrap
    from nfl_lab import audit_weekly_grade_history_v1 as history,audit_weekly_template_v1 as template
    from nfl_lab import audit_weekly_operations_v1 as operations,private_draft_store as store,state,audit_weekly_controller_v1 as controller
    encoded=args.registration_root.read_bytes();root=json.loads(encoded)
    require(encoded==store.canonical(root) and root['operation']=='CONTROLLER_REGISTRATION'
        and root['schema_version']==template.ROOT_V4,'ORIGINAL_NEW_SOURCE_REGISTRATION_ROOT')
    require(not subprocess.check_output(['git','status','--porcelain'])
        and subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==root['source_sha']
        and root['code_pins']==hosted.pins(),'CLEAN_REGISTERED_CURRENT_SOURCE')
    owner=json.loads(subprocess.check_output([GH,'api','user']))
    require((owner['login'],owner['id'])==('NickNicky19',208912933),'CURRENT_OWNER_ONLY')
    for branch,sha in (('research/weekly-storage-probe-v1',root['source_sha']),('main',root['effective_epoch']['parent_source_sha'])):
        require(api('branches/'+branch)['commit']['sha']==sha,'REGISTRATION_SOURCE_HEAD_CHANGED')
    state_head=api('branches/lab-state')['commit']['sha']
    record_content=api('contents/'+bootstrap.LOCATOR_REGISTRY_PATH+'?ref='+state_head)
    record_raw=base64.b64decode(record_content['content']);record=json.loads(record_raw)
    require(record_raw==store.canonical(record),'EXACT_CREATE_ONLY_CLEARED_NATIVE_RECORD')
    native=bootstrap.safe_seal(base64.b64decode(record['native_artifact_zip_base64']),registry_version=2)
    require(native['owner_root_go_sha256']==store.sha(encoded) and native['source_sha']==root['source_sha'],
        'ACTUAL_CURRENT_SOURCE_NATIVE_REGISTRATION_REQUIRED')
    # Verify the complete create-only commit, native artifact/API jobs/clocks,
    # source inventories and local checkout using the existing bootstrap.
    # This metadata-only seal is not a current Owner/child execution proof.
    verification_calls=[]
    def metadata_get(url,cap):
        require(url.startswith(controller.API+'/'),'FIXED_REPOSITORY_METADATA_ONLY')
        reply=subprocess.run([GH,'api','--method','GET','--include',url],stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,timeout=12)
        require(reply.returncode==0,'NATIVE_BOOTSTRAP_METADATA_UNAVAILABLE')
        separator=b'\r\n\r\n' if b'\r\n\r\n' in reply.stdout else b'\n\n'
        header,found,body=reply.stdout.partition(separator)
        require(found and len(body)<=cap,'BOUNDED_ACTUAL_METADATA_REPLY')
        status=re.match(rb'HTTP/\S+\s+(\d{3})',header.splitlines()[0])
        require(status is not None,'ACTUAL_METADATA_HTTP_STATUS_REQUIRED')
        verification_calls.append(dict(url_sha256=store.sha(url.encode()),bytes=len(body)))
        return controller.Reply(int(status.group(1)),body)
    seal=bootstrap.load_seal(dict(GITHUB_EVENT_NAME='workflow_dispatch',GITHUB_JOB=hosted.JOBS['produce'],GITHUB_RUN_ID=''),
        Path.cwd(),metadata_get=metadata_get,registry_version=2)
    seal.verify()
    verified_registration=json.loads(seal.registration_bytes)
    require(seal.document['owner_root_go_sha256']==store.sha(encoded)
        and verified_registration['producer']['source_sha']==root['source_sha']
        and verified_registration['producer']['code_pins']==root['code_pins']
        and verified_registration['parent']['source_sha']==root['effective_epoch']['parent_source_sha'],
        'FULLY_VERIFIED_REGISTRATION_AND_SUPPLIED_ROOT_BINDINGS')
    binding=history.validate_source_history_binding(root);old=binding['predecessor']
    name=history.latest_locator(api('contents/'+history.LOCATOR_ROOT+'?ref='+state_head))
    require(name==old['locator']['path'],'LATEST_HISTORY_CHANGED_RECONCILE_BEFORE_NEW_ISSUE')
    content=api('contents/'+history.LOCATOR_ROOT+'/'+name+'?ref='+state_head)
    locator_raw=base64.b64decode(content['content']);require(store.sha(locator_raw)==old['locator']['sha256'],'EXACT_PREDECESSOR_LOCATOR')
    locator=history.metadata_document(locator_raw)
    receipt_path='state/public/weekly-adaptive-v1/receipts/'+old['feed_sha256']+'.json.gz'
    receipt_content=api('contents/'+receipt_path+'?ref='+state_head)
    receipt_raw=base64.b64decode(receipt_content['content']);require(store.sha(receipt_raw)==old['receipt_sha256'],'EXACT_ORIGINAL_RECEIPT')
    receipt=json.loads(gzip.decompress(receipt_raw))
    calendar_url='https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv'
    with urlopen(Request(calendar_url,headers={'User-Agent':'NFL-permitted-source-audit'}),timeout=30) as response:
        require(response.status==200 and response.url==calendar_url,'ACTUAL_PERMITTED_CALENDAR_RESPONSE')
        calendar=response.read((8<<20)+1)
    require(0<len(calendar)<=8<<20,'BOUNDED_ACTUAL_CALENDAR')
    retrieved=datetime.now(timezone.utc);issued=datetime.now(timezone.utc)
    plan=history.next_plan(locator['planning'],at=issued)
    require(plan['kind']=='FUTURE_CAPABLE','CURRENT_REMAINING_FUTURE_PLAN_REQUIRED')
    rows=operations.calendar(calendar,season=plan['season'],week=plan['week'])
    schedule=[{k:r[k] for k in ('season','week','game_type','game_id','kickoff_utc')} for r in rows]
    require(state.digest(schedule)==plan['calendar_sha256'],'CALENDAR_CHANGED_REQUIRES_EXPLICIT_RECONCILIATION')
    require(all(issued<state.utc(value) for value in plan['game_cutoffs'].values()),'NO_LATE_CAPTURE_OR_BACKFILL')
    original=json.loads((PRIVATE/'weekly-go-28.json').read_bytes())
    require(store.sha(store.canonical(original))==old['root_go_sha256'],'ORIGINAL_PREDECESSOR_ROOT_UNCHANGED')
    pending=history.continued_pending_recovery(root,original)
    registered_pending=template.pending_recovery(root)
    if registered_pending['handoffs'] or registered_pending['pending_reservations']:
        require(not pending['handoffs'] and not pending['pending_reservations'],
            'SEPARATE_CURRENT_NAMESPACE_FAILURE_POOL_ONLY')
        pending=template.validate_pending_recovery(registered_pending,binding=root['qualified_runtime']['binding'])
    root.update(operation='RECURRING_CAPTURE',issued_at_utc=issued.isoformat(),expires_at_utc=(issued+timedelta(hours=1)).isoformat(),
        effective_epoch=dict(schema_version=operations.CONTEXT_V5,controller_context=None,
            previous_capture={k:old[k] for k in ('feed_sha256','receipt_sha256')},
            previous_checkpoint=dict(schema_version=history.LOCATOR_REF,**old['locator']),plan=plan,
            pending_post_recovery=template.pending_recovery_envelope(pending)))
    history.source_history_scope(root,receipt,locator=locator,locator_sha256=old['locator']['sha256'])
    hosted.validate_root(root,now=issued);operations.context(root['effective_epoch']);bootstrap._recurring(store.canonical(root),bot=False)
    require(template.first_primary_root(root) is None and template.failed_first_recovery_root(root) is None,'NO_OLD_STARTUP_OR_FAILED_SUCCESSOR_REUSE')
    raw=store.canonical(root);dispatch=store.canonical(dict(ref='research/weekly-storage-probe-v1',inputs=dict(mode=hosted.MODE,
        inference_builder_go_json=raw.decode(),inference_builder_go_sha256=store.sha(raw))))
    require(len(raw)<=60<<10 and len(dispatch)<=65535,'UNCHANGED_ROOT_AND_DISPATCH_CAPS')
    require(not subprocess.check_output(['git','status','--porcelain']) and hosted.pins()==root['code_pins'],'SOURCE_CHANGED_DURING_PREPARATION')
    for name,body in ((f'weekly-go-{args.attempt}.json',raw),(f'weekly-dispatch-{args.attempt}.json',dispatch),
        (f'ops{args.attempt}-source-transition-calendar.csv',calendar)):
        with (PRIVATE/name).open('xb') as stream:stream.write(body)
    print(json.dumps(dict(state='SOURCE_HISTORY_CONTINUATION_PREPARED_NO_POST',source_sha=root['source_sha'],root_go_sha256=store.sha(raw),
        root_bytes=len(raw),dispatch_bytes=len(dispatch),predecessor_run=int(old['run_id']),previous_checkpoint_sha256=old['locator']['sha256'],
        previous_choice_sha256=old['choice_sha256'],games=len(plan['game_cutoffs']),all_cutoffs_preserved=True,cutoff_lead_seconds=root['cutoff_lead_seconds'],
        runtime_transition=binding['runtime_transition'],original_root_and_pending_evidence_retained=True,
        native_registration_full_bootstrap_verified=True,native_registration_metadata_calls=len(verification_calls),
        calendar_sha256=store.sha(calendar),calendar_retrieved_utc=retrieved.isoformat(),issued_at_utc=issued.isoformat(),
        old_first_or_recovery_claim_reused=False,private_payload_GETs=0,new_fits=0,remote_writes=0)))

if __name__=='__main__':
    os.umask(0o077)
    try:main()
    except Exception as error:
        reason=str(error) if type(error) is ValueError and re.fullmatch('[A-Z][A-Z0-9_]{0,100}',str(error)) else 'SOURCE_OR_METADATA_PREPARATION_REJECTED'
        print(json.dumps(dict(state='PREPARATION_REJECTED_NO_POST',reason=reason,remote_writes=0,new_fits=0)),file=sys.stderr)
        raise SystemExit(2)
