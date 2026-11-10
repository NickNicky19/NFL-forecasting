"""New finite timing-sensitivity allocation; all three older caps stay bound.

Only proven new generations owned by this namespace are excluded from older
delta charges. Aliases to baseline objects, unrelated growth and registry bytes
are never credited. All bytes remain in the same approved native parent.
"""
from __future__ import annotations
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path

VERSION = 'PROFILE-INCREMENT-CLOSURE-AND-NEXT-02-A-FRESHNESS-v1'
GO = VERSION + '-ROOT-AND-INDEPENDENT-GO'
RETAINED, PEAK, FAILURE = 16*1024**2, 20*1024**2, 2*1024**2
OLD_PATH = 'nfl_lab/profile_increment_a_def_remainder_storage_v1.py'
OLD_SHA = '0fd6ded236f1ce01bf63783b7255570ba884869f353a412d5a9c1deb494aff59'
OLD_ALLOCATION = 'reports/abc-championship/profile-increment-to-release-01/REMAINDER_NATIVE_ALLOCATION_V1.json'
OLD_ALLOCATION_SHA = '757f49107c919b34740283cd42fc75c449e4cba97f51592f69d5cb7e96f9f4d5'

def sha(b): return hashlib.sha256(b).hexdigest()
def enc(x): return (json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()

def bound_older(root):
    p=Path(root)/OLD_PATH
    if sha(p.read_bytes())!=OLD_SHA: raise ValueError('frozen older guard changed')
    spec=importlib.util.spec_from_file_location('freshness_bound_older_native',p)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    return m

def new_owned(current,baseline):
    """SET membership by immutable physical generation, never filename credit."""
    out={}
    for k,v in current.items():
        if type(v)is not int or v<0: raise ValueError('invalid physical generation')
        if k in baseline:
            if baseline[k]!=v: raise ValueError('baseline generation size changed')
        else: out[k]=v
    return out

def adjusted_physical(physical,current,baseline):
    owned=new_owned(current,baseline)
    if sum(owned.values())>physical: raise ValueError('owned bytes exceed all physical bytes')
    return physical-sum(owned.values()),sum(owned.values())

class FreshnessStore:
    def __init__(self,root,allocation_path,allocation_sha256,*,root_go):
        if root_go!=GO: raise ValueError('exact reviewed timing-allocation GO required')
        self.root=Path(root).resolve();body=Path(allocation_path).read_bytes()
        if sha(body)!=allocation_sha256: raise ValueError('allocation identity differs')
        self.plan=json.loads(body)
        expect=dict(version=VERSION,state='ROOT_AND_INDEPENDENT_REVIEWED_ALLOCATION',
                    retained_bytes=RETAINED,peak_bytes=PEAK,failure_reserve_bytes=FAILURE)
        if any(self.plan.get(k)!=v for k,v in expect.items()):raise ValueError('finite allocation contract differs')
        if not self.plan.get('independent_review_sha256'):raise ValueError('missing independent review')
        for p,h in self.plan['code_sha256'].items():
            if sha((self.root/p).read_bytes())!=h:raise ValueError('bound allocation source changed')
        self.oldguard=bound_older(self.root);o=self.oldguard
        if sha((self.root/OLD_ALLOCATION).read_bytes())!=OLD_ALLOCATION_SHA:raise ValueError('older allocation changed')
        self.h=o.helpers(self.root);self.outer,self.prior=o.attach(self.root)
        self.primary=self.prior.forward_root/'research'/o.PRIMARY
        self.old=self.prior.forward_root/'research'/o.OLD
        self.remainder=self.prior.forward_root/'research'/o.VERSION
        self.destination=self.prior.forward_root/'research'/VERSION
        with self.outer.transaction():
            self._load_older()
            statepath=self.destination/'ALLOCATION_STATE.json'
            if not statepath.exists():
                if self.destination.exists():raise ValueError('interrupted new namespace cannot rebaseline')
                self.baseline=self.prior._scan()['forward_physical_bytes']
                self.fb=self.h.generation_inventory(self.prior._roots)
                if sum(self.fb.values())!=self.baseline:raise ValueError('new baseline does not bind physical inventory')
                self._admit(PEAK)
                self.prior.register_root(self.destination)
                b=gzip.compress(enc(self.fb),mtime=0);bp=self.destination/'BASELINE_NATIVE_GENERATIONS.json.gz'
                self.prior.write_bytes(bp,b)
                state=dict(version=VERSION,allocation_sha256=allocation_sha256,baseline_prior_bytes=self.baseline,
                    baseline_ref=dict(id=bp.name,bytes=len(b),sha256=sha(b)),retained_bytes=RETAINED,peak_bytes=PEAK,
                    older_state_hashes=self.older_state_hashes)
                self.prior.write_bytes(statepath,enc(state))
            s=o.native_json(self.prior,statepath)
            if s['version']!=VERSION or s['allocation_sha256']!=allocation_sha256:raise ValueError('existing timing allocation cannot reset')
            if s['older_state_hashes']!=self.older_state_hashes:raise ValueError('older accounting state changed')
            self.baseline=s['baseline_prior_bytes'];r=s['baseline_ref'];p=self.destination/r['id']
            self.prior.validate_reference(p,r['sha256']);b=p.read_bytes()
            if len(b)!=r['bytes']or sha(b)!=r['sha256']:raise ValueError('timing baseline readback differs')
            self.fb=json.loads(gzip.decompress(b))
            if sum(self.fb.values())!=self.baseline:raise ValueError('timing baseline byte sum differs')
            self._admit(0)

    def _load_older(self):
        o=self.oldguard
        paths={'primary':self.primary/'ALLOCATION_ACCOUNTING_V3.json','old':self.old/'ALLOCATION_STATE.json',
               'remainder':self.remainder/'ALLOCATION_STATE.json'}
        self.older_state_hashes={k:sha(p.read_bytes())for k,p in paths.items()}
        expected=self.plan['older_state_hashes']
        if self.older_state_hashes!=expected:raise ValueError('named older state bytes changed')
        self.ps=o.native_json(self.prior,paths['primary'],expected['primary'])
        self.os=o.native_json(self.prior,paths['old'],expected['old'])
        self.rs=o.native_json(self.prior,paths['remainder'],expected['remainder'])
        if (self.ps['retained_bytes']!=o.PRIMARY_RETAINED or self.ps['peak_bytes']!=o.PRIMARY_PEAK
            or self.os['retained_bytes']!=o.OLD_RETAINED or self.os['peak_bytes']!=o.OLD_PEAK
            or self.rs['retained_bytes']!=o.RETAINED or self.rs['peak_bytes']!=o.PEAK):raise ValueError('old cap changed')
        self.primary_floor=self.rs['primary_charge_floor_bytes']
        self.pb=self._baseline(self.primary,self.ps['baseline_prior_inode_ref'])
        self.rb=self._baseline(self.remainder,self.rs['baseline_ref'])

    def _baseline(self,folder,ref):
        p=folder/ref['id'];self.prior.validate_reference(p,ref['sha256']);b=p.read_bytes()
        if 'bytes'in ref and len(b)!=ref['bytes']:raise ValueError('older baseline size differs')
        return json.loads(gzip.decompress(b))

    def _usage(self):
        o=self.oldguard;physical=self.prior._scan()['forward_physical_bytes']
        pg=self.h.generation_inventory([self.primary]);rg=self.h.generation_inventory([self.remainder])
        og=self.h.generation_inventory([self.old])
        # Completed older namespaces are frozen before this baseline. Reject
        # resumed writers/alias overlap rather than crediting a shared new
        # generation once here and again inside older ownership accounting.
        if any(new_owned(g,self.fb) for g in (pg,rg,og)):
            raise ValueError('older namespace changed after freshness phase barrier')
        # Remove only physically new owned generations from older delta views.
        virtual,owned=adjusted_physical(physical,self.h.generation_inventory([self.destination]),self.fb)
        u=o.accounting(self.h.unique_bytes(self.old),self.ps['old_charged_at_registration'],virtual-self.os['baseline_prior_bytes'],
            self.h.unique_bytes(self.primary),self.primary_floor,virtual-self.ps['baseline_prior_bytes'],
            self.h.unique_bytes(self.remainder),virtual-self.rs['baseline_prior_bytes'],
            pg,self.pb,rg,self.rb)
        fresh=max(self.h.unique_bytes(self.destination),physical-self.baseline)
        if u['old8_charged_bytes']>o.OLD_RETAINED or u['primary16_charged_bytes']>o.PRIMARY_RETAINED or u['supplement_charged_bytes']>o.RETAINED:
            raise ValueError('unchanged older retained cap exceeded')
        if fresh>RETAINED:raise ValueError('timing retained cap exceeded')
        return dict(u,prior_physical_bytes=physical,freshness_charged_bytes=fresh,proven_freshness_owned_bytes=owned)

    def _admit(self,incoming):
        o=self.oldguard;self.outer._refresh();self.outer._require(incoming)
        self.outer.complete_peer._refresh();self.outer.complete_peer._require(o.CAPTURE+incoming)
        self.prior._refresh();self._usage()
        self.prior._require(o.PROTECTED_PRIOR+o.OLD_RETAINED+o.PRIMARY_RETAINED+o.RETAINED+PEAK+incoming)

    def reserve(self,n,failure=False):
        if type(n)is not int or n<0:raise ValueError('nonnegative reservation required')
        with self.outer.transaction():
            self._admit(n);u=self._usage()
            if u['freshness_charged_bytes']+n+(0 if failure else FAILURE)>RETAINED:raise ValueError('timing reservation exhausted')
            return u

    def _path(self,name,namespace):
        p=Path(name)
        if p.is_absolute()or not p.parts or any(x in {'.','..'}for x in p.parts):raise ValueError('immutable relative member required')
        roots={'PRIMARY':self.primary,'DEF_REMAINDER':self.remainder,'FRESHNESS':self.destination}
        if namespace not in roots:raise ValueError('explicit supported namespace required')
        return roots[namespace]/p

    def read_many(self,references):
        refs=list(references);ids=[r['id']for r in refs]
        if len(ids)!=len(set(ids)):raise ValueError('duplicate native member IDs')
        out={}
        with self.outer.transaction():
            self._admit(0)
            for r in refs:
                if type(r.get('bytes'))is not int or r['bytes']<0:raise ValueError('native exact size required')
                p=self._path(r['id'],r['namespace']);self.prior.validate_reference(p,r['sha256']);b=p.read_bytes()
                if len(b)!=r['bytes']or sha(b)!=r['sha256']:raise ValueError('native read hash/size differs')
                out[r['id']]=b
            self._admit(0)
        return out

    def read(self,name,sha256,namespace='FRESHNESS'):
        with self.outer.transaction():
            self._admit(0);p=self._path(name,namespace);self.prior.validate_reference(p,sha256);b=p.read_bytes()
            if sha(b)!=sha256:raise ValueError('native readback differs')
            return b

    def put(self,name,body,failure=False):
        if not isinstance(body,bytes):raise TypeError('exact bytes required')
        with self.outer.transaction():
            p=self._path(name,'FRESHNESS')
            if p.exists():
                self._admit(0);self.prior.validate_reference(p,sha(body))
            else:
                self.reserve(len(body),failure);self.prior.write_bytes(p,body)
            self.prior.validate_reference(p,sha(body));self._usage()
        return dict(id=str(name),bytes=len(body),sha256=sha(body),namespace='FRESHNESS')

    def checkpoint(self):
        with self.outer.transaction():
            self._admit(0);q=self.outer.verify_retained_checkpoint()
            return dict(state='PASS_FRESHNESS16_AND_OLDER8_PRIMARY16_REMAINDER8_UNCHANGED',**self._usage(),
                retained_cap=RETAINED,peak_cap=PEAK,protected_prior_plan_bytes=self.oldguard.PROTECTED_PRIOR,
                unchanged_capture_reserve_bytes=self.oldguard.CAPTURE,old_wave_headroom_bytes=q['wave_retained_headroom_bytes'],
                complete_accounted_bytes=q['matched12_complete_accounted_bytes'],complete_limit_bytes=q['matched12_complete_limit_bytes'])
