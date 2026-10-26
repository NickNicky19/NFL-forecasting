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


def test_v2_fragments_are_literal_original_canonical_bytes_across_utf8(packet):
    document = dict(a="x"*100, b="é🏈", c="x"*50, forecasts=[dict(value=-0.0, actual=None)], retained=[0,"DNP","played_corrected"])
    raw = state.canonical(document)
    split = raw.index("é".encode())+1
    if split < (len(raw)+1)//2:
        document["a"] += "x"*len(raw); raw = state.canonical(document); split = raw.index("é".encode())+1
    output = packet["base"]/"literal-parts"; packet["storage"].register_root(output)
    ref = grade._write_snapshot_v2(packet["storage"], output, document, part_bytes=split)
    manifest = grade._unpack(Path(ref["path"]).read_bytes(), 64 << 20)
    assert len(manifest["parts"]) == 2 and manifest["logical_sha256"] == store.sha(raw)
    assert b"".join(gzip.decompress((output/p["name"]).read_bytes()) for p in manifest["parts"]) == raw
    actual = grade._load_snapshot(packet["storage"], ref)
    assert actual == json.loads(raw) and grade._digest(actual) == store.sha(raw)
    assert grade.LIMITS["decoded_bytes"] == 64 << 20 and grade.LIMITS["encoded_bytes"] == 8 << 20


@pytest.mark.parametrize("kind", ["missing", "reordered", "duplicate", "decoded_hash", "decoded_size", "logical_hash", "oversized_part"])
def test_v2_local_manifest_rejects_incomplete_reordered_or_false_parts(packet, kind):
    document = dict(forecasts=[dict(n=i, text="fictional") for i in range(10)])
    raw = state.canonical(document); output = packet["base"]/("bad-parts-"+kind); packet["storage"].register_root(output)
    ref = grade._write_snapshot_v2(packet["storage"], output, document, part_bytes=(len(raw)+1)//2)
    manifest = grade._unpack(Path(ref["path"]).read_bytes(), 64 << 20)
    if kind == "missing": manifest["parts"].pop()
    elif kind == "reordered": manifest["parts"].reverse()
    elif kind == "duplicate": manifest["parts"][1] = deepcopy(manifest["parts"][0])
    elif kind == "decoded_hash": manifest["parts"][0]["decoded_sha256"] = "0"*64
    elif kind == "decoded_size": manifest["parts"][0]["decoded_bytes"] += 1; manifest["logical_bytes"] += 1
    elif kind == "logical_hash": manifest["logical_sha256"] = "0"*64
    else: manifest["parts"][0]["decoded_bytes"] = (64 << 20)+1
    body = gzip.compress(state.canonical(manifest), mtime=0); path = output/"FORGED.json.gz"
    packet["storage"].write_bytes(path, body)
    forged = dict(path=str(path), bytes=len(body), sha256=store.sha(body))
    with pytest.raises((grade.GradeError, store.StoreError)): grade._load_snapshot(packet["storage"], forged)


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


def two_full_scope_fixture(root):
    """Two disjoint original games, assigned to distinct captures before values."""
    import ast
    import test_audit_weekly_grade_v1 as original
    from nfl_lab.operational_storage import OperationalStorage
    storage = OperationalStorage(root/"cache", ROOT/"config/operational-source-policy-v2.json", state=root/"state")
    packet = next(n for n in ast.parse(Path(original.__file__).read_text()).body if isinstance(n,ast.FunctionDef) and n.name=="packet")
    results = []
    for number, game in enumerate(("sunday", "monday")):
        node = deepcopy(packet); node.decorator_list = []
        class Fixture(ast.NodeTransformer):
            def visit_Constant(self, node):
                if number and node.value == "fictional-sunday": node.value = "fictional-monday"
                if number and node.value == "112": node.value = "113"
                if node.value == "fictional-prevalue-root-capture-id": node.value = "fictional-prevalue-"+game
                return node
            def visit_Subscript(self, node):
                self.generic_visit(node)
                if number and isinstance(node.value,ast.Subscript) and isinstance(node.value.slice,ast.Constant) and node.value.slice.value=="schedule" and isinstance(node.slice,ast.Constant) and node.slice.value==1:
                    node.slice = ast.Constant(2)
                return node
            def visit_Delete(self, node):
                self.generic_visit(node)
                if len(node.targets)==1 and isinstance(node.targets[0],ast.Subscript) and isinstance(node.targets[0].slice,ast.Constant) and node.targets[0].slice.value=="scientific_qualification":
                    extra=deepcopy(node.targets[0]);extra.slice=ast.Constant("public_export_authorized");node.targets.append(extra)
                return node
            def visit_Call(self, node):
                self.generic_visit(node)
                if isinstance(node.func,ast.Name) and node.func.id=="range" and len(node.args)==1 and isinstance(node.args[0],ast.Constant) and node.args[0].value==3:
                    node.args[0]=ast.Constant(1000)
                if isinstance(node.func,ast.Name) and node.func.id=="dict":
                    for key in node.keywords:
                        if key.arg=="position" and isinstance(key.value,ast.Constant) and key.value.value=="RB": key.value=ast.Constant("QB")
                        if key.arg in {"rows","expected_rows","issued_rows"} and isinstance(key.value,ast.Constant) and key.value.value==3: key.value=ast.Constant(1000)
                for key in node.keywords:
                    if key.arg=="assignments":
                        key.value=ast.Dict(keys=[ast.Constant("fictional-sunday"),ast.Constant("fictional-monday")],
                            values=[ast.Call(func=ast.Name(id="h",ctx=ast.Load()),args=[ast.Constant("fictional-prevalue-"+s)],keywords=[]) for s in ("sunday","monday")])
                return node
        scope=dict(vars(original));scope["OperationalStorage"]=lambda *_a,**_k:storage
        exec(compile(ast.fix_missing_locations(ast.Module(body=[Fixture().visit(node)],type_ignores=[])),"two-full-capture-fixture","exec"),scope)
        q=scope["packet"](root/game); results.append(q)
        assert len(q["capture"].document["forecasts"])==23000 and len(q["capture"].document["selected"])==5000
        assert len(q["capture"].document["opportunities"])==5000
    left,right=results
    assert left["r"].epoch.sha256==right["r"].epoch.sha256 and left["c"].document==right["c"].document
    assert left["pop"]["assignments"]==right["pop"]["assignments"]
    assert {o["offered_id"] for o in left["capture"].document["opportunities"]}.isdisjoint(o["offered_id"] for o in right["capture"].document["opportunities"])
    return results


def _save_fictional_service(service, path):
    path.mkdir(parents=True, exist_ok=True)
    from datetime import datetime
    attributes = {k:dict(datetime=v.isoformat()) if isinstance(v,datetime) else v
        for k,v in vars(service).items() if k not in {"server","calls"}}
    server = {k:v for k,v in vars(service.server).items() if k not in {"assets","calls"}}
    assets=[]
    for asset in service.server.assets:
        body=path/(str(asset["id"])+".bin");body.write_bytes(asset["body"])
        assets.append(dict(metadata={k:v for k,v in asset.items() if k!="body"},path=str(body),sha256=store.sha(asset["body"])))
    metadata=path/"service.json";metadata.write_bytes(state.canonical(dict(attributes=attributes,server=server,assets=assets)))
    return str(metadata)


TWO_CAPTURE_NATIVE_SCRIPT = r'''
import ast,json,socket,sys,time,resource
from pathlib import Path
from datetime import datetime,timedelta,timezone
from copy import deepcopy
from types import SimpleNamespace
from tools.private_draft_store_v2 import limits
limits()
from nfl_lab import audit_weekly_grade_v1 as g,audit_weekly_grade_checkpoint_v1 as k,audit_weekly_epoch_v1 as epoch,state,private_draft_store as s
from nfl_lab import audit_private_rotation_v1 as rotation
from nfl_lab.operational_storage import OperationalStorage
sys.path.insert(0,str(Path.cwd()/'tests'))
import pytest
from test_private_draft_store_v2 import Server,Response,RUN,SOURCE
from test_owner_private_bootstrap import qualification
socket.socket.connect=lambda *_:(_ for _ in ()).throw(AssertionError('NO_REAL_NETWORK'))
ROOT=Path.cwd();ROOT_SHA='d'*64;GRADE=state.utc('2026-10-28T08:00:00Z')
seed=json.loads(Path(sys.argv[1]).read_bytes());phase=sys.argv[2];began=time.monotonic()
def metric(stage,**extra):
 memory={line.partition(':')[0]:int(line.partition(':')[2].split()[0])*1024 for line in Path('/proc/self/status').read_text().splitlines() if line.partition(':')[0] in {'VmPeak','VmSize','VmRSS','VmHWM'}}
 print(json.dumps(dict(stage=stage,phase=phase,pid=__import__('os').getpid(),CPU_seconds=time.process_time(),wall_seconds=time.monotonic()-began,**memory,**extra)),flush=True)
ns=globals()
for filename,names in [('test_audit_weekly_archive_v1.py',{'Service'}),('test_audit_weekly_grade_checkpoint_v1.py',{'Service','Parent','case'})]:
 nodes=[n for n in ast.parse((ROOT/'tests'/filename).read_text()).body if isinstance(n,(ast.ClassDef,ast.FunctionDef)) and n.name in names]
 # This test uses real per-process native identities in the unchanged service ABI.
 class Process(ast.NodeTransformer):
  def visit_keyword(self,n):
   self.generic_visit(n)
   if n.arg=='process':n.value=ast.Call(func=ast.Attribute(value=ast.Name(id='s',ctx=ast.Load()),attr='process_identity',ctx=ast.Load()),args=[],keywords=[])
   return n
 nodes=[Process().visit(n) for n in nodes]
 exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),filename,'exec'),ns)
 if filename=='test_audit_weekly_archive_v1.py':ArchiveService=Service
service_path=seed['initial_service'] if phase=='writer' else seed['saved_service']
saved=json.loads(Path(service_path).read_bytes());service=Service.__new__(Service);service.calls=[];service.server=Server()
for name,value in saved['attributes'].items():setattr(service,name,state.utc(value['datetime']) if isinstance(value,dict) and set(value)=={'datetime'} else value)
for name,value in saved['server'].items():setattr(service.server,name,value)
service.server.assets=[]
for asset in saved['assets']:
 body=Path(asset['path']).read_bytes();assert s.sha(body)==asset['sha256'];service.server.assets.append(dict(asset['metadata'],body=body))
e=epoch.restore_epoch(seed['epoch'],seed['original_choice'].encode(),seed['original_completion'],seed['slate'],seed['catalog'],seed['policy'],history_binding=seed['history_binding'],now=GRADE)
r=epoch.bind_registration(e,seed['completion'],now=GRADE);c=epoch.EpochChoice(seed['choice'],state.digest(seed['choice']));c.verify(r,GRADE)
storage=OperationalStorage(seed['cache'],ROOT/'config/operational-source-policy-v2.json',state=seed['state_root'])
metric('TYPED_TWO_CAPTURE_METADATA_READY')
if phase=='writer':
 population=g.bind_population(seed['population'],r,c,authenticate=lambda _:True,at=GRADE)
 captures=[g.bind_capture(r,c,population,item['restored'],storage=storage,capture_id=item['capture_id'],role_catalog=seed['roles'],frozen_schedule=seed['schedule'],authenticate=lambda _:True,at=GRADE) for item in seed['captures']]
 assert len(captures)==2 and all(len(x.document['forecasts'])==23000 and len(x.document['selected'])==5000 for x in captures)
 metric('TWO_FULL_CAPTURES_BOUND')
 doc=dict(schema_version=g.VERSION+'-provider-observations',source_policy_sha256=g.cp.POLICY_SHA,captured_at=GRADE.isoformat(),observations=[],finality=[dict(season=2026,week=7,status_source_sha256='a'*64,observed_at=(GRADE-timedelta(hours=1)).isoformat(),games=[dict(game_id='espn:'+x['website_game_id'],kickoff_utc=x['kickoff_utc'],home=x['home'],away=x['away'],final=True) for x in seed['schedule']])])
 batch=g.bind_observations(captures,doc,authenticate=lambda _:True,at=GRADE)
 snapshot=g.grade(r,captures,[batch],storage=storage,output=Path(seed['output'])/'grade',clock=lambda:GRADE)
 manifest=g._unpack(Path(snapshot.binding['path']).read_bytes(),64<<20)
 assert manifest['schema_version']==g.SNAPSHOT_WIRE_V2 and len(manifest['parts'])==2
 assert manifest['logical_bytes']>64<<20 and manifest['logical_sha256']==snapshot.sha256
 assert sum(len(v['snapshot']['rows']) for v in snapshot.document['versions'])==10000
 metric('TWO_FULL_CAPTURES_GRADED',logical_bytes=manifest['logical_bytes'],part_bytes=[p['bytes'] for p in manifest['parts']])
 q=dict(storage=storage,snapshot=snapshot,r=r)
else:
 handoff=json.loads(Path(seed['handoff']).read_bytes());q=dict(storage=storage,snapshot=SimpleNamespace(sha256=handoff['snapshot_sha256']),r=r)
path=Path(seed['output'])/phase;path.mkdir(parents=True,mode=0o700)
patch=pytest.MonkeyPatch();actual_envelope=k.native_envelope
# Use the already initialized fictional remote; no extra native client/budget.
original_service=Service;Service=lambda unused:service
operation=ns['case'].__wrapped__(q,path,patch);Service=original_service;patch.setattr(k,'native_envelope',actual_envelope)
if phase=='writer':
 handoff,client=operation['append']();Path(seed['handoff']).write_bytes(s.canonical(handoff))
 tree=ast.parse((ROOT/'tests/test_audit_weekly_grade_native_memory_v1.py').read_text());save=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_save_fictional_service')
 store=s;exec(compile(ast.fix_missing_locations(ast.Module(body=[save],type_ignores=[])),'fictional-service-save','exec'),globals())
 _save_fictional_service(service,Path(seed['saved_service']).parent)
 metric('TWO_FULL_PARTITION_CHECKPOINT_APPENDED',HTTP_calls=client.calls,logical_sha256=handoff['snapshot_sha256'],runtime_bytes=sum(a['size'] for a in service.server.assets),writer_process=client.process)
else:
 operation['parent'].handoff=deepcopy(handoff)
 result,client=operation['restore'](handoff);result.verify();k.native_envelope()
 assert len(result.durable.document['captures'])==2 and all(len(x['forecasts'])==23000 and len(x['selected'])==5000 for x in result.durable.document['captures'])
 assert sum(len(v['snapshot']['rows']) for v in result.durable.document['versions'])==10000
 assert all(v['actual'] is None for version in result.durable.document['versions'] for v in version['snapshot']['rows'])
 assert all(request.method=='GET' for request in service.calls)
 assert result.proof['producer']['process_identity']!=result.proof['reader']['process_identity']
 assert result.report['all_negative_weeks_retained'] is True and result.report['public_release'] is False
 assert all('catboost' not in name for name in sys.modules)
 evidence=snapshot_path=path/'restore/FRESH_READER_NATIVE_PROOF.json'
 proof=json.loads(evidence.read_bytes());assert len(proof['context']['multipart_readback']['parts'])==2
 assert proof['context']['multipart_readback']['completed_at_utc']<=result.proof['known_by_at']
 metric('TWO_FULL_PARTITION_CHECKPOINT_RESTORED_AND_REPORTED',HTTP_calls=client.calls,all_GET=True,known_by_at=result.proof['known_by_at'],reader_process=client.process)
'''


def test_two_full_disjoint_captures_partition_checkpoint_in_separate_native_processes(tmp_path):
    from test_audit_weekly_grade_checkpoint_v1 import Service
    left,right=two_full_scope_fixture(tmp_path/"fixture");q=left;f=q["f"]
    remote=tmp_path/"remote";remote.mkdir(mode=0o700);service=Service(remote)
    initial=_save_fictional_service(service,tmp_path/"initial-remote")
    seed=dict(cache=str(q["storage"].cache),state_root=str(q["storage"].state_root),epoch=q["r"].epoch.document,
        completion=q["r"].completion,original_choice=f["raw"].decode(),original_completion=f["completion"],slate=f["slate"],catalog=f["catalog"],policy=f["policy"],history_binding=f["history_binding"],
        choice=q["c"].document,population=q["pop"],roles=q["roles"],schedule=q["schedule"],captures=[dict(restored=x["restored"],capture_id=x["capture_id"]) for x in (left,right)],
        initial_service=initial,saved_service=str(tmp_path/"writer-remote/service.json"),handoff=str(tmp_path/"handoff.json"),output=str(tmp_path/"worker"))
    path=tmp_path/"two-full-native-seed.json";path.write_bytes(state.canonical(seed))
    profile=json.loads((ROOT/"config/audit-weekly-numerical-runtime-v1.json").read_bytes())["environment"]
    phases=[]
    for phase in ("writer","reader"):
        result=subprocess.run([sys.executable,"-B","-c",TWO_CAPTURE_NATIVE_SCRIPT,str(path),phase],cwd=ROOT,
            env=dict(PYTHONDONTWRITEBYTECODE="1",**profile),capture_output=True,text=True,timeout=185)
        print(result.stdout,end="",flush=True)
        assert result.returncode==0,result.stderr
        values=[json.loads(line) for line in result.stdout.splitlines()]
        assert all(v["VmPeak"]<=512<<20 and v["CPU_seconds"]<120 and v["wall_seconds"]<180 for v in values)
        assert values[-1]["HTTP_calls"]<=40;phases.append(values[-1])
    assert phases[0]["stage"]=="TWO_FULL_PARTITION_CHECKPOINT_APPENDED" and phases[1]["stage"]=="TWO_FULL_PARTITION_CHECKPOINT_RESTORED_AND_REPORTED"
    assert phases[0]["pid"]!=phases[1]["pid"] and phases[0]["runtime_bytes"]<32<<20
