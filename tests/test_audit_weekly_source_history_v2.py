"""Source-history V2 controls; fictional metadata is not native authority."""
from copy import deepcopy
from datetime import timedelta
import gzip
from pathlib import Path
from types import SimpleNamespace

import pytest
from nfl_lab import audit_weekly_grade_history_v1 as history
from test_audit_weekly_grade_history_v1 import (
    no_network, parent_metadata, source_metadata, source_transition_root,
)

# Explicit V2 metadata tests. Fictional records are not native authority.
def _source_v2_retime(package, start):
    from nfl_lab import private_draft_store as store
    q=package['qualification']
    at=store.utc(start)
    for i,proof in enumerate((q['before_proof'],q['read_proof'],q)):
        proof['started_at_utc']=(at+timedelta(minutes=2*i)).isoformat()
        proof['created_at_utc']=(at+timedelta(minutes=2*i,seconds=30)).isoformat()
    before,read=q['before_proof'],q['read_proof']
    read['before_sha256']=store.sha(store.canonical(before))
    q.update(before_sha256=store.sha(store.canonical(before)),read_sha256=store.sha(store.canonical(read)),
        before_completed_at_utc=before['created_at_utc'],read_completed_at_utc=read['created_at_utc'])


def _source_v2_reseal(case):
    from nfl_lab import private_draft_store as store,audit_weekly_template_v1 as template
    old=case.original;root_hash=store.sha(store.canonical(old))
    case.receipt.update(root_go_sha256=root_hash,source_sha=old['source_sha'],policy_sha256=old['publication_registration']['policy_sha256'])
    case.locator['cohort'].update(root_go_sha256=root_hash,source_sha=old['source_sha'])
    case.locator['anchor'].update(receipt_sha256=store.sha(gzip.compress(store.canonical(case.receipt),mtime=0)))
    body=history.validate_source_history_binding(case.current)
    body['predecessor'].update(root_go_sha256=root_hash,root_static_sha256=template.static_root_sha256(old),
        locator=dict(path=history.locator_filename(case.locator),sha256=store.sha(gzip.compress(store.canonical(case.locator),mtime=0))),
        receipt_sha256=case.locator['anchor']['receipt_sha256'])
    body['predecessor_source_history_sha256']=store.sha(store.canonical(old['source_history_binding']))
    case.current['prior_capture_qualified_runtime'].update(root_static_sha256=template.static_root_sha256(old),anchor=deepcopy(case.locator['anchor']))
    case.current['effective_epoch'].update(previous_capture=deepcopy(case.locator['anchor']),
        previous_checkpoint=dict(schema_version=history.LOCATOR_REF,**body['predecessor']['locator']))
    case.current['source_history_binding']=history.source_history_envelope(body)


@pytest.fixture
def source_v2_metadata(source_metadata):
    """Closed synthetic native-preimage metadata, no HTTP or saved PASS grant."""
    from nfl_lab import private_draft_store as store,audit_weekly_template_v1 as template,state
    from test_audit_weekly_controller_bootstrap_v1 import fictional_runtime_metadata
    x=source_metadata;base=deepcopy(x.original);package=deepcopy(base['qualified_runtime'])
    _source_v2_retime(package,'2026-10-27T00:00:00+00:00')
    census=dict(schema_version='audit-private-rotation-v1-pending-census',complete=True,
        as_of_utc='2026-10-26T23:59:00+00:00',owner_evidence_sha256='a'*64,reservations=[])
    package['quota_reservation']=dict(schema_version='audit-private-rotation-v1-quota-reservation',global_cap_bytes=512<<20,
        reserved_before_bytes=32<<20,new_runtime_reserved_bytes=32<<20,reserved_after_bytes=64<<20,
        existing_draft_runtimes=1,pending_unlocated_runtimes=0,pending_records=0,charged_existing_bytes=117,charged_existing_assets=1,
        inventory_sha256='b'*64,pending_census_sha256=store.sha(store.canonical(census)),new_runtime_id=package['runtime_id'],
        old_assets_deleted=0,metadata_only=True)
    base.update(qualified_runtime=package,pending_census=census,
        prior_capture_qualified_runtime=dict(schema_version=template.PRIOR_RUNTIME,purpose='PRIOR_CAPTURE_QUALIFIED_RUNTIME',
            anchor=dict(feed_sha256='1'*64,receipt_sha256='2'*64),qualified_runtime=fictional_runtime_metadata(package,census,number=2),
            pending_census=deepcopy(census),root_static_sha256=None))
    base['effective_epoch']['pending_post_recovery']=dict(schema_version=template.PENDING_RECOVERY,handoffs=[],pending_reservations=[])
    old_receipt=deepcopy(x.receipt);old_receipt['root_go_sha256']=store.sha(store.canonical(base))
    old_locator=deepcopy(x.locator);old_locator['cohort']['root_go_sha256']=old_receipt['root_go_sha256']
    original=source_transition_root(base,old_receipt,old_locator,runtime_transition='DUAL_RUNTIME_ROTATE')
    original.update(issued_at_utc='2026-10-28T07:05:00+00:00',expires_at_utc='2026-10-28T08:05:00+00:00')
    receipt=deepcopy(x.receipt)
    receipt.update(source_sha=original['source_sha'],run_id='45000000004',root_go_sha256=store.sha(store.canonical(original)),
        policy_sha256=original['publication_registration']['policy_sha256'],feed_sha256=store.sha(b'FICTIONAL_IMMEDIATE_V4_FEED'))
    locator=deepcopy(x.locator)
    locator['anchor']=dict(feed_sha256=receipt['feed_sha256'],receipt_sha256=store.sha(gzip.compress(store.canonical(receipt),mtime=0)))
    locator['cohort'].update(**{k:receipt[k] for k in ('source_sha','run_id','root_go_sha256','feed_sha256')})
    locator['cohort']['root_issued_at_utc']=original['issued_at_utc']
    locator['planning']['calendar']['retrieved_utc']='2026-10-28T07:07:00+00:00'
    locator['helper_sha256']={p:original['code_pins'][p] for p in history.LOCATOR_HELPERS}
    handoff=locator['sidecar']['checkpoint_handoff']
    handoff.update(runtime_binding_sha256=store.sha(store.canonical(original['qualified_runtime']['binding'])),
        qualified_package_sha256=state.digest(original['qualified_runtime']))
    current=deepcopy(original);current['source_sha']='8'*40
    overrides={}
    for p in history.FILES:
        overrides[p]=current['code_pins'][p];current['code_pins'][p]=store.sha(('FICTIONAL_V2_PIN:'+p).encode())
    current['publication_registration'].update(policy_sha256=store.sha(b'FICTIONAL_V2_POLICY'),policy_gzip_base64='FICTIONAL_V2_POLICY')
    current.update(qualified_runtime=fictional_runtime_metadata(original['qualified_runtime'],census,number=6),
        pending_census=deepcopy(census),issued_at_utc='2026-10-28T10:00:00+00:00',expires_at_utc='2026-10-28T11:00:00+00:00')
    _source_v2_retime(current['qualified_runtime'],'2026-10-28T09:00:00+00:00')
    current['prior_capture_qualified_runtime']=dict(schema_version=template.PRIOR_RUNTIME,purpose='PRIOR_CAPTURE_QUALIFIED_RUNTIME',
        anchor=deepcopy(locator['anchor']),qualified_runtime=deepcopy(original['qualified_runtime']),pending_census=deepcopy(census),
        root_static_sha256=template.static_root_sha256(original))
    predecessor={k:receipt[k] for k in ('source_sha','workflow_sha256','policy_sha256','recipe_registration_sha256',
        'run_id','feed_sha256','root_go_sha256','epoch_sha256','choice_sha256')}
    predecessor.update(receipt_sha256=locator['anchor']['receipt_sha256'],root_static_sha256=template.static_root_sha256(original),
        code_pins_sha256=store.sha(store.canonical(original['code_pins'])),
        locator=dict(path=history.locator_filename(locator),sha256=store.sha(gzip.compress(store.canonical(locator),mtime=0))))
    binding=dict(schema_version=history.SOURCE_HISTORY_BINDING_V2,target_source_sha=current['source_sha'],
        target_policy_sha256=current['publication_registration']['policy_sha256'],predecessor=predecessor,pin_overrides=overrides,
        runtime_transition='DUAL_RUNTIME_ROTATE',predecessor_root_schema=history.ROOT_V4,
        predecessor_source_history_sha256=store.sha(store.canonical(original['source_history_binding'])))
    current['source_history_binding']=history.source_history_envelope(binding)
    current['effective_epoch'].update(previous_capture=deepcopy(locator['anchor']),
        previous_checkpoint=dict(schema_version=history.LOCATOR_REF,**predecessor['locator']),
        pending_post_recovery=dict(schema_version=template.PENDING_RECOVERY,handoffs=[],pending_reservations=[]))
    jobs=deepcopy(x.jobs);jobs['produce']['started_at']='2026-10-28T07:06:00+00:00'
    return SimpleNamespace(original=original,current=current,receipt=receipt,locator=locator,jobs=jobs,at=x.at)


def _source_v2_root_check(case, *, static=False):
    from nfl_lab import audit_weekly_template_v1 as template
    root=deepcopy(case.current)
    if static:
        root['approved']=False
        for p in template.DYNAMIC_FIELDS-{'approved'}:root[p]=None
    return history._root_envelope(dict(root_go=case.original,planning=deepcopy(case.locator['planning'])),
        case.locator,case.jobs,code_pins=case.original['code_pins'],static_root=root,at=case.at,
        locator_sha256=history.validate_source_history_binding(case.current)['predecessor']['locator']['sha256'])


def test_v2_immediate_v4_native_preimage_metadata_keeps_original_bytes_and_hashes(source_v2_metadata):
    from nfl_lab import private_draft_store as store
    x=source_v2_metadata;before=store.canonical(x.original)
    assert history.source_history_scope(x.current,x.receipt,locator=x.locator,
        locator_sha256=history.validate_source_history_binding(x.current)['predecessor']['locator']['sha256'])==x.original['code_pins']
    assert _source_v2_root_check(x)['root_go'] is x.original
    assert _source_v2_root_check(x,static=True)['root_go'] is x.original
    assert store.canonical(x.original)==before
    assert len(x.current['code_pins'])==128
    assert (history.SOURCE_HISTORY_PLAIN_CAP,history.SOURCE_HISTORY_ENCODED_CAP)==(16<<10,12<<10)


def test_v2_inner_v2_is_structural_and_does_not_recursively_resolve_grandparents(source_v2_metadata,monkeypatch):
    from nfl_lab import private_draft_store as store
    x=source_v2_metadata;inner=history.validate_source_history_binding(x.original)
    inner.update(schema_version=history.SOURCE_HISTORY_BINDING_V2,predecessor_root_schema=history.ROOT_V4,
        predecessor_source_history_sha256=store.sha(b'OPAQUE_EARLIER_CANONICAL_BINDING_COMMITMENT'))
    x.original['source_history_binding']=history.source_history_envelope(inner);_source_v2_reseal(x)
    calls=[];actual=history._source_history_runtime_scope
    def one(current,original,binding):
        calls.append(original['source_sha']);return actual(current,original,binding)
    monkeypatch.setattr(history,'_source_history_runtime_scope',one)
    _source_v2_root_check(x)
    assert calls==[x.original['source_sha']]


@pytest.mark.parametrize('damage',['root_hash','static_hash','prior_binding_hash','policy','source','schema',
    'current_slot','prior_slot','prior_census','anchor','rights','source_config','current_source_cycle','inner_source_cycle'])
def test_v2_rejects_wrong_preimages_sources_policies_and_slot_changes(source_v2_metadata,damage):
    from nfl_lab import audit_weekly_template_v1 as template,private_draft_store as store
    x=source_v2_metadata;body=history.validate_source_history_binding(x.current)
    if damage=='root_hash':body['predecessor']['root_go_sha256']='f'*64
    elif damage=='static_hash':body['predecessor']['root_static_sha256']='f'*64
    elif damage=='prior_binding_hash':body['predecessor_source_history_sha256']='f'*64
    elif damage=='policy':x.original['publication_registration']['policy_sha256']='f'*64
    elif damage=='source':x.original['source_sha']='f'*40
    elif damage=='schema':x.original['schema_version']=template.ROOT_V3
    elif damage=='current_slot':x.current['qualified_runtime']=deepcopy(x.original['qualified_runtime'])
    elif damage=='prior_slot':x.current['prior_capture_qualified_runtime']['qualified_runtime']=deepcopy(x.original['prior_capture_qualified_runtime']['qualified_runtime'])
    elif damage=='prior_census':x.current['prior_capture_qualified_runtime']['pending_census']['owner_evidence_sha256']='f'*64
    elif damage=='anchor':x.current['prior_capture_qualified_runtime']['anchor']['feed_sha256']='f'*64
    elif damage=='rights':x.current['publication_registration']['rights_authority']={'forbidden':'new rights'}
    elif damage=='source_config':x.current['source_config']={'forbidden':'new source'}
    elif damage=='current_source_cycle':x.current['source_sha']=x.original['source_sha']
    elif damage=='inner_source_cycle':
        inner=history.validate_source_history_binding(x.original);inner['predecessor']['source_sha']=x.current['source_sha']
        x.original['source_history_binding']=history.source_history_envelope(inner);_source_v2_reseal(x)
        body=history.validate_source_history_binding(x.current)
    x.current['source_history_binding']=history.source_history_envelope(body)
    with pytest.raises((history.HistoryError,template.TemplateError,store.StoreError,ValueError)):_source_v2_root_check(x)


def test_v2_requires_fresh_native_qualification_after_immediate_delivery(source_v2_metadata):
    x=source_v2_metadata;_source_v2_retime(x.current['qualified_runtime'],'2026-10-27T00:00:00+00:00')
    with pytest.raises(history.HistoryError,match='FRESH_NATIVE_ROTATION_AFTER_IMMEDIATE_DELIVERY'):_source_v2_root_check(x)


def test_v1_does_not_gain_v4_predecessor_authority(source_v2_metadata):
    x=source_v2_metadata;body=history.validate_source_history_binding(x.current)
    body['schema_version']=history.SOURCE_HISTORY_BINDING
    for p in ('predecessor_root_schema','predecessor_source_history_sha256'):del body[p]
    x.current['source_history_binding']=history.source_history_envelope(body)
    with pytest.raises(history.HistoryError,match='EXPLICIT_ORIGINAL_V3_SOURCE_HISTORY_ROOT'):_source_v2_root_check(x)


@pytest.mark.parametrize('damage',['v1_extra','outer_version','missing_parent_hash','v3_schema','preserve_enum','unknown'])
def test_v2_dispatch_is_closed_and_v1_transport_stays_exact(source_v2_metadata,damage):
    x=source_v2_metadata;body=history.validate_source_history_binding(x.current)
    if damage=='v1_extra':body['schema_version']=history.SOURCE_HISTORY_BINDING
    elif damage=='outer_version':x.current['source_history_binding']['schema_version']=history.SOURCE_HISTORY_TRANSPORT
    elif damage=='missing_parent_hash':del body['predecessor_source_history_sha256']
    elif damage=='v3_schema':body['predecessor_root_schema']='audit-weekly-hosted-v3-root-GO'
    elif damage=='preserve_enum':body['runtime_transition']='PRESERVE'
    else:body['saved_PASS']=True
    with pytest.raises(history.HistoryError):
        if damage!='outer_version':x.current['source_history_binding']=history.source_history_envelope(body)
        history.validate_source_history_binding(x.current)


def test_v2_saved_flags_cannot_replace_the_native_original_root_preimage(source_v2_metadata):
    from nfl_lab import audit_weekly_template_v1 as template
    x=source_v2_metadata
    with pytest.raises((history.HistoryError,template.TemplateError)):
        history._root_envelope(dict(root_go={'saved_PASS':True},planning=x.locator['planning']),x.locator,x.jobs,
            code_pins=x.original['code_pins'],static_root=x.current,at=x.at)


def test_original128_pinned_source_files_fit_unchanged_history_source_cap():
    from nfl_lab import audit_weekly_hosted_v1 as hosted
    assert len(hosted.PINS) == 128
    assert history.LIMITS["source_bytes"] == 128 << 10
    source_root = Path(hosted.__file__).resolve().parents[1]
    invalid = {name: (source_root/name).stat().st_size for name in hosted.PINS
        if not 0 < (source_root/name).stat().st_size <= history.LIMITS["source_bytes"]}
    assert not invalid, invalid
