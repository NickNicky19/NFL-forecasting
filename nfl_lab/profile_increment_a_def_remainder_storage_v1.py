"""Finite native-prior supplement for the single unfinished defense arm.

No old cap/baseline/guard is changed. Primary16MiB excludes only newly owned
supplement generations; old8MiB excludes the deduplicated union of proven new
primary/supplement generations. Unknown growth remains conservatively charged.
"""
from __future__ import annotations
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path

VERSION = "PROFILE-INCREMENT-TO-RELEASE-01-A-v2-def-remainder-v1"
PRIMARY = "PROFILE-INCREMENT-TO-RELEASE-01-A-v2"
OLD = "PLAYER-CONTEXT-COMPLETION-DECISION-01-A-forward-v1"
GO = VERSION + "-ROOT-AND-INDEPENDENT-GO"
RETAINED, PEAK, FAILURE = 8*1024**2, 10*1024**2, 2*1024**2
PRIMARY_RETAINED, OLD_RETAINED = 16*1024**2, 8*1024**2
PRIMARY_PEAK, OLD_PEAK = 20*1024**2, 12*1024**2
PROTECTED_PRIOR, CAPTURE = 343932928, 80*1024**2
OUTER_ALLOCATION = "f123cd5ffd6f4a204a76c68bf63817cce63cecd7021543a23503d0233cc3eb26"
HELPER_SHA = "2b4c8bff5fe59a1cc6cbea42a146d79431d127fee7f76840c97d4bb6f6eb9eb1"

def sha(body): return hashlib.sha256(body).hexdigest()
def enc(value): return (json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False)+"\n").encode()

def helpers(root):
    path=Path(root)/"nfl_lab/profile_increment_a_storage_v2.py"
    if sha(path.read_bytes())!=HELPER_SHA: raise ValueError("frozen primary accounting helper changed")
    spec=importlib.util.spec_from_file_location("bound_profile_accounting_v5",path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def attach(root):
    from tools.category_topfive_matched12_storage_v1 import open_store,GO as ORIGINAL_GO
    outer,_=open_store(Path(root),allocation_sha256=OUTER_ALLOCATION,root_go=ORIGINAL_GO,readonly=True)
    prior=outer.complete_peer.prior_forward
    if outer._local is not prior._local or outer._thread_lock is not prior._thread_lock or outer.lock_path!=prior.lock_path:
        raise ValueError("existing permanent shared lock identity required")
    return outer,prior

def native_json(prior,path,expected=None):
    prior.validate_reference(path,expected)
    return json.loads(path.read_bytes())

def accounting(old_namespace_bytes, old_floor, old_delta, primary_namespace_bytes,
               primary_floor, primary_delta, child_namespace_bytes, child_delta,
               primary_generations, primary_baseline, child_generations, child_baseline):
    """Pure, independently testable ownership accounting; no blanket delta subtraction."""
    def owned(current,baseline):
        result={}
        for key,value in current.items():
            if type(value)is not int or value<0: raise ValueError("invalid physical generation size")
            if key in baseline:
                if baseline[key]!=value: raise ValueError("immutable generation size differs")
            else: result[key]=value
        return result
    po,co=owned(primary_generations,primary_baseline),owned(child_generations,child_baseline)
    union=dict(po)
    for key,value in co.items():
        if key in union and union[key]!=value: raise ValueError("union generation size differs")
        union[key]=value
    return dict(old8_charged_bytes=max(old_namespace_bytes,old_floor,max(0,old_delta-sum(union.values()))),
        primary16_charged_bytes=max(primary_namespace_bytes,primary_floor,max(0,primary_delta-sum(co.values()))),
        supplement_charged_bytes=max(child_namespace_bytes,max(0,child_delta)),
        proven_primary_owned_bytes=sum(po.values()),proven_child_owned_bytes=sum(co.values()),
        deduplicated_union_owned_bytes=sum(union.values()))

def readonly_inventory(root):
    """Fresh pre-supplement native sizing, after the primary writer stops."""
    obj=RemainderStore.__new__(RemainderStore)
    obj.root=Path(root).resolve();obj.h=helpers(obj.root);obj.outer,obj.prior=attach(obj.root)
    obj.primary=obj.prior.forward_root/"research"/PRIMARY;obj.old=obj.prior.forward_root/"research"/OLD
    obj.destination=obj.prior.forward_root/"research"/VERSION
    with obj.outer.transaction():
        if obj.destination.exists(): raise ValueError("preallocation inventory cannot rebaseline an existing supplement")
        ps_path=obj.primary/"ALLOCATION_ACCOUNTING_V3.json";os_path=obj.old/"ALLOCATION_STATE.json"
        obj.ps=native_json(obj.prior,ps_path);obj.os=native_json(obj.prior,os_path)
        ref=obj.ps["baseline_prior_inode_ref"];bp=obj.primary/ref["id"]
        obj.prior.validate_reference(bp,ref["sha256"]);obj.pb=json.loads(gzip.decompress(bp.read_bytes()))
        obj.baseline=obj.prior._scan()["forward_physical_bytes"]
        obj.cb=obj.h.generation_inventory(obj.prior._roots);obj.primary_floor=0
        if sum(obj.cb.values())!=obj.baseline: raise ValueError("fresh native generation inventory differs")
        usage=obj._usage();obj.primary_floor=usage["primary16_charged_bytes"]
        obj._admit(PEAK)
        old=obj.outer.verify_retained_checkpoint()
        protection=PROTECTED_PRIOR+usage["old8_charged_bytes"]+PRIMARY_RETAINED+PEAK
        return dict(state="PASS_READONLY_SUPPLEMENT_ADMISSION_NO_NAMESPACE_CREATED",**usage,
            primary_accounting_state_sha256=sha(ps_path.read_bytes()),old_completion_state_sha256=sha(os_path.read_bytes()),
            native_prior_limit_bytes=obj.prior.limit_bytes,protection_bytes=protection,
            headroom_after_protection_bytes=obj.prior.limit_bytes-obj.baseline-protection,
            proposed_retained_bytes=RETAINED,proposed_peak_bytes=PEAK,unchanged_primary_reserved_bytes=PRIMARY_RETAINED,
            unchanged_capture_reserve_bytes=CAPTURE,old_wave_headroom_bytes=old["wave_retained_headroom_bytes"],
            new_private_writes=0,constructors=0)

class RemainderStore:
    def __init__(self,root,allocation_path,allocation_sha256,*,root_go):
        if root_go!=GO: raise ValueError("explicit reviewed one-arm supplemental allocation GO required")
        self.root=Path(root).resolve();body=Path(allocation_path).read_bytes()
        if sha(body)!=allocation_sha256: raise ValueError("supplement allocation changed")
        self.plan=json.loads(body)
        required=dict(version=VERSION,state="ROOT_AND_INDEPENDENT_REVIEWED_ALLOCATION",
            retained_bytes=RETAINED,peak_bytes=PEAK,failure_reserve_bytes=FAILURE,
            protected_prior_plan_bytes=PROTECTED_PRIOR,unchanged_capture_reserve_bytes=CAPTURE,
            unchanged_primary_reserved_bytes=PRIMARY_RETAINED,unchanged_old_completion_cap_bytes=OLD_RETAINED)
        if any(self.plan.get(k)!=v for k,v in required.items()): raise ValueError("finite unchanged-cap supplement contract differs")
        if not self.plan.get("independent_review_sha256"): raise ValueError("independent receipt binding required")
        for path,expected in self.plan["code_sha256"].items():
            if sha((self.root/path).read_bytes())!=expected: raise ValueError("bound supplemental code changed")
        self.h=helpers(self.root);self.outer,self.prior=attach(self.root)
        self.primary=self.prior.forward_root/"research"/PRIMARY
        self.old=self.prior.forward_root/"research"/OLD
        self.destination=self.prior.forward_root/"research"/VERSION
        with self.outer.transaction():
            self.ps=native_json(self.prior,self.primary/"ALLOCATION_ACCOUNTING_V3.json",self.plan["primary_accounting_state_sha256"])
            self.os=native_json(self.prior,self.old/"ALLOCATION_STATE.json",self.plan["old_completion_state_sha256"])
            if (self.ps["retained_bytes"]!=PRIMARY_RETAINED or self.os["retained_bytes"]!=OLD_RETAINED
                    or self.ps["peak_bytes"]!=PRIMARY_PEAK or self.os["peak_bytes"]!=OLD_PEAK):
                raise ValueError("existing primary/old caps changed")
            ref=self.ps["baseline_prior_inode_ref"];path=self.primary/ref["id"]
            self.prior.validate_reference(path,ref["sha256"])
            self.pb=json.loads(gzip.decompress(path.read_bytes()))
            statepath=self.destination/"ALLOCATION_STATE.json"
            if not statepath.exists():
                if self.destination.exists():
                    raise ValueError("incomplete supplemental initialization retained; explicit recovery required, no rebaseline")
                physical=self.prior._scan()["forward_physical_bytes"]
                self.cb=self.h.generation_inventory(self.prior._roots)
                if sum(self.cb.values())!=physical: raise ValueError("supplement baseline differs from native physical scan")
                self.baseline=physical;self.primary_floor=0
                usage=self._usage()
                self.primary_floor=usage["primary16_charged_bytes"]
                self._admit(PEAK)
                self.prior.register_root(self.destination)
                baselinebody=gzip.compress(enc(self.cb),mtime=0)
                bp=self.destination/"BASELINE_NATIVE_GENERATIONS.json.gz"
                self.prior.write_bytes(bp,baselinebody)
                state=dict(version=VERSION,allocation_sha256=allocation_sha256,baseline_prior_bytes=physical,
                    primary_charge_floor_bytes=self.primary_floor,primary_accounting_state_sha256=self.plan["primary_accounting_state_sha256"],
                    old_completion_state_sha256=self.plan["old_completion_state_sha256"],
                    baseline_ref=dict(id=bp.name,bytes=len(baselinebody),sha256=sha(baselinebody)),
                    retained_bytes=RETAINED,peak_bytes=PEAK,unchanged_primary_retained_bytes=PRIMARY_RETAINED,
                    unchanged_old_completion_retained_bytes=OLD_RETAINED)
                self.prior.write_bytes(statepath,enc(state))
            state=native_json(self.prior,statepath)
            if state["allocation_sha256"]!=allocation_sha256 or state["version"]!=VERSION:
                raise ValueError("existing supplement cannot be reset")
            self.baseline=state["baseline_prior_bytes"];self.primary_floor=state["primary_charge_floor_bytes"]
            ref=state["baseline_ref"];path=self.destination/ref["id"]
            self.prior.validate_reference(path,ref["sha256"]);baselinebody=path.read_bytes()
            if len(baselinebody)!=ref["bytes"]: raise ValueError("supplement baseline size differs")
            self.cb=json.loads(gzip.decompress(baselinebody))
            if sum(self.cb.values())!=self.baseline: raise ValueError("supplement baseline physical binding differs")
            self._admit(0);self._usage()

    def _usage(self):
        physical=self.prior._scan()["forward_physical_bytes"]
        result=accounting(self.h.unique_bytes(self.old),self.ps["old_charged_at_registration"],
            physical-self.os["baseline_prior_bytes"],self.h.unique_bytes(self.primary),self.primary_floor,
            physical-self.ps["baseline_prior_bytes"],self.h.unique_bytes(self.destination),physical-self.baseline,
            self.h.generation_inventory([self.primary]),self.pb,self.h.generation_inventory([self.destination]),self.cb)
        if result["old8_charged_bytes"]>OLD_RETAINED or result["primary16_charged_bytes"]>PRIMARY_RETAINED:
            raise ValueError("unchanged old8/primary16 retained cap exceeded; preserve evidence")
        if result["supplement_charged_bytes"]>RETAINED: raise ValueError("supplement retained cap exceeded")
        return dict(result,prior_physical_bytes=physical)

    def _admit(self,incoming):
        self.outer._refresh();self.outer._require(incoming)
        self.outer.complete_peer._refresh();self.outer.complete_peer._require(CAPTURE+incoming)
        self.prior._refresh();usage=self._usage()
        self.prior._require(PROTECTED_PRIOR+usage["old8_charged_bytes"]+PRIMARY_RETAINED+PEAK)

    def reserve(self,expected_bytes,failure=False):
        if type(expected_bytes)is not int or expected_bytes<0: raise ValueError("finite nonnegative reservation required")
        with self.outer.transaction():
            self._admit(expected_bytes);usage=self._usage()
            if usage["supplement_charged_bytes"]+expected_bytes+(0 if failure else FAILURE)>RETAINED:
                raise ValueError("supplement retained reservation exhausted")
            return usage

    def _path(self,name,namespace):
        name=Path(name)
        if name.is_absolute() or not name.parts or any(x in {".",".."}for x in name.parts): raise ValueError("relative immutable member name required")
        if namespace not in {"PRIMARY","DEF_REMAINDER"}: raise ValueError("explicit known namespace required")
        return (self.primary if namespace=="PRIMARY" else self.destination)/name

    def read(self,name,sha256,namespace=None):
        with self.outer.transaction():
            self._admit(0)
            if namespace is None:
                found=[n for n in ["PRIMARY","DEF_REMAINDER"] if self._path(name,n).exists()]
                if len(found)!=1: raise ValueError("missing or ambiguous native artifact namespace")
                namespace=found[0]
            path=self._path(name,namespace);self.prior.validate_reference(path,sha256);body=path.read_bytes()
            if sha(body)!=sha256: raise ValueError("native artifact readback changed")
            return body

    def read_many(self,references):
        """One shared transaction; retain every native member integrity check."""
        references=list(references)
        ids=[ref["id"] for ref in references]
        if len(ids)!=len(set(ids)):raise ValueError("batch member IDs must be unique")
        for ref in references:
            if (ref.get("namespace") not in {"PRIMARY","DEF_REMAINDER"}
                    or type(ref.get("bytes"))is not int or ref["bytes"]<0
                    or not isinstance(ref.get("sha256"),str)or len(ref["sha256"])!=64):
                raise ValueError("exact namespace/hash/size reference required")
        bodies={}
        with self.outer.transaction():
            self._admit(0)
            for ref in references:
                path=self._path(ref["id"],ref["namespace"])
                self.prior.validate_reference(path,ref["sha256"])
                body=path.read_bytes()
                if len(body)!=ref["bytes"]or sha(body)!=ref["sha256"]:
                    raise ValueError("batch native member hash/size changed")
                bodies[ref["id"]]=body
            self._admit(0)
        return bodies

    def put(self,name,body,failure=False):
        if not isinstance(body,bytes): raise TypeError("exact immutable bytes required")
        path=self._path(name,"DEF_REMAINDER")
        with self.outer.transaction():
            self._admit(len(body));usage=self._usage()
            if path.exists(): self.prior.validate_reference(path,sha(body))
            else:
                if usage["supplement_charged_bytes"]+len(body)+(0 if failure else FAILURE)>RETAINED:
                    raise ValueError("supplement retained/failure reservation exhausted")
                self.prior.write_bytes(path,body);self.prior.validate_reference(path,sha(body))
            self._usage()
        return dict(id=str(name),bytes=len(body),sha256=sha(body),namespace="DEF_REMAINDER")

    def checkpoint(self):
        with self.outer.transaction():
            self._admit(0);old=self.outer.verify_retained_checkpoint();usage=self._usage()
            return dict(state="PASS_NATIVE_AND_UNCHANGED_OLD8_PRIMARY16_PLUS_SUPPLEMENT8",**usage,
                retained_cap=RETAINED,peak_cap=PEAK,unchanged_primary_retained_cap=PRIMARY_RETAINED,
                unchanged_primary_peak_cap=PRIMARY_PEAK,unchanged_old_completion_retained_cap=OLD_RETAINED,
                unchanged_old_completion_peak_cap=OLD_PEAK,protected_prior_plan_bytes=PROTECTED_PRIOR,
                unchanged_capture_reserve_bytes=CAPTURE,old_wave_headroom_bytes=old["wave_retained_headroom_bytes"],
                complete_accounted_bytes=old["matched12_complete_accounted_bytes"],
                unchanged_complete_cap_bytes=old["matched12_complete_limit_bytes"])

# Allows the source-only scorer adapter to retain its constructor interface.
ProfileIncrementStore=RemainderStore
