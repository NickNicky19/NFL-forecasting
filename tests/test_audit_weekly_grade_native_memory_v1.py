"""Lossless fictional rows, exact legacy codec bytes and actual native limits.

No outcome/source/model body from production is opened. The full-census native
test uses the existing 18k-candidate/5k-selected fixture, the real bind/grade and
checkpoint helpers, and the existing fictional private transport. Unknown
outcomes stay unknown. This tests a finite capture, not 36 full-history captures.
"""
from copy import copy, deepcopy
import gzip
import io
import json
from pathlib import Path
import subprocess
import sys

import pytest

from nfl_lab import audit_weekly_grade_v1 as grade, state, private_draft_store as store
from test_audit_weekly_grade_v1 import packet

ROOT = Path(__file__).resolve().parents[1]


def test_paged_originals_keep_all_values_and_read_operations():
    rows = [dict(category="rec", n=i, value=-0.0, text="fictional é🏈", components=[dict(weight=.5)]) for i in range(131)]
    pages = grade._PagedRows.join([grade._PagedRows(rows[:3]), grade._PagedRows(rows[3:])])
    assert len(pages) == 131 and pages == rows and rows == pages
    assert pages == grade._PagedRows(rows)
    assert grade._PagedRows([dict(n=1)]) == grade._PagedRows([dict(n=1.0)])
    assert grade._PagedRows([dict(n=1)]) != grade._PagedRows([dict(n=2)])
    assert list(pages) == rows and pages[3] == rows[3] and pages[-1] == rows[-1]
    assert pages[::7] == rows[::7] and list(reversed(pages)) == rows[::-1]
    assert rows[2] in pages and pages.count(rows[2]) == 1 and pages.index(rows[2], -130) == 2
    assert pages + [] == rows and [] + pages == rows and pages * 2 == rows * 2
    assert copy(pages) is deepcopy(pages) is pages.copy() is pages
    assert state.canonical(dict(forecasts=pages)) == state.canonical(dict(forecasts=rows))
    assert b"".join(grade._canonical_chunks(dict(forecasts=pages))) == state.canonical(dict(forecasts=rows))
    assert grade._digest(dict(forecasts=pages)) == state.digest(dict(forecasts=rows))
    with pytest.raises(TypeError): pages.append(rows[0])
    with pytest.raises(TypeError): pages._count = 0
    with pytest.raises(TypeError): pages[0]["n"] = 99
    with pytest.raises(TypeError): pages[0]["components"][0]["weight"] = 1
    with pytest.raises(TypeError): pages[0]["components"].clear()
    editable = deepcopy(pages[0]); editable["components"][0]["weight"] = 1
    assert pages[0] == rows[0]


@pytest.mark.parametrize("size", [0, 1, 63, 64, 65, 131])
def test_incremental_snapshot_is_exact_original_canonical_and_gzip(packet, size):
    rows = [dict(n=i, category="rec", text="fictional €", nested=[None, True, -0.0, 1e-99]) for i in range(size)]
    ordinary = dict(forecasts=rows, selected=rows[:2], opportunities=[], unchanged=dict(z=1, a="λ"))
    paged = dict(ordinary, forecasts=grade._PagedRows(rows))
    ref = grade._write_snapshot(packet["storage"], packet["base"] / ("codec-" + str(size)), paged)
    actual = Path(ref["path"]).read_bytes()
    assert actual == gzip.compress(state.canonical(ordinary), mtime=0)
    restored = grade._unpack(actual, len(state.canonical(ordinary)))
    assert restored == ordinary and grade._digest(restored) == state.digest(ordinary)


@pytest.mark.parametrize("read_size", range(1, 10))
def test_json_stream_handles_split_utf8_numbers_and_bounded_reads(read_size):
    document = dict(forecasts=[dict(category="rec", text="é🏈" * 100, number=-1.23456789e123)], other=[{}, [], 123456789, -1.23e-22])
    raw = state.canonical(document)
    class TinyReads(io.BytesIO):
        def read(self, count=-1):
            assert 0 < count <= 32768
            return super().read(min(count, read_size))
    assert grade._JSONStream(TinyReads(raw), len(raw)).load() == document
    with pytest.raises(grade.GradeError, match="FINITE_FULL_GRADING_SNAPSHOT"):
        grade._JSONStream(TinyReads(raw), len(raw)-1).load()


@pytest.mark.parametrize("encoding", ["utf-8-sig", "utf-16", "utf-16-be", "utf-32", "utf-32-be"])
def test_restore_keeps_original_json_byte_encoding_support(encoding):
    document = dict(forecasts=[dict(category="rec", text="fictional é🏈")])
    raw = json.dumps(document, ensure_ascii=False).encode(encoding)
    assert grade._unpack(gzip.compress(raw, mtime=0), len(raw)) == document


@pytest.mark.parametrize("raw", [
    b'{"forecasts":[{"n":1,"n":2}]}', b'{"n":1,"n":2}', b'{"n":NaN}', b'{"n":Infinity}',
    b'{"n":-Infinity}', b'{"n":1}{}', b'{"n":1,}', b'{"n":[1,]}', b'{"n":1e}', b'{"n":01}',
    b'{"forecasts":[{"n":1}', b'{"n":"unterminated}', b'{"n":"\xff"}', b'',
])
def test_streaming_decode_keeps_strict_json_rejections(raw):
    with pytest.raises((ValueError, UnicodeError, store.StoreError)):
        grade._unpack(gzip.compress(raw, mtime=0), 1 << 20)


def test_gzip_crc_truncation_multiple_members_and_decoded_cap():
    body = gzip.compress(b'{"forecasts":[]}', mtime=0)
    with pytest.raises((EOFError, OSError)): grade._unpack(body[:-1], 1 << 20)
    corrupt = bytearray(body); corrupt[-8] ^= 1
    with pytest.raises(OSError): grade._unpack(bytes(corrupt), 1 << 20)
    combined = gzip.compress(b'{"forecasts":', mtime=0) + gzip.compress(b'[]}', mtime=0)
    assert grade._unpack(combined, 16) == {"forecasts": []}
    with pytest.raises(grade.GradeError, match="FINITE_FULL_GRADING_SNAPSHOT"):
        grade._unpack(body, 15-1)


def test_source_stream_limits_and_immutable_original_bytes(packet):
    storage = packet["storage"]; path = packet["base"] / "fictional-stream.gz"
    rows = [dict(category="rec", n=i) for i in range(65)]
    body = gzip.compress(b"".join(state.canonical(r)+b"\n" for r in rows), mtime=0)
    storage.write_bytes(path, body)
    ref = grade.cp.binding(path)
    assert grade._rows(storage, ref, maximum=65, budget=[0]) == rows
    with pytest.raises(grade.GradeError, match="FINITE_ORIGINAL_FORECAST_STREAM"):
        grade._rows(storage, ref, maximum=64, budget=[0])
    with pytest.raises(grade.GradeError, match="FINITE_ORIGINAL_FORECAST_STREAM"):
        grade._rows(storage, ref, maximum=65, budget=[grade.LIMITS["decoded_bytes"]])
    assert path.read_bytes() == body
    forged = dict(ref, bytes=ref["bytes"]+1)
    with pytest.raises((ValueError, store.StoreError)): grade._rows(storage, forged, maximum=65, budget=[0])


def test_snapshot_caps_reject_whole_history_without_publishing_or_deleting(packet, monkeypatch):
    root = packet["base"] / "over-cap"
    rows = grade._PagedRows(dict(category="rec", text="fictional" * 100) for _ in range(200))
    monkeypatch.setitem(grade.LIMITS, "decoded_bytes", 32768)
    with pytest.raises(grade.GradeError, match="FINITE_FULL_GRADING_SNAPSHOT"):
        grade._write_snapshot(packet["storage"], root, dict(forecasts=rows))
    assert not (root / "GRADING_SNAPSHOT.json.gz").exists() and len(rows) == 200
    monkeypatch.setitem(grade.LIMITS, "decoded_bytes", 64 << 20)
    monkeypatch.setitem(grade.LIMITS, "encoded_bytes", 32)
    with pytest.raises(grade.GradeError, match="FULL_GRADING_SNAPSHOT_ASSET_BOUND_NO_TRUNCATION"):
        grade._write_snapshot(packet["storage"], root, dict(forecasts=rows))
    assert not (root / "GRADING_SNAPSHOT.json.gz").exists() and len(rows) == 200


def test_record_batch_preserves_original_records_bytes_order_and_digests(packet, monkeypatch):
    from nfl_lab.operational_io import operational_io
    storage = packet["storage"]; base = packet["base"]
    rows = [dict(player_id="00-"+str(i).zfill(7), game_id="espn:112", target="rec", actual=i % 3,
        participation_state="played", source="fictional", source_sha256="a"*64, status_sha256="b"*64,
        source_timestamp=None, observed_at="2026-10-28T08:00:00+00:00") for i in range(24)]
    version = dict(schema_version="fictional-version", rows=rows, text="original é🏈")
    original = base/"original-records"; batched = base/"batched-records"
    scans = [0]; actual_scan = storage._scan
    def scan():
        scans[0] += 1
        return actual_scan()
    monkeypatch.setattr(storage, "_scan", scan)
    storage.register_root(original); scans[0] = 0
    with operational_io(storage):
        old = state.append_outcomes(original/"collector", rows+[rows[0]])
        sid = state.save(original, "weekly_versions", version)
        state.save(original, "weekly_completions", dict(snapshot_id=sid, persisted_completed_at="2026-10-28T08:00:00+00:00"))
    original_scans = scans[0]; scans[0] = 0
    expected = list(state.records(original/"collector", "outcomes"))
    with operational_io(storage), grade._record_batch(storage, batched):
        new = state.append_outcomes(batched/"collector", rows+[rows[0]])
        assert state.save(batched, "weekly_versions", version) == sid
        state.save(batched, "weekly_completions", dict(snapshot_id=sid, persisted_completed_at="2026-10-28T08:00:00+00:00"))
        assert list(state.records(batched/"collector", "outcomes")) == expected
        assert list(state.records(batched, "weekly_versions")) == [version]
    assert old == new == dict(appended=24)
    assert scans[0] < 20 < original_scans
    def census(root):
        return {str(p.relative_to(root)):p.read_bytes() for p in root.rglob("*") if p.is_file()}
    assert census(batched) == census(original)


def test_record_batch_existing_gzip_header_and_noop_cap_match_original(packet):
    from nfl_lab.operational_io import operational_io
    storage = packet["storage"]; root = packet["base"]/"existing-record"
    storage.register_root(root)
    document = dict(fictional=True, values=[0, -0.0, "é"]); key = state.digest(document)
    raw = gzip.compress(state.canonical(document), mtime=123)
    path = root/"weekly_versions"/(key+".json.gz"); storage.write_bytes(path, raw)
    previous = state.save, state.records, state.digest
    with operational_io(storage), grade._record_batch(storage, root):
        assert state.save(root, "weekly_versions", document, max_bytes=0) == key
    assert path.read_bytes() == raw
    assert (state.save, state.records, state.digest) == previous


def test_record_batch_failure_keeps_published_evidence_and_restores_seams(packet, monkeypatch):
    from nfl_lab.operational_io import operational_io
    storage = packet["storage"]; root = packet["base"]/"failed-cohort"
    previous = state.save, state.records, state.digest
    actual_alias = storage._alias; calls = [0]
    def fail_after_alias(blob, path, replace):
        actual_alias(blob, path, replace); calls[0] += 1
        if calls[0] == 2: raise RuntimeError("FICTIONAL_INTERRUPTED_COHORT")
    monkeypatch.setattr(storage, "_alias", fail_after_alias)
    with pytest.raises(RuntimeError, match="FICTIONAL_INTERRUPTED_COHORT"):
        with operational_io(storage), grade._record_batch(storage, root):
            for i in range(3): state.save(root/"collector", "outcomes", dict(fictional=True, n=i))
    assert (state.save, state.records, state.digest) == previous
    assert len(list((root/"collector/outcomes").glob("*.json.gz"))) == 2
    assert {v["n"] for v in state.records(root/"collector", "outcomes")} == {0, 1}
    storage.snapshot()


def test_record_batch_keeps_logical_and_global_quota_checks(packet, tmp_path):
    from nfl_lab.operational_io import operational_io
    from nfl_lab.operational_storage import OperationalStorage, StorageQuotaError
    storage = packet["storage"]; root = packet["base"]/"logical-cap"
    first = dict(fictional=True, n=1); second = dict(fictional=True, n=2)
    with pytest.raises(RuntimeError, match="durable evidence cap reached"):
        with operational_io(storage), grade._record_batch(storage, root):
            initial = sum(p.stat().st_size for p in (root/"collector").rglob("*") if p.is_file())
            maximum = initial + len(gzip.compress(state.canonical(first), mtime=0))
            state.save(root/"collector", "outcomes", first, max_bytes=maximum)
            state.save(root/"collector", "outcomes", second, max_bytes=maximum)
    assert list(state.records(root/"collector", "outcomes")) == [first]
    policy = json.loads((ROOT/"config/operational-source-policy-v2.json").read_bytes())
    policy["storage"]["limit_bytes"] = 32768
    small = OperationalStorage(tmp_path/"small-cache", policy, state=tmp_path/"small-state")
    payload = "".join(store.sha(str(i).encode()) for i in range(1000))
    target = tmp_path/"global-cap"
    with pytest.raises(StorageQuotaError):
        with operational_io(small), grade._record_batch(small, target):
            state.save(target/"collector", "outcomes", dict(fictional=payload))
    assert not list(target.rglob("*.json.gz")) and small.snapshot()["physical_bytes"] <= 32768


def test_record_batch_does_not_accept_matching_unowned_record(packet):
    import os
    from nfl_lab.operational_io import operational_io
    from nfl_lab.operational_storage import StorageIntegrityError
    storage = packet["storage"]; root = packet["base"]/"unowned-record"
    storage.register_root(root)
    document = dict(fictional=True); key = state.digest(document)
    path = root/"weekly_versions"/(key+".json.gz"); path.parent.mkdir()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
    try: os.write(fd, gzip.compress(state.canonical(document), mtime=0))
    finally: os.close(fd)
    with pytest.raises((StorageIntegrityError, FileNotFoundError)):
        with operational_io(storage), grade._record_batch(storage, root):
            state.save(root, "weekly_versions", document)


def test_compact_scans_preserve_full_census_hashes_roots_and_guards(packet, tmp_path):
    from nfl_lab.operational_storage import StorageIntegrityError
    storage = packet["storage"]
    for root in (packet["base"], packet["base"]/"actual-runtime-serializer", tmp_path): storage.register_root(root)
    before = storage.snapshot(); roots = list(storage._roots)
    with grade._compact_scans(storage):
        assert storage.snapshot() == before and storage._roots == roots
        with grade._compact_scans(storage): assert storage.snapshot() == before
    assert storage.snapshot() == before and storage._roots == roots
    link = packet["base"]/"fictional-symlink"
    link.symlink_to(packet["base"])
    with pytest.raises(StorageIntegrityError):
        with grade._compact_scans(storage): storage.snapshot()
    assert link.is_symlink()  # Failed evidence is retained, never cleaned up.


NATIVE_SCRIPT = r'''
import ast,json,socket,sys,time,resource
began=time.monotonic()
from pathlib import Path
from datetime import datetime,timedelta,timezone
from copy import deepcopy
from tools.private_draft_store_v2 import limits
limits()
from nfl_lab import audit_weekly_grade_v1 as g,audit_weekly_grade_checkpoint_v1 as k,audit_weekly_epoch_v1 as epoch,state,private_draft_store as s
from nfl_lab import audit_private_rotation_v1 as rotation
from nfl_lab.operational_storage import OperationalStorage
sys.path.insert(0,str(Path.cwd()/"tests"))
import pytest
from test_private_draft_store_v2 import Server,Response,RUN,SOURCE
from test_owner_private_bootstrap import qualification
socket.socket.connect=lambda *_:(_ for _ in ()).throw(AssertionError("REAL_NETWORK_FORBIDDEN"))
ROOT=Path.cwd();ROOT_SHA="d"*64;GRADE=state.utc("2026-10-28T08:00:00Z")
seed=json.loads(Path(sys.argv[1]).read_bytes())
def metric(stage):
    memory={}
    for line in Path('/proc/self/status').read_text().splitlines():
        key,_,value=line.partition(':')
        if key in {'VmPeak','VmSize','VmRSS','VmHWM'}:memory[key]=int(value.split()[0])*1024
    print(json.dumps(dict(fictional=True,stage=stage,CPU_seconds=time.process_time(),wall_seconds=time.monotonic()-began,**memory)),flush=True)
e=epoch.restore_epoch(seed['epoch'],seed['original_choice'].encode(),seed['original_completion'],seed['slate'],seed['catalog'],seed['policy'],history_binding=seed['history_binding'],now=GRADE)
r=epoch.bind_registration(e,seed['completion'],now=GRADE)
c=epoch.EpochChoice(seed['choice'],state.digest(seed['choice']));c.verify(r,GRADE)
storage=OperationalStorage(seed['cache'],ROOT/'config/operational-source-policy-v2.json',state=seed['state_root'])
metric('TYPED_METADATA_READY')
population=g.bind_population(seed['population'],r,c,authenticate=lambda _:True,at=GRADE)
capture=g.bind_capture(r,c,population,seed['restored'],storage=storage,capture_id=seed['capture_id'],role_catalog=seed['roles'],frozen_schedule=seed['schedule'],authenticate=lambda _:True,at=GRADE)
assert len(capture.document['forecasts'])==23000 and len(capture.document['selected'])==5000 and len(capture.document['opportunities'])==5000
metric('FULL_CAPTURE_BOUND')
# Explicitly unknown fictional outcomes, plus the fixture's complete finality.
# No source observation is invented to make an unknown statistic scoreable.
doc=dict(schema_version=g.VERSION+'-provider-observations',source_policy_sha256=g.cp.POLICY_SHA,captured_at=GRADE.isoformat(),observations=[],finality=[dict(season=2026,week=7,status_source_sha256='a'*64,observed_at=(GRADE-timedelta(hours=1)).isoformat(),games=[dict(game_id='espn:'+x['website_game_id'],kickoff_utc=x['kickoff_utc'],home=x['home'],away=x['away'],final=True) for x in seed['schedule']])])
batch=g.bind_observations([capture],doc,authenticate=lambda _:True,at=GRADE)
snapshot=g.grade(r,[capture],[batch],storage=storage,output=Path(seed['output'])/'grade',clock=lambda:GRADE)
assert sum(len(v['snapshot']['rows']) for v in snapshot.document['versions'])==5000
assert all(row['actual'] is None for v in snapshot.document['versions'] for row in v['snapshot']['rows'])
q=dict(storage=storage,snapshot=snapshot,r=r)
metric('FULL_CAPTURE_GRADED')
ns=globals()
for filename,names in (('test_audit_weekly_archive_v1.py',{'Service'}),('test_audit_weekly_grade_checkpoint_v1.py',{'Service','Parent','case'})):
    tree=ast.parse((ROOT/'tests'/filename).read_text())
    nodes=[n for n in tree.body if isinstance(n,(ast.ClassDef,ast.FunctionDef)) and n.name in names]
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),filename,'exec'),ns)
    if filename=='test_audit_weekly_archive_v1.py':ArchiveService=Service
ROLES=dict(produce='fictional_capture_writer',restore='fictional_capture_reader',consume='fictional_capture_exporter')
path=Path(seed['output'])/'native';path.mkdir(parents=True,mode=0o700)
patch=pytest.MonkeyPatch();actual=k.native_envelope
operation=ns['case'].__wrapped__(q,path,patch);patch.setattr(k,'native_envelope',actual)
handoff,_=operation['append']();metric('FULL_CHECKPOINT_APPENDED')
result,_=operation['restore'](handoff);result.verify();k.native_envelope()
assert len(result.durable.document['captures'][0]['forecasts'])==23000
assert len(result.durable.document['captures'][0]['selected'])==5000
assert result.durable.document['versions']==snapshot.document['versions']
assert result.durable.document['week_revisions']==snapshot.document['week_revisions']
assert result.report['public_release'] is False and 'catboost' not in sys.modules
assert resource.getrlimit(resource.RLIMIT_AS)==(512<<20,512<<20)
metric('FULL_CHECKPOINT_RESTORED_AND_REPORTED')
'''


def test_full_capture_grade_and_checkpoint_under_actual_native_limits(tmp_path):
    from test_audit_weekly_operations_grade_scale_v1 import full_scope_fixture
    q = full_scope_fixture(tmp_path / "fixture"); f = q["f"]
    originals = {name: store.sha(Path(ref["path"]).read_bytes()) for name, ref in q["restored"]["aliases"].items()}
    seed = dict(cache=str(q["storage"].cache), state_root=str(q["storage"].state_root),
        epoch=q["r"].epoch.document, completion=q["r"].completion, original_choice=f["raw"].decode(),
        original_completion=f["completion"], slate=f["slate"], catalog=f["catalog"], policy=f["policy"],
        history_binding=f["history_binding"], choice=q["c"].document, population=q["pop"],
        restored=q["restored"], roles=q["roles"], schedule=q["schedule"], capture_id=q["capture_id"], output=str(tmp_path/"worker"))
    path = tmp_path / "fictional-native-seed.json"; path.write_bytes(state.canonical(seed))
    profile = json.loads((ROOT/"config/audit-weekly-numerical-runtime-v1.json").read_bytes())["environment"]
    result = subprocess.run([sys.executable, "-B", "-c", NATIVE_SCRIPT, str(path)], cwd=ROOT,
        env=dict(PYTHONDONTWRITEBYTECODE="1", **profile), capture_output=True, text=True, timeout=185)
    print(result.stdout, end="", flush=True)
    assert result.returncode == 0, result.stderr
    metrics = [json.loads(line) for line in result.stdout.splitlines()]
    assert metrics[-1]["stage"] == "FULL_CHECKPOINT_RESTORED_AND_REPORTED"
    assert all(m["VmPeak"] <= 512 << 20 and m["CPU_seconds"] < 120 and m["wall_seconds"] < 180 for m in metrics)
    assert {name: store.sha(Path(ref["path"]).read_bytes()) for name, ref in q["restored"]["aliases"].items()} == originals
