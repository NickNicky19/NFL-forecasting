import numpy as np
import pytest
from nfl_lab.cdf_engine import SupportPrior
from nfl_lab.threshold_cdf import StableMixtureBatch
from nfl_lab.combined_yard_copula import (vector_quantile, cdf_grid, fit_dependence,
    sum_draws, empirical_sum_law, draw_digest, DRAWS)

def law(atoms=(-2, 0, 5), weights=(.2, .5, .3), b=.05):
    return StableMixtureBatch(atoms, [weights], SupportPrior('signed_integer',center=0,q=.8), prior_weight=b)

def test_vector_inverse_full_tail_and_boundary():
    x=law();p=np.array([[1e-10,.01,.2,.5,.9,1-1e-10]])
    q=vector_quantile(x,p)
    assert (cdf_grid(x,q)>=p).all() and (cdf_grid(x,q-1)<p).all()
    assert q.min() < -2 and q.max()>5
    assert np.array_equal(q[0,3:4],x.quantile(.5))
    for v in [0.,1.,np.nan]:
        with pytest.raises(ValueError):vector_quantile(x,[[v]])

def test_vector_multiple_rows_and_analytic_discrete():
    x=StableMixtureBatch([0,10],[[.75,.25],[.25,.75]],SupportPrior('signed_integer',q=.5),prior_weight=0)
    assert np.array_equal(vector_quantile(x,[[.75,.75001],[.25,.25001]]),[[0,10],[0,10]])

def test_coherent_reproducible_draws_and_dependence():
    x=law();ids=[(2023,1,'fictional-game','fictional-player')]
    s,a,b=sum_draws(x,x,.8,ids)
    assert np.array_equal(s,a+b) and np.array_equal(s,sum_draws(x,x,.8,ids)[0])
    assert np.corrcoef(a[0],b[0])[0,1]>.5
    assert draw_digest(s)==draw_digest(s.copy())
    with pytest.raises(ValueError):sum_draws(x,x,1.,ids)

def test_shrink_no_parameter_search_and_fallback():
    p=np.linspace(.01,.99,100)
    assert np.isclose(fit_dependence(p,p)['rho'],.5)
    assert fit_dependence([],[])['rho']==0
    assert fit_dependence([.5,.5],[.2,.8])['rho']==0

def test_empirical_crps_and_median_addition_counterexample():
    # Each marginal has P(0)=.6; median0+0=0, independent sum median10.
    x=law((0,10),(.6,.4),b=0)
    s,_,_=sum_draws(x,x,0.,[(2023,1,'g','p')]);e=empirical_sum_law(s[0],x.prior)
    assert x.quantile(.5)[0]+x.quantile(.5)[0]==0
    assert e.quantile(.5)[0]==10
    y=7;raw=s[0].astype(float)
    exact=np.mean(np.abs(raw-y))-.5*np.mean(np.abs(raw[:,None]-raw[None,:]))
    assert np.isclose(e.crps([y])[0],exact)

def test_signed_and_no_artificial_push_probability_floor():
    d=np.full(DRAWS,-5,dtype=int);e=empirical_sum_law(d,law().prior)
    assert e.mean[0]==-5 and e.crps([-5])[0]==0
    assert e.cdf([0])[0]==1 and np.isneginf(e.logpmf([0]))[0]

class FictionalDesign:
    def transform(self,q):return np.zeros((len(q),1))

class FictionalForest:
    def apply(self,x):return np.zeros((len(x),1),dtype=int)

@pytest.mark.parametrize('missing',[True,False])
def test_libc_refusal_before_thread_helper_or_heavy_import(tmp_path,monkeypatch,missing):
    import builtins,hashlib
    from pathlib import Path
    from tools.run_cached_combined_yard import run
    libc=Path('/usr/lib/x86_64-linux-gnu/libc.so.6')
    manifest={} if missing else {'libc':dict(path=str(libc),bytes=libc.stat().st_size,sha256='0'*64)}
    original_import=builtins.__import__
    called=[]
    def forbid_heavy(name,*args,**kwargs):
        if name in {'tools.ngboost_law_software_v1','threadpoolctl','joblib','numpy','pandas'}:
            called.append(name);raise AssertionError('libc refusal must precede thread helper/heavy import')
        return original_import(name,*args,**kwargs)
    monkeypatch.setattr(builtins,'__import__',forbid_heavy)
    with pytest.raises(ValueError,match='libc binding|binding changed'):run(manifest)
    assert called==[] and not list(tmp_path.iterdir())

def test_complete_runner_only_fictional_artifacts(tmp_path,monkeypatch):
    import json,hashlib,joblib,os
    import pandas as pd
    from scipy.sparse import csr_matrix
    from nfl_lab.cdf_engine import LeafCDFModel,KEYS
    from tools import run_threshold_cdf_after_audit as shared
    from tools.run_cached_combined_yard import run
    from pathlib import Path
    def ref(p):return dict(path=str(p),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
    spec=json.loads((Path(__file__).parents[1]/'config/combined-yard-copula-v1.json').read_text());spec['state']='FROZEN_ROOT_REVIEWER_SEALED'
    for k in spec['thread_environment']:monkeypatch.setenv(k,'2')
    rp=tmp_path/'fictional-registration.json';rp.write_text(json.dumps(spec));m=dict(registration=ref(rp),inputs={},output=str(tmp_path/'fictional-output'),versions={})
    m['libc']=ref(Path('/usr/lib/x86_64-linux-gnu/libc.so.6'))
    prior=SupportPrior('signed_integer',center=0,q=.5)
    for year in [2022,2023,2024]:
        for target in ['rush_yd','rec_yd','rush_rec_yd']:
            n=2 if target=='rush_yd' else 4
            q=pd.DataFrame(dict(season=[year]*n,week=[1]*n,game_id=['fictional-g']*n,player_id=[f'fictional-{i}'for i in range(n)],team=['FIC']*n,opponent=['SYN']*n,position=['RB','RB','WR','TE'][:n],kickoff_utc=[f'{year}-09-01T12:00:00Z']*n,cutoff_utc=[f'{year}-08-31T12:00:00Z']*n,outcome_available_utc=[f'{year}-09-08T12:00:00Z']*n,feature_max_source_available_utc=[f'{year-1}-01-01T00:00:00Z']*n))
            for i in range(95):q[f'f_fictional_{i}']=1.
            q['f_player_games_prior']=1.;q['f_player_play_rate8']=np.nan
            cat=dict(target=target,support='signed_integer',modeled_roles=['RB','WR','TE'])
            model=LeafCDFModel(cat,'context',FictionalDesign(),FictionalForest(),np.array([0.,10.]),[csr_matrix([[.6,.4]])],{k:prior for k in ['RB','WR','TE']},prior)
            forecast=shared.infer(model,q);label=q.copy();label['actual']=np.arange(n)+2.;label['participation_state']=['played']*n
            scored=shared.infer(model,q,label=label);scored['actual']=label.actual;scored['participation_state']=label.participation_state
            for kind,obj in [('query',q),('forecast',forecast),('scored',scored)]:
                p=tmp_path/f'{year}-{target}-{kind}.parquet';obj.to_parquet(p,index=False);m['inputs'][f'{year}/{target}/{kind}']=ref(p)
            p=tmp_path/f'{year}-{target}.joblib';joblib.dump(model,p);m['inputs'][f'{year}/{target}/model']=ref(p)
            if target=='rush_rec_yd'and year>2022:
                c=scored.copy();c['point']=c['median'];c['primary_role']=True;c['target']=target;c['method']='direct_catboost_medium';c['point_semantics']='median_objective_point_heuristic'
                p=tmp_path/f'{year}-cat.parquet';c.to_parquet(p,index=False);m['inputs'][f'{year}/cat_medium']=ref(p)
    run(m)
    out=Path(m['output']);done=json.loads((out/'completion.json').read_text());freeze=json.loads((out/'forecast-freeze.json').read_text());aggregate=json.loads((out/'aggregate.json').read_text())
    assert done['state']=='COMPLETED'and done['dependence_fits']==2 and done['base_fits']==0 and done['model_loads']==9
    assert len(aggregate['comparisons'])==16 and len(freeze['weights'])==2
    rows=pd.read_parquet(out/'2023/independent_sum-scored.parquet')
    assert len(rows)==4 and rows.sum_mode.value_counts().to_dict()=={'INFORMED_MONTE_CARLO_SUM':2,'DIRECT_COMBINED_FALLBACK':2}

@pytest.mark.parametrize('remove_veclib',[False,True])
def test_fresh_native_child_seven_caps_and_missing_cap_refusal(tmp_path,remove_veclib):
    import hashlib,json,subprocess,sys
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    names=['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','OMP_THREAD_LIMIT','ARROW_IO_THREADS','VECLIB_MAXIMUM_THREADS']
    output=tmp_path/'fictional-payload';receipt=tmp_path/'native-receipt.json';result=tmp_path/'native-entry.json'
    script=tmp_path/'native-worker.py';monitor=tmp_path/'fresh-monitor.py'
    body="import os,json\nfrom pathlib import Path\n"+f"names={names!r}\nresult=Path({str(result)!r})\n"+"observed={n:os.environ.get(n)for n in names}\nassert all(v=='2'for v in observed.values())\n"
    if remove_veclib:
        libc=Path('/usr/lib/x86_64-linux-gnu/libc.so.6');ref=dict(path=str(libc),bytes=libc.stat().st_size,sha256=hashlib.sha256(libc.read_bytes()).hexdigest())
        spec=tmp_path/'fictional-registration.json';spec.write_text(json.dumps(dict(registration_id='combined-yard-copula-v1-20261025',state='FROZEN_ROOT_REVIEWER_SEALED',thread_environment=names)))
        sr=dict(path=str(spec),bytes=spec.stat().st_size,sha256=hashlib.sha256(spec.read_bytes()).hexdigest());m=dict(libc=ref,registration=sr,inputs={},versions={},output=str(output))
        body+="os.environ.pop('VECLIB_MAXIMUM_THREADS')\nfrom tools.run_cached_combined_yard import run\n"+f"m={m!r}\n"+"try:run(m)\nexcept ValueError as e:\n assert str(e)=='exact two-thread environment required'\n assert not Path(m['output']).exists()\n result.write_text(json.dumps({'observed_at_entry':observed,'refused_missing_VECLIB':True,'worker_output_created':False}))\nelse:raise AssertionError('strict seventh cap did not refuse')\n"
    else:body+="result.write_text(json.dumps({'observed_at_entry':observed,'all_seven_two':True}))\n"
    script.write_text(body)
    monitor.write_text("import sys\nfrom pathlib import Path\n"+f"sys.path.insert(0,{str(root)!r})\n"+"from tools import combined_yard_native_core_env_f2 as core\n"+f"p=core.supervise([{sys.executable!r},'-B',{str(script)!r}],cwd=Path({str(root)!r}),output=Path({str(output)!r}),receipt=Path({str(receipt)!r}),limits=core.Limits(cpu=10,wall=15,rss=1073741824,retained=1048576,soft_reserve=1,grace=1,poll=.05,address_space=8589934592),metadata={{'fictional_only':True}})\nassert p['state']=='COMPLETED'and p['process_tree_clean']\n")
    done=subprocess.run([sys.executable,'-B',str(monitor)],capture_output=True,text=True,timeout=25)
    assert done.returncode==0,done.stderr
    entry=json.loads(result.read_text());native=json.loads(receipt.read_text())
    assert entry['observed_at_entry']==dict.fromkeys(names,'2')
    assert native['worker_pid']!=native['supervisor_pid'] and native['worker_returncode']==0 and native['process_tree_clean']
    assert entry.get('refused_missing_VECLIB',False)==remove_veclib
