"""Owner-local saved B completion/profile replay. No fits, model loading or private rows written.

Execution requires the integrator's exact published finite protocol. Public
forecast packets are parsed as data, never deserialized models or imported code.
"""
from __future__ import annotations
import argparse,datetime,gzip,hashlib,importlib,io,json,math,os,platform,resource,signal,sys,time,zipfile
from collections import Counter,defaultdict
from decimal import Decimal
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
VERSION='PROFILE-INCREMENT-CLOSURE-AND-NEXT-02-A-B-CMP-SAVED-JOIN-v1'
B_SOURCE='62cbf5af364ad8b3a5d178cd7ed6221ee43c5f26'
B_CURRENT='05032e19e30b1f890a6b2679c70d3c97f0bbb2a1'
B_NAMESPACE='B-QB-OPPORTUNITY-PROFILE-INCREMENT-v1'
ARMS=['R0','R1','R2','R3']
PRODUCTS=['mean','lower_median','P2']
SOURCE_SHA=dict(offers='f224f17930e8da7ed5683808de3339d9656cc4b71edb0deefcfb9c48dfd82ffb',qualified_labels='61da98ad90542b07c6c6664b674086ba4f9474e597325aba62dec44bb2fa72f5',frozen_bundle='753970f359a5089286dde4c7ace6eeeb02c82b59eed07a50fd8ecc797eec8c33')
MEMBER_SHA='7d849d60902a2aa0a4922dd1ba0d09d4e0a21290cb5121e48279c6f54349e23f'
ALLOCATION='f123cd5ffd6f4a204a76c68bf63817cce63cecd7021543a23503d0233cc3eb26'
PHASE='NOT_STARTED'

def enc(v):return (json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def check(v,m):
    if not v:raise ValueError(m)
def pin(p,h,size=None):
    b=Path(p).read_bytes();check(sha(b)==h and(size is None or len(b)==size),'Bound file bytes differ');return b
def finite(v):return type(v)in[int,float]and math.isfinite(v)
def point_side(p,l):
    if p is None:return None
    a,b=Decimal(str(p)),Decimal(str(l));return'OVER'if a>b else'UNDER'if a<b else'ABSTAIN'
def grade(r):
    s=r['selected_side']
    if s is None:return'UNAVAILABLE_FORECAST'
    if s=='ABSTAIN':return'ABSTAIN'
    if r['appearance']!='PLAYED':return {'DNP':'DNP','PENDING':'PENDING'}.get(r['appearance'],'UNKNOWN_PARTICIPATION')
    if r['actual']is None:return'MISSING_ACTUAL'
    a,b=Decimal(str(r['actual'])),Decimal(str(r['line']))
    return'PUSH'if a==b else'WIN'if(a>b)==(s=='OVER')else'LOSS'
def mask(rows,decided=False):return sha(enc(sorted(r['opportunity_key']for r in rows if not decided or r['status']in['WIN','LOSS'])))

def law_prepare(law,mean,median):
    check(law['kind']=='leaf_mixture','Unexpected retained B law type')
    y,w=law['support'],law['weights'];b=law['mixture'];p=law['prior']
    check(len(y)==len(w)>0 and all(finite(v)and v>=0 and v==int(v)for v in y),'B count support invalid')
    check(all(a<c for a,c in zip(y,y[1:]))and all(finite(v)and v>=0 for v in w)and abs(math.fsum(w)-1)<1e-9,'B law mass invalid')
    check(finite(b)and 0<=b<=1 and p['kind']in['zero','geometric'],'B prior contract invalid')
    q=0. if p['kind']=='zero'else p['q'];check(finite(q)and 0<=q<1,'B geometric prior invalid')
    m=(1-b)*math.fsum(a*c for a,c in zip(y,w))+b*q/(1-q)
    check(abs(m-mean)<=1e-8*max(1,abs(mean)),'Retained B mean differs from law')
    def cdf(x):
        k=math.floor(x);prior=0. if k<0 else 1.-q**(k+1)
        return(1-b)*math.fsum(z for a,z in zip(y,w)if a<=k)+b*prior
    check(cdf(median)>=.5-1e-10 and cdf(median-1)<.5+1e-10,'Retained B lower median differs from law')
    return cdf
def probabilities(cdf,line):
    u=cdf(math.ceil(line)-1);o=1-cdf(math.floor(line));p=cdf(line)-cdf(line-1)if line==math.floor(line)else 0.
    check(all(math.isfinite(v)and-1e-10<=v<=1+1e-10 for v in[u,p,o])and abs(u+p+o-1)<1e-9,'Exact-line law not normalized')
    return dict(p_under=max(0.,u),p_push=max(0.,p),p_over=max(0.,o))
def probability_side(p):return'OVER'if p['p_over']>p['p_under']else'UNDER'if p['p_under']>p['p_over']else'ABSTAIN'

def numerical(rows):
    q=[r for r in rows if r['point']is not None and r['actual']is not None and r['appearance']=='PLAYED'];e=[r['point']-r['actual']for r in q];a=sorted(map(abs,e))
    return dict(scored=len(e),MAE=math.fsum(a)/len(e)if e else None,MSE=math.fsum(v*v for v in e)/len(e)if e else None,bias=math.fsum(e)/len(e)if e else None,max_absolute_error=max(a)if a else None,absolute_error_p90=a[min(len(a)-1,math.ceil(.9*len(a))-1)]if a else None,learned_or_fallback_states=dict(Counter(str(r['fallback'])for r in q)))
def probscores(rows):
    q=[r for r in rows if r.get('p_over')is not None and r['actual']is not None and r['appearance']=='PLAYED'];b=[];ll=[];inf=0;rel=defaultdict(list)
    for r in q:
        y,l=r['actual'],r['line'];p=r['p_over'];b.append((p-float(y>l))**2);v=r['p_under']if y<l else r['p_push']if y==l else p
        if v>0:ll.append(-math.log(v))
        else:inf+=1
        rel[min(9,int(p*10))].append((p,float(y>l)))
    pos=[r['p_over']for r in q if r['actual']>r['line']];neg=[r['p_over']for r in q if r['actual']<=r['line']]
    auc=math.fsum(float(a>b)+.5*float(a==b)for a in pos for b in neg)/(len(pos)*len(neg))if pos and neg else None
    return dict(events=len(q),Brier=math.fsum(b)/len(b)if b else None,three_state_log_loss=math.fsum(ll)/len(ll)if ll and not inf else None,infinite_log_loss_cases=inf,neutral_binary_half_Brier=.25 if q else None,Over_event_AUC=auc,reliability_fixed_bins=[dict(bin_index=k,count=len(v),predicted_Over=math.fsum(a for a,b in v)/len(v),observed_Over=math.fsum(b for a,b in v)/len(v))for k,v in sorted(rel.items())],conditioning='B retained physical-participation law; strict Over event. Push is false for binary event; venue nonvoid contract unverified. No recalibration/gate.')

def interval(groups,np):
    if len(groups)<2:return None
    g=[groups[k]for k in sorted(groups)];a=np.array([sum(v)for v in g]);n=np.array([len(v)for v in g]);rng=np.random.default_rng(20261110);ix=rng.integers(0,len(g),(500,len(g)));return list(map(float,np.quantile(a[ix].sum(axis=1)/n[ix].sum(axis=1),[.025,.975])))
def paired(left,right,np):
    lookup={r['opportunity_key']:r for r in right};check(len(lookup)==len(right),'Duplicate pair identity');check({r['opportunity_key']for r in left}==set(lookup),'Paired outer opportunity masks differ');matched=[(a,lookup[a['opportunity_key']])for a in left]
    for a,b in matched:
        check(all(a.get(k)==b.get(k)for k in['season','week','game_id','player_id','category','line','actual','appearance']),'Paired identity, threshold or outcome differs')
    known=[(a,b)for a,b in matched if a['appearance']=='PLAYED'and finite(a['actual'])and finite(b['actual'])]
    q=[(a,b)for a,b in matched if a['status']in['WIN','LOSS']and b['status']in['WIN','LOSS']];games=defaultdict(list);weeks=defaultdict(list)
    for a,b in q:
        d=int(a['status']=='WIN')-int(b['status']=='WIN');games[a['game_id']].append(d);weeks[a['week']].append(d)
    nums=[(a,b)for a,b in known if finite(a['point'])and finite(b['point'])];ng=defaultdict(list);nw=defaultdict(list)
    for a,b in nums:
        d=abs(a['point']-a['actual'])-abs(b['point']-b['actual']);ng[a['game_id']].append(d);nw[a['week']].append(d)
    laws=[(a,b)for a,b in known if finite(a.get('p_over'))and finite(b.get('p_over'))];pg=defaultdict(list);pw=defaultdict(list)
    for a,b in laws:
        y=float(a['actual']>a['line']);d=(a['p_over']-y)**2-(b['p_over']-y)**2;pg[a['game_id']].append(d);pw[a['week']].append(d)
    lw=sum(a['status']=='WIN'for a,b in q);rw=sum(b['status']=='WIN'for a,b in q)
    return dict(common_decided=len(q),left_wins=lw,right_wins=rw,accuracy_change=(lw-rw)/len(q)if q else None,side_disagreements=sum(a['selected_side']!=b['selected_side']for a,b in q),game_clusters=len(games),week_clusters=len(weeks),game_interval95=interval(games,np),week_interval95=interval(weeks,np),decided_mask_sha256=mask([a for a,b in q]),common_numerical=len(nums),numerical_mask_sha256=mask([a for a,b in nums]),MAE_change=math.fsum(v for g in ng.values()for v in g)/len(nums)if nums else None,MAE_game_interval95=interval(ng,np),MAE_week_interval95=interval(nw,np),common_law_events=len(laws),law_mask_sha256=mask([a for a,b in laws]),Brier_change=math.fsum(v for g in pg.values()for v in g)/len(laws)if laws else None,Brier_game_interval95=interval(pg,np),Brier_week_interval95=interval(pw,np))

def run(args):
    global PHASE
    start=time.monotonic();cpu=time.process_time();PHASE='REGISTRATION';raw=pin(args.protocol,args.protocol_sha256);p=json.loads(raw)
    check(p['id']==VERSION and p['state']=='ROOT_REGISTERED_SCORING_GO','Exact published completion GO required')
    check(p['new_fits']==p['new_model_inference']==p['native_writes']==0,'Zero-fit/inference/native-write scope differs')
    for f,h in p['code_sha256'].items():pin(ROOT/f,h)
    for f,h in p['original_source_configs_sha256'].items():pin(ROOT/f,h)
    budget=p['resources'];resource.setrlimit(resource.RLIMIT_CPU,(budget['CPU_seconds'],)*2);resource.setrlimit(resource.RLIMIT_AS,(budget['RSS_bytes'],)*2);signal.alarm(budget['wall_seconds'])
    for n in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[n]='1'
    import numpy as np
    import pandas as pd
    import pyarrow as pa
    runtime=dict(python=platform.python_version(),numpy=np.__version__,pandas=pd.__version__,pyarrow=pa.__version__)
    check(runtime==p['runtime'],'Exact pinned runtime package versions required')
    pa.set_cpu_count(1);pa.set_io_thread_count(1);pa.set_memory_pool(pa.system_memory_pool());sys.path.insert(0,str(ROOT))
    for f,h in p['C_bound_code'].items():pin(args.c_cache/f,h)
    sys.path.insert(0,str(args.c_cache));common=importlib.import_module('abc_championship_v2')
    a_products=[tuple(v)for v in p['A_products']];a_ids=['A::'+a+'::'+b for a,b in a_products];b_ids=[B_NAMESPACE+':'+a+'::'+z for a in ARMS for z in PRODUCTS];ids=a_ids+b_ids+['ALWAYS_OVER','ALWAYS_UNDER']
    check(ids==p['candidate_ids'],'Registered product identities differ');pairs=p['paired_candidate_ids'];check(len({tuple(q)for q in pairs})==len(pairs)and all(a in ids and b in ids for a,b in pairs),'Registered pairs invalid')
    PHASE='PUBLIC_SAVED_FORECASTS';cache={};cdf={};inventory=[]
    check(sum(r['bytes']for r in p['B_forecast_refs'])<=8*1024**2,'Public packet cache exceeds8MiB')
    for ref in p['B_forecast_refs']:
        body=pin(args.b_cache/ref['id'],ref['sha256'],ref['bytes']);v=json.loads(gzip.decompress(body));week=ref['week'];check(v['season']==2026 and v['week']==week and v['original_issuance']is False,'B packet period/issuance differs');counts=Counter()
        for r in v['rows']:
            arm=r['method'];check(arm in ARMS and r['procedure_id']==B_NAMESPACE+':'+arm and r['target']=='pass_cmp'and r['position']=='QB','B procedure/target/role differs')
            check(r['season']==2026 and r['week']==week and r['original_issuance']is False,'B row period differs');check(finite(r['fit_cutoff'])and finite(r['feature_cutoff'])and r['fit_cutoff']<=r['feature_cutoff'],'B history clocks differ')
            check(r.get('latest_source_available')is None or r['latest_source_available']<r['feature_cutoff'],'B source is not earlier')
            check(all(finite(r[k])and r[k]>=0 for k in['mean','lower_median']),'B saved count point invalid');check(r['history_regime']=='H-RECENT'and r['feature_memory']=='2022_EXPANDING','B history identity differs')
            k=(arm,str(r['game_id']),str(r['player_id']));check(k not in cache,'Duplicate B arm/player-game');cache[k]=r;cdf[k]=law_prepare(r['law'],r['mean'],r['lower_median']);counts[arm]+=1
        inventory.append(dict(week=week,bytes=len(body),sha256=sha(body),arm_rows=dict(counts)))
    PHASE='ORIGINAL_READONLY_SOURCE_GATE'
    from tools import category_topfive_matched12_storage_v1 as storage
    from tools import abc_a_dynamic_carry_wave_v1 as base
    store,_=storage.open_store(ROOT,allocation_sha256=ALLOCATION,root_go=storage.GO,readonly=True);_,_,g,_=base.sources()
    check(all(g[k]['sha256']==h for k,h in SOURCE_SHA.items()),'A original source version differs')
    PHASE='ORIGINAL_METRIC_PRESENT_SOURCES'
    with zipfile.ZipFile(io.BytesIO(base.pin(g['frozen_bundle'])))as z:
        a=z.read('FORECASTS.parquet');check(sha(a)==MEMBER_SHA,'A forecast member differs');af=pd.read_parquet(io.BytesIO(a))
    af=af.loc[af.target.eq('pass_cmp')&af.season.eq(2026)&af.week.between(1,7)].copy();check(not af.duplicated(['method','product','season','game_id','player_id']).any(),'A saved product identities ambiguous')
    av={};provenance={}
    for cid,(m,o)in zip(a_ids,a_products):
        s=af.loc[af.method.eq(m)&af['product'].eq(o)];av[cid]={(str(r['game_id']),str(r['player_id'])):r for r in s.to_dict('records')};fields=[f for f in['output_procedure_version','source_forecast_sha256','source_forecast_member_sha256','source_information_policy','source_issue_time_UTC']if f in s];provenance[cid]=dict(method=m,product=o,rows=len(s),state='RETAINED'if len(s)else'NOT_RETAINED',bindings=[{k:None if pd.isna(v)else str(v)for k,v in r.items()}for r in s[fields].drop_duplicates().to_dict('records')])
    with zipfile.ZipFile(io.BytesIO(base.pin(g['offers'])))as z:offers=pd.read_parquet(io.BytesIO(z.read(g['offers']['member'])))
    with zipfile.ZipFile(io.BytesIO(base.pin(g['qualified_labels'])))as z:labels=pd.read_parquet(io.BytesIO(z.read(g['qualified_labels']['member'])))
    source_inventory=[]
    for week in range(1,9):
        s=offers.loc[offers.target.eq('pass_cmp')&offers.season.eq(2026)&offers.week.eq(week)];source_inventory.append(dict(week=week,offers=len(s),games=int(s.game_id.nunique()),source_panels=dict(Counter(map(str,s.source_stream)))))
    board=offers.loc[offers.target.eq('pass_cmp')&offers.season.eq(2026)&offers.week.between(1,7)].copy();check(not board.duplicated(['season','game_id','player_id']).any()and not board.opportunity_key.duplicated().any(),'A primary completion offers ambiguous')
    labels=labels.loc[labels.target.eq('pass_cmp')&labels.season.eq(2026)&labels.week.between(1,7)];check(not labels.duplicated(['season','game_id','player_id']).any(),'A labels ambiguous');lm={(str(r.game_id),str(r.player_id)):r for r in labels.itertuples()}
    PHASE='SAVED_POINT_AND_LAW_EXACT_LINE_JOIN';vectors={i:[]for i in ids};full=set(map(str,board.opportunity_key));b_shared=set();members=[];conflicts=Counter();badkeys=[]
    def match(r,o,who):
        if r is None:return'MISSING_'+who+'_RETAINED_CANONICAL_QB_GAME'
        if r['position']!=o['position']or r['team']!=o['team']or r['opponent']!=o['opponent']:return who+'_ROLE_TEAM_OPPONENT_MISMATCH'
        for f in ['kickoff_utc','cutoff_utc']:
            oq=pd.Timestamp(o[f]);fq=pd.Timestamp(r[f])if who=='A'else pd.Timestamp(r['feature_cutoff'],unit='s',tz='UTC')
            if oq.tzinfo is None or fq.tzinfo is None or oq!=fq:return who+'_EXACT_'+f.upper()+'_MISMATCH'
        return None
    for o in board.to_dict('records'):
        check(o['position']=='QB'and finite(float(o['line'])),'A completion offer contract differs');k=(str(o['game_id']),str(o['player_id']));lab=lm.get(k);st=getattr(lab,'participation_state',None);appearance='PENDING'if getattr(lab,'outcome_state',None)=='pending'else'DNP'if str(st).lower()=='dnp'else'PLAYED'if st=='played'else'UNKNOWN';actual=getattr(lab,'actual',None);actual=float(actual)if appearance=='PLAYED'and finite(actual)and actual>=0 and actual==math.floor(actual)else None
        if actual is not None:check(getattr(lab,'label_reason',None)in['EXPLICIT_REPORTED_ZERO','EXPLICIT_REPORTED_VALUE']and bool(getattr(lab,'participation_evidence',None)),'A metric-presence/participation contract differs')
        bs={arm:cache.get((arm,*k))for arm in ARMS};why={arm:match(bs[arm],o,'B')for arm in ARMS}
        if not any(why.values()):b_shared.add(str(o['opportunity_key']))
        for arm,r in bs.items():
            if r is not None:
                check(r['week']==int(o['week']),'B target week differs')
                if actual is not None and finite(r.get('actual'))and r['actual']!=actual:conflicts[arm]+=1;badkeys.append(sha(enc([arm,*k])))
        for cid in ids:
            point=None;prob=None;side=None;fallback=None;reason=None;own_no_history=None;clock=None
            if cid in a_ids:
                r=av[cid].get(k);reason=match(r,o,'A')
                if reason is None:
                    point=float(r['prediction'])if finite(r['prediction'])else None;reason=None if point is not None else'A_POINT_UNAVAILABLE';fallback=None if pd.isna(r['fallback'])else str(r['fallback']);clock=str(r['cutoff_utc'])
                side=point_side(point,o['line'])
            elif cid.startswith(B_NAMESPACE+':'):
                arm,prod=cid.removeprefix(B_NAMESPACE+':').split('::');r=bs[arm];reason=why[arm]
                if reason is None:
                    prob=probabilities(cdf[(arm,*k)],float(o['line']));point=None if prod=='P2'else r[prod];side=probability_side(prob)if prod=='P2'else point_side(point,o['line']);fallback=r.get('fallback');own_no_history=r.get('own_prior_games')==0;clock=r['feature_cutoff']
            else:side=cid.removeprefix('ALWAYS_')
            row=dict(season=2026,week=int(o['week']),game_id=k[0],player_id=k[1],category='pass_cmp',comparator='STRICT_OVER_UNDER',line=float(o['line']),actual=actual,appearance=appearance,point=point,selected_side=side,candidate_id=cid,opportunity_key=str(o['opportunity_key']),source_stream=str(o['source_stream']),fallback=fallback,unavailability_reason=reason,no_own_history=own_no_history,**(prob or{}));row['status']=grade(row);check(common.status(row)==row['status'],'Canonical and independent grades differ');vectors[cid].append(row)
            members.append([cid,row['opportunity_key'],str(o['line']),str(o['source_stream']),str(o['source_sha256']),str(o['quote_timing_status']),point,prob,appearance,actual,side,row['status'],clock])
    PHASE='FROZEN_METHOD_AND_STRONG_CONTROL_SUMMARIES';summaries=[];contrasts=[];panels=['ALL']+sorted(set(map(str,board.source_stream)));views=[('FULL_A_BOARD',full),('SHARED_ALL_FOUR_B_ARMS',b_shared)]
    for view,selected in views:
        vv={i:[r for r in v if r['opportunity_key']in selected]for i,v in vectors.items()}
        for panel in panels:
            pp={i:[r for r in v if panel=='ALL'or r['source_stream']==panel]for i,v in vv.items()}
            for cid,rs in pp.items():
                for week in ['ALL']+list(range(1,9)):
                    rr=[r for r in rs if week=='ALL'or r['week']==week];aw=sorted({r['week']for r in rr if r['source_stream']=='ANNUAL_NAMED_NJ'and r['status']in['WIN','LOSS','PUSH']});summaries.append(dict(candidate_id=cid,view=view,source_panel=panel,week_view=week,requested_weeks=list(range(1,9)),actual_retained_threshold_scored_weeks=aw,diagnostic_scored_weeks=sorted({r['week']for r in rr if r['status']in['WIN','LOSS','PUSH']}),**common.summary(rr),numerical=numerical(rr),probability=probscores(rr),unavailable_reasons=dict(Counter(r['unavailability_reason']for r in rr if r['unavailability_reason'])),fallback_states=dict(Counter(str(r['fallback'])for r in rr)),no_own_history_queries=sum(r['no_own_history']is True for r in rr),forecast_outcome_cross_counts=[dict(forecast_available=a,appearance=b,known_actual=c,rows=n)for(a,b,c),n in sorted(Counter((r['selected_side']is not None,r['appearance'],r['actual']is not None)for r in rr).items())],eligible_mask_sha256=mask(rr),decided_mask_sha256=mask(rr,True),five_actual_week_duration_only=len(aw)>=5,admission='DURATION_ONLY_NOT_PRIMARY_ADMISSION;QUOTE_TIMING_UNVERIFIED'))
            for left,right in pairs:contrasts.append(dict(view=view,source_panel=panel,left=left,right=right,**paired(pp[left],pp[right],np)))
    PHASE='IMMUTABLE_AGGREGATE_RESULT';result=dict(id=VERSION,state='COMPLETED_OWNER_LOCAL_SAVED_COMPLETION_JOIN',UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),protocol_sha256=sha(raw),B_current_research_ref=B_CURRENT,B_scientific_producer_commit=B_SOURCE,B_forecast_inventory=inventory,A_source_sha256=SOURCE_SHA,A_member_sha256=MEMBER_SHA,A_product_provenance=provenance,A_CMP_source_inventory=source_inventory,candidate_ids=ids,eligible_A_offers=len(board),eligible_A_games=int(board.game_id.nunique()),shared_all_B_offers=len(b_shared),summaries=summaries,paired=contrasts,B_cached_actual_disagreements=dict(conflicts),B_cached_actual_conflict_case_hashes=sorted(set(badkeys)),outcome_policy='All forecasts regraded on exact bound A qualified outcome version. Original B predictions and original B grades unchanged; cached-actual differences retained separately, not silently zero-filled or discarded.',membership_sha256=sha(enc(sorted(members))),full_A_mask_sha256=sha(enc(sorted(full))),shared_B_mask_sha256=sha(enc(sorted(b_shared))),evidence_tier='CURRENT_VINTAGE_7DAY_RECONSTRUCTION;ANNUAL_W1_5_ACTUAL_RETAINED_LINES_QUOTE_TIMING_UNVERIFIED;SITE_W6_7_UNQUALIFIED_DIAGNOSTIC;NO_ORIGINAL_ISSUANCE',rules=dict(P1='unrounded saved point vs original line; equal abstains',P2='strictmaxOver/Under from same retained law; equal abstains; pushmass retained',W5='Aannual andBPropLine are different source opportunities on overlapping physical player-games, never concatenated here',prevalence='Exact new-A-line earlier-prevalence outputs not retained in selected packets; unavailable, not substituted from unmatched B aggregates',incumbent='B saved adjusted/raw controls live in its private offered-source rows; unavailable on this A board unless separately transferred; A saved named methods retained but not relabelled authenticated incumbent',joint='Saved completion law is marginal; no new completion-attempt joint model or silent cap',point_probability='No probabilities inferred for A point-only controls',current='No current query, primary release, TopPicks/EV or consumer acknowledgment implied'),resources=dict(CPU_seconds=time.process_time()-cpu,wall_seconds=time.monotonic()-start,RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024),counts=dict(new_fits=0,new_model_inference=0,new_source_acquisition=0,native_writes=0,protected_rows_published=0,production_writes=0))
    body=enc(result);check(len(gzip.compress(body,mtime=0))<=p['resources']['compressed_result_max_bytes'],'Finite aggregate result reservation exceeded')
    with args.output.open('xb')as f:f.write(gzip.compress(body,mtime=0)if args.output.suffix=='.gz'else body);f.flush();os.fsync(f.fileno())
    signal.alarm(0);print(json.dumps(dict(state=result['state'],A_offers=len(board),B_shared=len(b_shared),summaries=len(summaries),pairs=len(contrasts),sha256=sha(args.output.read_bytes()),resources=result['resources'])))

def main():
    a=argparse.ArgumentParser();a.add_argument('--protocol',type=Path,required=True);a.add_argument('--protocol-sha256',required=True);a.add_argument('--b-cache',type=Path,default=Path('/tmp/next02-b-public'));a.add_argument('--c-cache',type=Path,default=Path('/tmp/acceptance-c-review/src'));a.add_argument('--output',type=Path,required=True);v=a.parse_args();check(not v.output.exists(),'Immutable result already exists')
    try:run(v)
    except BaseException as e:
        signal.alarm(0);failure=dict(id=VERSION,state='FAILED_NO_AUTOMATIC_RETRY',phase=PHASE,error_type=type(e).__name__,error_sha256=sha(str(e).encode()),new_fits=0,new_model_inference=0,native_writes=0)
        q=v.output.with_name('B_CMP_JOIN_FAILURE_'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json');q.write_bytes(enc(failure));print(enc(failure).decode());raise
if __name__=='__main__':main()
