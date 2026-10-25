"""Fictional scale regression: real CAS, codec and injected native transport only."""
from datetime import datetime, timedelta, timezone
import base64
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from nfl_lab import audit_weekly_archive_v1 as a
from nfl_lab.operational_storage import OperationalStorage, StorageIntegrityError, StorageQuotaError
import test_audit_weekly_archive_v1 as fixture
from test_private_draft_store_v2 import Server


def _build(base):
    p = fixture.capture.__wrapped__(base)
    noise = lambda n, size: hashlib.shake_256(str(n).encode()).hexdigest(size // 2)
    old = p.root
    p.root = p.storage.register_root(base / "scaled-runtime")
    def put(name, value): return a.write(p.storage, p.root / name, value)
    changed = {"CANDIDATES.json", "FINISHED.json", "EXPORT_INPUTS.json", "features.capture.json", "IDENTITY_BRIDGE.json",
               "selected.jsonl.gz", "selected.jsonl.completion.json"}
    for path in old.rglob("*"):
        if path.is_file() and path.name != ".operational-storage-owner":
            name = path.relative_to(old).as_posix()
            if name not in changed and not name.startswith(("candidates/", "model-status/")):
                p.storage.import_file(path, p.root / name, a.cp.binding(path)["sha256"])
    feature = a.cp.binding(p.root / "features.parquet")
    capture = a.cp.strict_json((old / "features.capture.json").read_bytes())
    capture["feature_binding"] = feature
    put("features.capture.json", capture)
    slots = []
    def rows(template, count):
        return gzip.compress(b"".join(a.store.canonical(dict(template, offered_id=hashlib.sha256(str(i).encode()).hexdigest()))
                                    + b"\n" for i in range(count)), mtime=0)
    for slot in p.slots:
        target, method = slot["target"], slot["method_id"]
        name = f"candidates/{target}/{method}.jsonl.gz"
        row = json.loads(gzip.decompress((old / name).read_bytes()))
        p.storage.write_bytes(p.root / name, rows(row, 1000))
        receipt = dict(slot["persistence"], rows=1000, binding=a.cp.binding(p.root / name))
        put(name.replace(".jsonl.gz", ".jsonl.completion.json"), receipt)
        current = dict(slot, expected_rows=1000, issued_rows=1000, persistence=receipt)
        put(f"model-status/{target}-{method}.json", current)
        slots.append(current)
    candidate = put("CANDIDATES.json", dict(schema_version=a.RUNTIME + "-candidates", slots=slots))
    row = json.loads(gzip.decompress((old / "selected.jsonl.gz").read_bytes()))
    p.storage.write_bytes(p.root / "selected.jsonl.gz", rows(row, 5000))
    selected = a.cp.binding(p.root / "selected.jsonl.gz")
    completion = a.cp.strict_json((old / "selected.jsonl.completion.json").read_bytes())
    completion.update(rows=5000, binding=selected)
    completion_ref = put("selected.jsonl.completion.json", completion)
    terminal = a.cp.strict_json((old / "FINISHED.json").read_bytes())
    terminal.update(prediction_rows=18000, selected=completion)
    terminal_ref = put("FINISHED.json", terminal)
    put("IDENTITY_BRIDGE.json", dict(schema_version=a.RUNTIME + "-identity", identities=[], name_matching=False,
                                     fictional_source_bindings=noise(-4, 1 << 20)))
    handoff = a.cp.strict_json((old / "EXPORT_INPUTS.json").read_bytes())
    handoff.update(terminal=terminal_ref, selected=selected, completion=completion_ref, candidates=candidate)
    for role, name in (("identity_bridge", "IDENTITY_BRIDGE.json"), ("recipe", "RUNTIME_RECIPE.json"),
                       ("choice", "WEEKLY_CHOICE.json"), ("artifact_catalog", "ARTIFACT_CATALOG.json"),
                       ("selected_version_catalog", "SELECTED_VERSION_CATALOG.json")):
        handoff[role] = a.cp.binding(p.root / name)
    put("EXPORT_INPUTS.json", handoff)
    for n in range(36):
        put(f"views/{n % 18}/projections/{a.store.sha(str(n).encode())}.json",
            dict(projection_features=["f_fixture"], parent_shared_capture=a.cp.binding(p.root / "features.capture.json"),
                 feature_binding=feature, fictional_projection=n))
    ts = lambda n: (p.stamp + timedelta(seconds=n)).isoformat()
    # Size distribution comes from control metadata, never from retained
    # forecast bodies: native ~45KB, board ~1.83MB, R0 controls ~6.19MB.
    native = p.body("r0/native.json.gz", gzip.compress(a.store.canonical({"fictional_native": noise(-1, 74 << 10)}), mtime=0))
    board = p.put("r0/output/data/week.json", {"fictional_board": noise(-2, 1_829_040)})
    # Exactly 383 archived paths, including all 172 END observations. BEGIN
    # receipts remain physically retained, but are not worker completion refs.
    prepared = a.cp.strict_json(a.cp.read_ref(p.context["prepared"]))
    base_count = len(a.CONTROL_FILES | a.CANDIDATE_NAMES | a.STATUS_NAMES) + 36 + len(p.context) + len(prepared["refs"]) + 1 + 3
    cache_count = 383 - base_count - 8 - 172
    assert 2 < cache_count <= 256
    caches = {"output/data/week.json": board, "data/cache/empty.json": p.body("r0/data/cache/empty.json", b"")}
    for n in range(cache_count - 2):
        caches[f"data/cache/{n:03}.json"] = p.put(f"r0/data/cache/{n:03}.json", {"fictional_cache": noise(n, 128 << 10)})
    state = p.put("r0/state.json", dict(files=caches))
    observations = []
    for n in range(172):
        p.put(f"r0/source-observations/{n:04}-BEGIN.json", dict(fictional=n, started_at=ts(-17)))
        observations.append(p.put(f"r0/source-observations/{n:04}-END.json",
                                 dict(fictional=n, status=200, sha256="a" * 64, completed_at=ts(-16))))
    prepared_r0 = p.put("r0/prepared.json", dict(current_values_used=False, slate={"game_cutoffs": {"fictional": ts(3600)}},
                                               fictional_metadata=noise(-3, 1_514_000)))
    controls = p.put("r0/controls.json", dict(rows=[dict(fictional_ordinal=n, forecast_value=None, operational_eligible=False,
                                                       fictional_binding=noise(n + 1000, 1130))
                                                   for n in range(5000)], actual_issued_at=ts(-13)))
    assert 6_000_000 <= controls["bytes"] <= 6_230_000
    worker = dict(state="ORIGINAL_R0_DEFAULT_PROCEDURE_CAPTURED", native=native, next_state=state, source_observations=observations,
                  actual_source_completed_at=ts(-16), actual_native_observed_at=ts(-15), actual_native_persist_completed_at=ts(-14))
    p.put("r0/WORKER_COMPLETE.json", worker)
    receipt = p.put("r0/completion.json", dict(schema_version="audit-reference-capture-v1-control-completion", forecast_binding=controls,
        source_receipt_sha256=a.store.sha(a.store.canonical(worker)), original_native_persist_completed_at=ts(-14), actual_issued_at=ts(-13),
        body_persist_completed_at=ts(-12), remote_durability_qualified=False, public_release=False))
    r0 = p.put("r0/CAPTURE_COMPLETE.json", dict(schema_version="audit-reference-capture-v1-capture", state="ORIGINAL_R0_CAPTURE_COMPLETE_PRIVATE",
        prepared=prepared_r0, native=native, original_board=board, next_state=state, control_forecast_rows=controls, control_completion=receipt))
    request = dict(root=str(p.root), context=p.context, r0=r0, cache=str(base / "cache"), state=str(base / "state"))
    path = base / "fictional-request.json"
    path.write_bytes(a.store.canonical(request))
    return path


def _service_state(service):
    return dict(tag=service.server.tag, assets=[dict(v, body=base64.b64encode(v["body"]).decode()) for v in service.server.assets],
                binding=service.binding, qrun=service.qrun, q=service.q, package=service.package, census=service.census,
                started=service.started.isoformat(), writer_completed=service.writer_completed.isoformat(),
                reader_completed=service.reader_completed.isoformat() if service.reader_completed else None)


def _service(raw):
    service = fixture.Service.__new__(fixture.Service)
    service.server = Server(); service.server.tag = raw["tag"]
    service.server.assets = [dict(v, body=base64.b64decode(v["body"])) for v in raw["assets"]]
    for k in ("binding", "qrun", "q", "package", "census"): setattr(service, k, raw[k])
    for k in ("started", "writer_completed", "reader_completed"):
        setattr(service, k, datetime.fromisoformat(raw[k]) if raw[k] else None)
    service.calls = []; service.bad_writer = service.bad_qualifier = False
    return service


def _child(request_path, phase, original=None):
    global a
    if original:
        spec = importlib.util.spec_from_file_location("nfl_lab._fictional_archive_before", original)
        a = importlib.util.module_from_spec(spec); spec.loader.exec_module(a)
        fixture.a = a
    from tools.private_draft_store_v2 import limits
    limits()
    assert resource.getrlimit(resource.RLIMIT_CPU) == (120, 120)
    assert resource.getrlimit(resource.RLIMIT_AS) == (512 << 20, 512 << 20)
    base = request_path.parent
    request = json.loads(request_path.read_bytes())
    scan = OperationalStorage._scan
    calls = 0
    def counted(instance):
        nonlocal calls
        calls += 1
        return scan(instance)
    OperationalStorage._scan = counted
    functions = {}
    def measured(owner, name):
        original = getattr(owner, name)
        def call(*args, **kwargs):
            cpu = time.process_time()
            try: return original(*args, **kwargs)
            finally: functions[name] = functions.get(name, 0.) + time.process_time() - cpu
        setattr(owner, name, call)
    measured(a, "validate_capture"); measured(a.codec, "encode"); measured(a.codec, "verify_bundle")
    started = time.monotonic(); cpu = time.process_time()
    storage = OperationalStorage(request["cache"], ROOT / "config/operational-source-policy-v2.json", state=request["state"])
    stages = {}
    def mark(label):
        nonlocal cpu
        current = time.process_time(); stages[label] = round(current - cpu, 4); cpu = current
        print(json.dumps(dict(fictional=True, phase=phase, stage=label, CPU_seconds=stages[label], scan_calls=calls)), flush=True)
    if phase == "produce":
        snapshot = a.collect(request["root"], request["context"], storage=storage, output=base / "collection", r0=request["r0"])
        assert len(snapshot["files"]) == 383
        assert 22 << 20 <= sum(f["bytes"] for f in snapshot["files"]) <= 26 << 20
        mark("collect_validate")
        service = fixture.Service(base)
        handoff = a.produce(snapshot, service.factory(base / "writer-journal", "produce"), service.package, storage=storage,
                            output=base / "producer", root_go_sha256="d" * 64, jobs=fixture.ROLES, pending_census=service.census)
        service.writer_completed = datetime.now(timezone.utc)
        result = dict(handoff=handoff, snapshot=snapshot)
        mark("validate_encode_native_append")
    else:
        raw = json.loads((base / "fictional-transport.json").read_bytes())
        service = _service(raw["service"]); result = raw["result"]
        service.active = phase
        factory = service.factory(base / (phase + "-journal"), phase)
        kwargs = dict(storage=storage, output=base / phase, root_go_sha256="d" * 64, pending_census=service.census)
        if phase == "restore":
            restored = a.restore(result["handoff"], factory, service.package, **kwargs)
            service.reader_completed = datetime.now(timezone.utc)
            result["reader_handoff"] = json.loads((base / phase / "READER_HANDOFF.json").read_bytes())
        else: restored = a.consume(result["reader_handoff"], factory, service.package, **kwargs)
        assert restored["validation"]["candidate_rows"] == 18000
        assert restored["validation"]["selected_rows"] == 5000
        assert len(restored["aliases"]) == 383
        for f in result["snapshot"]["files"]:
            assert a.cp.binding(restored["aliases"][f["logical_path"]]["path"]) == restored["aliases"][f["logical_path"]]
            assert Path(f["path"]).read_bytes() == Path(restored["aliases"][f["logical_path"]]["path"]).read_bytes()
        assert restored["scope_qualified_for_publication"] is False
        mark("native_restore_extract_validate_all383")
    (base / "fictional-transport.json").write_bytes(a.store.canonical(dict(service=_service_state(service), result=result)))
    print(json.dumps(dict(fictional=True, phase=phase, stages=stages, wall_seconds=round(time.monotonic()-started, 4),
                         CPU_seconds=round(time.process_time(), 4), scan_calls=calls, max_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                         function_CPU_seconds={k: round(v, 4) for k, v in functions.items()},
                         logical_bytes=sum(f["bytes"] for f in result["snapshot"]["files"]),
                         files=383, candidate_rows=18000, selected_rows=5000, native_durability_claim=False, fits=0)), flush=True)


def _run(path, phase, original=None):
    numerical = json.loads((ROOT / "config/weekly-owner-private-bootstrap-v1.json").read_bytes())["numerical_environment"]
    command = [sys.executable, "-B", str(Path(__file__).resolve()), str(path), phase]
    if original: command.append(str(original))
    return subprocess.run(command, cwd=ROOT, env={**os.environ, **numerical}, capture_output=True, text=True, timeout=185)


def test_full383_capture_with_maximum_rows_fits_each_unchanged_native_envelope(tmp_path):
    request = _build(tmp_path)
    for phase in ("produce", "restore", "consume"):
        result = _run(request, phase)
        assert result.returncode == 0, (phase, result.returncode, result.stdout, result.stderr)
        summary = json.loads(result.stdout.splitlines()[-1])
        assert summary["CPU_seconds"] < 120 and summary["wall_seconds"] < 180
        assert summary["files"] == 383 and summary["native_durability_claim"] is False
        assert summary["scan_calls"] < 150
        print(result.stdout, end="")


@pytest.mark.parametrize("failure", ["unowned", "wrong_hash"])
def test_batch_collection_still_rejects_each_unowned_or_changed_original(tmp_path, failure):
    p = fixture.capture.__wrapped__(tmp_path)
    context = dict(p.context)
    ref = dict(context["original_slate"])
    if failure == "unowned":
        path = tmp_path / "unowned-copy.json"
        path.write_bytes(Path(ref["path"]).read_bytes()); path.chmod(0o444)
        ref["path"] = str(path)
    else: ref["sha256"] = "a" * 64
    context["original_slate"] = ref
    with pytest.raises(StorageIntegrityError):
        a.collect(p.root, context, storage=p.storage, output=tmp_path / "rejected-collection")
    assert not (tmp_path / "rejected-collection/COLLECTED.json").exists()


def test_group_batch_reserves_full_original_quota_before_first_alias(tmp_path):
    policy = json.loads((ROOT / "config/operational-source-policy-v2.json").read_bytes())
    policy["storage"]["limit_bytes"] = policy["namespaces"]["private_retention_bytes"] = 16 << 10
    storage = OperationalStorage(tmp_path / "small-cache", policy, state=tmp_path / "small-state")
    output = storage.register_root(tmp_path / "output")
    before = storage.snapshot()
    with pytest.raises(StorageQuotaError):
        a._publish_owned_files(storage, [("one.json", b"a" * (8 << 10)), ("two.json", b"b" * (8 << 10))], output)
    assert not (output / "one.json").exists() and not (output / "two.json").exists()
    assert storage.snapshot() == before


if __name__ == "__main__":
    _child(Path(sys.argv[1]), sys.argv[2], sys.argv[3] if len(sys.argv) == 4 else None)
