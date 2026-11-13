"""Root-authorized projection of existing aggregate counts; no NFL row grading."""
from pathlib import Path
import collections, datetime, gzip, hashlib, json, math, os, resource, signal, sys, time

sys.dont_write_bytecode = True
ROOT = Path('/workspace/nfl-methods-integration')
OUT = Path(__file__).resolve().parent
RECON = ROOT/'reports/abc-championship/category-decision-release-01/LAW_DIRECTION_RECONCILIATION_V1.json'
RECON_SHA = '1e982369240307f141d8ab6c266a55407c4deed61f8d2c866f1273777d6d01f1'
FIELDS = ['wins','losses','decided','rate','unresolved','push','DNP','selected']
WCOL = ['week','over','under','combined','full_board_eligible','source_policy_opportunities',
        'selected_sides','intentional_abstentions','technical_unavailable','source_games','source_fallback_count']
VERSION = 'A-INFORMATION-FIRST-W1-W9-AGGREGATE-PROJECTION-v1'

def enc(x):
    return (json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def sha(b): return hashlib.sha256(b).hexdigest()
def require(x,message):
    if not x: raise ValueError(message)
def readref(path,expected=None,size=None):
    p=Path(path)
    require(p.is_absolute() and p.resolve()==p and not any(q.is_symlink() for q in [p,*p.parents]),'Canonical immutable source required')
    b=p.read_bytes()
    require(expected is None or sha(b)==expected,'Source SHA mismatch: '+p.name)
    require(size is None or len(b)==size,'Source size mismatch: '+p.name)
    return b,dict(path=str(p.relative_to(ROOT)),bytes=len(b),sha256=sha(b))
def integer(v):
    if v is None:return None
    require(not isinstance(v,bool) and isinstance(v,(int,float)) and math.isfinite(v) and v>=0 and int(v)==v,'Invalid aggregate count')
    return int(v)
def take(d,*names):
    for k in names:
        if k in d and d[k] is not None:return integer(d[k])
    return None
def total(values): return sum(values) if all(v is not None for v in values) else None
def side(d,states):
    if not isinstance(d,dict):return [None]*8
    n=take(d,'decided');w=take(d,'wins');l=take(d,'losses')
    # Empty aggregate count cells, not unknown player statistics.
    if n==0:w=0 if w is None else w;l=0 if l is None else l
    if None not in [w,l,n]:require(w+l==n,'Wins/losses do not reconcile')
    p=take(d,'push','pushes');v=take(d,'DNP','dnp');u=take(d,'unresolved');s=take(d,'selected')
    # A complete histogram's absent category denotes count zero. This is not a
    # sparse player-stat contract and never assigns a missing NFL outcome zero.
    if isinstance(states,dict):
        if p is None and states.get('PUSH',0)==0:p=0
        if v is None and states.get('DNP',0)==0:v=0
    void_free=not isinstance(states,dict) or (states.get('VOID',0)==0 and states.get('VOIDED',0)==0)
    if u is None and void_free and None not in [s,n,p,v]:
        u=s-n-p-v;require(u>=0,'Negative unresolved aggregate')
    if s is None:s=total([w,l,u,p,v])
    if void_free and None not in [s,w,l,u,p,v]:require(s==w+l+u+p+v,'Selected side count mismatch')
    return [w,l,n,w/n if n and w is not None else None,u,p,v,s]
def combine(a,b):
    z=[total([a[i],b[i]]) if i!=3 else None for i in range(8)]
    z[3]=z[0]/z[2] if z[2] and z[0] is not None else None
    return z
def basekey(key):return json.dumps({k:v for k,v in key.items()if k!='selection_policy'},sort_keys=True,separators=(',',':'))
def broad_policy(policy):
    if policy.startswith('TOP_'):return 'FULL_PRIMARY_ROSTER_INTERSECTION_RECORDED_BOARD'
    if policy.startswith('P2_EXACT_LINE::'):
        return 'P2_EXACT_LINE::FULL_BOARD'
    if policy=='P2_EXACT_LAW_CONF55':return 'P2_EXACT_LAW'
    return policy
def scope(policy):
    if policy=='CONSTANT':return 'BROAD_BOARD_CONSTANT_CONTROL'
    if 'TOP_' in policy or 'ABSTAIN_' in policy or 'CONF55' in policy:return 'SELECTIVE'
    return 'BROAD_BOARD'
def summary(entries):
    if not entries:
        return dict(over=[None]*8,under=[None]*8,combined=[None]*8,eligible=None,
            selected=None,coverage=None,selected_unknown_accuracy_bounds=None)
    sides=[]
    for side_index in [1,2,3]:
        z=[total([r[side_index][i] for r in entries]) if i!=3 else None for i in range(8)]
        z[3]=z[0]/z[2] if z[2] and z[0] is not None else None;sides.append(z)
    eligible=total([r[4]for r in entries]);selected=total([r[6]for r in entries]);c=sides[2]
    bounds=[c[0]/(c[2]+c[4]),(c[0]+c[4])/(c[2]+c[4])] if None not in [c[0],c[2],c[4]] and c[2]+c[4]>0 else None
    return dict(over=sides[0],under=sides[1],combined=c,eligible=eligible,selected=selected,
        coverage=selected/eligible if eligible and selected is not None else None,
        selected_unknown_accuracy_bounds=bounds)
def write_once(path,body):
    with path.open('xb')as f:f.write(body);f.flush();os.fsync(f.fileno())

def main():
    start=time.monotonic();cpu=time.process_time()
    resource.setrlimit(resource.RLIMIT_CPU,(55,56));resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,)*2)
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('80second aggregate projection continuation bound')));signal.alarm(80)
    require(json.loads((OUT/'ADOPTION_AND_BUDGET_V1.json').read_text())['document_id']=='ABC-INFORMATION-FIRST-20261112-01','Assignment adoption required')
    output=OUT/'DIRECTION_W1_W9_PROJECTION_V1.json.gz';readable=OUT/'DIRECTION_W1_W9_PROJECTION_V1.md'
    require(not output.exists()and not readable.exists(),'Immutable output already exists')
    raw,recon_ref=readref(RECON,RECON_SHA);recon=json.loads(raw);refs=[];records=[]
    for item in recon['public_source_parts']:
        body,ref=readref(ROOT/item['path'],item['sha256'],item['bytes']);refs.append(ref)
        doc=json.loads(gzip.decompress(body))
        for ordinal,r in enumerate(doc['records']):
            if r['metric']=='statistical_decisive_hit_rate':records.append((len(refs)-1,ordinal,r))
    require(len(refs)==10 and len(records)>0,'Expected ten bound category parts')
    lookup={}
    for _,_,r in records:
        k=(basekey(r['key']),r['key']['selection_policy']);require(k not in lookup,'Ambiguous complete product key');lookup[k]=r
    projected=[]
    for part,ordinal,r in records:
        key=r['key'];policy=key['selection_policy'];bp=broad_policy(policy)
        board=lookup.get((basekey(key),bp));bw={int(x['week']):x for x in board['weekly_support']if x['season']==2026}if board else {}
        ww={int(x['week']):x for x in r['weekly_support']if x['season']==2026}
        actual=[];diagnostic=[];weekstates=[];zero=[];no_decisions=[];evaluated=[];decisions=[]
        for week in range(1,10):
            w=ww.get(week)
            if week>=8 or w is None:
                weekstates.append('DIFFERENT_SAVED_W8_PRODUCTS_NOT_SUBSTITUTABLE'if week==8 else'MISSING_EXACT_ACTUAL_BOARD_OR_OUTPUT')
                continue
            states=w.get('states');a=side(w.get('over'),states);b=side(w.get('under'),states);c=combine(a,b)
            board_week=bw.get(week);eligible=take(board_week,'eligible','eligible_or_opportunities')if board_week else None
            # For original point/law records this is the policy frame size;
            # selected records cannot supply their own broader denominator.
            opp=take(w,'eligible_or_opportunities','eligible');selected=total([a[7],b[7]])
            abst=take(w,'no_lean','abstain','abstentions')
            if abst is None and isinstance(states,dict):abst=integer(states.get('ABSTAIN',0))
            unavailable=take(w,'unavailable','missing_law','missing_prediction','missing_offer_or_prediction')
            row=[week,a,b,c,eligible,opp,selected,abst,unavailable,take(w,'games'),take(w,'fallback_rows','fallback_scored')]
            if week in [6,7]:
                diagnostic.append(row);weekstates.append('SITE_THRESHOLD_DIAGNOSTIC_NOT_ADMITTED_AS_ACTUAL_OFFER');continue
            actual.append(row);evaluated.append(week);weekstates.append('OBSERVED_INDIVIDUAL_BOOK_LINE_QUOTE_TIME_UNVERIFIED')
            if c[2] and c[2]>0:decisions.append(week)
            else:no_decisions.append(week)
            if selected==0:
                reason='TECHNICAL_UNAVAILABILITY'if unavailable and unavailable>0 else'POLICY_ABSTENTION'if unavailable==0 and abst and eligible==abst else'REASON_NOT_BOUND_BY_AGGREGATE'
                zero.append([week,reason])
        s=summary(actual);o,u,c=s['over'],s['under'],s['combined']
        side_scope='UNBOUND_SIDE_SCOPE'if None in [o[7],u[7]]else'TWO_SIDED'if o[7]and u[7]else'OVER_ONLY'if o[7]else'UNDER_ONLY'if u[7]else'NO_SELECTED_SIDE'
        projected.append(dict(key_sha256=r['key_sha256'],key=key,method=r['method_alias'],source_part=part,
            source_record=ordinal,scope=scope(policy),board_key_sha256=board['key_sha256']if board else None,
            actual_weekly=actual,diagnostic_weekly=diagnostic,W1_W9_states=weekstates,
            actual_boards_evaluated=evaluated,weeks_with_decisions=decisions,no_decision_weeks=no_decisions,
            zero_selected_weeks=zero,missing_actual_board_weeks=[w for w in range(1,10)if w not in evaluated],
            summary=s,side_scope=side_scope,partial_observed_combined_90=c[3]is not None and c[3]>=.9,
            partial_observed_over_90=o[3]is not None and o[3]>=.9,partial_observed_under_90=u[3]is not None and u[3]>=.9,
            target_status='TARGET_NOT_ESTABLISHED',duration_decision_weeks=len(decisions),
            original_reported_floor=r['five_week_floor']))
    # Separate calculation already recorded in the earlier public reconciliation.
    byid={r['key_sha256']:r for r in projected};checks=0
    for group in recon['category_comparisons']+recon['selective_raw_maxima']:
        for old in group.get('law_maxima',group.get('own_population_raw_maxima',[])):
            r=byid[old['key']]
            require(r['summary']['over'][:3]==old['O'][:3] and r['summary']['under'][:3]==old['U'][:3],'Independent old annual count parity failed')
            require(r['summary']['combined'][4]==old['O'][3]+old['U'][3],'Source unresolved parity failed');checks+=1
    top=byid['03987dde683658f5cabc4f4a0407b459e42e8f3861730ea3612e40bba53fc4f2']
    require(top['summary']['combined'][:3]==[23,7,30]and top['summary']['eligible']==266 and top['summary']['selected']==30,'Backfield23/30 and30/266 parity failed')
    cmp=byid['a402a89090d5e7d2a3b527e60d7b45a3604581be62c56f40b67e10b0248521d1']
    require(cmp['actual_boards_evaluated']==[1,2,3,4,5]and cmp['weeks_with_decisions']==[1,2,3,4]and cmp['summary']['selected']==18 and any(x[0]==5 for x in cmp['zero_selected_weeks']),'Completion zero-selection-week parity failed')
    categories=['pass_yd','pass_td','pass_cmp','pass_att','pass_int','rush_yd','rush_att','rec','rec_yd','rush_rec_yd','anytime_td','nick-chart-ppr-v1']
    status=[]
    for category in categories:
        rr=[x for x in projected if x['key']['target']==category];b=[x for x in rr if x['scope']!='SELECTIVE'];s=[x for x in rr if x['scope']=='SELECTIVE']
        status.append(dict(category=category,broad_records=len(b),selective_records=len(s),partial_observed90_broad=sum(x['partial_observed_combined_90']for x in b),partial_observed90_selective=sum(x['partial_observed_combined_90']for x in s),broad_target='TARGET_NOT_ESTABLISHED',selective_target='TARGET_NOT_ESTABLISHED',gap='NO_MATCHING_EVENT_SIDE_OFFER_CONTRACT'if not rr else'NO_EXACT_COMPLETE_QUALIFIED_W1_W9_BOARD_RECORD'))
    result=dict(id=VERSION,owner='A; contribution to C common coordinator, not a new master ranking',UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),reconciliation=recon_ref,source_parts=refs,
        side_columns=FIELDS,weekly_columns=WCOL,records=projected,all_twelve_status=status,
        contract=dict(source_window='AdmitW1-5 only; W6-7 retain separate site/reference diagnostics; W8 different frozen products; W9missing',ordinary_mainline='UNVERIFIED_WHERE_NO_BOUND_CLASSIFICATION',side_unknown='Source side unresolved; complete histogram/selected arithmetic only for aggregate count states; never missingNFLstat->zero',missing_counts='Null means unsupplied, not intentionalabstention. Source fallback counts are not independently certified learnedprovenance.',unknown_bound='[wins/(decided+selected_unresolved),(wins+selected_unresolved)/(decided+selected_unresolved)]; knownpush/DNP separate; no inventedmissingboardN',venue_void='Not qualified venue settlement; VOID counts N/A, statistical push/DNP only',duration_counts='Evaluated boards and positive-decision weeks reported separately; no new week-count or admission rule inferred',uncertainty='No newinterval. Original mixedwindow intervals remainboundin originalsource and are not transferred to this filteredpanel.',ninety='Partialexposed observedaccuracy is not predictedconfidence, controlled statistical>=90claim, completeW1-9 record or laterperformance. Constantcontrols notapprovedliveprocedures.',aliases='Output/policy views and aliases are not independent learners or NFLobservations.'),
        checks=dict(old_reconciliation_count_parity=checks,Backfield23of30_30of266=True,completion5boards4decisionweeks=True),new_fits_inference_grades_NFL_games_weeks=0,
        resources=dict(CPU_seconds=time.process_time()-cpu,wall_seconds=time.monotonic()-start,RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024),worker_sha256=sha(Path(__file__).read_bytes()),format_continuation_GO_sha256=sha((OUT/'DIRECTION_FORMAT_CONTINUATION_GO_V1.json').read_bytes()))
    body=gzip.compress(enc(result),compresslevel=9,mtime=0);require(len(body)<=114688,'112KiB compressed projection estimate')
    lines=['A executed a new accounting projection of existing frozen aggregate records. No NFL forecasts, grades, threshold searches, fits or tested weeks were added.','',
        '2026 W1-9 broad-board and selective target: TARGET_NOT_ESTABLISHED. Source-qualified retained lines cover W1-5 with unverified quote clocks; ordinary/mainline classification is unverified where unbound. W6-7 diagnostic boards, different W8 captured products and missing W9 exact products are kept separate.','',
        '| Category | Broad/control records | Selective records | Partial observed combined >=90: broad / selective | W1-9 status |','|---|---:|---:|---:|---|']
    for x in status:lines.append('|'+x['category']+'|'+str(x['broad_records'])+'|'+str(x['selective_records'])+'|'+str(x['partial_observed90_broad'])+' / '+str(x['partial_observed90_selective'])+'|TARGET_NOT_ESTABLISHED|')
    lines+=['','Backfield-CDF frozen Top-6: Over3-1 / Under20-6 / combined23-7 (76.67%),30/266 boardcoverage(11.28%), decisions in allfive admittedweeks. Its selectedunknown count is0. This is not a 90% finding or website cross-category Top Picks replay.',
        'Completion RESPONSE_CDF SHRINK0.5 frozen confidence0.55 policy: five boardweeks evaluated, decisions in onlyW1-4, zero selected inW5;18/88 selected. Zero selection is not a missingboard and does not create a fifth decisionweek.','',
        'Every retained direction record, each own Over/Under/combined count/rate, W1-W9 week state, selected unknown/push/DNP counts, technical unavailability where supplied, exact full-board denominator pairing and selected-unknown sensitivity bounds are in DIRECTION_W1_W9_PROJECTION_V1.json.gz. Unbound fields remain null. Side-only >=90 values do not establish a two-sided category result.']
    observed=[x for x in projected if x['partial_observed_combined_90']]
    lines+=['','Partial observed >=90 complete-policy records: '+str(len(observed))+'. All are exposed partial samples; none establishes the complete W1-9 target.']
    for x in sorted(observed,key=lambda x:x['key_sha256'])[:12]:
        c=x['summary']['combined'];lines.append('- '+x['key']['target']+' / '+str(x['method'])+' / '+x['key']['selection_policy']+': '+str(c[0])+'/'+str(c[2])+', '+x['side_scope']+', actualweeks'+str(x['actual_boards_evaluated'])+'.')
    if len(observed)>12:lines.append('Remaining records are preserved in the machine output; the display truncation uses key order, not accuracy.')
    lines+=['','Independent sanity checks matched '+str(checks)+' previously recorded annual law summaries, including source unresolved counts; Backfield23/30 and fullboard266; completion five evaluated versus four decisionweeks. Original seven-week floor labels and raw source versions remain preserved by reference, without inheriting their unqualified weeks.']
    text=('\n'.join(lines)+'\n').encode();require(len(text)<=8192,'8KiB readable cap')
    require(sum(p.stat().st_size for p in OUT.rglob('*')if p.is_file())+len(body)+len(text)+16384<=262144,'Shared metadata cap with root reserve')
    write_once(output,body);require(sha(output.read_bytes())==sha(body),'Compressed readback mismatch');require(json.loads(gzip.decompress(output.read_bytes()))==result,'Decoded readback mismatch')
    write_once(readable,text);require(readable.read_bytes()==text,'Readable readback mismatch')
    signal.alarm(0)
    print(json.dumps(dict(state='COMPLETE_AGGREGATE_ONLY_PROJECTION',records=len(projected),output_sha256=sha(body),compressed_bytes=len(body),readable_bytes=len(text),partial_observed90_records=len(observed),checks=checks,resources=result['resources'])))

if __name__=='__main__':
    try:main()
    except BaseException as e:
        failure=OUT/('DIRECTION_PROJECTION_FAILED_'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.json')
        write_once(failure,enc(dict(state='FAILED_PRESERVED_NO_AUTOMATIC_RETRY',error=type(e).__name__,message=str(e),worker_sha256=sha(Path(__file__).read_bytes()))));raise
