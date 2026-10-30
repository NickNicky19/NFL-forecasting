"""Independent streamed O/U side, count-event, score and paper-record QA."""
from pathlib import Path
from collections import Counter, defaultdict
from decimal import Decimal, localcontext
import argparse, datetime, gzip, hashlib, io, json, math, os, random, resource, signal, sys, time, zipfile

VERSION='opportunity-four-ou-independent-qa-v1-20261030'
FOCUS=['pass_att','rush_att','rec']
IDENTITY=['season','week','game_id','player_id','target','book_id','source_collection_naive','line','source_row_number']
BOOK_STATES=('WIN','LOSS','PUSH','VOID','PENDING','UNRESOLVED','ABSTAIN')
STAT_STATES=('CORRECT','INCORRECT','PUSH_STATISTIC','ABSTAIN','UNRESOLVED')
CAPS={'CPU_seconds':50,'wall_seconds':75,'RSS_bytes':768*1024**2,'attempts':1,'metadata_bytes':80*1024,'models':0,'fits':0,'HTTP':0,'CAS':0}
TOL=Decimal('0.000000000002')


def sha(body):return hashlib.sha256(body).hexdigest()
def enc(x):return (json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def dec(x):
    if x is None or isinstance(x,bool):return None
    try:r=Decimal(str(x))
    except Exception:return None
    return r if r.is_finite() else None
def prob(x):
    p=dec(x);return p if p is not None and 0<=p<=1 else None
def key(r):return tuple(str(r[k]) for k in IDENTITY)
def auth(r):
    p=Path(r['path']);assert p.resolve()==p and not p.is_symlink();b=p.read_bytes();assert len(b)==r['bytes'] and sha(b)==r['sha256'];return b
def neglog(p):
    if p==0:return {'state':'POSITIVE_INFINITY','value':None}
    with localcontext() as context:context.prec=40;return {'state':'FINITE','value':float(-p.ln())}


class Aggregate:
    def __init__(self):
        self.n=0;self.valid=0;self.status=Counter();self.sides=Counter();self.outcomes=Counter();self.book=Counter();self.side_status={s:Counter() for s in ['over','under']};self.side_book={s:Counter() for s in ['over','under']};self.games=set();self.weeks=set()
        self.point_n=0;self.a=Decimal(0);self.sq=Decimal(0);self.bias=Decimal(0);self.strict=0;self.inclusive=0;self.close=0;self.bn=0;self.bs=Decimal(0);self.fn=0;self.fs=Decimal(0);self.ln=0;self.ls=0.;self.inf=0;self.fln=0;self.fls=0.;self.finf=0
    def add(self,r):
        self.n+=1;self.status[r['direction_result']]+=1;side=r['selected_side'] or 'abstain';self.sides[side]+=1;self.outcomes[r['outcome_state']]+=1;self.book[r['book_settlement_status']]+=1
        if side in self.side_status:self.side_status[side][r['direction_result']]+=1;self.side_book[side][r['book_settlement_status']]+=1
        if r['actual_direction'] is None:return
        self.valid+=1;self.games.add(r['game_id']);self.weeks.add(r['week'])
        if r['point_absolute_error'] is not None:
            self.point_n+=1;self.a+=dec(r['point_absolute_error']);self.sq+=dec(r['point_squared_error']);self.bias+=dec(r['point_signed_error']);self.strict+=r['strict_error_lt1'] is True;self.inclusive+=r['inclusive_error_le1'] is True;self.close+=r['close_and_correct'] is True
        if r['Brier'] is not None:self.bn+=1;self.bs+=dec(r['Brier'])
        if r['full_statistic_Brier'] is not None:self.fn+=1;self.fs+=dec(r['full_statistic_Brier'])
        if r['log_loss']['state']!='UNAVAILABLE':
            self.ln+=1;self.inf+=r['log_loss']['state']=='POSITIVE_INFINITY'
            if r['log_loss']['state']=='FINITE':self.ls+=r['log_loss']['value']
        if 'full_statistic_log_loss' in r:
            self.fln+=1;self.finf+=r['full_statistic_log_loss']['state']=='POSITIVE_INFINITY'
            if r['full_statistic_log_loss']['state']=='FINITE':self.fls+=r['full_statistic_log_loss']['value']
    def summary(self):
        n=self.status['CORRECT']+self.status['INCORRECT'];s=self.point_n
        return {'offered_decisions':self.n,'supported_statistic_rows':self.valid,'counts':dict(self.status),'selected_sides':dict(self.sides),'correct_over_decisive_selected':self.status['CORRECT']/n if n else None,'decisive_selected_denominator':n,'selection_coverage':(self.n-self.sides['abstain'])/self.n if self.n else None,'outcome_states':dict(self.outcomes),'point_MAE':float(self.a/s) if s else None,'point_rows':s,'Brier_decisive':float(self.bs/self.bn) if self.bn else None,'Brier_rows':self.bn,'full_statistic_Brier':float(self.fs/self.fn) if self.fn else None,'full_statistic_Brier_rows':self.fn,'log_loss_decisive':{'state':'POSITIVE_INFINITY' if self.inf else 'FINITE' if self.ln else 'UNAVAILABLE','value':None if self.inf or not self.ln else self.ls/self.ln,'denominator':self.ln,'impossible_events':self.inf},'full_statistic_log_loss':{'state':'POSITIVE_INFINITY' if self.finf else 'FINITE' if self.fln else 'UNAVAILABLE','value':None if self.finf or not self.fln else self.fls/self.fln,'denominator':self.fln,'impossible_events':self.finf},'games':len(self.games),'weeks':len(self.weeks),'point_MSE':float(self.sq/s) if s else None,'point_bias':float(self.bias/s) if s else None,'strict_error_lt1':self.strict/s if s else None,'inclusive_error_le1':self.inclusive/s if s else None,'close_and_correct_strict_rate':self.close/s if s else None,'by_selected_side':{side:{'selected':self.sides[side],'correct':self.side_status[side]['CORRECT'],'incorrect':self.side_status[side]['INCORRECT'],'statistic_push':self.side_status[side]['PUSH_STATISTIC'],'unresolved':self.side_status[side]['UNRESOLVED'],'decisive':self.side_status[side]['CORRECT']+self.side_status[side]['INCORRECT'],'book_settlement_counts':{name:self.side_book[side][name] for name in BOOK_STATES}} for side in ['over','under']},'statistical_status_counts':{name:self.status[name] for name in STAT_STATES},'book_settlement_counts':{name:self.book[name] for name in BOOK_STATES}}


def main():
    p=argparse.ArgumentParser()
    for n in ['plan','sha256','go']:p.add_argument('--'+n,required=True)
    a=p.parse_args();b=Path(a.plan).read_bytes();assert sha(b)==a.sha256;plan=json.loads(b)
    assert plan['version']==VERSION and plan['state']=='ROOT_REVIEWED_AND_SEALED' and plan['execution_authorized'] is True and plan['resources']==CAPS
    assert json.loads(Path(a.go).read_bytes())=={'state':'GO','root':'/root','scope':VERSION,'plan_sha256':a.sha256,'source_review':'PASS'}
    assert sha(Path(__file__).read_bytes())==plan['worker_sha256'] and sys.flags.dont_write_bytecode
    out=Path(plan['native_root']);assert not out.exists();out.mkdir();cpu,wall=time.process_time(),time.monotonic();resource.setrlimit(resource.RLIMIT_CPU,(50,51))
    class Stop(BaseException):pass
    def stop(*unused):raise Stop('finite streamed independent OU QA exhausted')
    signal.signal(signal.SIGALRM,stop);signal.signal(signal.SIGXCPU,stop);signal.setitimer(signal.ITIMER_REAL,70);blocked=[]
    def deny(event,args):
        if event.startswith(('socket.','pickle.')) or event in ['subprocess.Popen','os.system','os.fork','os.posix_spawn'] or (event=='import' and args[0].split('.')[0] in ['joblib','sklearn']):blocked.append(event);raise Stop('offline model-free child-free QA')
    sys.addaudithook(deny)
    def usage():return {'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-wall,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,'models':0,'fits':0,'new_forecasts':0,'HTTP':0,'CAS':0,'blocked_calls':blocked}
    def note(name,value):
        body=enc(value);assert sum(x.stat().st_size for x in out.parent.rglob('*') if x.is_file())+len(body)<=CAPS['metadata_bytes'];assert sum(x.stat().st_size for x in Path(plan['role_root']).rglob('*') if x.is_file())+len(body)<=256*1024
        with (out/name).open('xb') as f:f.write(body);f.flush();os.fsync(f.fileno())
    note('CONSUMED.json',{'state':'ONE_INDEPENDENT_STREAMED_QA_ATTEMPT_CONSUMED','at_UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'plan_sha256':a.sha256,'resources':CAPS})
    try:
        for name in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[name]='1'
        inputs={k:auth(r) for k,r in plan['inputs'].items()}
        def raw_member(capsule,name,ref):
            with zipfile.ZipFile(io.BytesIO(capsule)) as z:assert z.namelist().count(name)==1;body=z.read(name)
            assert {'bytes':len(body),'sha256':sha(body)}==ref;return body
        def stream(capsule,name,ref):
            # Authenticate compressed member, then parse one JSON record at a time.
            body=raw_member(capsule,name,ref)
            with gzip.GzipFile(fileobj=io.BytesIO(body),mode='rb') as f:
                for line in f:yield json.loads(line)
        reported=json.loads(raw_member(inputs['grade'],'PUBLIC_SUMMARY.json',plan['members']['summary']))
        freeze_hash={};freeze_columns=None;frozen_paper={};method_counts=Counter();pool_counts=Counter();pool_ids=defaultdict(set)
        for r in stream(inputs['freeze'],'decisions.jsonl.gz',plan['members']['decisions']):
            assert r['target'] in FOCUS and r['season'] in [2024,2026] and (r['season']!=2026 or 1<=r['week']<=5)
            assert r['opportunity_id']==sha(enc(key(r)))
            if freeze_columns is None:freeze_columns=list(r)
            assert set(r)==set(freeze_columns)
            token=(r['opportunity_id'],r['procedure']);assert token not in freeze_hash;freeze_hash[token]=sha(enc(r));method_counts[r['procedure']]+=1
            for pool in r['pools']:pool_counts[pool]+=1;pool_ids[pool].add(r['opportunity_id'])
            line,point=dec(r['line']),dec(r.get('point'));assert line is not None
            proc=r['procedure'];expected=None
            if proc.startswith('P1_'):expected=None if point is None or point==line else 'over' if point>line else 'under'
            elif proc.startswith('ALWAYS_'):expected=proc.split('_')[1].lower()
            elif proc.startswith('P2_CONDITIONAL_') or proc=='P50_DECISIVE_CONTROL':
                q=prob(r['conditional_p_over']);expected=None if q is None or q==Decimal('.5') else 'over' if q>Decimal('.5') else 'under'
            elif proc=='P2_F_FULL':
                ps=[prob(r['p_'+s]) for s in ['over','under','push']]
                if all(v is not None for v in ps) and abs(sum(ps)-1)<=TOL:
                    expected=None if ps[0]==ps[1] else 'over' if ps[0]>ps[1] else 'under'
                    if ps[0]+ps[1]:assert dec(r['conditional_p_over'])==ps[0]/(ps[0]+ps[1])
                    else:assert r['conditional_p_over'] is None
                else:assert r['conditional_p_over'] is None
            else:raise AssertionError('unregistered decision procedure')
            assert r['selected_side']==expected and r['book_settlement']=='UNRESOLVED_UNQUALIFIED'
        for r in stream(inputs['freeze'],'original_paper_selections.jsonl.gz',plan['members']['paper_frozen']):
            token=key(r)+(r['policy'],);assert token not in frozen_paper;frozen_paper[token]=r
        checked=0
        def compare(x,y):
            nonlocal checked
            if isinstance(x,dict):
                assert isinstance(y,dict) and set(x)==set(y)
                for k in x:compare(x[k],y[k])
            elif isinstance(x,list):
                assert len(x)==len(y)
                for first,second in zip(x,y):compare(first,second)
            elif isinstance(x,(float,int)) and not isinstance(x,bool):assert isinstance(y,(float,int)) and math.isclose(x,y,rel_tol=1e-12,abs_tol=1e-12);checked+=1
            else:assert x==y;checked+=1
        groups=defaultdict(Aggregate);pairs=defaultdict(dict);seen=set();graded_n=0;full_rows=0;infinite_rows=0;source_states=Counter()
        for r in stream(inputs['grade'],'grade.jsonl.gz',plan['members']['graded']):
            token=(r['opportunity_id'],r['procedure']);assert token in freeze_hash and token not in seen;seen.add(token)
            assert sha(enc({k:r[k] for k in freeze_columns}))==freeze_hash[token];graded_n+=1
            actual,line=dec(r['actual']),dec(r['line']);event=None;state=r['outcome_state'];side=r['selected_side'];source_states[state]+=1
            if state=='supported_played':
                assert actual is not None and actual>=0 and actual==actual.to_integral_value();event='over' if actual>line else 'under' if actual<line else 'push'
            direction='UNRESOLVED' if event is None else 'ABSTAIN' if side is None else 'PUSH_STATISTIC' if event=='push' else 'CORRECT' if side==event else 'INCORRECT'
            assert r['actual_direction']==event and r['direction_result']==direction
            assert r['book_settlement_status']==('ABSTAIN' if side is None else 'PENDING' if state in ['pending','PENDING'] else 'UNRESOLVED')
            point=dec(r['point']);ae=sq=bias=None;strict=inclusive=close=None
            if event is not None and point is not None:
                bias=point-actual;ae=abs(bias);sq=bias*bias;strict=ae<1;inclusive=ae<=1;close=strict and direction=='CORRECT'
            for name,value in [('point_absolute_error',ae),('point_squared_error',sq),('point_signed_error',bias)]:assert dec(r[name])==value
            assert r['strict_error_lt1']==strict and r['inclusive_error_le1']==inclusive and r['close_and_correct']==close
            q=prob(r['conditional_p_over']);brier=None;log={'state':'UNAVAILABLE','value':None}
            if event is not None and event!='push' and q is not None:
                y=Decimal(int(event=='over'));brier=(q-y)**2;log=neglog(q if y else 1-q)
            assert dec(r['Brier'])==brier;compare(log,r['log_loss']);infinite_rows+=log['state']=='POSITIVE_INFINITY'
            ps=[prob(r['p_'+s]) for s in ['over','under','push']];full=None
            if event is not None and all(v is not None for v in ps) and abs(sum(ps)-1)<=TOL:
                full=sum((v-int(event==s))**2 for v,s in zip(ps,['over','under','push']));compare(neglog(ps[['over','under','push'].index(event)]),r['full_statistic_log_loss']);full_rows+=1
            else:assert 'full_statistic_log_loss' not in r
            assert dec(r['full_statistic_Brier'])==full
            for pool in r['pools']:
                base=(r['season'],r['target'],pool,r['procedure']);groups[base+('SEASON',)].add(r);groups[base+(str(r['week']),)].add(r)
                if pool!='FULL_CANONICAL':pairs[base][r['opportunity_id']]={k:r[k] for k in ['line','actual','outcome_state','direction_result','Brier','game_id','week']}
        assert len(seen)==len(freeze_hash)==graded_n
        expected_keys={}
        for k,g in groups.items():
            year,target,pool,proc,period=k
            if period!='SEASON':continue
            if pool.startswith('P1') and not(proc.startswith('P1_') or proc.startswith('ALWAYS_')):continue
            if pool.startswith('P2') and not(proc.startswith('P2_') or proc.startswith('ALWAYS_') or proc.startswith('P50_')):continue
            expected_keys[k]=g.summary()
        assert len(reported['summaries'])==len(expected_keys)
        for row in reported['summaries']:
            k=tuple(row[n] for n in ['season','target','pool','procedure','period']);expected=expected_keys.pop(k);compare(expected,{n:row[n] for n in expected})
        assert not expected_keys
        weekly_expected=set()
        for year,target,pool,proc,period in groups:
            if period=='SEASON' or pool=='FULL_CANONICAL':continue
            if pool.startswith('P1') and not(proc.startswith('P1_') or proc.startswith('ALWAYS_')):continue
            if pool.startswith('P2') and not(proc.startswith('P2_') or proc.startswith('ALWAYS_') or proc.startswith('P50_')):continue
            weekly_expected.add((year,target,'P1' if pool.startswith('P1') else 'P2',proc,int(period)))
        weekly_reported=[tuple(row[:5]) for row in reported['weekly']['rows']]
        assert len(weekly_reported)==len(set(weekly_reported)) and set(weekly_reported)==weekly_expected
        for row in reported['weekly']['rows']:
            year,target,pool,proc,week=row[:5];g=groups[(year,target,'P1_COMMON_ORIGINAL_OFFER_RULE' if pool=='P1' else 'P2_COMMON_ORIGINAL_OFFER_RULE',proc,str(week))];s=g.summary()
            compare([year,target,pool,proc,week,s['offered_decisions'],*[s['statistical_status_counts'][x] for x in STAT_STATES],s['point_MAE'],s['Brier_decisive'],s['Brier_rows'],s['games']],row)
        def contrast(left,right,loss,cluster):
            values=defaultdict(lambda:[0.,0]);nrows=0;total=0.
            for oid in sorted(set(left)&set(right)):
                x,y=left[oid],right[oid];assert (x['line'],x['actual'],x['outcome_state'])==(y['line'],y['actual'],y['outcome_state'])
                if loss=='direction':
                    if x['direction_result'] not in ['CORRECT','INCORRECT'] or y['direction_result'] not in ['CORRECT','INCORRECT']:continue
                    delta=int(x['direction_result']=='INCORRECT')-int(y['direction_result']=='INCORRECT')
                else:
                    if x['Brier'] is None or y['Brier'] is None:continue
                    delta=float(dec(x['Brier'])-dec(y['Brier']))
                v=values[str(x[cluster])];v[0]+=delta;v[1]+=1;nrows+=1;total+=delta
            ci=None
            if len(values)>=8:
                rng=random.Random(1703);items=list(values.values());samples=[]
                for _ in range(500):
                    draws=rng.choices(items,k=len(items));samples.append(sum(x[0] for x in draws)/sum(x[1] for x in draws))
                samples.sort()
                def quantile(q):
                    i=(len(samples)-1)*q;lo=math.floor(i);hi=math.ceil(i);return samples[lo]+(samples[hi]-samples[lo])*(i-lo)
                ci=[quantile(.025),quantile(.975)]
            return {'loss':loss,'paired_rows':nrows,'clusters':len(values),'cluster':cluster,'candidate_minus_control':total/nrows if nrows else None,'nominal95_interval':ci,'replicates':500,'seed':1703,'state':'UNAVAILABLE_FEWER_THAN8CLUSTERS' if len(values)<8 else 'EXPOSED_DEVELOPMENT_PAIRED_CLUSTER_BOOTSTRAP'}
        contrast_expected=set()
        for year in [2024,2026]:
            for target in FOCUS:
                for pool,methods,control in [('P1_COMMON_ORIGINAL_OFFER_RULE',['P1_F','P1_FC','P1_M','P1_H','ALWAYS_OVER','ALWAYS_UNDER'],'P1_F'),('P2_COMMON_ORIGINAL_OFFER_RULE',['P2_F_FULL','P2_CONDITIONAL_F','P2_CONDITIONAL_FC','P2_CONDITIONAL_FS','P2_CONDITIONAL_M','P2_CONDITIONAL_H','P50_DECISIVE_CONTROL'],'P2_CONDITIONAL_F')]:
                    for method in methods:
                        prefix=(year,target,pool)
                        if pairs.get(prefix+(method,)) and pairs.get(prefix+(control,)):contrast_expected.add(prefix+(method,control))
        contrast_reported=[tuple(row[k] for k in ['season','target','pool','candidate','control']) for row in reported['paired_contrasts']]
        assert len(contrast_reported)==len(set(contrast_reported)) and set(contrast_reported)==contrast_expected
        for row in reported['paired_contrasts']:
            prefix=(row['season'],row['target'],row['pool']);loss='direction' if row['pool'].startswith('P1') else 'Brier'
            for name,cluster in [('game','game_id'),('week','week')]:compare(contrast(pairs[prefix+(row['candidate'],)],pairs[prefix+(row['control'],)],loss,cluster),row[name])
        # Verify preserved original paper entries against authenticated original
        # frozen Parquet, without loading nonfocus labels or selecting new offers.
        import pyarrow as pa,pyarrow.parquet as pq
        pa.set_cpu_count(1);pa.set_io_thread_count(1)
        old_matched=raw_member(inputs['original_grade'],'MATCHED_SCORES.parquet',plan['members']['original_matched'])
        source_rows=pq.read_table(pa.BufferReader(old_matched),columns=['season','target','primary_role','outcome_state'],filters=[('target','in',FOCUS),('season','in',[2024,2026])],use_threads=False).to_pylist()
        compare({'matched_offer_rows':len(source_rows),'primary_role_rows':sum(r['primary_role'] is True for r in source_rows),'pool_opportunities':{k:len(v) for k,v in pool_ids.items()},'outcome_states':dict(Counter(r['outcome_state'] for r in source_rows))},reported['source_coverage'])
        del old_matched,source_rows
        offer_features=raw_member(inputs['original_forecasts'],'EVALUATION_FORECASTS.parquet',plan['members']['original_forecast_values'])
        feature_columns=['season','target','book_id','M_probability','M_point','independent_probability_books','independent_point_books']
        restored_offers=pq.read_table(pa.BufferReader(offer_features),columns=feature_columns,filters=[('target','in',FOCUS),('season','in',[2024,2026])],use_threads=False).to_pylist()
        independent_market_feature_rows=0
        for r in restored_offers:
            offering=str(int(r['book_id']))
            for value,field in [(r['M_probability'],'independent_probability_books'),(r['M_point'],'independent_point_books')]:
                if dec(value) is not None:
                    books=str(r[field]).split(',');assert books!=[''] and offering not in books
                    independent_market_feature_rows+=1
        del restored_offers,offer_features
        with zipfile.ZipFile(io.BytesIO(inputs['original_forecasts'])) as z:
            old=raw_member(inputs['original_forecasts'],'PAPER_LISTS_FROZEN.parquet',plan['members']['original_paper'])
            cols=IDENTITY+['policy','side','decimal_odds','conditional_probability','conditional_EV','score','settlement_contract']
            original=pq.read_table(pa.BufferReader(old),columns=cols,filters=[('target','in',FOCUS),('season','in',[2024,2026])],use_threads=False).to_pylist()
        assert len(original)==len(frozen_paper)
        def normalized(r):
            return {k:(None if isinstance(v,float) and not math.isfinite(v) else v.isoformat() if isinstance(v,(datetime.datetime,datetime.date)) else v) for k,v in r.items()}
        for row in original:
            row=normalized(row);assert frozen_paper[key(row)+(row['policy'],)]==row
        paper_groups=defaultdict(list);paper_seen=set()
        for r in stream(inputs['grade'],'original_paper_grade.jsonl.gz',plan['members']['paper_graded']):
            token=key(r)+(r['policy'],);assert token in frozen_paper and token not in paper_seen;paper_seen.add(token);prior=frozen_paper[token];assert all(r[k]==v for k,v in prior.items())
            side,odds=r['side'],dec(r['decimal_odds']);value=None;settlement='UNQUALIFIED_SETTLEMENT_CONTRACT'
            if r['settlement_contract']=='EXPLORATORY_ASSUMED_REFUND_PUSH_VOID_ACTUAL_BOOK_UNQUALIFIED':
                if side not in ['over','under'] or odds is None or odds<=1:settlement='MISSING_OR_INVALID_SIDE_PRICE'
                elif r['outcome_state']=='known_DNP_void':value=Decimal(0);settlement='assumed_DNP_void_refund'
                elif r['outcome_state']!='supported_played':settlement='unknown_ungraded'
                else:
                    actual,line=dec(r['actual']),dec(r['line']);assert actual is not None and actual>=0 and actual==actual.to_integral_value();event='over' if actual>line else 'under' if actual<line else 'push'
                    if event=='push':value=Decimal(0);settlement='assumed_push_refund'
                    elif event==side:value=odds-1;settlement='assumed_win'
                    else:value=Decimal(-1);settlement='assumed_loss'
            assert r['settlement']==settlement and r['authenticated_book_settlement'] is False
            assert (value is None and r['net_units'] is None) or (value is not None and dec(r['net_units']) is not None and abs(value-dec(r['net_units']))<=TOL)
            assert dec(r['return_recomputed_from_original_decimal_representation'])==value
            paper_groups[(r['season'],r['target'],r['policy'])].append(r)
        assert len(paper_seen)==len(frozen_paper)
        paper_reported=[(r['season'],r['target'],r['policy']) for r in reported['original_paper_exploratory']]
        assert len(paper_reported)==len(set(paper_reported)) and set(paper_reported)==set(paper_groups)
        for r in reported['original_paper_exploratory']:
            rows=paper_groups[(r['season'],r['target'],r['policy'])];counts=Counter(x['settlement'] for x in rows);known=[x for x in rows if x['net_units'] is not None];net=sum(dec(x['net_units']) for x in known) if known else None;n=counts['assumed_win']+counts['assumed_loss']
            expected={'season':r['season'],'target':r['target'],'policy':r['policy'],'selected':len(rows),'states':dict(counts),'original_sides_preserved':True,'assumed_net_units_known_only':float(net) if net is not None else None,'known_settled_stakes_including_push_void':len(known),'ROI_known_settled':float(net/len(known)) if known else None,'hit_rate_wins_over_decisive':counts['assumed_win']/n if n else None,'actual_book_settlement':'UNQUALIFIED','new_selection':False};compare(expected,r)
        assert reported['activity']['new_deterministic_side_decisions']==graded_n and reported['activity']['new_fits']==reported['activity']['new_models']==reported['activity']['new_statistic_forecasts']==reported['activity']['new_pregame_capture']==0
        u=usage();assert u['CPU_seconds']<49 and u['wall_seconds']<74 and u['RSS_bytes']<=CAPS['RSS_bytes'] and not blocked
        note('RESULT.json',{'state':'PASS_INDEPENDENT_STREAMED_OU_SCORE_AND_PAPER_QA','at_UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'inputs_sha256':{k:r['sha256'] for k,r in plan['inputs'].items()},'frozen_graded_decisions':graded_n,'method_counts':dict(method_counts),'pool_record_views':dict(pool_counts),'original_paper_rows_preserved':len(paper_seen),'proper_full_statistic_rows':full_rows,'decisive_impossible_event_rows_retained':infinite_rows,'offering_book_exclusion_feature_rows_checked':independent_market_feature_rows,'aggregate_fields_compared':checked,'usage':usage(),'limitations':['Independent saved-vector scoring QA;0newforecasts/fits/models.','Same-host readback, not off-host restoration.','2024/2026W1-5timing-unverified exploratory source; oldfootballcontrol not currentwebsitechampion.','Booksettlement remains unqualified; originalpaper returns only assumption-based, no newEV selections or profitability claim.','Restored market feature book lists checked; earlier training exclusion relies on pinned original code, not an independent refit.','All-quote secondary remains deferred; noWeek8protectedoutcomes accessed.']})
    except BaseException as e:
        note('FAILED.json',{'state':'INDEPENDENT_OU_QA_FAILED_RETAINED','at_UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'type':type(e).__name__,'error':str(e),'usage':usage(),'automatic_retry':False});raise
    finally:signal.setitimer(signal.ITIMER_REAL,0)


if __name__=='__main__':main()
