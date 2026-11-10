"""Finite suballocation on an EXISTING approved prior peer; no quota changes.

Every write keeps the original shared lock and all native integrity/quota
checks, plus the complete accounting stack and unchanged capture reservation.
"""
from __future__ import annotations
import hashlib,json,os
from pathlib import Path

ALLOCATION='f123cd5ffd6f4a204a76c68bf63817cce63cecd7021543a23503d0233cc3eb26'
GO='PLAYER-CONTEXT-COMPLETION-DECISION-01-A-PRIOR-FORWARD-GO-v1'
VERSION='PLAYER-CONTEXT-COMPLETION-DECISION-01-A-forward-v1'
RETAINED=8*1024**2
PEAK=12*1024**2
PROTECTED_PRIOR=343932928
CAPTURE=80*1024**2

def digest(b):return hashlib.sha256(b).hexdigest()
def encoded(x):return(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()

class CompletionStore:
 def __init__(self,root,allocation_path,allocation_sha256,*,root_go):
  if root_go!=GO:raise ValueError('explicit completion allocation GO required')
  self.root=Path(root).resolve();raw=Path(allocation_path).read_bytes()
  if digest(raw)!=allocation_sha256:raise ValueError('completion allocation changed')
  self.plan=json.loads(raw)
  for k,v in [('version',VERSION),('retained_bytes',RETAINED),('peak_bytes',PEAK),('protected_prior_plan_bytes',PROTECTED_PRIOR),('unchanged_capture_reserve_bytes',CAPTURE)]:
   if self.plan.get(k)!=v:raise ValueError('exact finite existing-cap allocation required: '+k)
  for p,h in self.plan['code_sha256'].items():
   if digest((self.root/p).read_bytes())!=h:raise ValueError('bound completion storage code changed')
  from tools.category_topfive_matched12_storage_v1 import open_store,GO as OLD_GO
  self.outer,_=open_store(self.root,allocation_sha256=ALLOCATION,root_go=OLD_GO,readonly=True)
  self.prior=self.outer.complete_peer.prior_forward
  if self.outer._local is not self.prior._local or self.outer._thread_lock is not self.prior._thread_lock or self.outer.lock_path!=self.prior.lock_path:
   raise ValueError('existing shared reentrant lock identity required')
  self.destination=self.prior.forward_root/'research'/VERSION
  with self.outer.transaction():
   self._admit(PEAK)
   if not self.destination.exists():
    baseline=self.prior._scan()['forward_physical_bytes']
    self.prior.register_root(self.destination)
    state=encoded(dict(version=VERSION,allocation_sha256=allocation_sha256,baseline_prior_bytes=baseline,retained_bytes=RETAINED,peak_bytes=PEAK,protected_prior_plan_bytes=PROTECTED_PRIOR,capture_reserve_bytes=CAPTURE))
    self.prior.write_bytes(self.destination/'ALLOCATION_STATE.json',state)
   statepath=self.destination/'ALLOCATION_STATE.json'
   self.prior.validate_reference(statepath)
   self.state=json.loads(statepath.read_bytes())
   if self.state['allocation_sha256']!=allocation_sha256 or self.state['version']!=VERSION:raise ValueError('existing allocation cannot be reset')
   self.baseline=self.state['baseline_prior_bytes']
   self._usage()
 def _admit(self,incoming):
  self.outer._refresh();self.outer._require(incoming)
  self.outer.complete_peer._refresh();self.outer.complete_peer._require(CAPTURE+incoming)
  self.prior._refresh();self.prior._require(PROTECTED_PRIOR+PEAK)
 def _usage(self):
  u=self.prior._scan();seen=set();logical=0
  if self.destination.exists():
   for p in self.destination.rglob('*'):
    if p.is_symlink():raise ValueError('completion namespace symlink forbidden')
    if p.is_file():
     st=p.stat();key=(st.st_dev,st.st_ino)
     if key not in seen:seen.add(key);logical+=st.st_size
  delta=max(0,u['forward_physical_bytes']-self.baseline)
  return dict(namespace_unique_bytes=logical,prior_delta_including_controls_or_orphans=delta,charged_bytes=max(logical,delta),prior_physical_bytes=u['forward_physical_bytes'])
 def _path(self,name):
  p=Path(name)
  if p.is_absolute()or not p.parts or any(x in {'..','.'}for x in p.parts):raise ValueError('relative immutable artifact name required')
  return self.destination/p
 def reserve(self,expected_bytes):
  if type(expected_bytes)is not int or expected_bytes<0:raise ValueError('nonnegative finite reservation required')
  with self.outer.transaction():
   self._admit(expected_bytes);u=self._usage()
   if u['charged_bytes']+expected_bytes>RETAINED:raise ValueError('completion retained reservation exhausted before fit/write')
  return u
 def put(self,name,body):
  if not isinstance(body,bytes):raise TypeError('exact immutable bytes required')
  path=self._path(name)
  with self.outer.transaction():
   self._admit(len(body));u=self._usage()
   if path.exists():
    self.prior.validate_reference(path,digest(body))
    if path.read_bytes()!=body:raise ValueError('immutable completion artifact conflict')
   else:
    if u['charged_bytes']+len(body)>RETAINED:raise ValueError('completion retained envelope exceeded; no write')
    self.prior.write_bytes(path,body);self.prior.validate_reference(path,digest(body))
   if self._usage()['charged_bytes']>RETAINED:raise ValueError('completion checkpoint exceeds retained envelope; evidence preserved')
  return dict(id=str(Path(name)),bytes=len(body),sha256=digest(body))
 def read(self,name,sha256):
  with self.outer.transaction():
   self._admit(0);p=self._path(name);self.prior.validate_reference(p,sha256);b=p.read_bytes()
   if digest(b)!=sha256:raise ValueError('completion readback changed')
   return b
 def validate_reference(self,name,sha256):
  b=self.read(name,sha256);return dict(id=str(name),bytes=len(b),sha256=sha256)
 def checkpoint(self):
  with self.outer.transaction():
   self._admit(0);old=self.outer.verify_retained_checkpoint();u=self._usage()
   if u['charged_bytes']>RETAINED:raise ValueError('new retained suballocation exceeded')
   return dict(state='PASS_EXISTING_AND_NEW_CAPS',**u,retained_cap=RETAINED,peak_cap=PEAK,protected_prior_plan_bytes=PROTECTED_PRIOR,unchanged_capture_reserve_bytes=CAPTURE,old_wave_headroom_bytes=old['wave_retained_headroom_bytes'],complete_accounted_bytes=old['matched12_complete_accounted_bytes'],unchanged_complete_cap_bytes=old['matched12_complete_limit_bytes'])
