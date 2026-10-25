"""Fresh stdlib monitor only; all numerical imports belong to its new worker."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time

VERSION="anytime-td-blend-v1-20261025"
START=time.monotonic()
CORE_SHA="1ef8e8a4109ebc2c098e6f814d72e7aeb17da66cba31d0dfea809d6ac7d751a6"


def pin(item):
    path=Path(item["path"])
    if path.stat().st_size!=item["bytes"] or any(p.is_symlink() for p in (path,*path.parents)):
        raise ValueError("outer binding identity changed")
    with path.open("rb") as stream:
        if hashlib.file_digest(stream,"sha256").hexdigest()!=item["sha256"]:raise ValueError("outer binding hash changed")
    return path


def main():
    parser=argparse.ArgumentParser()
    for name in ["manifest","sha256","go","go_sha256"]:parser.add_argument(name)
    a=parser.parse_args()
    for path,digest in [(a.manifest,a.sha256),(a.go,a.go_sha256)]:
        if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=digest:raise ValueError("outer metadata changed")
    m=json.loads(Path(a.manifest).read_text());go=json.loads(Path(a.go).read_text())
    if (go.get("state")!="ROOT_GO_SINGLE_ANYTIME_TD_BLEND" or go.get("manifest_sha256")!=a.sha256
            or go.get("registration_sha256")!=m["registration"]["sha256"] or go.get("actual_invocations")!=1
            or go.get("automatic_retries")!=0 or go.get("seal",{}).get("integrator")!="/root"):
        raise ValueError("new blend root GO required")
    review=json.loads(pin(go["independent_review"]).read_text())
    if review.get("state")!="PASS_EXACT_ANYTIME_TD_BLEND_PREEXEC" or review.get("manifest_sha256")!=a.sha256:
        raise ValueError("new exact independent blend review required")
    outer=m["outer_supervisor"];core_binding=outer["core"]
    if core_binding["sha256"]!=CORE_SHA:raise ValueError("exact c57 ownership core required")
    spec=importlib.util.spec_from_file_location("_blend_c57_core",pin(core_binding))
    core=importlib.util.module_from_spec(spec);sys.modules[spec.name]=core;spec.loader.exec_module(core)
    core.require_isolated_monitor()
    worker=m["worker"];root=Path(worker["cwd"])
    pin(worker["script"])
    interpreter=Path(worker["interpreter"]["path"])
    if (str(interpreter)!="/workspace/nfl-direct-boosters-venv/bin/python"
            or str(interpreter.resolve())!=worker["interpreter"]["resolved_path"]
            or worker["script"]["path"]!=str(root/"tools/run_anytime_td_blend_v1.py")):
        raise ValueError("fixed blend worker/interpreter identity changed")
    if hashlib.sha256(interpreter.read_bytes()).hexdigest()!=worker["interpreter"]["sha256"]:
        raise ValueError("interpreter changed")
    limits=core.Limits(cpu=60,wall=90,rss=536870912,retained=2097152,soft_reserve=10.,grace=3.,poll=.05,address_space=8589934592)
    command=[str(interpreter),"-B",worker["script"]["path"],a.manifest,a.sha256,a.go,a.go_sha256]
    proof=core.supervise(command,cwd=root,output=Path(m["output"]),limits=limits,receipt=Path(outer["receipt"]),
        start=START,cpu_origin=0.,metadata=dict(registration_id=VERSION,manifest_sha256=a.sha256,
        registration=m["registration"],core_sha256=CORE_SHA,worker_binding=worker["script"]))
    raise SystemExit(0 if proof["state"]=="COMPLETED" else 1)


if __name__=="__main__":main()
