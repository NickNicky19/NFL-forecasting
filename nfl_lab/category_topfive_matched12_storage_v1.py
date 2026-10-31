"""A fourth finite CAS peer; original writers, policies and flock stay intact.

No store is opened on import. Constructors require a separately sealed root GO
through the reviewed helper. The new peer inherits every CAS, streaming, atomic
publication and restore primitive from the byte-pinned ForwardOperationalStorage.
Only allocation binding, disjointness and complete accounting are extended.
"""
from __future__ import annotations
import hashlib,json,os
from pathlib import Path

VERSION = "matched-all12-forward-v1-20261030"
NEW_LIMIT = 128 * 1024**2
WAVE_RETAINED_LIMIT = 96 * 1024**2
LEGACY_LIMIT = 512 * 1024**2
OLD_COMPLETE_LIMIT = 1367343104
COMPLETE_LIMIT = OLD_COMPLETE_LIMIT + NEW_LIMIT
OLD_UPCOMING_RESERVE = 80 * 1024**2
FORWARD_SOURCE_SHA256 = "647a3b0bf75e695fcf234f265832f9c034e96618272e1370ceb4b23718fe1499"
LEGACY_SOURCE_SHA256 = "ac27a0a09938991e6220d947292fc6a284b2d01dff2a0217fe5656c2643a59ad"


def _encoded(value):
    return (json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False)+"\n").encode()


def _overlap(a,b):
    a,b=Path(a),Path(b)
    return a==b or a.is_relative_to(b) or b.is_relative_to(a)


def _verify_bindings(legacy, bindings):
    if not isinstance(bindings,dict) or not bindings:
        raise legacy.StorageIntegrityError("nonempty pinned source/policy manifest required")
    for ref in bindings.values():
        if set(ref)!={"path","bytes","sha256"}:
            raise legacy.StorageIntegrityError("exact source binding schema required")
        path=legacy._absolute(ref["path"])
        legacy._no_symlinks(path)
        if (not path.is_file() or type(ref["bytes"]) is not int
            or ref["bytes"]<0 or not isinstance(ref["sha256"],str)
            or len(ref["sha256"])!=64):
            raise legacy.StorageIntegrityError("invalid source/policy binding")
        raw=path.read_bytes()
        if len(raw)!=ref["bytes"] or hashlib.sha256(raw).hexdigest()!=ref["sha256"]:
            raise legacy.StorageIntegrityError("reviewed source/policy bytes changed")


def attach_readonly_complete_peer(base, *, legacy_cache, market_policy,
        legacy_policy, prior_policy, metadata16_policy, metadata8_policy,
        market_module, metadata16_module, metadata8_module):
    """Attach the existing three-store stack without any old constructor.

    This is the same class composition as the retained scorecard writer's
    storage() helper. __new__ plus the pinned readonly attachment avoids its
    constructor's otherwise-idempotent root registration writes. All old
    registry, owner, outer-policy, source, alias and quota validation remains.
    """
    outer_path=Path(market_policy["store_policy"]["storage"]["forward_root"])/"state"/"historical-market-outer-policy.json"
    outer_bytes=base.legacy._encoded({"version":market_module.VERSION,
        "outer_policy":market_policy,"prior_forward_policy":prior_policy,"legacy_policy":legacy_policy})
    base.legacy._no_symlinks(outer_path)
    if not outer_path.is_file() or outer_path.read_bytes()!=outer_bytes:
        raise base.legacy.StorageIntegrityError("existing complete outer policy changed before readonly attachment")
    old_cls=metadata8_module.build_storage_class(
        metadata16_module.build_storage_class(market_module.build_storage_class(base),metadata16_policy),
        metadata8_policy)
    raw=market_module.attach_readonly_forward(base,legacy_cache,market_policy["store_policy"],legacy_policy)
    obj=old_cls.__new__(old_cls)
    obj.__dict__.update(raw.__dict__)
    obj.prior_forward=market_module.attach_readonly_forward(base,legacy_cache,prior_policy,legacy_policy)
    obj.global_limit_bytes=market_policy["global_limit_bytes"]
    obj.market_limit_bytes=market_policy["store_policy"]["storage"]["limit_bytes"]
    obj.external_inputs=market_policy["uploaded_archive_originals"]
    obj.metadata_reserve_bytes=market_policy["working_metadata_reserve_bytes"]
    obj.metadata_scopes=market_policy["working_metadata_scopes"]
    obj._external_verified={}
    obj._outer_descriptor_path=outer_path
    obj._outer_descriptor_bytes=outer_bytes
    obj._initializing_outer=False
    with obj._locked():
        obj._verify_outer_descriptor()
        obj._refresh()
        usage=obj._require(OLD_UPCOMING_RESERVE)
        if usage["category_topfive_combined_limit_bytes"]!=OLD_COMPLETE_LIMIT:
            raise base.legacy.StorageIntegrityError("existing complete allocation identity changed")
    return obj


def build_storage_class(base, *, complete_peer_factory, allocation):
    """Bind one immutable new allocation without changing inherited writers.

    complete_peer_factory is a root-pinned readonly factory; it is not invoked
    until the new policy/source/descriptor has been checked. Every ordinary new
    write still enters the inherited permanent legacy flock and quota path.
    """
    legacy=base.legacy
    if hashlib.sha256(Path(base.__file__).read_bytes()).hexdigest()!=FORWARD_SOURCE_SHA256 or hashlib.sha256(Path(legacy.__file__).read_bytes()).hexdigest()!=LEGACY_SOURCE_SHA256:
        raise legacy.StorageIntegrityError("unchanged byte-pinned storage parents required")
    policy=json.loads(_encoded(allocation))
    required={"version","store_policy","approved_parent","legacy_policy","old_complete_limit_bytes",
        "new_complete_limit_bytes","old_upcoming_reserve_bytes","wave_retained_limit_bytes",
        "new_storage_module_sha256","source_bindings","old_policy_bindings"}
    if (set(policy)!=required or policy["version"]!=VERSION
        or policy["old_complete_limit_bytes"]!=OLD_COMPLETE_LIMIT
        or policy["new_complete_limit_bytes"]!=COMPLETE_LIMIT
        or policy["old_upcoming_reserve_bytes"]!=OLD_UPCOMING_RESERVE
        or policy["wave_retained_limit_bytes"]!=WAVE_RETAINED_LIMIT
        or policy["new_storage_module_sha256"]!=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()):
        raise legacy.StorageIntegrityError("exact reviewed fourth-peer allocation required")
    # Validate every source and policy before even the readonly old stack opens.
    _verify_bindings(legacy,policy["source_bindings"])
    _verify_bindings(legacy,policy["old_policy_bindings"])
    spec=policy["store_policy"]["storage"]
    if (spec["version"]!=base.VERSION or spec["limit_bytes"]!=NEW_LIMIT
        or spec["legacy_limit_bytes"]!=LEGACY_LIMIT
        or spec["joint_limit_bytes"]!=LEGACY_LIMIT+NEW_LIMIT
        or policy["legacy_policy"]["storage"]["limit_bytes"]!=LEGACY_LIMIT):
        raise legacy.StorageIntegrityError("old limits unchanged; separate new128MiB only")
    new_root=legacy._absolute(spec["forward_root"])
    parent=legacy._absolute(policy["approved_parent"])
    if new_root.parent!=parent or new_root.name!=VERSION:
        raise legacy.StorageIntegrityError("new peer must be the registered sibling namespace")
    for p in (new_root,parent):legacy._no_symlinks(p)
    descriptor_bytes=_encoded({"version":VERSION,"allocation":policy})
    descriptor_path=new_root/"state"/"matched-all12-outer-policy.json"

    class MatchedAll12Storage(base.ForwardOperationalStorage):
        @classmethod
        def attach_readonly(cls,legacy_cache,readonly_forward_factory):
            obj=cls.__new__(cls)
            obj._matched_descriptor_path=descriptor_path
            obj._matched_descriptor_bytes=descriptor_bytes
            obj._matched_initializing=False
            obj._verify_matched_descriptor()
            peer=complete_peer_factory()
            raw=readonly_forward_factory(base,legacy_cache,policy["store_policy"],policy["legacy_policy"])
            obj.__dict__.update(raw.__dict__)
            obj.complete_peer=peer
            obj._matched_old_roots=list(peer._roots+peer.prior_forward._roots+peer.legacy._roots)
            if new_root.parent!=peer.forward_root.parent:
                raise legacy.StorageIntegrityError("new peer parent differs from approved old peer")
            if obj._thread_lock is not peer._thread_lock or obj._local is not peer._local or obj.registration_lock!=peer.registration_lock:
                raise legacy.StorageIntegrityError("readonly peer permanent lock differs")
            with obj._locked():
                obj._refresh()
                obj._require(0)
            return obj

        def __init__(self, legacy_cache):
            self._matched_descriptor_path=descriptor_path
            self._matched_descriptor_bytes=descriptor_bytes
            registry=new_root/base.VERSION/"registry.json"
            # Validate an existing new store BEFORE opening any old complete
            # peer. Interrupted first initialization remains preserved/rejected.
            self._matched_initializing=not registry.exists()
            if not self._matched_initializing:
                self._verify_matched_descriptor()
            elif new_root.exists() and any(new_root.iterdir()):
                raise legacy.StorageIntegrityError("incomplete fourth-peer initialization retained; review required")
            self.complete_peer=complete_peer_factory()
            self._matched_old_roots=list(self.complete_peer._roots+self.complete_peer.prior_forward._roots+self.complete_peer.legacy._roots)
            if new_root.parent!=self.complete_peer.forward_root.parent:
                raise legacy.StorageIntegrityError("new root is not sibling of the approved existing private peer")
            if any(_overlap(new_root,r) for r in self._matched_old_roots):
                raise legacy.StorageIntegrityError("fourth-peer overlaps retained evidence")
            super().__init__(legacy_cache,policy["store_policy"],policy["legacy_policy"])
            if self._thread_lock is not self.complete_peer._thread_lock or self._local is not self.complete_peer._local or self.registration_lock!=self.complete_peer.registration_lock:
                raise legacy.StorageIntegrityError("permanent original flock/thread context differs")
            if self._matched_initializing:
                # Inherited immutable CAS write; counted in the new peer. The
                # temporary initializer exemption ends immediately afterward.
                self.write_bytes(self._matched_descriptor_path,self._matched_descriptor_bytes)
                self._matched_initializing=False
            with self._locked():
                self._verify_matched_descriptor()
                self._scan()

        def _verify_matched_descriptor(self):
            legacy._no_symlinks(self._matched_descriptor_path)
            p=self._matched_descriptor_path
            if not p.is_file() or p.stat().st_mode&0o222 or p.read_bytes()!=self._matched_descriptor_bytes:
                raise legacy.StorageIntegrityError("immutable fourth-peer policy/source binding changed")

        def _check_roots(self, roots):
            super()._check_roots(roots)
            for r in roots:
                if any(_overlap(r,old) for old in self._matched_old_roots):
                    raise legacy.StorageIntegrityError("new private roots overlap old peer allocation")

        def _scan(self):
            if not self._matched_initializing:self._verify_matched_descriptor()
            current=super()._scan()
            self.complete_peer._refresh()
            previous=self.complete_peer._scan()
            if (previous["category_topfive_combined_limit_bytes"]!=OLD_COMPLETE_LIMIT
                or current["legacy_physical_bytes"]!=previous["legacy_physical_bytes"]):
                raise legacy.StorageIntegrityError("complete old accounting or shared legacy identity differs")
            # The complete peer ALREADY includes legacy, prior, market, uploads
            # and4/16/8MiB reserves. Add only new forward physical bytes; never
            # add this base wrapper's legacy joint bytes a second time.
            total=previous["category_topfive_combined_accounted_bytes"]+current["forward_physical_bytes"]
            if total>COMPLETE_LIMIT:
                raise legacy.StorageQuotaError("fourth-peer complete quota exhausted; preserve evidence")
            return {**current,"allocation_version":VERSION,
                "old_complete_accounted_bytes":previous["category_topfive_combined_accounted_bytes"],
                "old_complete_limit_bytes":OLD_COMPLETE_LIMIT,
                "new_peer_physical_bytes":current["forward_physical_bytes"],
                "new_peer_limit_bytes":NEW_LIMIT,"wave_retained_limit_bytes":WAVE_RETAINED_LIMIT,
                "wave_retained_headroom_bytes":WAVE_RETAINED_LIMIT-current["forward_physical_bytes"],
                "old_upcoming_reservation_bytes":OLD_UPCOMING_RESERVE,
                "matched12_complete_accounted_bytes":total,"matched12_complete_limit_bytes":COMPLETE_LIMIT}

        def _require(self, incoming):
            usage=super()._require(incoming)
            # Readonly check preserves the existing upcoming-capture reservation
            # in its own allocation; new study bytes cannot consume that space.
            self.complete_peer._require(OLD_UPCOMING_RESERVE)
            if usage["matched12_complete_accounted_bytes"]+incoming>COMPLETE_LIMIT:
                raise legacy.StorageQuotaError("incoming fourth-peer write exceeds complete peak")
            return usage

        def verify_retained_checkpoint(self):
            """Enforce the separately registered retained envelope at a safe end.

            Peak prewrite accounting remains 128MiB so atomic/streaming writes
            can complete. Every control, partial, failure and unique CAS blob is
            still retained and counted. A worker cannot mark its checkpoint
            complete merely because that larger peak allocation was respected.
            """
            with self._locked():
                self._refresh()
                usage=self._require(0)
                if usage["new_peer_physical_bytes"]>WAVE_RETAINED_LIMIT:
                    raise legacy.StorageQuotaError("96MiB retained-wave envelope exceeded; checkpoint incomplete, preserve evidence")
                return usage

    return MatchedAll12Storage
