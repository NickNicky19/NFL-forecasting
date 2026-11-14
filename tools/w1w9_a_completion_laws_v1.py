"""Proposal-only A retained-law inference; exact ROOT GO and owner receipt first.

Two previously tested A models, unchanged W1--7 query features, zero fits.  The
registered weekly Top-K rules are retrospective diagnostics, not pregame lists.
"""
from pathlib import Path
import argparse, copy, datetime, gzip, hashlib, importlib, importlib.util, io
import json, math, os, platform, resource, signal, stat, sys, time, zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = 'A-W1W9-RETAINED-COMPLETION-LAWS-v1'
OLD_PLAN_SHA = 'f8d3f348c23ab002e9b5355426ae334de0cd624874842096babe3a29a0e9b1b5'
FEATURE_SHA = '5450041c91f3c5dce3a4078c81b861f388e4682dd5cc57d3f1e6b250338f5b0e'
PANELS = ['CMP_A_W1_W4_PLUS_B_NATIVE_W5_W9', 'A_ANNUAL_W1_W5_pass_cmp']
POLICIES = ['FULL_BOARD', 'ABSTAIN_CONFIDENCE_0_55', 'TOP_6_PER_CATEGORY_WEEK',
            'TOP_10_PER_CATEGORY_WEEK', 'TOP_20_PER_CATEGORY_WEEK']
FAMILIES = ['LEAF_CDF', 'RESPONSE_CDF']
ARMS = ['FOOTBALL', 'SHRINK_0_5']
KEY = ['season', 'week', 'game_id', 'player_id']


def require(ok, message):
    if not ok:
        raise ValueError(message)


def encoded(value):
    def scalar(v):
        if hasattr(v, 'item'):
            return v.item()
        raise TypeError(type(v).__name__)
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False,
                       default=scalar) + '\n').encode()


def sha(body):
    return hashlib.sha256(body).hexdigest()


def decode(body):
    return json.loads(gzip.decompress(body) if body.startswith(b'\x1f\x8b') else body)


def source_value(value):
    """Undo only the existing private archive's lossless typed-scalar wrapper."""
    if isinstance(value,dict) and value.get('source_type') in ['Timestamp','datetime','Decimal']:
        return value['value']
    return value


def stamp(path):
    p = Path(path)
    require(p.is_absolute() and p.resolve() == p and not any(q.is_symlink() for q in [p,*p.parents]),
            'Owned input path is not canonical or contains a symlink')
    s = p.lstat()
    require(stat.S_ISREG(s.st_mode) and not s.st_mode & 0o222, 'Owned input must be immutable regular file')
    return [s.st_dev, s.st_ino, s.st_size, s.st_mode, s.st_mtime_ns, s.st_ctime_ns]


def module(name, ref):
    p = Path(ref['path']); b = p.read_bytes()
    require(len(b) == ref['bytes'] and sha(b) == ref['sha256'], 'Original code differs: ' + p.name)
    spec = importlib.util.spec_from_file_location(name, p)
    obj = importlib.util.module_from_spec(spec); sys.modules[name] = obj
    spec.loader.exec_module(obj)
    return obj


def frozen_policy(rows, policy):
    """The exact already-registered combined-side weekly policy, no new router."""
    result = copy.deepcopy(rows)
    if policy == 'FULL_BOARD':
        return result
    if policy == 'ABSTAIN_CONFIDENCE_0_55':
        for row in result:
            if row['selected_side'] in ['OVER', 'UNDER'] and row['decisive_confidence'] < .55:
                row['selected_side'] = 'ABSTAIN'
        return result
    require(policy in POLICIES[2:], 'Unregistered selection rule')
    k = int(policy.split('_')[1])
    ranked = sorted([r for r in result if r['selected_side'] in ['OVER', 'UNDER']],
                    key=lambda r: (r['week'], -r['decisive_confidence'], r['game_id'], r['player_id']))
    chosen, per_week = set(), {}
    for row in ranked:
        week = row['week']; per_week.setdefault(week, 0)
        if per_week[week] < k:
            chosen.add(row['opportunity_key']); per_week[week] += 1
    for row in result:
        if row['selected_side'] in ['OVER', 'UNDER'] and row['opportunity_key'] not in chosen:
            row['selected_side'] = 'ABSTAIN'
    return result


def run(a):
    started, cpu = time.monotonic(), time.process_time()
    raw = a.plan.read_bytes(); require(sha(raw) == a.plan_sha256, 'Root plan wire differs')
    p = decode(raw)
    require(p['id'] == VERSION and p['state'] == 'ROOT_REGISTERED_A_OWNED_LAW_GO'
            and p['registered_by'] == '/root', 'Explicit original A law GO required')
    require(p['new_fits'] == p['network_calls'] == 0 and p['model_restorations'] == 2,
            'Only two retained own-model restorations, zero fits/network permitted')
    require(p['resources'] == dict(CPU_seconds=600, wall_seconds=900, RSS_bytes=3*1024**3,
            output_bytes=1572864, query_law_rows=512, fixture_rows=8), 'Finite law budget differs')
    for path, digest in p['code_sha256'].items():
        require(sha((ROOT/path).read_bytes()) == digest, 'Executing source differs: ' + path)
    require(p['code_sha256'].get('tools/w1w9_a_completion_laws_v1.py') == sha(Path(__file__).read_bytes()),
            'This worker is not pinned')
    resource.setrlimit(resource.RLIMIT_CPU, (580, 600))
    resource.setrlimit(resource.RLIMIT_AS, (3*1024**3,)*2)
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('Law wall budget')))
    signal.alarm(850)
    def offline(event, _):
        if event in ['socket.connect', 'socket.connect_ex', 'socket.getaddrinfo']:
            raise RuntimeError('Retained own-law replay is offline')
    sys.addaudithook(offline); sys.dont_write_bytecode = True
    for key in ['OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS']:
        os.environ[key] = '1'
    sys.path.insert(0, str(ROOT))
    from tools.w1w9_source_cache_v1 import original
    old_raw = (ROOT/p['old_plan_path']).read_bytes()
    require(sha(old_raw) == OLD_PLAN_SHA, 'Original law-plan identity differs')
    old = decode(old_raw)
    registered_raw = (ROOT/p['registered_records']['path']).read_bytes()
    require(len(registered_raw) == p['registered_records']['bytes']
            and sha(registered_raw) == p['registered_records']['sha256'], 'Original registered product records differ')
    registered = decode(registered_raw)['records']
    origin_records = {}
    for record in registered:
        key = record['key']
        if (record['method_alias'] in FAMILIES and key['output'] in ARMS
                and key['selection_policy'].startswith('P2_EXACT_LINE::')):
            cid = 'A::'+record['method_alias']+'::'+key['output']+'::'+key['selection_policy']
            require(cid not in origin_records, 'Duplicate original registered product')
            origin_records[cid] = dict(key_sha256=record['key_sha256'],procedure_version=key['procedure_version'],
                                       selection_policy=key['selection_policy'])
    require(len(origin_records) == 20, 'All twenty already-registered two-law product identities required')
    owner = decode(original(p['owner_admission']))
    require(owner['state'] == 'ROOT_VALIDATED_ORIGINAL_A_LAW_INPUTS'
            and owner['registered_by'] == '/root' and owner['old_plan_sha256'] == OLD_PLAN_SHA,
            'Original owner/CAS validation receipt required; bare hashes are insufficient')
    owned = owner['refs']
    def authenticate(refs):
        out = {}
        for ref in refs:
            path = ref['path']; admitted = owned[path]
            require(all(admitted[k] == ref[k] for k in ['path','bytes','sha256'])
                    and admitted.get('owner') and admitted['stat'] == stamp(path),
                    'Root-validated original ownership/stat changed')
            b = Path(path).read_bytes()
            require(len(b) == ref['bytes'] and sha(b) == ref['sha256'], 'Owned source changed after admission')
            out[path] = {k: ref[k] for k in ['path','bytes','sha256']}
        return out
    specs = [s for s in old['specs'] if s['target'] == 'pass_cmp']
    require(len(specs) == 2 and [s['methods'][0] for s in specs] == FAMILIES,
            'Original two completion-law specifications differ')
    refs = []
    for spec in specs:
        require(spec['features']['sha256'] == FEATURE_SHA and spec['expected_query_rows'] == 718
                and spec['query_roles'] == spec['primary_roles'] == ['QB'] and spec['scale'] == 1,
                'Original feature/history/role contract differs')
        refs += [spec[k] for k in ['artifact','features','forecast','law_replay','source_terminal']]
        if spec.get('future_manifest'):
            refs.append(spec['future_manifest'])
    authenticate(list({r['path']:r for r in refs}.values()))
    import numpy as np, pandas as pd, pyarrow as pa, joblib
    from threadpoolctl import threadpool_limits
    from nfl_lab import cdf_engine as engine, weekly_future_inference as api
    require(api.environment() == old['environment'], 'Original model environment differs')
    require(dict(python=platform.python_version(), numpy=np.__version__, pandas=pd.__version__, pyarrow=pa.__version__)
            == p['runtime'], 'Comparison runtime differs')
    pa.set_cpu_count(1); pa.set_io_thread_count(1)
    for ref in old['source_pins'].values():
        b = Path(ref['path']).read_bytes()
        require(len(b) == ref['bytes'] and sha(b) == ref['sha256'], 'Original law source pin differs')
    stable = module('nfl_lab.threshold_cdf', old['source_pins']['threshold']).StableMixtureBatch
    response_type = module('nfl_lab.distribution_split_cdf', old['source_pins']['response']).DistributionSplitCDFModel
    loss = module('w1w9_a_exact_law_math', old['source_pins']['loss'])
    from tools import timing_confirm_b_completion_join_v1 as shared
    from tools import w1w9_saved_comparison_v1 as existing
    base_plan = decode(original(p['comparison_plan']))
    for name, digest in base_plan['common_code'].items():
        require(sha((a.c_cache/name).read_bytes()) == digest, 'Accepted grader source differs')
    sys.path.insert(0, str(a.c_cache)); common = importlib.import_module('abc_championship_v2')
    require(Path(common.__file__).resolve() == (a.c_cache/'abc_championship_v2.py').resolve(), 'Wrong accepted grader')
    with zipfile.ZipFile(io.BytesIO(original(p['comparison_vectors']))) as z:
        private = json.loads(z.read('COMPLETE_COMPARISON_VECTORS.json'))
    require(private['id'] == existing.VERSION and private['plan_sha256'] == sha(original(p['comparison_plan'])),
            'Completed comparison source policy/rows not bound to exact plan')
    boards = {key: [{name:source_value(value) for name,value in row.items()}
                    for row in private['offer_contracts'][key]] for key in PANELS}
    baselines = {key: private['vectors'][key] for key in PANELS}
    expected = {(int(o['season']),int(o['week']),o['game_id'],o['player_id'])
                for board in boards.values() for o in board if int(o['week']) <= 7}
    features = pd.read_parquet(io.BytesIO(Path(specs[0]['features']['path']).read_bytes()))
    q = features.loc[features.position.eq('QB')].copy()
    require(len(q) == 718 and not q.duplicated(KEY).any(), 'Original complete QB query universe differs')
    for name in ['kickoff_utc','cutoff_utc','feature_max_source_available_utc']:
        q[name] = pd.to_datetime(q[name],utc=True)
    require((q.cutoff_utc == q.kickoff_utc).all()
            and not (q.feature_max_source_available_utc.notna() & (q.feature_max_source_available_utc >= q.cutoff_utc)).any(),
            'Original seven-day query chronology differs')
    q = q.loc[[tuple(x) in expected for x in q[KEY].to_numpy()]].reset_index(drop=True)
    query_columns = KEY + ['team','opponent','position','kickoff_utc','cutoff_utc','feature_max_source_available_utc']
    query_columns += [c for c in q if c.startswith('f_')]
    q = q[query_columns]
    laws, proofs, law_count, fixture_count = {}, [], 0, 0
    for spec in specs:
        family = spec['methods'][0]; session = None
        if family == 'LEAF_CDF':
            session = api.FutureInferenceSession(authenticate).prepare([spec['future_manifest']])
            _, model = session.models[spec['future_manifest']['sha256']]
            require(type(model) is engine.LeafCDFModel, 'Wrong trusted Leaf class')
        else:
            with zipfile.ZipFile(io.BytesIO(Path(spec['artifact']['path']).read_bytes())) as z:
                inner = z.read(spec['member'])
            require(sha(inner) == spec['inner_sha256'], 'Original Response model member differs')
            model = joblib.load(io.BytesIO(inner))
            require(type(model) is response_type, 'Wrong trusted Response class')
        require(model.category['target'] == 'pass_cmp' and model.category['support'] == 'count', 'Wrong law target/support')
        require(model.audit['prior_weight'] == engine.PRIOR_WEIGHT, 'Original prior mixture changed')
        forecast_body = Path(spec['forecast']['path']).read_bytes()
        if spec['forecast'].get('member'):
            with zipfile.ZipFile(io.BytesIO(forecast_body)) as z:
                forecast_body = z.read(spec['forecast']['member'])
            require(sha(forecast_body) == spec['forecast']['member_sha256'], 'Original point member differs')
        f = pd.read_parquet(io.BytesIO(forecast_body))
        f = f.loc[f.method.eq(family)]
        require(len(f) == 718 and not f.duplicated(KEY).any(), 'Saved point identity coverage differs')
        saved = {tuple(r[k] for k in KEY):r for r in f.to_dict('records')}
        own = {}; point_checks = 0
        with threadpool_limits(limits=1):
            for positions, batch, reasons in model.predict_batches(q,batch_size=128):
                if batch is None:
                    continue
                law = stable.from_batch(batch)
                require(law.prior.support == 'count', 'Completion law must have count support')
                means, medians = law.mean, law.quantile(.5)
                original_means = batch.mean if family == 'LEAF_CDF' else means
                original_medians = batch.quantile(.5) if family == 'LEAF_CDF' else medians
                for j,index in enumerate(positions):
                    key = tuple(q.iloc[index][k] for k in KEY); old_point = saved[key]
                    require(abs(float(original_means[j])-float(old_point['mean'])) <= 1e-10
                            and float(original_medians[j]) == float(old_point['median']), 'Unchanged original mean/median parity failed')
                    point_checks += 1
                    # Original outer.subset semantics: preserve the already
                    # normalized law; do not normalize the histogram twice.
                    one = copy.copy(law)
                    for name in ['weights','cumulative','weighted_cumulative']:
                        setattr(one,name,getattr(law,name)[j:j+1])
                    own[key] = (one, str(reasons[j]), dict(support=one.support.tolist(),weights=one.weights[0].tolist(),
                        cumulative=one.cumulative[0].tolist(),weighted_cumulative=one.weighted_cumulative[0].tolist(),
                        prior=vars(one.prior),a=float(one.a),b=float(one.b),mean=float(means[j]),median=float(medians[j]),
                        retained_point_mean=float(old_point['mean']),retained_point_median=float(old_point['median'])))
                    law_count += 1
                    require(law_count <= 512, 'Query law-row budget exhausted')
            # Outcome-independent first two keys, single-versus-batch exact law identity.
            for index in range(min(2,len(q))):
                key = tuple(q.iloc[index][k] for k in KEY)
                if key not in own:
                    continue
                single = list(model.predict_batches(q.iloc[[index]],batch_size=1))
                require(len(single) == 1 and single[0][1] is not None, 'Single restoration unavailable')
                law = stable.from_batch(single[0][1]); previous = own[key][0]
                require(np.array_equal(law.support,previous.support) and np.array_equal(law.weights,previous.weights)
                        and vars(law.prior) == vars(previous.prior) and law.b == previous.b, 'Batch/single law identity differs')
                fixture_count += 1
        require(fixture_count <= 4, 'Fixture budget exhausted')
        if session is not None:
            session.close()
        proofs.append(dict(family=family,model_sha256=spec['inner_sha256'],query_law_rows=len(own),
            point_parity_checks=point_checks,point_tolerance=1e-10,median_tolerance=0,
            saved_point_arithmetic='ORIGINAL_RAW_LEAF_MIXTURE' if family=='LEAF_CDF' else 'ORIGINAL_NORMALIZED_RESPONSE_MIXTURE',
            corrector='NONE_NATIVE_LAW;NORMALIZED_STABLE_MIXTURE_ONCE',prior_weight='ORIGINAL_MODEL_VALUE_UNCHANGED'))
        laws[family] = own
    authenticate(list({r['path']:r for r in refs}.values()))
    full_vectors, reports = {}, []
    def original_attribution(rows):
        groups = [('LEARNED',[r for r in rows if r['selected_side'] is not None and r['fallback']=='']),
                  ('PRIOR_FALLBACK',[r for r in rows if r['selected_side'] is not None and r['fallback']!='']),
                  ('TECHNICALLY_UNAVAILABLE',[r for r in rows if r['selected_side'] is None])]
        return {name:common.summary(subset) for name,subset in groups}
    def own_summary(rows):
        result = existing.summary(rows,common,shared)
        result['learned_prior_reference_contributions'] = original_attribution(rows)
        result['attribution_contract'] = 'ORIGINAL_PREDICT_BATCHES_REASON_EMPTY_LEARNED_ELSE_PRIOR;UNAVAILABLE_SEPARATE'
        return result
    for panel_id, board in boards.items():
        full_vectors[panel_id] = {}
        for family in FAMILIES:
            for arm in ARMS:
                base = []
                for offer in board:
                    context = existing.offer_context(offer); key = tuple(context[k] for k in KEY)
                    law_info = laws[family].get(key); probs = None; point = None; confidence = None
                    side = None; reason = 'ORIGINAL_W8_W9_FEATURES_NOT_AVAILABLE' if key[1] >= 8 else 'ORIGINAL_QUERY_OR_LAW_UNAVAILABLE'
                    fallback = None; proper = None
                    if law_info:
                        law, fallback, law_data = law_info
                        query = q.loc[(q.game_id == key[2]) & (q.player_id == key[3])].iloc[0]
                        require(existing.instant(context['kickoff_utc']) == query.kickoff_utc.to_pydatetime()
                                and existing.team(query.team) == existing.team(offer['team'])
                                and existing.team(query.opponent) == existing.team(offer['opponent']), 'Canonical query/offer context differs')
                        event = loss.threshold_probabilities(law,[context['line']])
                        if arm == 'SHRINK_0_5':
                            event = loss.shrink_control(event)
                        selected = loss.select_sides(event)
                        side = str(selected['side'][0]).upper(); confidence = float(selected['decisive_confidence'][0])
                        probs = dict(zip(['p_under','p_push','p_over'],map(float,event['probabilities'][0])))
                        reason = None
                        if offer['appearance'] == 'PLAYED' and offer['actual'] is not None:
                            scores = loss.threshold_scores(event,[offer['actual']])
                            proper = dict(half_three_outcome_Brier=float(scores['Brier'][0]),log_loss=float(scores['log_loss'][0]))
                    row = dict(season=2026,week=context['week'],game_id=context['game_id'],player_id=context['player_id'],
                        category='pass_cmp',comparator='STRICT_OVER_UNDER',line=context['line'],actual=offer['actual'],
                        appearance=offer['appearance'],point=point,selected_side=side,opportunity_key=context['opportunity_key'],
                        source_stream=existing.source_name(offer),candidate_id='A::'+family+'::'+arm,
                        fallback=fallback,unavailability_reason=reason,decisive_confidence=confidence,
                        native_proper_scores=proper,retained_point_mean=law_info[2]['retained_point_mean'] if law_info else None,
                        retained_point_median=law_info[2]['retained_point_median'] if law_info else None,**(probs or {}))
                    base.append(row)
                for policy in POLICIES:
                    rows = frozen_policy(base,policy); cid = 'A::'+family+'::'+arm+'::P2_EXACT_LINE::'+policy
                    require(cid in origin_records, 'New unregistered law/selector identity forbidden')
                    for row in rows:
                        row['candidate_id'] = cid; row['status'] = shared.grade(row)
                        row['origin_product_binding'] = origin_records[cid]
                        require(common.status(row) == row['status'], 'Accepted grader mismatch')
                    full_vectors[panel_id][cid] = rows
                    own = own_summary(rows)
                    contributions = original_attribution(rows)
                    reference_rows = baselines[panel_id]
                    comparisons = []
                    for reference in p['references']:
                        require(reference in reference_rows, 'Frozen strong reference missing')
                        comparisons.append(dict(reference=reference,**shared.paired(rows,reference_rows[reference],np)))
                    def native_scores(subset):
                        supported=[r['native_proper_scores'] for r in subset if r['native_proper_scores'] is not None]
                        return dict(n=len(supported),**{name:math.fsum(r[name] for r in supported)/len(supported)
                            if supported else None for name in ['half_three_outcome_Brier','log_loss']})
                    numeric={name:shared.numerical([{**r,'point':r['retained_point_'+name]} for r in rows]) for name in ['mean','median']}
                    report = dict(panel_id=panel_id,candidate_id=cid,origin_product_binding=origin_records[cid],summary=own,
                        weekly=[dict(week=w,**own_summary([r for r in rows if r['week']==w])) for w in range(1,10)],
                        source_sensitivity=[dict(source=s,**own_summary([r for r in rows if r['source_stream']==s]))
                                            for s in sorted({r['source_stream'] for r in rows})],
                        contributions=contributions,paired_strong_controls=comparisons,
                        unchanged_saved_points_offered_numerical=numeric,native_proper_scores_all_available=native_scores(rows),
                        native_proper_scores_selected=native_scores([r for r in rows if r['selected_side'] in ['OVER','UNDER']]),
                        native_proper_score_scope='HALF_THREE_OUTCOME_BRIER kept per frozen vector; shared binary strict-Over Brier is distinct',
                        admission='PARTIAL_W1_W7_QUERIES;NO_W8_W9_INHERITANCE;RETROSPECTIVE_WEEKLY_TOPK_NOT_PREGAME_LIST')
                    reports.append(report)
    serial_laws = {family:[dict(identity=list(key),fallback=entry[1],law=entry[2]) for key,entry in sorted(own.items())]
                   for family,own in laws.items()}
    private_out = dict(id=VERSION,plan_sha256=sha(raw),models=proofs,complete_laws=serial_laws,vectors=full_vectors,
        original_features_sha256=FEATURE_SHA,comparison_vectors_sha256=p['comparison_vectors']['sha256'],
        restrictions='PRIVATE_OWNER_LOCAL_ONLY;UNTOUCHED_ORIGINAL_MODELS_AND_FEATURES;NO_NEW_PREGAME_ISSUANCE')
    buff = io.BytesIO()
    with zipfile.ZipFile(buff,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        info=zipfile.ZipInfo('COMPLETE_A_LAWS_AND_POLICY_VECTORS.json',date_time=(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
        z.writestr(info,encoded(private_out))
    private_body = buff.getvalue()
    public = dict(id=VERSION,state='COMPLETED_RETAINED_A_LAWS_PARTIAL_QUERY_COVERAGE',plan_sha256=sha(raw),
        reports=reports,model_restoration_proofs=proofs,new_fits=0,new_model_restorations=2,
        extra_single_query_fixture_rows=fixture_count,original_future_restore_fixture_upper_bound=4,
        new_NFL_games=0,new_original_issued_picks=0,network_calls=0,
        policy='EXACT_REGISTERED_0_55_AND_COMBINED_SIDE_WEEKLY_TOP6_10_20;NO_BATCH_CLOCK_CLAIM',
        full_law_private=dict(bytes=len(private_body),sha256=sha(private_body)),
        resources=dict(CPU_seconds=time.process_time()-cpu,wall_seconds=time.monotonic()-started,
                       RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024))
    public_body=gzip.compress(encoded(public),mtime=0)
    require(len(private_body)+len(public_body) <= p['resources']['output_bytes'], 'Complete law output reservation exhausted')
    existing.immutable(a.private_zip,private_body); existing.immutable(a.output,public_body)
    signal.alarm(0)
    print(json.dumps(dict(state=public['state'],private_bytes=len(private_body),public_bytes=len(public_body),resources=public['resources'])))


if __name__ == '__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--plan',type=Path,required=True);ap.add_argument('--plan-sha256',required=True)
    ap.add_argument('--c-cache',type=Path,required=True);ap.add_argument('--private-zip',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True);run(ap.parse_args())
