"""Independent finite packing counterexample; all bodies and transport fictional."""
from collections import Counter
from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import random
import resource
import subprocess
import tempfile
import sys
import time

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nfl_lab import audit_weekly_archive_v1 as a
from nfl_lab.operational_storage import OperationalStorage


def _wire_size(files):
    """Independent byte count from the documented canonical/base64 wire format."""
    canonical = lambda value: json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    size = len(canonical(dict(files=[], schema_version=a.codec.VERSION)))
    for n, f in enumerate(files):
        header = dict(bytes=f["bytes"], content_b64="", origin=f["origin"], path=f["logical_path"], sha256=f["sha256"])
        size += len(canonical(header)) + 4 * ((f["bytes"] + 2) // 3) + (n > 0)
    return size


def _item(root, name, size, body=None):
    ref = dict(path=str(root / name), bytes=size, sha256=hashlib.sha256(body if body is not None else name.encode()).hexdigest())
    return a.cp.file_item(ref, name, "control")


def _shape(root):
    small = [_item(root, f"a-small/{i:04}.bin", 1536 << 10) for i in range(5)]
    large = [_item(root, f"b-large/{i:04}.bin", 3 << 20) for i in range(5)]
    tiny = [_item(root, f"c-control/{i:04}.bin", 128) for i in range(373)]
    return small, large, tiny



# Permitted original partial-scope headers, anonymized to body byte count,
# logical-path JSON length and physical-path JSON length (excluding quotes).
# No names, body hashes, private paths, rows or model data are retained here.
# This is 353 originals; two source JSON metadata originals were unavailable.
_PARTIAL_SHAPE = """18337:18:86
1559:31:99
109558:27:116
4461:29:122
35737:28:113
10342:28:119
3028:27:101
1698:21:89
9592:26:94
33307:28:89
54967:19:94
10036:30:97
22026:20:94
1680:31:98
6870:20:95
10058:30:105
9034:31:105
1723:24:98
39334:23:97
13734:38:113
298208:40:115
73401:38:113
73550:38:113
73238:38:113
73074:38:113
65193:38:113
67137:38:113
67693:38:113
59752:38:113
64017:38:113
63540:38:113
68446:38:113
63807:38:113
71919:38:113
64909:38:113
71673:38:113
74033:38:113
72656:38:113
59998:38:113
73915:38:113
74327:38:113
74248:38:113
73162:38:113
69659:38:113
64446:38:113
6245:38:113
359711:42:117
356089:42:117
349156:42:117
355810:42:117
1582:37:112
802959:32:107
698:32:107
62:30:105
191614:31:106
27490:38:113
1835059:30:141
337:49:124
1670747:106:181
1670747:106:181
1670747:106:181
474:50:125
36050:115:190
36050:115:190
474:123:198
474:123:198
108539:40:115
108615:40:115
108552:40:115
106929:40:115
101935:40:115
95186:40:115
645:26:103
5695754:29:106
15464:18:99
41261:26:107
1835059:22:105
1393443:16:90
364:31:110
369:31:110
367:31:110
368:31:110
367:31:110
367:31:110
366:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
365:31:110
367:31:110
368:31:110
365:31:110
366:31:110
365:31:110
365:31:110
365:31:110
365:31:110
365:31:110
365:31:110
365:31:110
365:31:110
365:31:110
365:31:110
365:31:110
365:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
368:31:110
368:31:110
368:31:110
368:31:110
368:31:110
368:31:110
368:31:110
368:31:110
368:31:110
368:31:110
368:31:110
368:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
365:31:110
365:31:110
365:31:110
365:31:110
365:31:110
365:31:110
365:31:110
365:31:110
365:31:110
365:31:110
365:31:110
365:31:110
365:31:110
365:31:110
365:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
365:31:110
365:31:110
365:31:110
365:31:110
365:31:110
365:31:110
365:31:110
365:31:110
365:31:110
365:31:110
365:31:110
365:31:110
365:31:110
365:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
367:31:110
10036:29:96
17431:23:90
111:21:88
2486:26:93
2807:21:88
344084:28:95
5767:27:94
671:23:90
6870:27:94
9034:37:104
22026:26:93
596:67:134
81964:54:121
588:59:126
81971:46:113
586:57:124
76152:44:111
586:57:124
76091:44:111
586:57:124
75989:44:111
585:56:123
76119:43:110
593:64:131
73364:51:118
585:56:123
75159:43:110
581:52:119
78332:39:106
581:52:119
80661:39:106
592:63:130
77619:50:117
584:55:122
74782:42:109
586:57:124
78318:44:111
586:57:124
79891:44:111
597:68:135
78288:55:122
589:60:127
75301:47:114
593:64:131
75101:51:118
585:56:123
74091:43:110
5779:29:96
231775:24:91
981:52:119
963:44:111
957:42:109
957:42:109
957:42:109
954:41:108
972:49:116
954:41:108
937:37:104
942:37:104
969:48:115
951:40:107
952:42:109
957:42:109
984:53:120
966:45:112
972:49:116
954:41:108
10959:33:100
9205:26:93
32985:23:90
569:38:105
468930:25:92
7445:97:164
7445:97:164
6931:97:164
7315:97:164
6931:97:164
7189:97:164
7444:97:164
7444:97:164
6930:97:164
7314:97:164
6930:97:164
7188:97:164
7444:97:164
7444:97:164
6930:97:164
7314:97:164
6930:97:164
7188:97:164
7444:97:164
7444:97:164
6930:97:164
7314:97:164
6930:97:164
7188:97:164
7444:97:164
7444:97:164
6930:97:164
7314:97:164
6930:97:164
7188:97:164
42283:33:120"""


def _partial_shape(root=Path("/fictional")):
    rows = [tuple(map(int, line.split(":"))) for line in _PARTIAL_SHAPE.splitlines()]
    assert hashlib.sha256(a.store.canonical(rows)).hexdigest() == "e599b2babc75e4673abd821d890a4bbeddd03578a4521147e1404469758decce"
    files = []
    for n, (size, logical_length, physical_length) in enumerate(rows):
        name = f"f{n:04}_".ljust(logical_length, "x")
        physical = (str(root) + "/" + f"f{n:04}_").ljust(physical_length, "x")
        assert len(name) == logical_length and len(physical) == physical_length
        ref = dict(path=physical, bytes=size, sha256=hashlib.sha256(str(n).encode()).hexdigest())
        files.append(a.cp.file_item(ref, name, "control"))
    return files


def _prior_first_fit_decreasing(files):
    """Reproduce the rejected FFD heuristic using independent full wire sizes."""
    bins = []
    for item in sorted(files, key=lambda f: (-_wire_size([f]), f["logical_path"])):
        for group in bins:
            if len(group) < 64 and _wire_size(group + [item]) <= a.codec.GROUP_JSON:
                group.append(item)
                break
        else: bins.append([item])
    return bins


def test_partial353_anonymous_exact_wire_shape_exposes_stranded_ffd_slots():
    files = _partial_shape()
    assert len(files) == 353 and sum(f["bytes"] for f in files) == 24_257_203
    assert len(a.codec.groups(files)) == 9
    prior = _prior_first_fit_decreasing(files)
    assert [len(g) for g in prior] == [3, 6, 9, 64, 64, 64, 64, 64, 15]
    _coverage(prior, files)
    original = deepcopy(files)
    balanced = a.capture_groups(files)
    assert len(balanced) == math.ceil(len(files) / 64) == 6
    _coverage(balanced, files)
    assert files == original
    assert a.capture_groups(list(reversed(files))) == balanced


def _coverage(groups, files):
    encoded = lambda f: json.dumps(f, sort_keys=True, separators=(",", ":"))
    assert Counter(encoded(f) for g in groups for f in g) == Counter(map(encoded, files))
    assert all(g and len(g) <= 64 and _wire_size(g) <= a.codec.GROUP_JSON for g in groups)
    assert all(_wire_size(g) == a.codec.inflated_size(g) for g in groups)


def _witness(small, large, tiny):
    # Five large+small pairs have 6MiB base64 bodies, leaving ample JSON
    # headroom. Each takes 62 controls; the final 63 controls form group six.
    return [[large[i], small[i], *tiny[62*i:62*(i+1)]] for i in range(5)] + [tiny[310:]]


def test_hand_checked383_lex12_has_optimal_six_group_witness(tmp_path):
    small, large, tiny = _shape(tmp_path)
    files = small + large + tiny
    assert len(files) == 383 and sum(f["bytes"] for f in files) == 23_640_704
    # Lex next-fit: three small, two small, five separate large, then the
    # remaining controls consume five more groups after the last large fills.
    assert len(a.codec.groups(files)) == 12
    _coverage(_witness(small, large, tiny), files)
    assert math.ceil(len(files) / 64) == 6
    original = deepcopy(files)
    packed = a.capture_groups(files)
    assert len(packed) == 6
    _coverage(packed, files)
    assert files == original, "packing must not mutate the already-hashed original census"
    shuffled = files.copy(); random.Random(20261025).shuffle(shuffled)
    assert a.capture_groups(shuffled) == packed
    assert a.capture_groups(list(reversed(files))) == packed


@pytest.mark.parametrize("over", [0, 1])
def test_exact_empty_wrapper_and_interfile_comma_boundary(tmp_path, over):
    assert _wire_size([]) == a.codec.inflated_size([])
    left = _item(tmp_path, "boundary/left.bin", 3 << 20)
    low, high = 1, 6 << 20
    while low < high:
        middle = (low + high + 1) // 2
        if _wire_size([left, _item(tmp_path, "boundary/right.bin", middle)]) <= a.codec.GROUP_JSON:
            low = middle
        else: high = middle - 1
    right = _item(tmp_path, "boundary/right.bin", low)
    gap = a.codec.GROUP_JSON - _wire_size([left, right])
    assert 0 <= gap <= 3
    # Only origin.source_path grows: changing its length adjusts exact wire
    # size by one byte without modifying any body/base64-length arithmetic.
    right["path"] += "q" * (gap + over)
    right["origin"]["source_path"] = right["path"]
    assert _wire_size([left, right]) == a.codec.GROUP_JSON + over
    groups = a.capture_groups([left, right])
    assert len(groups) == (1 if over == 0 else 2)
    _coverage(groups, [left, right])


def test_original_zero_length_file_stays_in_census_and_out_of_encoded_groups(tmp_path):
    positive = _item(tmp_path, "positive.bin", 128)
    empty = _item(tmp_path, "empty.bin", 0, b"")
    files = [positive, empty]; original = deepcopy(files)
    assert a.capture_groups(files) == [[positive]]
    assert files == original and files[1]["bytes"] == 0
    assert files[1]["sha256"] == hashlib.sha256(b"").hexdigest()


@pytest.mark.parametrize("case", ["duplicate", "duplicate-logical", "duplicate-path", "single-too-large", "nine-bins", "over512"])
def test_packing_rejects_closed_invalid_or_infeasible_metadata(tmp_path, case):
    first = _item(tmp_path, "one.bin", 128)
    files = [first]
    if case == "duplicate": files = [first, deepcopy(first)]
    elif case == "duplicate-logical":
        second = _item(tmp_path / "other", "one.bin", 128); files = [first, second]
    elif case == "duplicate-path":
        second = a.cp.file_item({k: first[k] for k in ("path", "bytes", "sha256")}, "other.bin", "control"); files = [first, second]
    elif case == "single-too-large": files = [_item(tmp_path, "large.bin", 6 << 20)]
    elif case == "nine-bins":
        files = [_item(tmp_path, f"large/{n:03}.bin", 5 << 20) for n in range(9)]
        assert all(a.codec.GROUP_JSON / 2 < _wire_size([f]) <= a.codec.GROUP_JSON for f in files)
    elif case == "over512": files = [_item(tmp_path, f"many/{n:03}.bin", 1) for n in range(513)]
    with pytest.raises(a.store.StoreError): a.capture_groups(files)


def test_infeasible_owned_failure_capture_stops_before_encoder_and_any_POST(tmp_path, monkeypatch):
    from test_audit_weekly_archive_v1 import capture, Service, ROLES
    p = capture.__wrapped__(tmp_path)
    service = Service(tmp_path)
    source = p.storage.register_root(tmp_path / "infeasible-source")
    files = []
    for n in range(9):
        body = bytes([65+n]) * (5 << 20)
        name = f"failed/{n:03}.bin"
        a._publish_owned_files(p.storage, [(name, body)], source)
        files.append(_item(source, name, len(body), body))
    snapshot = dict(files=files, census=dict(archive_state="FAILURE_EVIDENCE", raw_HTTP_corpus_archived=False,
        model_weights_reuploaded=False, source_started_at=service.started.isoformat(), source_completed_at=service.started.isoformat(),
        actual_collected_at=service.started.isoformat()))
    assert a.validate_capture(snapshot, lambda name: source / name, complete=False)["qualified_selected"] is False
    def forbidden(*args, **kwargs): raise AssertionError("must reject the whole plan before encoding")
    monkeypatch.setattr(a.codec, "encode", forbidden)
    with pytest.raises(a.store.StoreError):
        a.produce(snapshot, service.factory(tmp_path / "infeasible-journal", "produce"), service.package,
            storage=p.storage, output=tmp_path / "infeasible-produce", root_go_sha256="d" * 64, jobs=ROLES, pending_census=service.census)
    assert service.posts() == []
    assert (tmp_path / "infeasible-produce/CONSUMED.json").exists()
    assert not (tmp_path / "infeasible-produce/APPENDED.json").exists()


def _native(base):
    from tools.private_draft_store_v2 import limits
    limits()
    assert resource.getrlimit(resource.RLIMIT_AS) == (512 << 20, 512 << 20)
    assert resource.getrlimit(resource.RLIMIT_CPU) == (120, 120)
    started = time.monotonic()
    storage = OperationalStorage(base / "cache", ROOT / "config/operational-source-policy-v2.json", state=base / "state")
    source = storage.register_root(base / "source"); restored = storage.register_root(base / "restored")
    small, large, tiny = _shape(source)
    real = {}
    for n in range(5):
        values = [(small[n]["logical_path"], bytes([97+n]) * small[n]["bytes"]),
                  (large[n]["logical_path"], bytes([65+n]) * large[n]["bytes"])]
        a._publish_owned_files(storage, values, source)
        for name, body in values: real[name] = _item(source, name, len(body), body)
    for start in range(0, len(tiny), 64):
        values = [(f["logical_path"], b"" if n == 372 else (f"FICTIONAL_OWNED_CONTROL_{n:04}".encode()).ljust(128, b"_")) for n, f in enumerate(tiny[start:start+64], start)]
        a._publish_owned_files(storage, values, source)
        for name, body in values: real[name] = _item(source, name, len(body), body)
    del values, body
    files = [real[f["logical_path"]] for f in small+large+tiny]
    positive = [f for f in files if f["bytes"]]
    assert len(a.codec.groups(positive)) == 12
    plan = a.capture_groups(files); assert len(plan) == 6
    _coverage(plan, positive)
    assert len(files) == 383 and len(positive) == 382
    total_encoded = 0
    for n, members in enumerate(plan):
        encoded, inflated = a.codec.encode(members)
        assert inflated == _wire_size(members) <= a.codec.GROUP_JSON
        assert len(encoded) <= 8 << 20
        record = dict(index=n, bytes=len(encoded), sha256=a.store.sha(encoded), inflated_bytes=inflated, files=members)
        # Original codec validates every file and original origin before any
        # owned batch extraction; no model or outcome object is deserialized.
        a._extract_owned_group(encoded, record, storage, restored)
        total_encoded += len(encoded)
    empty = [(f["logical_path"], b"") for f in files if not f["bytes"]]
    a._publish_owned_files(storage, empty, restored)
    a._owned_files(storage, [dict(path=str(restored/f["logical_path"]), bytes=f["bytes"], sha256=f["sha256"]) for f in files])
    for f in files:
        assert (source/f["logical_path"]).read_bytes() == (restored/f["logical_path"]).read_bytes()
    assert storage.snapshot()["physical_bytes"] <= 512 << 20
    print(json.dumps(dict(state="FICTIONAL_PACKING_AND_NATIVE_CODEC_PASSED", files=383, groups=6,
        logical_bytes=sum(f["bytes"] for f in files), encoded_bytes=total_encoded,
        CPU_seconds=round(time.process_time(), 4), wall_seconds=round(time.monotonic()-started, 4),
        RSS_peak_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        private_native_durability_claim=False, fits=0)), flush=True)


def test_full383_packing_and_owned_restore_in_fresh_original_native_envelope(tmp_path):
    numerical = json.loads((ROOT / "config/weekly-owner-private-bootstrap-v1.json").read_bytes())["numerical_environment"]
    result = subprocess.run([sys.executable, "-B", str(Path(__file__).resolve()), str(tmp_path)], cwd=ROOT,
        env={**os.environ, **numerical}, capture_output=True, text=True, timeout=185)
    print(result.stdout, end="", flush=True)
    if result.returncode: print(result.stderr, end="", file=sys.stderr, flush=True)
    assert result.returncode == 0
    summary = json.loads(result.stdout.splitlines()[-1])
    assert summary["files"] == 383 and summary["groups"] == 6
    assert summary["logical_bytes"] == 23_640_576
    assert summary["CPU_seconds"] < 120 and summary["wall_seconds"] < 180


def _native_partial(base):
    from tools.private_draft_store_v2 import limits
    limits()
    assert resource.getrlimit(resource.RLIMIT_AS) == (512 << 20, 512 << 20)
    assert resource.getrlimit(resource.RLIMIT_CPU) == (120, 120)
    started = time.monotonic()
    storage = OperationalStorage(base / "cache", ROOT / "config/operational-source-policy-v2.json", state=base / "state")
    # A short owned root lets every fictional physical path retain its exact
    # original wire length even when pytest's own temporary path is long.
    with tempfile.TemporaryDirectory(prefix="awp-") as short:
        source = storage.register_root(Path(short) / "source")
        restored = storage.register_root(base / "restored")
        files = _partial_shape(source)
        batch = []; batch_size = 0
        for n, f in enumerate(files):
            if batch and (len(batch) == 64 or batch_size + f["bytes"] > 8 << 20):
                a._publish_owned_files(storage, batch, source)
                batch = []; batch_size = 0
            body = bytes([33+n%90]) * f["bytes"]
            f["sha256"] = f["origin"]["source_sha256"] = a.store.sha(body)
            batch.append((str(Path(f["path"]).relative_to(source)), body))
            batch_size += len(body)
        if batch: a._publish_owned_files(storage, batch, source)
        del batch, body
        assert len(a.codec.groups(files)) == 9
        plan = a.capture_groups(files)
        assert len(plan) == 6
        _coverage(plan, files)
        a._owned_files(storage, files)
        total_encoded = 0
        for n, members in enumerate(plan):
            encoded, inflated = a.codec.encode(members)
            assert inflated == _wire_size(members) <= a.codec.GROUP_JSON
            assert len(encoded) <= 8 << 20
            record = dict(index=n, bytes=len(encoded), sha256=a.store.sha(encoded), inflated_bytes=inflated, files=members)
            a._extract_owned_group(encoded, record, storage, restored)
            total_encoded += len(encoded)
        a._owned_files(storage, [dict(path=str(restored/f["logical_path"]), bytes=f["bytes"], sha256=f["sha256"]) for f in files])
        for f in files:
            assert Path(f["path"]).read_bytes() == (restored/f["logical_path"]).read_bytes()
        assert storage.snapshot()["physical_bytes"] <= 512 << 20
        print(json.dumps(dict(state="FICTIONAL_PARTIAL_SHAPE_NATIVE_CODEC_PASSED", files=len(files), groups=len(plan),
            logical_bytes=sum(f["bytes"] for f in files), encoded_bytes=total_encoded,
            CPU_seconds=round(time.process_time(), 4), wall_seconds=round(time.monotonic()-started, 4),
            RSS_peak_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            missing_source_metadata_files=2, original_private_bodies_read=False,
            private_native_durability_claim=False, fits=0)), flush=True)


def test_partial353_exact_wire_shape_owned_roundtrip_in_original_native_envelope(tmp_path):
    numerical = json.loads((ROOT / "config/weekly-owner-private-bootstrap-v1.json").read_bytes())["numerical_environment"]
    result = subprocess.run([sys.executable, "-B", str(Path(__file__).resolve()), str(tmp_path), "partial"], cwd=ROOT,
        env={**os.environ, **numerical}, capture_output=True, text=True, timeout=185)
    print(result.stdout, end="", flush=True)
    if result.returncode: print(result.stderr, end="", file=sys.stderr, flush=True)
    assert result.returncode == 0
    summary = json.loads(result.stdout.splitlines()[-1])
    assert summary["files"] == 353 and summary["groups"] == 6
    assert summary["logical_bytes"] == 24_257_203
    assert summary["missing_source_metadata_files"] == 2
    assert summary["original_private_bodies_read"] is False
    assert summary["CPU_seconds"] < 120 and summary["wall_seconds"] < 180


if __name__ == "__main__":
    (_native_partial if len(sys.argv) > 2 else _native)(Path(sys.argv[1]))
