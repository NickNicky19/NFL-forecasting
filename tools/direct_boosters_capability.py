"""One finite CPU software capability invocation; never reads NFL inputs."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import email
import hashlib
import importlib.metadata as metadata
import io
import json
import os
from pathlib import Path
import resource
import selectors
import signal
import subprocess
import sys
import sysconfig
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

START = time.monotonic()
CPU_START = time.process_time()
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.tags import sys_tags
from packaging.utils import canonicalize_name, parse_wheel_filename
from packaging.version import Version, InvalidVersion

BASE_NAMES = ("numpy", "pandas", "scipy", "scikit-learn", "joblib", "threadpoolctl", "matplotlib", "six", "packaging")
POLICY_SHA = "311e661b7cacca1983a52c60cafacacbd31e3d82ec94482577519f4deb54a6f9"


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def versions():
    return {name: metadata.version(name) for name in BASE_NAMES}


def disk(paths):
    total=0
    for root in paths:
        for path in Path(root).rglob("*"):
            try:
                if path.is_file() and not path.is_symlink(): total+=path.stat().st_size
            except FileNotFoundError:
                continue  # pip may atomically move its private temporary files.
    return total


def storage_for(spec):
    from nfl_lab.operational_storage import OperationalStorage
    policy_path = ROOT / "config/operational-source-policy-v2.json"
    if sha(policy_path) != spec["storage_policy_sha256"]:
        raise ValueError("storage policy changed")
    if sha(ROOT / "nfl_lab/operational_storage.py") != spec["storage_code_sha256"]:
        raise ValueError("storage code changed")
    store = OperationalStorage(spec["metadata_cache"], json.loads(policy_path.read_text()))
    store.register_root(spec["output"])
    return store


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("redirect forbidden")


class Run:
    def __init__(self, spec, policy, phase):
        self.spec, self.policy = spec, policy
        self.output = Path(spec["output"])
        self.software = Path(spec["software"])
        self.environment = Path(policy["environment"])
        self.store = storage_for(spec)
        self.events, self.http, self.wheel_bytes, self.metadata_bytes, self.fits = 0, 0, 0, 0, 0
        self.http_started = 0
        self.installed = {}
        self.failed, self.installing, self.metadata_cache, self.verified_wheels = {}, set(), {}, {}
        self.phase = phase
        self.opener = urllib.request.build_opener(NoRedirect())
        self.tags = {tag: i for i, tag in enumerate(sys_tags())}
        self.check_base()

    def write(self, name, value):
        self.store.atomic_json(self.output / name, value)

    def event(self, event, **values):
        self.events += 1
        self.write(f"events/{self.phase}-{self.events:04d}.json", {"at": now(), "event": event, **values})

    def check_base(self):
        if versions() != self.spec["base_versions"]:
            raise ValueError("inherited base versions changed")

    def request(self, url, *, wheel=None):
        parsed = urllib.parse.urlsplit(url)
        if (parsed.scheme != "https" or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.port is not None or parsed.hostname != ("files.pythonhosted.org" if wheel else "pypi.org")):
            raise ValueError("unapproved public package URL")
        if not wheel and not (parsed.path.startswith("/pypi/") and parsed.path.endswith("/json")):
            raise ValueError("unapproved metadata endpoint")
        if not wheel and url in self.metadata_cache:
            return self.metadata_cache[url]
        if wheel and wheel["filename"] in self.verified_wheels:
            existing=self.verified_wheels[wheel["filename"]]
            if existing.stat().st_size!=wheel["size"] or sha(existing)!=wheel["sha256"]:
                raise ValueError("cached verified wheel changed")
            return existing
        if self.http >= 24:
            raise RuntimeError("HTTP budget consumed")
        self.http += 1
        self.event("HTTP_CONSUMED", transaction=self.http, url=url, kind="wheel" if wheel else "metadata")
        request = urllib.request.Request(url, headers={"User-Agent": "NFL-lab-software-capability/1", "Accept-Encoding": "identity"})
        body = io.BytesIO() if wheel is None else None
        target = None
        partial = None
        count, checksum = 0, hashlib.sha256()
        try:
            if wheel:
                if self.wheel_bytes + wheel["size"] > 512*1024*1024:
                    raise RuntimeError("advertised wheel budget exceeded")
                if disk([self.software, self.environment]) + wheel["size"] > 2*1024**3-32*1024**2:
                    raise RuntimeError("software disk reservation unavailable")
                partial = self.software / "wheels" / (wheel["filename"] + ".partial")
                partial.parent.mkdir(parents=True, exist_ok=True)
                target = partial.open("xb")
            self.http_started += 1
            with self.opener.open(request, timeout=25) as response:
                if response.status != 200 or response.geturl() != url:
                    raise ValueError("unexpected HTTP status/URL")
                if response.headers.get("Content-Encoding", "identity").lower().strip() != "identity":
                    raise ValueError("encoded HTTP body forbidden")
                length_header = response.headers.get("Content-Length")
                length = None
                if length_header is not None:
                    if not length_header or not all("0" <= c <= "9" for c in length_header):
                        raise ValueError("invalid HTTP Content-Length")
                    length = int(length_header)
                if response.headers.get("Transfer-Encoding") and length is not None:
                    raise ValueError("ambiguous HTTP transfer length")
                allowance = (min(wheel["size"],512*1024*1024-self.wheel_bytes) if wheel else
                             min(2*1024*1024,12*1024*1024-self.metadata_bytes))
                if allowance <= 0 or (length is not None and length > allowance):
                    raise RuntimeError("advertised HTTP body exceeds remaining allowance")
                if wheel and length is not None and length != wheel["size"]:
                    raise ValueError("wheel advertised HTTP length mismatch")
                while True:
                    if length is not None and count == length:
                        break
                    remaining = allowance-count
                    if remaining <= 0:
                        # Never consume an extra byte to probe EOF at a cap.
                        raise RuntimeError("HTTP body reached bound without declared completion")
                    chunk = response.read(min(256*1024,remaining,length-count if length is not None else remaining))
                    if not chunk:
                        if length is not None and count != length:
                            raise ValueError("HTTP body shorter than declared length")
                        break
                    count += len(chunk); checksum.update(chunk)
                    if wheel:
                        self.wheel_bytes += len(chunk)
                        target.write(chunk)
                    else:
                        self.metadata_bytes += len(chunk)
                        body.write(chunk)
            if target:
                target.close(); target = None
                if count != wheel["size"] or checksum.hexdigest() != wheel["sha256"]:
                    raise ValueError("downloaded wheel size/SHA256 mismatch")
                destination = partial.with_suffix("")
                if destination.exists(): raise ValueError("refuse to overwrite retained wheel")
                partial.rename(destination)
                self.verified_wheels[wheel["filename"]]=destination
                self.event("WHEEL_VERIFIED", path=str(destination), bytes=count, sha256=checksum.hexdigest())
                return destination
            encoded = body.getvalue()
            self.store.write_bytes(self.output / f"metadata/{self.http:02d}-{checksum.hexdigest()}.json", encoded)
            decoded=json.loads(encoded)
            self.metadata_cache[url]=decoded
            return decoded
        except BaseException as error:
            if not wheel and body is not None and body.tell():
                self.store.write_bytes(self.output / f"metadata/{self.http:02d}-partial.bin", body.getvalue())
            self.event("HTTP_FAILED", transaction=self.http, bytes=count, error_type=type(error).__name__)
            raise
        finally:
            if target:
                target.close()

    def choose(self, name, requirement=None):
        name = canonicalize_name(name)
        if any(x in name for x in ("nvidia", "cuda", "nccl", "cupy", "tensorflow", "torch")):
            raise ValueError("GPU/large unrelated dependency forbidden")
        data = self.request(f"https://pypi.org/pypi/{name}/json")
        choices = []
        for version, files in data["releases"].items():
            try:
                parsed_version = Version(version)
            except InvalidVersion:
                continue
            if parsed_version.is_prerelease or parsed_version.is_devrelease or (requirement and parsed_version not in requirement.specifier):
                continue
            for item in files:
                if item.get("yanked") or item.get("packagetype") != "bdist_wheel":
                    continue
                if item.get("requires_python") and Version(".".join(map(str, sys.version_info[:3]))) not in SpecifierSet(item["requires_python"]):
                    continue
                try:
                    wheel_name, wheel_version, _, tags = parse_wheel_filename(item["filename"])
                except ValueError:
                    continue
                ranks = [self.tags[t] for t in tags if t in self.tags]
                if ranks and canonicalize_name(wheel_name) == name and wheel_version == parsed_version:
                    choices.append((parsed_version, -min(ranks), item["filename"], item))
        if not choices:
            raise ValueError("no compatible non-yanked wheel")
        version, _, _, item = max(choices, key=lambda x: x[:3])
        if str(data["info"]["version"]) != str(version):
            data = self.request(f"https://pypi.org/pypi/{name}/{version}/json")
        pinned = {"name": name, "version": str(version), "filename": item["filename"],
            "url": item["url"], "size": item["size"], "sha256": item["digests"]["sha256"],
            "requires_python": item.get("requires_python"), "license": data["info"].get("license"),
            "license_expression": data["info"].get("license_expression"),
            "license_classifiers": [x for x in data["info"].get("classifiers", []) if x.startswith("License ::")]}
        if (type(pinned["size"]) is not int or pinned["size"] <= 0 or len(pinned["sha256"]) != 64
                or any(c not in "0123456789abcdef" for c in pinned["sha256"])):
            raise ValueError("invalid advertised wheel size/hash")
        # The exact public selection is immutable before any wheel request.
        self.write(f"pins/{name}-{version}.json", pinned)
        return pinned

    def install(self, name, requirement=None):
        name=canonicalize_name(name)
        if name in self.failed:
            raise RuntimeError("previous package capability failure retained; no retry: "+name)
        if name in self.installing:
            raise ValueError("cyclic package dependency")
        self.installing.add(name)
        try:
            return self._install(name,requirement)
        except Exception as error:
            # Inherited-version conflicts are constraint-specific; never modify
            # that base, but a different library may accept its current version.
            try: metadata.version(name)
            except metadata.PackageNotFoundError:
                self.failed[name]={"error_type":type(error).__name__,"error":str(error)[:300]}
            raise
        finally:
            self.installing.discard(name)

    def _install(self, name, requirement=None):
        name = canonicalize_name(name)
        if name in self.installed:
            if requirement and Version(self.installed[name]["version"]) not in requirement.specifier:
                raise ValueError("already installed dependency incompatible")
            return self.installed[name]
        try:
            inherited = metadata.version(name)
        except metadata.PackageNotFoundError:
            inherited = None
        if inherited is not None:
            if requirement and Version(inherited) not in requirement.specifier:
                raise ValueError("required dependency would upgrade frozen base")
            return {"name": name, "version": inherited, "inherited": True}
        pinned = self.choose(name, requirement)
        path = self.request(pinned["url"], wheel=pinned)
        with zipfile.ZipFile(path) as archive:
            names = [n for n in archive.namelist() if n.endswith(".dist-info/METADATA")]
            if len(names) != 1:
                raise ValueError("wheel METADATA identity unavailable")
            if archive.getinfo(names[0]).file_size > 2*1024*1024:
                raise ValueError("wheel METADATA exceeds bounded metadata size")
            info = email.message_from_bytes(archive.read(names[0]))
            if canonicalize_name(info["Name"]) != name or Version(info["Version"]) != Version(pinned["version"]):
                raise ValueError("wheel package identity mismatch")
            dependencies = info.get_all("Requires-Dist", [])
            uncompressed = sum(i.file_size for i in archive.infolist())
            if disk([self.software, self.environment]) + 2*uncompressed + 32*1024**2 > 2*1024**3:
                raise RuntimeError("wheel unpack/install peak exceeds software disk cap")
        self.write(f"wheel-metadata/{name}-{pinned['version']}.json", {
            "name": info["Name"], "version": info["Version"], "requires_dist": dependencies,
            "requires_python": info.get("Requires-Python"), "license": info.get("License"),
            "license_expression": info.get("License-Expression"), "uncompressed_bytes": uncompressed,
            "source_wheel_sha256": pinned["sha256"]})
        for raw in dependencies:
            dependency = Requirement(raw)
            if dependency.marker is not None and not dependency.marker.evaluate({"extra": ""}):
                continue
            if dependency.url or dependency.extras:
                raise ValueError("unregistered direct/extra dependency")
            self.install(dependency.name, dependency)
        command = [str(self.environment / "bin/python"), "-m", "pip", "--isolated", "install",
                   "--no-index", "--no-deps", "--no-cache-dir", "--no-compile", "--disable-pip-version-check", str(path)]
        self.event("LOCAL_INSTALL_STARTED", name=name, command=command)
        completed = subprocess.run(command, capture_output=True, timeout=45)
        if len(completed.stdout)+len(completed.stderr) > 1024*1024:
            raise ValueError("installation log bound exceeded")
        self.store.write_bytes(self.output / f"install/{name}.log", completed.stdout+completed.stderr)
        if completed.returncode:
            raise RuntimeError(f"local install failed: {name}")
        self.installed[name] = {**pinned, "inherited": False, "wheel_path": str(path)}
        self.check_base()
        return self.installed[name]

    def smoke(self, library):
        import numpy as np
        from threadpoolctl import threadpool_limits
        if library == "xgboost-cpu":
            import xgboost as module
        elif library == "lightgbm":
            import lightgbm as module
        else:
            import catboost as module
        x = np.column_stack([np.linspace(-2, 2, 64), np.sin(np.arange(64))])
        for product in ("count_mean", "signed_median", "binary_probability"):
            if self.fits >= 9:
                raise RuntimeError("fictional fit budget consumed")
            y = np.arange(64)%5 if product == "count_mean" else (5*x[:, 0] if product == "signed_median" else (x[:, 0]>0).astype(int))
            if library == "xgboost-cpu":
                params = dict(n_estimators=8,max_depth=2,n_jobs=2,random_state=1751,tree_method="hist",device="cpu",verbosity=0)
                if product == "count_mean": params.update(objective="count:poisson")
                elif product == "signed_median": params.update(objective="reg:quantileerror",quantile_alpha=0.5)
                else: params.update(objective="binary:logistic",eval_metric="logloss")
                cls = module.XGBClassifier if product == "binary_probability" else module.XGBRegressor
            elif library == "lightgbm":
                params = dict(n_estimators=8,max_depth=2,num_leaves=4,n_jobs=2,random_state=1751,
                              verbosity=-1,force_col_wise=True,min_child_samples=2,deterministic=True)
                params.update(objective={"count_mean":"poisson","signed_median":"quantile","binary_probability":"binary"}[product])
                if product == "signed_median": params.update(alpha=0.5)
                cls = module.LGBMClassifier if product == "binary_probability" else module.LGBMRegressor
            else:
                params = dict(iterations=8,depth=2,thread_count=2,random_seed=1751,task_type="CPU",
                              verbose=False,allow_writing_files=False,
                              loss_function={"count_mean":"Poisson","signed_median":"Quantile:alpha=0.5","binary_probability":"Logloss"}[product])
                cls = module.CatBoostClassifier if product == "binary_probability" else module.CatBoostRegressor
            self.fits += 1
            self.event("FICTIONAL_FIT_CONSUMED", library=library, product=product, attempt=self.fits, parameters=params)
            began, cpu = time.monotonic(), time.process_time()
            try:
                with threadpool_limits(limits=2):
                    model = cls(**params); model.fit(x, y)
                    if product == "binary_probability": prediction = model.predict_proba(x)[:, 1]
                    elif library == "catboost" and product == "count_mean": prediction = model.predict(x,prediction_type="Exponent")
                    else: prediction = model.predict(x)
                if prediction.shape != (64,) or not np.isfinite(prediction).all():
                    raise ValueError("prediction shape/finite contract failed")
                if product == "count_mean" and (prediction<0).any(): raise ValueError("negative count mean")
                if product == "binary_probability" and ((prediction<0)|(prediction>1)).any(): raise ValueError("probability outside support")
                if product == "signed_median" and not ((prediction<0).any() and (prediction>0).any()): raise ValueError("signed fictional support not exercised")
                result = {"state":"PASSED","rows":64,"prediction_min":float(prediction.min()),"prediction_max":float(prediction.max())}
            except Exception as error:
                result = {"state":"FAILED","error_type":type(error).__name__,"error":str(error)[:300]}
            self.write(f"smoke/{library}-{product}.json", {"library":library,"version":module.__version__,
                "product":product,"parameters":params,"wall_seconds":time.monotonic()-began,
                "CPU_seconds":time.process_time()-cpu,**result})


def child(spec, policy):
    run = Run(spec, policy, "install")
    result = {}
    for name in policy["packages"]:
        try:
            result[name] = {"state":"INSTALLED","package":run.install(name)}
        except Exception as error:
            result[name] = {"state":"UNAVAILABLE","error_type":type(error).__name__,"error":str(error)[:300]}
    run.check_base()
    # Imports/fits must occur in the new environment, not the installer parent.
    manifest = {"packages":result,"installed":run.installed,"failed_packages":run.failed,"HTTP_transactions_started":run.http_started,"HTTP_transaction_budget_charges":run.http,
        "wheel_body_bytes":run.wheel_bytes,"metadata_body_bytes":run.metadata_bytes,"fictional_fits":run.fits}
    run.write("installation.json", manifest)
    return manifest


def smoke_child(spec, policy):
    run = Run(spec, policy, "smoke")
    if Path(sys.prefix).absolute() != run.environment.absolute():
        raise ValueError("fictional fits require the separate environment")
    manifest = json.loads((Path(spec["output"])/"installation.json").read_text())
    for name, status in manifest["packages"].items():
        if status["state"] != "INSTALLED": continue
        try:
            run.smoke(name)
        except Exception as error:
            run.write(f"smoke/{name}-import-failed.json", {"state":"FAILED","error_type":type(error).__name__,"error":str(error)[:300]})
    run.check_base()
    run.write("smoke-completion.json", {"fictional_fit_attempts":run.fits,"base_versions":versions(),
        "executable":sys.executable,"prefix":sys.prefix,"python":sys.version,"installed_versions":{
            name:metadata.version(name) for name in manifest["installed"]},
        "NFL_rows_models_outcomes_scores":0,"evidence":"fictional software capability only"})


def group_cpu(pgid):
    ticks = os.sysconf("SC_CLK_TCK")
    total = 0.0
    for path in Path("/proc").glob("[0-9]*/stat"):
        try:
            v = path.read_text().rsplit(")", 1)[1].split()
            if int(v[2]) == pgid: total += sum(int(v[i]) for i in (11,12,13,14))/ticks
        except (OSError,ValueError,IndexError): pass
    return total


def supervise(spec, policy, freeze_path, freeze_sha):
    from nfl_lab.cdf_campaign import proc_usage
    store = storage_for(spec)
    output, environment, software = Path(spec["output"]), Path(policy["environment"]), Path(spec["software"])
    if (output/"CAPABILITY_CONSUMED.json").exists() or environment.exists() or software.exists():
        raise ValueError("one invocation only; existing environment/software/consumption retained")
    store.atomic_json(output/"CAPABILITY_CONSUMED.json", {"at":now(),"freeze_sha256":freeze_sha,"policy_sha256":POLICY_SHA,"invocation":1})
    software.mkdir(parents=True)
    env = dict(os.environ)
    env.update({name:"2" for name in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS","NUMEXPR_NUM_THREADS","OMP_THREAD_LIMIT")})
    env.update(PYTHONDONTWRITEBYTECODE="1",TMPDIR=str(software/"tmp"),MPLCONFIGDIR=str(software/"mpl"),MPLBACKEND="Agg")
    Path(env["TMPDIR"]).mkdir()
    # The supervisor starts before any network/import/install work and stays out
    # of the worker's native calls. All descendants inherit the worker group.
    peak_rss, peak_cpu, reason = 0, 0.0, None
    logs = bytearray()
    for mode, executable in (("prepare",sys.executable),("install",sys.executable),("smoke",str(environment/"bin/python"))):
        command = [executable,str(Path(__file__).resolve()),"--freeze",str(freeze_path),"--freeze-sha256",freeze_sha,"--worker",mode]
        process = subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,env=env)
        selector = selectors.DefaultSelector(); selector.register(process.stdout,selectors.EVENT_READ)
        while process.poll() is None or selector.get_map():
            for key,_ in selector.select(timeout=0.05):
                chunk = os.read(key.fileobj.fileno(),65536)
                if chunk: logs.extend(chunk)
                else: selector.unregister(key.fileobj)
            rss,_ = proc_usage(os.getpgrp())
            peak_rss = max(peak_rss,rss)
            # The group already includes this process and its reaped children.
            cpu = group_cpu(os.getpgrp())
            peak_cpu = max(peak_cpu,cpu)
            if time.monotonic()-START >= 238: reason="WALL_LIMIT"
            elif cpu >= 178: reason="CPU_LIMIT"
            elif peak_rss >= 1024**3-16*1024**2: reason="RSS_LIMIT"
            elif disk([software,environment]) > 2*1024**3-16*1024**2: reason="SOFTWARE_DISK_LIMIT"
            elif len(logs)>1024*1024: reason="LOG_LIMIT"
            if reason:
                try: os.killpg(os.getpgrp(),signal.SIGKILL)
                except ProcessLookupError: pass
                process.wait(); break
        selector.close()
        if process.wait() != 0:
            reason = reason or mode.upper()+"_PROCESS_FAILED"
        if reason: break
    store.write_bytes(output/"process.log", bytes(logs[:1024*1024]))
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    completion = {"state":"FAILED" if reason else "COMPLETED","limit_or_error":reason,
        "generated_at":now(),"wall_seconds":time.monotonic()-START,
        "CPU_seconds":time.process_time()+usage.ru_utime+usage.ru_stime,
        "peak_sampled_combined_RSS_bytes":peak_rss,"software_environment_and_wheel_bytes":disk([software,environment]),
        "base_versions":versions(),"base_environment_unchanged":versions()==spec["base_versions"],
        "actual_NFL_rows_models_fits_predictions_outcomes_scores":0,"threads":2}
    store.atomic_json(output/"completion.json",completion)
    print(json.dumps(completion,sort_keys=True))
    if reason: raise SystemExit(1)


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--freeze",required=True);parser.add_argument("--freeze-sha256",required=True)
    parser.add_argument("--worker",choices=("prepare","install","smoke"));args=parser.parse_args()
    freeze=Path(args.freeze)
    if sha(freeze)!=args.freeze_sha256: raise ValueError("execution freeze changed")
    spec=json.loads(freeze.read_text())
    if sha(__file__)!=spec["runner_sha256"] or sha(ROOT/"config/direct-boosters-capability-v1.json")!=POLICY_SHA:
        raise ValueError("runner/policy changed")
    policy=json.loads((ROOT/"config/direct-boosters-capability-v1.json").read_text())
    if versions()!=spec["base_versions"]: raise ValueError("base versions changed")
    if args.worker=="prepare":
        environment=Path(policy["environment"])
        subprocess.run([sys.executable,"-m","venv","--system-site-packages","--without-pip",str(environment)],check=True,timeout=15)
        purelib=environment/"lib"/f"python{sys.version_info.major}.{sys.version_info.minor}"/"site-packages"
        (purelib/"frozen-base.pth").write_text(spec["base_purelib"]+"\n")
    elif args.worker=="install": child(spec,policy)
    elif args.worker=="smoke": smoke_child(spec,policy)
    else: supervise(spec,policy,freeze,args.freeze_sha256)


if __name__=="__main__": main()
