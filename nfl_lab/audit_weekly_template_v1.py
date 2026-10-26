"""Static private Root metadata transport; never an execution authorization.

Native append/restore require the parent's live Root authority callback and real
dispatch Client. Scheduler reads use a separate GET-only client with a live
controller.Proof before EVERY exchange, including redirects. The independently
trusted seal digest must come from authenticated owner registration, never the
artifact itself. Root instantiation, owner-registration authentication, cadence,
activation and dispatch remain the parent's responsibilities.
"""
from __future__ import annotations

import base64
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import gzip
import io
from pathlib import Path
import re
import time
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import Request

from . import private_draft_store as store
from . import owner_private_bootstrap as owner, audit_weekly_controller_v1 as controller

VERSION = 'audit-weekly-template-v1'
PLAIN_CAP = 128 << 10
PACKED_CAP = PLAIN_CAP + 4096
ENTRY_CAP = 16 << 10
POLICY_SHA = 'e7f54213218031c978c766af7a1a3b22a57c2a424b51f62056742162154fe441'
TARGETS = ('pass_yd','pass_td','pass_cmp','pass_att','pass_int','rush_yd','rush_att','rec','rec_yd','rush_rec_yd','anytime_td')
JOBS = tuple([(target,'leaf_cdf_base','LAB_CDF') for target in TARGETS]
    + [(target,'count_A','COUNT_A') for target in ('rush_att','rec')]
    + [(target,'catboost_medium','CATBOOST_MEDIUM') for target in ('pass_yd','rush_yd','rec_yd','rush_rec_yd','anytime_td')])
LIMITS = dict(plain_bytes=PLAIN_CAP, packed_bytes=PACKED_CAP, HTTP_calls=40,
    authentication_callbacks=40, transfer_bytes=16 << 20, redirects=2,
    CPU_seconds=120, wall_seconds=180, address_space_bytes=512 << 20,
    runtime_bytes=32 << 20, runtime_assets=128, global_private_bytes=512 << 20,
    retries=0, append_attempts=1, model_decodes=0, fits=0, forecast_or_outcome_decodes=0)
ROOT_KEYS = {'schema_version','approved','repository','mode','operation','source_sha','workflow_ref',
    'owner_authorization','issued_at_utc','expires_at_utc','single_writer_group','code_pins','limits',
    'jobs','failure_restorer','retained_registration','original_selected_handoff','qualified_runtime',
    'pending_census','source_config','cutoff_lead_seconds','publication','publication_registration','effective_epoch'}
ROOT_V3 = 'audit-weekly-hosted-v3-root-GO'
ROOT_V3_KEYS = ROOT_KEYS | {'prior_capture_qualified_runtime'}
STATIC_V3 = VERSION + '-static-v3'
PRIOR_RUNTIME = 'audit-weekly-prior-capture-qualified-runtime-v1'
DYNAMIC_FIELDS = {'approved','issued_at_utc','expires_at_utc','operation','effective_epoch'}
DOCUMENT_KEYS = {'schema_version','source_sha','code_pins','readiness','root_template'}
HANDOFF_KEYS = {'schema_version','repository','binding','descriptor','template_sha256','template_bytes',
    'writer','root_go_sha256','appended_at_utc'}
SEAL_KEYS = HANDOFF_KEYS | {'reader','reader_proof_sha256','verified_at_utc'}
IDENTITY_KEYS = {'execution_lane','repository','source_sha','run_id','run_attempt','process_identity',
    'job_id','api_job_id','permission','workflow_ref'}
DENIED_KEYS = {'authorization','token','secret','api_key','github_token','gh_token','access_token','password',
    'private_key','credential','credentials','aws_secret_access_key','aws_access_key_id','session_token',
    'model_bytes','model_body','model_base64','forecast_rows','outcomes','content_b64','body_base64',
    'expected_bits','float64_hex','forecast_value'}


class TemplateError(ValueError):
    """Fixed ASCII guards; never interpolate private/library values."""


def require(value, code):
    if not value: raise TemplateError(code)


def now(): return datetime.now(timezone.utc)
def digest(value): return store.sha(store.canonical(value))
def hashed(value, n=64): return type(value) is str and re.fullmatch('[a-f0-9]{'+str(n)+'}', value) is not None
def identifier(value): return type(value) is str and re.fullmatch('[1-9][0-9]{0,19}', value) is not None
def label(value): return type(value) is str and re.fullmatch('[A-Za-z0-9_-]{1,100}', value) is not None
def decode_json(body): return controller.decode(body)


def root_keys(root):
    require(type(root) is dict and root.get('schema_version') in {'audit-weekly-hosted-v2-root-GO', ROOT_V3},
        'EXPLICIT_STATIC_ROOT_VERSION')
    return ROOT_V3_KEYS if root['schema_version'] == ROOT_V3 else ROOT_KEYS


def static_root_sha256(root):
    """Original Root interpretation commitment, never execution authority."""
    require(set(root) == root_keys(root), 'EXACT_ORIGINAL_STATIC_ROOT_KEYS')
    value = deepcopy(root); value['approved'] = False
    for name in DYNAMIC_FIELDS - {'approved'}: value[name] = None
    return digest(value)


def prior_runtime(root, *, before=None):
    """Closed owner-sealed metadata. Live API/canary checks remain mandatory."""
    require(type(root) is dict, 'EXPLICIT_RUNTIME_ROOT')
    if root.get('schema_version') != ROOT_V3:
        require('prior_capture_qualified_runtime' not in root, 'NO_PRIOR_RUNTIME_ON_LEGACY_ROOT')
        return None
    require(set(root) == ROOT_V3_KEYS, 'CLOSED_DUAL_RUNTIME_ROOT')
    value = root['prior_capture_qualified_runtime']
    require(type(value) is dict and set(value) == {'schema_version','purpose','anchor','qualified_runtime','pending_census','root_static_sha256'}
        and value['schema_version'] == PRIOR_RUNTIME and value['purpose'] == 'PRIOR_CAPTURE_QUALIFIED_RUNTIME'
        and type(value['anchor']) is dict and set(value['anchor']) == {'feed_sha256','receipt_sha256'}
        and all(hashed(v) for v in value['anchor'].values())
        and (value['root_static_sha256'] is None or hashed(value['root_static_sha256'])), 'CLOSED_PRIOR_CAPTURE_RUNTIME')
    from . import audit_weekly_controller_bootstrap_v1 as bootstrap
    for package in (root['qualified_runtime'], value['qualified_runtime']):
        require(type(package) is dict and type(package.get('binding')) is dict
            and type(package.get('qualification')) is dict, 'CLOSED_PRIOR_QUALIFIED_PACKAGE')
        bootstrap._qualified_locator_package(package, package['binding'],
            before=before or package['qualification']['created_at_utc'])
    old, current = value['qualified_runtime']['binding'], root['qualified_runtime']['binding']
    require(old['runtime_id'] != current['runtime_id'] and old['release_id'] != current['release_id'],
        'DISTINCT_PRIOR_AND_CURRENT_RUNTIME')
    pending = value['pending_census']; package = value['qualified_runtime']
    require(type(pending) is dict and set(pending) == {'schema_version','complete','as_of_utc','owner_evidence_sha256','reservations'}
        and pending['schema_version'] == 'audit-private-rotation-v1-pending-census' and pending['complete'] is True
        and hashed(pending['owner_evidence_sha256']) and type(pending['reservations']) is list
        and len(pending['reservations']) <= 128
        and digest(pending) == package['quota_reservation']['pending_census_sha256']
        and len(pending['reservations']) == package['quota_reservation']['pending_records']
        and store.utc(pending['as_of_utc']) <= store.utc(package['qualification']['created_at_utc']),
        'ORIGINAL_PRIOR_QUALIFICATION_CENSUS')
    seen = set()
    for row in pending['reservations']:
        require(type(row) is dict and set(row) == {'reservation_sha256','runtime_id','release_id','pending_bytes','pending_assets'}
            and hashed(row['reservation_sha256']) and row['reservation_sha256'] not in seen
            and (row['runtime_id'] is None or hashed(row['runtime_id'],32))
            and (row['release_id'] is None or type(row['release_id']) is int and row['release_id'] > 0)
            and type(row['pending_bytes']) is int and 0 <= row['pending_bytes'] <= 32 << 20
            and type(row['pending_assets']) is int and 0 <= row['pending_assets'] <= 128,
            'CLOSED_PRIOR_PENDING_RESERVATION')
        seen.add(row['reservation_sha256'])
    return deepcopy(value)


def capture_runtime(root, *, anchor=None):
    """Select exactly one sealed namespace; never search/fallback or authorize."""
    prior = prior_runtime(root, before=root.get('issued_at_utc'))
    anchor = anchor if anchor is not None else (root.get('effective_epoch') or {}).get('previous_capture')
    if prior is not None and anchor == prior['anchor']:
        return prior['qualified_runtime'], prior['pending_census']
    return deepcopy(root['qualified_runtime']), deepcopy(root['pending_census'])


def checkpoint_runtime(root, handoff, *, anchor=None, checkpoint=None):
    prior = prior_runtime(root, before=root.get('issued_at_utc'))
    current = (deepcopy(root['qualified_runtime']), deepcopy(root['pending_census']))
    if prior is None: return current
    candidates = [current, (prior['qualified_runtime'], prior['pending_census'])]
    matches = [p for p in candidates if handoff.get('runtime_binding_sha256') == digest(p[0]['binding'])
        and handoff.get('qualified_package_sha256') == digest(p[0])]
    require(len(matches) == 1, 'UNIQUE_SEALED_CHECKPOINT_RUNTIME')
    if matches[0][0] == prior['qualified_runtime']:
        epoch = root.get('effective_epoch') or {}
        anchor = anchor if anchor is not None else epoch.get('previous_capture')
        checkpoint = checkpoint if checkpoint is not None else epoch.get('previous_checkpoint')
        require(anchor == prior['anchor'] and type(checkpoint) is dict and hashed(checkpoint.get('sha256'))
            and prior['root_static_sha256'] is not None, 'EXACT_REGISTERED_PRIOR_CHECKPOINT_RUNTIME')
    return matches[0]


def _descriptor(value):
    """Metadata-only checks of the unchanged native v2 restore descriptor.

No checkpoint module import: that module's owned-storage dependency imports
NumPy/pandas. Actual reads/writes still execute unchanged store.append/restore.
"""
    require(type(value) is dict and set(value) == {'entry','manifest_asset_id','manifest_sha256','manifest_bytes'},
        'CLOSED_TEMPLATE_NATIVE_DESCRIPTOR')
    entry=value['entry']
    require(type(entry) is dict and set(entry) == {'schema_version','payload','payload_asset_id','payload_name',
        'producer_process','binding_sha256','writer_run_id'}, 'CLOSED_TEMPLATE_NATIVE_ENTRY')
    p=entry['payload']
    require(type(p) is dict and set(p) == {'schema_version','payload_kind','format','bytes','sha256','source_policy_sha256'}
        and p['schema_version'] == 'weekly-private-payload-v2' and p['payload_kind'] == 'runtime_manifest'
        and p['format'] == 'gzip' and type(p['bytes']) is int and 0 < p['bytes'] <= PACKED_CAP
        and hashed(p['sha256']) and p['source_policy_sha256'] == POLICY_SHA, 'STATIC_TEMPLATE_NATIVE_PAYLOAD_SCOPE')
    require(entry['schema_version'] == 'weekly-private-restore-manifest-v2' and hashed(entry['producer_process'])
        and hashed(entry['binding_sha256']) and identifier(entry['writer_run_id'])
        and entry['payload_name'] == 'blob-'+p['sha256']+'.bin'
        and all(type(v) is int and 0 < v < 10**20 for v in (entry['payload_asset_id'],value['manifest_asset_id']))
        and type(value['manifest_bytes']) is int and value['manifest_bytes'] == len(store.canonical(entry)) <= ENTRY_CAP
        and value['manifest_sha256'] == digest(entry), 'EXACT_TEMPLATE_NATIVE_ENTRY_HASH')
    return entry


def _client_identity(client):
    return dict(execution_lane='github_actions',repository=store.REPO,source_sha=client.source_sha,
        run_id=client.run_id,run_attempt=1,process_identity=client.process,job_id=client.job['job_id'],
        api_job_id=client.job['api_job_id'],permission='write',workflow_ref=client.job['workflow_ref'])


def _metadata(value):
    count = 0
    def visit(v, depth):
        nonlocal count
        count += 1
        require(count <= 20000 and depth <= 24, 'FINITE_TEMPLATE_METADATA')
        if type(v) is dict:
            require(len(v) <= 512 and all(type(k) is str for k in v), 'CLOSED_TEMPLATE_METADATA_OBJECT')
            require(not (set(k.lower() for k in v) & DENIED_KEYS), 'TEMPLATE_PRIVATE_BODY_OR_CREDENTIAL_FORBIDDEN')
            for k, item in v.items():
                if k == 'policy_gzip_base64':
                    require(type(item) is str and len(item) <= 4*((PLAIN_CAP+2)//3), 'BOUNDED_ENCODED_PUBLIC_POLICY')
                    try: raw = base64.b64decode(item, validate=True)
                    except (ValueError, TypeError): raise TemplateError('INVALID_ENCODED_PUBLIC_POLICY') from None
                    with gzip.GzipFile(fileobj=io.BytesIO(raw)) as z: plain = z.read(PLAIN_CAP+1)
                    require(len(plain) <= PLAIN_CAP, 'PUBLIC_POLICY_INFLATION_CAP')
                    policy = decode_json(plain)
                    require(store.canonical(policy) == plain, 'CANONICAL_STATIC_PUBLIC_POLICY')
                    visit(policy, depth+1)
                else: visit(item, depth+1)
        elif type(v) is list:
            require(len(v) <= 4096, 'BOUNDED_TEMPLATE_METADATA_LIST')
            for item in v: visit(item, depth+1)
        elif type(v) is str:
            require(len(v) <= PLAIN_CAP and not re.search(
                r'(?:^|[^A-Za-z0-9])(?:gh[pousr]_|github_pat_|sk-[A-Za-z0-9]{12,}|AKIA[A-Z0-9]{12}|Bearer\s|-----BEGIN .*PRIVATE KEY)',v),
                'TEMPLATE_CREDENTIAL_VALUE_FORBIDDEN')
        else: require(v is None or type(v) in (bool,int,float), 'JSON_TEMPLATE_METADATA_ONLY')
    visit(value, 0)


REGISTRATION_ENVELOPE = 'audit-weekly-retained-registration-envelope-v1'
REGISTRATION_PLAIN_CAP = 128 << 10
REGISTRATION_ENCODED_CAP = 48 << 10


def retained_registration(root):
    """Losslessly read original registration bytes; never grant authority.

    This optional transport keeps the full source inventory inside the existing
    60KiB Root / GitHub dispatch ceilings. Original registration validation is
    still performed by its original validator after this bounded decode.
    """
    value = root['retained_registration']
    if type(value) is not dict or value.get('schema_version') != REGISTRATION_ENVELOPE:
        return value
    require(set(value) == {'schema_version','body_sha256','body_bytes','gzip_base64'}
        and hashed(value['body_sha256']) and type(value['body_bytes']) is int
        and 0 < value['body_bytes'] <= REGISTRATION_PLAIN_CAP
        and type(value['gzip_base64']) is str and 0 < len(value['gzip_base64']) <= REGISTRATION_ENCODED_CAP,
        'CLOSED_BOUNDED_RETAINED_REGISTRATION_ENVELOPE')
    try:
        packed = base64.b64decode(value['gzip_base64'], validate=True)
        with gzip.GzipFile(fileobj=io.BytesIO(packed)) as stream:
            raw = stream.read(value['body_bytes'] + 1)
        require(len(raw) == value['body_bytes'] and store.sha(raw) == value['body_sha256'],
            'EXACT_ORIGINAL_RETAINED_REGISTRATION_BYTES')
        reg = decode_json(raw)
        require(type(reg) is dict and store.canonical(reg) == raw
            and reg.get('schema_version') == 'audit-count-retained-v1-registration',
            'CANONICAL_ORIGINAL_RETAINED_REGISTRATION')
        _metadata(reg)  # Compression cannot hide forbidden/private-shaped data.
        return reg
    except TemplateError:
        raise
    except Exception:
        raise TemplateError('INVALID_RETAINED_REGISTRATION_ENVELOPE') from None


def registration_envelope(registration):
    """Prepare metadata only; original decoded body/hash remain unchanged."""
    require(type(registration) is dict
        and registration.get('schema_version') == 'audit-count-retained-v1-registration',
        'ORIGINAL_RETAINED_REGISTRATION_REQUIRED')
    _metadata(registration)
    raw = store.canonical(registration)
    value = dict(schema_version=REGISTRATION_ENVELOPE, body_sha256=store.sha(raw), body_bytes=len(raw),
        gzip_base64=base64.b64encode(gzip.compress(raw,mtime=0)).decode())
    require(retained_registration({'retained_registration':value}) == registration,
        'LOSSLESS_RETAINED_REGISTRATION_TRANSPORT')
    return value


def _pins(value):
    require(type(value) is dict and 0 < len(value) <= 192, 'BOUNDED_STATIC_SOURCE_PINS')
    for name, sha in value.items():
        require(type(name) is str and len(name) <= 256 and not Path(name).is_absolute() and str(Path(name)) == name
            and all(p not in {'','..','.'} and (not p.startswith('.') or i == 0 and p == '.github')
                for i,p in enumerate(Path(name).parts))
            and hashed(sha), 'EXACT_STATIC_SOURCE_PIN')


def _readiness(value):
    require(type(value) is dict and set(value) == controller.READY_KEYS
        and hashed(value['source_sha'],40) and identifier(value['run_id'])
        and type(value['branch']) is str and controller.branch(value['branch'])
        and all(hashed(value[k]) for k in ('workflow_sha256','receipt_sha256','receipt_body_sha256')),
        'STATIC_REGISTERED_READINESS_METADATA')
    require(type(value['jobs']) is dict and set(value['jobs']) == {'produce','restore','consume'}
        and all(type(j) is dict and set(j) == {'job_id','api_job_id'} and label(j['job_id'])
            and type(j['api_job_id']) is int and j['api_job_id'] > 0 for j in value['jobs'].values())
        and len({j['api_job_id'] for j in value['jobs'].values()}) == 3, 'EXACT_THREE_READINESS_JOBS')
    require(type(value['receipt_bindings']) is dict and set(value['receipt_bindings']) == controller.RECEIPT_HASH_KEYS
        and all(hashed(v) for v in value['receipt_bindings'].values()), 'READINESS_RECEIPT_HASH_BINDINGS')


def _document(value):
    require(type(value) is dict and set(value) == DOCUMENT_KEYS and value['schema_version'] in {VERSION+'-static',VERSION+'-static-v2',STATIC_V3}
        and hashed(value['source_sha'],40), 'CLOSED_STATIC_TEMPLATE_DOCUMENT')
    _pins(value['code_pins']); _readiness(value['readiness'])
    root = value['root_template']
    require(type(root) is dict and set(root) == root_keys(root) and root['approved'] is False
        and all(root[k] is None for k in ('issued_at_utc','expires_at_utc','operation','effective_epoch')),
        'STATIC_PLACEHOLDERS_ONLY_NO_EXPIRED_OR_ACTIVE_GO')
    require((value['schema_version'] == STATIC_V3) == (root['schema_version'] == ROOT_V3), 'MATCHING_STATIC_ROOT_VERSION')
    if value['schema_version'] == STATIC_V3:
        require(len(value['code_pins']) <= 128 and len(store.canonical(root)) <= 60 << 10, 'BOUNDED_DUAL_RUNTIME_STATIC_ROOT')
        prior_runtime(root)
    require(root['repository'] == store.REPO and root['mode'] == 'audit-weekly-producer-v1'
        and root['source_sha'] == value['source_sha'] and root['code_pins'] == value['code_pins']
        and root['single_writer_group'] == 'nfl-lab-single-writer'
        and re.fullmatch(re.escape(store.REPO)+r'/\.github/workflows/lab\.yml@refs/heads/[A-Za-z0-9_./-]+',str(root['workflow_ref'])),
        'STATIC_ROOT_SOURCE_AND_EXISTING_WORKFLOW')
    reg = retained_registration(root)
    require(type(reg) is dict and reg.get('schema_version') == 'audit-count-retained-v1-registration'
        and reg.get('approved') is True and type(reg.get('maximum_new_fits')) is int
        and reg['maximum_new_fits'] == 0 and reg.get('public_release') is False,
        'EXISTING_PRIVATE_RETAINED_REGISTRATION_REQUIRED')
    slots = reg.get('origin',{}).get('replay_catalog',{}).get('slots')
    require(type(slots) is list and len(slots) == 18, 'EXACT18_STATIC_RETAINED_CATALOG')
    for slot, expected in zip(slots, JOBS):
        require((slot.get('target'),slot.get('family'),slot.get('method_id')) == expected
            and all(hashed(slot.get(k)) for k in ('procedure_version','model_sha256','manifest_sha256','transport_manifest_sha256')),
            'EXACT_RETAINED_SLOT_METADATA')
    _metadata(value)
    plain = store.canonical(value)
    require(0 < len(plain) <= PLAIN_CAP, 'STATIC_TEMPLATE_PLAIN_CAP')
    return plain


@dataclass(frozen=True)
class Prepared:
    document: dict
    plain: bytes
    body: bytes
    def verify(self):
        require(_document(self.document) == self.plain and 0 < len(self.body) <= PACKED_CAP,
            'PREPARED_STATIC_TEMPLATE_CHANGED')
        with gzip.GzipFile(fileobj=io.BytesIO(self.body)) as z: recovered=z.read(PLAIN_CAP+1)
        require(recovered == self.plain and self.body[:8] == b'\x1f\x8b\x08\x00\x00\x00\x00\x00',
            'CANONICAL_STATIC_TEMPLATE_ENCODING')
        return self


def prepare(document):
    """Pure metadata validation/encoding. Never authorizes or accesses a client."""
    value = deepcopy(document); plain = _document(value); body = gzip.compress(plain,mtime=0)
    require(len(body) <= PACKED_CAP, 'STATIC_TEMPLATE_PACKED_CAP')
    return Prepared(value,plain,body)


def decode_static(body, *, template_sha256, template_bytes):
    require(type(body) is bytes and 0 < len(body) <= PACKED_CAP, 'STATIC_TEMPLATE_PACKED_CAP')
    with gzip.GzipFile(fileobj=io.BytesIO(body)) as z: plain = z.read(PLAIN_CAP+1)
    require(len(plain) == template_bytes <= PLAIN_CAP and store.sha(plain) == template_sha256,
        'STATIC_TEMPLATE_ORIGINAL_BODY_HASH')
    # Verify the original authenticated compressed bytes; do not require a
    # future runner's zlib to recompress them identically.
    return Prepared(decode_json(plain),plain,body).verify()


def _identity(value):
    require(type(value) is dict and set(value) == IDENTITY_KEYS and value['execution_lane'] == 'github_actions'
        and value['repository'] == store.REPO and type(value['run_attempt']) is int and value['run_attempt'] == 1 and identifier(value['run_id'])
        and hashed(value['source_sha'],40) and hashed(value['process_identity']) and label(value['job_id'])
        and type(value['api_job_id']) is int and value['api_job_id'] > 0 and value['permission'] == 'write'
        and re.fullmatch(re.escape(store.REPO)+r'/\.github/workflows/lab\.yml@refs/heads/[A-Za-z0-9_./-]+',str(value['workflow_ref'])),
        'GENUINE_TEMPLATE_JOB_LOCATOR')
    return value


def _handoff(value, *, sealed=False):
    require(type(value) is dict and set(value) == (SEAL_KEYS if sealed else HANDOFF_KEYS)
        and value['schema_version'] == VERSION+('-seal' if sealed else '-appended') and value['repository'] == store.REPO
        and hashed(value['template_sha256']) and type(value['template_bytes']) is int and 0 < value['template_bytes'] <= PLAIN_CAP
        and hashed(value['root_go_sha256']), 'CLOSED_TEMPLATE_ARTIFACT_LOCATOR')
    b=store.checked_binding(value['binding']); e=_descriptor(value['descriptor'])
    w=_identity(value['writer'])
    require(e['writer_run_id'] == w['run_id'] and e['producer_process'] == w['process_identity']
        and e['binding_sha256'] == digest(b), 'EXACT_TEMPLATE_NATIVE_WRITER')
    store.utc(value['appended_at_utc'])
    if sealed:
        r=_identity(value['reader'])
        require(r['run_id'] == w['run_id'] and r['source_sha'] == w['source_sha'] and r['workflow_ref'] == w['workflow_ref']
            and r['api_job_id'] != w['api_job_id'] and r['job_id'] != w['job_id']
            and r['process_identity'] != w['process_identity'] and hashed(value['reader_proof_sha256'])
            and store.utc(value['appended_at_utc']) <= store.utc(value['verified_at_utc']), 'INDEPENDENT_NATIVE_TEMPLATE_READER')
    require(len(store.canonical(value)) <= 16 << 10, 'SAFE_TEMPLATE_LOCATOR_CAP')
    return value


def _package(client, package):
    require(type(package) is dict and package.get('schema_version') == 'audit-private-rotation-v1-qualified-runtime'
        and package.get('runtime_reserved_bytes') == store.TOTAL_CAP and package['binding'] == client.binding,
        'EXACT_QUALIFIED_TEMPLATE_NAMESPACE')
    owner.archived_qualification(client.binding,package['qualification'])
    owner.authenticate_past_run(client,package['qualification']); owner.verify_canary(client)
    reservation=package['quota_reservation']
    require(reservation['global_cap_bytes'] == 512 << 20 and reservation['reserved_after_bytes'] <= 512 << 20
        and reservation['new_runtime_id'] == client.binding['runtime_id'], 'ORIGINAL_GLOBAL_RESERVATION_REQUIRED')


def _get_json(client, path):
    url=store.API+path;client.allowed.add(url)
    return client.json(url)


def _run_jobs(client, identity, *, completed, whole_run_complete=False):
    base='/actions/runs/'+identity['run_id']
    run=_get_json(client,base); listing=_get_json(client,base+'/jobs?per_page=100&page=1')
    require(run.get('id') == int(identity['run_id']) and run.get('head_sha') == identity['source_sha']
        and run.get('repository',{}).get('full_name') == run.get('head_repository',{}).get('full_name') == store.REPO
        and run.get('event') == 'workflow_dispatch' and run.get('run_attempt') == 1 and run.get('path') == controller.WORKFLOW
        and run.get('head_branch') == identity['workflow_ref'].split('@refs/heads/',1)[1]
        and run.get('actor',{}).get('login') == 'NickNicky19' and run.get('actor',{}).get('id') == 208912933,
        'ACTUAL_OWNER_TEMPLATE_RUN_REQUIRED')
    if whole_run_complete:
        require(run.get('status') == 'completed' and run.get('conclusion') == 'success',
            'ORIGINAL_OWNER_TEMPLATE_RUN_COMPLETED_SUCCESSFULLY')
    require(type(listing.get('jobs')) is list and listing.get('total_count') == len(listing['jobs']) <= 100,
        'COMPLETE_TEMPLATE_JOB_LIST')
    matches=[j for j in listing['jobs'] if j.get('id') == identity['api_job_id']]
    require(len(matches) == 1, 'EXACT_TEMPLATE_API_JOB')
    j=matches[0]
    require(j.get('name') == identity['job_id'] and j.get('run_id') == int(identity['run_id'])
        and j.get('head_sha') == identity['source_sha'] and j.get('status') == ('completed' if completed else 'in_progress')
        and j.get('conclusion') == ('success' if completed else None), 'ACTUAL_TEMPLATE_JOB_STATUS')
    if completed: require(store.utc(j['started_at']) <= store.utc(j['completed_at']) <= now(), 'COMPLETED_TEMPLATE_JOB_CLOCK')
    return j


def _native(client, package, root_go_sha256, phase, input_sha256, check_authority):
    require(callable(check_authority) and hashed(root_go_sha256), 'LIVE_ROOT_AUTHORITY_CALLBACK_REQUIRED')
    request=digest(dict(phase=phase,input_sha256=input_sha256,root_go_sha256=root_go_sha256))
    require(check_authority(request) is None, 'ROOT_CALLBACK_MUST_ENFORCE_NOT_RETURN_FLAGS')
    client.authenticate_actions_job()
    require(client.job['execution_lane'] == 'github_actions' and client.job['run_authenticated'] is True
        and client.job['permission'] == 'write' and client.job['event_name'] == 'workflow_dispatch'
        and client.job['workflow_sha'] == client.source_sha and client.operation == phase, 'ACTUAL_NATIVE_TEMPLATE_CLIENT')
    identity=_client_identity(client); _identity(identity)
    _run_jobs(client,identity,completed=False); _package(client,package)
    return identity


def append(prepared, client, package, *, storage, output, root_go_sha256, check_authority):
    """One native append in the genuine owner registration job. No dispatch."""
    prepared.verify(); output=store.parents_safe(output)
    require(not output.exists(), 'ONE_TEMPLATE_APPEND_NO_RETRY')
    identity=_native(client,package,root_go_sha256,'append',store.sha(prepared.plain),check_authority)
    require(identity['source_sha'] == prepared.document['source_sha'], 'TEMPLATE_WRITER_SOURCE_MISMATCH')
    storage.register_root(output)
    storage.write_bytes(output/'APPEND_INTENT.json',store.canonical(dict(template_sha256=store.sha(prepared.plain),fits=0)))
    assets,total=client.inventory()
    require(not any(a['name'] == 'blob-'+store.sha(prepared.body)+'.bin' for a in assets), 'STATIC_TEMPLATE_ALREADY_APPENDED')
    require(total+len(prepared.body)+ENTRY_CAP <= store.TOTAL_CAP and client.inventory_slots+2 <= store.MAX_ASSETS,
        'COMPLETE_TEMPLATE_APPEND_QUOTA_BEFORE_POST')
    manifest=dict(schema_version='weekly-private-payload-v2',payload_kind='runtime_manifest',format='gzip',
        bytes=len(prepared.body),sha256=store.sha(prepared.body),source_policy_sha256=POLICY_SHA)
    store.payload_manifest(manifest,prepared.body)
    descriptor=store.append(client,prepared.body,manifest,package['qualification'])
    result=dict(schema_version=VERSION+'-appended',repository=store.REPO,binding=deepcopy(client.binding),descriptor=descriptor,
        template_sha256=store.sha(prepared.plain),template_bytes=len(prepared.plain),writer=identity,
        root_go_sha256=root_go_sha256,appended_at_utc=now().isoformat())
    _handoff(result);storage.write_bytes(output/'APPENDED.json',store.canonical(result));return result


def restore(handoff, client, package, *, storage, output, root_go_sha256, check_authority):
    """Actual fresh dispatch reader; returns safe seal and separate native proof."""
    _handoff(handoff); output=store.parents_safe(output)
    require(not output.exists(), 'ONE_TEMPLATE_RESTORE_NO_RETRY')
    current=_native(client,package,root_go_sha256,'restore',digest(handoff),check_authority)
    require(root_go_sha256 == handoff['root_go_sha256'] and client.binding == handoff['binding']
        and current['run_id'] == handoff['writer']['run_id'] and current['source_sha'] == handoff['writer']['source_sha']
        and current['api_job_id'] != handoff['writer']['api_job_id'] and current['job_id'] != handoff['writer']['job_id']
        and current['process_identity'] != handoff['writer']['process_identity'], 'INDEPENDENT_CURRENT_TEMPLATE_READER')
    writer=_run_jobs(client,handoff['writer'],completed=True)
    require(store.utc(writer['completed_at']) <= store.utc(client.started_at), 'TEMPLATE_WRITER_PRECEDES_READER')
    storage.register_root(output)
    proof=store.restore(client,handoff['descriptor'],output/'STATIC_ROOT_TEMPLATE.json.gz')
    body=store.read_local(output/'STATIC_ROOT_TEMPLATE.json.gz',PACKED_CAP)
    decode_static(body,template_sha256=handoff['template_sha256'],template_bytes=handoff['template_bytes'])
    # check_proof verifies evidence from ANOTHER process; never relabel this
    # client's identity to self-verify the proof just minted by native restore.
    entry=handoff['descriptor']['entry']['payload']
    require(set(proof) == store.BASE_PROOF_FIELDS | store.PHASE_FIELDS['restore']
        and proof['schema_version'] == 'weekly-private-proof-v2.1' and proof['phase'] == proof['operation'] == 'restore'
        and proof['run_id'] == current['run_id'] and proof['source_sha'] == current['source_sha']
        and proof['job'] == client.job and proof['process_identity'] == client.process
        and proof['binding_sha256'] == digest(client.binding) and proof['config_sha256'] == store.config_sha()
        and proof['exact_readback'] is proof['separate_process'] is proof['draft_before_after'] is True
        and proof['payload_sha256'] == entry['sha256'] and proof['bytes'] == entry['bytes'],
        'ACTUAL_CURRENT_NATIVE_TEMPLATE_RESTORE_RESULT')
    seal=dict(deepcopy(handoff),schema_version=VERSION+'-seal',reader=current,
        reader_proof_sha256=digest(proof),verified_at_utc=now().isoformat())
    _handoff(seal,sealed=True)
    storage.write_bytes(output/'NATIVE_RESTORE_PROOF.json',store.canonical(proof))
    storage.write_bytes(output/'SAFE_SEAL.json',store.canonical(seal))
    return dict(seal=seal,proof=proof)


class ParentGETClient:
    """Separate schedule lane. No core Client construction or native proof minting.

authenticate(seal_sha256) must enforce trusted owner registration AND current
parent API guard, returning a live controller.Proof. Its API budget and the
native 180s/120CPU/512MiB process envelope are enforced by the parent; this
client additionally bounds its own exchanges and callback invocations.
"""
    path=store.Client.path
    browser=store.Client.browser
    bind=store.Client.bind
    draft=store.Client.draft
    inventory=store.Client.inventory
    asset=store.Client.asset
    read_asset=store.Client.read_asset

    def __init__(self, token, *, seal_sha256, registration_sha256, parent_run_id, parent_job_id,
            authenticate, journal, transport=None, clock=time.monotonic):
        require(type(token) is str and token.startswith('ghs_') and not any(c.isspace() for c in token), 'AUTOMATIC_PARENT_TOKEN_ONLY')
        require(hashed(seal_sha256) and hashed(registration_sha256) and identifier(parent_run_id)
            and label(parent_job_id) and callable(authenticate), 'TRUSTED_SEAL_AND_LIVE_PARENT_CALLBACK_REQUIRED')
        self._token=token;self.seal_sha256=seal_sha256;self.registration_sha256=registration_sha256
        self.parent_run_id=parent_run_id;self.parent_job_id=parent_job_id;self.authenticate=authenticate
        self.journal=store.parents_safe(journal)
        require(self.journal.is_dir() and not self.journal.stat().st_mode & 0o077, 'PRIVATE_PARENT_JOURNAL_REQUIRED')
        self.transport=transport or store.network;self.clock=clock;self.started=clock();self.calls=0;self.transferred=0
        self.allowed=set();self.binding=None;self.live_parent_sha256=None;self.authentication_calls=0;self.parent_started_at=None
        self.asset_ids=set();self.run_ids=set()

    def guard(self):
        require(self.clock()-self.started < LIMITS['wall_seconds'] and self.calls < LIMITS['HTTP_calls']
            and self.authentication_calls < LIMITS['authentication_callbacks'], 'BOUNDED_PARENT_TEMPLATE_GET')
        self.authentication_calls+=1
        proof=self.authenticate(self.seal_sha256)
        require(type(proof) is controller.Proof and proof.document.get('schema_version') == controller.VERSION+'-parent-proof',
            'LIVE_TYPED_PARENT_PROOF_REQUIRED')
        proof.verify(registration_sha256=self.registration_sha256,run_id=self.parent_run_id,job_id=self.parent_job_id)
        verified=store.utc(proof.document['scheduled_parent']['verified_at_utc'])
        require(verified <= now() and (now()-verified).total_seconds() <= LIMITS['wall_seconds'], 'FRESH_LIVE_PARENT_PROOF_REQUIRED')
        self.live_parent_sha256=proof.sha256
        self.parent_started_at=store.utc(proof.document['scheduled_parent']['job_started_at'])

    def _route(self,url):
        if self.binding is None:return False
        release=store.API+'/releases/'+str(self.binding['release_id'])
        if url == release or re.fullmatch(re.escape(release)+r'/assets\?per_page=100&page=[1-4]',url):return True
        for asset_id in self.asset_ids:
            if url == store.API+'/releases/assets/'+str(asset_id):return True
        return any(url in {store.API+'/actions/runs/'+r,store.API+'/actions/runs/'+r+'/jobs?per_page=100&page=1'} for r in self.run_ids)

    def allow(self,url):
        require(self._route(url) or self.binding is not None and url == self.browser(), 'TEMPLATE_METADATA_GET_ROUTE_ONLY')
        self.allowed.add(url);return url

    def request(self,url,*,method='GET',data=None,anonymous=False,octet=False,download=False,cap=store.META_CAP):
        require(method == 'GET' and data is None and not anonymous and url in self.allowed and self._route(url),
            'PARENT_TEMPLATE_GET_ONLY_NO_MUTATIONS')
        require(0 < cap <= store.ASSET_CAP, 'BOUNDED_TEMPLATE_RESPONSE')
        current=url
        for hop in range(LIMITS['redirects']+1):
            self.guard()
            target=urlsplit(current)
            require(target.scheme == 'https' and not target.username and not target.password and not target.port and not target.fragment,
                'TEMPLATE_REDIRECT_FORBIDDEN')
            headers={'Accept':'application/octet-stream' if octet else 'application/vnd.github+json',
                'Cache-Control':'no-cache','X-GitHub-Api-Version':'2022-11-28'}
            if hop == 0:
                require(current.startswith(store.API+'/') and current in self.allowed, 'EXACT_REGISTERED_TEMPLATE_ROUTE')
                headers['Authorization']='Bearer '+self._token
            else: require(target.hostname in store.probe.CDN_HOSTS, 'TEMPLATE_REDIRECT_FORBIDDEN')
            self.calls+=1
            try:
                with self.transport(Request(current,method='GET',headers=headers),20) as response:
                    status=response.status;observed={k.lower():v for k,v in response.headers.items()}
                    length=observed.get('content-length')
                    require(length is None or length.isdigit() and int(length) <= cap, 'TEMPLATE_RESPONSE_CAP')
                    body=response.read(cap+1)
            except (URLError,OSError,TimeoutError): raise TemplateError('TEMPLATE_GET_FAILED_NO_RETRY') from None
            self.transferred+=len(body)
            require(len(body) <= cap and self.transferred <= LIMITS['transfer_bytes'], 'TEMPLATE_TRANSFER_CAP')
            require(self.clock()-self.started < LIMITS['wall_seconds'], 'BOUNDED_PARENT_TEMPLATE_GET')
            require('retry-after' not in observed and observed.get('x-ratelimit-remaining') != '0', 'TEMPLATE_API_RATE_GUARD')
            if status in {301,302,303,307,308}:
                require(download and hop < LIMITS['redirects'], 'TEMPLATE_REDIRECT_FORBIDDEN')
                current=observed.get('location','');continue
            require(status == 200, 'TEMPLATE_GET_STATUS')
            return status,observed,body
        raise TemplateError('TEMPLATE_REDIRECT_FORBIDDEN')

    def json(self,url,**kwargs): return decode_json(self.request(url,**kwargs)[2])


def recover_for_parent(seal, package, client, *, storage, output):
    """GET-only metadata derivative. Caller independently authenticated seal first."""
    _handoff(seal,sealed=True)
    require(type(client) is ParentGETClient and digest(seal) == client.seal_sha256, 'INDEPENDENTLY_TRUSTED_TEMPLATE_SEAL_REQUIRED')
    output=store.parents_safe(output);require(not output.exists(), 'ONE_PARENT_TEMPLATE_READ_NO_RETRY')
    client.guard()
    client.asset_ids={seal['binding']['canary_asset_id'],seal['descriptor']['manifest_asset_id'],seal['descriptor']['entry']['payload_asset_id']}
    client.run_ids={seal['writer']['run_id'],package['qualification']['run_id']}
    client.bind(seal['binding']);_package(client,package)
    _run_jobs(client,seal['writer'],completed=True,whole_run_complete=True)
    reader=_run_jobs(client,seal['reader'],completed=True,whole_run_complete=True)
    require(store.utc(reader['completed_at']) <= client.parent_started_at <= now(), 'ORIGINAL_TEMPLATE_READER_PRECEDES_PARENT')
    d=seal['descriptor'];e=d['entry'];client.draft()
    saved=client.read_asset(d['manifest_asset_id'],'manifest-'+d['manifest_sha256']+'.json',d['manifest_bytes'],d['manifest_sha256'])
    require(saved == store.canonical(e), 'EXACT_ORIGINAL_TEMPLATE_NATIVE_ENTRY')
    p=e['payload'];body=client.read_asset(e['payload_asset_id'],e['payload_name'],p['bytes'],p['sha256']);client.draft()
    prepared=decode_static(body,template_sha256=seal['template_sha256'],template_bytes=seal['template_bytes'])
    require(prepared.document['source_sha'] == seal['writer']['source_sha'], 'ORIGINAL_TEMPLATE_SOURCE_BINDING')
    storage.register_root(output)
    result=dict(schema_version=VERSION+'-current-parent-metadata',created_at_utc=now().isoformat(),
        seal_sha256=client.seal_sha256,template_sha256=seal['template_sha256'],live_parent_sha256=client.live_parent_sha256,
        original_reader_proof_sha256=seal['reader_proof_sha256'],document=prepared.document,
        native_durability_qualified=False,execution_authority=False,forecast_authority=False,public_authority=False,
        fits=0,model_decodes=0)
    storage.write_bytes(output/'CURRENT_PARENT_METADATA.json',store.canonical(result));return result
