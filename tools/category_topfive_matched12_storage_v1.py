"""Fourth-peer source seal, explicit initialization and readonly inventory.

describe only reads metadata; it neither constructs nor opens a managed store.
initialize requires the exact allocation digest reviewed by the root integrator.
Existing peers are always attached without their constructors or write calls.
"""
from __future__ import annotations
import argparse,hashlib,importlib.util,json,os,resource,signal,sys,time
from pathlib import Path

sys.dont_write_bytecode=True

GO="ROOT_REVIEWED_MATCHED12_STORAGE_V1"
ROOT_DEFAULT=Path(__file__).resolve().parents[1]


def encoded(value):
    return (json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False)+"\n").encode()


def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def reference(path):
    p=Path(path)
    if not p.is_absolute() or p.resolve()!=p or any(x.is_symlink() for x in (p,*p.parents)):
        raise ValueError("canonical nonsymlink source/policy required")
    raw=p.read_bytes()
    return {"path":str(p),"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest()}


def prepare(root):
    """Read only pinned code, policy and control metadata; no NFL values."""
    root=Path(root).resolve()
    cap_path=root/"config/category-topfive-opportunity-over-under-capacity-v3.json"
    cap=json.loads(cap_path.read_text())
    prior_path=root/cap["storage_base_plan"]
    sp=json.loads(prior_path.read_text())["storage"]
    for key,ref in sp.items():
        if isinstance(ref,dict) and "sha256" in ref and key!="metadata_descriptor":
            if reference(ref["path"])!=ref:
                raise ValueError("frozen parent code/policy changed: "+key)
    paths={"market":Path(sp["market_policy"]["path"]),
        "legacy":Path(sp["legacy_policy"]["path"]),
        "prior":Path(sp["prior_policy"]["path"]),
        "metadata16":root/cap["old_metadata_descriptor"],
        "metadata8":root/cap["topfive_metadata_descriptor"]}
    policies={k:json.loads(p.read_text()) for k,p in paths.items()}
    market_root=Path(policies["market"]["store_policy"]["storage"]["forward_root"])
    cache=Path(sp["legacy_cache"])
    # Read the permanent control identities without constructing a store or
    # opening its flock. Initialization rechecks both under the inherited lock.
    control=cache/policies["legacy"]["storage"]["version"]
    lock=control/".quota.lock"
    registry=control/"registry.json"
    for p in (market_root.parent,lock,registry):
        if p.resolve()!=p or any(x.is_symlink() for x in (p,*p.parents)):
            raise ValueError("canonical existing approved control metadata required")
    stat=lock.stat()
    if not lock.is_file() or stat.st_nlink!=1:
        raise ValueError("single permanent existing flock required")
    source_paths={"fourth_module":root/"nfl_lab/category_topfive_matched12_storage_v1.py",
        "fourth_helper":Path(__file__).resolve(),
        "market_helper":Path(sp["original_helper"]["path"]),
        "metadata16_helper":Path(sp["helper"]["path"]),
        "metadata8_helper":root/"nfl_lab/category_topfive_storage_v1.py",
        "forward_parent":Path(sp["forward_implementation"]["path"]),
        "legacy_parent":Path(sp["legacy_library_root"])/"nfl_lab/operational_storage.py"}
    source_refs={k:reference(p) for k,p in source_paths.items()}
    old_refs={k:reference(p) for k,p in paths.items()}
    old_refs.update({"capacity_plan":reference(cap_path),"storage_plan":reference(prior_path),
        "execution_registration":reference(root/"config/category-topfive-matched-all12-execution-v1-20261030.json")})
    if any(json.loads(paths[k].read_text())!=v or reference(paths[k])!=old_refs[k]
        for k,v in policies.items()):
        raise ValueError("policy changed during source sealing")
    module=load(source_paths["fourth_module"],"matched12_allocation_source")
    allocation={"version":module.VERSION,"approved_parent":str(market_root.parent),
        "store_policy":{"storage":{"version":"operational-forward-storage-v3",
            "forward_root":str(market_root.parent/module.VERSION),
            "limit_bytes":module.NEW_LIMIT,"joint_limit_bytes":module.LEGACY_LIMIT+module.NEW_LIMIT,
            "legacy_limit_bytes":module.LEGACY_LIMIT,
            "legacy_registry_sha256_at_registration":reference(registry)["sha256"],
            "legacy_lock_at_registration":[stat.st_dev,stat.st_ino]}},
        "legacy_policy":policies["legacy"],"old_complete_limit_bytes":module.OLD_COMPLETE_LIMIT,
        "new_complete_limit_bytes":module.COMPLETE_LIMIT,
        "old_upcoming_reserve_bytes":module.OLD_UPCOMING_RESERVE,
        "wave_retained_limit_bytes":module.WAVE_RETAINED_LIMIT,
        "new_storage_module_sha256":source_refs["fourth_module"]["sha256"],
        "source_bindings":source_refs,"old_policy_bindings":old_refs}
    return {"allocation":allocation,"allocation_sha256":hashlib.sha256(encoded(allocation)).hexdigest(),
        "outer_descriptor_sha256":hashlib.sha256(encoded({"version":module.VERSION,"allocation":allocation})).hexdigest(),
        "outer_descriptor_bytes":len(encoded({"version":module.VERSION,"allocation":allocation})),
        "module":module,"sp":sp,"paths":paths,"policies":policies}


def open_store(root, *, allocation_sha256, root_go, readonly=False):
    prepared=prepare(root)
    if root_go!=GO or allocation_sha256!=prepared["allocation_sha256"]:
        raise ValueError("exact root-reviewed allocation digest and explicit GO required")
    a=prepared["allocation"];sp=prepared["sp"];p=prepared["policies"]
    # All pin checks precede module loading and every existing store attachment.
    old=load(sp["original_helper"]["path"],"matched12_market_source")
    metadata16=load(sp["helper"]["path"],"matched12_metadata16_source")
    metadata8=load(a["source_bindings"]["metadata8_helper"]["path"],"matched12_metadata8_source")
    base=old.load_frozen(sp["forward_implementation"]["path"],sp["legacy_library_root"])
    def peer():
        return prepared["module"].attach_readonly_complete_peer(base,
            legacy_cache=sp["legacy_cache"],market_policy=p["market"],legacy_policy=p["legacy"],
            prior_policy=p["prior"],metadata16_policy=p["metadata16"],metadata8_policy=p["metadata8"],
            market_module=old,metadata16_module=metadata16,metadata8_module=metadata8)
    cls=prepared["module"].build_storage_class(base,complete_peer_factory=peer,allocation=a)
    store=(cls.attach_readonly(sp["legacy_cache"],old.attach_readonly_forward) if readonly
        else cls(sp["legacy_cache"]))
    return store,prepared


def safe_plan(p):
    a=p["allocation"]
    return {"version":a["version"],"state":"SOURCE_SEAL_ONLY_NO_STORE_OPENED",
        "allocation_sha256":p["allocation_sha256"],"outer_descriptor_sha256":p["outer_descriptor_sha256"],
        "outer_descriptor_bytes":p["outer_descriptor_bytes"],
        "limits_bytes":{"old_complete":a["old_complete_limit_bytes"],"new_complete":a["new_complete_limit_bytes"],
            "new_peer":a["store_policy"]["storage"]["limit_bytes"],"wave_retained":a["wave_retained_limit_bytes"],
            "old_upcoming_reserve":a["old_upcoming_reserve_bytes"]},
        "bindings":{kind:{k:{"bytes":v["bytes"],"sha256":v["sha256"]} for k,v in a[kind].items()}
            for kind in ("source_bindings","old_policy_bindings")},
        "private_paths":"REDACTED_APPROVED_EXISTING_PRIVATE_WORKSPACE_ONLY",
        "offhost_restoration":"NOT_VERIFIED","NFL_models_fits_scoring_HTTP":0}


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--root",type=Path,default=ROOT_DEFAULT)
    ap.add_argument("--mode",choices=("describe","initialize","inventory"),required=True)
    ap.add_argument("--allocation-sha256");ap.add_argument("--root-go")
    args=ap.parse_args();begin=time.monotonic();cpu=time.process_time()
    resource.setrlimit(resource.RLIMIT_CPU,(120,121));resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,)*2)
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError("finite fourth-peer accounting operation")))
    signal.alarm(180)
    if args.mode=="describe":
        result=safe_plan(prepare(args.root))
    else:
        store,p=open_store(args.root,allocation_sha256=args.allocation_sha256,
            root_go=args.root_go,readonly=args.mode=="inventory")
        with store.transaction():
            store._refresh();usage=store._require(0)
            descriptor=store.validate_reference(store._matched_descriptor_path,p["outer_descriptor_sha256"])
        usage=store.verify_retained_checkpoint()
        result={**safe_plan(p),"state":"PASS_LOCAL_"+args.mode.upper(),
            "immutable_descriptor":{"sha256":descriptor["sha256"],"bytes":descriptor["bytes"]},
            "usage":{k:v for k,v in usage.items() if k.endswith("_bytes") and type(v) is int},
            "new_private_data_written":0,"new_controls_only":args.mode=="initialize"}
        result["retained_wave_checkpoint"]="PASS_ALL_NEW_CONTROLS_PARTIALS_FAILURES_AND_UNIQUE_BLOBS_COUNTED"
    result["actual"]={"CPU_seconds":time.process_time()-cpu,"wall_seconds":time.monotonic()-begin,
        "RSS_bytes":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024}
    signal.alarm(0);print(json.dumps(result,sort_keys=True),flush=True)


if __name__=="__main__":main()
