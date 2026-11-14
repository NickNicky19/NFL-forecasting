"""Append one explicitly reviewed event identity, preserving both original clocks.

No source choice, threshold, model, forecast, side, selector or grade is changed.
The previous partial source reconstruction remains immutable evidence.
"""
from pathlib import Path
import argparse, collections, copy, datetime, gzip, hashlib, json, os, resource, signal, sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.w1w9_source_cache_v1 import original
from tools.w1w9_retained_offer_panel_v1 import qualified_actual,stamp,fingerprint,encoded


def sha(body):return hashlib.sha256(body).hexdigest()
def doc(ref):
    b=original(ref)
    return json.loads(gzip.decompress(b) if b.startswith(b'\x1f\x8b') else b)
def write(path,body):
    with path.open('xb')as h:h.write(body);h.flush();os.fsync(h.fileno())


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--plan',type=Path,required=True)
    ap.add_argument('--plan-sha256',required=True);ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--receipt',type=Path,required=True);a=ap.parse_args();raw=a.plan.read_bytes()
    assert sha(raw)==a.plan_sha256
    resource.setrlimit(resource.RLIMIT_CPU,(90,120));resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,)*2)
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('Bounded identity admission')));signal.alarm(160)
    def offline(event,_):
        if event in ['socket.connect','socket.connect_ex','socket.getaddrinfo']:raise RuntimeError('Offline identity admission only')
    sys.addaudithook(offline)
    p=json.loads(raw);assert p['state']=='ROOT_ONE_EVENT_DUAL_CLOCK_IDENTITY_ADMISSION' and p['registered_by']=='/root'
    assert sha(Path(__file__).read_bytes())==p['code_sha256']
    proof=doc(p['served_metadata']);assert p['served_metadata']['sha256']=='631871255e34241ef907ba63c18ee8c7fc77f3dffd3f0c964bf8c15038bdad54'
    found=[]
    def walk(x):
        if isinstance(x,dict):
            if str(x.get('id'))=='401873047':found.append(x)
            for v in x.values():walk(v)
        elif isinstance(x,list):
            for v in x:walk(v)
    walk(proof);assert len(found)==1 and found[0]['away']=='LV' and found[0]['home']=='SF'
    source_clock=stamp(found[0]['kickoff']);canonical_clock=stamp('2026-11-08T21:05:00+00:00')
    assert source_clock==stamp('2026-11-08T21:25:00+00:00') and (source_clock-canonical_clock).total_seconds()==1200
    previous=doc(p['prior_panel']);assert previous['state']=='PARTIAL_SOURCE_OR_IDENTITY_DEPENDENCY_BLOCKED'
    assert p['prior_panel']['sha256']=='d0dfb2b902bd9c357d76e9ceacd019cc48ad4b2cbdbcfcad02d5ab36cc8e15b9'
    assert p['football']['original_sha256']==previous['football_source_sha256']=='45aaab99d41f2e2643066c001355b26430f55dca06e7c7e366eace252f2e021b'
    result=copy.deepcopy(previous);rows=result['rows'];target=[r for r in rows if r['week']==9 and r['source_game_id']=='401873047']
    assert len(target)==2 and all(r['game_id'] is None and r['identity_state']=='EXACT_SOURCE_ID_BINDING' for r in target)
    football=doc(p['football']);games={r['game_id'] for r in football if r['season']==2026 and r['week']==9 and {r['team'],r['opponent']}=={'LV','SF'}}
    assert games=={'2026_09_LV_SF'}
    eligible=[r for r in football if r['season']==2026 and r['week']==9]
    labels={(r['game_id'],r['player_id']):r for r in eligible};assert len(labels)==len(eligible)
    players={r['player_id'] for r in target}
    untouched=[encoded(r)for r in rows if r not in target]
    for row in target:
        label=labels.get(('2026_09_LV_SF',row['player_id']));assert label is not None
        assert stamp(label['kickoff'])==canonical_clock and {label['team'],label['opponent']}=={'LV','SF'}
        assert stamp(row['kickoff_utc'])==source_clock and row['source_head']=='fe369c7462e4e4f290727b2d03b696d28ef5454b'
        assert stamp(row['source_server_clock'])<=canonical_clock-datetime.timedelta(minutes=90)
        row['source_game_kickoff_utc']=row['kickoff_utc']
        row['game_id']='2026_09_LV_SF';row['kickoff_utc']=canonical_clock.isoformat();row['cutoff_utc']=canonical_clock.isoformat()
        row['canonical_forecast_query_kickoff_utc']=canonical_clock.isoformat();row['source_clock_discrepancy_seconds']=1200
        row['canonical_T90_deadline']=(canonical_clock-datetime.timedelta(minutes=90)).isoformat()
        row['source_game_identity_state']='EXACT_PUBLIC_EVENT_WEEK_OPPONENTS_DUAL_CLOCK_ADMITTED'
        row['independent_game_identity_state']='EXPLICIT_SOURCE_QUERY_CLOCK_DISCREPANCY_PRESERVED'
        row['actual'],row['appearance'],row['label_reason']=qualified_actual(label,row,canonical_clock)
    assert untouched==[encoded(r)for r in rows if r not in target]
    keys=result['source_CMP_ATT_identities']['9'];changed=0
    for row in keys:
        if row['game_id'] is None and row['player_id'] in players:
            assert row['source_head']=='fe369c7462e4e4f290727b2d03b696d28ef5454b'
            row['game_id']='2026_09_LV_SF';changed+=1
    assert changed==4
    actual=fingerprint(keys);assert actual=='dbdbaf111852cd1d2421c24e3425ca9632c9b65954aa0bf3aebafdb40ab4159d'
    cov=next(x for x in result['coverage']if x['week']==9);rr=[x for x in rows if x['week']==9]
    cov.update(actual_native_CMP_ATT_identity_sha256=actual,native_identity_parity=True,
        canonical_games=len({x['game_id']for x in rr}),appearance_states=dict(collections.Counter(x['appearance']for x in rr)),
        outcome_states=dict(collections.Counter(x['label_reason']for x in rr)),
        independent_game_identity_states=dict(collections.Counter(x.get('independent_game_identity_state',x.get('source_game_identity_state','UNKNOWN'))for x in rr)),
        explicit_dual_clock_offers=2)
    assert all(x['native_identity_parity'] and x['source_CMP_rows']==x['expected_CMP'] and not x['missing_lines']for x in result['coverage'])
    result.update(state='PASS_EXACT_NATIVE_SOURCE_MEMBERSHIP_RECONSTRUCTION',
        source_clock_admission={'state':'ONE_EVENT_DUAL_CLOCK_DIAGNOSTIC_ONLY','event':'401873047',
            'canonical_game':'2026_09_LV_SF','source_kickoff_utc':source_clock.isoformat(),
            'forecast_query_kickoff_utc':canonical_clock.isoformat(),'source_clock_not_replaced':True,
            'model_forecast_clock_not_changed':True,'thresholds_and_source_choice_unchanged':True,
            'historical_quote_availability':'UNVERIFIED','prior_panel_sha256':p['prior_panel']['sha256'],
            'served_metadata_sha256':p['served_metadata']['sha256'],'native_full_membership_hash_verified':actual})
    body=gzip.compress(encoded(result),mtime=0);assert len(body)<2*1024**2;write(a.output,body)
    public={'state':result['state'],'scoped_change':result['source_clock_admission'],'CMP_offers':len(rows),
        'qualified_count':sum(r['actual']is not None for r in rows),'unchanged_other_CMP_rows':len(untouched),
        'new_scores':0,'new_fits':0,'source_GETs':0,'private_bytes':len(body),'private_sha256':sha(body)}
    write(a.receipt,encoded(public));print(json.dumps(public))


if __name__=='__main__':main()
