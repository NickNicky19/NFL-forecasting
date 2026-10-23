"""Opt-in, scoped consumer of an exact frozen scored-row manifest.

This runner adds descriptive groups only. It streams a single target-method,
writes deterministic compressed aggregates through the unchanged shared quota,
and never loads a learner, forecast, feature source or new outcome partition.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.metadata
import io
import json
from pathlib import Path, PurePosixPath
import platform
import re
import resource
import socket
import stat
import sys
import time
from unittest.mock import patch

import pandas as pd
from threadpoolctl import threadpool_limits

from .cdf_engine import KEYS, validate_category
from .frozen_subgroups import (DIMENSIONS, EXPOSURE, LAW_FIELDS, METHODS, NUMERIC_FIELDS,
    REGISTRATION_SHA256, YEARS, build_frozen_subgroups)
from .models import TARGETS
from .operational_storage import OperationalStorage, _no_symlinks, _stamp
from .owned_reference_batch import validate_owned_references
from .reference_runtime import _deadline, _no_fits

VERSION = "source-matched-frozen-subgroup-run-v1"
PARENT_POLICY_SHA256 = "7c834dff5515eab9384218a3144026ffe52933f79ffa70437a4eb9e1ae75324f"
PARENT_EXECUTION_FREEZE_SHA256 = "332a07b5aaeb9abbaf7d9147cad816325711753379d8cc76fe93889746693736"
PACKAGES = ("numpy", "pandas", "scipy", "scikit-learn", "pyarrow", "joblib", "threadpoolctl", "requests", "urllib3")
LIMITS = {"invocations": 1, "automatic_retries": 0, "max_wall_seconds": 300, "max_CPU_seconds": 450,
    "max_RSS_bytes": 512 * 1024**2, "threads": 1, "max_shared_unique_file_bytes": 512 * 1024**2}
READ_COLUMNS = tuple(dict.fromkeys([*KEYS, *DIMENSIONS, *NUMERIC_FIELDS, "year", "target", "method",
    "participation_state", "primary_role", "cutoff_utc", "kickoff_utc", "season_type"]))


def _sha(body):
    return hashlib.sha256(body).hexdigest()


def _hash(value):
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError("exact lowercase SHA256 required")
    return value


def _absolute(value):
    if not isinstance(value, (str, Path)):
        raise ValueError("absolute canonical path required")
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts or path.absolute() != path.resolve():
        raise ValueError("absolute canonical path required")
    _no_symlinks(path)
    return path


def _relative(root, value):
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError("safe canonical manifest-relative path required")
    name = PurePosixPath(value)
    if name.is_absolute() or name.as_posix() != value or any(p in {".", ".."} for p in name.parts):
        raise ValueError("safe canonical manifest-relative path required")
    path = _absolute(root / value)
    if root not in path.parents:
        raise ValueError("manifest path escaped parent output")
    return path


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _decode(body):
    def invalid(value):
        raise ValueError("nonfinite JSON literal: " + value)
    return json.loads(body, object_pairs_hook=_pairs, parse_constant=invalid)


def _pin(binding, *, read=False):
    if not isinstance(binding, dict) or set(binding) - {"path", "sha256", "bytes", "inode", "mode"} or not {"path", "sha256"} <= set(binding):
        raise ValueError("exact frozen file binding required")
    path, expected = _absolute(binding["path"]), _hash(binding["sha256"])
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode):
        raise ValueError("frozen file must be regular")
    if "bytes" in binding and binding["bytes"] != before.st_size:
        raise ValueError("frozen file size differs")
    if "inode" in binding and binding["inode"] != [before.st_dev, before.st_ino]:
        raise ValueError("frozen file inode differs")
    if "mode" in binding:
        mode = int(binding["mode"], 8)
        if mode != (stat.S_IMODE(before.st_mode) if mode <= 0o7777 else before.st_mode):
            raise ValueError("frozen file mode differs")
    if read:
        body = path.read_bytes()
        digest = _sha(body)
    else:
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if digest != expected or _stamp(path.lstat()) != _stamp(before):
        raise ValueError("frozen file content changed")
    return _decode(body) if read else path


def _same_pointer(left, right):
    return left["path"] == right["path"] and left["sha256"] == right["sha256"]


def _environment(expected):
    if not isinstance(expected, dict) or expected.get("threads") != 1 or expected.get("python") not in {sys.version, platform.python_version()}:
        raise ValueError("frozen one-thread Python environment required")
    if Path(expected["executable"]).resolve() != Path(sys.executable).resolve() or set(expected["packages"]) != set(PACKAGES):
        raise ValueError("exact frozen interpreter and nine dependency versions required")
    for name in PACKAGES:
        if importlib.metadata.version(name) != expected["packages"][name]:
            raise ValueError("frozen dependency differs: " + name)


def _codes(expected):
    root = Path(__file__).resolve().parent.parent
    names = {str(p.relative_to(root)) for p in (root / "nfl_lab").rglob("*.py")}
    if not isinstance(expected, dict) or set(expected) != names:
        raise ValueError("exact full nfl_lab Python code inventory required")
    for name, digest in expected.items():
        _pin({"path": str(root / name), "sha256": digest})


class _Budget:
    def __init__(self):
        self.start, self.cpu = time.monotonic(), time.process_time()

    def usage(self):
        return {"wall_seconds": time.monotonic() - self.start, "CPU_seconds": time.process_time() - self.cpu,
            "max_RSS_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
            "RSS_scope": "single-process high water; root supervisor measures the full invocation",
            "fits_predictions_HTTP_new_labels_search": 0}

    def check(self):
        usage = self.usage()
        if usage["wall_seconds"] > LIMITS["max_wall_seconds"] or usage["CPU_seconds"] > LIMITS["max_CPU_seconds"]:
            raise RuntimeError("fixed subgroup resource budget exhausted")
        if usage["max_RSS_bytes"] > LIMITS["max_RSS_bytes"]:
            raise RuntimeError("fixed subgroup RSS budget exhausted")


def _write_gzip(storage, path, value):
    """Stream JSON into gzip RAM, never retain an uncompressed JSON copy."""
    buffer = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buffer, mtime=0) as zipped:
        with io.TextIOWrapper(zipped, encoding="utf-8", newline="\n") as text:
            json.dump(value, text, sort_keys=True, separators=(",", ":"), allow_nan=False)
            text.write("\n")
    body = buffer.getvalue()
    storage.write_bytes(path, body)
    return {"sha256": _sha(body), "bytes": len(body)}


def _slot_status(slot):
    return {key: slot[key] for key in ("year", "target", "method", "state", "kind", "alias_method", "rows") if key in slot} | {"failure_detail_available": bool(slot.get("reason"))}


def _schema_columns(path):
    # Footer/schema inspection only, after exact owned-reference validation.
    import pyarrow.parquet as pq
    return set(pq.ParquetFile(path).schema_arrow.names)


def _manifest(manifest, spec):
    if manifest.get("state") != "SCORED_ROWS_FROZEN" or manifest.get("registration_sha256") != spec["parent_execution"]["sha256"]:
        raise ValueError("parent scored freeze identity differs")
    clocks = [manifest[key] for key in ("forecast_freeze_sha256", "parent_forecast_freeze_sha256") if key in manifest]
    if not clocks or any(value != spec["forecast_freeze_sha256"] for value in clocks):
        raise ValueError("parent forecast freeze binding differs")
    slots = manifest.get("slots")
    expected = {(year, target, method) for year in YEARS for target in TARGETS for method in METHODS}
    if not isinstance(slots, list) or len(slots) != 216:
        raise ValueError("all 216 parent annual statuses required")
    by_key = {}
    for slot in slots:
        key = (slot["year"], slot["target"], slot["method"])
        if key not in expected or key in by_key or not isinstance(slot["state"], str) or re.fullmatch(r"[A-Z][A-Z0-9_]{0,79}", slot["state"]) is None:
            raise ValueError("invalid or duplicate parent annual status")
        if key[1] == "fantasy_ppr" and not slot["state"].startswith("BLOCKED"):
            raise ValueError("all eighteen exact PPR annual slots must remain blocked")
        if "kind" in slot and slot["kind"] not in {"blocked", "alias", "reference", "model"}:
            raise ValueError("unregistered parent slot kind")
        if "alias_method" in slot and slot["alias_method"] is not None and slot["alias_method"] not in METHODS:
            raise ValueError("unregistered parent alias method")
        if "rows" in slot and (type(slot["rows"]) is not int or slot["rows"] < 0):
            raise ValueError("invalid parent offered-row count")
        if slot["state"] == "COMPLETED" and (type(slot.get("rows")) is not int or slot["rows"] <= 0):
            raise ValueError("completed parent slot requires a positive frozen row count")
        by_key[key] = slot
    root = _absolute(spec["parent_output"])
    bindings = manifest.get("bindings")
    if not isinstance(bindings, dict):
        raise ValueError("parent scored reference bindings required")
    for relative, digest in bindings.items():
        _relative(root, relative)
        _hash(digest)
    files = manifest.get("scored_files")
    if not isinstance(files, list) or len(set(files)) != len(files):
        raise ValueError("unique parent scored files required")
    cells = {}
    for relative in files:
        _relative(root, relative)
        parts = PurePosixPath(relative).parts
        if len(parts) != 6 or parts[:2] != ("private", "scored") or parts[2] not in {str(y) for y in YEARS} or parts[3] not in TARGETS or parts[4] not in METHODS or parts[5] not in {"rows.parquet", "role-prior.parquet"}:
            raise ValueError("unregistered scored-file layout")
        key = (int(parts[2]), parts[3], parts[4])
        if relative not in bindings or key[1] == "fantasy_ppr" or parts[5] == "role-prior.parquet" and key[2] != "leaf_cdf":
            raise ValueError("scored file lacks exact binding or is forbidden")
        if parts[5] == "rows.parquet":
            if by_key[key]["state"] != "COMPLETED":
                raise ValueError("only completed annual rows may be consumed")
            cells[key] = relative
    for key, slot in by_key.items():
        if (slot["state"] == "COMPLETED") != (key in cells):
            raise ValueError("completed annual status and scored files differ")
    return slots, cells, {str(_relative(root, relative)): bindings[relative] for relative in files}


def _preflight(spec):
    required = {"registration_id", "subgroup_plan", "parent_policy", "parent_execution", "parent_kind", "parent_output", "scored_manifest", "forecast_freeze_sha256",
        "source_policy", "source_manifest", "category_contract", "cache", "output", "code_sha256", "environment", "budgets"}
    if not isinstance(spec, dict) or set(spec) != required or spec["registration_id"] != VERSION or spec["budgets"] != LIMITS:
        raise ValueError("exact fixed subgroup execution schema and budgets required")
    if spec["subgroup_plan"]["sha256"] != REGISTRATION_SHA256 or spec["parent_policy"]["sha256"] != PARENT_POLICY_SHA256:
        raise ValueError("predeclared subgroup and parent policies required")
    plan, parent = _pin(spec["subgroup_plan"], read=True), _pin(spec["parent_policy"], read=True)
    if plan["parent_policy_sha256"] != PARENT_POLICY_SHA256 or plan["parent_actual_freeze_sha256"] != PARENT_EXECUTION_FREEZE_SHA256:
        raise ValueError("subgroup registration parent bindings differ")
    for field in ("source_policy", "source_manifest", "category_contract"):
        if not _same_pointer(spec[field], parent[field]):
            raise ValueError("parent source/category binding changed: " + field)
    if spec["cache"] != parent["cache"]:
        raise ValueError("parent shared quota cache changed")
    execution = _pin(spec["parent_execution"], read=True)
    if spec["parent_kind"] == "benchmark":
        if not _same_pointer(spec["parent_policy"], spec["parent_execution"]):
            raise ValueError("original parent execution must be its exact policy")
    elif spec["parent_kind"] == "report_recovery":
        if not _same_pointer(execution["parent_config"], spec["parent_policy"]) or execution["parent_forecast_freeze"]["sha256"] != spec["forecast_freeze_sha256"]:
            raise ValueError("recovery parent policy/forecast binding differs")
    else:
        raise ValueError("unsupported parent kind")
    if spec["parent_output"] != execution["output"] or _absolute(spec["scored_manifest"]["path"]) != _absolute(spec["parent_output"]) / "scored-freeze.json":
        raise ValueError("scored manifest must belong to the frozen parent output")
    _hash(spec["forecast_freeze_sha256"])
    _pin(spec["source_manifest"])
    policy, contract = _pin(spec["source_policy"], read=True), _pin(spec["category_contract"], read=True)
    categories = contract.get("categories")
    if not isinstance(categories, dict) or set(categories) != set(TARGETS) or categories["fantasy_ppr"].get("state") == "READY":
        raise ValueError("all twelve categories including blocked exact PPR required")
    for target in TARGETS:
        if target != "fantasy_ppr":
            validate_category({**categories[target], "target": target})
    if policy["storage"]["limit_bytes"] != LIMITS["max_shared_unique_file_bytes"] or policy["namespaces"]["private_retention_bytes"] != LIMITS["max_shared_unique_file_bytes"]:
        raise ValueError("unchanged shared 512 MiB quota required")
    _environment(spec["environment"])
    _codes(spec["code_sha256"])
    output = _absolute(spec["output"])
    for input_root in (_absolute(spec["cache"]), _absolute(spec["parent_output"]), _absolute(parent["output"])):
        if output == input_root or input_root in output.parents or output in input_root.parents:
            raise ValueError("new output must be separate from every input namespace")
    return policy, categories, output


def run_subgroups(execution_config, config_sha256):
    """Execute one separately frozen, scoped aggregate-only invocation."""
    budget = _Budget()
    spec = _pin({"path": str(_absolute(execution_config)), "sha256": config_sha256}, read=True)
    policy, categories, output = _preflight(spec)
    budget.check()
    storage = OperationalStorage(spec["cache"], policy)
    with storage._locked():
        storage._refresh()
        storage._scan()
        if output.exists():
            raise RuntimeError("subgroup output already exists; invocation cannot retry")
        storage.register_root(output)
        storage.atomic_json(output / "SUBGROUPS_CONSUMED.json", {"version": VERSION, "config_sha256": config_sha256,
            "generated_at": datetime.now(timezone.utc).isoformat(), "invocations": 1,
            "fits_predictions_HTTP_new_labels_search": 0})
        succeeded = False
        try:
            with _deadline(max(.001, LIMITS["max_wall_seconds"] - budget.usage()["wall_seconds"])), threadpool_limits(limits=1), _no_fits(), ExitStack() as guards:
                def forbidden(*args, **kwargs):
                    raise AssertionError("subgroup consumer forbids network")
                for obj, name in ((socket.socket, "connect"), (socket.socket, "connect_ex"), (socket, "getaddrinfo")):
                    guards.enter_context(patch.object(obj, name, forbidden))
                # Authenticate the manifest as an owned immutable alias before
                # decoding it; then verify its exact scored references in batch.
                manifest_path = spec["scored_manifest"]["path"]
                _, initial_validation = validate_owned_references(storage, {manifest_path: spec["scored_manifest"]["sha256"]})
                manifest = _pin(spec["scored_manifest"], read=True)
                annual, cells, bindings = _manifest(manifest, spec)
                annual_by_key = {(s["year"], s["target"], s["method"]): s for s in annual}
                bindings[manifest_path] = spec["scored_manifest"]["sha256"]
                bindings[spec["source_manifest"]["path"]] = spec["source_manifest"]["sha256"]
                _, validation = validate_owned_references(storage, bindings)
                budget.check()
                _write_gzip(storage, output / "private/input-validation.json.gz", {"config_sha256": config_sha256,
                    "scored_manifest": spec["scored_manifest"], "source_manifest": spec["source_manifest"],
                    "category_contract": spec["category_contract"], "parent_execution": spec["parent_execution"],
                    "code_sha256": spec["code_sha256"], "environment": spec["environment"],
                    "initial_manifest_validation": initial_validation, "owned_validation": validation})
                pooled = [{"target": target, "method": method, "state": "BLOCKED_EXACT_PPR" if target == "fantasy_ppr" else "UNRUN"} for target in TARGETS for method in METHODS]
                header = {"version": VERSION, "config_sha256": config_sha256, "subgroup_plan_sha256": REGISTRATION_SHA256,
                    "parent_scored_manifest_sha256": spec["scored_manifest"]["sha256"], "parent_execution_sha256": spec["parent_execution"]["sha256"],
                    "annual_slots": [_slot_status(slot) for slot in annual], "planned_pooled_slots": 72,
                    "supported_pooled_slots": 66, "blocked_exact_PPR_pooled_slots": 6, "exposure": EXPOSURE,
                    "regular_season_basis": "Pinned original accepted source and frozen parent pipeline; optional season_type checked when retained; week1..18 is only a consistency guard",
                    "promotion": "NONE", "new_fits_predictions_labels_HTTP": 0}
                _write_gzip(storage, output / "public/plan.json.gz", {**header, "pooled_slots": pooled})
                private_files = []
                for slot in pooled:
                    budget.check()
                    target, method = slot["target"], slot["method"]
                    if target == "fantasy_ppr":
                        continue
                    selected = [(year, cells[(year, target, method)]) for year in YEARS if (year, target, method) in cells]
                    slot["included_years"] = [year for year, _ in selected]
                    slot["absent_years"] = [year for year in YEARS if year not in slot["included_years"]]
                    if not selected:
                        slot["state"] = "MISSING_OR_UNRUN"
                        continue
                    frames = []
                    type_presence = []
                    slot["season_type_metadata"] = {}
                    for year, relative in selected:
                        path = _relative(_absolute(spec["parent_output"]), relative)
                        schema = _schema_columns(path)
                        has_type = "season_type" in schema
                        if set(READ_COLUMNS) - {"season_type"} - schema:
                            raise ValueError("required scored columns absent from frozen schema")
                        columns = [name for name in READ_COLUMNS if name != "season_type" or has_type]
                        filters = [("season", "==", year), ("year", "==", year)]
                        if has_type:
                            filters.append(("season_type", "==", "REG"))
                        frame = pd.read_parquet(path, columns=columns, filters=filters)
                        if frame.empty or not frame.season.eq(year).all() or not frame.year.eq(year).all() or not frame.target.eq(target).all() or not frame.method.eq(method).all() or has_type and not frame.season_type.eq("REG").all():
                            raise ValueError("scored annual identity/type differs from frozen slot")
                        annual_slot = annual_by_key[(year, target, method)]
                        if len(frame) != annual_slot["rows"]:
                            raise ValueError("scored annual offered-row count differs")
                        type_presence.append(has_type)
                        slot["season_type_metadata"][str(year)] = "present_validated_REG" if has_type else "absent; original source REG provenance retained"
                        frames.append(frame)
                    if not all(type_presence):
                        # Do not manufacture REG cells for missing metadata.
                        # Any retained values were checked above. The grouping
                        # helper does not need this optional metadata column.
                        for part in frames:
                            part.drop(columns="season_type", errors="ignore", inplace=True)
                    rows = pd.concat(frames, ignore_index=True)
                    del frames, frame
                    public, private = build_frozen_subgroups(rows, {**categories[target], "target": target})
                    del rows
                    budget.check()
                    public_path = f"public/groups/{target}/{method}.json.gz"
                    private_path = f"private/players/{target}/{method}.json.gz"
                    slot["public"] = {"path": public_path, **_write_gzip(storage, output / public_path, public)}
                    del public
                    private_files.append({"target": target, "method": method, "path": private_path,
                        **_write_gzip(storage, output / private_path, private)})
                    del private
                    slot["state"] = "COMPLETED" if len(selected) == 3 else "PARTIAL_COMPLETED_YEARS"
                budget.check()
                for field in ("subgroup_plan", "source_policy", "source_manifest", "category_contract", "parent_policy", "parent_execution"):
                    _pin(spec[field])
                _pin({"path": str(_absolute(execution_config)), "sha256": config_sha256})
                _codes(spec["code_sha256"])
                _, final_validation = validate_owned_references(storage, bindings)
                _write_gzip(storage, output / "private/final-input-validation.json.gz", final_validation)
                _write_gzip(storage, output / "private/player-files.json.gz", {"files": private_files})
                budget.check()
                result = {**header, "pooled_slots": pooled, "usage": budget.usage()}
                _write_gzip(storage, output / "public/report.json.gz", result)
                budget.check()
                succeeded = True
                return result
        except BaseException as error:
            storage.atomic_json(output / "SUBGROUPS_FAILURE.json", {"exception": type(error).__name__, "usage": budget.usage(),
                "automatic_retry": False, "partial_outputs_preserved": True})
            raise
        finally:
            storage.atomic_json(output / "SUBGROUPS_FINISHED.json", {"state": "COMPLETED" if succeeded else "FAILED", "usage": budget.usage()})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--config-sha256", required=True)
    args = parser.parse_args(argv)
    result = run_subgroups(args.config, args.config_sha256)
    print(json.dumps({"version": VERSION, "pooled_slots": len(result["pooled_slots"]), "usage": result["usage"]}, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
