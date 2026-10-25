"""Exact fictional 555-file failure scope; no clients, POSTs or native proofs.

Run the real Root method through the existing AST fixture, then the unchanged
group codec and independent archive validator. Original control bytes remain
immutable. No actual private capture data, credentials, models or outcomes.
"""
import base64
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from nfl_lab import audit_weekly_archive_v1 as archive
from nfl_lab import gha_private_checkpoint as cp, private_draft_store as store
from nfl_lab import owner_bootstrap_bundle as codec
from nfl_lab.owned_reference_batch import validate_owned_references
import test_audit_weekly_failed_scope_v1 as scope


BUNDLE = 'failed/reference/SOURCE_OBSERVATIONS_BUNDLE.json'
SCHEMA = 'audit-weekly-hosted-v2-original-source-observations-bundle'
PREFIX = 'failed/reference/source-observations/'


def original_case(tmp_path):
    case = scope.fixture(tmp_path, partial=False)
    storage, root = case.runner.storage, case.runner.root
    storage.register_root(root/'reference')

    def put(relative, body):
        path = root/relative
        storage.write_bytes(path, body)
        case.included['failed/'+relative] = (path, body)

    # These look like receipts but are not eligible direct-child BEGIN/END
    # files. Their original incomplete bytes must stay directly archived.
    put('reference/source-observations/0001-BEGIN.json.tmp', b'FICTIONAL interrupted control\x00\xff')
    put('reference/source-observations/nested/0001-BEGIN.json', b'FICTIONAL nested original control\x00')
    for n in range(211-len(case.included)):
        put(f'metadata/retained-controls/{n:04d}.json', store.canonical(dict(
            schema_version='fictional-retained-control-v1', ordinal=n,
            successful_forecast=False, public_release=False, fits=0)))
    assert len(case.included) == 211

    case.receipts = {}
    for n in range(1, 173):
        request_sha = store.sha(f'FICTIONAL REQUEST {n}'.encode())
        for phase in ('BEGIN', 'END'):
            value = dict(schema_version='audit-reference-capture-v1-source-'+(
                'start' if phase == 'BEGIN' else 'observation'), request_sha256=request_sha,
                started_at='2099-01-01T00:00:00+00:00')
            if phase == 'BEGIN':
                value['host'] = 'api.sleeper.app'
            else:
                value.update(completed_at='2099-01-01T00:00:01+00:00', status='OBSERVED',
                    bytes=n, payload_sha256=store.sha(f'FICTIONAL RESPONSE {n}'.encode()))
            relative = f'reference/source-observations/{n:04d}-{phase}.json'
            # Deliberately varied valid JSON whitespace must survive intact.
            body = store.canonical(value)+(b'\n' if n % 2 else b'')
            put(relative, body)
            case.receipts['failed/'+relative] = (root/relative, body)
    assert len(case.receipts) == 344 and len(case.included) == 555
    return case


@pytest.fixture(scope='module')
def captured(tmp_path_factory):
    case = original_case(tmp_path_factory.mktemp('receipt-bundle'))
    method, jobs = scope.parent_preserver()
    snapshots = []

    def before_post(snapshot, factory, package, **kwargs):
        assert callable(factory) and package is case.package
        assert kwargs['storage'] is case.runner.storage
        assert kwargs['root_go_sha256'] == case.runner.go_sha and kwargs['jobs'] == jobs
        assert kwargs['pending_census'] == case.runner.go['pending_census']
        snapshots.append(snapshot)
        raise scope.BeforePost

    def forbidden_client(*args, **kwargs):
        raise AssertionError('no transport factory or native client may execute')

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(archive, 'produce', before_post)
        patch.setattr(archive, 'Client', forbidden_client)
        with pytest.raises(scope.BeforePost):
            method(case.runner)
    assert len(snapshots) == 1
    assert not Path(case.runner.env['GITHUB_OUTPUT']).exists()
    assert not (case.runner.root/'archive-produce').exists()
    return SimpleNamespace(case=case, snapshot=snapshots[0])


def codec_roundtrip(snapshot):
    files = snapshot['files']
    archive.validate_files(files)
    decoded = {f['logical_path']:b'' for f in files if not f['bytes']}
    groups = codec.groups([f for f in files if f['bytes']])
    assert len(groups) <= archive.MAX_GROUPS == 8
    for members in groups:
        body, inflated = codec.encode(members)
        record = dict(bytes=len(body), sha256=store.sha(body), inflated_bytes=inflated, files=members)
        decoded.update(codec.verify_bundle(body, record))
    assert set(decoded) == {f['logical_path'] for f in files}
    return decoded


def test_exact_555_originals_roundtrip_as_212_transport_files(captured):
    case, snapshot = captured.case, captured.snapshot
    files, census = snapshot['files'], snapshot['census']
    assert archive.MAX_FILES == 512
    assert len(files) == census['logical_files'] == 212
    assert census['logical_bytes'] == sum(f['bytes'] for f in files)
    direct = set(case.included)-set(case.receipts)
    expected = direct | {BUNDLE}
    assert [f['logical_path'] for f in files] == sorted(expected)
    assert set(census['physical_origins']) == expected
    assert census['archive_state'] == 'FAILURE_EVIDENCE'
    assert census['fits'] == 0
    assert census['public_release'] is census['successful_forecast'] is False
    assert census['raw_HTTP_corpus_archived'] is census['model_weights_reuploaded'] is False
    assert all(f['required'] and f['kind'] == 'control' for f in files)
    validate_owned_references(case.runner.storage, {f['path']:f['sha256'] for f in files})

    decoded = codec_roundtrip(snapshot)
    bundle_body = decoded.pop(BUNDLE)
    assert len(bundle_body) < 1 << 20
    bundle = cp.strict_json(bundle_body)
    assert set(bundle) == {'schema_version', 'records'} and bundle['schema_version'] == SCHEMA
    assert store.canonical(bundle) == bundle_body
    records = bundle['records']
    assert len(records) == 344
    assert [r['logical_path'] for r in records] == sorted(case.receipts)
    assert census['bundled_control_sources'] == {BUNDLE:[
        dict(logical_path=name, reference=cp.binding(case.receipts[name][0])) for name in sorted(case.receipts)]}
    for record in records:
        assert set(record) == {'logical_path', 'reference', 'body_base64'}
        name = record['logical_path']; original, body = case.receipts[name]
        assert record['reference'] == cp.binding(original)
        assert base64.b64decode(record['body_base64'], validate=True) == body
        decoded[name] = body
    assert decoded == {name:body for name, (_, body) in case.included.items()}
    for name, (original, body) in case.included.items():
        assert original.read_bytes() == body  # No deletion, repair or rewrite.
        if name in direct:
            assert census['physical_origins'][name] == cp.binding(original)
    assert not any(body in restored for body in case.excluded.values() for restored in decoded.values())
    by_name = {f['logical_path']:Path(f['path']) for f in files}
    assert archive.validate_capture(snapshot, by_name.__getitem__, complete=False) == dict(
        state='FAILURE_EVIDENCE', qualified_selected=False, forecast_rows=0)


@pytest.mark.parametrize('tamper', ['inner_body', 'missing_census'])
def test_rehashed_container_or_missing_census_cannot_bypass_validation(captured, tamper):
    case = captured.case
    snapshot = deepcopy(captured.snapshot)
    if tamper == 'inner_body':
        item = next(f for f in snapshot['files'] if f['logical_path'] == BUNDLE)
        bundle = cp.strict_json(Path(item['path']).read_bytes())
        record = bundle['records'][0]
        original = base64.b64decode(record['body_base64'], validate=True)
        changed = original[:-1]+bytes([original[-1] ^ 1])
        record['body_base64'] = base64.b64encode(changed).decode('ascii')
        # Rebind every outer file/hash/size control to the changed container.
        # Only the inner original binding exposes the corruption.
        body = store.canonical(bundle)
        path = case.runner.root/'tampered-container.json'
        case.runner.storage.write_bytes(path, body)
        replacement = cp.file_item(cp.binding(path), BUNDLE, 'control')
        snapshot['files'] = [replacement if f['logical_path'] == BUNDLE else f for f in snapshot['files']]
        snapshot['census']['physical_origins'][BUNDLE] = cp.binding(path)
        snapshot['census']['logical_bytes'] = sum(f['bytes'] for f in snapshot['files'])
        assert codec_roundtrip(snapshot)[BUNDLE] == body
    else:
        snapshot['census'].pop('bundled_control_sources')
        assert BUNDLE in codec_roundtrip(snapshot)
    by_name = {f['logical_path']:Path(f['path']) for f in snapshot['files']}
    with pytest.raises(store.StoreError):
        archive.validate_capture(snapshot, by_name.__getitem__, complete=False)
