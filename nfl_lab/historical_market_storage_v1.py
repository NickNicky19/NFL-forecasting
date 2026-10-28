"""Bounded third allocation reusing frozen CAS, quota and locking primitives.

The old v2 and v3 stores are read-only accounting peers. No CAS method is
copied or replaced. Uploaded ZIP originals remain counted even after private
copies are made; no original evidence or old budget is reclaimed.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import threading


VERSION = "historical-market-forward-v1"
MAX_MARKET_BYTES = 256 * 1024**2
MAX_GLOBAL_BYTES = 1280 * 1024**2
FORWARD_SHA256 = "647a3b0bf75e695fcf234f265832f9c034e96618272e1370ceb4b23718fe1499"
LEGACY_SHA256 = "ac27a0a09938991e6220d947292fc6a284b2d01dff2a0217fe5656c2643a59ad"


def load_frozen(forward_path, legacy_library_root):
    """Load explicit source identities without initializing either store."""
    forward_path, legacy_library_root = Path(forward_path), Path(legacy_library_root)
    if hashlib.sha256(forward_path.read_bytes()).hexdigest() != FORWARD_SHA256:
        raise ValueError("frozen forward implementation changed")
    sys.path.insert(0, str(legacy_library_root))
    from nfl_lab import operational_storage as legacy
    if hashlib.sha256(Path(legacy.__file__).read_bytes()).hexdigest() != LEGACY_SHA256:
        raise ValueError("frozen legacy implementation changed")
    spec = importlib.util.spec_from_file_location("frozen_market_storage_parent", forward_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if module.legacy is not legacy:
        raise ValueError("storage implementations do not share lock context")
    return module


def attach_readonly_forward(module, cache, policy, legacy_policy):
    """Bind existing controls only; intentionally never call a constructor."""
    legacy = module.legacy
    spec = policy["storage"]
    obj = module.ForwardOperationalStorage.__new__(module.ForwardOperationalStorage)
    obj.forward_root = legacy._absolute(spec["forward_root"])
    obj.limit_bytes = module._limit(spec["limit_bytes"], module.MAX_FORWARD_BYTES)
    obj.joint_limit_bytes = module._limit(spec["joint_limit_bytes"], module.MAX_JOINT_BYTES)
    obj.legacy_limit_bytes = module._limit(spec["legacy_limit_bytes"], legacy.MAX_BYTES)
    if (spec["version"] != module.VERSION
            or legacy_policy["storage"]["version"] != legacy.VERSION
            or legacy_policy["storage"]["limit_bytes"] != obj.legacy_limit_bytes
            or legacy_policy["namespaces"]["private_retention_bytes"] != obj.legacy_limit_bytes):
        raise ValueError("peer storage policy mismatch")
    obj.registration_registry_sha256 = spec["legacy_registry_sha256_at_registration"]
    obj.registration_lock = spec["legacy_lock_at_registration"]
    old = legacy.OperationalStorage.__new__(legacy.OperationalStorage)
    old.cache = legacy._absolute(cache)
    old.control_root = old.cache / legacy.VERSION
    old.blob_root = old.control_root / "blobs" / "sha256"
    old.registry_path = old.control_root / "registry.json"
    old.lock_path = old.control_root / ".quota.lock"
    old.limit_bytes = obj.legacy_limit_bytes
    old._verified = {}
    with legacy._THREAD_GUARD:
        old._thread_lock = legacy._THREAD_LOCKS.setdefault(str(old.control_root), threading.RLock())
        old._local = legacy._THREAD_CONTEXTS.setdefault(str(old.control_root), threading.local())
    obj.legacy = old
    obj.legacy_cache, obj.legacy_state_root = old.cache, None
    obj.cache = obj.forward_root / "cache"
    obj.control_root = obj.forward_root / module.VERSION
    obj.blob_root = obj.control_root / "blobs" / "sha256"
    obj.source_root = obj.cache / "operational-source-v3"
    obj.feature_root = obj.cache / "processed" / "operational-source-v3"
    obj.live_root = obj.cache / "operational-live-v3"
    obj.state_root = obj.forward_root / "state"
    obj.model_root = obj.state_root / "models" / "permitted-operational-reference-v3"
    obj.registry_path = obj.control_root / "registry.json"
    obj.base_manifest_path = obj.control_root / "frozen-base-inventory.json"
    obj.lock_path = old.lock_path
    obj._thread_lock, obj._local = old._thread_lock, old._local
    obj._verified, obj._stream_owned = {}, {}
    obj._roots, obj._base_manifest, obj._base_sha256 = [], None, None
    for p in [old.lock_path, old.registry_path, obj.registry_path, obj.base_manifest_path]:
        legacy._no_symlinks(p)
        if not p.is_file():
            raise ValueError("complete preexisting read-only controls required")
    with obj._locked():
        identity = os.fstat(obj._local.lock_fd)
        if [identity.st_dev, identity.st_ino] != obj.registration_lock:
            raise ValueError("permanent peer flock identity changed")
        obj._refresh()
        obj._scan()
    return obj


def build_storage_class(module):
    """Wrap accounting only; use inherited immutable publication everywhere."""
    legacy = module.legacy

    class HistoricalMarketStorage(module.ForwardOperationalStorage):
        def __init__(self, cache, policy, legacy_policy, prior_policy):
            if policy["version"] != VERSION:
                raise ValueError("explicit historical market allocation required")
            self.prior_forward = attach_readonly_forward(module, cache, prior_policy, legacy_policy)
            self.global_limit_bytes = module._limit(policy["global_limit_bytes"], MAX_GLOBAL_BYTES)
            self.market_limit_bytes = module._limit(policy["store_policy"]["storage"]["limit_bytes"], MAX_MARKET_BYTES)
            self.external_inputs = policy["uploaded_archive_originals"]
            self.metadata_reserve_bytes = policy["working_metadata_reserve_bytes"]
            self.metadata_scopes = policy["working_metadata_scopes"]
            if (type(self.metadata_reserve_bytes) is not int or self.metadata_reserve_bytes < 0
                    or policy["excluded_seasons"] != [2025]
                    or self.global_limit_bytes != self.prior_forward.legacy_limit_bytes
                    + self.prior_forward.limit_bytes + self.market_limit_bytes):
                raise ValueError("unmodified old caps plus separate new cap required")
            self._external_verified = {}
            # Frozen internal controls bind their own two-store policy. Bind
            # this complete outer policy separately, including the third peer,
            # uploaded originals, working metadata and every wave envelope.
            new_root = Path(policy["store_policy"]["storage"]["forward_root"])
            self._outer_descriptor_path = new_root / "state" / "historical-market-outer-policy.json"
            self._outer_descriptor_bytes = legacy._encoded({
                "version": VERSION, "outer_policy": policy,
                "prior_forward_policy": prior_policy, "legacy_policy": legacy_policy,
            })
            registry = new_root / module.VERSION / "registry.json"
            self._initializing_outer = not registry.exists()
            if not self._initializing_outer:
                self._verify_outer_descriptor()
            elif new_root.exists() and any(new_root.iterdir()):
                raise ValueError("incomplete outer initialization retained; review required")
            super().__init__(cache, policy["store_policy"], legacy_policy)
            if self._initializing_outer:
                self.write_bytes(self._outer_descriptor_path, self._outer_descriptor_bytes)
                self._initializing_outer = False
            with self._locked():
                self._verify_outer_descriptor()
                self._scan()

        def _verify_outer_descriptor(self):
            legacy._no_symlinks(self._outer_descriptor_path)
            if (not self._outer_descriptor_path.is_file()
                    or self._outer_descriptor_path.read_bytes() != self._outer_descriptor_bytes):
                raise legacy.StorageIntegrityError("immutable complete outer accounting policy mismatch")

        def _check_roots(self, roots):
            super()._check_roots(roots)
            self.prior_forward._refresh()
            for root in roots:
                if any(module._overlap(root, old) for old in self.prior_forward._roots):
                    raise legacy.StorageIntegrityError("new and old forward roots overlap")

        def _external_bytes(self):
            total, seen = 0, set()
            for ref in self.external_inputs:
                p = Path(ref["path"])
                legacy._no_symlinks(p)
                if p.resolve() != p or any(legacy._beneath(p, r) for r in self._roots + self.prior_forward._roots + self.legacy._roots):
                    raise legacy.StorageIntegrityError("uploaded input counted in two boundaries")
                before = p.stat()
                identity = (before.st_dev, before.st_ino)
                if before.st_nlink != 1 or identity in seen or before.st_size != ref["bytes"]:
                    raise legacy.StorageIntegrityError("uploaded archive identity/size/link mismatch")
                seen.add(identity)
                stamp = legacy._stamp(before)
                if self._external_verified.get(str(p)) != stamp:
                    if legacy._digest_file(p) != ref["sha256"] or legacy._stamp(p.stat()) != stamp:
                        raise legacy.StorageIntegrityError("uploaded archive bytes changed")
                    self._external_verified[str(p)] = stamp
                total += before.st_size
            return total

        def _metadata_bytes(self):
            seen, total = set(), 0
            for scope in self.metadata_scopes:
                root = Path(scope["root"])
                legacy._no_symlinks(root)
                if root.resolve() != root or any(module._overlap(root, r) for r in self._roots + self.prior_forward._roots + self.legacy._roots):
                    raise legacy.StorageIntegrityError("metadata scope overlaps counted store")
                for item in root.glob(scope["pattern"]):
                    items = [item]
                    if item.is_dir():
                        for directory, dirs, files in os.walk(item, followlinks=False, onerror=legacy._walk_error):
                            items.extend(Path(directory) / n for n in dirs + files)
                    for p in items:
                        legacy._no_symlinks(p)
                        if p.is_dir():
                            continue
                        st = p.stat()
                        if st.st_nlink != 1:
                            raise legacy.StorageIntegrityError("working metadata has unaccounted hardlink")
                        key = st.st_dev, st.st_ino
                        if key not in seen:
                            total += st.st_size
                            seen.add(key)
            if total > self.metadata_reserve_bytes:
                raise legacy.StorageQuotaError("actual working metadata exceeds reserved peak")
            return total

        def _scan(self):
            if not self._initializing_outer:
                self._verify_outer_descriptor()
            usage = super()._scan()
            self.prior_forward._refresh()
            prior = self.prior_forward._scan()
            external = self._external_bytes()
            metadata_actual = self._metadata_bytes()
            market = usage["forward_physical_bytes"] + external + self.metadata_reserve_bytes
            global_usage = usage["joint_physical_bytes"] + prior["forward_physical_bytes"] + external + self.metadata_reserve_bytes
            if market > self.market_limit_bytes or global_usage > self.global_limit_bytes:
                raise legacy.StorageQuotaError("third allocation/global quota exceeded; evidence retained")
            return {**usage, "outer_allocation_version": VERSION,
                    "prior_forward_physical_bytes": prior["forward_physical_bytes"],
                    "prior_forward_limit_bytes": self.prior_forward.limit_bytes,
                    "uploaded_original_bytes": external,
                    "working_metadata_reserved_bytes": self.metadata_reserve_bytes,
                    "working_metadata_actual_bytes": metadata_actual,
                    "market_accounted_bytes": market,
                    "market_limit_bytes": self.market_limit_bytes,
                    "global_accounted_bytes": global_usage,
                    "global_limit_bytes": self.global_limit_bytes}

        def _require(self, incoming):
            usage = super()._require(incoming)
            if (usage["market_accounted_bytes"] + incoming > self.market_limit_bytes
                    or usage["global_accounted_bytes"] + incoming > self.global_limit_bytes):
                raise legacy.StorageQuotaError("incoming bytes exceed complete market/global peak quota")
            return usage

    return HistoricalMarketStorage
