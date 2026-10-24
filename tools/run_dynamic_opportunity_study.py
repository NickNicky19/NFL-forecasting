"""Sealed worker for one54-package exposed opportunity experiment."""
import ctypes
import os
import signal
import sys

ARMED_PARENT = None
if __name__ == "__main__":
    try:
        ARMED_PARENT = int(sys.argv[sys.argv.index("--parent-pid") + 1])
    except (ValueError, IndexError):
        raise SystemExit("explicit resource supervisor parent required")
    if ARMED_PARENT <= 1 or os.getppid() != ARMED_PARENT:
        raise SystemExit("guard parent absent")
    _libc = ctypes.CDLL(None, use_errno=True)
    if _libc.prctl(1, signal.SIGKILL, 0, 0, 0) != 0:
        raise SystemExit("PDEATHSIG failed")
    if os.getppid() != ARMED_PARENT:
        os.kill(os.getpid(), signal.SIGKILL)

import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import resource
import stat

VERSION = "dynamic-opportunity-study-v1-20261023"
THREADS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS",
           "OMP_THREAD_LIMIT", "ARROW_IO_THREADS", "VECLIB_MAXIMUM_THREADS")
EXPECTED_BUDGET = dict(actual_invocations=1, wall_seconds=600, CPU_seconds=600, combined_RSS_bytes=1073741824,
    numerical_threads=2, new_retained_bytes=50331648, shared_retention_bytes=536870912,
    packages=54, development_cells=24, forecast_row_incidences=600000, prior_vector_formations=16,
    per_package_wall_seconds=20, per_package_CPU_seconds=20, HTTP=0,
    model_loads_gradient_fits=0, automatic_retries=0)


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def pin(item):
    path = Path(item["path"])
    if not path.is_absolute() or path.resolve() != path or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("canonical nonsymlink execution binding required")
    info = path.stat()
    if (not stat.S_ISREG(info.st_mode) or info.st_size != item["bytes"]
            or [info.st_dev, info.st_ino] != item["inode"] or oct(info.st_mode) != item["mode"]
            or sha(path) != item["sha256"]):
        raise ValueError("execution binding changed: " + str(path))


def load(path, expected):
    if sha(path) != expected:
        raise ValueError("sealed execution digest changed")
    freeze = json.loads(Path(path).read_text())
    seal = freeze.get("seal", {})
    if (freeze.get("state") != "SEALED_ROOT_AND_REVIEWER" or seal.get("integrator") != "/root"
            or not str(seal.get("reviewer", "")).startswith("/root/") or freeze.get("preexec_review") != "PASS"):
        raise ValueError("root seal and independent exact PREEXEC required")
    sys.path.insert(0, freeze["code_root"])
    for relative in ("nfl_lab/__init__.py", "nfl_lab/dynamic_opportunity_recovery.py"):
        path = str(Path(freeze["code_root"]) / relative)
        matches = [b for b in freeze["bindings"] if b["path"] == path]
        if len(matches) != 1:
            raise ValueError("metadata recovery loader binding missing")
        pin(matches[0])
    from nfl_lab.dynamic_opportunity_recovery import expand_environment
    return expand_environment(freeze, pin=pin)


def verify(freeze):
    if sha(freeze["plan_path"]) != freeze["plan_sha256"]:
        raise ValueError("registered science policy changed")
    policy = json.loads(Path(freeze["plan_path"]).read_text()); spec = freeze["execution_metadata"]
    if policy["registration_id"] != VERSION or spec["registration_id"] != VERSION:
        raise ValueError("different study registration")
    if spec["state"] != "FROZEN_ROOT_REVIEWER_SEALED" or not spec.get("seal"):
        raise ValueError("actual backend has no execution seal")
    if spec["budgets"] != EXPECTED_BUDGET or policy["budgets"] != EXPECTED_BUDGET:
        raise ValueError("finite54-package600s48MiB budget changed")
    if spec.get("recovery_envelope"):
        from nfl_lab.dynamic_opportunity_recovery import validate
        validate(spec["recovery_envelope"], source_plan=spec["source_plan"], output=spec["output"])
        if json.loads(Path(spec["recovery_plan"]["path"]).read_text()) != spec["recovery_envelope"]:
            raise ValueError("registered recovery envelope changed")
    bindings = {item["path"]: item for item in freeze["bindings"]}
    if len(bindings) != len(freeze["bindings"]):
        raise ValueError("duplicate execution path")
    required = {str(p) for p in (Path(freeze["code_root"]) / "nfl_lab").glob("*.py")}
    required |= {freeze["plan_path"], *(item["path"] for item in freeze["tools"].values())}
    required |= {item["path"] for item in spec["owned_inputs"]}
    required |= {item["path"] for item in freeze["extension_modules"]}
    required |= {freeze[k]["path"] for k in ("resource_guard", "resource_sampler")}
    if not required <= set(bindings):
        raise ValueError("complete source/evaluator/tool/input extension freeze required")
    for item in freeze["bindings"]:
        pin(item)
    for item in freeze["extension_modules"]:
        bound = bindings[item["path"]]
        if (not isinstance(item.get("module"), str) or not item["module"].startswith("nfl_lab.")
                or any(item[k] != bound[k] for k in ("path", "bytes", "sha256"))):
            raise ValueError("extension differs from exact binding")
    for name, expected in (("direct_booster_screen.py", "a47a5a21910a132977bda33ad531ba4c82b24cc9120143d40e3b415f32b84016"),
                           ("direct_boosters.py", "475e6aaca01790c896a81e51d911f5f48e4116b95383536501799c4242701e3f")):
        if sha(Path(freeze["code_root"]) / "nfl_lab" / name) != expected:
            raise ValueError("original common science helper changed")
    for field in ("source_policy", "category_contract", "control_freeze"):
        item = spec[field]
        if item["path"] not in bindings or bindings[item["path"]]["sha256"] != item["sha256"]:
            raise ValueError("required metadata contract unbound: " + field)
    if spec.get("recovery_envelope"):
        refs = [spec["recovery_plan"], *spec["recovery_envelope"]["previous_receipts"]]
        for item in refs:
            if item["path"] not in bindings or any(bindings[item["path"]][k] != item[k] for k in ("path", "bytes", "sha256")):
                raise ValueError("earlier failure/diagnosis or recovery registration not bound")
    plan = spec["source_plan"]
    if (plan["state"] != "FROZEN_ROOT_REVIEWER_SEALED" or not plan.get("seal")
            or plan["source_policy"] != spec["source_policy"]):
        raise ValueError("sealed permitted source plan mismatch")
    owned = {r["path"]: r["sha256"] for r in spec["owned_inputs"]}
    if any(owned.get(r["path"]) != r["sha256"] for r in plan["owned_inputs"]):
        raise ValueError("source plan escapes owned input inventory")
    for year in (2022, 2023, 2024):
        for target in ("rush_att", "rec", "rec_yd"):
            for method in ("leaf_cdf", "count_A", "role_B", "recent", "pooled"):
                item = spec["control_metadata"][str(year)][target][method]
                if owned.get(item["binding"]["path"]) != item["binding"]["sha256"]:
                    raise ValueError("unbound original comparator")
                if set(item["forecast_columns"]) & {"actual", "participation_state", "outcome_state"}:
                    raise ValueError("forecast projection includes forbidden scoring fields")
    environment = freeze["environment"]
    if sys.executable != environment["executable"] or sys.version != environment["python"] or not environment["file_bindings"]:
        raise ValueError("exact original environment required")
    for item in environment["file_bindings"]:
        pin(item)
    for name, expected in environment["packages"].items():
        if importlib.metadata.version(name) != expected:
            raise ValueError("environment package changed: " + name)
    if freeze["external_timeout"]["path"] != "/usr/bin/timeout":
        raise ValueError("pinned GNU timeout required")
    pin(freeze["external_timeout"])
    if any(os.environ.get(name) != "2" for name in THREADS):
        raise ValueError("all numerical thread limits must be inherited as2")
    return spec


def extensions(freeze):
    """Add separately pinned new files to the unchanged original helper assembly."""
    sys.path.insert(0, freeze["code_root"])
    for item in freeze["extension_modules"]:
        name = item["module"]; path = Path(item["path"])
        if sha(path) != item["sha256"]:
            raise ValueError("extension changed before import")
        if name in sys.modules:
            if Path(sys.modules[name].__file__).resolve() != path.resolve():
                raise ValueError("extension import collision: " + name)
            continue
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec); sys.modules[name] = module
        spec.loader.exec_module(module)


def arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze", required=True); parser.add_argument("--freeze-sha256", required=True)
    parser.add_argument("--parent-pid", type=int)
    return parser.parse_args()


def main():
    args = arguments()
    if ARMED_PARENT is None or os.getppid() != ARMED_PARENT or args.parent_pid != ARMED_PARENT:
        raise RuntimeError("worker parent-death guard absent")
    def deny(event, values):
        if event.startswith("socket.") or event in {"subprocess.Popen", "os.posix_spawn", "os.fork", "os.forkpty", "os.system"}:
            raise RuntimeError("dynamic worker forbids network and child processes")
    sys.addaudithook(deny)
    resource.setrlimit(resource.RLIMIT_CPU, (598, 599))
    ticks = int(Path("/proc/self/stat").read_text().rsplit(")", 1)[1].split()[19])
    ready = dict(state="DYNAMIC_WORKER_READY_NO_SCIENCE_IMPORTED", pid=os.getpid(), start_ticks=ticks,
                 parent_pid=ARMED_PARENT, freeze_sha256=args.freeze_sha256, PDEATHSIG_armed=True)
    print("DYNAMIC_READY " + json.dumps(ready, sort_keys=True), flush=True)
    def startup_timeout(signum, frame):
        raise RuntimeError("bounded startup GO missing")
    signal.signal(signal.SIGALRM, startup_timeout); signal.setitimer(signal.ITIMER_REAL, 2)
    release = json.loads(sys.stdin.readline())
    signal.setitimer(signal.ITIMER_REAL, 0)
    if release != dict(state="GO", pid=os.getpid(), start_ticks=ticks, parent_pid=ARMED_PARENT,
                       freeze_sha256=args.freeze_sha256, positive_RSS_verified=True):
        raise RuntimeError("startup GO identity or exact freeze mismatch")
    freeze = load(args.freeze, args.freeze_sha256); spec = verify(freeze)
    from nfl_lab.dynamic_opportunity_recovery import caps
    resource.setrlimit(resource.RLIMIT_CPU, (caps(spec)["CPU_seconds"] - 2, caps(spec)["CPU_seconds"] - 1))
    import pyarrow as pa
    pa.set_cpu_count(2); pa.set_io_thread_count(2)
    from offline_report_imports_v1 import offline_dependency_imports
    with offline_dependency_imports():
        extensions(freeze)
    from nfl_lab.dynamic_opportunity_backend import run
    run(spec, registration_sha256=freeze["plan_sha256"], final_static=lambda: verify(freeze))
    print(json.dumps(dict(phase="DYNAMIC_REPORT_COMPLETE", packages=54, new_fits_models_HTTP=0)), flush=True)


if __name__ == "__main__":
    main()
