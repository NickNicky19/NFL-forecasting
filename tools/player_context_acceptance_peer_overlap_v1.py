"""A-owned zero-refit owner-local replay of retained C points on A's rec board.

Run only after the integrator publishes the bound acceptance registration.
No model/source acquisition, C mutation, original-selection or issuance claim.
"""
from __future__ import annotations

import argparse
import collections
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
VERSION = 'PLAYER-CONTEXT-ACCEPTANCE-01-A-peer-overlap-v1'
C_COMMIT = 'fa503c1e1a9993e655a905195ce428edf630add5'
C_ROWS_SHA = '398957af85dbd55444a88725397b91060599ebb6e008771f35a9399d8f4af4c8'
C_FEATURES_SHA = '63f9853f19042bb3e4af691ce46001920d9df28830d1c6a34abfb5f1eab75ed0'
ALLOCATION = 'f123cd5ffd6f4a204a76c68bf63817cce63cecd7021543a23503d0233cc3eb26'
EVIDENCE = 'TIMING_UNVERIFIED_ACTUAL_LINE_DIAGNOSTIC;CURRENT_REVISED_7DAY_RECONSTRUCTION;EXPOSED_DEVELOPMENT'
PREFIX = 'C::PLAYER-CONTEXT-MATCHUP-01::v1.1::'
PRODUCTS = [(m, p) for m in ['P1', 'P2'] for p in ['mean', 'median']]
PRIVATE_HARD_CAP = 60_000
OUT = ROOT/'reports/abc-championship/player-context-acceptance-01'
STATE = {'phase':'NOT_STARTED'}
POINT_TYPES = {'mean':'POISSONREGRESSOR_CONDITIONAL_EXPECTED_MEAN',
               'median':'LOWER_MEDIAN_OF_SAME_POISSON_LAW'}


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def sha(value):
    return hashlib.sha256(value).hexdigest()


def finite(value):
    return value is not None and isinstance(value, (int, float)) and math.isfinite(value)


def pin(path, expected):
    body = Path(path).read_bytes()
    if sha(body) != expected:
        raise ValueError('public retained artifact hash mismatch')
    return body


def independent_grade(row):
    if row['selected_side'] is None:
        return 'UNAVAILABLE_FORECAST'
    if row['selected_side'] == 'ABSTAIN':
        return 'ABSTAIN'
    if row['appearance'] != 'PLAYED':
        return {'DNP': 'DNP', 'PENDING': 'PENDING'}.get(row['appearance'], 'UNKNOWN_PARTICIPATION')
    if row['actual'] is None:
        return 'MISSING_ACTUAL'
    actual, line = Decimal(str(row['actual'])), Decimal(str(row['line']))
    if actual == line:
        return 'PUSH'
    return 'WIN' if ((actual > line) == (row['selected_side'] == 'OVER')) else 'LOSS'


def point_side(point, line):
    if not finite(point):
        return None
    a, b = Decimal(str(point)), Decimal(str(line))
    return 'OVER' if a > b else 'UNDER' if a < b else 'ABSTAIN'


def numeric(rows):
    errors = [r['point'] - r['actual'] for r in rows if finite(r['point']) and r['actual'] is not None]
    return {'scored': len(errors), 'MAE': sum(abs(x) for x in errors) / len(errors) if errors else None,
            'MSE': sum(x*x for x in errors) / len(errors) if errors else None,
            'bias': sum(errors) / len(errors) if errors else None,
            'max_absolute_error': max(map(abs, errors)) if errors else None}


def paired(left, right, np):
    rm = {r['opportunity_key']: r for r in right}
    pairs = [(r, rm[r['opportunity_key']]) for r in left
             if r['status'] in ['WIN', 'LOSS'] and r['opportunity_key'] in rm
             and rm[r['opportunity_key']]['status'] in ['WIN', 'LOSS']]
    bygame = collections.defaultdict(list)
    for a, b in pairs:
        bygame[a['game_id']].append(int(a['status'] == 'WIN') - int(b['status'] == 'WIN'))
    intervals = None
    if bygame:
        groups = [bygame[g] for g in sorted(bygame)]
        sizes = np.array([len(z) for z in groups]); diffs = np.array([sum(z) for z in groups])
        rng = np.random.default_rng(20261110); boot = []
        for _ in range(500):
            ix = rng.integers(0, len(groups), len(groups)); boot.append(float(diffs[ix].sum() / sizes[ix].sum()))
        intervals = [float(x) for x in np.quantile(boot, [.025, .975])]
    return {'common_decided': len(pairs), 'left_wins': sum(a['status'] == 'WIN' for a,b in pairs),
            'right_wins': sum(b['status'] == 'WIN' for a,b in pairs),
            'win_change': sum(int(a['status'] == 'WIN') - int(b['status'] == 'WIN') for a,b in pairs),
            'side_disagreements': sum(a['selected_side'] != b['selected_side'] for a,b in pairs),
            'game_clusters': len(bygame), 'week_clusters': len({a['week'] for a,b in pairs}),
            'paired_accuracy_change_interval95': intervals,
            'uncertainty': 'Nominal game-bootstrap500 seed20261110; exposed periods, few week clusters, multiplicity unadjusted',
            'common_mask_sha256': sha(encode(sorted(a['opportunity_key'] for a,b in pairs)))}


def run(args):
    start = time.monotonic(); cpu = time.process_time()
    STATE.update(phase='REGISTRATION',protocol_sha256=args.protocol_sha256)
    resource.setrlimit(resource.RLIMIT_CPU, (180, 185))
    resource.setrlimit(resource.RLIMIT_AS, (3*1024**3, 3*1024**3))
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('registered300secondwallbudget')))
    signal.alarm(300)
    raw = pin(args.protocol, args.protocol_sha256); plan = json.loads(raw)
    spec = plan['peer_overlap']
    if spec.get('enabled') is not True:
        raise ValueError('peer overlap not enabled in published registration')
    private_cap = spec['private_peak_bytes']
    if type(private_cap) is not int or not 20_000 <= private_cap <= PRIVATE_HARD_CAP:
        raise ValueError('registered peer allocation must be20000through60000bytes')
    code = dict(plan.get('code_sha256', {}))
    bindings = plan.get('code_bindings', {})
    if isinstance(bindings,dict):
        code.update({p:(r.get('sha256',r.get('SHA256')) if isinstance(r,dict) else r) for p,r in bindings.items()})
    elif isinstance(bindings,list):
        code.update({r['path']:r.get('sha256',r.get('SHA256')) for r in bindings})
    else:
        raise ValueError('unsupported code binding schema')
    own = str(Path(__file__).resolve().relative_to(ROOT))
    if code.get(own) != sha(Path(__file__).read_bytes()):
        raise ValueError('executing verifier not registration-bound')
    for path, digest in code.items():
        if sha((ROOT / path).read_bytes()) != digest:
            raise ValueError('registered code changed')
    # Public source hashes are immutable constants; arbitrary paths cannot replace bytes.
    cr = json.loads(gzip.decompress(pin(args.c_rows, C_ROWS_SHA)))
    cf = json.loads(gzip.decompress(pin(args.c_features, C_FEATURES_SHA)))
    for name in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:
        os.environ[name] = '1'
    import numpy as np
    import pandas as pd
    STATE['phase'] = 'PARQUET_RUNTIME_DEPENDENCY'
    import pyarrow as pa
    pa.set_cpu_count(1);pa.set_io_thread_count(1);pa.set_memory_pool(pa.system_memory_pool())
    import nfl_lab  # Own package before frozen storage helper loads its dependencies.
    from tools import abc_a_dynamic_carry_wave_v1 as base
    from tools import category_topfive_matched12_storage_v1 as storage
    STATE['phase'] = 'ORIGINAL_STORE_GATE'
    store, _ = storage.open_store(ROOT,allocation_sha256=ALLOCATION,root_go=storage.GO)
    # Original guard runs before the first private source/capsule read.
    with store.transaction(): store._refresh();store._require(private_cap)
    cache = Path(args.C_code_cache)
    for ref in spec['C_bound_code']:
        if sha((cache / Path(ref['path']).name).read_bytes()) != ref.get('sha256',ref.get('SHA256')):
            raise ValueError('canonical evaluator binding changed')
    sys.path.insert(0, str(cache)); common = importlib.import_module('abc_championship_v2')
    # Source metadata identifies exactly the same approved offers/outcomes without
    # loading unrelated carry training/query/history features or constructing models.
    STATE['phase'] = 'QUALIFIED_PRIVATE_SOURCE_READ'
    b, c, g, fr = base.sources()
    with zipfile.ZipFile(io.BytesIO(base.pin(g['offers']))) as z:
        offers = pd.read_parquet(io.BytesIO(z.read(g['offers']['member'])))
    with zipfile.ZipFile(io.BytesIO(base.pin(g['qualified_labels']))) as z:
        labels = pd.read_parquet(io.BytesIO(z.read(g['qualified_labels']['member'])))
    rec = offers.loc[offers.target.eq('rec') & offers.season.eq(2026) & offers.week.between(1,7)].copy()
    exclusions = rec.loc[~rec.position.isin(['WR','TE'])].groupby(['week','position']).size().to_dict()
    rec = rec.loc[rec.position.isin(['WR','TE'])].copy()
    if rec.duplicated(['season','game_id','player_id']).any():
        raise ValueError('approved board has duplicate primary opportunity')
    if rec.opportunity_key.isna().any() or rec.opportunity_key.astype(str).str.strip().eq('').any() or rec.opportunity_key.duplicated().any():
        raise ValueError('primary opportunity keys must be nonnull and unique')
    ll = labels.loc[labels.target.eq('rec') & labels.season.eq(2026) & labels.week.between(1,7)]
    if ll.duplicated(['season','game_id','player_id']).any():
        raise ValueError('ambiguous qualified outcome')
    lm = {(int(r.season), str(r.game_id), str(r.player_id)): r for r in ll.itertuples()}
    feature_keys = [(r['origin'],r['game_id'],r['player_id']) for r in cf]
    if len(set(feature_keys)) != len(feature_keys):
        raise ValueError('duplicate immutable C feature identity')
    features = dict(zip(feature_keys,cf))
    forecasts = {}; c_outside = collections.Counter()
    for r in cr:
        season, week = map(int, r['origin'].split('-W'))
        if season != 2026 or not 1 <= week <= 7 or r['procedure'] not in ['P1','P2']:
            continue
        if r['position'] not in ['WR','TE']:
            c_outside[r['position']] += 1; continue
        key = (season, r['game_id'], r['player_id'], r['procedure'])
        if key in forecasts:
            raise ValueError('duplicate immutable C forecast identity')
        if (r['origin'],r['game_id'],r['player_id']) not in features:
            raise ValueError('C point lacks bound source/context identity')
        forecasts[key] = r
    rows = []; unique = []; source_counts = collections.Counter(); missing = collections.Counter()
    STATE['phase'] = 'MATCHED_POINT_REPLAY'
    for o in rec.to_dict('records'):
        if not finite(float(o['line'])):
            raise ValueError('unsupported original threshold')
        season, week, game, player = int(o['season']), int(o['week']), str(o['game_id']), str(o['player_id'])
        k = (season,game,player); label = lm.get(k)
        state = getattr(label,'participation_state',None) if label is not None else None
        pending = getattr(label,'outcome_state',None) == 'pending'
        appearance = 'PENDING' if pending else 'DNP' if str(state).lower() == 'dnp' else 'PLAYED' if state == 'played' else 'UNKNOWN'
        value = getattr(label,'actual',None) if label is not None else None
        actual = float(value) if appearance == 'PLAYED' and finite(value) and value >= 0 and value % 1 == 0 else None
        outer_outcome_state = 'KNOWN_ACTUAL' if actual is not None else 'MISSING_ACTUAL' if appearance == 'PLAYED' else 'UNKNOWN_PARTICIPATION' if appearance == 'UNKNOWN' else appearance
        if actual is not None:
            presence_reason = getattr(label,'label_reason',None)
            witness = getattr(label,'participation_evidence',None)
            if presence_reason not in ['EXPLICIT_REPORTED_ZERO','EXPLICIT_REPORTED_VALUE'] or not isinstance(witness,str) or not witness:
                raise ValueError('qualified reception label lacks explicit metric-presence/participation binding')
        op = str(o['opportunity_key']); source = str(o['source_stream']); source_counts[source] += 1
        points = []; fallbacks = []; reason = []; cutoffs = []; selected = []; grades = []
        for method, product in PRODUCTS:
            f = forecasts.get((*k,method)); point = f.get(product) if f else None
            if f and actual is not None and finite(f.get('actual')) and actual != float(f['actual']):
                raise ValueError('A/C retained reception outcome conflict; reconcile versions before scoring; case_SHA256='+sha(encode([game,player])))
            if f and f['position'] != o['position']:
                point = None; why = 'POSITION_CONTRACT_MISMATCH'
            else:
                why = 'MISSING_C_CANONICAL_PLAYER_GAME' if not f else 'C_POINT_UNAVAILABLE' if not finite(point) else None
            if f and int(f['origin'][-2:]) != week:
                raise ValueError('same game identity has inconsistent week')
            feature = features.get((f['origin'],game,player)) if f else None
            if f and feature['position'] != f['position']:
                raise ValueError('C point-feature role mismatch')
            side = point_side(point, float(o['line']))
            row = dict(season=season,week=week,game_id=game,player_id=player,category='rec',line=float(o['line']),actual=actual,
                       appearance=appearance,selected_side=side,status='WIN',comparator='STRICT_OVER_UNDER',
                       procedure_id=PREFIX+method,product=product,policy='A::POINT_DIRECTION_UNROUNDED_TIE_ABSTAIN_v1',
                       point=float(point) if finite(point) else None,fallback=bool(f['fallback']) if f else None,
                       point_type=POINT_TYPES[product],outer_outcome_state=outer_outcome_state,
                       source_stream=source,opportunity_key=op,unavailability_reason=why)
            row['status'] = independent_grade(row)
            checked = common.status(row)
            if checked != row['status']:
                raise ValueError('canonical and independent threshold grader disagree')
            rows.append(row); points.append(row['point']); fallbacks.append(row['fallback']); reason.append(why)
            selected.append(side);grades.append(row['status'])
            cutoffs.append(feature['kickoff_UTC'] if feature else None)
            if why: missing[why] += 1
        unique.append([game,player,week,str(o['line']),actual,appearance,op,source,o['source_sha256'],str(o['source_quote_time']),str(o['quote_timing_status']),points,fallbacks,reason,cutoffs,selected,grades])
    scores = []; paired_results = []
    STATE['phase'] = 'CANONICAL_SUMMARIES_AND_PAIRED_CONTROLS'
    for method, product in PRODUCTS:
        rs = [r for r in rows if r['procedure_id'] == PREFIX+method and r['product'] == product]
        for source in ['ALL'] + sorted(source_counts):
            sr = [r for r in rs if source == 'ALL' or r['source_stream'] == source]
            for week in ['ALL'] + list(range(1,8)):
                rr = [r for r in sr if week == 'ALL' or r['week'] == week]
                control_results = {}
                for side in ['OVER','UNDER']:
                    controls = [dict(r,selected_side=side) for r in rr]
                    for co in controls: co['status'] = independent_grade(co)
                    control_results[side] = common.summary(controls)
                    if source == 'ALL' and week == 'ALL':
                        paired_results.append(dict(left=PREFIX+method,product=product,right='ALWAYS_'+side,**paired(rr,controls,np)))
                scored_weeks = sorted({r['week'] for r in rr if r['status'] in ['WIN','LOSS','PUSH']})
                scores.append(dict(procedure_id=PREFIX+method,product=product,policy='A::POINT_DIRECTION_UNROUNDED_TIE_ABSTAIN_v1',
                    period_id='E1_2026_W1_W7_C_POINTS_ON_A_RETAINED_REC_WRTE_BOARD',requested_weeks=list(range(1,8)),
                    source_panel=source,week_view=week,actual_scored_weeks=scored_weeks,**common.summary(rr),
                    point_type=POINT_TYPES[product],
                    outer_outcome_states_independent_of_forecast=dict(collections.Counter(r['outer_outcome_state'] for r in rr)),
                    forecast_availability_by_outer_outcome=[{'forecast_available':a,'outcome_state':s,'rows':n} for (a,s),n in sorted(collections.Counter((r['point'] is not None,r['outer_outcome_state']) for r in rr).items())],
                    numerical_on_same_offered_rows=numeric(rr),fallback_outputs=sum(r['fallback'] is True for r in rr),
                    learned_outputs=sum(r['fallback'] is False for r in rr),unavailable_reasons=dict(collections.Counter(r['unavailability_reason'] for r in rr if r['unavailability_reason'])),
                    constants=control_results,five_distinct_scored_week_floor=len(scored_weeks)>=5,
                    qualification='DURATION_FLOOR_ONLY_NOT_ADMISSION' if len(scored_weeks)>=5 else 'BELOW_FIVE_WEEK_FLOOR',evidence_tier=EVIDENCE))
    for product in ['mean','median']:
        left = [r for r in rows if r['procedure_id']==PREFIX+'P2' and r['product']==product]
        right = [r for r in rows if r['procedure_id']==PREFIX+'P1' and r['product']==product]
        paired_results.append(dict(left=PREFIX+'P2',right=PREFIX+'P1',product=product,**paired(left,right,np)))
    akeys = {(int(o.season),str(o.game_id),str(o.player_id)) for o in rec.itertuples()}
    coverage = {'outer_A_WRTE_offers':len(rec),'outer_A_games':int(rec.game_id.nunique()),'outer_A_weeks':sorted(map(int,rec.week.unique())),
        'A_excluded_outside_WRTE':[{ 'week':int(k[0]),'position':str(k[1]),'rows':int(v)} for k,v in sorted(exclusions.items())],
        'C_points_outside_WRTE':dict(c_outside),'C_only_no_A_offer_by_method':{m:sum(k[:3] not in akeys for k in forecasts if k[3]==m) for m in ['P1','P2']},
        'source_panels':dict(source_counts),'unavailable_product_rows_reasons':dict(missing)}
    # Lossless relational retention: one offer row carries four products in fixed order.
    manifest = {'version':VERSION,'protocol_sha256':sha(raw),'C_commit':C_COMMIT,'C_points_sha256':C_ROWS_SHA,
        'C_feature_export_sha256':C_FEATURES_SHA,'A_offers_sha256':g['offers']['sha256'],
        'A_outcomes_sha256':g['qualified_labels']['sha256'],'products':PRODUCTS,'point_types':POINT_TYPES,
        'row_columns':['game','player','week','original_line_exact_text','actual','appearance','opportunity','source_panel','source_sha256','source_quote_time','quote_timing_status','points','fallbacks','unavailability_reasons','C_query_horizon_UTC','selected_sides','statistical_grades'],
        'status_reconstruction':'Declared unrounded point direction, independent_grade() and pinned C status; original side was not replayed or overwritten',
        'clocks':'C_query_horizon is target kickoff feature horizon, NOT authenticated issuance/information availability; no original-issuance claim',
        'evidence':EVIDENCE,'new_fits':0,'new_inference':0,'new_source_requests':0}
    payload = lzma.compress(encode({'manifest':manifest,'rows':unique}),format=lzma.FORMAT_XZ,preset=9)
    STATE['phase'] = 'GUARDED_PRIVATE_PERSISTENCE'
    dest = store.forward_root/'research'/VERSION
    if dest.exists(): raise ValueError('immutable peer overlap run already exists; no overwrite')
    store.register_root(dest)
    with store.transaction(): store._refresh();store._require(private_cap)
    if len(payload)>private_cap:
        failure = encode({'version':VERSION,'state':'LOSSLESS_PRIVATE_PACKAGE_EXCEEDS_REGISTERED_CAP','required_bytes':len(payload),'cap_bytes':private_cap,'protocol_sha256':sha(raw),'source_hashes':[C_ROWS_SHA,C_FEATURES_SHA],'replay_unique_rows':len(unique),'new_fits':0,'automatic_retry':False})
        store.write_bytes(dest/'FAILURE.json',failure);store.validate_reference(dest/'FAILURE.json',sha(failure))
        raise ValueError('lossless scorecard exceeds registered peer byte allocation; failure retained; no cap bypass')
    path = dest/'RELATIONAL_SCORECARD.json.xz';store.write_bytes(path,payload);store.validate_reference(path,sha(payload))
    usage = store.verify_retained_checkpoint()
    public = {'version':VERSION,'state':'OWNER_LOCAL_ZERO_REFIT_REPLAY_DURABLE_READBACK','protocol_sha256':sha(raw),
        'C_commit':C_COMMIT,'C_protocol':spec['C_protocol'],'C_scorer_sha256':spec['C_scorer_sha256'],
        'sources':{'C_points':C_ROWS_SHA,'C_features':C_FEATURES_SHA,'A_offers':g['offers']['sha256'],'A_outcomes':g['qualified_labels']['sha256']},
        'coverage':coverage,'scores':scores,'paired':paired_results,
        'private_scorecard':{'artifact_id':VERSION+'::RELATIONAL_SCORECARD','bytes':len(payload),'sha256':sha(payload),'readback':'PASS','unique_offers':len(unique),'product_grade_rows':len(rows)},
        'actual':{'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-start,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024},
        'new_fits':0,'new_inference':0,'new_source_requests':0,'new_C_admission':'NOT_OBSERVED',
        'limits':['Original C W2–3 Pinnacle panel remains frozen; this is a new A owner-local panel.',
                  'Reconstructed point decisions, not original website/C recommendations or authenticated pregame availability.',
                  'No probability/price/EV or changedTopPicks qualification; no production change.',
                  'Seven requested weeks do not guarantee all7scored; actualweeks and unavailable states are explicit.',
                  'Fiveweek floor alone does not establish adequate support, improvement or operational admission.']}
    STATE['phase'] = 'PUBLIC_AGGREGATE_RECEIPT'
    output = OUT/'C_POINTS_ON_A_REC_BOARD_V1.json'
    with output.open('xb') as f: f.write(encode(public));f.flush();os.fsync(f.fileno())
    signal.alarm(0)
    print(json.dumps({'version':VERSION,'state':public['state'],'private_bytes':len(payload),'outer_offers':len(unique),'scored_products':len(rows),'public_result':str(output.relative_to(ROOT))}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--protocol',type=Path,default=OUT/'PEER_PROTOCOL_V2.json')
    parser.add_argument('--protocol-sha256',required=True)
    parser.add_argument('--c-rows',type=Path,default=Path('/tmp/acceptance-c-review/artifacts/player-context-matchup-01/v1.1/NUMERICAL_ROWS.json.gz'))
    parser.add_argument('--c-features',type=Path,default=Path('/tmp/acceptance-c-review/artifacts/player-context-matchup-01/v1.1/FEATURE_EXPORT.json.gz'))
    parser.add_argument('--C-code-cache',default='/tmp/acceptance-c-review/src')
    args = parser.parse_args()
    try:
        run(args)
    except BaseException as error:
        signal.alarm(0)
        # Preserve only a bounded known digest from the diagnostic; never serialize
        # exception text/tracebacks, which can contain approved-private locators.
        import re
        found = re.search(r'case_SHA256=([0-9a-f]{64})',str(error))
        receipt = {'version':VERSION,'state':'FAILED','error_type':type(error).__name__,
                   'phase':STATE.get('phase'),'protocol_sha256':args.protocol_sha256,
                   'case_SHA256':found.group(1) if found else None,'new_fits':0,
                   'new_inference':0,'automatic_retry':False,
                   'recorded_UTC':datetime.datetime.now(datetime.timezone.utc).isoformat()}
        OUT.mkdir(parents=True,exist_ok=True)
        path = OUT/'C_POINTS_ON_A_REC_BOARD_FAILURE_V1.json'
        if path.exists():
            path = OUT/('C_POINTS_ON_A_REC_BOARD_FAILURE_'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json')
        with path.open('xb') as f: f.write(encode(receipt));f.flush();os.fsync(f.fileno())
        print(json.dumps(receipt))
        raise SystemExit(1) from None


if __name__=='__main__':
    main()
