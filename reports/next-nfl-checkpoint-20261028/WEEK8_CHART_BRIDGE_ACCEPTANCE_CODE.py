"""Independent bounded chart-label arithmetic acceptance, not NFL accuracy."""
from pathlib import Path
import collections
import datetime
import gzip
import gc
import hashlib
import io
import json
import math
import resource
import signal
import sys
import time

PLAN = Path(__file__).with_name('WEEK8_CHART_BRIDGE_QA_PLAN.json')
OUTPUT = Path(__file__).with_name('WEEK8_CHART_BRIDGE_INDEPENDENT_ACCEPTANCE.json')
WEIGHTS = {'pass_yd':.04,'pass_td':4.,'pass_int':-1.,'rush_yd':.1,'rush_td':6.,'rec':1.,'rec_yd':.1,'rec_td':6.,'fum_lost':-1.,'pass_2pt':2.,'rush_2pt':2.,'rec_2pt':2.,'off_fum_rec_td':6.,'kick_return_td':6.,'punt_return_td':6.,'fg_return_td':6.}
SIGNED={'pass_yd','rush_yd','rec_yd'}
start=time.monotonic(); cpu=time.process_time()
checks=0

def require(x,message):
    global checks
    checks+=1
    if not x:raise ValueError(message)

def sha(b):return hashlib.sha256(b).hexdigest()

def read(ref, compressed=False):
    p=Path(ref['path']);require(p.resolve()==p and p.is_absolute(),'canonical immutable source path')
    before=p.stat();b=p.read_bytes();after=p.stat()
    require(len(b)==ref['bytes'] and sha(b)==ref['sha256'],'byte/hash identity')
    require((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns),'source stamp stable')
    if compressed:
        require(len(b)<=plan['resources']['maximum_compressed_input_bytes'],'compressed source cap')
        with gzip.GzipFile(fileobj=io.BytesIO(b)) as f:decoded=f.read(plan['resources']['maximum_uncompressed_bytes_per_capsule']+1)
        require(len(decoded)<=plan['resources']['maximum_uncompressed_bytes_per_capsule'],'decoded cap')
    else:decoded=b
    return json.loads(decoded)

def key(r):return tuple(r['identity'][k] for k in ('season','week','game_id','team','opponent','player_id','season_type'))

def numeric(row):
    if row['value'] is None:
        require(row['state'] not in ('played_zero','played_score'),'numeric state missing value')
        return False
    require(row['state'] in ('played_zero','played_score') and bool(row['participation_evidence']),'numeric independent participation state')
    require(not row['missing_components'] and not row['invalid_components'],'numeric complete components')
    require(set(row['components'])==set(WEIGHTS),'all16 component keys')
    for k,w in WEIGHTS.items():
        v=row['components'][k]
        require(type(v) in (int,float) and math.isfinite(v),'finite primitive')
        if k not in SIGNED:require(v>=0 and v==int(v),'nonnegative integer primitive')
    value=math.fsum(WEIGHTS[k]*row['components'][k] for k in WEIGHTS)
    require(math.isclose(value,row['value'],rel_tol=0,abs_tol=1e-10),'independent chart arithmetic')
    require((row['state']=='played_zero')==(value==0),'zero vs score state')
    return True

def rare_check(record):
    events=record['source_events'];identity=record['identity'];broad=record['broad_totals'];given=record['classified_components'];want={}
    for e in events:
        require(e['game_id']==identity['game_id'] and e['td_team']==identity['team'] and e['td_player_id']==identity['player_id'],'rare exact scorer context')
        require(e['play_deleted']==0 and e['play_type'] not in (None,'no_play') and e['two_point_attempt']==0 and e['touchdown']==1,'rare valid nonnullified scoring event')
    n=broad['fumble_recovery_tds']
    if isinstance(n,(float,int)) and n>0:
        found=[e for e in events if e['fumble']==1 and e['pass_touchdown']==0 and e['rush_touchdown']==0]
        if len(found)==n and all(e['special']==0 and e['td_team'] in (e['posteam'],e['defteam']) for e in found):
            offense=[e for e in found if e['td_team']==e['posteam']]
            if all(e['td_player_id'] in (e['fumble_recovery_1_player_id'],e['fumble_recovery_2_player_id']) or e['lateral_recovery']==1 for e in offense):want['off_fum_rec_td']=len(offense)
    n=broad['special_teams_tds']
    if isinstance(n,(float,int)) and n>0:
        found=[e for e in events if e['special']==1 and e['fumble']==0]
        counts={'kick_return_td':0,'punt_return_td':0,'fg_return_td':0};okay=len(found)==n
        for e in found:
            flags=[e[k] for k in ('kickoff_attempt','punt_attempt','field_goal_attempt')]
            if any(v not in (0,1) for v in flags) or sum(flags)>1 or e['own_kickoff_recovery_td']!=0:okay=False
            elif e['return_touchdown']==1 and sum(flags)==1:
                if e['punt_attempt']==1 and e['punt_blocked']!=0:okay=False
                else:counts[list(counts)[flags.index(1)]]+=1
            elif e['rush_touchdown']==1 or e['pass_touchdown']==1 or e['interception']==1:pass
            else:okay=False
        if okay:want.update(counts)
    require({k:v['value'] for k,v in given.items()}==want,'independent conservative rare-classification reconciliation')

raw=PLAN.read_bytes();plan=json.loads(raw)
require(len(sys.argv)==3 and sys.argv[1]==sha(raw),'exact proposed plan hash')
go=json.loads(Path(sys.argv[2]).read_bytes())
require(go['state']=='GO' and go['root']=='/root' and go['plan_sha256']==sha(raw),'root GO before label decode')
resource.setrlimit(resource.RLIMIT_CPU,(15,16))
def alarm(*unused):raise TimeoutError('independent acceptance30s bound')
signal.signal(signal.SIGALRM,alarm);signal.setitimer(signal.ITIMER_REAL,30)
try:
    old=read(plan['inputs']['original'],True)
    old_target=old['target'];old_count=len(old['labels'])
    before={key(r):(sha(json.dumps(r,sort_keys=True,separators=(',',':'),allow_nan=False).encode()),r['value'],r['state']) for r in old['labels']}
    del old
    gc.collect()
    new=read(plan['inputs']['bridge'],True);summary=read(plan['inputs']['safe_aggregate'])
    require(old_target==new['target']==summary['target']=='nick-chart-ppr-v1','scoring contract identity')
    require(new['plan_sha256']==summary['plan_sha256'],'bridge plan binding')
    require(new['original_label_capsule_sha256']==summary['original_label_capsule_sha256']==plan['inputs']['original']['sha256'],'original preserved source hash')
    require(old_count==len(new['labels'])==14160,'complete14160 population')
    after={key(r):r for r in new['labels']}
    require(len(before)==len(after)==14160 and set(before)==set(after),'full unique canonical identities')
    transitions=collections.Counter();numeric_counts=collections.Counter();season_states=collections.defaultdict(collections.Counter);changed=0
    for k,a in after.items():
        o=before[k]
        require(a['scoring_version']=='nick-chart-ppr-v1','per-row target')
        if k[0] in (2024,2025):require(sha(json.dumps(a,sort_keys=True,separators=(',',':'),allow_nan=False).encode())==o[0],'original earlier-season label byte-equivalent structured values')
        else:
            require(k[0]==2026 and k[-1]=='REG' and 1<=k[1]<=6,'only admitted2026W1-6')
            transitions[o[2],a['state']]+=1
            changed+=o[2]!=a['state'] or o[1]!=a['value']
        if o[1] is not None:require(a['value']==o[1],'prior numeric value unchanged')
        if numeric(a):numeric_counts[k[0]]+=1
        season_states[k[0]][a['state']]+=1
    require(sum(1 for k in after if k[0]==2026)==2117,'full2026 population')
    require(summary['newly_qualified_or_state_changed_2026_rows']==changed,'state-change count')
    expected=[{'before':k[0],'after':k[1],'n':v} for k,v in sorted(transitions.items())]
    require(expected==summary['transitions']==new['bridge']['transitions'],'exact transitions')
    for year in (2024,2025,2026):
        s=summary['seasons'][str(year)]
        require(s['planned']==sum(v for v in season_states[year].values()) and s['numeric_after']==numeric_counts[year] and s['states_after']==dict(season_states[year]),'season total/state arithmetic')
    for r in new['bridge']['rare_manifest']:rare_check(r)
    require(summary['predictive_population_admissible'] is False and summary['fits']==summary['forecasts']==summary['accuracy_comparisons']==0,'labels not predictive validation')
    use={'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-start,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024}
    require(use['CPU_seconds']<=15 and use['wall_seconds']<=30 and use['RSS_bytes']<=268435456,'finite acceptance resource caps')
    result={'schema_version':'week8-chart-bridge-independent-acceptance-v1','state':'PASS_LABEL_ARITHMETIC_AND_FULL_POPULATION_ONLY','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'plan_sha256':sha(raw),'checker_sha256':sha(Path(__file__).read_bytes()),'checks':checks,'labels_checked':14160,'numeric_checked':sum(numeric_counts.values()),'numeric_by_season':dict(numeric_counts),'state_changes_2026':changed,'rare_events_independently_reconciled':len(new['bridge']['rare_manifest']),'resources':use,'new_fits_forecasts_accuracy_HTTP_original_source_table_decodes':0,'original_PBP_game_census':'not reread; source runner evidence only','offhost_restore':'UNPROVEN','new_live_use':False}
    require(not OUTPUT.exists(),'one fresh metadata acceptance receipt')
    body=(json.dumps(result,indent=2,sort_keys=True)+'\n').encode();require(len(body)<=32768,'metadata cap');OUTPUT.write_bytes(body)
    print(json.dumps({'receipt':str(OUTPUT),'sha256':sha(body),'result':result}))
finally:signal.setitimer(signal.ITIMER_REAL,0)
