"""Finite fictional fourth-peer checks; no real managed store is opened."""
import copy,hashlib,importlib.util,json,os,resource,signal,sys,tempfile,time
from pathlib import Path
from types import SimpleNamespace

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[3]
def load(p,n):
    s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def ref(p):
    b=p.read_bytes();return {"path":str(p),"bytes":len(b),"sha256":hashlib.sha256(b).hexdigest()}

def run():
    start=time.monotonic();cpu=time.process_time()
    resource.setrlimit(resource.RLIMIT_CPU,(20,21));resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,)*2)
    signal.alarm(30)
    helper=load(ROOT/'tools/category_topfive_matched12_storage_v1.py','fictional_fourth_helper')
    prepared=helper.prepare(ROOT) # metadata only; never open_store()
    sp=prepared['sp'];module=prepared['module']
    market=load(sp['original_helper']['path'],'fictional_fourth_market')
    base=market.load_frozen(sp['forward_implementation']['path'],sp['legacy_library_root'])
    L=base.legacy;checks=[]
    def ok(name,condition):
        assert condition,name;checks.append(name)
    def rejected(name,call,kind=L.StorageIntegrityError):
        try:call()
        except kind:checks.append(name)
        else:raise AssertionError(name)
    with tempfile.TemporaryDirectory(prefix='fictional-matched12-',dir='/tmp') as td:
        parent=Path(td);old_policy={"storage":{"version":L.VERSION,"limit_bytes":module.LEGACY_LIMIT},
            "namespaces":{"private_retention_bytes":module.LEGACY_LIMIT}}
        old=L.OperationalStorage(parent/'old'/'cache',old_policy)
        old.write_bytes(old.source_root/'old-proof',b'fictional retained evidence')
        before={str(p):(p.stat().st_ino,p.stat().st_mode,p.read_bytes()) for p in
            [old.registry_path,old.lock_path,*[r/L._OWNER for r in old._roots if r!=old.control_root]]}
        policy_file=parent/'fictional-policy.json';policy_file.write_text(json.dumps(old_policy))
        calls={"peer":0,"reserve":0,"block":False}
        class Peer:
            def __init__(self):
                self.forward_root=parent/'oldpeer';self._roots=[self.forward_root]
                self.prior_forward=SimpleNamespace(_roots=[parent/'priorpeer'])
                self.legacy=old;self._thread_lock=old._thread_lock;self._local=old._local
                self.registration_lock=json.loads(old.registry_path.read_bytes())['lock']
            def _refresh(self):old._refresh()
            def _scan(self):
                used=old._scan()['physical_bytes']
                return {"legacy_physical_bytes":used,"category_topfive_combined_accounted_bytes":used+1024,
                    "category_topfive_combined_limit_bytes":module.OLD_COMPLETE_LIMIT}
            def _require(self,n):
                assert n==module.OLD_UPCOMING_RESERVE
                calls['reserve']+=1
                if calls['block']:raise L.StorageQuotaError('fictional old upcoming reserve unavailable')
                return self._scan()
        def peer():calls['peer']+=1;return Peer()
        a={"version":module.VERSION,"approved_parent":str(parent),"store_policy":{"storage":{
            "version":base.VERSION,"forward_root":str(parent/module.VERSION),"limit_bytes":module.NEW_LIMIT,
            "joint_limit_bytes":module.LEGACY_LIMIT+module.NEW_LIMIT,"legacy_limit_bytes":module.LEGACY_LIMIT,
            "legacy_registry_sha256_at_registration":ref(old.registry_path)['sha256'],
            "legacy_lock_at_registration":json.loads(old.registry_path.read_bytes())['lock']}},
            "legacy_policy":old_policy,"old_complete_limit_bytes":module.OLD_COMPLETE_LIMIT,
            "new_complete_limit_bytes":module.COMPLETE_LIMIT,"old_upcoming_reserve_bytes":module.OLD_UPCOMING_RESERVE,
            "wave_retained_limit_bytes":module.WAVE_RETAINED_LIMIT,"new_storage_module_sha256":ref(Path(module.__file__))['sha256'],
            "source_bindings":{"actual_module":ref(Path(module.__file__))},"old_policy_bindings":{"fictional":ref(policy_file)}}
        bad=copy.deepcopy(a);bad['old_complete_limit_bytes']+=1
        rejected('oldlimit drift before old attachment',lambda:module.build_storage_class(base,complete_peer_factory=peer,allocation=bad))
        ok('rejected allocation did not attach peer',calls['peer']==0)
        cls=module.build_storage_class(base,complete_peer_factory=peer,allocation=a)
        ok('immutable writer inherited',cls.write_bytes is L.OperationalStorage.write_bytes)
        ok('stream capture inherited',cls.capture_writes is L.OperationalStorage.capture_writes)
        ok('restore validator inherited',cls.validate_reference is L.OperationalStorage.validate_reference)
        store=cls(old.cache)
        ok('same permanent flock',store.lock_path==old.lock_path and store.registration_lock==Peer().registration_lock)
        ok('same thread lock context',store._thread_lock is old._thread_lock and store._local is old._local)
        ok('new root disjoint',not any(module._overlap(store.forward_root,r) for r in old._roots))
        body=b'fictional new immutable forecast';path=store.live_root/'prediction'
        store.write_bytes(path,body)
        u=store.verify_retained_checkpoint()
        ok('complete usage nonduplicated',u['matched12_complete_accounted_bytes']==u['old_complete_accounted_bytes']+u['new_peer_physical_bytes'])
        ok('limits unchanged',u['old_complete_limit_bytes']==module.OLD_COMPLETE_LIMIT and u['new_peer_limit_bytes']==module.NEW_LIMIT)
        ok('reservation checked',calls['reserve']>0)
        ok('cas readback',store.validate_reference(path,hashlib.sha256(body).hexdigest())['bytes']==len(body))
        frozen={str(p):(p.stat().st_ino,p.stat().st_mode,p.read_bytes()) for p in map(Path,before)}
        ok('old controls immutable',before==frozen)
        ro=cls.attach_readonly(old.cache,market.attach_readonly_forward)
        ok('readonly reference restored',ro.validate_reference(path,hashlib.sha256(body).hexdigest())['bytes']==len(body))
        ok('readonly identical accounting',ro.verify_retained_checkpoint()==store.verify_retained_checkpoint())
        n=calls['peer'];d=store._matched_descriptor_path;mode=d.stat().st_mode;d.chmod(0o644)
        rejected('mutable descriptor before old peer',lambda:cls.attach_readonly(old.cache,market.attach_readonly_forward))
        ok('bad descriptor did not attach peer',calls['peer']==n);d.chmod(mode)
        with store.transaction():
            rejected('new128MiB incoming peak rejected',lambda:store._require(module.NEW_LIMIT+1),L.StorageQuotaError)
        calls['block']=True
        rejected('upcoming old reservation protected',lambda:store.write_bytes(store.live_root/'blocked',b'must not write'),L.StorageQuotaError)
        ok('blocked destination absent',not (store.live_root/'blocked').exists());calls['block']=False
        require,refresh=store._require,store._refresh
        store._require=lambda n:{'new_peer_physical_bytes':module.WAVE_RETAINED_LIMIT+1}
        store._refresh=lambda:None
        rejected('retained96MiB checkpoint enforced',store.verify_retained_checkpoint,L.StorageQuotaError)
        store._require,store._refresh=require,refresh
        # Existing outer descriptor validation must precede old class factories.
        dummy_policy={'store_policy':{'storage':{'forward_root':str(parent/'missing-old-outer')}}}
        rejected('old outer descriptor checked before attachment',lambda:module.attach_readonly_complete_peer(base,
            legacy_cache=old.cache,market_policy=dummy_policy,legacy_policy=old_policy,prior_policy={},
            metadata16_policy={},metadata8_policy={},market_module=SimpleNamespace(VERSION='fake'),
            metadata16_module=None,metadata8_module=None))
        ok('evidence preserved after failures',path.read_bytes()==body)
        ok('retained checkpoint still valid',store.verify_retained_checkpoint()['new_peer_physical_bytes']<module.WAVE_RETAINED_LIMIT)
    signal.alarm(0)
    return {"state":"PASS_FICTIONAL_ACTUAL_INHERITED_CAS_WITH_SIMULATED_OLD_COMPLETE_PEER",
        "checks":checks,"check_count":len(checks),"source_sha256":ref(Path(module.__file__))['sha256'],
        "fixture_sha256":ref(Path(__file__))['sha256'],"real_managed_store_opened":False,
        "NFL_decode_fits_forecasts_scoring_HTTP":0,"limitations":["Old complete aggregate simulated; real peer initialization/inventory still requires independent root review and explicit GO.","No off-host restoration tested."],
        "actual":{"CPU_seconds":time.process_time()-cpu,"wall_seconds":time.monotonic()-start,
            "RSS_bytes":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024}}

if __name__=='__main__':print(json.dumps(run(),sort_keys=True))
