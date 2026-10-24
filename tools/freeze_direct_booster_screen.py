"""Create a nonexecutable exact-byte draft; never decode NFL values or fit."""
import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path
import resource
import sys
import time

START=time.monotonic()
CODE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(CODE))
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name


def pin(path):
    path=Path(path).resolve(strict=True)
    with path.open("rb") as stream: checksum=hashlib.file_digest(stream,"sha256").hexdigest()
    info=path.stat()
    return {"path":str(path),"sha256":checksum,"bytes":info.st_size,
            "inode":[info.st_dev,info.st_ino],"mode":oct(info.st_mode)}


def main():
    plan_path=CODE/"config/direct-booster-screen-v1.json"
    plan=json.loads(plan_path.read_text())
    output=Path(plan["output"])
    if (output/"screen-supervisor-consumed.json").exists(): raise ValueError("already consumed")
    environment_inventory=Path("/workspace/website-methods-research/resumed/direct-boosters-capability-v1-20261023/environment-inventory.json")
    roots={"numpy","pandas","scipy","scikit-learn","joblib","threadpoolctl","pyarrow","requests",
           "jsonschema","referencing","xgboost-cpu","lightgbm","catboost"}
    distributions={};todo=list(roots)
    while todo:
        name=canonicalize_name(todo.pop())
        if name in distributions: continue
        distribution=metadata.distribution(name)
        distributions[name]=distribution
        for text in distribution.requires or []:
            req=Requirement(text)
            if req.marker is not None and not req.marker.evaluate({"extra":""}): continue
            if req.url: raise ValueError("direct dependency URL not frozen")
            if metadata.version(req.name) not in req.specifier: raise ValueError("installed dependency violates metadata")
            todo.append(req.name)
    files={}
    for distribution in distributions.values():
        for relative in distribution.files or []:
            path=Path(distribution.locate_file(relative))
            if path.is_file():
                actual=path.resolve(strict=True)
                if actual not in files: files[actual]=pin(actual)
    tools={key:pin(CODE/"tools"/name) for key,name in {
        "run":"direct_booster_screen_run.py","supervisor":"direct_booster_screen_supervisor.py",
        "guard":"direct_booster_screen_guard.py","freezer":"freeze_direct_booster_screen.py"}.items()}
    inputs=[plan[key]["path"] for key in ("input_features","source_manifest","source_policy","category_contract","control_scored_freeze","capability_installation")]
    inputs.extend(item["path"] for item in plan["partition_audits"].values())
    bindings={str(Path(p).resolve()):pin(p) for p in [*sorted((CODE/"nfl_lab").glob("*.py")),plan_path,
        CODE/"config/direct-booster-adapter-v1.json",environment_inventory,*inputs,*[item["path"] for item in tools.values()]]}
    controls=json.loads(Path(plan["control_scored_freeze"]["path"]).read_text())
    if pin(plan["control_scored_freeze"]["path"])["sha256"]!=plan["control_scored_freeze"]["sha256"]:
        raise ValueError("original scored control freeze changed")
    categories=json.loads(Path(plan["category_contract"]["path"]).read_text())["categories"]
    targets=[name for name,item in categories.items() if item["state"]=="READY"]
    if len(targets)!=11 or "fantasy_ppr" in targets: raise ValueError("eleven supported control targets required")
    selected_controls=[]
    for year in plan["partitions"]["evaluation_years"]:
        for target in sorted(targets):
            for method in ("leaf_cdf","count_A","role_B","recent","pooled"):
                relative=f"private/scored/{year}/{target}/{method}/rows.parquet"
                expected=controls["bindings"].get(relative)
                if not expected or relative not in controls["scored_files"]:
                    raise ValueError("selected exact control is not globally frozen")
                item=pin(Path(plan["control_root"])/relative)
                if item["sha256"]!=expected: raise ValueError("selected frozen control bytes changed")
                bindings[item["path"]]=item
                selected_controls.append(item["path"])
    if len(selected_controls)!=165: raise ValueError("exactly165selected old controls required")
    # The metadata-only prerequisite must still match; this invokes no _verify.
    from nfl_lab.operational_sources import _code_hashes
    source=json.loads(Path(plan["source_manifest"]["path"]).read_text())
    if source["code_sha256s"]!=_code_hashes(): raise ValueError("source-compatible assembly changed")
    freeze={"schema_version":"direct-booster-screen-execution-v1","state":"DRAFT_REVIEW_REQUIRED",
        "seal":{"integrator":"ROOT_MUST_SEAL","reviewer":"REVIEWER_MUST_ACCEPT_EXACT_BYTES"},
        "code_root":str(CODE),"plan_path":str(plan_path),"plan_sha256":pin(plan_path)["sha256"],
        "cache":plan["cache"],"output":str(output),"timeout":pin("/usr/bin/timeout"),"tools":tools,
        "environment":{"executable":sys.executable,"python":sys.version,
            "packages":{name:d.version for name,d in sorted(distributions.items())},
            "inventory_path":str(environment_inventory),"inventory_sha256":pin(environment_inventory)["sha256"],
            "file_bindings":list(sorted(files.values(),key=lambda x:x["path"]))},
        "bindings":list(sorted(bindings.values(),key=lambda x:x["path"])),
        "selected_control_paths":selected_controls,
        "scope":"Byte hashes/JSON metadata only; no NFL semantic/model/outcome reads, fitting or screen invocation",
        "actual_screen_invocations_at_freeze":0,"source_coupled_code_files_matched":len(_code_hashes())}
    from nfl_lab.operational_storage import OperationalStorage
    policy=json.loads(Path(plan["source_policy"]["path"]).read_text())
    storage=OperationalStorage(plan["cache"],policy);storage.register_root(output)
    tag=hashlib.sha256(json.dumps(freeze,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()[:12]
    destination=output/f"DIRECT_BOOSTER_SCREEN_FREEZE_DRAFT-{tag}.json"
    storage.atomic_json(destination,freeze)
    cpu=resource.getrusage(resource.RUSAGE_SELF)
    result={"draft_path":str(destination),"draft_sha256":pin(destination)["sha256"],
        "code_input_bindings":len(bindings),"environment_files":len(files),
        "environment_bytes_hashed":sum(f["bytes"] for f in files.values()),
        "wall_seconds":time.monotonic()-START,"CPU_seconds":cpu.ru_utime+cpu.ru_stime,
        "max_RSS_bytes":cpu.ru_maxrss*1024,"actual_screen_invocations":0}
    storage.atomic_json(output/f"freeze-preparation-receipt-{tag}.json",result)
    print(json.dumps(result,sort_keys=True))


if __name__=="__main__": main()
