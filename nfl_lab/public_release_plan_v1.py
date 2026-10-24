"""Metadata-only job4 exporter plan: one pinned archived public-board GET."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request,build_opener,HTTPRedirectHandler

from . import private_draft_store as s,gha_private_checkpoint as cp,weekly_public_feed as feed,weekly_durable_acceptance as a
from .owned_reference_batch import validate_owned_references

VERSION='weekly-hosted-public-release-plan-v1'
GO_KEYS={'schema_version','state','authority_kind','repository','source_sha','procedure_sha256','review_sha256','root_ledger_sha256','registered_at_utc','input_cutoff_utc','policy','rights_authority','r0','canary_acceptance','board'}
RIGHTS={'schema_version','state','authority_kind','source_policy_sha256','scope','public_fields','source_review_sha256','basis','upstream_blanket_grant','public_raw_or_model_weights','human_approval'}
REFS=('selected','producer_proof','terminal','completion','decision','parent_capture','bridge','startup_policy','procedure_catalog','selected_version_catalog','inference_consumed','durability','selected_relocation','selected_snapshot_index')


def require(v,code):
    if not v:raise s.StoreError(code)
def now():return datetime.now(timezone.utc).isoformat()
def utc(v):return s.utc(v)
def h(v):return a.h(v)
def archive_url(url):
    require(type(url) is str,'PINNED_ARCHIVE_URL_REQUIRED');p=urlsplit(url)
    require(p.scheme=='https' and p.netloc=='raw.githubusercontent.com' and not p.query and not p.fragment and not p.username and not p.password
        and re.fullmatch(r'/NickNicky19/nicks-expert-nfl-picks/[a-f0-9]{40}/output/data/[A-Za-z0-9_./-]+\.json',p.path)
        and all(part not in {'..','.'} for part in p.path.split('/')),'IMMUTABLE_OWNER_WEBSITE_BOARD_ONLY')
    return url
class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args):return None


class BoardGET:
    def __init__(self,transport=None):self.transport=transport;self.calls=0;self.bytes=0
    def __call__(self,spec):
        archive_url(spec['url']);require(self.calls==0,'ONE_BOARD_GET_NO_RETRY');self.calls+=1
        req=Request(spec['url'],headers={'Accept':'application/json','User-Agent':'weekly-public-release-plan-v1'})
        try:
            response=self.transport(req,10) if self.transport else build_opener(NoRedirect()).open(req,timeout=10)
            with response:
                require(response.status==200,'ARCHIVED_BOARD_HTTP_FAILED');body=response.read((4<<20)+1)
        except (HTTPError,OSError,TimeoutError):raise s.StoreError('ARCHIVED_BOARD_GET_FAILED') from None
        self.bytes=len(body);require(len(body)==spec['bytes']<=4<<20 and s.sha(body)==spec['sha256'],'ARCHIVED_BOARD_EXACT_BYTES_REQUIRED')
        return body


def validate_go(go,*,procedure_sha256,source_sha,event,go_text,go_sha,at,recovery_v2=False,build_config_sha256=None):
    from .initial_horizon import resolve
    route=resolve(recovery_v2)
    require(type(go) is dict and set(go)==GO_KEYS and go['schema_version']==route.public_version+'-GO' and go['state']=='ROOT_APPROVED_DERIVED_PUBLICATION'
        and go['authority_kind']=='ROOT_APPROVED_PROCEDURE' and go['repository']==s.REPO and go['source_sha']==source_sha and go['procedure_sha256']==procedure_sha256
        and h(go['review_sha256']) and h(go['root_ledger_sha256']) and go['input_cutoff_utc']==route.cutoff
        and utc(go['registered_at_utc'])<=utc(at)<utc(go['input_cutoff_utc']),'EXACT_ROOT_PUBLIC_RELEASE_GO')
    require(s.canonical(go).decode()==go_text and s.sha(go_text.encode())==go_sha and len(go_text.encode())<=48<<10,'CANONICAL_PUBLIC_GO_PIN')
    require(event.get('repository',{}).get('full_name')==s.REPO and event.get('inputs',{}).get('mode')=='genuine-hosted-fixed-build-v1'
        and event['inputs'].get('public_release_go_json')==go_text and event['inputs'].get('public_release_go_sha256')==go_sha,'EXACT_PUBLIC_GO_DISPATCH')
    text=event['inputs']['build_registration_json'];build=cp.strict_json(text)
    require(s.canonical(build).decode()==text and s.sha(text.encode())==event['inputs']['build_registration_sha256'] and build['source_sha']==source_sha
        and build.get('schema_version')==route.build_registration_schema and build.get('approved') is True and build.get('repository')==s.REPO
        and build.get('scope')=='SOURCE_AND_TRAIN_FIXED18_ONLY' and build.get('maximum_new_fits')==18
        and utc(go['registered_at_utc'])<=utc(build['registered_at_utc'])<=utc(at),'PUBLIC_GO_BEFORE_SOURCE_REGISTRATION')
    if recovery_v2:
        require(h(build_config_sha256),'EXACT_RECOVERY_BUILD_CONFIG_REQUIRED')
        route.adapter().validate_build_registration(build,source_sha=source_sha,config_sha256=build_config_sha256,
            initial_sha256=s.sha(s.canonical(build['initial_registration'])),now=utc(at))
    policy=go['policy'];require(policy['schema_version']==feed.POLICY_V2 and policy['publication_authority']['source_sha']==source_sha and policy['source_policy_sha256']==cp.POLICY_SHA,'REGISTERED_CURRENT_PUBLIC_V2_POLICY')
    feed.policy_check(policy)
    rights=go['rights_authority']
    require(type(rights) is dict and set(rights)==RIGHTS and rights['schema_version']=='weekly-selected-derived-rights-authority-v1' and rights['state']=='ROOT_REGISTERED'
        and rights['authority_kind']=='ROOT_APPROVED_DERIVED_PUBLICATION' and rights['source_policy_sha256']==cp.POLICY_SHA and rights['scope']=='SELECTED_DERIVED_ONLY'
        and rights['public_fields']==list(feed.overlay().ROW_FIELDS) and rights['source_review_sha256']==go['review_sha256']
        and type(rights['basis']) is str and 0<len(rights['basis'])<=4096 and rights['upstream_blanket_grant'] is False and rights['public_raw_or_model_weights'] is False and rights['human_approval'] is False
        and a.digest(rights) in policy['rights_authorities'],'EXPLICIT_ROOT_DERIVED_RIGHTS_AUTHORITY')
    r0=go['r0'];require(a.digest(r0) in policy['r0_identities'] and r0['schema_version']=='weekly-actual-r0-freeze-v1' and r0['state']=='ACTUAL_FIRST_RELEASE_R0_FROZEN'
        and r0['engine_sha256']==policy['engine_sha256'] and utc(r0['frozen_at'])<=utc(go['registered_at_utc']),'EXTERNALLY_VERIFIED_R0_REQUIRED')
    board=go['board'];require(type(board) is dict and set(board)=={'url','sha256','bytes','captured_at'} and type(board['bytes']) is int and 0<board['bytes']<=4<<20
        and h(board['sha256']) and r0['visible_board_sha256']==board['sha256'] and utc(board['captured_at'])<=utc(go['registered_at_utc']),'PINNED_ROOT_BOARD_CAPTURE')
    archive_url(board['url']);return build


def build_plan(inputs,*,go,storage,root,output,context,source_policy_ref,board_get,at,recovery_v2=False):
    """Inputs are the existing consume handoff; no invented exporter keys."""
    require(inputs['schema_version']=='weekly-selected-private-snapshot-v1-restored-inputs' and inputs['candidates_retained']==18 and inputs['public_export_authorized'] is False,'GENUINE_RELOCATED_INPUTS_REQUIRED')
    refs={k:inputs[k] for k in REFS};validate_owned_references(storage,{r['path']:r['sha256'] for r in refs.values()})
    def doc(name):return cp.strict_json(cp.read_ref(refs[name],2<<20))
    terminal=doc('terminal');completion=doc('completion');producer=doc('producer_proof');durable=doc('durability');relocation=doc('selected_relocation');physical=relocation['physical_restore_proof']
    require(producer['schema_version']=='weekly-selected-packager-provenance-v2' and producer['identity']['source_sha']==go['source_sha'] and producer['identity']['run_id']==context['run_id']
        and relocation['restored_selected']==refs['selected'] and relocation['original_selected']==completion['binding']
        and terminal['selected']==completion and completion['state']=='PERSISTED' and utc(go['registered_at_utc'])<=utc(producer['inference_consumed_at'])<=utc(terminal['actual_completed_at'])
        and producer['terminal_sha256']==refs['terminal']['sha256'],'ORIGINAL_BODY_AND_CLOCK_BINDING')
    ident=a.restored_identity(physical)
    require(ident['source_sha']==context['source_sha'] and ident['run_id']==context['run_id'] and ident['job_id']==context['job']['job_id']
        and ident['workflow_ref']==context['job']['workflow_ref'] and physical['payload_sha256']==refs['selected']['sha256'] and physical['bytes']==refs['selected']['bytes'],'INHERITED_CURRENT_JOB_API_PROOF')
    verifier=SimpleNamespace(binding=s.checked_binding(durable['runtime_binding']),process=context['process_identity'],source_sha=context['source_sha'],run_id=context['run_id'],job=context['job'])
    s.check_proof(verifier,physical,'restore');a.canary_check(go['canary_acceptance'],go['policy'],durable,at)
    s.check_proof(verifier,durable['restore_proof'],'restore')
    require(producer['identity']['job_id']=='genuine-hosted-fixed-build-restore-v1' and durable['restore_proof']['job']['job_id']=='genuine-hosted-selected-restore-v1','EXACT_SELECTED_CHAIN_ROLES')
    consumed=doc('inference_consumed')
    a.facts(dict(producer_proof=producer,terminal=terminal,terminal_body_sha256=refs['terminal']['sha256'],completion=completion,durability=durable,inference_consumed=consumed,inference_consumed_body_sha256=refs['inference_consumed']['sha256'],inference_consumed_body_bytes=refs['inference_consumed']['bytes']),go['policy'])
    require(utc(go['canary_acceptance']['verified_at'])<=utc(go['registered_at_utc']),'CANARY_ACCEPTED_BEFORE_PUBLIC_GO')
    catalog_body=cp.read_ref(refs['selected_version_catalog'],2<<20)
    require((len(catalog_body),s.sha(catalog_body))==(terminal['selected_version_catalog']['bytes'],terminal['selected_version_catalog']['sha256']),'ORIGINAL_ISSUED_CATALOG_BYTES')
    feed.catalog_policy_v2(go['policy'],feed.strict_public_json(catalog_body))
    # Archived public output only, checksum/size BEFORE JSON decoding.
    board_body=board_get(go['board']);board=cp.strict_json(board_body)
    require(type(board) is dict and {'season','week','games','players'}<=set(board) and (board['season'],board['week'])==(context['season'],context['week']),'ARCHIVED_BOARD_SCHEMA_OR_WEEK')
    output=Path(output);output.mkdir(mode=0o700);storage.register_root(output)
    def save(name,body):storage.write_bytes(output/name,body);return cp.binding(output/name)
    policy=save('PUBLIC_POLICY.json',s.canonical(go['policy']));rights_authority=save('RIGHTS_AUTHORITY.json',s.canonical(go['rights_authority']))
    rights=dict(schema_version='weekly-derived-selected-rights-v1',state='SOURCE_REVIEW_ACCEPTED',authority_kind='REGISTERED_SOURCE_RIGHTS_POLICY',authority_policy_sha256=a.digest(go['rights_authority']),selected_sha256=completion['binding']['sha256'],source_policy_sha256=cp.POLICY_SHA,
        scope='SELECTED_DERIVED_ONLY',public_fields=go['policy']['public_fields'],reviewed_at=at,authority_registered_at=go['registered_at_utc'],human_approval=False)
    r0=save('R0_IDENTITY.json',s.canonical(go['r0']));canary=save('CANARY_ACCEPTANCE.json',s.canonical(go['canary_acceptance']));rights_ref=save('RIGHTS_RECEIPT.json',s.canonical(rights));board_ref=save('ARCHIVED_BOARD.json',board_body)
    procedures=[p for p in go['policy']['durability_verifier_procedures'] if p['source_sha']==context['source_sha'] and p['export_job']==context['job']['job_id']]
    require(len(procedures)==1 and procedures[0]['verifier_sha256']==s.sha(Path(a.__file__).read_bytes()),'EXACT_REGISTERED_LIVE_VERIFIER')
    journal=output/'acceptance-journal';journal.mkdir(mode=0o700);state=Path(root)/'public-derived-state';storage.register_root(state)
    plan=dict(schema_version='weekly-public-feed-export-plan-v1',execution_authorized=True,authority_kind='AUTOMATED_REGISTERED_DERIVED_POLICY',registration_policy_sha256=policy['sha256'],policy=policy,
        durability_authority='ROOT_APPROVED_PROCEDURE_VERIFIED',**{k:refs[k] for k in ['terminal','completion','decision','parent_capture','bridge','durability','producer_proof','inference_consumed','selected','selected_relocation','selected_snapshot_index','selected_version_catalog']},
        rights=rights_ref,r0=r0,canary_acceptance=canary,verifier_procedure_sha256=a.digest(procedures[0]),acceptance_journal=str(journal),durability_acceptance_output=str(output/'LIVE_ACCEPTANCE.json'),board=board_ref,
        source_policy=source_policy_ref,cache_root=str(Path(root)/'cache'),state_root=str(state),publication_manifest=str(output/'PUBLICATION_MANIFEST.json'))
    plan_ref=save('EXPORT_PLAN.json',s.canonical(plan))
    from .initial_horizon import resolve
    save('BUILDER_RECEIPT.json',s.canonical(dict(schema_version=resolve(recovery_v2).public_version,state='METADATA_PLAN_READY_NOT_PUBLISHED',plan_sha256=plan_ref['sha256'],GO_sha256=s.sha(s.canonical(go)),rights_authority_sha256=rights_authority['sha256'],inherited_current_job_proof_sha256=a.digest(physical),fresh_API_auth_by_builder=False,archived_board_GET_attempts=board_get.calls,archived_board_bytes=board_get.bytes,NFL_provider_HTTP=0,model_decodes=0,selected_values_decoded=0,public_export_authorized=False,created_at=at)))
    return plan_ref
