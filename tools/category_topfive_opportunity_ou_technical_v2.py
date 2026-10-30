"""Bounded zero-refit four-category direction/probability/paper comparison.

Only an exact prepublished protocol, reviewed plan, closed predecessor writer,
authenticated retained capsules and approved private storage permit NFL decode.
"""
from pathlib import Path
import argparse, base64, csv, datetime, gzip, hashlib, html, importlib.metadata, importlib.util
import io, json, math, os, re, resource, signal, sys, time, zipfile

VERSION = 'opportunity-four-ou-zero-refit-technical-v2-20261030'
SCIENTIFIC_VERSION = 'opportunity-four-ou-zero-refit-v1-20261030'
FOCUS = ('pass_att', 'rush_att', 'rec')
UNIT = ['season', 'week', 'game_id', 'player_id', 'target']
IDENTITY = UNIT+['book_id', 'source_collection_naive', 'line', 'source_row_number']
PROJECTION = IDENTITY+['team','opponent','position','kickoff_utc','period','side','book_kind',
    'source_sha256','source_member','primary_role','F_point','FC_point','H_point','M_point',
    'F_probability','FC_probability','FS_probability','M_probability','H_probability',
    'F_over','F_under','F_push','F_fallback','F_model_year','F_control_age','evidence_lane',
    'd_over','d_under','american_odds','under_american_odds','price_qualified','probability_qualified',
    'quote_pair_status','under_source_row_number','independent_probability_books','independent_point_books']
CAPS = {'CPU_seconds':180,'wall_seconds':240,'RSS_bytes':768*1024**2,'fits':0,'model_loads':0,
    'HTTP':0,'automatic_retries':0,'managed_write_attempts':3,'retained_private_bytes':32*1024**2,
    'peak_private_bytes':64*1024**2,'maximum_member_bytes':32*1024**2,'maximum_source_rows':62576,
    'maximum_decision_rows':200000,'public_aggregate_bytes':512*1024,'native_metadata_bytes':65536,
    'bootstrap_replicates':500,'seed':1703}


def sha(body): return hashlib.sha256(body).hexdigest()
def encoded(value): return (json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def auth(ref):
    path=Path(ref['path']); assert path.resolve()==path and not any(p.is_symlink() for p in [path,*path.parents])
    body=path.read_bytes(); assert len(body)==ref['bytes'] and sha(body)==ref['sha256']
    if 'blob' in ref: assert path.samefile(ref['blob'])
    return body
def module(ref,name):
    auth(ref); spec=importlib.util.spec_from_file_location(name,ref['path']); result=importlib.util.module_from_spec(spec);sys.modules[name]=result;spec.loader.exec_module(result);return result
def clean(value):
    if isinstance(value,dict): return {str(k):clean(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)): return [clean(v) for v in value]
    if isinstance(value,float) and not math.isfinite(value): return None
    if isinstance(value,(datetime.datetime,datetime.date)): return value.isoformat()
    return value
def jsonl_gzip(rows):
    sink=io.BytesIO()
    with gzip.GzipFile(fileobj=sink,mode='wb',mtime=0) as stream:
        for row in rows:stream.write(encoded(row))
    return sink.getvalue()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--plan',required=True);parser.add_argument('--sha256',required=True);parser.add_argument('--go',required=True);args=parser.parse_args()
    body=Path(args.plan).read_bytes();assert sha(body)==args.sha256;plan=json.loads(body)
    assert plan['version']==VERSION and plan['state']=='ROOT_AND_REVIEWER_SEALED' and plan['resources']==CAPS and plan['scientific_version']==SCIENTIFIC_VERSION
    assert plan['execution_authorized'] is True and sys.flags.dont_write_bytecode
    assert json.loads(Path(args.go).read_bytes())=={'state':'GO','root':'/root','independent_review':'PASS','scope':VERSION,'plan_sha256':args.sha256,'previous_managed_writer_closed':True}
    assert plan['evaluation_seasons']==[2024,2026] and plan['excluded_quote_seasons']==[2025]
    for ref in plan['source_pins'].values(): auth(ref)
    proof=json.loads(auth(plan['public_protocol']))
    assert proof['state']=='PUBLICATION_COMPLETE' and proof['experiment_id']=='e:'+VERSION and proof['run_id']=='r:'+VERSION
    assert re.fullmatch('[0-9a-f]{40}',proof['commit']) and proof['readback_ref'].startswith('https://github.com/NickNicky19/NFL-forecasting/blob/'+proof['commit']+'/')
    fixture=json.loads(auth(plan['fixture_receipt']))
    assert fixture['state']=='PASS' and fixture['cases']>=14 and fixture['scorer_sha256']==plan['source_pins']['scorer']['sha256']
    smoke=json.loads(auth(plan['package_smoke_receipt']))
    assert smoke['state']=='PASS' and smoke['kind']=='AUTHENTICATED_PACKAGE_IMPORT_ONLY' and smoke['shared_legacy_OperationalStorage_class'] is True
    for name in ['owned_reference_batch','legacy_operational_storage','legacy_package_init']:
        assert smoke['source_pins'][name]=={k:plan['source_pins'][name][k] for k in ['bytes','sha256']}
    cpu=time.process_time();wall=time.monotonic();started=now();native=Path(plan['native_root']);assert not native.exists();native.mkdir(parents=True)
    resource.setrlimit(resource.RLIMIT_CPU,(180,181));resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3))
    class Stop(BaseException): pass
    def stop(*unused): raise Stop('Finite zero-refit O/U allocation consumed')
    signal.signal(signal.SIGALRM,stop);signal.signal(signal.SIGXCPU,stop);signal.setitimer(signal.ITIMER_REAL,236)
    for name in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']: os.environ[name]='1'
    writes=[];blocked=[];store=None;active={};grade_rows=[];paper_rows=[]
    def deny(event,unused):
        if event.startswith('socket.') or event in ('subprocess.Popen','os.system','os.fork','os.posix_spawn','pickle.find_class'):
            blocked.append(event);raise Stop('Offline model-free child-free evaluation required')
    sys.addaudithook(deny)
    def usage(): return {'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-wall,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,'CAS_attempts':len(writes),'fits':0,'model_loads':0,'HTTP':0,'blocked_calls':blocked}
    def note(name,value):
        data=encoded(value);assert sum(p.stat().st_size for p in native.iterdir())+len(data)<=CAPS['native_metadata_bytes']
        with (native/name).open('xb') as stream: stream.write(data);stream.flush();os.fsync(stream.fileno())
    def check(retain=False):
        u=usage();assert u['CPU_seconds']<(179 if retain else 160) and u['wall_seconds']<(239 if retain else 215) and u['RSS_bytes']<=CAPS['RSS_bytes'] and (retain or not blocked)
    note('CONSUMED.json',{'state':'ONE_ZERO_REFIT_OU_ATTEMPT_CONSUMED','started_at_UTC':started,'plan_sha256':args.sha256,'resources':CAPS,'original_studies_preserved':True})
    try:
        import pyarrow as pa,pyarrow.parquet as pq
        for name,version in plan['environment'].items(): assert importlib.metadata.version(name)==version
        pa.set_cpu_count(1);pa.set_io_thread_count(1)
        scorer=module(plan['source_pins']['scorer'],'opportunity_ou_scorer')
        assert scorer.VERSION==SCIENTIFIC_VERSION
        sp=plan['storage'];old=module(sp['original_helper'],'ou_market');wrap=module(sp['helper'],'ou_prior_meta')
        auth(sp['forward_implementation']);auth(plan['source_pins']['legacy_operational_storage']);auth(plan['source_pins']['legacy_package_init'])
        base=old.load_frozen(sp['forward_implementation']['path'],sp['legacy_library_root'])
        legacy=sys.modules['nfl_lab.operational_storage'];assert Path(legacy.__file__).resolve()==Path(plan['source_pins']['legacy_operational_storage']['path'])
        assert Path(sys.modules['nfl_lab'].__file__).resolve()==Path(plan['source_pins']['legacy_package_init']['path'])
        prior=wrap.build_storage_class(old.build_storage_class(base),json.loads(auth(sp['prior_metadata_descriptor'])))
        extension=module(sp['forward_metadata_helper'],'ou_new_meta');cls=extension.build_storage_class(prior,json.loads(auth(sp['metadata_descriptor'])))
        store=cls(sp['legacy_cache'],json.loads(auth(sp['market_policy'])),json.loads(auth(sp['legacy_policy'])),json.loads(auth(sp['prior_policy'])))
        output=Path(plan['output']);assert output==store.live_root/'research'/VERSION and not output.exists();store.register_root(output)
        with store.transaction(): store._refresh();store._require(CAPS['peak_private_bytes'])
        def save(name,members,retain=False):
            check(retain);assert len(writes)<3
            sink=io.BytesIO()
            with zipfile.ZipFile(sink,'w',compression=zipfile.ZIP_STORED) as archive:
                for key,value in sorted(members.items()): archive.writestr(key,value)
            data=sink.getvalue();retained=sum(r['bytes'] for r in writes)+65536
            assert len(data)<=16*1024**2 and retained+len(data)<=CAPS['retained_private_bytes'] and retained+2*len(data)<=CAPS['peak_private_bytes']
            ref={'path':str(output/name),'bytes':len(data),'sha256':sha(data)};writes.append(ref);store.write_bytes(output/name,data)
            validated=store.validate_reference(output/name);assert all(validated[k]==ref[k] for k in ref) and (output/name).read_bytes()==data
            with zipfile.ZipFile(output/name) as archive: assert set(archive.namelist())==set(members) and all(archive.read(k)==v for k,v in members.items())
            note(name.replace('.zip','_READBACK.json'),{'state':'PASS_CAPSULE_AND_INNER_BYTES','reference':ref,'members':{k:{'bytes':len(v),'sha256':sha(v)} for k,v in members.items()},'usage':usage()});return ref
        def member(ref,columns=None):
            check();assert ref['bytes']<=CAPS['maximum_member_bytes']
            with zipfile.ZipFile(io.BytesIO(auth(ref['container']))) as archive:
                assert archive.namelist().count(ref['member'])==1;assert archive.getinfo(ref['member']).file_size==ref['bytes'];raw=archive.read(ref['member'])
            assert len(raw)==ref['bytes'] and sha(raw)==ref['sha256']
            if columns is None:return json.loads(raw)
            pf=pq.ParquetFile(io.BytesIO(raw));assert pf.metadata.num_rows<=CAPS['maximum_source_rows'] and set(columns)<=set(pf.schema_arrow.names)
            # Only the four-category market-supported subset is materialized.
            rows=pq.read_table(io.BytesIO(raw),columns=columns,filters=[('target','in',list(FOCUS)),('season','in',[2024,2026])],use_threads=False).to_pylist()
            return [clean(r) for r in rows]
        owned=module(plan['source_pins']['owned_reference_batch'],'nfl_lab.owned_reference_batch')
        assert owned.__package__=='nfl_lab' and owned.OperationalStorage is legacy.OperationalStorage
        validate_owned_references=owned.validate_owned_references
        refs={r['container']['path']:r['container']['sha256'] for r in plan['inputs'].values()}
        ownership=[]
        for owner in [store.legacy,store.prior_forward,store]:
            selected={path:digest for path,digest in refs.items() if (store if Path(path).is_relative_to(store.forward_root) else store.prior_forward if Path(path).is_relative_to(store.prior_forward.forward_root) else store.legacy) is owner}
            if selected:
                verified,receipt=validate_owned_references(owner,selected);assert set(verified)==set(selected);ownership.append({'count':len(verified),'receipt_sha256':sha(encoded(receipt))})
        global_freeze=member(plan['inputs']['global_freeze'])
        assert global_freeze['state']=='ALL_FORECASTS_PARAMETERS_AND_PAPER_LISTS_FROZEN_BEFORE_EVALUATION_GRADING'
        original_members={r['member']:r for r in global_freeze['members']}
        for name in ['forecasts','paper_frozen']:
            ref=plan['inputs'][name];assert all(original_members[ref['member']][k]==ref[k] for k in ('bytes','sha256'))
        forecasts=member(plan['inputs']['forecasts'],PROJECTION)
        assert all(r['target'] in FOCUS and r['season'] in [2024,2026] and (r['season']!=2026 or 1<=r['week']<=5) for r in forecasts)
        assert all(r['book_kind']=='named' and r['book_id'] in [68,69,79] and r['period']=='event' for r in forecasts)
        def identity(row): return tuple(str(row[k]) for k in IDENTITY)
        assert len({identity(r) for r in forecasts})==len(forecasts)
        def representative(rows):
            result={}
            for row in sorted(rows,key=lambda r:tuple(str(r[k]) for k in UNIT)+(r['book_id'],r['source_collection_naive'],scorer.number(r['line']),r['source_row_number'])):
                result.setdefault(tuple(str(row[k]) for k in UNIT),row)
            return list(result.values())
        primary=[r for r in forecasts if r['primary_role'] is True]
        pools={'FULL_CANONICAL':representative(primary),
            'P1_COMMON_ORIGINAL_OFFER_RULE':representative([r for r in primary if all(scorer.number(r[a+'_point']) is not None for a in ['F','FC','M','H'])]),
            'P2_COMMON_ORIGINAL_OFFER_RULE':representative([r for r in primary if all(scorer.probability(r[a+'_probability']) is not None for a in ['F','FC','FS','M','H']) and scorer.number(r['d_under']) is not None])}
        frozen=[];source_by_id={};selection_counts={};pool_by_key={}
        def append(row,pool,procedure,side,reason,point=None,conditional=None,full=None):
            key=identity(row);oid=sha(encoded(key));source_by_id[oid]=row;record_id=(oid,procedure)
            if record_id in pool_by_key:
                pool_by_key[record_id]['pools'].append(pool);return
            r={k:row[k] for k in IDENTITY+['team','opponent','position','kickoff_utc','source_sha256','source_member','F_fallback','F_model_year','F_control_age','evidence_lane','d_over','d_under','american_odds','under_american_odds','under_source_row_number','quote_pair_status','price_qualified']}
            r.update(opportunity_id=oid,procedure=procedure,pools=[pool],selected_side=side,abstention_reason=reason,
                point=None if scorer.number(point) is None else str(scorer.number(point)),
                conditional_p_over=None if scorer.probability(conditional) is None else str(scorer.probability(conditional)),
                p_over=None,p_under=None,p_push=None,book_settlement='UNRESOLVED_UNQUALIFIED',source_forecast_capsule_sha256=plan['inputs']['forecasts']['container']['sha256'])
            if full is not None:r.update({f'p_{name}':str(value) for name,value in full.items()})
            pool_by_key[record_id]=r;frozen.append(r)
        for pool,rows in pools.items():
            selection_counts[pool]=len(rows)
            for row in rows:
                for arm in ['F','FC','M','H','OFFERED_LINE']:
                    point=row['line'] if arm=='OFFERED_LINE' else row[arm+'_point'];side,reason=scorer.point_side(point,row['line'])
                    append(row,pool,'P1_'+arm,side,reason,point=point)
                for side in ['over','under']:append(row,pool,'ALWAYS_'+side.upper(),side,None)
                for arm in ['F','FC','FS','M','H']:
                    p=row[arm+'_probability'];side,reason=scorer.conditional_side(p)
                    append(row,pool,'P2_CONDITIONAL_'+arm,side,reason,conditional=p)
                full=scorer.law(row['F_over'],row['F_under'],row['F_push']);side,reason=scorer.law_side(row['F_over'],row['F_under'],row['F_push'])
                denom=(full['over']+full['under']) if full else 0
                append(row,pool,'P2_F_FULL',side,reason,conditional=full['over']/denom if denom else None,full=full)
                append(row,pool,'P50_DECISIVE_CONTROL',None,'EQUAL_CONDITIONAL_PROBABILITIES_ABSTAIN',conditional='.5')
        assert len(frozen)<=CAPS['maximum_decision_rows']
        frozen_paper=member(plan['inputs']['paper_frozen'],IDENTITY+['policy','side','decimal_odds','conditional_probability','conditional_EV','score','settlement_contract'])
        active={'decisions.jsonl.gz':jsonl_gzip(frozen),
            'original_paper_selections.jsonl.gz':jsonl_gzip(frozen_paper),
            'FREEZE.json':encoded({'state':'ALL_NEW_POINT_AND_PROBABILITY_SIDES_FROZEN_BEFORE_OUTCOME_DECODE','pool_counts':selection_counts,'decisions':len(frozen),'new_fits':0,'sources':plan['inputs'],'ownership':ownership,'plan_sha256':args.sha256,'actual_UTC':now()})}
        freeze_ref=save('DECISIONS_FROZEN.zip',active);active={}
        # Outcomes are first decoded only after the entire decision freeze reads back.
        labels=member(plan['inputs']['matched'],PROJECTION+['participation_state','original_outcome_state','actual','outcome_state','label_source'])
        assert len(labels)==len(forecasts)
        original={identity(r):r for r in forecasts};joined={}
        for row in labels:
            key=identity(row);assert key in original and {k:row[k] for k in PROJECTION}==original[key]
            assert key not in joined;joined[key]=row
        for decision in frozen:
            row=joined[identity(decision)];graded=scorer.grade(decision,row['actual'],row['outcome_state']);graded['label_source']=row['label_source'];graded['participation_state']=row['participation_state'];grade_rows.append(graded)
        paper_graded=member(plan['inputs']['paper_graded'],IDENTITY+['policy','side','decimal_odds','conditional_probability','conditional_EV','score','settlement_contract','actual','outcome_state','net_units','settlement'])
        paper_key=lambda r:identity(r)+(r['policy'],)
        frozen_map={paper_key(r):r for r in frozen_paper};assert len(frozen_map)==len(frozen_paper)==len(paper_graded)
        for row in paper_graded:
            prior=frozen_map[paper_key(row)];assert all(row[k]==value for k,value in prior.items())
            exact,state=scorer.assumed_settlement(row['side'],row['actual'],row['line'],row['outcome_state'],row['decimal_odds'],row['settlement_contract'])
            assert state==row['settlement'] and ((exact is None and row['net_units'] is None) or (exact is not None and scorer.number(row['net_units']) is not None and abs(exact-scorer.number(row['net_units']))<=scorer.TOL))
            paper_rows.append(dict(row,return_recomputed_from_original_decimal_representation=None if exact is None else str(exact),authenticated_book_settlement=False))
        from collections import defaultdict,Counter
        source_coverage={'matched_offer_rows':len(labels),'primary_role_rows':len(primary),'pool_opportunities':selection_counts,'outcome_states':dict(Counter(r['outcome_state'] for r in labels))}
        new_decisions_n=len(frozen);original_paper_n=len(frozen_paper)
        del frozen,pool_by_key,pools,primary,forecasts,source_by_id,original,joined,labels
        groups=defaultdict(list)
        for row in grade_rows:
            for pool in row['pools']:
                groups[(row['season'],row['target'],pool,row['procedure'],'SEASON')].append(row)
                groups[(row['season'],row['target'],pool,row['procedure'],str(row['week']))].append(row)
        summaries=[];weekly=[]
        for (year,target,pool,procedure,week),rows in sorted(groups.items()):
            if pool=='P1_COMMON_ORIGINAL_OFFER_RULE' and not (procedure.startswith('P1_') or procedure.startswith('ALWAYS_')):continue
            if pool=='P2_COMMON_ORIGINAL_OFFER_RULE' and not (procedure.startswith('P2_') or procedure.startswith('ALWAYS_') or procedure.startswith('P50_')):continue
            metric=scorer.summarize(rows)
            if week=='SEASON':summaries.append({'season':year,'target':target,'pool':pool,'procedure':procedure,'period':week,**metric})
            elif pool!='FULL_CANONICAL':weekly.append([year,target,'P1' if pool.startswith('P1') else 'P2',procedure,int(week),len(rows),*[metric['counts'].get(k,0) for k in ['CORRECT','INCORRECT','PUSH_STATISTIC','ABSTAIN','UNRESOLVED']],metric['point_MAE'],metric['Brier_decisive'],metric['Brier_rows'],metric['games']])
        contrasts=[]
        for year in [2024,2026]:
            for target in FOCUS:
                for pool,procedures,control,loss in [('P1_COMMON_ORIGINAL_OFFER_RULE',['P1_F','P1_FC','P1_M','P1_H','ALWAYS_OVER','ALWAYS_UNDER'],'P1_F','direction'),('P2_COMMON_ORIGINAL_OFFER_RULE',['P2_F_FULL','P2_CONDITIONAL_F','P2_CONDITIONAL_FC','P2_CONDITIONAL_FS','P2_CONDITIONAL_M','P2_CONDITIONAL_H','P50_DECISIVE_CONTROL'],'P2_CONDITIONAL_F','Brier')]:
                    b=groups.get((year,target,pool,control,'SEASON'),[])
                    for method in procedures:
                        a=groups.get((year,target,pool,method,'SEASON'),[])
                        if a and b:contrasts.append({'season':year,'target':target,'pool':pool,'candidate':method,'control':control,'game':scorer.paired(a,b,loss),'week':scorer.paired(a,b,loss,'week')})
        paper_summary=[]
        for year in [2024,2026]:
            for target in FOCUS:
                policies=sorted({r['policy'] for r in paper_rows if r['season']==year and r['target']==target})
                for policy in policies:
                    rows=[r for r in paper_rows if r['season']==year and r['target']==target and r['policy']==policy];counts=Counter(r['settlement'] for r in rows);known=[r for r in rows if r['net_units'] is not None];net=sum(scorer.number(r['net_units']) for r in known) if known else None;decisive=counts['assumed_win']+counts['assumed_loss']
                    paper_summary.append({'season':year,'target':target,'policy':policy,'selected':len(rows),'states':dict(counts),'original_sides_preserved':True,'assumed_net_units_known_only':float(net) if net is not None else None,'known_settled_stakes_including_push_void':len(known),'ROI_known_settled':float(net/len(known)) if known else None,'hit_rate_wins_over_decisive':counts['assumed_win']/decisive if decisive else None,'actual_book_settlement':'UNQUALIFIED','new_selection':False})
        public={'version':VERSION,'scientific_version':SCIENTIFIC_VERSION,'preserved_v1_failure':plan['preserved_v1_failure_public_record'],'state':'NEW_ZERO_REFIT_DIRECTION_COMPARISON_COMPLETE','primary':'P1 fixed-side statistical 0/1 error on decisive selected common rows; P2 proper decisive Brier separate',
            'evidence_lane':'TIMING_UNVERIFIED_EXPLORATORY_RECONSTRUCTION_NOT_PREGAME_OR_CURRENT_WEBSITE','seasons':[2024,2026],'2026_weeks':[1,2,3,4,5],
            'all_original_quote_artifacts':'PRESERVED; new scoring uses registered representative offers only; all-quote secondary direction analysis DEFERRED_PENDING_SEPARATE_BOUNDED_ADMISSION',
            'category_status':{'pass_att':'SCORED_WHERE_SUPPORTED','rush_att':'SCORED_WHERE_SUPPORTED','rec':'SCORED_WHERE_SUPPORTED','rec_tgt':'NOT_AVAILABLE_NO_MATCHED_TARGET_MARKET_OR_FORECAST_IN_SOURCE'},
            'activity':{'new_fits':0,'new_models':0,'new_statistic_forecasts':0,'new_deterministic_side_decisions':new_decisions_n,'new_pregame_capture':0,'original_paper_selection_rows_reused':original_paper_n},
            'source_coverage':source_coverage,
            'summaries':summaries,'weekly':{'columns':['season','target','common_pool','procedure','week','offered','correct','incorrect','statistic_push','abstain','unresolved','point_MAE','decisive_Brier','Brier_rows','games'],'rows':weekly},'paired_contrasts':contrasts,'original_paper_exploratory':paper_summary,
            'limitations':['2026 football F is frozen2024 model, not modern/current website champion.','Naive collector timestamps do not authenticate historical pregame odds availability.','All seasons are exposed development; nominal cluster intervals do not establish selected-winner superiority.','FC/FS/M/H probabilities are conditional decisive; no push mass, full PMF or unconditional EV is inferred.','P1 is point direction; lower MAE and direction hit rate are separate products.','No new football forecasts, fits, probability calibration, EV selections, live admission or deployment.','Original paper lists remain frozen and actual sportsbook settlement unqualified.','Decimal comparisons preserve stored float decimal representations, not unknown upstream precision.','Week7 and modern/backfield compatibility require separate admissions.'],
            'freeze_manifest_id':VERSION+'/DECISIONS_FROZEN.zip','started_at_UTC':started,'finished_scoring_at_UTC':now(),'usage':usage(),'independent_QA':'PENDING_SEPARATE_FINITE_REVIEW','publication':'RESULT_SAVED_PUBLICATION_PENDING'}
        def csv_gzip(rows):
            fields=sorted({k for r in rows for k in r});sink=io.BytesIO()
            with io.TextIOWrapper(gzip.GzipFile(fileobj=sink,mode='wb',mtime=0),encoding='utf-8',newline='') as stream:
                writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
                for row in rows:writer.writerow({k:json.dumps(v,sort_keys=True) if isinstance(v,(list,dict)) else v for k,v in row.items()})
            return sink.getvalue()
        view_columns=['season','week','game_id','player_id','target','procedure','point','line','selected_side','conditional_p_over','actual','direction_result','point_absolute_error','outcome_state','book_settlement_status','d_over','d_under','source_collection_naive']
        payload=encoded({'columns':view_columns,'rows':[[r.get(k) for k in view_columns] for r in grade_rows],'public_summary':public})
        packed=base64.b64encode(gzip.compress(payload,mtime=0)).decode()
        page=('<!doctype html><meta charset="utf-8"><title>NFL four-category original offers and forecasts</title><h1>Timing-unverified research scorecard</h1><p>Original point, side, line, actual and outcome status. Paper settlements are assumptions, not authenticated bookmaker results.</p><select id="category"><option value="">All categories</option><option>pass_att</option><option>rush_att</option><option>rec</option></select><select id="method"><option value="">All procedures</option></select><div id="out"></div><script>const packed="'+packed+'";let rows=[];async function main(){let a=Uint8Array.from(atob(packed),c=>c.charCodeAt(0)),s=new Blob([a]).stream().pipeThrough(new DecompressionStream("gzip")),d=JSON.parse(await new Response(s).text());rows=d.rows.map(v=>Object.fromEntries(d.columns.map((k,i)=>[k,v[i]])));for(let m of [...new Set(rows.map(r=>r.procedure))].sort()){let o=document.createElement("option");o.textContent=m;method.append(o)}render()}function render(){out.replaceChildren();let list=rows.filter(r=>(!category.value||r.target===category.value)&&(!method.value||r.procedure===method.value));let p=document.createElement("p");p.textContent=list.length+" saved method/offer records; repeated procedures are not independent games";out.append(p);let t=document.createElement("table");for(let r of list.slice(0,2000)){let tr=document.createElement("tr");for(let k of ["season","week","game_id","player_id","target","procedure","point","line","selected_side","conditional_p_over","actual","direction_result","point_absolute_error","outcome_state"]){let td=document.createElement("td");td.textContent=r[k]??"unavailable";tr.append(td)}t.append(tr)}out.append(t)}category.onchange=method.onchange=render;main()</script>').encode()
        active={'grade.jsonl.gz':jsonl_gzip(grade_rows),'original_paper_grade.jsonl.gz':jsonl_gzip(paper_rows),'predictions_actuals.csv.gz':csv_gzip(grade_rows),'original_paper.csv.gz':csv_gzip(paper_rows),'scorecard.html':page,'PUBLIC_SUMMARY.json':encoded(public)}
        assert len(active['PUBLIC_SUMMARY.json'])<=CAPS['public_aggregate_bytes'];grade_ref=save('GRADE_COMPLETE.zip',active);active={}
        check()
        # Private standalone scorecard is optional only if all retained/peak caps permit it.
        if plan['standalone_scorecard']:
            save('PRIVATE_SCORECARD.zip',{'scorecard.html':page})
        public['usage']=usage();public['managed_writer']='CLOSED';public['finished_at_UTC']=now()
        check();note('COMPLETE.json',{'state':public['state'],'started_at_UTC':started,'finished_at_UTC':now(),'freeze':freeze_ref,'grade':grade_ref,'usage':usage(),'managed_writer':'CLOSED'})
        public_bytes=encoded(public);assert len(public_bytes)<=CAPS['public_aggregate_bytes'];Path(plan['public_result']).write_bytes(public_bytes)
        print(encoded({'state':public['state'],'usage':usage(),'freeze':freeze_ref,'grade':grade_ref}).decode())
    except BaseException as error:
        failure={'state':'FAILED_PARTIALS_PRESERVED_NO_AUTOMATIC_RETRY','started_at_UTC':started,'finished_at_UTC':now(),'error':type(error).__name__+':'+str(error),'usage':usage(),'writes':writes,'managed_writer':'CLOSED'}
        if store is not None and len(writes)<3:
            try:
                if grade_rows:active['partial_grade.jsonl.gz']=jsonl_gzip(grade_rows)
                if 'frozen' in locals():active['partial_decisions.jsonl.gz']=jsonl_gzip(frozen)
                save('FAILED.zip',{'FAILURE.json':encoded(failure),**active},retain=True)
            except BaseException as retention:failure['retention_error']=type(retention).__name__+':'+str(retention)
        try:note('FAILED.json',failure)
        except BaseException:pass
        raise
    finally:signal.setitimer(signal.ITIMER_REAL,0)


if __name__=='__main__':main()
