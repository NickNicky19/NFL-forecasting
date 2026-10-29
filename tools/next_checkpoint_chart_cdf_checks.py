"""Zero-NFL/zero-fit full-GO, signed-lattice and exact-CRPS fixtures."""
from pathlib import Path
import argparse,copy,hashlib,importlib.util,json,os,resource,signal,sys,time
BASE=Path(__file__).resolve().parents[1]

def sha(b):return hashlib.sha256(b).hexdigest()
def refcheck(ref):
 p=Path(ref['path']);assert p.resolve()==p;b=p.read_bytes();assert len(b)==ref['bytes']and sha(b)==ref['sha256'];return p

def load(ref,name):
 p=refcheck(ref);s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m


def main():
 parser=argparse.ArgumentParser();parser.add_argument('--plan',required=True);parser.add_argument('--sha256',required=True);a=parser.parse_args();raw=Path(a.plan).read_bytes();assert sha(raw)==a.sha256
 p=json.loads(raw);assert p['state']=='ROOT_AUTHORIZED_ZERO_NFL_SOFTWARE_CHECK'
 assert p['resources']=={'CPU_seconds':15,'wall_seconds':30,'RSS_bytes':384*1024**2,'invocations':1,'fits':0,'NFL_values':0,'HTTP':0,'managed_writes':0,'automatic_retries':0}
 start=time.monotonic();cpu=time.process_time();resource.setrlimit(resource.RLIMIT_CPU,(15,16));signal.signal(signal.SIGALRM,lambda *unused:os._exit(124));signal.alarm(29)
 sys.dont_write_bytecode=True
 for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','ARROW_NUM_THREADS']:os.environ[key]='1'
 run=load(p['runner'],'cdf_check_runner')
 attempts={'children':0,'sockets':0}
 def deny(event,unused):
  if event.startswith('socket.'):
   attempts['sockets']+=1;raise ValueError('fixture sockets forbidden')
  if event in {'subprocess.Popen','os.system','os.fork','os.posix_spawn'}:
   attempts['children']+=1;raise ValueError('fixture children forbidden')
 sys.addaudithook(deny)
 run.bootstrap_threadpool(p['technical_bootstrap'])
 sys.path[:0]=[str(BASE/'tools'),str(BASE)]
 build=load(p['builder'],'cdf_check_builder')
 import numpy as np
 science=json.loads(refcheck(p['scientific_preseal']).read_bytes());science['state']='ROOT_AND_INDEPENDENT_SEALED';science['execution_authorized']=True;science['independent_review']='PASS';science['root_registration']={'registered_by':'/root'}
 fake_sha='a'*64;go=copy.deepcopy(science['GO_template']);go['plan_sha256']=fake_sha
 caps=run.validate_plan_go(science,go,fake_sha);assert caps['maximum_trees']==32
 rejected=[]
 for name in ['state','plan_sha256','registered_by','independent_review','predictive_fits','source_native_broad_zero_qualification','code_sha256']:
  broken=copy.deepcopy(go);broken.pop(name)
  try:run.validate_plan_go(science,broken,fake_sha)
  except (ValueError,KeyError):rejected.append(name)
  else:raise AssertionError('missing GO field accepted:'+name)
 assert np.array_equal(build.lattice([-1.02,-.04,0,.02,6.18]),np.array([-51,-2,0,1,309],dtype=float))
 try:build.lattice([.01])
 except ValueError:pass
 else:raise AssertionError('odd-cent label silently rounded')
 prior=build.engine.SupportPrior('signed_integer',center=-2,q=.5,n=5)
 support=np.array([-4.,0.,3.]);weights=np.array([[.2,.5,.3]])
 law=build.engine.MixtureBatch(support,weights,prior)
 assert abs(law.mean[0]/50-(-.0001))<1e-12
 assert abs(law.quantile(.5)[0]/50)<1e-12
 assert np.isfinite(law.logpmf([-100])).all()
 grid=np.arange(-128,129,dtype=float);many=build.engine.MixtureBatch(support,np.repeat(weights,len(grid),axis=0),prior)
 independent=np.sum((many.cdf(grid)-(grid>=-3).astype(float))**2)/50
 exact=law.crps([-3])[0]/50
 assert abs(exact-independent)<1e-11
 pools=build.engine.threadpool_limits
 with pools(limits=2):
  from threadpoolctl import threadpool_info
  threads=threadpool_info();assert all(item['num_threads']<=2 for item in threads)
 use={'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-start,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024}
 assert use['CPU_seconds']<=15 and use['wall_seconds']<=30 and use['RSS_bytes']<=384*1024**2
 assert not any(attempts.values())
 print(json.dumps({'state':'FULL_GO_AND_SIGNED_CHART_CDF_FICTIONAL_CHECKS_PASS','plan_sha256':a.sha256,'runner_sha256':p['runner']['sha256'],'builder_sha256':p['builder']['sha256'],'required_GO_field_rejections':rejected,'lattice_scale':50,'odd_cent_rejected':True,'signed_tail_supported':True,'CRPS_formula_matches_independent_CDF_sum':True,'resources':use,'attempted_children_sockets':attempts,'NFL_values_fits_models_HTTP_managedwrites':0}))
 signal.alarm(0)

if __name__=='__main__':main()
