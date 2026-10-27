"""Fictional failed-byte scope only; no Actions, authentication, POST or models.

Execute the actual parent method, isolated from unrelated root initialization
when the assembly does not yet contain that module. Intercept archive.produce
at entry, before its factory/authentication/transport. This proves a complete
owned snapshot and codec bytes, not hosted authorization or durability.
"""
import ast
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from nfl_lab import audit_weekly_archive_v1 as archive
from nfl_lab import gha_private_checkpoint as cp, private_draft_store as store
from nfl_lab import owner_bootstrap_bundle as codec
from nfl_lab.operational_storage import OperationalStorage, _OWNER
from nfl_lab.owned_reference_batch import validate_owned_references
from nfl_lab.state import now_utc


ROOT = Path(__file__).resolve().parents[1]


class BeforePost(Exception):
    """The test deliberately stops before any transport/authentication call."""


def parent_preserver():
    source = ROOT/'nfl_lab/audit_weekly_hosted_v1.py'
    if not source.is_file():
        source = ROOT.parent/'producer-runtime-fix/nfl_lab/audit_weekly_hosted_v1.py'
    assert source.is_file(), 'actual parent root source is required, never skip scope checks'
    tree = ast.parse(source.read_text(), filename=str(source))
    runner = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'Runner')
    method = next(node for node in runner.body if isinstance(node, ast.FunctionDef) and node.name == 'preserve_opaque_outputs')
    require = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'require')
    jobs = next(node for node in tree.body if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == 'JOBS' for target in node.targets))
    # Only the actual method and its closed metadata dependencies are compiled;
    # the root initializer, services, credentials and execution modes never run.
    namespace = dict(__name__='nfl_lab.audit_weekly_hosted_fixture',
        archive=archive, cp=cp, store=store, _OWNER=_OWNER, now_utc=now_utc)
    exec(compile(ast.Module(body=[jobs, require, method], type_ignores=[]), str(source), 'exec'), namespace)
    return namespace['preserve_opaque_outputs'], namespace['JOBS']


def fixture(tmp_path, *, partial):
    root = tmp_path/'fictional-failed-attempt'
    storage = OperationalStorage(root/'cache', ROOT/'config/operational-source-policy-v2.json', state=root/'state')
    storage.register_root(root)
    included = {}

    def put(relative, body, logical):
        storage.write_bytes(root/relative, body)
        included[logical] = (root/relative, body)

    for name in ('OWNER_ROOT.json', 'QUALIFIED_RUNTIME.json', 'BOOTSTRAP_STARTED.json',
            'BOOTSTRAP_FAILED.json', 'BOOTSTRAP_REAUTHENTICATED.json', 'PARENT_STARTED.json'):
        put(name, store.canonical(dict(fictional_control=name, fits=0, successful_forecast=False)), 'failed/bootstrap/'+name)
    for name in ('SOURCE_FINISHED.json', 'SOURCE_FAILED.json', 'CONSUMED.json'):
        put('source/'+name, store.canonical(dict(fictional_source_control=name, public_release=False)), 'failed/source-metadata/'+name)
    put('prepared/PREPARED.json', b'{"fictional_prepared":true,"current_values_used":false}', 'failed/prepared-metadata/PREPARED.json')
    controls = {
        'metadata/EPOCH.json': b'{"fictional_epoch":true,"scientific_qualification":false}',
        'phase-status/00-source.json': b'{"reason":"FICTIONAL_SOURCE_FAILURE","exit_code":137}',
        'phase-status/PARENT_FAILED.json': b'{"reason":"FICTIONAL_PARENT_FAILURE","successful_forecast":false}',
        'requests/01-infer.json': b'{"fictional_request":true,"fits":0}',
        'journal/original.payload.reservation.json': b'{"schema_version":"weekly-private-POST-reservation-v2","key":"FICTIONAL_PAYLOAD","bytes":9}',
        'journal/original.manifest.reservation.json': b'{"schema_version":"weekly-private-POST-reservation-v2","key":"FICTIONAL_MANIFEST","bytes":11}',
        'journal/nested/original.receipt.json': b'{"fictional_ambiguous_POST":true,"automatic_retries":0}',
    }
    if partial:
        controls.update({
            'runtime/FINISHED.json': b'{"state":"PARTIAL_RETAINED_NOT_QUALIFIED","successful_forecast":false}',
            # Intentionally incomplete opaque bytes: never decode or repair a
            # partial forecast body in this failure-only scope.
            'runtime/candidates/rec/COUNT_A.jsonl.gz': b'FICTIONAL_PARTIAL_FORECAST_BYTES\x00\xff',
            'runtime/model-status/rec-COUNT_A.json': b'{"state":"FAILED_RETAINED","issued_rows":1,"expected_rows":2,"attempt_qualified":false}',
            'runtime/empty-interrupted.bin': b'',
            'reference/WORKER_FAILED.json': b'{"state":"FAILED_PRIVATE_REFERENCE_ATTEMPT_RETAINED","public_release":false}',
        })
    for relative, body in controls.items():
        put(relative, body, 'failed/'+relative)

    # Create real internal owner markers; none is an archive file.
    for name in ('source', 'prepared', 'metadata', 'phase-status', 'requests', 'journal') + (('runtime', 'reference') if partial else ()):
        storage.register_root(root/name)

    excluded = {}
    for relative in ('source/raw/schedules.csv', 'source/raw/roster.parquet',
            'source/raw-http-corpus.bin', 'source/frames/stats.parquet',
            'prepared/private-extra.json', 'prepared/model-weights.bin',
            'cache/raw/private-cache.bin', 'retained/models/trained.joblib', 'models/weights.bin'):
        body = b'FICTIONAL_RAW_SECRET_OR_WEIGHT_NEVER_COLLECTED:'+relative.encode()
        storage.write_bytes(root/relative, body)
        excluded[relative] = body
    package = dict(fixture_only=True, authentication_or_qualification_claim=False)
    # Collection stops before the client factory; this legacy fixture supplies no live grant.
    # Authentication gates are exercised separately by the real Runner tests.
    runner = SimpleNamespace(root=root, storage=storage, started=now_utc()-timedelta(seconds=30),
        fresh_operations_proof=lambda: None, require_pending_scope=lambda: None,
        go=dict(qualified_runtime=package, pending_census=dict(fixture_no_remote_census=True)),
        go_sha=store.sha(b'FICTIONAL_OWNER_ROOT'), env=dict(GITHUB_OUTPUT=str(tmp_path/'unused-output')))
    return SimpleNamespace(runner=runner, included=included, excluded=excluded, package=package)


def verify_before_post(case, monkeypatch):
    method, jobs = parent_preserver()
    runner = case.runner
    observed = []

    def inspect(snapshot, factory, package, **kwargs):
        observed.append(snapshot)
        assert callable(factory) and package is case.package
        assert kwargs['storage'] is runner.storage
        assert kwargs['jobs'] == jobs and kwargs['root_go_sha256'] == runner.go_sha
        assert kwargs['pending_census'] == runner.go['pending_census']
        files = snapshot['files']; census = snapshot['census']
        assert set(snapshot) == {'files', 'census'}
        assert [item['logical_path'] for item in files] == sorted(case.included)
        assert len(files) == len(case.included) == census['logical_files']
        assert census['logical_bytes'] == sum(len(body) for _, body in case.included.values())
        assert set(census['physical_origins']) == set(case.included)
        assert census['schema_version'] == archive.VERSION+'-failed-opaque-census'
        assert census['archive_state'] == 'FAILURE_EVIDENCE'
        assert census['raw_HTTP_corpus_archived'] is census['model_weights_reuploaded'] is False
        assert census['public_release'] is census['successful_forecast'] is False
        assert census['fits'] == 0 and census['source_started_at'] == runner.started.isoformat()
        assert runner.started <= store.utc(census['actual_collected_at']) <= store.utc(census['source_completed_at']) <= now_utc()
        archive.validate_files(files)
        validate_owned_references(runner.storage, {item['path']:item['sha256'] for item in files})
        by_name = {item['logical_path']:item for item in files}
        for logical, (original, body) in case.included.items():
            item = by_name[logical]
            assert census['physical_origins'][logical] == cp.binding(original)
            assert store.read_local(original, store.ASSET_CAP) == body
            assert Path(item['path']).read_bytes() == body
            assert item['bytes'] == len(body) and item['sha256'] == store.sha(body)
            assert item['required'] is True and item['kind'] in {'control', 'forecast'}
            assert Path(item['path']).is_relative_to(runner.root/'failure-opaque-collection')
        validation = archive.validate_capture(snapshot, lambda name:Path(by_name[name]['path']), complete=False)
        assert validation['state'] == 'FAILURE_EVIDENCE' and validation['qualified_selected'] is False

        # Use the real unchanged codec. Explicit empty files stay in the index
        # census; positive original bodies round-trip without any truncation.
        decoded = {name:b'' for name,item in by_name.items() if item['bytes'] == 0}
        groups = codec.groups([item for item in files if item['bytes']])
        assert len(groups) <= archive.MAX_GROUPS
        for members in groups:
            body, inflated = codec.encode(members)
            record = dict(bytes=len(body), sha256=store.sha(body), inflated_bytes=inflated, files=members)
            decoded.update(codec.verify_bundle(body, record))
        assert decoded == {name:body for name,(_,body) in case.included.items()}
        assert not any(raw in value for raw in case.excluded.values() for value in decoded.values())
        assert not any(item['kind'] in {'model', 'model_manifest', 'source_raw'} for item in files)
        # No transport factory, native client, authentication or POST is called.
        raise BeforePost

    monkeypatch.setattr(archive, 'produce', inspect)
    with pytest.raises(BeforePost): method(runner)
    assert len(observed) == 1
    assert not Path(runner.env['GITHUB_OUTPUT']).exists()
    assert not (runner.root/'archive-produce').exists()
    return observed[0]


def test_partial_runtime_preserves_complete_boot_source_phase_and_POST_controls(tmp_path, monkeypatch):
    case = fixture(tmp_path, partial=True)
    snapshot = verify_before_post(case, monkeypatch)
    by_name = {item['logical_path']:Path(item['path']).read_bytes() for item in snapshot['files']}
    assert by_name['failed/phase-status/00-source.json'] == b'{"reason":"FICTIONAL_SOURCE_FAILURE","exit_code":137}'
    assert by_name['failed/runtime/candidates/rec/COUNT_A.jsonl.gz'] == b'FICTIONAL_PARTIAL_FORECAST_BYTES\x00\xff'
    assert by_name['failed/runtime/empty-interrupted.bin'] == b''
    assert {name for name in by_name if name.endswith('.reservation.json')} == {
        'failed/journal/original.payload.reservation.json', 'failed/journal/original.manifest.reservation.json'}


def test_pre_runtime_failure_still_archives_all_fixed_boot_and_source_metadata(tmp_path, monkeypatch):
    case = fixture(tmp_path, partial=False)
    assert not (case.runner.root/'runtime').exists() and not (case.runner.root/'reference').exists()
    snapshot = verify_before_post(case, monkeypatch)
    names = {item['logical_path'] for item in snapshot['files']}
    assert {name for name in names if name.startswith('failed/bootstrap/')} == {
        'failed/bootstrap/'+name for name in ('OWNER_ROOT.json', 'QUALIFIED_RUNTIME.json', 'BOOTSTRAP_STARTED.json',
            'BOOTSTRAP_FAILED.json', 'BOOTSTRAP_REAUTHENTICATED.json', 'PARENT_STARTED.json')}
    assert 'failed/source-metadata/SOURCE_FAILED.json' in names
    assert 'failed/prepared-metadata/PREPARED.json' in names
