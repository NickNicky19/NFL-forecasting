"""Retain pinned public reference bytes in A's existing accounted private store.

This is source/access evidence only: no models, inference, B workspace access,
private-provider download, forecast grading, or production operation.
"""
from __future__ import annotations
import base64, datetime, gzip, hashlib, io, json, resource, signal, sys, time, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
def enc(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)+"\n").encode()
def sha(data):
    return hashlib.sha256(data).hexdigest()
def execute(payload):
    cpu, wall = time.process_time(), time.monotonic()
    resource.setrlimit(resource.RLIMIT_CPU, (60, 61))
    resource.setrlimit(resource.RLIMIT_AS, (512*1024**2,)*2)
    signal.alarm(120)
    assert len(payload["source_calls"]) == 24
    assert payload["total_normalized_source_payload_bytes"] <= 8*1024**2
    assert payload["B_private_rows"] == payload["new_fits"] == payload["new_model_inference"] == 0
    sys.path.insert(0, str(ROOT))
    from tools import category_topfive_matched12_storage_v1 as st
    binding = json.loads(gzip.decompress((ROOT/"config/session-ab-private-transport-v1.private.json.gz").read_bytes()))
    store, _ = st.open_store(ROOT, allocation_sha256=binding["allocation_sha256"], root_go=st.GO)
    out = Path(binding["destination_root"])/"READ_ONLY_REFERENCE_CHECK_V2.zip"
    assert not out.exists(), "immutable destination already exists; do not overwrite"
    old = out.parent/"PUBLIC_B_CONTRACTS.zip"
    store.validate_reference(old, "02e36722f427533682037100399d021c2b01099ec2fa924c94d0431d39eab2b9")
    reuse = {}
    with zipfile.ZipFile(old) as z:
        assert sum(x.file_size for x in z.infolist()) <= 8*1024**2
        for info in z.infolist():
            data = z.read(info)
            reuse[sha(data)] = data
            if info.filename == "B_PUBLIC_CAPTURE.json":
                old_capture = json.loads(data)
                assert old_capture["version"] == "ab-public-B-contract-capture-v1"
                for source in old_capture["sources"]:
                    body = source["body"].encode()
                    reuse[sha(body)] = body
    members, manifest = {}, []
    for index, ref in enumerate(payload["files"]):
        data = ref["content"].encode() if ref["content"] is not None else reuse[ref["reuse_private_member_by_sha256"]]
        actual_blob = hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()
        assert actual_blob == ref["git_blob_sha1"], ref["path"]
        if ref["content"] is None:
            assert len(data) == ref["expected_bytes"]
        name = f"public-sources/{index:02d}.txt"
        members[name] = data
        manifest.append({"repository":"NickNicky19/NFL-forecasting-V2", "commit":ref["commit"],
                         "repository_path":ref["path"], "member":name, "bytes":len(data),
                         "sha256":sha(data), "git_blob_sha1":actual_blob,
                         "reuse":ref["content"] is None})
    metadata = {k:v for k,v in payload.items() if k != "files"}
    metadata["source_manifest"] = manifest
    metadata["captured_at_UTC"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    members["ACCESS_METADATA.json"] = enc(metadata)
    members["MEMBER_MANIFEST.json"] = enc({n:{"sha256":sha(b), "bytes":len(b)} for n,b in members.items()})
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name, data in sorted(members.items()):
            info = zipfile.ZipInfo(name, (1980,1,1,0,0,0))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, data)
    data = buffer.getvalue()
    assert len(data) <= 8*1024**2
    store.write_bytes(out, data)
    reference = store.validate_reference(out, sha(data))
    restored = out.read_bytes()
    assert sha(restored) == sha(data)
    with zipfile.ZipFile(io.BytesIO(restored)) as z:
        assert z.testzip() is None and set(z.namelist()) == set(members)
        for name, original in members.items():
            assert z.read(name) == original
    result = {"version":"A-readonly-reference-retention-v2.1", "state":"PASS_LOCAL_OWNED_IMMUTABLE_REFERENCE_READBACK",
              "artifact_id":"A-AB-READONLY-REFERENCE-CHECK-V2", "bytes":reference["bytes"], "sha256":reference["sha256"],
              "source_manifest":manifest, "source_calls":payload["source_calls"],
              "normalized_source_payload_bytes":payload["total_normalized_source_payload_bytes"],
              "offhost_restore":"NOT_VERIFIED", "B_private_rows_copied_or_scored":0,
              "new_fits_or_inference":0, "source_file_count":len(manifest),
              "actual_CPU_seconds":time.process_time()-cpu, "actual_wall_seconds":time.monotonic()-wall,
              "RSS_bytes":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
              "storage_limits_or_permissions_changed":0}
    (ROOT/"reports/session-a-b-matched-20261031/READ_ONLY_ACCESS_SOURCE_MANIFEST_V2.json").write_bytes(enc(result))
    signal.alarm(0)
    return result

if __name__ == "__main__":
    print(json.dumps(execute(json.loads(base64.b64decode(sys.argv[1]))), sort_keys=True))
