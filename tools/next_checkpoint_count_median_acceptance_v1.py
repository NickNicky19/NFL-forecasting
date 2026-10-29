"""Independent cached-row arithmetic acceptance; never fit or issue forecasts."""
import argparse
import hashlib
import io
import json
import math
import resource
import sys
import time
import zipfile
from pathlib import Path


def main():
    start, cpu = time.monotonic(), time.process_time()
    args = argparse.ArgumentParser()
    args.add_argument('--plan', required=True)
    args.add_argument('--sha256', required=True)
    args = args.parse_args()
    raw = Path(args.plan).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == args.sha256
    plan = json.loads(raw)
    assert plan['state'] == 'ROOT_AND_REVIEWER_SEALED'
    assert plan['execution_authorized'] and plan['independent_review'] == 'PASS'
    assert plan['resources'] == {'CPU_seconds': 20, 'wall_seconds': 30,
        'RSS_bytes': 536870912, 'fits': 0, 'model_loads': 0,
        'new_forecasts': 0, 'network': 0, 'children': 0, 'CAS_writes': 0,
        'invocations': 1, 'safe_output_bytes': 16384}
    out = Path(plan['output'])
    assert not out.exists(), 'one invocation only'
    for ref in [plan['worker'], *plan['inputs'].values()]:
        b = Path(ref['path']).read_bytes()
        assert len(b) == ref['bytes'] and hashlib.sha256(b).hexdigest() == ref['sha256']
    blocked = {'network': 0, 'children': 0}
    def audit(name, arguments):
        if name.startswith('socket.'):
            blocked['network'] += 1
            raise RuntimeError('no network')
        if name in {'subprocess.Popen', 'os.system', 'os.fork', 'os.forkpty', 'os.posix_spawn', 'os.posix_spawnp'}:
            blocked['children'] += 1
            raise RuntimeError('no child process')
    sys.addaudithook(audit)
    resource.setrlimit(resource.RLIMIT_CPU, (20, 21))
    import numpy as np
    import pandas as pd
    import pyarrow
    assert np.__version__ == '2.3.5' and pd.__version__ == '2.2.3' and pyarrow.__version__ == '23.0.1'
    assert sys.version_info[:3] == (3,12,14)
    def capsule(ref):
        with zipfile.ZipFile(ref['path']) as z:
            return {n: z.read(n) for n in z.namelist()}
    freeze, grade = (capsule(plan['inputs'][n]) for n in ['freeze', 'grade'])
    f = pd.read_parquet(io.BytesIO(freeze['FORECASTS.parquet']))
    g = pd.read_parquet(io.BytesIO(grade['GRADED_ROWS.parquet']))
    report = json.loads(grade['RESULT.json'])
    keys = ['season', 'week', 'game_id', 'player_id', 'target', 'method']
    assert not f.duplicated(keys).any() and not g.duplicated(keys).any()
    # Complete original values, clocks and fallback fields must remain identical.
    pd.testing.assert_frame_equal(f.sort_values(keys).reset_index(drop=True),
        g[f.columns].sort_values(keys).reset_index(drop=True), check_exact=True)
    checks = 0
    def equal(a, b):
        nonlocal checks
        checks += 1
        if a is None or b is None:
            assert a is None and b is None
        elif isinstance(a, dict):
            assert set(a) == set(b)
            for k in a:
                equal(a[k], b[k])
        elif isinstance(a, (list, tuple)):
            assert len(a) == len(b)
            for x, y in zip(a, b): equal(x, y)
        elif isinstance(a, (float, int)):
            assert math.isclose(a, b, rel_tol=1e-11, abs_tol=1e-11), (a, b)
        else:
            assert a == b, (a, b)
    def supported(t):
        return t.participation_state.eq('played') & np.isfinite(t.actual.astype(float))
    def metrics(t):
        ok = supported(t)
        e = t.loc[ok, 'point'].to_numpy() - t.loc[ok, 'actual'].to_numpy()
        a = abs(e)
        fallback = t.fallback.fillna('').ne('')
        return dict(offered_rows=len(t), scored_rows=int(ok.sum()), games=int(t.loc[ok,'game_id'].nunique()),
            weeks=int(t.loc[ok,'week'].nunique()), fallback_rows=int(fallback.sum()),
            scored_fallback_rows=int((ok & fallback).sum()),
            participation_states={str(k):int(v) for k,v in t.participation_state.value_counts(dropna=False).items()},
            played_missing_rows=int((t.participation_state.eq('played') & ~np.isfinite(t.actual.astype(float))).sum()),
            played_zero_rows=int((t.participation_state.eq('played') & t.actual.eq(0)).sum()),
            MAE=float(a.mean()) if len(a) else None, MSE=float(np.square(e).mean()) if len(a) else None,
            RMSE=float(np.sqrt(np.square(e).mean())) if len(a) else None,
            bias=float(e.mean()) if len(a) else None,
            p90_absolute_error=float(np.percentile(a,90)) if len(a) else None,
            p95_absolute_error=float(np.percentile(a,95)) if len(a) else None,
            error_lt_1=float((a<1).mean()) if len(a) else None,
            error_le_1=float((a<=1).mean()) if len(a) else None)
    numeric = g.actual.notna()
    assert not (numeric & ~g.participation_state.eq('played')).any()
    values = g.loc[numeric,'actual'].to_numpy()
    assert np.isfinite(values).all() and (values>=0).all() and (values==np.floor(values)).all()
    equal(g.loc[numeric,'absolute_error'].to_numpy().tolist(),
          abs(g.loc[numeric,'point'].to_numpy()-values).tolist())
    assert g.loc[~numeric,'absolute_error'].isna().all()
    cell_out=[]
    assert {(c['year'],c['target']) for c in report['cells']} == {
        (2025,'pass_att'),(2025,'pass_int'),(2026,'pass_td'),(2026,'pass_att'),(2026,'pass_int')}
    for cell in report['cells']:
        y, target = cell['year'], cell['target']
        rows = g.loc[g.season.eq(y) & g.target.eq(target)]
        methods = {m:t for m,t in rows.groupby('method')}
        assert set(methods) == set(cell['summaries'])
        expected_n, expected_played = (1359,664) if y==2025 else (515,211)
        for m,t in methods.items():
            assert len(t)==expected_n and supported(t).sum()==expected_played
            assert t.participation_state.value_counts().to_dict() == {
                'played':expected_played,'unknown':expected_n-expected_played}
            equal(metrics(t),cell['summaries'][m])
        for week, summaries in cell['weekly'].items():
            for m,t in methods.items(): equal(metrics(t.loc[t.week.eq(int(week))]),summaries[m])
        for pair in cell['paired_against_CDF_mean']:
            ca, co = methods[pair['candidate']], methods[pair['control']]
            joined = ca.merge(co,on=['season','week','game_id','player_id','target'],suffixes=('_a','_b'),validate='one_to_one')
            use = joined.participation_state_a.eq('played') & joined.participation_state_b.eq('played') & joined.actual_a.notna() & joined.actual_b.notna()
            joined=joined.loc[use].copy()
            assert np.array_equal(joined.actual_a,joined.actual_b)
            delta=abs(joined.point_a-joined.actual_a)-abs(joined.point_b-joined.actual_b)
            joined['d']=delta; joined['n']=1
            for cluster, label in [('game_id','game'),('week','week')]:
                totals=joined.groupby(cluster,sort=True)[['d','n']].sum().to_numpy()
                k=len(totals)
                ci=None
                if k>=8:
                    ids=np.random.default_rng(1703).integers(k,size=(500,k))
                    res=totals[ids].sum(axis=1)
                    ci=np.quantile(res[:,0]/res[:,1],[.025,.975]).tolist()
                equal(dict(paired_rows=len(joined),cluster=cluster,clusters=k,
                    candidate_minus_control_MAE=float(delta.mean()),
                    nominal_exposed_development_95pct_interval=ci,minimum_clusters=8,replicates=500,seed=1703),pair[label])
            base=cell['summaries'][pair['control']]['MAE']
            equal(100*(base-cell['summaries'][pair['candidate']]['MAE'])/base if base else None,pair['signed_improvement_percent'])
        winner=min(cell['summaries'],key=lambda m:(cell['summaries'][m]['MAE'],m))
        equal(winner,cell['lowest_observed_MAE_method'])
        cell_out.append({'season':y,'target':target,'offered':expected_n,'supported':expected_played,
                         'unknown':expected_n-expected_played,'lowest_observed_MAE_method':winner})
    assert len(report['cells'])==5 and len(f)==18926 and int(numeric.sum())==8719
    elapsed=time.monotonic()-start; used=time.process_time()-cpu
    rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
    assert elapsed<=30 and used<=20 and rss<=536870912 and not any(blocked.values())
    receipt={'state':'PASS','scope':'independent arithmetic on frozen rows, not independent source-truth verification',
        'inputs':plan['inputs'],'plan_sha256':args.sha256,'forecast_rows':len(f),'scored_row_incidences':int(numeric.sum()),
        'cells':cell_out,'scalar_checks':checks,'fits':0,'model_loads':0,'new_forecasts':0,'CAS_writes':0,
        'blocked_attempts':blocked,'CPU_seconds':used,'wall_seconds':elapsed,'RSS_bytes':rss,
        'limits':['Does not establish original runtime/model-vector reproduction or source completeness',
            'Exposed historical reconstruction; no current-website or probability claim']}
    body=(json.dumps(receipt,sort_keys=True,indent=2)+'\n').encode()
    assert len(body)<=16384
    with out.open('xb') as stream: stream.write(body)
    print(json.dumps({'state':'PASS','checks':checks,'rows':len(f),'CPU_seconds':used,'wall_seconds':elapsed,'RSS_bytes':rss}))


if __name__ == '__main__': main()
