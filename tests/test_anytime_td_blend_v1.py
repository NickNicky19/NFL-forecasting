"""Bounded fictional probability/weight checks and a fresh stdlib monitor probe."""
import importlib.util
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import numpy as np
import pytest

from nfl_lab.anytime_td_blend import Weight,components,mixture
from nfl_lab.anytime_calibration import binary_losses
import nfl_lab.anytime_td_blend as blend


def test_one_registered_shrunk_formula_and_identical_component_half_weight():
    y=np.tile([0.,1.],100);cdf=.1+.8*y;cat=np.full(200,.5)
    model=Weight.fit(cdf,cat,y)
    d=cdf-cat
    expected=np.clip((np.mean((y-cat)*d)+.001*.5)/(np.mean(d*d)+.001),0,1)
    assert model.wCDF==expected and model.audit['state']=='FITTED_CLOSED_FORM'
    same=Weight.fit(cat,cat,y)
    assert same.wCDF==.5 and same.audit['optimizer_calls']==0


def test_minimum_failure_is_charged_fixed_half_without_parameter_search():
    model=Weight.fit([.1,.9],[.2,.8],[0.,1.])
    assert model.wCDF==.5 and model.audit['attempt_charged']
    assert model.audit['state']=='FIXED_HALF_FALLBACK'
    np.testing.assert_allclose(mixture([.1,.9],[.2,.8],model.wCDF),[.15,.85])


def test_missing_components_keep_abstention_at_endpoint_weights_and_reject_masks():
    assert np.isnan(mixture([np.nan,.2],[np.nan,.8],0)[0])
    assert np.isnan(mixture([np.nan,.2],[np.nan,.8],1)[0])
    with pytest.raises(ValueError,match='intersection forbidden'):components([np.nan,.2],[.3,.8])


def test_true_bernoulli_mixture_and_infinite_NLL_are_unclipped():
    p=mixture([0.,1.],[1.,0.],.5)
    np.testing.assert_array_equal(p,[.5,.5])
    brier,nll=binary_losses([0.,1.],[1.,0.])
    np.testing.assert_array_equal(brier,[1.,1.]);assert np.isposinf(nll).all()


def test_outer_import_is_fresh_stdlib_without_numerical_or_arrow_parent_state():
    launcher=Path(__file__).resolve().parents[1]/'tools/launch_anytime_td_blend_v1.py'
    script="import runpy,sys;runpy.run_path(sys.argv[1],run_name='probe');assert not any(n in sys.modules for n in ['numpy','pandas','pyarrow','scipy','sklearn']);print('STDLIB_PARENT_PASS')"
    result=subprocess.run([sys.executable,'-B','-c',script,str(launcher)],text=True,capture_output=True,timeout=5,check=True)
    assert result.stdout.strip()=='STDLIB_PARENT_PASS' and not result.stderr


def test_factored_fictional_run_preserves_masks_infinity_and_label_freeze_timeline(tmp_path,monkeypatch):
    import pandas as pd
    from tools import run_anytime_td_blend_v1 as worker
    shared=Path(__file__).resolve().parents[1]/'tools/run_anytime_calibration.py'
    shared_binding=dict(path=str(shared),bytes=shared.stat().st_size,
                        sha256=hashlib.sha256(shared.read_bytes()).hexdigest())
    common=worker.module(shared_binding,'_fictional_shared_blend_pipeline')
    common.load_runtime()
    out=tmp_path/'blend-output';frames={};contexts={};bases={name:dict(probability_column='mean' if name=='fresh_cdf' else 'probability',years={}) for name in common.BASES}
    for year in common.YEARS:
        count=32;dates=pd.date_range(f'{year}-09-01',periods=count,tz='UTC')
        context=pd.DataFrame(dict(season=year,week=np.arange(count)%16+1,
            game_id=[f'fictional-{year}-{i}' for i in range(count)],player_id='fictional',team='A',opponent='B',
            position='WR',kickoff_utc=dates,cutoff_utc=dates,outcome_available_utc=dates+pd.Timedelta(days=7)))
        cpath=f'fixture-context-{year}';contexts[str(year)]={'path':cpath};frames[cpath]=context
        actual=np.tile([0.,1.],count//2);actual[1]=np.nan;actual[4]=1.
        states=np.full(count,'played',dtype=object);states[1]='unknown';states[2]='DNP'
        for name in common.BASES:
            p=np.full(count,.2 if name=='fresh_cdf' else .3);p[3]=np.nan;p[4]=0.
            field=bases[name]['probability_column'];forecast=context.drop(columns='outcome_available_utc').copy()
            forecast[field]=p;forecast['fallback']='fictional-base-fallback'
            labels=context.drop(columns='outcome_available_utc').assign(actual=actual,participation_state=states)
            fp=f'fixture-forecast-{name}-{year}';lp=f'fixture-labels-{name}-{year}'
            frames[fp]=forecast;frames[lp]=labels
            bases[name]['years'][str(year)]=dict(forecast={'path':fp},labels={'path':lp})
    real_read=pd.read_parquet;label_events=[]
    def read(path,*,columns,**kwargs):
        key=str(path)
        if key.startswith('fixture-labels-'):
            year=int(key.rsplit('-',1)[1]);label_events.append(year)
            if year==2023:assert (out/'2023/forecast-freeze.json').is_file()
            if year==2024:assert (out/'forecast-freeze.json').is_file()
        return frames[key].loc[:,columns].copy()
    monkeypatch.setattr(common,'verify_binding',lambda item:Path(item['path']))
    monkeypatch.setattr(pd,'read_parquet',read)
    original_summary=common.summary;original_paired=common.paired
    def summary(rows):
        assert (out/'forecast-freeze.json').is_file()
        return original_summary(rows)
    def paired(*args):
        assert (out/'forecast-freeze.json').is_file()
        return original_paired(*args)
    monkeypatch.setattr(common,'summary',summary);monkeypatch.setattr(common,'paired',paired)
    def forbidden(*a,**k):raise AssertionError('old calibrator fit reached')
    monkeypatch.setattr(common.Calibrator,'fit',classmethod(forbidden))
    run=worker.make_run(common,blend)(dict(output=str(out),contexts=contexts,bases=bases),{},'fictional')
    assert type(run).load_forecasts is common.Run.load_forecasts
    assert type(run).load_labels is common.Run.load_labels
    run.run()
    aggregate=json.loads((out/'aggregate.json').read_text())
    assert run.calls==2 and len(aggregate['comparisons'])==18
    assert sum(row['state']=='UNAVAILABLE' for row in aggregate['comparisons'])==6
    for arm in blend.ARMS:
        cell=aggregate['summary']['2023+2024'][arm]
        assert cell['offered']==64 and cell['forecasted']==62
        assert cell['unknown']==2 and cell['DNP']==2 and cell['log_loss_state']=='positive_infinity'
        assert cell['infinite_log_losses']==2 and aggregate['descriptive_advance_only'][arm] is False
    factor=real_read(out/'2023/fixed_half-probability-factor.parquet')
    assert len(factor)==32 and not factor.loc[3,'forecast_available'] and np.isnan(factor.loc[3,'probability'])
    assert all('probability-factor' in p.name for p in out.rglob('*.parquet'))
    assert json.loads((out/'2023/forecast-freeze.json').read_text())['training_labels_opened']==[2022]
    assert json.loads((out/'forecast-freeze.json').read_text())['training_labels_opened']==[2022,2023]
    assert label_events.index(2023)<label_events.index(2024)
    assert sum(p.stat().st_size for p in out.rglob('*') if p.is_file())<2097152-65536
