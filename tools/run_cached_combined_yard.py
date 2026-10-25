"""One sealed private cached-law experiment. No source acquisition/base fitting."""
import argparse, hashlib, importlib.metadata, json, os, resource, sys, time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def pin(ref):
    p=Path(ref['path'])
    if not p.is_file() or p.is_symlink() or p.stat().st_size!=ref['bytes'] or sha(p)!=ref['sha256']:raise ValueError('frozen binding changed')
    return p

def gate(manifest,digest,go_path):
    if sha(manifest)!=digest:raise ValueError('manifest changed')
    m=json.loads(Path(manifest).read_text());g=json.loads(Path(go_path).read_text())
    if m.get('state')!='SEALED_ROOT_AND_REVIEWER' or m.get('preexec_review')!='PASS' or g.get('state')!='GO' or g.get('manifest_sha256')!=digest or g.get('actual_invocations')!=1 or g.get('automatic_retries')!=0 or g.get('root_ledger_writer')!='/root':raise ValueError('inert preparation; exact independent review and sole root GO required')
    for ref in [m['libc'],m['registration'],*m['inputs'].values(),*m['code'].values()]:pin(ref)
    return m

def run(m):
    # Heavy imports occur only after the exact sealed GO gate in a fresh worker.
    if 'libc' not in m:raise ValueError('missing frozen libc binding')
    pin(m['libc'])
    from tools.ngboost_law_software_v1 import process_free_threads
    import threadpoolctl
    import io, joblib, numpy as np, pandas as pd
    from threadpoolctl import threadpool_limits
    from nfl_lab import cdf_engine as cdf
    from nfl_lab.threshold_cdf import StableMixtureBatch
    from nfl_lab import combined_yard_copula as joint
    from nfl_lab.source_matched_benchmark import no_fits
    from tools import run_threshold_cdf_after_audit as common
    spec=json.loads(pin(m['registration']).read_text())
    if 'source_execution'in m['inputs']:
        v=json.loads(pin(m['inputs']['v2_registration']).read_text());d=json.loads(pin(m['inputs']['direct_registration']).read_text())
        if v['source_manifest_sha256']!=d['source_manifest']['sha256']or v['category_contract_sha256']!=d['category_contract']['sha256']or v['input_features_sha256']!=d['input_features']['sha256']:raise ValueError('source/category/all97feature reference mismatch before row decode')
    if spec['registration_id']!=joint.VERSION or spec['state']!='FROZEN_ROOT_REVIEWER_SEALED':raise ValueError('inactive science registration')
    if any(os.environ.get(k)!='2' for k in spec['thread_environment']):raise ValueError('exact two-thread environment required')
    for name,v in m['versions'].items():
        if importlib.metadata.version(name)!=v:raise ValueError('runtime package changed')
    class Report(common.Run):
        def __init__(self):
            self.m=m;self.s=spec;self.limits=spec['resources'];self.out=Path(m['output']);self.out.mkdir(mode=0o700,exist_ok=False)
            self.start=time.monotonic();self.cpu=time.process_time();self.fits=0;self.query_rows=0;self.expanded=0;self.bindings={};self.slots=[];self.models=0;self.draw_rows=0;self.inference_rows=0
        def check(self):
            if time.process_time()-self.cpu>=870 or time.monotonic()-self.start>=1170 or resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024>=2080374784 or self.models>9 or self.fits>2 or self.draw_rows>spec['maximum_draw_row_passes'] or self.inference_rows>spec['maximum_marginal_query_rows']:raise RuntimeError('finite cached-law allocation exhausted')
        def save(self,relative,value):self.check();return super().save(relative,value)
    report=Report();report.save('CONSUMED.json',dict(state='SINGLE_INVOCATION_CONSUMED',base_fits=0,HTTP=0,retries=0))
    keys=cdf.KEYS;context=common.META
    def read(key,columns=None):
        report.check();ref=m['inputs'][key];pin(ref);return pd.read_parquet(ref['path'],columns=columns)
    def same(a,b,labels=False):
        cols=context if all(c in a and c in b for c in context) else keys+['position','team','opponent','kickoff_utc','cutoff_utc']
        if not a[cols].equals(b[cols]):raise ValueError('offered identity/context/clock mismatch; no intersection')
        if labels and (not a.participation_state.equals(b.participation_state) or not np.array_equal(cdf.numeric(a,'actual'),cdf.numeric(b,'actual'),equal_nan=True)):raise ValueError('labels/participation differ before loss arithmetic')
    def query(year,target):
        q=read(f'{year}/{target}/query')
        if not q.season.eq(year).all() or q[keys].isna().any(axis=None) or q.duplicated(keys).any() or 'actual'in q or 'participation_state'in q:raise ValueError('forecast query identity/season/label contract')
        fc=sorted(c for c in q if c.startswith('f_'))
        if len(fc)!=97 or q.f_player_play_rate8.notna().any():raise ValueError('approved97feature mask changed')
        cut=pd.to_datetime(q.cutoff_utc,utc=True);kick=pd.to_datetime(q.kickoff_utc,utc=True);src=pd.to_datetime(q.feature_max_source_available_utc,utc=True)
        if (cut>kick).any() or (src.notna()&(src>=cut)).any():raise ValueError('query availability changed')
        return q.reset_index(drop=True)
    cache={}
    def annual(year):
        if year in cache:return cache[year]
        out={}
        for target in ['rush_yd','rec_yd','rush_rec_yd']:
            q=query(year,target);model=joblib.load(pin(m['inputs'][f'{year}/{target}/model']));report.models+=1
            if type(model)is not cdf.LeafCDFModel or model.category['target']!=target or model.category['support']!='signed_integer':raise ValueError('exact signed leaf marginal class required')
            first=pd.to_datetime(q.cutoff_utc,utc=True).min()
            for training in [model.training_binding,model.prior_training_binding]:
                if training is not None and (not training.season.lt(year).all() or not pd.to_datetime(training.outcome_available_utc,utc=True).lt(first).all()):raise ValueError('model training is not earlier OOF')
            laws=[None]*len(q);reasons=['unavailable']*len(q)
            report.inference_rows+=len(q);report.check()
            for idx,batch,why in model.predict_batches(q,batch_size=64):
                for j,i in enumerate(idx):
                    laws[i]=None if batch is None else StableMixtureBatch(batch.support,batch.weights[j:j+1],batch.prior,prior_weight=batch.b)
                    reasons[i]=str(why[j])
            out[target]=dict(query=q,laws=laws,reasons=reasons,lookup={tuple(v):i for i,v in enumerate(q[keys].itertuples(index=False,name=None))})
        out['query']=out['rush_rec_yd']['query'];out['direct']=read(f'{year}/rush_rec_yd/forecast');same(out['query'],out['direct'])
        for component in ['rush_yd','rec_yd']:
            o=out[component];q=o['query'];ids=out['query'].set_index(keys,drop=False);fcols=sorted(c for c in q if c.startswith('f_'))
            if not all(tuple(k)in ids.index for k in q[keys].itertuples(index=False,name=None)):raise ValueError('component outside offered combined population')
            aligned=ids.loc[list(q[keys].itertuples(index=False,name=None))].reset_index(drop=True)
            same(q,aligned)
            if not np.array_equal(q[fcols].to_numpy(),aligned[fcols].to_numpy(),equal_nan=True):raise ValueError('all97source features differ between marginal and combined query')
        cache[year]=out;return out
    def marginal_pair(data,i):
        q=data['query'];identity=tuple(q.loc[i,keys]);reason=''
        if q.iloc[i].position!='RB':return None,'non_RB_direct_combined'
        pair=[]
        for target in ['rush_yd','rec_yd']:
            obj=data[target];j=obj['lookup'].get(identity)
            if j is None or obj['laws'][j]is None or obj['reasons'][j]:return None,'missing_or_fallback_marginal_direct_combined'
            pair.append(obj['laws'][j])
        return pair,''
    pit_cache={}
    def training(year,evaluation_cutoff):
        data=annual(year);q=data['query'];labels={}
        for target in ['rush_yd','rec_yd']:
            obj=data[target];z=read(f'{year}/{target}/scored',columns=context+['actual','participation_state','fallback']);same(obj['query'],z);labels[target]=z
        a=[];b=[];excluded={}
        for i,row in q.iterrows():
            pair,why=marginal_pair(data,i)
            if pair is None:excluded[why]=excluded.get(why,0)+1;continue
            identity=tuple(row[keys]);vals=[];states=[]
            for target in ['rush_yd','rec_yd']:
                j=data[target]['lookup'][identity];r=labels[target].iloc[j];vals.append(r.actual);states.append(r.participation_state)
            if states[0]!=states[1]:raise ValueError('component participation disagreement')
            if states[0]!='played' or not cdf.valid_support(vals,'signed_integer').all() or not pd.to_datetime(row.outcome_available_utc,utc=True)<evaluation_cutoff:excluded['unavailable_or_late_training_label']=excluded.get('unavailable_or_late_training_label',0)+1;continue
            pits=[];ok=True
            for j,law in enumerate(pair):
                pit,valid=joint.randomized_pit(law,[vals[j]],[identity],f'PIT-{j}')
                ok &= bool(valid[0]);pits.append(pit[0])
            if ok:a.append(pits[0]);b.append(pits[1])
            else:excluded['unrepresented_PIT_interval']=excluded.get('unrepresented_PIT_interval',0)+1
        return a,b,excluded
    def draw(data,i,rho):
        pair,why=marginal_pair(data,i)
        if pair is None:return None,why,None
        ident=tuple(data['query'].loc[i,keys]);values,x,y=joint.sum_draws(*pair,rho,[ident]);report.draw_rows+=1;report.check()
        if not np.array_equal(values,x+y):raise ValueError('joint-sum coherence failed')
        return joint.empirical_sum_law(values[0],pair[0].prior),'',joint.draw_digest(values[0])
    forecasts={};weights={}
    with process_free_threads(threadpoolctl,m['libc']),no_fits(),threadpool_limits(limits=2):
        for year in [2023,2024]:
            data=annual(year);cutoff=pd.to_datetime(data['query'].cutoff_utc,utc=True).min();aa=[];bb=[];ex={}
            for earlier in range(2022,year):
                a,b,why=training(earlier,cutoff);aa.extend(a);bb.extend(b);ex[str(earlier)]=why
            rho=joint.fit_dependence(aa,bb);report.fits+=1;rho.update(training_years=list(range(2022,year)),first_evaluation_cutoff=str(cutoff),excluded_training=ex)
            weights[year]=rho;report.save(f'{year}/dependence.json',rho)
            for arm in joint.ARMS:
                rows=data['direct'].copy();rows['draw_sha256']='';rows['coupling_rho']=0. if arm=='independent_sum'else rho['rho'];rows['sum_mode']='DIRECT_COMBINED_FALLBACK'
                for threshold in spec['push_thresholds']:
                    rows[f'push_mass_{threshold}']=[np.nan if law is None else np.exp(law.logpmf([threshold]))[0]for law in data['rush_rec_yd']['laws']]
                for name in common.SCORES:rows[name]=np.nan
                for i in range(len(rows)):
                    law,why,digest=draw(data,i,rows.coupling_rho.iloc[i])
                    if law is None:rows.loc[i,'fallback']='direct_combined:'+why+':'+str(rows.iloc[i].fallback);continue
                    pair,_=marginal_pair(data,i);rows.loc[i,'mean']=float(pair[0].mean[0]+pair[1].mean[0]);rows.loc[i,'median']=law.quantile(.5)[0];rows.loc[i,'p10']=law.quantile(.1)[0];rows.loc[i,'p90']=law.quantile(.9)[0];rows.loc[i,'variance']=law.variance[0];rows.loc[i,'mass_zero']=np.exp(law.logpmf([0]))[0];rows.loc[i,'draw_sha256']=digest;rows.loc[i,'fallback']='';rows.loc[i,'sum_mode']='INFORMED_MONTE_CARLO_SUM'
                    for threshold in spec['push_thresholds']:rows.loc[i,f'push_mass_{threshold}']=np.exp(law.logpmf([threshold]))[0]
                forecasts[(year,arm)]=rows;report.save(f'{year}/{arm}-forecast.parquet',rows)
            # Only now can2023OOF labels enter the2024dependence fit.
        report.save('forecast-freeze.json',dict(state='ALL_TWO_WEIGHTS_FOUR_FORECASTS_FROZEN_BEFORE_EVALUATION',weights=weights,bindings=dict(report.bindings),inputs=m['inputs'],base_fits=0,dependence_fits=report.fits,model_loads=report.models,draw_rows=report.draw_rows))
        scored={};direct={};cat={};comparisons=[]
        for year in [2023,2024]:
            data=annual(year);control=read(f'{year}/rush_rec_yd/scored');same(data['query'],control)
            for arm in joint.ARMS:
                rows=forecasts[(year,arm)].copy();same(rows,control);rows['actual']=control.actual;rows['participation_state']=control.participation_state;same(rows,control,True)
                if not np.array_equal(np.isfinite(cdf.numeric(rows,'median')),np.isfinite(cdf.numeric(control,'median'))):raise ValueError('all-offered coverage differs; no favorable intersection')
                valid=rows.participation_state.eq('played').to_numpy()&cdf.valid_support(cdf.numeric(rows,'actual'),'signed_integer')
                for i in np.flatnonzero(valid):
                    law,why,digest=draw(data,int(i),rows.coupling_rho.iloc[i])
                    if law is None:
                        for field in common.SCORES:rows.loc[i,field]=control.iloc[i][field]
                    else:
                        if digest!=rows.draw_sha256.iloc[i]:raise ValueError('frozen joint draw digest changed')
                        y=rows.actual.iloc[i];rows.loc[i,'crps']=law.crps([y])[0];rows.loc[i,'cdf_actual_below']=law.cdf([y-1])[0];rows.loc[i,'cdf_actual']=law.cdf([y])[0]
                scored[(year,arm)]=rows;report.save(f'{year}/{arm}-scored.parquet',rows)
            direct[year]=control
            z=read(f'{year}/cat_medium');z=z.loc[z.primary_role].copy().sort_values(keys,kind='stable').reset_index(drop=True)
            target=control.sort_values(keys,kind='stable').reset_index(drop=True)
            if not z.method.eq('direct_catboost_medium').all() or not z.target.eq('rush_rec_yd').all() or not z.point_semantics.eq('median_objective_point_heuristic').all():raise ValueError('Catmedium point provenance/functional mismatch')
            same(z,target,True);z['median']=z.point;cat[year]=z
        summary=[]
        def describe(rows):
            v=common.loss_summary(rows,'signed_integer')
            if 'distribution'in v:
                v['distribution']['log_score_state']='NOT_COMPUTED_JOINT_DENSITY';v['distribution']['log_score']=None
                v['distribution']['mean_cdf_actual_below']=float(rows.cdf_actual_below.mean());v['distribution']['mean_cdf_actual']=float(rows.cdf_actual.mean())
                v['distribution']['fixed_push_mass']={str(t):float(rows[f'push_mass_{t}'].mean())for t in spec['push_thresholds']}
            v['sum_modes']=rows.sum_mode.value_counts(dropna=False).to_dict()
            return v
        for cohort in ['all_offered','RB_diagnostic']:
            def subset(df):return df if cohort=='all_offered'else df.loc[df.position.eq('RB')].copy()
            for arm in joint.ARMS:
                pooled=pd.concat([subset(scored[y,arm])for y in [2023,2024]],ignore_index=True);v=describe(pooled)
                summary.append(dict(cohort=cohort,arm=arm,pooled=v,annual={str(y):describe(subset(scored[y,arm]))for y in [2023,2024]}))
            pairs=[(arm,'direct_leaf_CDF','crps')for arm in joint.ARMS]+[(arm,'direct_leaf_CDF','MAE')for arm in joint.ARMS]+[('shrunk_gaussian_sum','independent_sum',metric)for metric in ['crps','MAE']]+[(arm,'Catmedium_POINT_ONLY','MAE')for arm in joint.ARMS]
            for arm,control_name,metric in pairs:
                annual={};aa=[];bb=[]
                for year in [2023,2024]:
                    a=subset(scored[year,arm]).sort_values(keys,kind='stable').reset_index(drop=True);b=subset(direct[year]if control_name=='direct_leaf_CDF'else cat[year]if control_name=='Catmedium_POINT_ONLY'else scored[year,'independent_sum']).sort_values(keys,kind='stable').reset_index(drop=True)
                    same(a,b,True);field='crps'if metric=='crps'else'median'
                    if not np.array_equal(np.isfinite(cdf.numeric(a,field)),np.isfinite(cdf.numeric(b,field))):raise ValueError('comparator eligible masks differ; no intersection')
                    annual[str(year)]=common.paired(a,b,metric,'signed_integer',point='median');aa.append(a);bb.append(b)
                comparisons.append(dict(cohort=cohort,arm=arm,control=control_name,metric=metric,annual=annual,pooled=common.paired(pd.concat(aa,ignore_index=True),pd.concat(bb,ignore_index=True),metric,'signed_integer',point='median')))
        report.save('aggregate.json',dict(state='DESCRIPTIVE_EXPOSED_PERIOD_ONLY',summary=summary,comparisons=comparisons,dependence=weights,primary='CRPS Monte Carlo empirical approximation; direct control exact',no_SITE_R0_current_site_or_qualification_claim=True,bootstrap='existing paired500PCG64 wholeweek1911/game1912',joint_log_density='not computed; no invented normal or probability floor'))
        report.check();report.save('completion.json',dict(state='COMPLETED',bindings=report.bindings,usage=report.usage(),base_fits=0,dependence_fits=report.fits,model_loads=report.models,draw_row_passes=report.draw_rows,HTTP=0,retries=0))

def main():
    p=argparse.ArgumentParser();p.add_argument('manifest');p.add_argument('sha256');p.add_argument('go');a=p.parse_args()
    m=gate(a.manifest,a.sha256,a.go)
    def offline(event,args):
        if event.startswith('socket.')or event in {'subprocess.Popen','os.fork','os.posix_spawn'}:raise RuntimeError('offline single-worker report')
    sys.addaudithook(offline);run(m)

if __name__=='__main__':main()
