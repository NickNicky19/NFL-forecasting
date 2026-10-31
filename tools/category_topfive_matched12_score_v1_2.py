"""Matched all-category cached scoring; no fitting, acquisition, inference or writers.

The root runner owns GO, protected labels, immutable forecast freeze and managed
storage. Importing this module performs no source decode. The source table is a
full saved comparison-row member, not a prior Top-N subset. Offers must already
be qualified, deduplicated and crosswalked by the independently registered rule.
"""
from __future__ import annotations
import hashlib,io,json,math,zipfile
from decimal import Decimal
from pathlib import Path

VERSION='matched12-cached-score-v1.2'
KEY=['target','season','week','game_id','player_id','team','opponent','cutoff_utc','kickoff_utc']
ID=['target','season','week','game_id','player_id','team','opponent']
COUNT={'pass_td','pass_cmp','pass_att','pass_int','rush_att','rec','rec_tgt'}
DEFAULT_GROUPS={'CDF_MEDIAN':'LEAF_CDF','CDF_MEAN':'LEAF_CDF','LAB_CDF':'LEAF_CDF',
 'CATBOOST_MEDIUM':'CATBOOST','CATBOOST_COUNT_MEAN':'CATBOOST',
 'COUNT_A_MEAN':'COUNT_A','RESPONSE_CDF_MEAN':'RESPONSE_CDF',
 'TD_EQUAL_CDF_CAT':'EQUAL_CDF_CAT_BLEND',
 'LEAF_CDF_CHART_MEAN_V1':'CHART_LEAF_CDF','LEAF_CDF_CHART_MEDIAN_V1':'CHART_LEAF_CDF',
 'ROLE_LAW_CHART_MEAN_V1':'CHART_ROLE_LAW','ROLE_LAW_CHART_MEDIAN_V1':'CHART_ROLE_LAW',
 'POSITION_CHART_MEAN_2024':'CHART_POSITION_PRIOR','POSITION_CHART_MEDIAN_2024':'CHART_POSITION_PRIOR',
 'GLOBAL_CHART_MEDIAN_2024':'CHART_GLOBAL_PRIOR','HGB_CHART_MEDIAN_V1':'CHART_HGB'}

def _clock(series):
    import pandas as pd
    for value in series.dropna().drop_duplicates():
        stamp=pd.Timestamp(value)
        if not pd.isna(stamp) and stamp.tzinfo is None:raise ValueError('known source clock has unknown timezone; no UTC fabrication')
    return pd.to_datetime(series,utc=True,errors='raise')

def _participation(series):
    out=series.map({'played':'played','unknown':'unknown','DNP':'dnp','dnp':'dnp'})
    if out.isna().any():raise ValueError('unregistered participation state')
    return out

def _context_consistency(f,scope):
    import pandas as pd
    base=['target','season','week','game_id','player_id','horizon_id']
    for field in ['team','opponent','position','cutoff_utc','kickoff_utc','participation_state','actual']:
        if f.groupby(base,dropna=False)[field].nunique(dropna=False).gt(1).any():
            raise ValueError('contradictory model-independent opportunity '+field)
    return base

def read_cached_table(ref,go):
    """First NFL decode: only callable after a fresh explicit root/reviewer GO."""
    if (go.get('state')!='ROOT_AND_INDEPENDENT_GO' or go.get('worker_version')!=VERSION
        or go.get('registered_by')!='/root' or go.get('input_sha256')!=ref['sha256']
        or go.get('worker_sha256')!=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()):
        raise ValueError('new exact matched12 GO required; old cohort GO is not authority')
    path=Path(ref['path'])
    if not path.is_absolute() or path.resolve()!=path or any(p.is_symlink() for p in (path,*path.parents)):
        raise ValueError('canonical nonsymlink cached source required')
    before=path.stat();body=path.read_bytes();after=path.stat()
    if len(body)!=ref['bytes'] or hashlib.sha256(body).hexdigest()!=ref['sha256'] or (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns):
        raise ValueError('cached source binding changed')
    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        info=archive.getinfo('COMPARISON_ROWS.parquet')
        if info.file_size>16*1024**2:raise ValueError('finite cached member envelope exceeded')
        raw=archive.read(info)
    import pyarrow.parquet as pq
    frame=pq.read_table(io.BytesIO(raw),use_threads=False).to_pandas()
    required=set(KEY+['prediction','fallback','method','product','actual','participation_state'])
    if not required<=set(frame):raise ValueError('comparison rows schema incomplete')
    if len(frame)>150000:raise ValueError('finite saved-output row envelope exceeded')
    return frame

def normalize(frame,scope,catalog):
    """No cohort filtering. Keep all expected rows in the source scope."""
    import numpy as np
    import pandas as pd
    f=frame.copy()
    if not scope.get('identity_namespace') or not scope.get('source_policy_id') or not scope.get('outcome_version'):
        raise ValueError('explicit identity/source/outcome policy required')
    if 'chart_ppr' in scope['targets'] and scope.get('chart_target_contract')!='nick-chart-ppr-v1':
        raise ValueError('exact separately qualified chart target required, not old website PPR')
    years=set(scope['seasons']);weeks=set(scope['weeks'])
    f=f.loc[f.season.isin(years)&f.week.isin(weeks)&f.target.isin(scope['targets'])].copy()
    if not scope.get('horizon_id'):raise ValueError('one explicit common horizon required per panel')
    if 'horizon_id' in f and not f.horizon_id.eq(scope['horizon_id']).all():raise ValueError('mixed forecast horizons require separate panels')
    f['horizon_id']=scope['horizon_id']
    if 'captured_participation_state' not in f:f['captured_participation_state']=f.participation_state
    f['participation_state']=_participation(f.participation_state)
    if f.duplicated(KEY+['method','product']).any():raise ValueError('duplicate procedure/output opportunity')
    f['prediction']=pd.to_numeric(f.prediction,errors='coerce');f['actual']=pd.to_numeric(f.actual,errors='coerce')
    for key in ['cutoff_utc','kickoff_utc']:
        f[key]=_clock(f[key])
    if f.duplicated(KEY+['method','product']).any():raise ValueError('clock normalization collapsed distinct saved identities')
    _context_consistency(f,scope)
    if (f.cutoff_utc.notna()&f.kickoff_utc.notna()&(f.cutoff_utc>f.kickoff_utc)).any():
        raise ValueError('historical query cutoff after kickoff; no timing relabel')
    unknown_numeric=f.actual.notna()&~f.participation_state.eq('played')
    if unknown_numeric.any():raise ValueError('numeric outcome without qualified played state')
    good=f.participation_state.eq('played')&f.actual.notna()
    if (~np.isfinite(f.loc[good,'actual'].to_numpy(float))).any():raise ValueError('nonfinite qualified actual')
    count=f.target.isin(COUNT)&good
    if (f.loc[count,'actual']<0).any() or (f.loc[count,'actual']%1!=0).any():raise ValueError('count actual outside integer support')
    chart=f.target.eq('chart_ppr')&good
    z=f.loc[chart,'actual'].to_numpy(float)*50
    if (np.abs(z-np.rint(z))>1e-8).any():raise ValueError('chart actual outside registered signed0.02 lattice')
    if len(f):
        # No method may select an easier target outcome version.
        values=f.loc[good,ID+['actual']].drop_duplicates()
        if values.duplicated(ID).any():raise ValueError('candidate target labels conflict; resolve source version first')
    def bind(row):
        cfg=catalog.get(row.target,{}).get(row.method)
        if cfg is None:raise ValueError('method absent from frozen candidate catalog: '+row.target+'/'+row.method)
        if 'products' in cfg and row.product not in cfg['products']:raise ValueError('undeclared source output product')
        return cfg
    configs=[bind(r) for r in f.itertuples()]
    f['procedure']=[c['procedure_id'] for c in configs]
    f['procedure_version']=[c['procedure_version'] for c in configs]
    f['shortlist_group']=[c.get('shortlist_group',c['procedure_id']) for c in configs]
    f['evidence_tier']=scope['evidence_tier'];f['source_policy_id']=scope['source_policy_id'];f['outcome_version']=scope['outcome_version']
    return f

def materialize_expected(frame,expected_roster,outcomes,scope,catalog):
    """The roster and canonical labels are independent of prediction availability."""
    import numpy as np
    import pandas as pd
    f=normalize(frame,scope,catalog);e=expected_roster.copy();o=outcomes.copy()
    for x in [e,o]:
        if 'horizon_id' in x and not x.horizon_id.eq(scope['horizon_id']).all():raise ValueError('expected/outcome horizon conflict')
        x['horizon_id']=scope['horizon_id']
    base=['target','season','week','game_id','player_id','horizon_id']
    required=KEY+['position']
    if not set(required)<=set(e) or e.duplicated(base).any():raise ValueError('complete unique expected roster required')
    e=e[required+['horizon_id']].copy()
    if not set(base+['actual','participation_state'])<=set(o) or o.duplicated(base).any():raise ValueError('unique canonical outcome table required')
    for c in ['cutoff_utc','kickoff_utc']:e[c]=_clock(e[c])
    o['participation_state']=_participation(o.participation_state)
    o['actual']=pd.to_numeric(o.actual,errors='raise')
    context=['team','opponent','position','cutoff_utc','kickoff_utc']
    check=f.merge(e[base+context],on=base,how='left',suffixes=('','_expected'),indicator=True,validate='many_to_one')
    if not check['_merge'].eq('both').all():raise ValueError('forecast outside registered expected roster')
    for c in context:
        if not (check[c].eq(check[c+'_expected'])|check[c].isna()&check[c+'_expected'].isna()).all():raise ValueError('forecast differs from expected roster context '+c)
    check=f.merge(o[base+['actual','participation_state']],on=base,how='left',suffixes=('','_canonical'),indicator=True,validate='many_to_one')
    if not check['_merge'].eq('both').all():raise ValueError('forecast lacks canonical outcome state')
    if not (check.actual.eq(check.actual_canonical)|check.actual.isna()&check.actual_canonical.isna()).all() or not check.participation_state.eq(check.participation_state_canonical).all():raise ValueError('saved labels disagree with canonical outcome version')
    e=e.merge(o[base+['actual','participation_state']],on=base,how='left',validate='one_to_one',indicator=True)
    if not e['_merge'].eq('both').all():raise ValueError('expected roster lacks explicit canonical outcome state')
    e=e.drop(columns='_merge');parts=[]
    for target in scope['targets']:
        population=e.loc[e.target.eq(target)]
        for method,cfg in catalog.get(target,{}).items():
            products=cfg.get('products')
            if not isinstance(products,list) or not products or len(products)!=len(set(products)):raise ValueError('declared unique output products required')
            for product in products:
                existing=f.loc[f.target.eq(target)&f.method.eq(method)&f['product'].eq(product)]
                keep=[c for c in existing if c not in base+context+['actual','participation_state']]
                grid=population.merge(existing[base+keep],on=base,how='left',validate='one_to_one')
                missing=grid['method'].isna();grid['method']=method;grid['product']=product
                grid.loc[missing,'prediction']=np.nan;grid.loc[missing,'fallback']=''
                grid['prediction_status']=np.where(missing,'MISSING_DECLARED_OUTPUT','CAPTURED_OUTPUT')
                parts.append(grid)
    if not parts:raise ValueError('no declared expected outputs')
    return normalize(pd.concat(parts,ignore_index=True),scope,catalog)

def _probabilities(p,y):
    import numpy as np
    if not len(p):return {'Brier':None,'log_loss':{'state':'UNAVAILABLE','value':None,'reason':'NO_SUPPORTED_EVENT_ROWS'}}
    if ((p<0)|(p>1)).any() or not np.isin(y,[0,1]).all():raise ValueError('binary probability/event contract violated')
    with np.errstate(divide='ignore',invalid='raise'):ll=np.where(y==1,-np.log(p),-np.log1p(-p))
    infinite=int(np.isposinf(ll).sum())
    bins=[]
    for i in range(10):
        take=(p>=i/10)&((p<(i+1)/10) if i<9 else p<=1)
        bins.append({'lower':i/10,'upper':(i+1)/10,'n':int(take.sum()),'mean_probability':float(p[take].mean()) if take.any() else None,'event_rate':float(y[take].mean()) if take.any() else None})
    return {'Brier':float(np.mean((p-y)**2)),'log_loss':{'state':'POSITIVE_INFINITY' if infinite else 'FINITE','value':None if infinite else float(ll.mean()),'positive_infinite_rows':infinite},'reliability':bins}

def metrics(frame,target):
    import numpy as np
    planned=len(frame);p=frame.prediction.to_numpy(float);y=frame.actual.to_numpy(float)
    state=_participation(frame.participation_state)
    good=state.eq('played').to_numpy()&np.isfinite(y)&np.isfinite(p)
    e=p[good]-y[good];ae=np.abs(e);fallback=frame.fallback.fillna('').astype(str).ne('').to_numpy()
    result={'planned':planned,'scored':int(good.sum()),'missing_prediction':int((~np.isfinite(p)).sum()),'unknown_participation':int(state.eq('unknown').sum()),
      'played_missing':int((state.eq('played').to_numpy()&~np.isfinite(y)).sum()),'DNP':int(state.eq('dnp').sum()),
      'fallback_planned':int(fallback.sum()),'fallback_scored':int((fallback&good).sum()),'played_zero':int((good&(y==0)).sum()),
      'games':int(frame.loc[good,'game_id'].nunique()),'weeks':int(frame.loc[good,'week'].nunique()),
      'MAE':float(ae.mean()) if len(e) else None,'MSE':float(np.mean(e*e)) if len(e) else None,'RMSE':float(np.sqrt(np.mean(e*e))) if len(e) else None,
      'bias':float(e.mean()) if len(e) else None,'p90_AE':float(np.quantile(ae,.9)) if len(e) else None,'p95_AE':float(np.quantile(ae,.95)) if len(e) else None,
      'forecast_product':str(frame['product'].iloc[0]) if planned else None,'unknown_clock_rows':int((frame.cutoff_utc.isna()|frame.kickoff_utc.isna()).sum())}
    if not len(e):result['unavailable_score_reason']='NO_SUPPORTED_FINITE_PREDICTION_OUTCOME_ROWS'
    c,k=_clock(frame.cutoff_utc),_clock(frame.kickoff_utc)
    result['clock_phenotypes']={'both_unknown':int((c.isna()&k.isna()).sum()),'cutoff_only_unknown':int((c.isna()&k.notna()).sum()),'kickoff_only_unknown':int((c.notna()&k.isna()).sum()),'known_equal_kickoff':int((c.notna()&c.eq(k)).sum()),'known_before_kickoff':int((c<k).sum())}
    if target in COUNT:
        integer=np.equal(p[good],np.rint(p[good]))
        result['exact_count']={'value':float(np.mean(p[good]==y[good])) if len(e) and integer.all() else None,'n':len(e) if len(e) and integer.all() else 0,'rule':'UNROUNDED_INTEGER_POINT_ONLY; fractional means are not rounded into an exact-count claim.'}
    tol=1 if target in COUNT or target=='chart_ppr' else 10
    if target!='anytime_td':result.update(tolerance=tol,strict_within=float((ae<tol).mean()) if len(e) else None,inclusive_within=float((ae<=tol).mean()) if len(e) else None)
    else:
        proper=_probabilities(p[good],y[good]);result.update(primary='Brier',probability_scores=proper,MSE=proper['Brier'],MSE_functional='BINARY_BRIER_NOT_EXPECTED_COUNT_MEAN',probability_bias=result['bias'])
        for key in ['MAE','RMSE','bias','p90_AE','p95_AE']:result[key]=None
        result['numeric_point_reason']='ANYTIME_TD_IS_A_BINARY_EVENT_PROBABILITY_PRODUCT'
    return result

def _bootstrap(delta,groups,seed,replicates,min_clusters):
    import numpy as np
    blocks={}
    for group,value in zip(groups,delta):blocks.setdefault(str(group),[]).append(float(value))
    n=len(blocks)
    if n<min_clusters:return {'state':'UNAVAILABLE_FEWER_THAN_REGISTERED_CLUSTERS','clusters':n}
    sums=np.asarray([sum(v) for v in blocks.values()]);sizes=np.asarray([len(v) for v in blocks.values()]);rng=np.random.default_rng(seed)
    sample=[]
    for _ in range(replicates):
        take=rng.integers(0,n,n);sample.append(float(sums[take].sum()/sizes[take].sum()))
    return {'state':'NOMINAL_EXPOSED_DEVELOPMENT_UNADJUSTED','clusters':n,'lower':float(np.quantile(sample,.025)),'upper':float(np.quantile(sample,.975)),'replicates':replicates,'seed':seed}

def paired(candidate,control,loss,uncertainty):
    import numpy as np
    import pandas as pd
    if loss not in ['MAE','MSE','Brier']:raise ValueError('unsupported point/event paired loss')
    cols=KEY+['prediction','actual','participation_state']
    for f in [candidate,control]:
        if f.duplicated(KEY).any():raise ValueError('duplicate paired opportunity')
    t=candidate[cols].merge(control[cols],on=KEY,how='inner',validate='one_to_one',suffixes=('_a','_b'))
    valid=t.participation_state_a.eq('played')&t.participation_state_b.eq('played')
    valid&=np.isfinite(t[['actual_a','actual_b','prediction_a','prediction_b']].to_numpy(float)).all(axis=1)
    t=t.loc[valid]
    if not np.array_equal(t.actual_a.to_numpy(float),t.actual_b.to_numpy(float)):raise ValueError('paired actual mismatch')
    e1=t.prediction_a.to_numpy(float)-t.actual_a.to_numpy(float);e0=t.prediction_b.to_numpy(float)-t.actual_b.to_numpy(float)
    a=np.abs(e1) if loss=='MAE' else e1*e1;b=np.abs(e0) if loss=='MAE' else e0*e0;delta=a-b
    base=float(b.mean()) if len(b) else None
    return {'paired_rows':len(t),'candidate_loss':float(a.mean()) if len(a) else None,'control_loss':base,'candidate_minus_control':float(delta.mean()) if len(delta) else None,
      'improvement_percent':100*(base-float(a.mean()))/base if base else None,'loss':loss,
      'intervals':{field:_bootstrap(delta,t[field],uncertainty['seed'],uncertainty['replicates'],uncertainty['minimum_clusters']) for field in ['game_id','week']}}

def point_sides(points,offers,offer_contract):
    """Caller supplies one qualified primary line for every independent opportunity."""
    import numpy as np
    if offer_contract.get('identity_namespace')!=offer_contract.get('forecast_identity_namespace'):
        raise ValueError('crosswalk to common identity namespace required before join')
    needed=set(ID+['cutoff_utc','line','evidence_tier','primary_offer_policy','statistical_contract'])
    if not needed<=set(offers):raise ValueError('primary offered board lacks explicit contract keys')
    points=points.copy();offers=offers.copy()
    points['cutoff_utc']=_clock(points.cutoff_utc);points['participation_state']=_participation(points.participation_state)
    offers['cutoff_utc']=_clock(offers.cutoff_utc);offers['line']=offers.line.map(_line)
    primary=ID+['cutoff_utc']
    if offers.duplicated(primary).any():raise ValueError('one model-independent primary offer required')
    if points.target.eq('anytime_td').any():raise ValueError('ATD is event-probability comparison, not ordinary point-side track')
    joined=points.merge(offers,on=primary,how='left',validate='many_to_one',suffixes=('','_offer'))
    for column in ['selected_side','statistical_result','threshold_outcome']:joined[column]='UNRESOLVED'
    for i,r in joined.iterrows():
        if not math.isfinite(float(r.prediction)) or r.line is None or not math.isfinite(float(r.line)):continue
        p=Decimal(str(r.prediction));line=Decimal(str(r.line));side='over' if p>line else 'under' if p<line else 'abstain'
        joined.at[i,'selected_side']=side
        if side=='abstain':joined.at[i,'statistical_result']='ABSTAIN';continue
        if r.participation_state!='played' or not math.isfinite(float(r.actual)):
            joined.at[i,'statistical_result']='DNP' if r.participation_state=='dnp' else 'UNRESOLVED';continue
        y=Decimal(str(r.actual))
        if r.target=='chart_ppr':y=Decimal(int(round(float(r.actual)*50)))/Decimal(50)
        joined.at[i,'threshold_outcome']='EXACT_LINE' if y==line else 'ABOVE_LINE' if y>line else 'BELOW_LINE'
        joined.at[i,'statistical_result']='PUSH' if y==line else 'WIN' if (y>line if side=='over' else y<line) else 'LOSS'
    return joined

def _line(value):
    import numpy as np
    import pandas as pd
    if value is None or isinstance(value,(bool,np.bool_)) or pd.isna(value):raise ValueError('unsupported missing/bool line')
    result=Decimal(str(value))
    if not result.is_finite():raise ValueError('nonfinite line')
    return result

def summarize_sides(frame):
    out={}
    for side in ['over','under']:
        f=frame.loc[frame.selected_side.eq(side)];counts=f.statistical_result.value_counts().to_dict();wins=int(counts.get('WIN',0));losses=int(counts.get('LOSS',0))
        out[side]={'wins':wins,'losses':losses,'decided':wins+losses,'hit_rate':wins/(wins+losses) if wins+losses else None,
          'pushes':int(counts.get('PUSH',0)),'DNP':int(counts.get('DNP',0)),'unresolved':int(counts.get('UNRESOLVED',0))}
    out.update(no_lean=int(frame.selected_side.eq('abstain').sum()),missing_offer_or_prediction=int(frame.selected_side.eq('UNRESOLVED').sum()),
      settlement='STATISTICAL_ONLY_UNLESS_SEPARATELY_QUALIFIED',venue_voids=None,venue_voids_reason='Not inferred from statistical grades.')
    return out

def probability_sides(frame):
    """Exact-line law outputs supplied by caller, never inferred from point error."""
    import numpy as np
    required={'p_over','p_under','p_push','line','participation_contract','law_version'}
    if not required<=set(frame):raise ValueError('supported exact-line probability/conditioning contract required')
    f=frame.copy();f['line']=f.line.map(_line);f['participation_state']=_participation(f.participation_state);p=f[['p_over','p_under','p_push']].to_numpy(float)
    if f.target.eq('anytime_td').any():raise ValueError('ATD requires its separate event/Yes-No contract, not numeric line reconstruction')
    valid=np.isfinite(p).all(axis=1)
    if ((p[valid]<0)|(p[valid]>1)).any() or (np.abs(p[valid].sum(axis=1)-1)>1e-10).any():raise ValueError('incoherent side/push probabilities')
    if f.loc[valid,'law_version'].isna().any() or f.loc[valid,'participation_contract'].isna().any():raise ValueError('missing probability provenance/conditioning')
    for r in f.loc[valid].itertuples():
        integer=r.target in COUNT or r.target in ['pass_yd','rush_yd','rec_yd','rush_rec_yd'];scale=1 if integer else 50 if r.target=='chart_ppr' else None
        if scale and abs(float(r.line)*scale-round(float(r.line)*scale))>1e-8 and r.p_push>1e-10:raise ValueError('push mass outside the declared outcome lattice')
    f['selected_side']='UNRESOLVED';f['statistical_result']='UNRESOLVED'
    for i,r in f.loc[valid].iterrows():
        side='over' if r.p_over>r.p_under else 'under' if r.p_under>r.p_over else 'abstain';f.at[i,'selected_side']=side
        if side=='abstain':f.at[i,'statistical_result']='ABSTAIN';continue
        if r.participation_state!='played' or not math.isfinite(float(r.actual)):
            f.at[i,'statistical_result']='DNP' if r.participation_state=='dnp' else 'UNRESOLVED';continue
        y=Decimal(str(r.actual));line=Decimal(str(r.line))
        if r.target=='chart_ppr':y=Decimal(int(round(float(r.actual)*50)))/Decimal(50)
        f.at[i,'statistical_result']='PUSH' if y==line else 'WIN' if (y>line if side=='over' else y<line) else 'LOSS'
    return f

def offered_probability_metrics(frame):
    """Three statistical outcomes: Under, equality, Over; no venue void inference."""
    import numpy as np
    f=probability_sides(frame);p=f[['p_under','p_push','p_over']].to_numpy(float)
    good=f.participation_state.eq('played').to_numpy()&np.isfinite(f.actual.to_numpy(float))&np.isfinite(p).all(axis=1)
    a=f.loc[good];p=p[good];events=[]
    for r in a.itertuples():
        y=Decimal(str(r.actual));line=Decimal(str(r.line))
        if r.target=='chart_ppr':y=Decimal(int(round(float(r.actual)*50)))/Decimal(50)
        events.append(0 if y<line else 2 if y>line else 1)
    y=np.asarray(events,dtype=int);one=np.eye(3)[y] if len(y) else np.empty((0,3))
    with np.errstate(divide='ignore'):loss=-np.log(p[np.arange(len(y)),y]) if len(y) else np.asarray([])
    inf=int(np.isposinf(loss).sum())
    return {'primary':'THREE_OUTCOME_BRIER_SUM','n':len(y),'push_outcomes':int((y==1).sum()),'Brier':float(np.mean(np.sum((p-one)**2,axis=1))) if len(y) else None,
      'log_loss':{'state':'POSITIVE_INFINITY' if inf else 'FINITE' if len(y) else 'UNAVAILABLE','value':None if inf or not len(y) else float(loss.mean()),'positive_infinite_rows':inf},
      'conditioning':'Exactly the supplied participation_contract; unknown/DNP and venue settlement remain separate.','over_reliability':_probabilities(p[:,2],(y==2).astype(float))['reliability'] if len(y) else []}

def score_panel(frame,scope,catalog,uncertainty,*,expected_roster,outcomes):
    """Explicit full-system + predeclared common core + pairwise, by season/week."""
    import numpy as np
    f=materialize_expected(frame,expected_roster,outcomes,scope,catalog);records=[];pairs=[];dedup=[]
    for (target,season),group in f.groupby(['target','season'],sort=True):
        views={name:g for name,g in group.groupby(['method','product'],sort=True)}
        for (method,product),view in views.items():
            records.append({'target':target,'season':int(season),'weeks':sorted(map(int,view.week.unique())),'method':method,'product':product,'procedure':str(view.procedure.iloc[0]),
              'procedure_version':str(view.procedure_version.iloc[0]),'scope':'FULL_REGISTERED_METHOD_POPULATION','metrics':metrics(view,target),
              'weekly':[{'week':int(w),'metrics':metrics(v,target)} for w,v in view.groupby('week',sort=True)]})
        # Core membership was frozen in scope before scoring, not chosen by loss.
        core=scope['primary_core_outputs'].get(target,[])
        if not core:raise ValueError('explicit nonempty primary common core required per target')
        selected=[];present=[];excluded=[]
        for method,product in core:
            if (method,product) not in views:raise ValueError('registered primary core output unavailable')
            v=views[(method,product)];present.append(v[KEY])
            valid=v.participation_state.eq('played')&np.isfinite(v.prediction.to_numpy(float))&np.isfinite(v.actual.to_numpy(float))
            selected.append(v.loc[valid,KEY]);excluded.append({'method':method,'product':product,'expected':len(v),'excluded_not_jointly_eligible':int((~valid).sum())})
        common=selected[0]
        for other in selected[1:]:common=common.merge(other,on=KEY,validate='one_to_one')
        presence=present[0]
        for other in present[1:]:presence=presence.merge(other,on=KEY,validate='one_to_one')
        for (method,product),view in views.items():
            matched=view.merge(common,on=KEY,validate='one_to_one')
            met=metrics(matched,target)
            records.append({'target':target,'season':int(season),'method':method,'product':product,'scope':'PREDECLARED_PRIMARY_COMMON_CORE','metrics':met,'core_present_rows':len(presence),'joint_finite_played_rows':len(common),'excluded_core_rows':len(presence)-len(common),'core_exclusions':excluded,'headline_eligible':bool(len(common) and met['scored']==len(common)),'headline_reason':'Only joint finite predictions and same supported actuals across the predeclared core; noncore partial candidates cannot claim this full-board rank.'})
        # Pairwise intersection preserves new entrants' different coverage explicitly.
        reference=tuple(scope['reference_output'][target]);control=views[reference]
        for name,view in views.items():
            loss='Brier' if target=='anytime_td' else 'MAE'
            pairs.append({'target':target,'season':int(season),'candidate':list(name),'reference':list(reference),'primary':paired(view,control,loss,uncertainty),
              'MSE_diagnostic_preserving_output_type':paired(view,control,'MSE',uncertainty) if target!='anytime_td' else None})
        names=list(views)
        for n,a in enumerate(names):
            for b in names[n+1:]:
                aa=views[a][KEY+['prediction']];bb=views[b][KEY+['prediction']]
                j=aa.merge(bb,on=KEY,how='outer',indicator=True,suffixes=('_a','_b'))
                if j['_merge'].eq('both').all() and j.prediction_a.equals(j.prediction_b):dedup.append({'target':target,'season':int(season),'outputs':[list(a),list(b)],'state':'IDENTICAL_FORECAST_VALUES_NOT_INDEPENDENT_SUPPORT','same_procedure':str(views[a].shortlist_group.iloc[0])==str(views[b].shortlist_group.iloc[0])})
    return {'version':VERSION,'state':'COMPLETED_CACHED_MATCHED_POINT_SCORING','records':records,'pairwise':pairs,'identical_output_audit':dedup,
      'new_fits':0,'new_model_inference':0,'new_forecasts':0,'scope':scope,'limitations':['Saved 2026W1-6 rows are not a completed W1-7 experiment.','Authentic offers, probability laws and later-seasons/W7 rows require their own compatible inputs.','Source clocks and unknown participation remain original; no retrospective website/R0 forecasts invented.']},f
