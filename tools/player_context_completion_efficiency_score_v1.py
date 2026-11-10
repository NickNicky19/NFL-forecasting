"""Score a completed frozen efficiency wave with C's pinned common evaluator.

No fit, model loading, feature construction, inference or network collection.
Requires a later root-published exact scoring GO and completed execution receipt.
W8 saved website thresholds are reference diagnostics unless separately qualified.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import datetime
from decimal import Decimal
import gzip
import hashlib
import importlib
import io
import json
import lzma
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
VERSION = 'A-efficiency-saved-vector-scoring-v1'
ASSIGNMENT = 'PLAYER-CONTEXT-COMPLETION-DECISION-01'
OUT = ROOT / 'reports/abc-championship/player-context-completion-decision-01'
NEW = ['D0_UNCHANGED_HGB_MAE', 'D1_HGB_RAW_CONDITIONAL_PROFILE',
       'S0_UNCONDITIONAL_OWN_YPC_FIXED_N', 'S1_CONDITIONAL_EFFICIENCY_FIXED_N']
SAVED_PRODUCTS = [('CATBOOST_MEDIUM', 'median_objective_point'),
    ('EQUAL_CDF_CAT_HGB_POINT', 'empirical_point_blend'), ('HGB_MAE_DIRECT', 'mae_objective_point'),
    ('LEAF_CDF', 'mean'), ('LEAF_CDF', 'median'), ('RESPONSE_CDF', 'mean'), ('RESPONSE_CDF', 'median')]
SAVED = ['SAVED_' + m + '__' + p for m,p in SAVED_PRODUCTS]
CONSTANTS = ['ALWAYS_OVER', 'ALWAYS_UNDER']
CANDIDATES = NEW + SAVED + CONSTANTS
PAIRS = [[NEW[i], NEW[j]] for i in range(4) for j in range(i+1,4)] + [[a,b] for a in NEW for b in SAVED+CONSTANTS]
KEY = ['season', 'week', 'game_id', 'player_id']
CONTEXT = ['team', 'opponent', 'position', 'kickoff_utc', 'cutoff_utc']
PINS = {'A_offers': 'f224f17930e8da7ed5683808de3339d9656cc4b71edb0deefcfb9c48dfd82ffb',
    'A_labels': '61da98ad90542b07c6c6664b674086ba4f9474e597325aba62dec44bb2fa72f5',
    'A_saved': '753970f359a5089286dde4c7ace6eeeb02c82b59eed07a50fd8ecc797eec8c33',
    'A_saved_member': '7d849d60902a2aa0a4922dd1ba0d09d4e0a21290cb5121e48279c6f54349e23f',
    'W8_sources': '6290b6a501ac5adf33ce693c2c4dc92d5f371ffdc3e6c6ba1da83ca6d1b623c5',
    'W8_graded': 'be9c13b0f42f5e164b29d00cce69fbe1c30acce703d1b33a8103a057888ac2c1',
    'W8_overlay': '2f8df2a10dcbba9074a04e9d2477fb76490311e2fedcbf70fa54c17dfec1f5fa',
    'W8_feature_identity': '5450041c91f3c5dce3a4078c81b861f388e4682dd5cc57d3f1e6b250338f5b0e'}
C_PINS = {'abc_championship_v2.py': '2ba450f91bb5fac869ce3adde031099390ec70408a91204653869032b49b2bce',
    'actual_accuracy_v6.py': '92260304be31b0fbee42faa3ab78616f77c3791bd2613edb9d322f9bbf29aa2a',
    'selection.py': 'ba3cd2d5c33eb05f3c07e8f2674f6d51b51694c8fd722f8eaba5db089907997f',
    'contracts_v2.py': '9321d35ba5c7d7af59684784cbf92322849e968097ab7c01a2990493d061a77a',
    'actual_offers_v4.py': '39b187dbdf750b5cdd7b26197bc2c56240ce5aab2bef67392fc77c1a8938e186',
    'offer_validator_v2.py': 'a24a51491c061d7825a31a98fdfdf57358a666dd9b850e0f1b117cc776b0ac51'}
PHASE = 'NOT_STARTED'


def enc(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode()


def sha(body):
    return hashlib.sha256(body).hexdigest()


def check(value, message):
    if not value:
        raise ValueError(message)


def finite(value):
    return type(value) in [int, float] and math.isfinite(value)


def norm(value):
    value = str(value) if value is not None else ''
    return value[:-2] if value.endswith('.0') else value


def team(value):
    return {'LA':'LAR', 'WSH':'WAS', 'OAK':'LV', 'SD':'LAC', 'STL':'LAR'}.get(value,value)


def read_ref(ref):
    body = Path(ref['path']).read_bytes()
    check(sha(body) == ref['sha256'] and len(body) == ref['bytes'], 'bound source bytes changed')
    return body


def clock(value, pd):
    x = pd.Timestamp(value)
    return x if x is not pd.NaT and x.tzinfo is not None else None


def key(row):
    return (int(row['season']), int(row['week']), str(row['game_id']), str(row['player_id']))


def fallback(row):
    if 'fallback' not in row:
        return 'UNRECORDED'
    value = row['fallback']
    return 'LEARNED_EXPLICIT_NO_FALLBACK' if value in [None, '', False, 'none'] else 'FALLBACK:' + str(value)


def compatible(forecast, query, pd):
    if forecast is None:
        return 'MISSING_FROZEN_FORECAST'
    for f in ['team', 'opponent', 'position']:
        if str(forecast.get(f)) != str(query.get(f)):
            return 'EXACT_' + f.upper() + '_MISMATCH'
    for f in ['kickoff_utc', 'cutoff_utc']:
        a,b = clock(forecast.get(f),pd), clock(query.get(f),pd)
        if a is None or b is None or a != b:
            return 'EXACT_' + f.upper() + '_MISMATCH_OR_UNKNOWN'
    return None


def point_side(point, line):
    if not finite(point):
        return None
    a,b = Decimal(str(point)),Decimal(str(line))
    return 'OVER' if a>b else 'UNDER' if a<b else 'ABSTAIN'


def canonical_row(query, candidate, point, reason, label, source, line, opportunity, common, fallback_state):
    appearance = label['appearance']
    selected = candidate.removeprefix('ALWAYS_') if candidate in CONSTANTS else point_side(point,line)
    initial = ('UNAVAILABLE_FORECAST' if selected is None else 'ABSTAIN' if selected=='ABSTAIN' else
        'DNP' if appearance=='DNP' else 'PENDING' if appearance=='PENDING' else
        'UNKNOWN_PARTICIPATION' if appearance!='PLAYED' else 'MISSING_ACTUAL' if label['actual'] is None else 'READY_FOR_CANONICAL_STATUS')
    row = dict(season=int(query['season']),week=int(query['week']),game_id=str(query['game_id']),player_id=str(query['player_id']),
        candidate_id=candidate,category='rush_yd',point=point,actual=label['actual'],appearance=appearance,
        selected_side=selected,line=float(line),comparator='STRICT_OVER_UNDER',status=initial,
        opportunity_key=opportunity,source_panel=source,unavailability_reason=reason,fallback_state=fallback_state)
    row['status'] = common.status(row)
    return row


def numerical(rows):
    rr = [r for r in rows if finite(r['point']) and r['actual'] is not None]
    errors = [r['point']-r['actual'] for r in rr]
    n = len(errors)
    ordered = sorted(abs(x) for x in errors)
    return dict(intended=len(rows),available=sum(finite(r['point']) for r in rows),scored=n,
        unavailable=sum(not finite(r['point']) for r in rows),unknown_outcome=sum(r['actual'] is None for r in rows),
        MAE=math.fsum(map(abs,errors))/n if n else None,MSE=math.fsum(x*x for x in errors)/n if n else None,
        RMSE=math.sqrt(math.fsum(x*x for x in errors)/n) if n else None,bias=math.fsum(errors)/n if n else None,
        absolute_error_p90=ordered[min(n-1,math.ceil(.9*n)-1)] if n else None,
        max_absolute_error=max(ordered) if n else None,
        fallback=dict(Counter(r['fallback_state'] for r in rows)),
        unavailability_reasons=dict(Counter(r['unavailability_reason'] for r in rows if r['unavailability_reason'])))


def block_interval(groups, np):
    if len(groups)<2:
        return None
    a = np.asarray([groups[k] for k in sorted(groups)],dtype=float)
    ix = np.random.default_rng(20261110).integers(0,len(a),(500,len(a)))
    samples = a[ix].sum(axis=1)
    return list(map(float,np.quantile(samples[:,0]/samples[:,1],[.025,.975])))


def paired(left, right, np, numeric_only=False):
    rm = {r['opportunity_key']:r for r in right}
    pp = [(r,rm[r['opportunity_key']]) for r in left if r['opportunity_key'] in rm]
    numeric = [(a,b) for a,b in pp if finite(a['point']) and finite(b['point']) and a['actual'] is not None and b['actual'] is not None]
    decided = [] if numeric_only else [(a,b) for a,b in pp if a['status'] in ['WIN','LOSS'] and b['status'] in ['WIN','LOSS']]
    def intervals(pairs, change):
        games = defaultdict(lambda:[0.,0.]); weeks = defaultdict(lambda:[0.,0.])
        for a,b in pairs:
            d = change(a,b)
            games[a['game_id']][0]+=d;games[a['game_id']][1]+=1
            weeks[(a['season'],a['week'])][0]+=d;weeks[(a['season'],a['week'])][1]+=1
        return dict(game_clusters=len(games),week_clusters=len(weeks),game_interval95=block_interval(games,np),week_interval95=block_interval(weeks,np))
    return dict(common_decided=len(decided),left_wins=sum(a['status']=='WIN' for a,b in decided),
        right_wins=sum(b['status']=='WIN' for a,b in decided),
        accuracy_change=(sum(int(a['status']=='WIN')-int(b['status']=='WIN') for a,b in decided)/len(decided)) if decided else None,
        side_disagreements=sum(a['selected_side']!=b['selected_side'] for a,b in decided),
        decision_uncertainty=intervals(decided,lambda a,b:int(a['status']=='WIN')-int(b['status']=='WIN')),
        common_numerical=len(numeric),MAE_change=math.fsum(abs(a['point']-a['actual'])-abs(b['point']-b['actual']) for a,b in numeric)/len(numeric) if numeric else None,
        MAE_change_uncertainty=intervals(numeric,lambda a,b:abs(a['point']-a['actual'])-abs(b['point']-b['actual'])),
        decided_mask_sha256=sha(enc(sorted(a['opportunity_key'] for a,b in decided))),
        numerical_mask_sha256=sha(enc(sorted(a['opportunity_key'] for a,b in numeric))))


def restore_w8(store, refs, pd):
    """Same frozen source-presence qualification as the prior Nov5/6 overlay."""
    old = store.outer.forward_root
    base = old/'research/week8-original-grade-v2-batch-20261102'
    def retained(path, expected, name):
        body=Path(path).read_bytes();check(sha(body)==expected,'original W8 source checksum differs')
        refs[name]={'path':str(path),'bytes':len(body),'sha256':expected}
        return body
    with zipfile.ZipFile(io.BytesIO(retained(base/'SOURCES.zip',PINS['W8_sources'],'W8_sources'))) as z:
        original=json.loads(z.read('archive_pre_first.bin'))
    with zipfile.ZipFile(io.BytesIO(retained(base/'A_LOCAL_WEEK8_REGRADING_V2_20261103.zip',PINS['W8_graded'],'W8_graded'))) as z:
        members={n:z.read(n) for n in z.namelist()}
    manifest=json.loads(members['MANIFEST.json'])
    for name,r in manifest.items():
        check(sha(members[name])==r['sha256'] and len(members[name])==r['bytes'],'W8 original member differs')
    grades=json.loads(gzip.decompress(members['GRADED_ROWS.json.gz']));report=json.loads(members['REPORT.json'])
    check(len(report['schedule'])==14 and all(g['final'] for g in report['schedule']),'frozen14game finality differs')
    overlay_path=old/'research/ABC-PREDICTIVE-IMPROVEMENT-01-A-runtime-v2/AUDIT_WEEK8_MEASUREMENT_OVERLAY_V1.json.gz'
    overlay=json.loads(gzip.decompress(retained(overlay_path,PINS['W8_overlay'],'W8_overlay')))
    check(overlay['source_archive']['sha256']==PINS['W8_graded'] and overlay['source_member']==manifest['GRADED_ROWS.json.gz'],'W8 qualification version differs')
    check(len(overlay['row_overlays']['numerical'])==len(grades['numerical']),'W8 overlay ordinal population differs')
    feature_ref=json.loads((ROOT/'config/category-topfive-matched12-inference-v1.json').read_bytes())['features']
    check(feature_ref['sha256']==PINS['W8_feature_identity'],'identity bridge source differs')
    refs['W8_feature_identity']=feature_ref
    roster=pd.read_parquet(io.BytesIO(read_ref(feature_ref)),columns=['sleeper_id','player_id'])
    players=defaultdict(set)
    for r in roster.itertuples():
        if pd.notna(r.sleeper_id) and pd.notna(r.player_id):players[norm(r.sleeper_id)].add(str(r.player_id))
    sched_ref=json.loads((ROOT/'config/category-topfive-matched12-primary-preparation-v1.json').read_bytes())['inputs']['schedule']
    refs['W8_schedule']=sched_ref
    schedule=list(csv.DictReader(io.StringIO(read_ref(sched_ref).decode())))
    games={norm(r['espn']):r for r in schedule if r['season']=='2026' and r['week']=='8' and r['game_type']=='REG' and r['espn']}
    rawstats={}
    for s in json.loads(members['sleeper_stats.json']):
        check(s['season'] in [2026,'2026'] and s['week']==8 and s['season_type']=='regular' and s['category']=='stat','W8 raw period differs')
        matches=[g['game_id'] for g in report['schedule'] if {team(g['home']),team(g['away'])}=={team(s['team']),team(s['opponent'])}]
        check(len(matches)==1,'W8 raw event ambiguous')
        k=(norm(s['player_id']),norm(matches[0]))
        check(k not in rawstats or rawstats[k]==s,'W8 raw duplicate conflict')
        rawstats[k]=s
    labels={}
    for k,s in rawstats.items():
        raw=s.get('stats');presence='MISSING_SOURCE_ROW' if not isinstance(raw,dict) else 'ABSENT_REQUIRED_COMPONENT' if 'rush_yd' not in raw else 'EXPLICIT_UNKNOWN' if not finite(raw['rush_yd']) else 'EXPLICIT_FINITE_REQUIRED_COMPONENTS'
        played=isinstance(raw,dict) and ((finite(raw.get('gp')) and raw['gp']>0) or (finite(raw.get('off_snp')) and raw['off_snp']>0))
        actual=float(raw['rush_yd']) if played and presence=='EXPLICIT_FINITE_REQUIRED_COMPONENTS' else None
        labels[k]=dict(actual=actual,appearance='PLAYED' if played else 'UNKNOWN',presence=presence)
    for i,r in enumerate(grades['numerical']):
        q=overlay['row_overlays']['numerical'][i]
        check(q['member_row']==i and q['original_measurement_state']==r['status'],'W8 overlay ordinal version differs')
        if r['category']!='rush_yd':continue
        lab=labels.get((norm(r['player_id']),norm(r['game_id'])),dict(actual=None,appearance='UNKNOWN',presence='MISSING_SOURCE_ROW'))
        check(q['source_presence']==lab['presence'] and (q['qualified_measurement_state']=='SUPPORTED')==(lab['actual'] is not None),'W8 frozen SUPPORTED qualification differs')
        check(lab['actual'] is None or r['actual']==lab['actual'],'W8 qualified actual conflict')
    canonical={};offered=[];source_queries=[];seen=set();threshold_exclusions=Counter()
    boardgames={norm(g['id']):g for g in original['games']}
    for p in original['players']:
        if p['pos']!='RB':continue
        sid,event=norm(p['id']),norm(p['game_id']);g=games.get(event);ids=players.get(sid,set())
        reason=None if g is not None and len(ids)==1 else 'UNAVAILABLE_CANONICAL_EVENT_OR_PLAYER'
        if g is not None:
            check({team(p['team']),team(p['opp'])}=={team(g['home_team']),team(g['away_team'])},'W8 reciprocal teams differ')
        query=dict(season=2026,week=8,game_id=g['game_id'] if g else 'UNMAPPED_EVENT:'+event,
            player_id=next(iter(ids)) if len(ids)==1 else 'UNMAPPED_SLEEPER:'+sid,team=team(p['team']),opponent=team(p['opp']),position='RB',
            kickoff_utc=boardgames[event]['kickoff'] if event in boardgames else None,cutoff_utc=original['saved_at'],identity_reason=reason)
        lab=labels.get((sid,event),dict(actual=None,appearance='UNKNOWN',presence='MISSING_SOURCE_ROW'))
        query['_label']=lab;query['_source_identity']=(sid,event)
        source_queries.append(query)
        if reason is None:
            check(key(query) not in canonical,'W8 canonical query ambiguous');canonical[key(query)]=query
        for prop in p['props']:
            if prop['key']!='rush_yd':continue
            if p.get('late'):
                threshold_exclusions['ORIGINAL_LATE_PLAYER_RUSH_YD_THRESHOLD']+=1;continue
            if prop.get('line_from') not in ['dk','sleeper']:
                why='GENERATED_OURS_REFERENCE_THRESHOLD' if prop.get('line_from')=='ours' else 'UNKNOWN_OR_UNAPPROVED_LINE_SOURCE'
                threshold_exclusions[why]+=1;continue
            if not finite(prop.get('line')):
                threshold_exclusions['NO_FINITE_ORIGINAL_RECORDED_RUSH_YD_THRESHOLD']+=1;continue
            # The stored source alias alone is not proof of an actual sportsbook quote.
            op=sha(enc([2026,8,event,sid,'rush_yd',prop.get('line_from'),str(prop['line'])]))
            check(op not in seen,'W8 primary threshold identity ambiguous');seen.add(op)
            offered.append(dict(query=query,line=float(prop['line']),opportunity=op,label=lab,
                source='W8_SITE_REFERENCE_THRESHOLD_DIAGNOSTIC',tier='SITE_REFERENCE_THRESHOLD_DIAGNOSTIC',original_side=prop.get('lean')))
    return source_queries,canonical,offered,dict(captured_at=original['saved_at'],final_games=14,qualification='FROZEN_NOV5_NOV6_EXPLICIT_METRIC_PRESENCE',
        threshold_exclusions=dict(threshold_exclusions),threshold_exclusion_scope='Original RB rush_yd props only; generated ours and unknown/unapproved source aliases excluded before comparison; broad numerical queries unchanged',
        actual_offered_line_state='NOT_ESTABLISHED; saved aliases/reference thresholds are not sportsbook evidence')


def run(args):
    global PHASE
    started,cpu=time.monotonic(),time.process_time()
    PHASE='REGISTRATION'
    raw=args.protocol.read_bytes();check(sha(raw)==args.protocol_sha256,'root scoring protocol changed')
    plan=json.loads(raw)
    check(plan.get('assignment_id')==ASSIGNMENT and plan.get('version')==VERSION and plan.get('registered_by')=='/root' and plan.get('state')=='ROOT_REGISTERED_EXECUTION_GO','published root scoring GO required')
    check(plan['candidate_ids']==CANDIDATES and plan['paired_candidate_ids']==PAIRS,'finite candidate/comparison order differs')
    check(plan['resources']['CPU_seconds']<=400 and plan['resources']['wall_seconds']<=900 and plan['resources']['RSS_bytes']<=3*1024**3,'finite scoring cap exceeded')
    check(0<plan['resources']['private_view_max_bytes']<=65536,'finite scoring view cap required')
    own=str(Path(__file__).resolve().relative_to(ROOT));check(own in plan['code_sha256'],'scorer is not hash-bound')
    for p,h in plan['code_sha256'].items():check(sha((ROOT/p).read_bytes())==h,'registered code changed')
    contract=read_ref(plan['scoring_contract']);check(json.loads(contract)['version']==VERSION,'original prefit scoring contract differs')
    receipt_raw=read_ref(plan['execution_receipt']);receipt=json.loads(receipt_raw)
    check(receipt['state']=='FROZEN_FORECASTS_COMPLETE_UNSCORED','completed frozen model-wave receipt required; no automatic recovery/refit')
    check(receipt['forecasts']['sha256']==plan['frozen_forecasts_sha256'],'frozen all-forecasts reference differs')
    for n in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[n]='1'
    resource.setrlimit(resource.RLIMIT_CPU,(plan['resources']['CPU_seconds'],plan['resources']['CPU_seconds']))
    resource.setrlimit(resource.RLIMIT_AS,(plan['resources']['RSS_bytes'],)*2)
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('registered scoring wall cap')))
    signal.alarm(plan['resources']['wall_seconds'])
    def offline(event,_args):
        if event in {'socket.connect','socket.connect_ex','socket.getaddrinfo'}:raise RuntimeError('saved forecast scoring is offline')
    sys.addaudithook(offline)
    import numpy as np
    import pandas as pd
    import pyarrow as pa
    pa.set_cpu_count(1);pa.set_io_thread_count(1);pa.set_memory_pool(pa.system_memory_pool())
    for name,h in C_PINS.items():check(sha((args.c_code_cache/name).read_bytes())==h,'pinned C evaluator changed')
    sys.path.insert(0,str(args.c_code_cache));common=importlib.import_module('abc_championship_v2')
    from nfl_lab import player_context_completion_storage_v1 as guard
    from tools import abc_a_dynamic_carry_wave_v1 as base
    PHASE='EXACT_FROZEN_FORECAST_READ'
    store=guard.CompletionStore(ROOT,Path(plan['allocation']['path']),plan['allocation']['sha256'],root_go=guard.GO)
    frozen=store.read(receipt['forecasts']['id'],receipt['forecasts']['sha256'])
    check(len(frozen)==receipt['forecasts']['bytes'],'frozen forecasts size differs')
    forecasts=json.loads(gzip.decompress(frozen));check(len(forecasts)==receipt['forecast_rows'],'frozen forecast row count differs')
    fm={};unexpected=set()
    for f in forecasts:
        check(f['target']=='rush_yd' and f['position']=='RB','frozen target/role differs')
        if f['arm'] not in NEW+SAVED:unexpected.add(f['arm']);continue
        k=(f['arm'],key(f));check(k not in fm,'frozen forecast identity ambiguous');fm[k]=f
    check(not unexpected,'unregistered saved forecast arm present')
    refs={};_,c,g,_=base.sources()
    for name,selector in [('A_offers','offers'),('A_labels','qualified_labels'),('A_saved','frozen_bundle')]:
        check(g[selector]['sha256']==PINS[name],'original A source selector differs');refs[name]=dict(g[selector])
    PHASE='QUALIFIED_OUTCOME_SOURCE_READ'
    with zipfile.ZipFile(io.BytesIO(read_ref(refs['A_offers']))) as z:offers=pd.read_parquet(io.BytesIO(z.read(refs['A_offers']['member'])))
    with zipfile.ZipFile(io.BytesIO(read_ref(refs['A_labels']))) as z:labels=pd.read_parquet(io.BytesIO(z.read(refs['A_labels']['member'])))
    with zipfile.ZipFile(io.BytesIO(read_ref(refs['A_saved']))) as z:
        member=z.read('FORECASTS.parquet');check(sha(member)==PINS['A_saved_member'],'original control member differs')
        controls=pd.read_parquet(io.BytesIO(member))
    controls=controls.loc[controls.target.eq('rush_yd') & controls.position.eq('RB')]
    saved_lookup={}
    for r in controls.to_dict('records'):
        arm='SAVED_'+r['method']+'__'+r['product']
        if arm in SAVED:saved_lookup[(arm,key(r))]=r
    for (arm,k),f in fm.items():
        source=saved_lookup.get((arm,k)) if arm in SAVED else saved_lookup.get(('SAVED_HGB_MAE_DIRECT__mae_objective_point',k)) if arm==NEW[0] and k[0]==2026 and k[1]<=7 else None
        if source is not None:
            check(float(source['prediction'])==f['point'],'frozen saved control point changed')
            if 'fallback' in source:f['fallback']=None if pd.isna(source['fallback']) else source['fallback']
    labelmap={}
    target=labels.loc[labels.target.eq('rush_yd') & labels.season.eq(2026) & labels.week.between(1,7)]
    check(not target.duplicated(KEY).any(),'qualified label identity ambiguous')
    for r in target.to_dict('records'):
        state=str(r.get('participation_state','unknown')).lower()
        appearance='PENDING' if r.get('outcome_state')=='pending' else 'DNP' if state=='dnp' else 'PLAYED' if state=='played' else 'UNKNOWN'
        supported=appearance=='PLAYED' and finite(r.get('actual')) and r.get('label_reason') in ['EXPLICIT_REPORTED_ZERO','EXPLICIT_REPORTED_VALUE'] and bool(r.get('participation_evidence'))
        labelmap[key(r)]=dict(actual=float(r['actual']) if supported else None,appearance=appearance,presence=r.get('label_reason'))
    for i,ref in enumerate(c['history_sources']):
        refs['history_'+str(i)]=dict(ref)
        h=pd.read_parquet(io.BytesIO(read_ref(ref)))
        h=h.loc[h.season.eq(2025) & h.week.between(1,8) & h.position.eq('RB')]
        for r in h.to_dict('records'):
            k=key(r);check(k not in labelmap,'historical outcome source identity ambiguous')
            state=str(r.get('participation_state','unknown')).lower()
            # Official stat-event presence plus explicit metric. Snap-only
            # participation never manufactures rush yards, including zeros.
            supported=state=='played' and r.get('stats_observed') is True and finite(r.get('rush_yd'))
            labelmap[k]=dict(actual=float(r['rush_yd']) if supported else None,
                appearance='DNP' if state=='dnp' else 'PLAYED' if state=='played' else 'UNKNOWN',
                presence='EXPLICIT_FINITE_OFFICIAL_STAT_EVENT' if supported else 'METRIC_OR_OFFICIAL_EVENT_UNQUALIFIED')
    w8queries,w8canonical,w8offers,w8meta=restore_w8(store,refs,pd)
    for k,q in w8canonical.items():labelmap[k]=q['_label']
    source_hashes={name:ref['sha256'] for name,ref in refs.items()}
    check(source_hashes==plan['source_sha256'],'registered complete outcome/source bindings differ')
    artifacts={r['id']:r for r in receipt['artifacts']}
    queries={}
    query_refs=[]
    for year in [2025,2026]:
        ref=artifacts['QUERY_IDENTITIES_'+str(year)+'.json.gz'];query_refs.append(ref)
        qrows=json.loads(gzip.decompress(store.read(ref['id'],ref['sha256'])))
        for q in qrows:
            k=key(q);check(k not in queries,'intended query identity ambiguous');queries[k]=q
    # Keep the two declared W8 unavailable ID profiles in the intended broad
    # population, without inventing a GSIS identity or a forecast value.
    for q in w8queries:
        if q['identity_reason'] is not None:queries[key(q)]=q
    check(len(w8queries)==receipt['week8']['captured_rb_rows'],'original W8 broad query population differs')
    for k,q in w8canonical.items():
        check(k in queries and compatible(queries[k],q,pd) is None,'frozen W8 query/source identity differs')
    broad={cid:[] for cid in CANDIDATES};board={cid:[] for cid in CANDIDATES};memberships=[]
    unknown=dict(actual=None,appearance='UNKNOWN',presence='NO_QUALIFIED_LABEL')
    def resolve(cid,q):
        if cid in CONSTANTS:return None,None,'CONSTANT_NOT_NUMERICAL'
        if cid in SAVED and (int(q['season'])!=2026 or not 1<=int(q['week'])<=7):
            return None,'OUTSIDE_RETAINED_SAVED_2026_W1_W7_SOURCE_SCOPE','OUTSIDE_SOURCE_SCOPE'
        if q.get('identity_reason') is not None:
            return None,str(q['identity_reason']),'UNAVAILABLE_CANONICAL_IDENTITY'
        f=fm.get((cid,key(q)));why=compatible(f,q,pd)
        point=float(f['point']) if why is None and finite(f.get('point')) else None
        if why is None and point is None:why='FROZEN_POINT_UNAVAILABLE'
        return point,why,fallback(f) if f is not None else 'UNAVAILABLE_FORECAST'
    for k,q in queries.items():
        label=labelmap.get(k,q.get('_label',unknown));op=sha(enc(list(k)))
        for cid in CANDIDATES:
            point,why,fb=resolve(cid,q)
            broad[cid].append(dict(season=k[0],week=k[1],game_id=k[2],player_id=k[3],opportunity_key=op,
                point=point,actual=label['actual'],appearance=label['appearance'],unavailability_reason=why,fallback_state=fb))
    aoffers=offers.loc[offers.target.eq('rush_yd') & offers.position.eq('RB') & offers.season.eq(2026) & offers.week.between(1,7)]
    check(not aoffers.duplicated(['opportunity_key']).any(),'original A offer identity ambiguous')
    actual_panels=set(plan['actual_recorded_source_panels'])
    offer_specs=[]
    for o in aoffers.to_dict('records'):
        source=str(o['source_stream']);tier='ACTUAL_RECORDED_QUOTE_TIMING_UNVERIFIED' if source in actual_panels else 'SOURCE_OFFER_STATUS_UNVERIFIED_DIAGNOSTIC'
        offer_specs.append(dict(query=o,line=float(o['line']),opportunity=str(o['opportunity_key']),label=labelmap.get(key(o),unknown),source=source,tier=tier,original_side=None))
    offer_specs.extend(w8offers)
    PHASE='CANONICAL_POINT_REPLAY'
    for o in offer_specs:
        q=o['query'];label=o['label']
        for cid in CANDIDATES:
            point,why,fb=resolve(cid,q)
            row=canonical_row(q,cid,point,why,label,o['source'],o['line'],o['opportunity'],common,fb)
            row['evidence_tier']=o['tier'];board[cid].append(row)
            memberships.append([cid,o['opportunity'],point,label['actual'],label['appearance'],row['selected_side'],row['status'],why,fb])
    core_broad={r['opportunity_key'] for r in broad[NEW[0]] if finite(r['point'])}
    core_board={r['opportunity_key'] for r in board[NEW[0]] if r['selected_side'] is not None}
    for cid in NEW[1:]:
        core_broad&={r['opportunity_key'] for r in broad[cid] if finite(r['point'])}
        core_board&={r['opportunity_key'] for r in board[cid] if r['selected_side'] is not None}
    periods=[(2025,'W1_W8',list(range(1,9))), (2026,'W1_W7',list(range(1,8))), (2026,'W8_SEPARATE',[8]), (2026,'W1_W8',list(range(1,9)))]
    summaries=[];pairs=[]
    for year,period,weeks in periods:
        for view in ['FULL_INTENDED','STABLE_NEW_FOUR_CORE']:
            for cid in CANDIDATES:
                nr=[r for r in broad[cid] if r['season']==year and r['week'] in weeks and (view=='FULL_INTENDED' or r['opportunity_key'] in core_broad)]
                summaries.append(dict(season=year,period=period,view=view,candidate_id=cid,population='BROAD_DECLARED_QUERIES',numerical=numerical(nr)))
                br=[r for r in board[cid] if r['season']==year and r['week'] in weeks and (view=='FULL_INTENDED' or r['opportunity_key'] in core_board)]
                panels=['ALL']+sorted({r['source_panel'] for r in br})
                for panel in panels:
                    for week in ['ALL']+weeks:
                        rr=[r for r in br if (panel=='ALL' or r['source_panel']==panel) and (week=='ALL' or r['week']==week)]
                        actual_weeks=sorted({r['week'] for r in rr if r['status'] in ['WIN','LOSS','PUSH'] and r['evidence_tier']=='ACTUAL_RECORDED_QUOTE_TIMING_UNVERIFIED'})
                        summaries.append(dict(season=year,period=period,week_view=week,view=view,candidate_id=cid,source_panel=panel,
                            population='ORIGINAL_RETAINED_THRESHOLD_BOARD',**common.summary(rr),numerical=numerical(rr),
                            evidence_tiers=dict(Counter(r['evidence_tier'] for r in rr)),
                            actual_recorded_line_scored_weeks=actual_weeks,diagnostic_scored_weeks=sorted({r['week'] for r in rr if r['status'] in ['WIN','LOSS','PUSH']}),
                            five_actual_week_duration_floor=len(actual_weeks)>=5,admission='DURATION_ONLY_NOT_PRIMARY_ADMISSION',
                            Brier=None,Brier_state='NOT_APPLICABLE_POINT_ONLY_NO_FULL_GAME_STAT_LAW'))
            for left,right in PAIRS:
                for population,data,core in [('BROAD_DECLARED_QUERIES',broad,core_broad),('ORIGINAL_RETAINED_THRESHOLD_BOARD',board,core_board)]:
                    subsets={cid:[r for r in data[cid] if r['season']==year and r['week'] in weeks and (view=='FULL_INTENDED' or r['opportunity_key'] in core)] for cid in [left,right]}
                    panels=['ALL'] if population=='BROAD_DECLARED_QUERIES' else ['ALL']+sorted({r['source_panel'] for r in subsets[left]+subsets[right]})
                    for panel in panels:
                        lr=[r for r in subsets[left] if panel=='ALL' or r['source_panel']==panel]
                        rr=[r for r in subsets[right] if panel=='ALL' or r['source_panel']==panel]
                        pairs.append(dict(season=year,period=period,view=view,population=population,source_panel=panel,left=left,right=right,
                            **paired(lr,rr,np,numeric_only=population=='BROAD_DECLARED_QUERIES')))
    # Per-week broad numerical coverage is independent of offered-player masks.
    for year in [2025,2026]:
        for week in range(1,9):
            for cid in CANDIDATES:
                rr=[r for r in broad[cid] if r['season']==year and r['week']==week]
                summaries.append(dict(season=year,period='SINGLE_WEEK',week_view=week,view='FULL_INTENDED',candidate_id=cid,
                    population='BROAD_DECLARED_QUERIES',numerical=numerical(rr)))
    view=dict(version=VERSION,protocol_sha256=args.protocol_sha256,source_refs=refs,
        execution_receipt_sha256=sha(receipt_raw),frozen_forecasts=receipt['forecasts'],query_references=query_refs,
        candidate_ids=CANDIDATES,paired_candidate_ids=PAIRS,source_forecast_member_sha256=PINS['A_saved_member'],
        selector='Exact frozen intended RB queries plus two source-ID-unavailable W8 profiles; g original rush_yd RB offersW1-7 and original W8 rush_yd reference props; no threshold substitution',
        labels='g qualified explicit rush_yd outcomes2026W1-7;2025played+stats_observed+finite retained rush_yd; frozen W8 explicitmetric GP/offense-snap and exact Nov5/6 qualification parity',
        W8_actual_offer_policy='Reference diagnostic only; no sportsbook quote proof from line_from alias; contributes no actual-line week',
        full_broad_mask_sha256=sha(enc(sorted(r['opportunity_key'] for r in broad[NEW[0]]))),
        core_broad_mask_sha256=sha(enc(sorted(core_broad))),core_board_mask_sha256=sha(enc(sorted(core_board))),
        decision_membership_sha256=sha(enc(sorted(memberships))),
        reconstruction='Original hash-bound source bytes, frozen rows, queries, label presence overlays and this code deterministically regenerate every point/side/grade. No model loading/inference needed.',
        no_new_fits_or_inference=True)
    payload=lzma.compress(enc(view),preset=6)
    check(len(payload)<=plan['resources']['private_view_max_bytes'],'lossless view exceeds registered64KiBcap')
    PHASE='GUARDED_SCORE_VIEW_PERSISTENCE'
    viewref=store.put('EFFICIENCY_SCORING_VIEW_V1.json.xz',payload)
    check(store.read(viewref['id'],viewref['sha256'])==payload,'score view readback differs')
    public=dict(version=VERSION,state='FROZEN_POINT_SCORING_COMPLETE',protocol_sha256=args.protocol_sha256,
        execution_receipt_sha256=sha(receipt_raw),frozen_forecasts=receipt['forecasts'],source_sha256=source_hashes,
        candidate_ids=CANDIDATES,summaries=summaries,paired=pairs,private_scorecard_view=viewref,
        W8_source_and_qualification=w8meta,
        original_archive_choices=dict(scope='Frozen original website lean fields retained in source; no reissued recommendations or actual-prop qualification',
            W8_source_side_counts=dict(Counter(str(o['original_side']) for o in w8offers))),
        core_masks=dict(broad=sha(enc(sorted(core_broad))),board=sha(enc(sorted(core_board)))),
        uncertainty='Nominal game/week block500 seed20261110; pinned canonical summaries retain own intervals. Few exposed periods, repeated players and multiplicity unadjusted.',
        probability='Full-game rush-yard Brier/EV/confidence NOT_APPLICABLE: point-only arms. Per-carry EPA-positive is a different diagnostic.',
        limitations=['W8savedthresholds reference diagnostics only, not proven actual sportsbook offers or an added actualpropweek.',
            'A/B/newarm complete systems have different input/learner/history contracts; no originalR0 claim or isolated mechanism attribution.',
            'Unrecorded fallback remains UNRECORDED. Missing metric/source/participation never becomes zero. Signed rush yards remain signed.',
            'No2025actual-offer panel or W8saved seven-control vectors fabricated. Five distinct actualweeks is duration floor only.'],
        counts=dict(new_fits=0,new_inference=0,new_source_HTTP=0,production_writes=0),storage=store.checkpoint(),
        resources=dict(CPU_seconds=time.process_time()-cpu,wall_seconds=time.monotonic()-started,RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024))
    with args.output.open('xb') as f:f.write(enc(public));f.flush();os.fsync(f.fileno())
    signal.alarm(0)
    print(json.dumps(dict(state=public['state'],output=str(args.output),private_view=viewref,new_fits=0,new_inference=0)))


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--protocol',type=Path,required=True);ap.add_argument('--protocol-sha256',required=True)
    ap.add_argument('--output',type=Path,default=OUT/'EFFICIENCY_SCORES_V1.json');ap.add_argument('--c-code-cache',type=Path,default=Path('/tmp/acceptance-c-review/src'))
    args=ap.parse_args();check(not args.output.exists(),'immutable scoring result already exists')
    try:run(args)
    except BaseException as e:
        signal.alarm(0)
        failure=dict(version=VERSION,state='SCORING_FAILED_NO_REFIT_OR_INFERENCE',phase=PHASE,error_type=type(e).__name__,
            protocol_sha256=args.protocol_sha256,new_fits=0,new_inference=0,automatic_retry=False)
        p=args.output.with_name('EFFICIENCY_SCORING_FAILURE_'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json')
        with p.open('xb') as f:f.write(enc(failure))
        print(json.dumps(failure));raise SystemExit(1) from None


if __name__=='__main__':main()
