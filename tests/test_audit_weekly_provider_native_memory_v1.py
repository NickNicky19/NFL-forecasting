"""Fictional owned reads with unchanged caps, hashes and live authority gates.

The small native probes reserve explicitly fictional scratch working memory,
then exercise real owned-read/provider paths under actual 512 MiB/120 CPU/180
wall guards. They expose cap-sized allocations independently of source size.
The ORIGINAL operations-grade scale test remains the full-census release test;
these probes grant no genuine transport, history or public-release authority.
"""
import json
from pathlib import Path
import subprocess
import sys

import pytest

from nfl_lab import audit_weekly_archive_v1 as archive, audit_weekly_provider_v1 as provider
from nfl_lab import private_draft_store as store
from test_audit_weekly_provider_v1 import setup, no_network, Transport, AT

ROOT = Path(__file__).resolve().parents[1]


def owned(storage, root, body=b'{"fictional":true}'):
    storage.register_root(root)
    path = root / "original.json"
    storage.write_bytes(path, body)
    return dict(path=str(path), bytes=len(body), sha256=store.sha(body))


def test_owned_reader_uses_declared_actual_length_after_CAS_validation(setup, tmp_path, monkeypatch):
    storage, _ = setup
    ref = owned(storage, tmp_path / "owned")
    calls = []; actual = archive.cp.read_ref
    def read(ref, cap):
        calls.append(cap)
        return actual(ref, cap)
    monkeypatch.setattr(archive.cp, "read_ref", read)
    assert archive.read_owned(storage, ref, 32 << 20) == {"fictional": True}
    assert calls == [ref["bytes"]]
    assert Path(ref["path"]).read_bytes() == b'{"fictional":true}'


@pytest.mark.parametrize("size", [None, True, 0, -1, (32 << 20)+1])
def test_invalid_declared_size_never_reads_body(setup, tmp_path, monkeypatch, size):
    storage, _ = setup
    ref = owned(storage, tmp_path / "owned"); ref["bytes"] = size
    monkeypatch.setattr(archive.cp, "read_ref", lambda *_: pytest.fail("PRIVATE_READ_BEFORE_SIZE_GATE"))
    with pytest.raises(store.StoreError): archive.read_owned(storage, ref, 32 << 20)


def test_owned_reader_preserves_hash_size_and_readback_checks(setup, tmp_path, monkeypatch):
    storage, _ = setup
    ref = owned(storage, tmp_path / "owned")
    with pytest.raises((store.StoreError, ValueError)):
        archive.read_owned(storage, dict(ref, bytes=ref["bytes"]+1), 32 << 20)
    with pytest.raises((store.StoreError, ValueError)):
        archive.read_owned(storage, dict(ref, sha256="0"*64), 32 << 20)
    actual = archive.cp.store.read_local
    def changed_readback(path, cap):
        body = actual(path, cap)
        return body + b" " if Path(path) == Path(ref["path"]) else body
    monkeypatch.setattr(archive.cp.store, "read_local", changed_readback)
    with pytest.raises(store.StoreError, match="CHECKPOINT_REFERENCE_HASH"):
        archive.read_owned(storage, ref, 32 << 20)


def test_provider_reads_actual_source_length_without_changing_observations(setup, monkeypatch):
    _, make = setup
    collector, parent, transport, request = make()
    calls = []; actual = store.read_local
    def read(path, cap):
        path = Path(path)
        if path.name.startswith(("schedule-", "statistics-")) and path.name.endswith(".json") and not path.name.endswith(".receipt.json"):
            calls.append((cap, path.stat().st_size))
        return actual(path, cap)
    monkeypatch.setattr(store, "read_local", read)
    result = collector(request)
    assert calls and all(cap == size for cap, size in calls)
    assert result["observations"][0]["actual"] == 0
    assert result["observations"][0]["participation_state"] == "played"
    assert len(transport.calls) == 2 and collector.capture.verify() is collector.capture
    assert [r["kind"] for r in parent.calls] == ["AUTHORIZE_REGISTERED_REQUEST", "AUTHENTICATE_SOURCE_BODY", "AUTHENTICATE_SOURCE_BODY", "COMPLETE_PROVIDER_OBSERVATIONS"]


@pytest.mark.parametrize("size", [0, -1, True, (50 << 20)+1, "short", "long"])
def test_provider_rejects_false_receipt_lengths_and_retains_source_pair(setup, size):
    _, make = setup
    transport = Transport()
    def change(receipt):
        receipt["bytes"] = receipt["bytes"] + (-1 if size == "short" else 1) if size in {"short", "long"} else size
    transport.receipt_change = change
    collector, _, _, request = make(transport=transport)
    with pytest.raises((provider.ProviderError, store.StoreError)): collector(request)
    assert collector.capture is None and len(transport.calls) == 1
    assert len(list((collector.output / "sources").glob("*"))) == 2
    assert not (collector.output / "COMPLETION.json").exists()


NATIVE_SCRIPT = r'''
import json,resource,socket,sys,time
from pathlib import Path
began=time.monotonic()
from tools.private_draft_store_v2 import limits
limits()
from nfl_lab import audit_weekly_archive_v1 as archive,audit_weekly_provider_v1 as provider,audit_weekly_grade_checkpoint_v1 as checkpoint
from nfl_lab import private_draft_store as store
from nfl_lab.operational_storage import OperationalStorage
sys.path.insert(0,str(Path.cwd()/'tests'))
from test_audit_weekly_provider_v1 import Transport,Parent,request,AT
socket.socket.connect=lambda *_:(_ for _ in ()).throw(AssertionError('REAL_PROVIDER_NETWORK_FORBIDDEN'))
root=Path(sys.argv[1]);phase=sys.argv[2]
storage=OperationalStorage(root/'cache',provider.POLICY,state=root/'state')
storage.register_root(root/'original')
body=b'{"fictional":true}'
path=root/'original'/'original.json';storage.write_bytes(path,body)
ref=dict(path=str(path),bytes=len(body),sha256=store.sha(body))
def metric(stage):
    m={}
    for line in Path('/proc/self/status').read_text().splitlines():
        key,_,value=line.partition(':')
        if key in {'VmPeak','VmSize','VmHWM','VmRSS'}:m[key]=int(value.split()[0])*1024
    print(json.dumps(dict(fictional=True,phase=phase,stage=stage,CPU_seconds=time.process_time(),wall_seconds=time.monotonic()-began,**m)),flush=True)
    return m
before=metric('BEFORE_FICTIONAL_SCRATCH')
# This is explicit scratch pressure, not a claim to model 36-capture capacity.
scratch=bytearray(max(0,(512<<20)-before['VmSize']-(12<<20)))
metric('NATIVE_READ_READY')
if phase=='archive':
    assert archive.read_owned(storage,ref,32<<20)=={'fictional':True}
else:
    req=request();transport=Transport();parent=Parent(storage,transport,req)
    collector=provider.Collector(storage=storage,output=root/'provider',authenticate=parent,fetch=transport,clock=lambda:AT)
    doc=collector(req)
    assert doc['observations'][0]['actual']==0 and len(transport.calls)==2
    assert collector.capture.verify().document['public_release'] is False
assert path.read_bytes()==body
checkpoint.native_envelope()
assert resource.getrlimit(resource.RLIMIT_AS)==(512<<20,512<<20)
metric('PASS_NATIVE_BOUNDED_READ')
'''


@pytest.mark.parametrize("phase", ["archive", "provider"])
def test_small_owned_and_provider_bodies_under_actual_native_scratch_pressure(tmp_path, phase):
    profile = json.loads((ROOT / "config/audit-weekly-numerical-runtime-v1.json").read_bytes())["environment"]
    result = subprocess.run([sys.executable, "-B", "-c", NATIVE_SCRIPT, str(tmp_path), phase], cwd=ROOT,
        env=dict(PYTHONDONTWRITEBYTECODE="1", **profile), capture_output=True, text=True, timeout=185)
    print(result.stdout, end="", flush=True)
    assert result.returncode == 0, result.stderr
    values = [json.loads(line) for line in result.stdout.splitlines()]
    assert values[-1]["stage"] == "PASS_NATIVE_BOUNDED_READ"
    assert all(v["VmPeak"] <= 512 << 20 and v["CPU_seconds"] < 120 and v["wall_seconds"] < 180 for v in values)
