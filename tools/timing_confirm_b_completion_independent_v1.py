"""Independent arithmetic review of the exact saved B F0-F3 completion join.

This reader imports only A's approved immutable source IO. It never imports the
join's grading, law, summary or pairing functions, or loads forecasting models.
All cache locations are explicit operator arguments, not public private locators.
"""
from __future__ import annotations
import argparse,collections,datetime,gzip,hashlib,io,json,math,os,pathlib,platform,resource,signal,sys,time,zipfile
from decimal import Decimal,localcontext

NEW='B-QB-ALIGNED-FRESHNESS-v1'
OLD='B-QB-OPPORTUNITY-PROFILE-INCREMENT-v1'
ARMS=('F0','F1','F2','F3')
PRODUCTS=('mean','lower_median','P2')
RESULT_SHA='841d874dd4eb15d7aca10195464ba54a6200d1ee0639e89df12885bf23707cf0'
GO_SHA='69c84b8b7b31d501cc508e6d002cd5226b33eae45e37543f71b81a6e785f329e'
PHASE='NOT_STARTED'
def sha(body):return hashlib.sha256(body).hexdigest()
def enc(v):return(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def require(ok,message):
    if not ok:raise AssertionError(message)
def finite(v):
    try:return v is not None and not isinstance(v,bool)and math.isfinite(float(v))
    except(TypeError,ValueError):return False
def same(a,b,tol=1e-10):return(a is None and b is None)or(a is not None and b is not None and abs(float(a)-float(b))<=tol)
def team(v):return'LAR'if str(v)=='LA'else str(v)
def point_direction(point,line):
    if point is None:return None
    x,l=Decimal(str(point)),Decimal(str(line));return'OVER'if x>l else'UNDER'if x<l else'ABSTAIN'
def state(side,participation,actual,line):
    if side is None:return'UNAVAILABLE_FORECAST'
    if side=='ABSTAIN':return'ABSTAIN'
    if participation!='PLAYED':return participation if participation in('DNP','PENDING')else'UNKNOWN_PARTICIPATION'
    if actual is None:return'MISSING_ACTUAL'
    y,l=Decimal(str(actual)),Decimal(str(line))
    if y==l:return'PUSH'
    return'WIN'if(side=='OVER'and y>l)or(side=='UNDER'and y<l)else'LOSS'
def membership(rows):return sha(enc(sorted(r['key']for r in rows)))
def read_bound(path,digest,size=None):
    b=path.read_bytes();require(sha(b)==digest and(size is None or len(b)==size),'Bound immutable bytes mismatch');return b

def run(args):
    global PHASE
    cpu=time.process_time();wall=time.monotonic();resource.setrlimit(resource.RLIMIT_CPU,(145,150));resource.setrlimit(resource.RLIMIT_AS,(3*1024**3,)*2);signal.alarm(590)
    for n in('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[n]='1'
    def no_network(event,_):
        if event in('socket.connect','socket.connect_ex','socket.getaddrinfo'):raise RuntimeError('Independent verification is offline')
    sys.addaudithook(no_network)
    import numpy as np
    import pandas as pd
    import pyarrow as pa
    pa.set_cpu_count(1);pa.set_io_thread_count(1)
    root=args.root.resolve();sys.path.insert(0,str(root));PHASE='BOUND_SCORE_AND_PROTOCOL'
    source_hash=sha(pathlib.Path(__file__).read_bytes());require(source_hash==args.expected_code_sha256,'Independent checker source differs from pre-NFL freeze')
    result_raw=read_bound(args.result,RESULT_SHA);result=json.loads(gzip.decompress(result_raw));go_raw=read_bound(args.protocol,GO_SHA);go=json.loads(go_raw)
    require(result['protocol_sha256']==GO_SHA,'Scored protocol differs')
    for relative,digest in go['code_sha256'].items():read_bound(root/relative,digest)
    for relative,digest in go['original_source_configs_sha256'].items():read_bound(root/relative,digest)
    previous_raw=read_bound(root/go['predecessor_result']['path'],go['predecessor_result']['sha256']);previous=json.loads(gzip.decompress(previous_raw))
    new_ids=[NEW+':'+a+'::'+z for a in ARMS for z in PRODUCTS]
    require(all(i in result['candidate_ids']for i in new_ids),'New candidate roster incomplete')
    old_ids=set(previous['candidate_ids']);old_s={(s['candidate_id'],s['source_panel'],s['week_view']):s for s in previous['summaries']if s['view']=='FULL_A_BOARD'}
    now_s={(s['candidate_id'],s['source_panel'],s['week_view']):s for s in result['summaries']if s['view']=='FULL_A_BOARD'and s['candidate_id']in old_ids}
    old_p={(s['left'],s['right'],s['source_panel']):s for s in previous['paired']if s['view']=='FULL_A_BOARD'}
    now_p={(s['left'],s['right'],s['source_panel']):s for s in result['paired']if s['view']=='FULL_A_BOARD'and(s['left'],s['right'],s['source_panel'])in old_p}
    require(old_s==now_s and len(old_s)==594,'Old FULL summaries changed');require(old_p==now_p and len(old_p)==453,'Old FULL pairs changed')
    PHASE='PUBLIC_SAVED_LAW_AND_REUSE_VERIFICATION';cache={};old_cache={};laws=0;reuse=0;moment_error=0.;median_checks=0;inventory=[]
    fields=['mean','lower_median','law','features','fit_cutoff','feature_cutoff','latest_source_available','history_regime','feature_memory','fallback','own_prior_games','position','team','opponent','season','week','game_id','player_id','target']
    for ns,refs,folder,destination in((OLD,go['B_retained_forecast_refs'],args.old_b_cache,old_cache),(NEW,go['B_forecast_refs'],args.b_cache,cache)):
        for ref in refs:
            body=read_bound(folder/ref['id'],ref['sha256'],ref['bytes']);packet=json.loads(gzip.decompress(body));require(packet['season']==2026 and packet['week']==ref['week']and packet['original_issuance']is False,'Packet period/issuance differs');counts=collections.Counter()
            for row in packet['rows']:
                arm=row['method'];require(row['procedure_id']==ns+':'+arm and row['target']=='pass_cmp'and row['position']=='QB','Exact saved procedure/role differs');require(row['history_regime']=='H-RECENT'and row['feature_memory']=='2022_EXPANDING','History identity differs')
                require(row['fit_cutoff']<=row['feature_cutoff']and(row.get('latest_source_available')is None or row['latest_source_available']<row['feature_cutoff']),'Saved source/fit clocks violate declared chronology')
                k=(arm,str(row['game_id']),str(row['player_id']));require(k not in destination,'Duplicate saved identity');destination[k]=row;counts[arm]+=1
                if ns==OLD:continue
                require(arm in ARMS and row['new_inference']==(arm in('F2','F3')),'New/reused identity differs');expected='ORIGINAL_SEVEN_DAY_RECONSTRUCTION'if arm in('F0','F1')else'DECLARED_KICKOFF_PLUS_48H_TIMING_SENSITIVITY';require(row['information_policy']==expected,'Timing policy differs')
                law=row['law'];ys,ws=law['support'],law['weights'];require(law['kind']=='leaf_mixture'and len(ys)==len(ws)>0 and ys==sorted(set(ys)),'Retained law support differs');require(all(finite(v)and float(v)>=0 and float(v).is_integer()for v in ys)and all(finite(v)and v>=0 for v in ws)and abs(math.fsum(ws)-1)<1e-9,'Retained law mass invalid')
                mix=law['mixture'];prior=law['prior'];require(prior['kind']in('zero','geometric'),'Unsupported prior');q=0. if prior['kind']=='zero'else prior['q'];require(0<=mix<=1 and 0<=q<1,'Mixture/prior bounds differ')
                with localcontext()as ctx:
                    ctx.prec=50;d=Decimal;mean=(1-d(str(mix)))*sum(d(str(y))*d(str(w))for y,w in zip(ys,ws))+d(str(mix))*d(str(q))/(1-d(str(q)))
                err=abs(float(mean)-row['mean']);moment_error=max(moment_error,err);require(err<=1e-8*max(1,abs(row['mean'])),'Saved mean inconsistent with independent law moment')
                def prefix(n):return 0. if n<0 else(1-mix)*math.fsum(w for y,w in zip(ys,ws)if y<=n)+mix*(1-q**(n+1))
                m=row['lower_median'];require(finite(m)and m>=0 and float(m).is_integer()and prefix(m)>=.5-1e-10 and prefix(m-1)<.5+1e-10,'Saved lower median inconsistent with law');laws+=1;median_checks+=1
                if arm in('F0','F1'):
                    oldarm='R0'if arm=='F0'else'R2';z=old_cache.get((oldarm,k[1],k[2]));require(z is not None and all(row.get(f)==z.get(f)for f in fields),'F0/F1 differs from retained own baseline');oldref=next(r for r in go['B_retained_forecast_refs']if r['week']==ref['week']);require(row['reused_original_procedure_id']==OLD+':'+oldarm and row['reused_artifact_sha256']==oldref['sha256'],'Reuse commitment differs');reuse+=1
            if ns==NEW:inventory.append(dict(week=ref['week'],bytes=len(body),sha256=sha(body),arm_rows=dict(counts)))
    require(laws==1108 and reuse==554 and inventory==result['B_forecast_inventory'],'Saved packet count/inventory differs')
    PHASE='ORIGINAL_A_READONLY_SOURCE_IO'
    from tools import category_topfive_matched12_storage_v1 as original_storage
    from tools import abc_a_dynamic_carry_wave_v1 as original_sources
    store,_=original_storage.open_store(root,allocation_sha256='f123cd5ffd6f4a204a76c68bf63817cce63cecd7021543a23503d0233cc3eb26',root_go=original_storage.GO,readonly=True)
    _,_,refs,_=original_sources.sources();require(all(refs[k]['sha256']==h for k,h in result['A_source_sha256'].items()),'Original A source hash mismatch')
    def member(key):
        with zipfile.ZipFile(io.BytesIO(original_sources.pin(refs[key])))as z:return z.read(refs[key]['member'])
    offers=pd.read_parquet(io.BytesIO(member('offers')));labels=pd.read_parquet(io.BytesIO(member('qualified_labels')))
    with zipfile.ZipFile(io.BytesIO(original_sources.pin(refs['frozen_bundle'])))as z:require(sha(z.read('FORECASTS.parquet'))==result['A_member_sha256'],'Original A retained forecast member differs')
    use=lambda frame:frame.loc[frame.target.eq('pass_cmp')&frame.season.eq(2026)&frame.week.between(1,7)].copy()
    board=use(offers);labels=use(labels);require(len(board)==144 and not board.duplicated(['game_id','player_id']).any()and not board.opportunity_key.duplicated().any(),'A board identity differs');require(not labels.duplicated(['game_id','player_id']).any(),'A label identity differs')
    lm={(str(r['game_id']),str(r['player_id'])):r for r in labels.to_dict('records')};vectors={cid:[]for cid in new_ids};shared=set();strict=set();conflicts=collections.Counter();tails=0;normalization_error=0.;monotonicity=0
    def compatible(row,offer,canonical=True):
        if row is None or row['position']!=offer['position']:return False
        transform=team if canonical else str
        if any(transform(row[f])!=transform(offer[f])for f in('team','opponent')):return False
        clock=pd.Timestamp(row['feature_cutoff'],unit='s',tz='UTC')
        for f in('kickoff_utc','cutoff_utc'):
            target=pd.Timestamp(offer[f])
            if target.tzinfo is None or clock!=target:return False
        return True
    def probabilities(law,line):
        nonlocal tails,normalization_error,monotonicity
        ys,ws=law['support'],law['weights'];mix=law['mixture'];q=0. if law['prior']['kind']=='zero'else law['prior']['q']
        def cdf(n):return 0. if n<0 else(1-mix)*math.fsum(w for y,w in zip(ys,ws)if y<=n)+mix*(1-q**(n+1))
        u=cdf(math.ceil(line)-1);o=1-cdf(math.floor(line));p=cdf(int(line))-cdf(int(line)-1)if float(line).is_integer()else 0.;total=u+p+o;normalization_error=max(normalization_error,abs(total-1));require(min(u,p,o)>=-1e-10 and max(u,p,o)<=1+1e-10 and abs(total-1)<1e-9,'Exact event law invalid');n=math.floor(line);require(cdf(n-1)<=cdf(n)+1e-12<=cdf(n+1)+1e-12,'CDF monotonicity failed');monotonicity+=1;tails+=1;return tuple(max(0.,v)for v in(u,p,o))
    for offer in board.to_dict('records'):
        k=(str(offer['game_id']),str(offer['player_id']));key=str(offer['opportunity_key']);line=float(offer['line']);require(offer['position']=='QB'and finite(line),'Offer role/line invalid');label=lm.get(k);participation='UNKNOWN';actual=None
        if label is not None:
            participation='PENDING'if label.get('outcome_state')=='pending'else'DNP'if str(label.get('participation_state')).lower()=='dnp'else'PLAYED'if label.get('participation_state')=='played'else'UNKNOWN'
            if participation=='PLAYED'and finite(label.get('actual'))and float(label['actual'])>=0 and float(label['actual']).is_integer():actual=float(label['actual']);require(label['label_reason']in('EXPLICIT_REPORTED_ZERO','EXPLICIT_REPORTED_VALUE')and bool(label['participation_evidence']),'A label presence contract invalid')
        rows={a:cache.get((a,*k))for a in ARMS}
        if all(compatible(r,offer)for r in rows.values()):shared.add(key)
        if all(compatible(r,offer,False)for r in rows.values()):strict.add(key)
        for arm,row in rows.items():
            if row is not None and actual is not None and finite(row.get('actual'))and float(row['actual'])!=actual:conflicts[NEW+':'+arm]+=1
            prob=probabilities(row['law'],line)if compatible(row,offer)else None
            for product in PRODUCTS:
                cid=NEW+':'+arm+'::'+product;point=None if prob is None or product=='P2'else row[product];direction=None if prob is None else('OVER'if prob[2]>prob[0]else'UNDER'if prob[0]>prob[2]else'ABSTAIN')if product=='P2'else point_direction(point,line)
                vectors[cid].append(dict(key=key,game=k[0],player=k[1],week=int(offer['week']),panel=str(offer['source_stream']),line=line,actual=actual,appearance=participation,point=point,side=direction,status=state(direction,participation,actual,line),prob=prob,fallback=row.get('fallback')if prob else None,nohistory=row.get('own_prior_games')==0 if prob else None))
    require(len(shared)==144 and len(strict)==133,'Canonical/strict B timing membership differs');require(membership([dict(key=k)for k in shared])==result['shared_B_mask_sha256'],'Shared source commitment differs')
    reported_conflicts={k:v for k,v in result['B_cached_actual_disagreements'].items()if k.startswith(NEW+':')};require(dict(conflicts)==reported_conflicts,'Cached actual disagreement scope differs')
    views={'FULL_A_BOARD':set(map(str,board.opportunity_key)),'SHARED_ALL_FOUR_B_TIMING_ARMS':shared,'CANONICAL_TEAM_ALIAS_TIMING_SUBGROUP':shared-strict}
    def selected(cid,view,panel,week='ALL'):return[r for r in vectors[cid]if r['key']in views[view]and(panel=='ALL'or r['panel']==panel)and(week=='ALL'or r['week']==week)]
    PHASE='INDEPENDENT_NEW_OWN_SIDE_METRICS';counts=collections.Counter();summaries=[s for s in result['summaries']if s['candidate_id']in new_ids]
    for s in summaries:
        rs=selected(s['candidate_id'],s['view'],s['source_panel'],s['week_view']);require(s['eligible']==len(rs)and s['games']==len({r['game']for r in rs}),'Summary population differs');require(s['states']==dict(collections.Counter(r['status']for r in rs)),'Summary status partition differs');require(membership(rs)==s['eligible_mask_sha256']and membership([r for r in rs if r['status']in('WIN','LOSS')])==s['decided_mask_sha256'],'Summary opportunity masks differ')
        aw=sorted({r['week']for r in rs if r['panel']=='ANNUAL_NAMED_NJ'and r['status']in('WIN','LOSS','PUSH')});dw=sorted({r['week']for r in rs if r['status']in('WIN','LOSS','PUSH')});require(s['actual_retained_threshold_scored_weeks']==aw and s['diagnostic_scored_weeks']==dw and s['five_actual_week_duration_only']==(len(aw)>=5),'Actual week/tier count differs')
        require(s['fallback_states']==dict(collections.Counter(str(r['fallback'])for r in rs))and s['no_own_history_queries']==sum(r['nohistory']is True for r in rs),'Fallback/no-history counts differ')
        for direction,label in(('OVER','OVER'),('UNDER','UNDER'),(None,'COMBINED')):
            rr=[r for r in rs if r['side']in('OVER','UNDER')and(direction is None or r['side']==direction)];wins=sum(r['status']=='WIN'for r in rr);losses=sum(r['status']=='LOSS'for r in rr);n=wins+losses;z=s[label];require(z['selected']==len(rr)and z['decided']==n and z['wins']==(wins if n else None)and z['losses']==(losses if n else None)and same(z['rate'],wins/n if n else None),'Own-side result differs');counts['side_partitions']+=1
        nr=[r for r in rs if r['appearance']=='PLAYED'and r['actual']is not None and r['point']is not None];errs=[r['point']-r['actual']for r in nr];ab=sorted(map(abs,errs));require(s['numerical']['scored']==len(nr),'Numerical population differs')
        metrics={'MAE':math.fsum(ab)/len(ab)if ab else None,'MSE':math.fsum(e*e for e in errs)/len(errs)if errs else None,'bias':math.fsum(errs)/len(errs)if errs else None,'max_absolute_error':max(ab)if ab else None,'absolute_error_p90':ab[min(len(ab)-1,math.ceil(.9*len(ab))-1)]if ab else None}
        for key,value in metrics.items():require(same(s['numerical'][key],value),'Numerical metric differs: '+key);counts['numerical_metrics']+=1
        require(s['numerical']['learned_or_fallback_states']==dict(collections.Counter(str(r['fallback'])for r in nr)),'Numerical learned/fallback mask differs')
        pr=[r for r in rs if r['appearance']=='PLAYED'and r['actual']is not None and r['prob']is not None];briers=[(r['prob'][2]-float(r['actual']>r['line']))**2 for r in pr];logs=[];inf=0;reliability=collections.defaultdict(list)
        for r in pr:
            u,p,o=r['prob'];q=u if r['actual']<r['line']else p if r['actual']==r['line']else o
            if q>0:logs.append(-math.log(q))
            else:inf+=1
            reliability[min(9,int(o*10))].append((o,float(r['actual']>r['line'])))
        probability=s['probability'];require(probability['events']==len(pr)and same(probability['Brier'],math.fsum(briers)/len(briers)if briers else None),'Brier/mask differs');require(probability['infinite_log_loss_cases']==inf and same(probability['three_state_log_loss'],math.fsum(logs)/len(logs)if logs and not inf else None),'Log loss differs');pos=[r['prob'][2]for r in pr if r['actual']>r['line']];neg=[r['prob'][2]for r in pr if r['actual']<=r['line']];auc=math.fsum(float(a>b)+.5*float(a==b)for a in pos for b in neg)/(len(pos)*len(neg))if pos and neg else None;require(same(probability['Over_event_AUC'],auc),'AUC differs')
        rr=[dict(bin_index=k,count=len(v),predicted_Over=math.fsum(a for a,b in v)/len(v),observed_Over=math.fsum(b for a,b in v)/len(v))for k,v in sorted(reliability.items())];require(len(rr)==len(probability['reliability_fixed_bins']),'Reliability bin count differs')
        for a,b in zip(rr,probability['reliability_fixed_bins']):require(a['bin_index']==b['bin_index']and a['count']==b['count']and same(a['predicted_Over'],b['predicted_Over'])and same(a['observed_Over'],b['observed_Over']),'Reliability bin arithmetic differs')
        counts['probability_cells']+=1;counts['summaries']+=1
    require(counts['summaries']==972,'New summary cell count differs')
    PHASE='INDEPENDENT_FOUR_PRIMARY_CONTRASTS';primary={((NEW+':'+a+'::'+z),(NEW+':'+b+'::'+z))for a,b in(('F1','F0'),('F2','F0'),('F3','F2'),('F3','F1'))for z in PRODUCTS};pair_rows=[p for p in result['paired']if(p['left'],p['right'])in primary]
    def resample(groups):
        if len(groups)<2:return None
        ordered=[groups[k]for k in sorted(groups)];totals=np.array([math.fsum(v)for v in ordered]);sizes=np.array([len(v)for v in ordered]);draw=np.random.default_rng(20261110).integers(0,len(ordered),(500,len(ordered)));return list(map(float,np.quantile(totals[draw].sum(axis=1)/sizes[draw].sum(axis=1),[.025,.975])))
    for p in pair_rows:
        left=selected(p['left'],p['view'],p['source_panel']);right=selected(p['right'],p['view'],p['source_panel']);lookup={r['key']:r for r in right};require(len(left)==len(right)==len(lookup)and{r['key']for r in left}==set(lookup),'Pair outer population differs');both=[(a,lookup[a['key']])for a in left];decided=[(a,b)for a,b in both if a['status']in('WIN','LOSS')and b['status']in('WIN','LOSS')];numeric=[(a,b)for a,b in both if a['appearance']=='PLAYED'and a['actual']is not None and a['point']is not None and b['point']is not None];law=[(a,b)for a,b in both if a['appearance']=='PLAYED'and a['actual']is not None and a['prob']is not None and b['prob']is not None]
        wins=sum(a['status']=='WIN'for a,b in decided);control=sum(b['status']=='WIN'for a,b in decided);require(p['common_decided']==len(decided)and p['left_wins']==wins and p['right_wins']==control and same(p['accuracy_change'],(wins-control)/len(decided)if decided else None),'Primary paired win arithmetic differs');require(p['side_disagreements']==sum(a['side']!=b['side']for a,b in decided),'Pair side disagreements differ')
        for rows,countkey,maskkey,changekey,intervalprefix,delta in((decided,'common_decided','decided_mask_sha256','accuracy_change','',lambda a,b:int(a['status']=='WIN')-int(b['status']=='WIN')),(numeric,'common_numerical','numerical_mask_sha256','MAE_change','MAE_',lambda a,b:abs(a['point']-a['actual'])-abs(b['point']-b['actual'])),(law,'common_law_events','law_mask_sha256','Brier_change','Brier_',lambda a,b:(a['prob'][2]-float(a['actual']>a['line']))**2-(b['prob'][2]-float(b['actual']>b['line']))**2)):
            require(p[countkey]==len(rows)and p[maskkey]==membership([a for a,b in rows]),'Primary paired scored mask differs');values=[delta(a,b)for a,b in rows];require(same(p[changekey],math.fsum(values)/len(values)if values else None),'Primary paired metric difference differs')
            for groupfield,kind in(('game','game'),('week','week')):
                groups=collections.defaultdict(list)
                for(a,b),value in zip(rows,values):groups[a[groupfield]].append(value)
                expected=resample(groups);actual_interval=p[intervalprefix+kind+'_interval95'];require((expected is None and actual_interval is None)or(expected is not None and actual_interval is not None and all(same(x,y,1e-9)for x,y in zip(expected,actual_interval))),'Primary paired cluster interval differs');counts['paired_intervals']+=1
                if not intervalprefix:require(p[kind+'_clusters']==len(groups),'Primary cluster count differs')
        counts['primary_contrasts']+=1
    require(counts['primary_contrasts']==108,'Four-contrast product/view/panel count differs')
    PHASE='RECEIPT';headline=[]
    for s in summaries:
        if s['view']=='FULL_A_BOARD'and s['source_panel']=='ANNUAL_NAMED_NJ'and s['week_view']=='ALL':headline.append({k:s[k]for k in('candidate_id','eligible','games','OVER','UNDER','COMBINED','numerical','probability','actual_retained_threshold_scored_weeks')})
    out=dict(id='A-TIMING-CONFIRM-B-COMPLETION-INDEPENDENT-v1',state='PASS_INDEPENDENT_ORIGINAL_SOURCE_DECIMAL_LAW_AND_PAIRED_ARITHMETIC',UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),code_sha256=source_hash,result_sha256=RESULT_SHA,protocol_sha256=GO_SHA,checked_scope=dict(**counts,new_products=12,old_FULL_summary_exact_reuse=594,old_FULL_pair_exact_reuse=453,old_other_views_independently_recomputed=False,public_laws=laws,law_mean_max_absolute_error=moment_error,law_lower_median_checks=median_checks,original_reuse_contracts=reuse,exact_line_events=tails,CDF_monotonicity_checks=monotonicity,normalization_max_error=normalization_error,canonical_offers=len(shared),strict_team_text_offers=len(strict),alias_only_offers=len(shared-strict)),A_source_sha256=result['A_source_sha256'],A_member_sha256=result['A_member_sha256'],counts_discrepancies=0,calculation='Independent original-source reader, Decimal point/label thresholds, separate finite-support/geometric law integration, own aggregation and paired cluster resampling. No author grade/law/summary/pair helper imported.',limits=['Within A separate calculation path, not independent private B source/model access.','No new fits, inference, model loading, acquisition, native writes or protected-row publication.','A W1-W5 retained actual thresholds have unverified original quote timing; W6-W7 stay a separate unqualified diagnostic.','B native W5-W8 and A W1-W5 source panels are not summed; overlapping W5 offer equivalence remains unresolved.','Old 22 FULL controls verified by exact immutable result equality, not relabeled as a new independent recomputation of all old views.','Historical timing sensitivity and point/probability products remain separately typed; no original issuance, current feed, Top Picks, EV or release claim.'],annual_W1_W5_new_product_headlines=headline,resources=dict(CPU_seconds=time.process_time()-cpu,wall_seconds=time.monotonic()-wall,RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,limit_CPU_seconds=150,limit_wall_seconds=600,limit_RSS_bytes=3*1024**3,new_fits=0,new_inference=0,native_writes=0,HTTP=0),environment=dict(python=platform.python_version(),numpy=np.__version__,pandas=pd.__version__,pyarrow=pa.__version__))
    with args.output.open('xb')as handle:handle.write(enc(out))
    signal.alarm(0);print(json.dumps(dict(state=out['state'],sha256=sha(args.output.read_bytes()),bytes=args.output.stat().st_size,checked=out['checked_scope'],resources=out['resources'])))

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=pathlib.Path,default=pathlib.Path(__file__).resolve().parents[1]);p.add_argument('--result',type=pathlib.Path,required=True);p.add_argument('--protocol',type=pathlib.Path,required=True);p.add_argument('--b-cache',type=pathlib.Path,required=True);p.add_argument('--old-b-cache',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path,required=True);p.add_argument('--expected-code-sha256',required=True);args=p.parse_args();require(not args.output.exists(),'Immutable receipt already exists')
    try:run(args)
    except BaseException as exc:
        signal.alarm(0);failure=dict(id='A-TIMING-CONFIRM-B-COMPLETION-INDEPENDENT-v1',state='FAILED_NO_AUTOMATIC_RETRY',phase=PHASE,error_type=type(exc).__name__,error_sha256=sha(str(exc).encode()),code_sha256=sha(pathlib.Path(__file__).read_bytes()),UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),CPU_seconds=resource.getrusage(resource.RUSAGE_SELF).ru_utime+resource.getrusage(resource.RUSAGE_SELF).ru_stime,RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,new_fits=0,new_inference=0,native_writes=0);receipt=args.output.with_name('B_INDEPENDENT_FAILURE_'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json');receipt.write_bytes(enc(failure));print(json.dumps(failure));raise
if __name__=='__main__':main()
