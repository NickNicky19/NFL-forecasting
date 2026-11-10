"""Separately registered native-prior allocation; no parent cap is changed.

The existing native implementation and permanent shared lock remain in use.
Legacy completion accounting is reconciled explicitly: its whole-prior delta
predates this sibling namespace and would otherwise charge these bytes twice.
The old allocation file/code/cap/failures remain untouched. This reconciliation
requires an explicit root and independent-review acknowledgment in the plan.
"""
from __future__ import annotations

import hashlib
import gzip
import json
from pathlib import Path

ALLOCATION = "f123cd5ffd6f4a204a76c68bf63817cce63cecd7021543a23503d0233cc3eb26"
VERSION = "PROFILE-INCREMENT-TO-RELEASE-01-A-v2"
GO = VERSION + "-NATIVE-PRIOR-ROOT-AND-INDEPENDENT-GO"
RETAINED = 16 * 1024**2
PEAK = 20 * 1024**2
FAILURE_RESERVE = 2 * 1024**2
PROTECTED_PRIOR = 343932928
CAPTURE = 80 * 1024**2
OLD_VERSION = "PLAYER-CONTEXT-COMPLETION-DECISION-01-A-forward-v1"
OLD_RETAINED = 8 * 1024**2
OLD_PEAK = 12 * 1024**2
RECONCILIATION = "EXCLUDE_EXACT_NEW_SIBLING_INODES_FROM_OLD_WHOLE_PRIOR_DELTA_V1"
ACCOUNTING_REVISION = "CONTENT_GENERATION_BASELINE_ADMISSION_RECOVERY_V3"


def digest(body):
    return hashlib.sha256(body).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def unique_bytes(root):
    seen = set()
    count = 0
    if root.exists():
        for path in root.rglob("*"):
            if path.is_symlink():
                raise ValueError("managed namespace cannot contain a symlink")
            if path.is_file():
                stat = path.stat()
                identity = stat.st_dev, stat.st_ino
                if identity not in seen:
                    seen.add(identity)
                    count += stat.st_size
    return count


def namespace_inventory(root):
    """Bind exact sibling inode ownership; never subtract unclassified growth."""
    members, seen, physical = [], set(), 0
    if root.exists():
        for path in sorted(root.rglob("*")):
            if path.is_symlink():
                raise ValueError("managed namespace cannot contain a symlink")
            if path.is_file():
                stat = path.stat()
                inode = stat.st_dev, stat.st_ino
                members.append([str(path.relative_to(root)), stat.st_size, *inode])
                if inode not in seen:
                    seen.add(inode)
                    physical += stat.st_size
    return dict(unique_bytes=physical, files=len(members), unique_inodes=len(seen),
                member_identity_sha256=digest(encoded(members)))


def inode_inventory(roots):
    """Metadata-only map matching the native scanner's complete root set."""
    inodes = {}
    for root in roots:
        root = Path(root)
        if root.is_symlink():
            raise ValueError("native managed root cannot be a symlink")
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_symlink():
                raise ValueError("native managed file cannot be a symlink")
            if path.is_file():
                stat = path.stat()
                key = f"{stat.st_dev}:{stat.st_ino}"
                if key in inodes and inodes[key] != stat.st_size:
                    raise ValueError("native inode changed during inventory")
                inodes[key] = stat.st_size
    return inodes


def generation_inventory(roots):
    """Bind content generations; inode-number reuse is not content mutation.

    Native integrity scanning must precede this metadata/body-hash inventory.
    A hardlink changes ctime, so timestamps cannot identify a CAS generation.
    Identical aliases share this key; same-inode new content has a new key.
    """
    generations, seen = {}, {}
    for root in roots:
        root = Path(root)
        if root.is_symlink():
            raise ValueError("managed root cannot be a symlink")
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_symlink():
                raise ValueError("managed file cannot be a symlink")
            if not path.is_file():
                continue
            stat = path.stat()
            inode = stat.st_dev, stat.st_ino
            if inode not in seen:
                content_sha = digest(path.read_bytes())
                after = path.stat()
                if (stat.st_size, stat.st_mtime_ns, stat.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
                    raise ValueError("file changed during content-generation inventory")
                seen[inode] = (stat.st_size, content_sha)
                generations[f"{stat.st_dev}:{stat.st_ino}:{stat.st_size}:{content_sha}"] = stat.st_size
            elif seen[inode][0] != stat.st_size:
                raise ValueError("alias size changed during generation inventory")
    return generations


def reconcile_owned(old_namespace_bytes, old_registration_charge, old_whole_prior_delta,
                    sibling_inodes, baseline_prior_inodes):
    """Subtract only proven newly allocated sibling-owned physical inodes.

    A sibling alias to a baseline CAS blob allocates zero physical bytes and is
    never deducted. Unclassified registry/orphan/concurrent growth remains old
    charged. Duplicate aliases have one map key and are deducted exactly once.
    This pure function is independently exercisable without managed storage.
    """
    owned_new = 0
    for inode, size in sibling_inodes.items():
        if type(size) is not int or size < 0:
            raise ValueError("invalid inode physical size")
        if inode in baseline_prior_inodes:
            if baseline_prior_inodes[inode] != size:
                raise ValueError("baseline inode changed size")
        else:
            owned_new += size
    old_charge = max(old_namespace_bytes, old_registration_charge,
                     max(0, old_whole_prior_delta - owned_new))
    return dict(old_reconciled_charged_bytes=old_charge,
                exact_new_sibling_owned_physical_bytes=owned_new,
                baseline_deduplicated_sibling_bytes=sum(sibling_inodes.values())-owned_new)


def readonly_inventory(root):
    """Fresh native admission and ownership sizing, without a new constructor."""
    from tools.category_topfive_matched12_storage_v1 import open_store, GO as OLD_GO
    outer, _ = open_store(Path(root), allocation_sha256=ALLOCATION, root_go=OLD_GO, readonly=True)
    prior = outer.complete_peer.prior_forward
    old_path = prior.forward_root / "research" / OLD_VERSION
    with outer.transaction():
        outer._refresh()
        complete = outer.verify_retained_checkpoint()
        prior._refresh()
        usage = prior._scan()
        prior.validate_reference(old_path / "ALLOCATION_STATE.json")
        old_state = json.loads((old_path / "ALLOCATION_STATE.json").read_bytes())
        old = namespace_inventory(old_path)
        old_charged = max(old["unique_bytes"], usage["forward_physical_bytes"] - old_state["baseline_prior_bytes"])
        required = PROTECTED_PRIOR + old_charged + PEAK
        prior._require(required)
        outer.complete_peer._require(CAPTURE + PEAK)
        outer._require(PEAK)
        return dict(state="PASS_READONLY_FRESH_ADMISSION_NO_NEW_ALLOCATION_CREATED",
            prior_physical_bytes=usage["forward_physical_bytes"], prior_limit_bytes=prior.limit_bytes,
            prior_incoming_protection_bytes=required,
            prior_remaining_after_protection_bytes=prior.limit_bytes-usage["forward_physical_bytes"]-required,
            old_completion=old, old_completion_charged_bytes=old_charged,
            old_completion_limit_bytes=OLD_RETAINED, old_wave_headroom_bytes=complete["wave_retained_headroom_bytes"],
            complete_accounted_bytes=complete["matched12_complete_accounted_bytes"],
            complete_limit_bytes=complete["matched12_complete_limit_bytes"],
            unchanged_capture_reserve_bytes=CAPTURE, new_namespace_created=False)


class ProfileIncrementStore:
    def __init__(self, root, allocation_path, allocation_sha256, *, root_go):
        if root_go != GO:
            raise ValueError("exact new allocation GO is required")
        self.root = Path(root).resolve()
        body = Path(allocation_path).read_bytes()
        if digest(body) != allocation_sha256:
            raise ValueError("registered allocation bytes changed")
        self.plan = json.loads(body)
        required = {"version": VERSION, "retained_bytes": RETAINED, "peak_bytes": PEAK,
            "failure_reserve_bytes": FAILURE_RESERVE, "protected_prior_plan_bytes": PROTECTED_PRIOR,
            "unchanged_capture_reserve_bytes": CAPTURE,
            "legacy_completion_reconciliation": RECONCILIATION,
            "accounting_revision": ACCOUNTING_REVISION,
            "state": "ROOT_AND_INDEPENDENT_REVIEWED_ALLOCATION"}
        for key, value in required.items():
            if self.plan.get(key) != value:
                raise ValueError("exact finite allocation/reconciliation required: " + key)
        if not self.plan.get("independent_review_sha256"):
            raise ValueError("allocation requires actual independent-review binding")
        for path, expected in self.plan["code_sha256"].items():
            if digest((self.root / path).read_bytes()) != expected:
                raise ValueError("bound allocation code changed")
        from tools.category_topfive_matched12_storage_v1 import open_store, GO as OLD_GO
        self.outer, _ = open_store(self.root, allocation_sha256=ALLOCATION, root_go=OLD_GO, readonly=True)
        self.prior = self.outer.complete_peer.prior_forward
        if (self.outer._local is not self.prior._local
                or self.outer._thread_lock is not self.prior._thread_lock
                or self.outer.lock_path != self.prior.lock_path):
            raise ValueError("native shared reentrant lock identity changed")
        self.destination = self.prior.forward_root / "research" / VERSION
        self.old_destination = self.prior.forward_root / "research" / OLD_VERSION
        with self.outer.transaction():
            old_state_path = self.old_destination / "ALLOCATION_STATE.json"
            self.prior.validate_reference(old_state_path)
            self.old_state = json.loads(old_state_path.read_bytes())
            if (self.old_state["version"] != OLD_VERSION
                    or self.old_state["retained_bytes"] != OLD_RETAINED
                    or self.old_state["peak_bytes"] != OLD_PEAK):
                raise ValueError("legacy completion allocation changed")
            original_path = self.destination / "ALLOCATION_STATE.json"
            self.prior.validate_reference(original_path, self.plan["original_allocation_state_sha256"])
            original = json.loads(original_path.read_bytes())
            if original["allocation_sha256"] != self.plan["amends_allocation_sha256"]:
                raise ValueError("explicit original allocation amendment binding required")
            state_path = self.destination / "ALLOCATION_ACCOUNTING_V3.json"
            if not state_path.exists():
                physical = self.prior._scan()["forward_physical_bytes"]
                baseline_inodes = generation_inventory(self.prior._roots)
                if sum(baseline_inodes.values()) != physical:
                    raise ValueError("generation baseline differs from native physical scan")
                # Every ambiguous pre-recovery object remains in the old floor;
                # no V1 identity is reclassified or silently rewritten.
                old_floor = max(unique_bytes(self.old_destination), physical-self.old_state["baseline_prior_bytes"])
                if old_floor > OLD_RETAINED:
                    raise ValueError("conservative old allocation floor exceeds unchanged cap")
                self.baseline_inodes, self.old_floor = baseline_inodes, old_floor
                self._admit(PEAK)
                baseline_body = gzip.compress(encoded(baseline_inodes), mtime=0)
                baseline_path = self.destination / "BASELINE_PRIOR_CONTENT_GENERATIONS_V3.json.gz"
                self.prior.write_bytes(baseline_path, baseline_body)
                state = dict(version=VERSION, accounting_revision=ACCOUNTING_REVISION,
                    allocation_sha256=allocation_sha256, original_allocation_sha256=original["allocation_sha256"],
                    original_allocation_state_sha256=self.plan["original_allocation_state_sha256"],
                    baseline_prior_bytes=original["baseline_prior_bytes"],
                    generation_baseline_prior_bytes=physical,
                    old_charged_at_registration=old_floor,
                    old_baseline_prior_bytes=self.old_state["baseline_prior_bytes"],
                    old_allocation_sha256=self.old_state["allocation_sha256"],
                    baseline_prior_inode_ref=dict(id=baseline_path.name, bytes=len(baseline_body), sha256=digest(baseline_body)),
                    retained_bytes=RETAINED, peak_bytes=PEAK,
                    legacy_completion_reconciliation=RECONCILIATION,
                    disposition="V1_BASELINE_STATE_FAILURES_PRESERVED_AMBIGUOUS_BYTES_NOT_DEDUCTED")
                self.prior.write_bytes(state_path, encoded(state))
            self.prior.validate_reference(state_path)
            self.state = json.loads(state_path.read_bytes())
            if self.state["version"] != VERSION:
                raise ValueError("existing allocation version cannot be reset")
            code_amendment = None
            if self.state["allocation_sha256"] != allocation_sha256:
                amendment = self.plan.get("code_binding_amendment", {})
                previous_ref = amendment.get("previous_allocation", {})
                previous_body = Path(previous_ref["path"]).read_bytes()
                if (len(previous_body) != previous_ref["bytes"]
                        or digest(previous_body) != previous_ref["sha256"]
                        or previous_ref["sha256"] != self.state["allocation_sha256"]
                        or amendment.get("id") != "HISTORICAL_BOUNDARY_CODE_BINDING_V4"):
                    raise ValueError("exact immutable previous allocation amendment required")
                previous = json.loads(previous_body)
                unchanged = ["version", "retained_bytes", "peak_bytes", "failure_reserve_bytes",
                    "protected_prior_plan_bytes", "unchanged_capture_reserve_bytes", "legacy_completion_reconciliation",
                    "accounting_revision", "original_allocation_state_sha256", "amends_allocation_sha256"]
                if any(previous.get(k) != self.plan.get(k) for k in unchanged):
                    raise ValueError("execution amendment cannot change allocation/baseline policy")
                before, after = previous["code_sha256"], self.plan["code_sha256"]
                if set(before) != set(after):
                    raise ValueError("execution amendment cannot change bound code scope")
                changed = {p for p in before if before[p] != after[p]}
                if not changed <= {"nfl_lab/profile_increment_a_storage_v2.py",
                    "nfl_lab/profile_increment_a_v2.py", "tools/profile_increment_a_run_v2.py"}:
                    raise ValueError("execution amendment exceeds reviewed clock/accounting scope")
                code_amendment = dict(id=amendment["id"], version=VERSION,
                    new_allocation_sha256=allocation_sha256, previous_allocation_sha256=previous_ref["sha256"],
                    changed_code_sha256={p: dict(previous=before[p], current=after[p]) for p in sorted(changed)},
                    accounting_state_sha256=digest(state_path.read_bytes()),
                    policy="CODE_BINDING_ONLY_NO_BASELINE_FLOOR_CAP_OR_CONSUMPTION_RESET")
            self.baseline = self.state["baseline_prior_bytes"]
            self.old_floor = self.state["old_charged_at_registration"]
            baseline_ref = self.state["baseline_prior_inode_ref"]
            baseline_path = self.destination / baseline_ref["id"]
            self.prior.validate_reference(baseline_path, baseline_ref["sha256"])
            baseline_body = baseline_path.read_bytes()
            if len(baseline_body) != baseline_ref["bytes"]:
                raise ValueError("immutable baseline inode map changed")
            self.baseline_inodes = json.loads(gzip.decompress(baseline_body))
            if sum(self.baseline_inodes.values()) != self.state["generation_baseline_prior_bytes"]:
                raise ValueError("baseline physical binding differs")
            self._admit(0)
            self._usage()
            if code_amendment is not None:
                amendment_path = self.destination / "ALLOCATION_CODE_BINDING_AMENDMENT_V4.json"
                amendment_body = encoded(code_amendment)
                self._admit(len(amendment_body))
                if amendment_path.exists():
                    self.prior.validate_reference(amendment_path, digest(amendment_body))
                else:
                    if self._usage()["charged_bytes"] + len(amendment_body) > RETAINED:
                        raise ValueError("code amendment exceeds unchanged retained allocation")
                    self.prior.write_bytes(amendment_path, amendment_body)
                    self.prior.validate_reference(amendment_path, digest(amendment_body))
                self._usage()

    def _admit(self, incoming):
        self.outer._refresh()
        self.outer._require(incoming)
        self.outer.complete_peer._refresh()
        self.outer.complete_peer._require(CAPTURE + incoming)
        self.prior._refresh()
        # Existing native _require scans all actual native-prior bytes. Protect
        # both the registered earlier plan and old completion namespace before
        # reserving this wave's unchanged finite peak.
        physical = self.prior._scan()["forward_physical_bytes"]
        sibling = generation_inventory([self.destination])
        old_actual = reconcile_owned(unique_bytes(self.old_destination), self.old_floor,
            physical - self.old_state["baseline_prior_bytes"], sibling, self.baseline_inodes)["old_reconciled_charged_bytes"]
        self.prior._require(PROTECTED_PRIOR + old_actual + PEAK)

    def _usage(self):
        usage = self.prior._scan()
        physical = usage["forward_physical_bytes"]
        sibling = namespace_inventory(self.destination)
        namespace = sibling["unique_bytes"]
        charged = max(namespace, max(0, physical - self.baseline))
        old_namespace = unique_bytes(self.old_destination)
        old_legacy_delta = max(0, physical - self.state["old_baseline_prior_bytes"])
        # Subtract only exact owned sibling inodes. Registry growth, unknown
        # orphan blobs and concurrent unrelated writes are NOT blanket removed.
        # They remain conservatively charged by the old whole-prior delta as
        # well as native global accounting until an explicit attribution exists.
        reconciled = reconcile_owned(old_namespace, self.state["old_charged_at_registration"],
            old_legacy_delta, generation_inventory([self.destination]), self.baseline_inodes)
        old_reconciled = reconciled["old_reconciled_charged_bytes"]
        if old_reconciled > OLD_RETAINED:
            raise ValueError("old completion retained cap exceeded under ownership reconciliation")
        return dict(namespace_unique_bytes=namespace,
            prior_delta_including_controls_or_orphans=max(0, physical - self.baseline),
            charged_bytes=charged, prior_physical_bytes=physical,
            old_completion_namespace_bytes=old_namespace,
            old_completion_reconciled_charged_bytes=old_reconciled,
            old_completion_legacy_whole_prior_delta_bytes=old_legacy_delta,
            old_completion_cap_bytes=OLD_RETAINED,
            exact_new_sibling_inventory=sibling,
            sibling_ownership_reconciliation=reconciled,
            legacy_completion_reconciliation=RECONCILIATION)

    def _path(self, name):
        value = Path(name)
        if value.is_absolute() or not value.parts or any(x in {"..", "."} for x in value.parts):
            raise ValueError("relative immutable managed artifact name required")
        return self.destination / value

    def reserve(self, expected_bytes, *, failure=False):
        if type(expected_bytes) is not int or expected_bytes < 0:
            raise ValueError("nonnegative finite reservation required")
        with self.outer.transaction():
            self._admit(expected_bytes)
            usage = self._usage()
            reserve = 0 if failure else FAILURE_RESERVE
            if usage["charged_bytes"] + expected_bytes + reserve > RETAINED:
                raise ValueError("new retained reservation exhausted before fit/write")
        return usage

    def put(self, name, body, *, failure=False):
        if not isinstance(body, bytes):
            raise TypeError("exact immutable bytes required")
        path = self._path(name)
        with self.outer.transaction():
            self._admit(len(body))
            usage = self._usage()
            if path.exists():
                self.prior.validate_reference(path, digest(body))
                if path.read_bytes() != body:
                    raise ValueError("immutable new-wave artifact conflict")
            else:
                if usage["charged_bytes"] + len(body) + (0 if failure else FAILURE_RESERVE) > RETAINED:
                    raise ValueError("new-wave retained cap/failure reserve exhausted")
                self.prior.write_bytes(path, body)
                self.prior.validate_reference(path, digest(body))
            if self._usage()["charged_bytes"] > RETAINED:
                raise ValueError("new retained cap exceeded; evidence preserved")
        return dict(id=str(name), bytes=len(body), sha256=digest(body))

    def read(self, name, sha256):
        with self.outer.transaction():
            self._admit(0)
            path = self._path(name)
            self.prior.validate_reference(path, sha256)
            body = path.read_bytes()
            if digest(body) != sha256:
                raise ValueError("managed readback changed")
            return body

    def checkpoint(self):
        with self.outer.transaction():
            self._admit(0)
            old = self.outer.verify_retained_checkpoint()
            usage = self._usage()
            if usage["charged_bytes"] > RETAINED:
                raise ValueError("new allocation retained cap exceeded")
            return dict(state="PASS_NATIVE_OLD_AND_NEW_CAPS_WITH_BOUND_OWNERSHIP_RECONCILIATION",
                **usage, retained_cap=RETAINED, peak_cap=PEAK,
                protected_prior_plan_bytes=PROTECTED_PRIOR,
                unchanged_capture_reserve_bytes=CAPTURE,
                old_wave_headroom_bytes=old["wave_retained_headroom_bytes"],
                complete_accounted_bytes=old["matched12_complete_accounted_bytes"],
                unchanged_complete_cap_bytes=old["matched12_complete_limit_bytes"])
