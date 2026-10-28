"""One bounded zero-NFL, zero-fit check of the V2 libc startup correction."""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import signal
import sys
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True)
    parser.add_argument("--sha256", required=True)
    args = parser.parse_args()
    raw = Path(args.plan).read_bytes()
    if hashlib.sha256(raw).hexdigest() != args.sha256:
        raise ValueError("exact root sealed bootstrap fixture required")
    plan = json.loads(raw)
    if plan["state"] != "ROOT_AUTHORIZED_ZERO_NFL_BOOTSTRAP_CHECK" or plan["resources"] != {
            "CPU_seconds": 10, "wall_seconds": 15, "RSS_bytes": 256 * 1024**2,
            "fits": 0, "NFL_values": 0, "HTTP": 0, "invocations": 1, "automatic_retries": 0}:
        raise ValueError("finite root bootstrap fixture authority required")
    start, cpu = time.monotonic(), time.process_time()
    resource.setrlimit(resource.RLIMIT_CPU, (10, 11))
    signal.signal(signal.SIGALRM, lambda *unused: os._exit(124))
    signal.setitimer(signal.ITIMER_REAL, 14)
    sys.dont_write_bytecode = True
    for name in ["OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "ARROW_NUM_THREADS"]:
        os.environ[name] = "1"
    ref = plan["runner"]
    path = Path(ref["path"])
    if path.resolve() != path or len(path.read_bytes()) != ref["bytes"] or hashlib.sha256(path.read_bytes()).hexdigest() != ref["sha256"]:
        raise ValueError("exact V2 runner source differs")
    spec = importlib.util.spec_from_file_location("new2025_v2_bootstrap_only", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    children = sockets = 0
    def deny(event, unused):
        nonlocal children, sockets
        if event.startswith("socket."):
            sockets += 1
            raise ValueError("fixture socket attempt forbidden")
        if event in {"subprocess.Popen", "os.system", "os.fork", "os.posix_spawn"}:
            children += 1
            raise ValueError("fixture child attempt forbidden")
    sys.addaudithook(deny)
    import numpy
    import scipy
    import sklearn.ensemble
    import threadpoolctl
    bootstrap = module.bootstrap_threadpool(plan["technical_bootstrap"])
    with threadpoolctl.threadpool_limits(limits=1):
        libraries = threadpoolctl.threadpool_info()
        if any(item["num_threads"] != 1 for item in libraries):
            raise ValueError("one-thread numerical library limit failed")
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    if rss > plan["resources"]["RSS_bytes"]:
        raise ValueError("bounded startup RSS exhausted")
    print(json.dumps({"state": "PINNED_THREADPOOL_CHILD_FREE_BOOTSTRAP_PASS",
        "runner_sha256": ref["sha256"], "plan_sha256": args.sha256,
        "bootstrap": bootstrap, "NFL_values": 0, "fits": 0,
        "attempted_child_calls": children, "attempted_socket_calls": sockets,
        "threadpools": [{"user_api": item["user_api"], "internal_api": item["internal_api"],
                        "num_threads": item["num_threads"]} for item in libraries],
        "resources": {"CPU_seconds": time.process_time() - cpu,
                      "wall_seconds": time.monotonic() - start, "RSS_bytes": rss}}))
    signal.setitimer(signal.ITIMER_REAL, 0)


if __name__ == "__main__":
    main()
