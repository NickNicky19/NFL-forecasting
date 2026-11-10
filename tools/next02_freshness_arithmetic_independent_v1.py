"""Independent arithmetic over original offers/labels and retained timing laws.

No scorer/summary function, model, fit, inference or writer is called. The
already reviewed native reader only restores exact bytes. All four aliases
are checked; strong-control and resampling calculations retain their separate
reviews. Source/quote vintage is not authenticated by this calculation.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import datetime
from decimal import Decimal, localcontext
import gzip
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import resource
import signal
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True
ARMS = ['F0_ORIGINAL_BASE', 'F1_ORIGINAL_PROFILE', 'F2_48H_BASE', 'F3_48H_PROFILE']
PRODUCTS = ['MEAN_P1', 'MEDIAN_P1', 'EXACT_LINE_P2']
KEY = ['season', 'week', 'game_id', 'player_id']
SOURCE_PINS = {
    'A_offers': 'f224f17930e8da7ed5683808de3339d9656cc4b71edb0deefcfb9c48dfd82ffb',
    'A_labels': '61da98ad90542b07c6c6664b674086ba4f9474e597325aba62dec44bb2fa72f5',
    'W8_sources': '6290b6a501ac5adf33ce693c2c4dc92d5f371ffdc3e6c6ba1da83ca6d1b623c5',
    'W8_graded': 'be9c13b0f42f5e164b29d00cce69fbe1c30acce703d1b33a8103a057888ac2c1',
    'W8_overlay': '2f8df2a10dcbba9074a04e9d2477fb76490311e2fedcbf70fa54c17dfec1f5fa',
    'W8_feature_identity': '5450041c91f3c5dce3a4078c81b861f388e4682dd5cc57d3f1e6b250338f5b0e'}

def enc(x): return (json.dumps(x, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode()
def sha(b): return hashlib.sha256(b).hexdigest()
def check(ok, why):
    if not ok: raise ValueError(why)
def finite(x): return type(x) in [int, float] and math.isfinite(x)
def identity(r): return int(r['season']), int(r['week']), str(r['game_id']), str(r['player_id'])
def close(a, b, tol=1e-9):
    return a is None and b is None or a is not None and b is not None and abs(float(a)-float(b)) <= tol*max(1., abs(float(a)), abs(float(b)))
def norm(x):
    x = str(x) if x is not None else ''
    return x[:-2] if x.endswith('.0') else x
def team(x): return {'LA':'LAR', 'WSH':'WAS', 'OAK':'LV', 'SD':'LAC', 'STL':'LAR'}.get(x, x)
def side(point, line):
    if not finite(point): return None
    a, b = Decimal(str(point)), Decimal(str(line))
    return 'OVER' if a > b else 'UNDER' if a < b else 'ABSTAIN'
def outcome(selected, appearance, actual, line):
    if selected is None: return 'UNAVAILABLE_FORECAST'
    if selected == 'ABSTAIN': return 'ABSTAIN'
    if appearance != 'PLAYED': return appearance if appearance in ['DNP','PENDING'] else 'UNKNOWN_PARTICIPATION'
    if actual is None: return 'MISSING_ACTUAL'
    y, l = Decimal(str(actual)), Decimal(str(line))
    if y == l: return 'PUSH'
    return 'WIN' if (y > l) == (selected == 'OVER') else 'LOSS'

def events(law, line):
    """Separate upper-tail/atom calculation with Decimal geometric tails."""
    check(law['kind'] == 'leaf_cdf', 'unexpected law')
    ys, ws = law['support'], law['weights']
    check(ys == sorted(set(ys)) and len(ys) == len(ws) > 0, 'support shape')
    check(all(finite(y) and int(y) == y for y in ys) and all(finite(w) and w >= 0 for w in ws), 'invalid signed law')
    check(abs(math.fsum(ws)-1) < 1e-12, 'empirical mass')
    p = law['prior']; c = p['center']; check(type(c) is int and p['support']=='signed_integer', 'prior support')
    with localcontext() as ctx:
        ctx.prec = 50; d = Decimal; q = d(str(p['q'])); b = d(str(law['prior_weight']))
        check(0 < q < 1 and 0 <= b <= 1, 'prior parameters')
        def upper(n):
            empirical = sum(d(str(w)) for y,w in zip(ys,ws) if y > n)
            tail = q**(n-c+1)/(1+q) if n >= c else 1-q**(c-n)/(1+q)
            return (1-b)*empirical+b*tail
        lower_cut, upper_cut = math.ceil(line)-1, math.floor(line)
        u = 1-upper(lower_cut); o = upper(upper_cut)
        z = d(0)
        if line == int(line):
            z = (1-b)*sum(d(str(w)) for y,w in zip(ys,ws) if y == line)+b*(1-q)/(1+q)*q**abs(int(line)-c)
        check(abs(u+z+o-1) < d('1e-12') and min(u,z,o) >= -d('1e-12'), 'event normalization')
        decimal_probs = tuple(float(v) for v in [u,z,o])
    # Numerical policy uses the registered binary64 CDF operations, including
    # a genuine floating equality. Compare Decimal probabilities separately;
    # do not retrospectively introduce an epsilon decision threshold.
    def prefix(n):
        e = math.fsum(w for y,w in zip(ys,ws) if y <= n)
        qf, bf = float(p['q']), float(law['prior_weight'])
        v = qf**(c-n)/(1+qf) if n < c else 1-qf**(n-c+1)/(1+qf)
        return (1-bf)*e+bf*v
    registered_probs = (prefix(lower_cut), prefix(int(line))-prefix(int(line)-1) if line==int(line) else 0., 1-prefix(upper_cut))
    check(all(close(a,b,1e-11) for a,b in zip(decimal_probs,registered_probs)), 'Decimal versus registered probability disagreement')
    return registered_probs, abs(decimal_probs[0]-decimal_probs[2]) <= 1e-13

def compatible(f, q, pd):
    if f is None: return 'MISSING_FROZEN_FORECAST'
    for x in ['team','opponent','position']:
        if str(f.get(x)) != str(q.get(x)): return 'EXACT_'+x.upper()+'_MISMATCH'
    for x in ['kickoff_utc','cutoff_utc']:
        a,b = pd.Timestamp(f.get(x)), pd.Timestamp(q.get(x))
        if a is pd.NaT or b is pd.NaT or a.tzinfo is None or b.tzinfo is None or a != b: return 'EXACT_'+x.upper()+'_MISMATCH_OR_UNKNOWN'
    return None
def fallback(f):
    if f is None: return 'UNAVAILABLE_FORECAST'
    if 'fallback' not in f: return 'UNRECORDED'
    v = f['fallback']
    return 'LEARNED_EXPLICIT_NO_FALLBACK' if v in [None,'',False,'none'] else 'FALLBACK:'+str(v)
def fallback_group(r):
    if r['reason'] is not None: return 'UNAVAILABLE'
    if r['fallback'] == 'LEARNED_EXPLICIT_NO_FALLBACK': return 'LEARNED'
    if r['fallback'].startswith('FALLBACK:'): return 'FALLBACK'
    return 'OTHER_EXPLICIT_STATE:'+r['fallback']

def synthetic():
    law = dict(kind='leaf_cdf',support=[-3,0,4],weights=[.2,.3,.5],prior_weight=.05,prior=dict(center=0,q=.5,support='signed_integer'))
    for line in [-3.,-.5,0.,.5,4.,4.5]:
        p,_ = events(law,line);check(close(sum(p),1), 'fictional event sum')
    check(side(0,.5)=='UNDER' and outcome('UNDER','PLAYED',0,.5)=='WIN', 'known zero')
    check(outcome('UNDER','PLAYED',None,.5)=='MISSING_ACTUAL', 'unknown not zero')
    check(outcome('OVER','UNKNOWN',0,.5)=='UNKNOWN_PARTICIPATION', 'unknown appearance')
    check(outcome('UNDER','PLAYED',0,0)=='PUSH' and side(0,0)=='ABSTAIN', 'push/abstain distinction')
    return dict(state='PASS_FICTIONAL_ARITHMETIC_ONLY',NFL_rows=0,native_reads=0,models=0,fits=0)

def run(args):
    check(args.root_notification=='ROOT_NOTIFIED_ALIGNED_TIMING_SCORE_COMPLETE', 'root must notify actual completed scoring')
    for n in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']: os.environ[n]='1'
    resource.setrlimit(resource.RLIMIT_CPU,(240,250));resource.setrlimit(resource.RLIMIT_AS,(3*1024**3,)*2);signal.alarm(600)
    def offline(event, _):
        if event in {'socket.connect','socket.connect_ex','socket.getaddrinfo'}: raise RuntimeError('offline independent calculation')
    sys.addaudithook(offline)
    import pandas as pd
    import pyarrow as pa
    pa.set_cpu_count(1);pa.set_io_thread_count(1)
    start, cpu = time.monotonic(),time.process_time()
    def document(path, expected):
        b=Path(path).read_bytes();check(sha(b)==expected,'document identity differs');return b,json.loads(gzip.decompress(b) if Path(path).suffix=='.gz' else b)
    score_bytes, result=document(args.score,args.score_sha256);protocol_bytes,plan=document(args.protocol,args.protocol_sha256)
    check(result['state']=='FROZEN_ALIGNED_TIMING_POINT_AND_LAW_SCORING_COMPLETE' and result['protocol_sha256']==args.protocol_sha256, 'completed score binding')
    # Reviewed read-only storage helper only; none of its model/math routines.
    hp=ROOT/'tools/next02_freshness_model_independent_v1.py'
    check(sha(hp.read_bytes())=='ea427efad29fdac723a99b98cc675f2ec522127ccfbc5dfab09bf8fa34acac05','read-only helper changed')
    spec=importlib.util.spec_from_file_location('next02_arithmetic_readonly_storage',hp);reader=importlib.util.module_from_spec(spec);sys.modules[spec.name]=reader;spec.loader.exec_module(reader)
    store=reader.readonly_store(plan)
    def native(ref):
        b=store.read(ref['id'],ref['sha256'],namespace=ref['namespace']);check(len(b)==ref['bytes'],'native size');return b
    def original(ref):
        b=Path(ref['path']).read_bytes();check(len(b)==ref['bytes'] and sha(b)==ref['sha256'],'original source hash');return b
    raw,execution=document(plan['execution_receipt']['path'],plan['execution_receipt']['sha256'])
    manifest=json.loads(gzip.decompress(native(execution['forecasts'])));forecasts={};law_checks=0
    for part in manifest['parts']:
        rr=json.loads(gzip.decompress(native(part['ref'])));arm=part['procedure_alias'];check(arm in ARMS and len(rr)==1364,'part identities')
        forecasts[arm]={identity(r):r for r in rr};check(len(forecasts[arm])==len(rr),'duplicate forecast identity')
        check(all(r['arm']==part['original_arm'] and r['target']=='rush_yd' and r['position']=='RB' for r in rr),'forecast contract')
    _,old_receipt=document(plan['old_execution_receipt']['path'],plan['old_execution_receipt']['sha256']);oldrefs={r['id']:r for r in old_receipt['artifacts']}
    oldroot=store.prior.forward_root/'research'/store.oldguard.OLD
    def old_native(ref):
        p=oldroot/ref['id'];store.prior.validate_reference(p,ref['sha256']);b=p.read_bytes();check(len(b)==ref['bytes'] and sha(b)==ref['sha256'],'old bytes');return b
    queries={identity(r):r for r in json.loads(gzip.decompress(old_native(oldrefs['QUERY_IDENTITIES_2026.json.gz'])))}
    from tools import abc_a_dynamic_carry_wave_v1 as original_sources
    _,_,grade,_=original_sources.sources();refs={n:dict(grade[k])for n,k in [('A_offers','offers'),('A_labels','qualified_labels')]}
    for name,ref in refs.items(): check(ref['sha256']==SOURCE_PINS[name] and result['source_sha256'][name]==ref['sha256'],'source identity')
    def member(ref):
        with zipfile.ZipFile(io.BytesIO(original(ref))) as z:return z.read(ref['member'])
    offers=pd.read_parquet(io.BytesIO(member(refs['A_offers'])));labels=pd.read_parquet(io.BytesIO(member(refs['A_labels'])))
    labels=labels.loc[labels.target.eq('rush_yd')&labels.season.eq(2026)&labels.week.between(1,7)];check(not labels.duplicated(KEY).any(),'label duplicates');labelmap={}
    for r in labels.to_dict('records'):
        appearance='PENDING'if r.get('outcome_state')=='pending'else'DNP'if str(r.get('participation_state')).lower()=='dnp'else'PLAYED'if str(r.get('participation_state')).lower()=='played'else'UNKNOWN'
        supported=appearance=='PLAYED'and finite(r.get('actual'))and r.get('label_reason')in['EXPLICIT_REPORTED_ZERO','EXPLICIT_REPORTED_VALUE']and bool(r.get('participation_evidence'))
        labelmap[identity(r)]=dict(actual=float(r['actual'])if supported else None,appearance=appearance)
    # W8 remains reference-only. Source qualification was independently checked
    # in the prior wave; only its original byte IO/qualification is reused here.
    source_helper='tools/player_context_completion_efficiency_score_v1.py'
    check(source_helper in plan['code_sha256'] and sha((ROOT/source_helper).read_bytes())==plan['code_sha256'][source_helper], 'original source qualification helper changed')
    from tools import player_context_completion_efficiency_score_v1 as original_w8_source
    w8queries,w8canonical,w8offers,_=original_w8_source.restore_w8(store,{},pd)
    for k,r in w8canonical.items():labelmap[k]=r['_label']
    for r in w8queries:
        if r['identity_reason']is not None:queries[identity(r)]=r
    aoffers=offers.loc[offers.target.eq('rush_yd')&offers.position.eq('RB')&offers.season.eq(2026)&offers.week.between(1,7)]
    check(not aoffers.duplicated('opportunity_key').any(),'offer duplicates')
    opportunities=[dict(q=r,key=str(r['opportunity_key']),line=float(r['line']),panel=str(r['source_stream']),label=labelmap.get(identity(r),dict(actual=None,appearance='UNKNOWN')))for r in aoffers.to_dict('records')]
    opportunities += [dict(q=r['query'],key=r['opportunity'],line=r['line'],panel=r['source'],label=r['label'])for r in w8offers]
    cohort_rows=json.loads(gzip.decompress(native(plan['cohort_reference'])));cohorts={identity(r):r for r in cohort_rows}
    qf=pd.read_parquet(io.BytesIO(native(plan['fixed_original_profile_reference'])),columns=KEY+['f_pce_own_supported']);support={identity(r):bool(r['f_pce_own_supported']>0)for r in qf.to_dict('records')}
    board={a+'::'+p:[]for a in ARMS for p in PRODUCTS};broad={k:[]for k in board};near_ties=0
    def components(arm,product,q,line):
        f=forecasts[arm].get(identity(q));reason=q.get('identity_reason')or compatible(f,q,pd);fb=fallback(f)
        if reason is not None:return None,None,None,reason,'UNAVAILABLE_FORECAST'
        point=f['mean']if product=='MEAN_P1'else f['median']if product=='MEDIAN_P1'else None
        probs=None;selected=None
        if line is not None:
            nonlocal law_checks,near_ties
            probs,near=events(f['law'],line);law_checks+=1;near_ties+=int(near)
            selected=('OVER'if probs[2]>probs[0]else'UNDER'if probs[0]>probs[2]else'ABSTAIN')if product=='EXACT_LINE_P2'else side(point,line)
        return point,probs,selected,None,fb
    def groups(k):
        return ['ALL_ELIGIBLE']+(['DETAILED_PRIORITY']if cohorts.get(k,{}).get('detailed_priority')else[])+(['WORKLOAD_TOP20']if cohorts.get(k,{}).get('top20_workload')else[])+(['PBP_OWN_SUPPORTED']if support.get(k)else[])
    for k,q in queries.items():
        lab=labelmap.get(k,q.get('_label',dict(actual=None,appearance='UNKNOWN')))
        for arm in ARMS:
            for product in PRODUCTS:
                point,prob,selected,reason,fb=components(arm,product,q,None)
                broad[arm+'::'+product].append(dict(key=sha(enc(list(k))),season=k[0],week=k[1],game=k[2],player=k[3],point=point,prob=None,side=None,reason=reason,fallback=fb,groups=groups(k),**lab))
    for o in opportunities:
        q=o['q'];k=identity(q)
        for arm in ARMS:
            for product in PRODUCTS:
                point,probs,selected,reason,fb=components(arm,product,q,o['line']);lab=o['label']
                board[arm+'::'+product].append(dict(key=o['key'],season=k[0],week=k[1],game=k[2],player=k[3],point=point,prob=probs,side=selected,reason=reason,fallback=fb,groups=groups(k),line=o['line'],panel=o['panel'],status=outcome(selected,lab['appearance'],lab['actual'],o['line']),**lab))
    core=set.intersection(*[{r['key']for r in rows if r['side']is not None}for rows in board.values()]);numeric_core=set.intersection(*[{r['key']for r in rows if finite(r['point'])}for c,rows in broad.items()if not c.endswith('P2')])
    check(sha(enc(sorted(core)))==result['common_new_core_mask_sha256'],'stable board mask')
    for collection,mask in [(board,core),(broad,numeric_core)]:
        for rows in collection.values():
            for r in rows:
                if r['key']in mask:r['groups'].append('STABLE_NEW_CORE')
    def numerical(rows):
        e=[r['point']-r['actual']for r in rows if finite(r['point'])and r['actual']is not None]
        return dict(scored=len(e),MAE=math.fsum(abs(v)for v in e)/len(e)if e else None,MSE=math.fsum(v*v for v in e)/len(e)if e else None,bias=math.fsum(e)/len(e)if e else None)
    def compare_fields(actual,expected,names):
        for name in names:check(close(actual[name],expected[name]),'metric disagreement '+name)
    summary_count=side_count=numeric_count=probability_count=0
    for s in result['summaries']:
        if s['candidate_id']not in board:continue
        weeks=range(1,8)if s['period']=='W1_W7'else[8]if s['period']=='W8_REFERENCE_ONLY'else range(1,9)
        broad_scope=s['population']=='BROAD_QUERIES';rs=[r for r in(broad if broad_scope else board)[s['candidate_id']]if r['week']in weeks and s['cohort']in r['groups']]
        if not broad_scope:rs=[r for r in rs if(s['source_panel']=='ALL'or r['panel']==s['source_panel'])and(s['week_view']=='ALL'or r['week']==s['week_view'])]
        n=numerical(rs);compare_fields(s['numerical'],n,['scored','MAE','MSE','bias']);numeric_count+=1
        if not broad_scope:
            check(s['eligible']==len(rs)and s['games']==len({r['game']for r in rs})and s['player_games']==len({(r['game'],r['player'])for r in rs}),'eligible/games')
            check(s['states']==dict(Counter(r['status']for r in rs)),'state partition')
            actual_weeks=sorted({r['week']for r in rs if r['status']in['WIN','LOSS','PUSH']and r['panel']in plan['actual_recorded_source_panels']})
            check(s['actual_recorded_line_scored_weeks']==actual_weeks and s['five_actual_week_duration_floor']==(len(actual_weeks)>=5),'actual-offer duration')
            check(s['diagnostic_scored_weeks']==sorted({r['week']for r in rs if r['status']in['WIN','LOSS','PUSH']}),'diagnostic weeks')
            check(s['unavailable']==sum(r['side']is None for r in rs)and s['abstentions']==sum(r['side']=='ABSTAIN'for r in rs),'unavailable/abstained')
            for side_name in ['OVER','UNDER','COMBINED']:
                group=[r for r in rs if r['side']in['OVER','UNDER']and(side_name=='COMBINED'or r['side']==side_name)];w=sum(r['status']=='WIN'for r in group);l=sum(r['status']=='LOSS'for r in group);n=w+l
                target=dict(selected=len(group),wins=w if n else None,losses=l if n else None,decided=n,rate=w/n if n else None);compare_fields(s[side_name],target,target);side_count+=1
            pr=[r for r in rs if r['prob']is not None and r['appearance']=='PLAYED'and r['actual']is not None];briers=[(r['prob'][2]-float(r['actual']>r['line']))**2 for r in pr]
            compare_fields(s['probability'],dict(qualified_law_outcomes=len(pr),decisive_law_outcomes=sum(r['actual']!=r['line']for r in pr),binary_Over_event_Brier=math.fsum(briers)/len(pr)if pr else None),['qualified_law_outcomes','decisive_law_outcomes','binary_Over_event_Brier']);probability_count+=1
        summary_count+=1
    primary=[(ARMS[1],ARMS[0]),(ARMS[2],ARMS[0]),(ARMS[3],ARMS[2]),(ARMS[3],ARMS[1])];pair_ids={(a+'::'+p,b+'::'+p)for a,b in primary for p in PRODUCTS};pair_count=0
    for s in result['paired']:
        if(s['left'],s['right'])not in pair_ids:continue
        weeks=range(1,8)if s['period']=='W1_W7'else[8]if s['period']=='W8_REFERENCE_ONLY'else range(1,9)
        aa=[r for r in board[s['left']]if r['week']in weeks and s['cohort']in r['groups']and(s['source_panel']=='ALL'or r['panel']==s['source_panel'])];bb={r['key']:r for r in board[s['right']]if r['week']in weeks and s['cohort']in r['groups']and(s['source_panel']=='ALL'or r['panel']==s['source_panel'])};pp=[(r,bb[r['key']])for r in aa if r['key']in bb]
        dd=[(a,b)for a,b in pp if a['status']in['WIN','LOSS']and b['status']in['WIN','LOSS']];nn=[(a,b)for a,b in pp if finite(a['point'])and finite(b['point'])and a['actual']is not None and b['actual']is not None]
        for mask_name,pairs in [('decided_mask_sha256',dd),('numerical_mask_sha256',nn)]:check(s[mask_name]==sha(enc(sorted(a['key']for a,b in pairs))),'paired mask')
        calc=dict(common_decided=len(dd),left_wins=sum(a['status']=='WIN'for a,b in dd),right_wins=sum(b['status']=='WIN'for a,b in dd),accuracy_change=math.fsum(int(a['status']=='WIN')-int(b['status']=='WIN')for a,b in dd)/len(dd)if dd else None,side_disagreements=sum(a['side']!=b['side']for a,b in dd),common_numerical=len(nn),MAE_change=math.fsum(abs(a['point']-a['actual'])-abs(b['point']-b['actual'])for a,b in nn)/len(nn)if nn else None);compare_fields(s,calc,calc)
        pr=[(a,b)for a,b in pp if a['prob']is not None and b['prob']is not None and a['appearance']=='PLAYED'and a['actual']is not None];pb=dict(common_probability_events=len(pr),binary_Over_event_Brier_change=math.fsum((a['prob'][2]-float(a['actual']>a['line']))**2-(b['prob'][2]-float(b['actual']>b['line']))**2 for a,b in pr)/len(pr)if pr else None);compare_fields(s['probability'],pb,pb);pair_count+=1
    attribution_count=0
    panels={'W1_W7_MIXED_THRESHOLDS':(False,lambda r:r['week']in range(1,8)),'ANNUAL_W1_W5':(False,lambda r:r['week']in range(1,6)and r['panel']=='ANNUAL_NAMED_NJ'),'W8_REFERENCE_ONLY':(False,lambda r:r['week']==8),'BROAD_NUMERICAL_W1_W7':(True,lambda r:r['week']in range(1,8)),'BROAD_NUMERICAL_W8':(True,lambda r:r['week']==8),'BROAD_NUMERICAL_W1_W8':(True,lambda r:r['week']in range(1,9))}
    for s in result['fallback_attribution']['records']:
        is_broad,predicate=panels[s['panel']];collection=broad if is_broad else board;aa=[r for r in collection[s['left']]if predicate(r)];bb={r['key']:r for r in collection[s['right']]if predicate(r)};pp=[(a,bb[a['key']])for a in aa if a['key']in bb]
        if s['group']!='FULL_SYSTEM':pp=[(a,b)for a,b in pp if fallback_group(b)+'_TO_'+fallback_group(a)==s['group']]
        check(s['cases']==len(pp)and s['unique_games']==len({a['game']for a,b in pp})and s['full_mask_sha256']==sha(enc(sorted(a['key']for a,b in pp))),'fallback group/mask')
        dd=[]if is_broad else[(a,b)for a,b in pp if a['status']in['WIN','LOSS']and b['status']in['WIN','LOSS']];nn=[(a,b)for a,b in pp if a['appearance']==b['appearance']=='PLAYED'and a['actual']is not None and b['actual']is not None and finite(a['point'])and finite(b['point'])];pr=[]if is_broad else[(a,b)for a,b in pp if a['appearance']==b['appearance']=='PLAYED'and a['actual']is not None and a['prob']is not None and b['prob']is not None]
        w=sum(a['status']=='WIN'for a,b in dd);v=sum(b['status']=='WIN'for a,b in dd);calc=dict(common_decided=len(dd),left_wins=w if dd else None,right_wins=v if dd else None,accuracy_change=(w-v)/len(dd)if dd else None,common_numerical=len(nn),MAE_change=math.fsum(abs(a['point']-a['actual'])-abs(b['point']-b['actual'])for a,b in nn)/len(nn)if nn else None,common_probability_events=len(pr),Brier_change=math.fsum((a['prob'][2]-float(a['actual']>a['line']))**2-(b['prob'][2]-float(b['actual']>b['line']))**2 for a,b in pr)/len(pr)if pr else None);compare_fields(s,calc,calc);attribution_count+=1
    receipt=dict(id='A-NEXT02-FRESHNESS-INDEPENDENT-ARITHMETIC-v1',UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),state='PASS_INDEPENDENT_DECIMAL_ORIGINAL_OFFER_LABEL_AND_PRIMARY_CONTRAST_ARITHMETIC',score_sha256=sha(score_bytes),protocol_sha256=sha(protocol_bytes),summary_cells=summary_count,side_partitions=side_count,numerical_cells=numeric_count,probability_cells=probability_count,primary_pair_cells=pair_count,fallback_attribution_cells=attribution_count,exact_line_law_calculations=law_checks,near_equal_law_probability_cases=near_ties,discrepancies=0,limits=['Within A independent calculation, not external B/C receipt','No model loading/inference or fresh fit','Original W8 source-presence qualification reused; reference-only not an authentic offer','Strong-control and bootstrap intervals are outside this new-arithmetic scope; preserved reviews remain separate','Current-vintage source and quote clocks remain unauthenticated'],activity=dict(CPU_seconds=time.process_time()-cpu,wall_seconds=time.monotonic()-start,RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,native_writes=0,external_HTTP=0,fits=0))
    with args.output.open('xb')as f:f.write(enc(receipt));f.flush();os.fsync(f.fileno())
    print(json.dumps(dict(state=receipt['state'],bytes=args.output.stat().st_size,sha256=sha(args.output.read_bytes()),summary_cells=summary_count,paired_cells=pair_count,attribution_cells=attribution_count,resources=receipt['activity'])))

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--synthetic',action='store_true')
    for name in ['protocol','score','output']:p.add_argument('--'+name,type=Path)
    for name in ['protocol-sha256','score-sha256','root-notification']:p.add_argument('--'+name)
    args=p.parse_args()
    if args.synthetic:print(json.dumps(synthetic()));return
    check(all(getattr(args,n)is not None for n in ['protocol','score','output','protocol_sha256','score_sha256','root_notification']),'all exact bindings required')
    check(not args.output.exists(),'immutable independent receipt exists')
    run(args)

if __name__=='__main__':main()
