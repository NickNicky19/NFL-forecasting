"""Exactly eight new fictional law methods, only after review and root GO.

One Python process under an authenticated native timeout; it creates no child.
The existing exact-PID sampler and parent-death helper remain the resource
framework. No pytest CLI, plugin discovery, old test body or NGBoost import.
"""
import argparse
from contextlib import contextmanager
import ctypes
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import signal
import sys
import time
import traceback
from unittest.mock import patch

START = time.monotonic()
VERSION = "ngboost-law-software-optional-dispatch-v9-20261024"
BUDGETS = {"invocations": 1, "CPU_seconds": 106, "wall_seconds": 106,
    "combined_RSS_bytes": 536870912, "numerical_threads": 2,
    "new_fictional_methods": 8, "automatic_retries": 0, "children": 0,
    "NFL_private_CSV_Parquet_models_fits_CAS_HTTP_old_suites": 0,
    "scalar_grid_cell_attempts": 200000000, "Python_calls": 799447,
    "receipt_bytes": 1048576, "method_progress_bytes": 524288}
THREAD_VARS = ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS", "OMP_THREAD_LIMIT", "ARROW_IO_THREADS")
TEST_NAMES = (
    "test_signed_integer_lower_quantile_half_ties_and_cdf_floors",
    "test_rounded_normal_pmf_normalization_stable_tails_and_no_density_substitute",
    "test_discrete_normal_moments_and_crps_against_independent_finite_sums",
    "test_poisson_mass_moments_lower_quantile_and_bounded_rps",
    "test_bernoulli_rps_is_brier_and_contrary_boundary_logloss_is_infinite",
    "test_invalid_parameters_support_thresholds_and_registration_caps",
    "test_grid_caps_are_charged_before_allocation_without_renormalization",
    "test_row_alignment_subset_frozen_parameters_and_postoutcome_failure",
)
RELATIVE_BINDINGS = (
    "nfl_lab/__init__.py", "nfl_lab/ngboost_laws.py", "tests/test_ngboost_laws_software_v1.py",
    "config/ngboost-law-software-v1-proposal.json", "tools/ngboost_law_software_v1.py",
    "tools/freeze_ngboost_law_software_v1.py", "tools/offline_report_imports_v1.py",
    "tools/direct_booster_frozen_report_run.py", "tools/review_direct_booster_screen_guard_v4.py",
    "tools/direct_xgboost_binary_recovery.py",
)
IMPORT_PREFIXES = ("numpy", "scipy", "pytest", "_pytest", "pluggy", "iniconfig", "packaging",
    "pygments", "py", "typing_extensions", "threadpoolctl", "Cython", "cython", "charset_normalizer")
OPTIONAL_MISSING_MODULES = {"scikits.umfpack": "scikits", "sksparse.cholmod": "sksparse", "sksparse": "sksparse", "uarray": "uarray"}
OPTIONAL_MISSING_SUFFIXES = ("", ".py", ".pyc", ".cpython-312-x86_64-linux-gnu.so", ".abi3.so", ".so")
PRIOR_FAILURE_PATH = "/tmp/ngboost-law-optional-backends-v8-output/FINISHED.json"
PRIOR_FAILURE_SHA = "c2cc4e2662f83c48166c7123d3186373ef834e9135206772979a46479c07eaa6"


class PacketGuardError(BaseException):
    """Cannot be mistaken for an expected law-level ValueError in a test."""


def authenticate_missing_optional_module(name, registration, search_roots):
    """Metadata checks only; never import or ask find_spec about the parent.

    A wholly absent top-level parent establishes this exact optional backend's
    ordinary absence. Any new parent/module/extension or symlink fails closed;
    no installed backend is disabled and no import prefix is widened.
    """
    parent = OPTIONAL_MISSING_MODULES[name]
    expected = {"module": name, "top_level": parent,
        "search_roots": list(search_roots),
        "absent_candidates": [str(Path(base) / (parent + suffix))
            for base in search_roots for suffix in OPTIONAL_MISSING_SUFFIXES]}
    if registration != expected or len(set(search_roots)) != 6:
        raise PacketGuardError("EXACT_OPTIONAL_BACKEND_ABSENCE_REGISTRATION_REQUIRED")
    if name in sys.modules or parent in sys.modules:
        raise PacketGuardError("REGISTERED_ABSENT_BACKEND_ALREADY_LOADED")
    for base in search_roots:
        path = Path(base)
        if not path.is_absolute() or path.resolve() != path or not path.is_dir() or any(p.is_symlink() for p in (path, *path.parents)):
            raise PacketGuardError("REGISTERED_OPTIONAL_BACKEND_SEARCH_ROOT_CHANGED")
    for candidate in expected["absent_candidates"]:
        path = Path(candidate)
        if path.exists() or path.is_symlink():
            raise PacketGuardError("REGISTERED_OPTIONAL_BACKEND_ABSENCE_CHANGED")


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def pin(binding):
    path = Path(binding["path"])
    if (not path.is_absolute() or path.resolve() != path or path.is_symlink()
            or not path.is_file() or path.stat().st_size != binding["bytes"] or sha(path) != binding["sha256"]):
        raise PacketGuardError("FROZEN_BINDING_CHANGED: " + str(path))


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    loaded = importlib.util.module_from_spec(spec)
    sys.modules[name] = loaded
    spec.loader.exec_module(loaded)
    return loaded


@contextmanager
def process_free_threads(threadpoolctl, binding):
    """The existing recovery helper's small resolver pattern, no heavy import.

    Its original file is frozen as reference only. Importing that whole helper
    would import estimators and storage, outside this law-only packet.
    """
    path = Path(binding["path"])
    loaded = {Path(line.split()[-1]).resolve() for line in Path("/proc/self/maps").read_text().splitlines()
        if len(line.split()) >= 6 and line.split()[-1].endswith("/libc.so.6")}
    if path not in loaded:
        raise PacketGuardError("PINNED_LIBC_NOT_ALREADY_LOADED")
    def resolve(name):
        if name != "c":
            raise PacketGuardError("UNREGISTERED_THREAD_LIBRARY_LOOKUP")
        return str(path)
    with patch.object(threadpoolctl, "find_library", resolve):
        yield


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze", required=True, type=Path)
    parser.add_argument("--freeze-sha256", required=True)
    parser.add_argument("--go", required=True, type=Path)
    parser.add_argument("--go-sha256", required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if not (sys.dont_write_bytecode and sys.flags.isolated and sys.flags.no_site):
        raise PacketGuardError("ISOLATED_NO_SITE_PYTHON_B_REQUIRED")
    if sha(args.freeze) != args.freeze_sha256 or sha(args.go) != args.go_sha256:
        raise PacketGuardError("FREEZE_OR_ROOT_GO_CHANGED")
    freeze, go = json.loads(args.freeze.read_text()), json.loads(args.go.read_text())
    if (freeze["schema_version"] != VERSION or freeze["root"] != str(root)
            or freeze["budgets"] != BUDGETS or freeze["test_names"] != list(TEST_NAMES)):
        raise PacketGuardError("EXACT_EIGHT_METHOD_PACKET_REQUIRED")
    if (go.get("state") != "GO" or go.get("registration_id") != VERSION
            or go.get("freeze_sha256") != args.freeze_sha256 or go.get("root_ledger_writer") != "/root"
            or go.get("independent_static_review") != "PASS" or not str(go.get("reviewer", "")).startswith("/root/")):
        raise PacketGuardError("SEPARATE_STATIC_REVIEW_AND_EXACT_ROOT_GO_REQUIRED")
    if set(freeze["bindings"]) != {str(root / relative) for relative in RELATIVE_BINDINGS}:
        raise PacketGuardError("EXACT_CODE_BINDING_SET_REQUIRED")
    executable = freeze["interpreter"]
    if (sys.executable != executable["executable"] or sys.version != executable["version"]
            or str(Path(sys.executable).resolve()) != executable["binary"]["path"]):
        raise PacketGuardError("FROZEN_INTERPRETER_REQUIRED")
    if any(os.environ.get(name) != "2" for name in THREAD_VARS):
        raise PacketGuardError("ALL_NUMERICAL_THREAD_CAPS_TWO_REQUIRED")
    if os.environ.get("NFL_LAB_RUN_NGBOOST_LAW_SOFTWARE_V1") != "1":
        raise PacketGuardError("EXPLICIT_EIGHT_METHOD_MODULE_GATE_REQUIRED")
    output = Path(freeze["output"])
    if not output.is_absolute() or output.resolve() != output or Path("/tmp") not in output.parents or output.exists():
        raise PacketGuardError("FRESH_TMP_OUTPUT_REQUIRED")
    # Establish the hard wall parent and parent-death guard before any numerical
    # dependency or test import. These unchanged helpers are stdlib only.
    for relative in ("tools/direct_booster_frozen_report_run.py", "tools/review_direct_booster_screen_guard_v4.py"):
        pin(freeze["bindings"][str(root / relative)])
    guard = module(root / "tools/direct_booster_frozen_report_run.py", "ngboost_law_existing_parent_guard")
    sampler = module(root / "tools/review_direct_booster_screen_guard_v4.py", "ngboost_law_existing_pid_sampler")
    pin(freeze["timeout"])
    parent = Path("/proc") / str(os.getppid())
    expected = [freeze["timeout"]["path"], "--signal=KILL", "--kill-after=1s", str(BUDGETS["wall_seconds"]) + "s",
        sys.executable, "-I", "-S", "-B", str(Path(__file__).resolve()), "--freeze", str(args.freeze),
        "--freeze-sha256", args.freeze_sha256, "--go", str(args.go), "--go-sha256", args.go_sha256]
    frozen_argv = [args.freeze_sha256 if part == "FREEZE_SHA256" else args.go_sha256 if part == "ROOT_GO_SHA256" else part
        for part in freeze["argv_template"]]
    if expected != frozen_argv or args.go != Path(freeze["future_go"]):
        raise PacketGuardError("FROZEN_NATIVE_ARGV_CHANGED")
    if ((parent / "exe").resolve() != Path(freeze["timeout"]["path"])
            or (parent / "cmdline").read_bytes().rstrip(b"\0").split(b"\0") != [part.encode() for part in expected]):
        raise PacketGuardError("EXACT_NATIVE_TIMEOUT_ARGV_REQUIRED")
    guard.arm_parent_death(os.getppid())
    required_pids = [sampler.process_binding(os.getppid()), sampler.process_binding(os.getpid())]
    output.mkdir(exist_ok=False)
    (output / "CONSUMED.json").write_text(json.dumps({"invocations": 1, "retries": 0,
        "freeze_sha256": args.freeze_sha256, "go_sha256": args.go_sha256}) + "\n")
    resource.setrlimit(resource.RLIMIT_CPU, (BUDGETS["CPU_seconds"], BUDGETS["CPU_seconds"]))
    resource.setrlimit(resource.RLIMIT_AS, (536870912, 536870912))
    counts = {"denied_effects": 0, "Python_calls": 0, "scalar_grid_cell_attempts": 0,
        "resource_checks": 0, "children": 0, "HTTP": 0, "CAS": 0, "old_suite_methods": 0,
        "blocked_optional_bytecode_reads": 0, "blocked_optional_metadata_reads": 0,
        "registered_missing_optional_imports": 0}
    entered = {name: 0 for name in TEST_NAMES}
    peak_rss, peak_cpu = 0, 0.
    methods, failure, threadpools = [], None, []
    progress_bytes = 0
    law_file, test_file = str(root / "nfl_lab/ngboost_laws.py"), str(root / "tests/test_ngboost_laws_software_v1.py")
    readable = set(freeze["runtime_dependencies"]) | set(freeze["bindings"])
    metadata_absences = set(freeze.get('optional_metadata_absences', []))
    optional_search_roots = [str(root), str(root / "tools"), *freeze["import_paths"]]
    optional_backends = freeze.get("optional_module_absences", {})
    # Importlib normally tries cached bytecode before its source. Do not open
    # unpinned caches: report an ordinary cache miss only for an exact pinned
    # source/cache pair, so SourceFileLoader reads the authenticated .py bytes.
    source_cache_pairs = {str(Path(importlib.util.cache_from_source(path)).absolute()): path
        for path in readable if path.endswith('.py')}
    proc_reads = {str(Path("/proc") / str(item["pid"]) / name) for item in required_pids for name in ("stat", "status")}
    proc_reads.add("/proc/self/maps")
    native_paths = {path for path in freeze["runtime_dependencies"] if ".so" in Path(path).name}
    native_paths.add(executable["binary"]["path"])

    def deny(reason):
        counts["denied_effects"] += 1
        raise PacketGuardError(reason)

    def progress(record):
        nonlocal progress_bytes
        body = (json.dumps(record, sort_keys=True) + "\n").encode()
        if progress_bytes + len(body) > BUDGETS["method_progress_bytes"]:
            deny("METHOD_PROGRESS_BYTE_CAP")
        progress_bytes += len(body)
        with (output / "METHODS.jsonl").open("ab") as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())

    def budget():
        nonlocal peak_rss, peak_cpu
        counts["resource_checks"] += 1
        if os.getppid() != required_pids[0]["pid"]:
            deny("AUTHENTICATED_PARENT_CHANGED")
        rss, cpu = sampler.required_usage(required_pids)
        peak_rss, peak_cpu = max(peak_rss, rss), max(peak_cpu, cpu)
        if (rss >= 503316480 or cpu >= BUDGETS["CPU_seconds"] - 2
                or time.monotonic() - START >= BUDGETS["wall_seconds"] - 2):
            deny("FINITE_SOFTWARE_RESOURCE_STOP")

    def observe(frame, event, argument):
        if event != "call":
            return
        counts["Python_calls"] += 1
        if counts["Python_calls"] > BUDGETS["Python_calls"]:
            deny("GLOBAL_PYTHON_CALL_CAP")
        filename, name = frame.f_code.co_filename, frame.f_code.co_name
        if filename == law_file and name == "charge":
            cells = frame.f_locals.get("cells")
            if type(cells) is not int or cells < 0:
                deny("INVALID_GRID_COUNTER_CALL")
            counts["scalar_grid_cell_attempts"] += cells
            if counts["scalar_grid_cell_attempts"] > BUDGETS["scalar_grid_cell_attempts"]:
                deny("GLOBAL_GRID_CELL_CAP")
        if filename == test_file and name.startswith("test_"):
            if name not in entered or entered[name] != 0:
                deny("UNREGISTERED_OR_REPEATED_TEST_METHOD")
            entered[name] += 1
        if name == "fit" and "/site-packages/scipy/" in filename:
            deny("SCIPY_FIT_FORBIDDEN_IN_LAW_PACKET")
        if filename.startswith("/workspace/") and filename not in readable:
            deny("UNBOUND_WORKSPACE_CODE")
        if counts["Python_calls"] % 4096 == 0:
            budget()

    def audit(event, values):
        if event.startswith(("socket.", "subprocess.")) or event in {
                "os.system", "os.fork", "os.forkpty", "os.exec", "os.posix_spawn", "pty.spawn"}:
            deny("NETWORK_OR_CHILD_PROCESS_FORBIDDEN")
        if event == "import" and values:
            name = values[0]
            if name in OPTIONAL_MISSING_MODULES:
                if sys.path != optional_search_roots:
                    deny("REGISTERED_OPTIONAL_BACKEND_IMPORT_PATHS_CHANGED")
                authenticate_missing_optional_module(name, optional_backends.get(name), optional_search_roots)
                counts["registered_missing_optional_imports"] += 1
                # SciPy's documented optional backend probes catch ImportError.
                # Raise before module loading, with the exact registered name.
                raise ModuleNotFoundError("No module named " + repr(name) + " (authenticated absence)", name=name)
            if (name not in {"nfl_lab", "nfl_lab.ngboost_laws"}
                    and name != '_sysconfigdata__linux_x86_64-linux-gnu'
                    and name.split(".")[0] not in sys.stdlib_module_names
                    and not any(name == prefix or name.startswith(prefix + ".") for prefix in IMPORT_PREFIXES)):
                deny("UNREGISTERED_IMPORT: " + name)
        if event == "ctypes.dlopen" and values and values[0] is not None:
            if str(Path(os.fsdecode(values[0])).resolve()) not in native_paths:
                deny("UNBOUND_NATIVE_LIBRARY")
        if event == "ctypes.dlsym" and len(values) > 1 and str(values[1]) in {
                "system", "popen", "fork", "vfork", "execve", "socket", "connect"}:
            deny("NATIVE_PROCESS_OR_NETWORK_SYMBOL")
        if event in {"os.remove", "os.rename", "os.link", "os.symlink", "os.truncate", "os.chmod", "os.chown", "os.mkdir"}:
            deny("FILESYSTEM_MUTATION_FORBIDDEN")
        if event == "open" and values:
            if isinstance(values[0], int):
                deny("UNBOUND_FILE_DESCRIPTOR_OPEN")
            path = str(Path(os.fsdecode(values[0])).absolute())
            mode, flags = str(values[1] or ""), values[2]
            writing = any(letter in mode for letter in "wax+") or bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
            if writing:
                if path not in {str(output / "FINISHED.json"), str(output / "METHODS.jsonl")}:
                    deny("UNDECLARED_WRITE")
            elif path not in readable and path not in proc_reads:
                if path in metadata_absences:
                    if Path(path).exists() or Path(path).is_symlink():
                        deny('REGISTERED_METADATA_ABSENCE_CHANGED')
                    counts['blocked_optional_metadata_reads'] += 1
                    raise FileNotFoundError('registered absent optional package metadata', path)
                if path in source_cache_pairs:
                    counts["blocked_optional_bytecode_reads"] += 1
                    raise FileNotFoundError('unpinned optional bytecode; use frozen source', path)
                deny("UNBOUND_PRIVATE_DATA_MODEL_OR_OLD_TEST_READ: " + path)
            if path.endswith((".csv", ".parquet", ".pkl", ".pickle", ".joblib", ".npz", ".npy")):
                deny("DATA_OR_MODEL_ARTIFACT_READ_FORBIDDEN")

    def timeout(*unused):
        raise PacketGuardError("INTERNAL_WALL_RESERVE_STOP")

    signal.signal(signal.SIGALRM, timeout)
    signal.setitimer(signal.ITIMER_REAL, max(.001, BUDGETS["wall_seconds"] - 1 - (time.monotonic() - START)))
    try:
        if set(optional_backends) != set(OPTIONAL_MISSING_MODULES):
            raise PacketGuardError("EXACT_OPTIONAL_BACKEND_REGISTRY_REQUIRED")
        for name in OPTIONAL_MISSING_MODULES:
            authenticate_missing_optional_module(name, optional_backends[name], optional_search_roots)
        prior_failure = freeze["prior_software_failure"]
        if prior_failure["path"] != PRIOR_FAILURE_PATH or prior_failure["sha256"] != PRIOR_FAILURE_SHA:
            raise PacketGuardError("EXACT_PRIOR_SOFTWARE_FAILURE_REQUIRED")
        pin(prior_failure)
        for binding in (*freeze["bindings"].values(), *freeze["runtime_dependencies"].values(),
                        freeze["interpreter"]["binary"], freeze["parent_environment"], freeze["accepted_environment_metadata"]):
            pin(binding)
        parent_environment = json.loads(Path(freeze["parent_environment"]["path"]).read_text())["environment"]
        canonical = json.dumps(parent_environment, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        metadata = json.loads(Path(freeze["accepted_environment_metadata"]["path"]).read_text())
        if (hashlib.sha256(canonical).hexdigest() != freeze["environment_sha256"]
                or len(parent_environment["file_bindings"]) != 14946 or metadata["mismatches"] != []
                or metadata["state"] != "ENVIRONMENT_METADATA_EXACT_MATCH"
                or metadata["environment_sha256"] != freeze["environment_sha256"]):
            raise PacketGuardError("ACCEPTED_FULL_PARENT_ENVIRONMENT_REFERENCE_CHANGED")
        budget()
        sys.addaudithook(audit)
        sys.setprofile(observe)
        sys.path[:] = [str(root), str(root / "tools"), *freeze["import_paths"]]
        offline = module(root / "tools/offline_report_imports_v1.py", "ngboost_law_offline_dependencies")
        with offline.offline_dependency_imports():
            import threadpoolctl
            with process_free_threads(threadpoolctl, freeze["libc"]), threadpoolctl.threadpool_limits(limits=2):
                tests = module(test_file, "new_ngboost_law_software_v1_contracts")
                names = tuple(name for name, item in vars(tests).items() if name.startswith("test_") and callable(item))
                if names != TEST_NAMES:
                    raise PacketGuardError("EXACT_EIGHT_NEW_FUNCTIONS_REQUIRED")
                for name in TEST_NAMES:
                    budget()
                    progress({"name": name, "state": "STARTED", "freeze_sha256": args.freeze_sha256})
                    try:
                        getattr(tests, name)()
                        methods.append({"name": name, "state": "PASS"})
                    except PacketGuardError as error:
                        progress({"name": name, "state": "GUARD_STOP", "type": type(error).__name__, "reason": str(error)})
                        raise
                    except BaseException as error:
                        text = traceback.format_exc(limit=12)
                        methods.append({"name": name, "state": "FAILED", "type": type(error).__name__,
                            "traceback": text[:32768], "traceback_truncated": len(text) > 32768})
                    progress(methods[-1])
                threadpools = threadpoolctl.threadpool_info()
                if any(item.get("num_threads", 0) > 2 for item in threadpools):
                    deny("NATIVE_THREAD_CAP_EXCEEDED")
        for line in Path("/proc/self/maps").read_text().splitlines():
            fields = line.split()
            if len(fields) >= 6 and fields[-1].startswith("/") and ".so" in Path(fields[-1]).name:
                if str(Path(fields[-1]).resolve()) not in native_paths:
                    deny("UNBOUND_LOADED_NATIVE_LIBRARY")
        budget()
    except BaseException as error:
        failure = {"type": type(error).__name__, "traceback": traceback.format_exc(limit=12)[:32768]}
    finally:
        sys.setprofile(None)
        signal.setitimer(signal.ITIMER_REAL, 0)
        own = resource.getrusage(resource.RUSAGE_SELF)
        children = resource.getrusage(resource.RUSAGE_CHILDREN)
        final_rss, final_cpu = sampler.required_usage(required_pids)
        peak_rss, peak_cpu = max(peak_rss, final_rss), max(peak_cpu, final_cpu)
        parent_status = (parent / "status").read_text().splitlines()
        parent_hwm = [int(line.split()[1]) * 1024 for line in parent_status if line.startswith("VmHWM:")]
        highwater_bound = own.ru_maxrss * 1024 + parent_hwm[0] if len(parent_hwm) == 1 else BUDGETS["combined_RSS_bytes"]
        wall = time.monotonic() - START
        passed = (failure is None and len(methods) == 8 and all(item["state"] == "PASS" for item in methods)
            and all(value == 1 for value in entered.values()) and counts["denied_effects"] == 0
            and peak_cpu < BUDGETS["CPU_seconds"] and wall < BUDGETS["wall_seconds"]
            and highwater_bound < BUDGETS["combined_RSS_bytes"]
            and children.ru_utime == children.ru_stime == children.ru_maxrss == 0)
        receipt = {"schema_version": VERSION, "state": "PASS" if passed else "FAILED", "methods": methods,
            "exception": failure, "budgets": BUDGETS, "counts": counts, "method_entries": entered,
            "method_progress_bytes": progress_bytes,
            "unrun_methods": [name for name in TEST_NAMES if entered[name] == 0],
            "wall_seconds_before_receipt": wall, "combined_CPU_seconds_before_receipt": peak_cpu,
            "combined_sampled_RSS_peak_bytes": peak_rss, "individual_HWM_sum_upper_bound_bytes": highwater_bound,
            "resource_scope": "exact timeout+single test PID/startticks; sampled RSS plus conservative sum of individual highwater marks",
            "threadpools": threadpools, "parent_death_guard_armed": True, "required_pids": required_pids,
            "freeze_sha256": args.freeze_sha256, "go_sha256": args.go_sha256,
            "parent_environment_file_bindings_inherited": 14946, "runtime_dependency_files_rehashed": len(freeze["runtime_dependencies"]),
            "scientific_claim": "none; fictional software only; no NFL, NGBoost import, estimator or fit",
            "actual_backend": "UNATTESTED", "requested_model": "GPT-6.1 Sol Extra High"}
        body = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode()
        if len(body) > BUDGETS["receipt_bytes"]:
            raise PacketGuardError("RECEIPT_BYTE_CAP")
        with (output / "FINISHED.json").open("xb") as stream:
            stream.write(body)
        print(json.dumps({"state": receipt["state"], "methods_attempted": len(methods), "counts": counts,
            "wall_seconds_before_receipt": wall, "combined_CPU_seconds_before_receipt": peak_cpu,
            "individual_HWM_sum_upper_bound_bytes": highwater_bound, "receipt_sha256": hashlib.sha256(body).hexdigest()}))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
