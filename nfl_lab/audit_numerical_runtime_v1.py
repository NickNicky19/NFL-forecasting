"""Registered numerical mechanics, never execution/publication authority.

preflight(root, env, *, cpuinfo=None) is stdlib-only. It reads the closed profile,
six original SOURCE files, installed distribution metadata and Linux CPU flags.
No numerical package, model, replay fixture, provider, credential or full
environment is read. cpuinfo is a fictional-test seam; genuine startup uses None.

loaded(root, env) repeats preflight BEFORE any imports it performs. It then
checks the imported NumPy dispatch table and actual NumPy/SciPy OpenBLAS pools;
changing environment variables after import cannot qualify a default runtime.
Thread counts are inspected, not repaired or hidden by a temporary limit.
"""
from __future__ import annotations

from datetime import datetime
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re

VERSION = "audit-numerical-runtime-v1"
CONFIG = "config/audit-weekly-numerical-runtime-v1.json"
CONFIG_ID = "effective18-haswell-numpy-generic-v1"
DISABLED = "AVX512F,AVX512CD,AVX512_SKX,AVX512_CLX,AVX512_CNL,AVX512_ICL,AVX512_SPR,AVX2,FMA3,AVX,F16C,SSE41,SSE42,SSSE3,POPCNT"
ENVIRONMENT = {
    "ARROW_DEFAULT_MEMORY_POOL":"system","ARROW_IO_THREADS":"2","MALLOC_ARENA_MAX":"2",
    "MKL_NUM_THREADS":"2","NPY_DISABLE_CPU_FEATURES":DISABLED,"NUMEXPR_NUM_THREADS":"2",
    "OMP_NUM_THREADS":"2","OMP_THREAD_LIMIT":"2","OPENBLAS_CORETYPE":"Haswell",
    "OPENBLAS_NUM_THREADS":"2","VECLIB_MAXIMUM_THREADS":"2"}
VERSIONS = {"catboost":"1.2.10","joblib":"1.5.3","numpy":"2.3.5","pandas":"2.2.3","scikit-learn":"1.8.0","scipy":"1.17.0"}
MODEL_CODE = {
    "baseline_correction.py":"077ff69ea3e9ab3183b588accd4972baaeb1fd47f0af4c56411ef4875db68ba2",
    "cdf_engine.py":"6a963111f4173a88affe90ca1ce17532cd5eb690a1f28b284e9fa4145eecb214",
    "direct_boosters.py":"475e6aaca01790c896a81e51d911f5f48e4116b95383536501799c4242701e3f",
    "median_boosting.py":"c5bf8ef481c05027a2a1d4e1d19764920c0820f0614f60736826c17526e7799d",
    "role_boosting.py":"294e7e588215e7b7e98d6f1fb251eed31420921dff9a59e88434913133dbdf93",
    "weekly_future_inference.py":"d84a4de76737252a910ed01b626e17403290277feb894621e625ae0791ccef42"}
ORIGINAL_BITS_SHA256 = "b32283012512e8a8d3b6cf3c22db05581e6da8262e3276ee1f21e845f0d74086"
CONFIG_KEYS = {"schema_version","state","approved","registered_at_utc","owner_authorization","local_evidence_sha256",
    "numerical_configuration_id","applicable_to","environment","expected_bits_edits","forecast_release","model_fits",
    "numeric_imports_must_follow_environment","original_expected_replay_sha256","original_genuine_job_hardware_reconstructed",
    "original_model_code_sha256","package_versions","readiness","required_hardware_features"}


class NumericalRuntimeError(ValueError):
    """Fixed safe guards; never echo environment values or private paths."""


def require(value, code):
    if not value:
        raise NumericalRuntimeError(code)


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()


def sha(body):
    return hashlib.sha256(body).hexdigest()


def read(path,cap):
    path=Path(path)
    require(not any(p.is_symlink() for p in (path,*path.parents)) and path.is_file(),"NUMERICAL_PLAIN_METADATA_OR_SOURCE_REQUIRED")
    with path.open("rb") as stream:
        body=stream.read(cap+1)
    require(0<len(body)<=cap,"NUMERICAL_METADATA_OR_SOURCE_BOUND")
    return body


def decode(body):
    def pairs(items):
        result={}
        for key,value in items:
            require(key not in result,"NUMERICAL_DUPLICATE_CONFIG_KEY")
            result[key]=value
        return result
    def bad(_):
        raise NumericalRuntimeError("NUMERICAL_NONFINITE_CONFIG")
    return json.loads(body,object_pairs_hook=pairs,parse_constant=bad)


def profile(root):
    raw=read(Path(root)/CONFIG,32 << 10);p=decode(raw)
    require(type(p) is dict and set(p)==CONFIG_KEYS
        and p["schema_version"]=="count-numerical-runtime-config-v1"
        and p["state"]=="OWNER_REGISTERED_ZERO_FIT_WEEKLY_RUNTIME_GENUINE_READINESS_REQUIRED"
        and p["numerical_configuration_id"]==CONFIG_ID and p["approved"] is True
        and p["forecast_release"] is False and p["original_genuine_job_hardware_reconstructed"] is False
        and p["numeric_imports_must_follow_environment"] is True
        and type(p["model_fits"]) is int and p["model_fits"]==0
        and type(p["expected_bits_edits"]) is int and p["expected_bits_edits"]==0,"NUMERICAL_CLOSED_REGISTERED_PROFILE_REQUIRED")
    require(p["environment"]==ENVIRONMENT and p["package_versions"]==VERSIONS
        and p["original_model_code_sha256"]==MODEL_CODE
        and p["required_hardware_features"]==["x86_64","AVX2","FMA3"]
        and p["applicable_to"]==["MODEL_RESTORE","GENERAL_FUTURE_INFERENCE"]
        and p["readiness"]==["ORIGINAL_ALL18_STRICT_RETAINED_REPLAY","EXISTING_COUNT_COLD_ROLE_ORACLES",
            "FUTURE_INFERENCE_WITH_THE_SAME_STARTUP_ENVIRONMENT"],"NUMERICAL_EXACT_SOURCE_ENVIRONMENT_AND_VERSION_PROFILE")
    bits=p["original_expected_replay_sha256"]
    require(type(bits) is dict and len(bits)==18
        and all(type(k) is str and type(v) is str and re.fullmatch("[a-f0-9]{64}",v) for k,v in bits.items())
        and sha(canonical(bits))==ORIGINAL_BITS_SHA256,"NUMERICAL_ORIGINAL18_BITS_MUST_REMAIN_UNCHANGED")
    require(type(p["registered_at_utc"]) is str and datetime.fromisoformat(p["registered_at_utc"].replace("Z","+00:00")).tzinfo is not None
        and p["owner_authorization"]=="OWNER_NFL_AUDIT_CONTINUATION_20261025"
        and type(p["local_evidence_sha256"]) is str and re.fullmatch("[a-f0-9]{64}",p["local_evidence_sha256"]),
        "NUMERICAL_REGISTERED_METADATA_ONLY")
    return p,sha(raw)


def cpu_flags(cpuinfo):
    require(os.uname().sysname=="Linux" and os.uname().machine=="x86_64","NUMERICAL_LINUX_X86_64_REQUIRED_BEFORE_IMPORTS")
    if cpuinfo is None:
        cpuinfo=read("/proc/cpuinfo",8 << 20).decode("ascii")
    require(type(cpuinfo) is str and 0<len(cpuinfo)<=8 << 20,"NUMERICAL_BOUNDED_CPUINFO_REQUIRED")
    records=[];ids=set()
    for block in re.split(r"\n\s*\n",cpuinfo.strip()):
        fields={}
        for line in block.splitlines():
            if ":" not in line:
                continue
            key,value=line.split(":",1);key=key.strip()
            require(key not in fields,"NUMERICAL_AMBIGUOUS_CPUINFO")
            fields[key]=value.strip()
        if "processor" not in fields:
            continue
        identifier=fields["processor"]
        require(re.fullmatch("[0-9]+",identifier) and identifier not in ids,"NUMERICAL_UNIQUE_LOGICAL_CPUS_REQUIRED")
        ids.add(identifier)
        flags=set(fields.get("flags","").split())
        require({"avx2","fma"}<=flags,"NUMERICAL_AVX2_FMA_REQUIRED_ON_EVERY_CPU_BEFORE_IMPORTS")
        records.append(dict(processor=int(identifier),flags=sorted(flags)))
    require(records,"NUMERICAL_ALL_CPU_FLAGS_REQUIRED")
    records.sort(key=lambda r:r["processor"])
    return len(records),sha(canonical(records))


def preflight(root,env,*,cpuinfo=None,scope="MODEL_EXECUTION"):
    """Read-only stdlib startup gate; no actor/ROOT/execution authority."""
    require(scope in {"MODEL_EXECUTION","METADATA_ONLY"},"CLOSED_NUMERICAL_PREFLIGHT_SCOPE")
    root=Path(root).absolute()
    p,config_sha=profile(root)
    required={}
    for key,value in ENVIRONMENT.items():
        observed=env.get(key)
        require(type(observed) is str and observed==value,"NUMERICAL_REQUIRED_STARTUP_ENVIRONMENT_MISMATCH")
        required[key]=observed
    count,flags_sha=cpu_flags(cpuinfo)
    actual={}
    for name,expected in MODEL_CODE.items():
        actual[name]=sha(read(root/"nfl_lab"/name,2 << 20))
        require(actual[name]==expected,"NUMERICAL_ORIGINAL_MODEL_CODE_PIN_CHANGED")
    versions={}
    for package,expected in VERSIONS.items():
        # The three metadata-only jobs install requirements.lock, not the
        # separate model lock containing CatBoost. They never decode a model.
        # Full model readiness still requires every original package below.
        if scope=="METADATA_ONLY" and package=="catboost":continue
        try:
            versions[package]=importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            raise NumericalRuntimeError("NUMERICAL_REQUIRED_PACKAGE_METADATA_MISSING") from None
        require(versions[package]==expected,"NUMERICAL_PACKAGE_VERSION_MISMATCH")
    return dict(schema_version=VERSION+"-preflight",configuration_id=CONFIG_ID,config_sha256=config_sha,
        env_sha256=sha(canonical(required)),cpu_flags_sha256=flags_sha,cpu_count=count,
        model_code_pins_sha256=sha(canonical(actual)),original_expected_bits_sha256=ORIGINAL_BITS_SHA256,
        package_versions=versions,scope="NUMERICAL_MECHANICS_ONLY" if scope=="MODEL_EXECUTION" else "METADATA_ONLY_NOT_MODEL_READINESS",
        execution_authorized=False,forecast_release=False,model_fits=0)


def _libc():
    # Read loaded mappings; never ctypes.util.find_library()/ldconfig/subprocess.
    maps=Path("/proc/self/maps").resolve(strict=True)
    paths={Path(line.split()[-1]).resolve(strict=True) for line in read(maps,8 << 20).decode().splitlines()
        if len(line.split())>=6 and line.split()[-1].endswith("/libc.so.6")}
    require(len(paths)==1,"NUMERICAL_SINGLE_ALREADY_LOADED_LIBC_REQUIRED")
    path=next(iter(paths));body=read(path,8 << 20)
    return dict(path=str(path),bytes=len(body),sha256=sha(body))


def loaded(root,env):
    """Verify actual dispatch/pools after the same preflight; no limit repair."""
    result=preflight(root,env)
    import numpy as np
    require(np.__version__==VERSIONS["numpy"],"NUMERICAL_ACTUAL_NUMPY_VERSION_MISMATCH")
    module=np._core._multiarray_umath
    features=getattr(module,"__cpu_features__",None)
    dispatch=getattr(module,"__cpu_dispatch__",None)
    baseline=getattr(module,"__cpu_baseline__",None)
    require(type(features) is dict and type(dispatch) in (list,tuple) and dispatch
        and type(baseline) in (list,tuple) and set(baseline)=={"SSE","SSE2","SSE3"},
        "NUMERICAL_ACTUAL_NUMPY_DISPATCH_METADATA_REQUIRED")
    require(all(type(name) is str and features.get(name) is False for name in dispatch)
        and all(features.get(name) is False for name in DISABLED.split(",")),
        "NUMERICAL_ACTUAL_NUMPY_DISPATCH_NOT_DISABLED_STARTUP_FLAGS_TOO_LATE")
    import scipy
    import scipy.linalg  # Load its actual BLAS library before inspecting pools.
    require(scipy.__version__==VERSIONS["scipy"],"NUMERICAL_ACTUAL_SCIPY_VERSION_MISMATCH")
    import threadpoolctl
    from tools.ngboost_law_software_v1 import process_free_threads
    libc=_libc()
    with process_free_threads(threadpoolctl,libc):
        infos=threadpoolctl.threadpool_info()
    require(type(infos) is list and 0<len(infos)<=16,"NUMERICAL_BOUNDED_ACTUAL_THREADPOOLS_REQUIRED")
    pools=[];origins=set()
    for item in infos:
        require(type(item) is dict and type(item.get("num_threads")) is int and 1<=item["num_threads"]<=2,
            "NUMERICAL_ACTUAL_THREAD_COUNT_EXCEEDS_TWO")
        origin="other"
        parts=Path(item.get("filepath","")).parts
        for package in ("numpy","scipy"):
            if package+".libs" in parts:
                origin=package;origins.add(package)
        if item.get("user_api")=="blas" or origin in {"numpy","scipy"}:
            require(item.get("internal_api")=="openblas" and item.get("architecture")=="Haswell",
                "NUMERICAL_ACTUAL_OPENBLAS_NOT_HASWELL_STARTUP_FLAGS_TOO_LATE")
        pools.append(dict(origin=origin,user_api=item.get("user_api"),internal_api=item.get("internal_api"),
            architecture=item.get("architecture"),num_threads=item["num_threads"],version=item.get("version"),
            threading_layer=item.get("threading_layer")))
    require(origins=={"numpy","scipy"},"NUMERICAL_BOTH_NUMPY_AND_SCIPY_OPENBLAS_POOLS_REQUIRED")
    result.update(schema_version=VERSION+"-loaded",numpy_baseline=list(baseline),
        numpy_dispatch={name:features[name] for name in dispatch},actual_versions=dict(numpy=np.__version__,scipy=scipy.__version__),
        threadpools=pools,libc_sha256=libc["sha256"])
    return result

