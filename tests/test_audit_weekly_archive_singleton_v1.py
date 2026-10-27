"""Fictional oversized originals use the unchanged bounded bundle wire format."""
from copy import deepcopy
import base64
import gzip
import json
import os
from pathlib import Path
import random
import resource
import subprocess
import sys
import time

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nfl_lab import audit_weekly_archive_v1 as a
from nfl_lab.operational_storage import OperationalStorage

SIZE = 6_318_636
NAME = "fictional/large-control.json"


def fictional_json():
    prefix, suffix = b'{"fictional_control":"', b'"}\n'
    return prefix + b"F" * (SIZE-len(prefix)-len(suffix)) + suffix


def item(root, name, size, body=b"fictional metadata only"):
    return a.cp.file_item(dict(path=str(root/name), bytes=size, sha256=a.store.sha(body)), name, "control")


def test_singleton_plan_preserves_every_original_and_ordinary_bounds(tmp_path):
    large = item(tmp_path, NAME, SIZE)
    small = item(tmp_path, "small.json", 128)
    empty = item(tmp_path, "empty.bin", 0, b"")
    files = [small, empty, large]; original = deepcopy(files)
    with pytest.raises(a.store.StoreError, match="SINGLE_FILE_BUNDLE_CAP"):
        a.codec.groups([large])  # Generic owner/checkpoint planning stays unchanged.
    groups = a.capture_groups(files)
    assert groups == [[large], [small]] == a.capture_groups(list(reversed(files)))
    assert a.codec.GROUP_JSON < a.codec.inflated_size(groups[0]) <= a.codec.INFLATED
    assert all(a.codec.inflated_size(g) <= a.codec.GROUP_JSON for g in groups[1:])
    assert files == original
    assert (a.codec.GROUP_JSON, a.codec.INFLATED, a.store.ASSET_CAP) == (8_323_072, 12_582_912, 8_388_608)
    assert (a.MAX_GROUPS, a.codec.MAX_FILES, a.MAX_FILES, a.store.MAX_ASSETS) == (8, 64, 512, 128)
    assert (a.store.TOTAL_CAP, a.LIMITS["global_bytes"]) == (32 << 20, 512 << 20)


@pytest.mark.parametrize("large_count,small_count,accepted", [(8, 0, True), (8, 1, False), (9, 0, False)])
def test_singletons_consume_existing_eight_group_budget(tmp_path, large_count, small_count, accepted):
    files = [item(tmp_path, f"large/{n}.json", SIZE) for n in range(large_count)]
    files += [item(tmp_path, "small.json", 128) for _ in range(small_count)]
    if accepted:
        assert len(a.capture_groups(files)) == 8
        assert all(len(g) == 1 for g in a.capture_groups(files))
    else:
        with pytest.raises(a.store.StoreError, match="EIGHT_ARCHIVE_GROUPS_NO_OMISSIONS"):
            a.capture_groups(files)


def test_singleton_still_obeys_actual_inflated_limit(tmp_path, monkeypatch):
    large = item(tmp_path, NAME, SIZE)
    monkeypatch.setattr(a.codec, "INFLATED", a.codec.inflated_size([large])-1)
    with pytest.raises(a.store.StoreError, match="SINGLE_FILE_BUNDLE_CAP"):
        a.capture_groups([large])


def native_phase(base, phase):
    from tools.private_draft_store_v2 import limits
    limits()
    started, cpu = time.monotonic(), time.process_time()
    assert resource.getrlimit(resource.RLIMIT_AS) == (512 << 20, 512 << 20)
    assert resource.getrlimit(resource.RLIMIT_CPU) == (120, 120)
    storage = OperationalStorage(base/(phase+"-cache"), ROOT/"config/operational-source-policy-v2.json", state=base/(phase+"-state"))
    output = storage.register_root(base/phase)
    if phase == "encode":
        source = storage.register_root(base/"source")
        original = fictional_json()
        assert len(original) == SIZE
        storage.write_bytes(source/NAME, original)
        files = [a.cp.file_item(a.cp.binding(source/NAME), NAME, "control")]
        before = deepcopy(files); records = []
        for n, members in enumerate(a.capture_groups(files)):
            body, inflated = a.codec.encode(members)
            record = dict(index=n, bytes=len(body), sha256=a.store.sha(body), inflated_bytes=inflated, files=members)
            # Independent gzip/JSON/base64 verification of the existing wire.
            plain = gzip.decompress(body); document = json.loads(plain)
            assert len(plain) == inflated and document["schema_version"] == a.codec.VERSION
            assert base64.b64decode(document["files"][0]["content_b64"], validate=True) == original
            assert a.codec.verify_bundle(body, record) == [(NAME, original)]
            assert a.codec.GROUP_JSON < inflated <= a.codec.INFLATED and len(body) <= a.store.ASSET_CAP
            storage.write_bytes(output/f"{n}.gz", body); records.append(record)
        assert files == before and len(records) == 1
        storage.write_bytes(output/"MANIFEST.json", a.store.canonical(records))
    else:
        assert phase == "restore"
        records = json.loads(a.store.read_local(base/"encode/MANIFEST.json", 1 << 20))
        for record in records:
            body = a.store.read_local(base/"encode"/f"{record['index']}.gz", a.store.ASSET_CAP)
            a._extract_owned_group(body, record, storage, output)
        restored = output/NAME
        assert restored.read_bytes() == fictional_json() == (base/"source"/NAME).read_bytes()
        assert not os.path.samestat(restored.stat(), (base/"source"/NAME).stat())
        storage.validate_reference(restored, records[0]["files"][0]["sha256"])
        with pytest.raises(a.store.StoreError, match="EXTRACTION_EXISTS"):
            a._extract_owned_group(body, records[0], storage, output)
    usage = storage.snapshot()["physical_bytes"]
    assert usage <= 512 << 20
    print(json.dumps(dict(phase=phase, pid=os.getpid(), original_bytes=SIZE,
        original_sha256=a.store.sha(fictional_json()), inflated_bytes=records[0]["inflated_bytes"],
        compressed_bytes=records[0]["bytes"], global_physical_bytes=usage,
        wall_seconds=time.monotonic()-started, CPU_seconds=time.process_time()-cpu,
        RSS_peak_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        independent_CAS=True, model_decodes=0, fits=0)), flush=True)


def test_exact_length_fictional_json_recovers_in_distinct_fresh_native_process(tmp_path):
    results = []
    for phase in ("encode", "restore"):
        run = subprocess.run([sys.executable, "-B", str(Path(__file__).resolve()), phase, str(tmp_path)],
            cwd=ROOT, env=os.environ.copy(), capture_output=True, text=True, timeout=185)
        assert run.returncode == 0, run.stderr
        print(run.stdout, end="", flush=True)
        results.append(json.loads(run.stdout.splitlines()[-1]))
    assert results[0]["pid"] != results[1]["pid"]
    assert results[0]["original_sha256"] == results[1]["original_sha256"]
    assert all(r["wall_seconds"] < 180 and r["CPU_seconds"] < 120 and r["RSS_peak_KiB"] < 512 << 10 for r in results)


def test_incompressible_maximum_original_fails_before_any_POST(tmp_path):
    from test_audit_weekly_archive_v1 import capture, Service, ROLES
    p = capture.__wrapped__(tmp_path); service = Service(tmp_path)
    source = p.storage.register_root(tmp_path/"incompressible-source")
    original = random.Random(20261027).randbytes(a.store.ASSET_CAP)
    p.storage.write_bytes(source/NAME, original)
    file = a.cp.file_item(a.cp.binding(source/NAME), NAME, "control")
    assert a.capture_groups([file]) == [[file]]
    snapshot = dict(files=[file], census=dict(archive_state="FAILURE_EVIDENCE", raw_HTTP_corpus_archived=False,
        model_weights_reuploaded=False, source_started_at=service.started.isoformat(),
        source_completed_at=service.started.isoformat(), actual_collected_at=service.started.isoformat()))
    with pytest.raises(a.store.StoreError, match="COMPRESSED_BUNDLE_CAP"):
        a.produce(snapshot, service.factory(tmp_path/"incompressible-journal", "produce"), service.package,
            storage=p.storage, output=tmp_path/"incompressible-produce", root_go_sha256="d"*64,
            jobs=ROLES, pending_census=service.census)
    assert not service.posts()
    assert (source/NAME).read_bytes() == original
    assert (tmp_path/"incompressible-produce/CONSUMED.json").exists()
    assert not (tmp_path/"incompressible-produce/APPENDED.json").exists()
    assert not list((tmp_path/"incompressible-produce").glob("APPEND_INTENT_*"))


def test_complete_archive_actual_transport_restores_large_control(tmp_path):
    from test_audit_weekly_archive_v1 import capture, Service, produce
    p = capture.__wrapped__(tmp_path); service = Service(tmp_path)
    p.context["original_policy"] = p.body("context/large-fictional-policy.json", fictional_json())
    handoff, _, snapshot = produce(p, service)
    assert handoff["archive_state"] == "COMPLETE_CAPTURE"
    service.active = "restore"
    restored = a.restore(handoff, service.factory(tmp_path/"reader-journal", "restore"), service.package,
        storage=p.storage, output=tmp_path/"reader", root_go_sha256="d"*64, pending_census=service.census)
    assert restored["state"] == "PRIVATE_CAPTURE_RESTORED"
    for original in snapshot["files"]:
        assert Path(restored["aliases"][original["logical_path"]]["path"]).read_bytes() == Path(original["path"]).read_bytes()


def test_actual_failure_opaque_collector_routes_large_original_through_shared_packer(tmp_path, monkeypatch):
    import test_audit_weekly_failed_scope_v1 as scope
    case = scope.fixture(tmp_path, partial=True)
    original = case.runner.root/"reference/FICTIONAL_CONTROL.json"
    case.runner.storage.write_bytes(original, fictional_json())
    method, _ = scope.parent_preserver()
    def before_post(snapshot, *args, **kwargs):
        groups = a.capture_groups(snapshot["files"])
        large = next(f for f in snapshot["files"] if f["bytes"] == SIZE)
        assert [large] in groups
        body, inflated = a.codec.encode([large])
        record = dict(bytes=len(body), sha256=a.store.sha(body), inflated_bytes=inflated, files=[large])
        assert a.codec.verify_bundle(body, record) == [(large["logical_path"], fictional_json())]
        assert snapshot["census"]["archive_state"] == "FAILURE_EVIDENCE"
        raise scope.BeforePost
    monkeypatch.setattr(a, "produce", before_post)
    with pytest.raises(scope.BeforePost):
        method(case.runner)
    assert original.read_bytes() == fictional_json()


if __name__ == "__main__":
    native_phase(Path(sys.argv[2]), sys.argv[1])
