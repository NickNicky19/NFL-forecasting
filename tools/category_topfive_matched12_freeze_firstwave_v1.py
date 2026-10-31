"""Authenticate completed forecasts before labels; prepare exact scoring GO."""
from pathlib import Path
import gzip,hashlib,io,json,resource,time,zipfile
ROOT=Path(__file__).resolve().parents[1]
def enc(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def sha(x):return hashlib.sha256(x).hexdigest()
def main():
 start=time.monotonic();cpu=time.process_time()
 import nfl_lab
 from nfl_lab.owned_reference_batch import validate_owned_references
 from tools import category_topfive_matched12_storage_v1 as st
 from tools import category_topfive_matched12_primary_score_v1 as scoring
 import pandas as pd
 import pyarrow as pa
 pa.set_cpu_count(1);pa.set_io_thread_count(1)
 store,_=st.open_store(ROOT,allocation_sha256='f123cd5ffd6f4a204a76c68bf63817cce63cecd7021543a23503d0233cc3eb26',root_go=st.GO)
 r=store.forward_root/'research';base=r/'matched12-fixed-parameter-historical-inference-v1'
 plan=json.loads((ROOT/'config/category-topfive-matched12-inference-v1.json').read_bytes())
 prep=json.loads((ROOT/'config/category-topfive-matched12-primary-preparation-v1.json').read_bytes())
 def ref(p):
  b=p.read_bytes();return {'path':str(p),'bytes':len(b),'sha256':sha(b)}
 terminalref=ref(base/'TERMINAL.json');terminal=json.loads(Path(terminalref['path']).read_bytes())
 assert terminal['state']=='FINITE_WAVE_FORECASTS_FROZEN_UNSCORED'
 assert len(terminal['results'])==len(plan['cells'])==18
 by={v['cell_id']:v for v in terminal['results']};refs=[terminalref,plan['features']]
 qref=ref(r/'matched12-primary-preparation-v1/EXPECTED_QUERIES.parquet');refs.append(qref)
 cells=[]
 for c in plan['cells']:
  v=by[c['cell_id']];assert v['state']=='FROZEN_HISTORICAL_INFERENCE_COMPLETE_UNSCORED'
  f={**v['forecast'],'path':str(base/v['forecast']['file'])};f.pop('file')
  refs.append(f);cells.append({**c,'forecast':f})
 owners=[store,store.complete_peer,store.complete_peer.prior_forward,store.complete_peer.legacy]
 batches=[]
 for owner in owners:
  owned={x['path']:x['sha256'] for x in refs if any(Path(x['path']).is_relative_to(Path(y)) for y in owner._roots)}
  if owned:
   validated,audit=validate_owned_references(owner,owned);batches.append({'references':len(validated),'full_scans':audit['full_scan_calls']})
 assert sum(v['references'] for v in batches)==len({x['path'] for x in refs})
 queries=pd.read_parquet(io.BytesIO(Path(qref['path']).read_bytes()))
 assert len(queries)==4985 and queries.game_id.nunique()==107
 context=scoring.CONTEXT;census=[]
 for c in cells:
  f=pd.read_parquet(io.BytesIO(Path(c['forecast']['path']).read_bytes()))
  wanted=queries.loc[queries.position.isin(c['query_roles']),context].copy()
  assert not f.duplicated(['season','week','game_id','player_id']).any()
  assert set(f.columns).isdisjoint({'actual','outcome_state','realized','label'})
  assert len(f)==len(wanted)==by[c['cell_id']]['rows']
  joined=f[context].merge(wanted,on=context,validate='one_to_one',how='outer',indicator=True)
  assert joined['_merge'].eq('both').all()
  census.append({'cell_id':c['cell_id'],'rows':len(f),'games':int(f.game_id.nunique()),'weeks':sorted(map(int,f.week.unique())),'sha256':c['forecast']['sha256']})
 state='FIRST18_COMPLETE_PRIVATE_FORECAST_READBACK_BEFORE_LABELS'
 freeze={'version':'matched12-first18-forecast-freeze-v1','state':state,'forecast_readback_verified':True,'inference_terminal_sha256':terminalref['sha256'],'feature_sha256':plan['features']['sha256'],'successful_forecasts':{c['cell_id']:c['forecast']['sha256'] for c in cells},'census':census,'source_queries_sha256':qref['sha256'],'total_procedure_query_rows':sum(c['rows'] for c in census),'new_fits':0,'evaluation_labels_decoded':0,'genuine_pregame_forecasts':0,'restoration_scope':'FRESH_PROCESS_LOCAL_OWNED_CAS_READBACK_NOT_OFFHOST'}
 out=r/'matched12-first18-forecast-freeze-v1';assert not out.exists();store.register_root(out)
 raw=enc(freeze);store.write_bytes(out/'FORECAST_MANIFEST.json',raw)
 freezeref=store.validate_reference(out/'FORECAST_MANIFEST.json',sha(raw));freezeref={k:freezeref[k] for k in ['path','bytes','sha256']}
 assert json.loads(Path(freezeref['path']).read_bytes())==freeze
 src=r/'public-git-sources-v1';roles={c['target']:c['query_roles'] for c in cells};primary={c['target']:c['primary_roles'] for c in cells}
 final=json.loads(gzip.decompress((ROOT/'reports/category-topfive-matched-all12-w1w7-20261030/labels/FINALITY_METADATA_RESULT_V1.json.gz').read_bytes()))
 sourceplan=json.loads((ROOT/'reports/category-topfive-matched-all12-w1w7-20261030/labels/SOURCE_PLAN_V1.json').read_bytes())
 inputs=prep['inputs']
 history=inputs['history'];week6=inputs['week6']
 labelcfg={'version':'matched12-current-vintage-labels-v1.1','roles_by_target':roles,'qualified_final_game_ids':final['qualified_final_game_ids'],'source_versions':sourceplan['source_versions'],'forecast_freeze':freezeref,'required_forecast_freeze_state':state,'inputs':{'queries':qref,'history':history,'week6':week6,'site_stats':ref(src/'SITE_ACTUALS_W7.json'),'site_archive':ref(src/'SITE_ARCHIVE_W7.json')}}
 offers=ref(r/'matched12-replay-legacy-board-technical-v1-2-20261031/PREPARED_OFFERS.zip')
 with zipfile.ZipFile(offers['path']) as z:
  names=z.namelist();member=next(x for x in names if x.endswith('PRIMARY_FULL.parquet'))
  offers['member']=member;offers['member_sha256']=sha(z.read(member))
 pins={k:ref(ROOT/'tools'/p) for k,p in {'scorer':'category_topfive_matched12_score_v1_2.py','auxiliary_helpers':'category_topfive_matched12_aux_runner_v1.py','offer_driver':'category_topfive_matched12_offer_driver_v1.py','labels':'category_topfive_matched12_labels_v1.py','storage_helper':'category_topfive_matched12_storage_v1.py'}.items()}
 cfg={'version':scoring.VERSION,'run_id':'matched12-primary-score-first18-v1-20261031','allocation_sha256':'f123cd5ffd6f4a204a76c68bf63817cce63cecd7021543a23503d0233cc3eb26','source_pins':pins,'forecast_freeze':freezeref,'required_forecast_freeze_state':state,'inference_terminal':terminalref,'queries':qref,'feature_source_sha256':plan['features']['sha256'],'cells':cells,'query_roles_by_target':roles,'primary_roles_by_target':primary,'horizon_id':'HISTORICAL_LEFT_LIMIT_KICKOFF_RECONSTRUCTION','outcome_version':'matched12-strict-explicit-source-labels-first18-v1','declared_equal_ATD_blend':True,'uncertainty':{'replicates':1000,'seed':20261030,'minimum_clusters':2},'resources':{'CPU_seconds':900,'wall_seconds':1500,'RSS_bytes':2147483648,'private_peak_bytes':16777216,'public_aggregate_bytes':524288,'maximum_output_rows':200000},'offers':offers,'label_configuration':labelcfg}
 raw=scoring.encoded(cfg);cfgpath=ROOT/'config/category-topfive-matched12-primary-score-first18-v1.json.gz';assert not cfgpath.exists();cfgpath.write_bytes(gzip.compress(raw,mtime=0))
 go={'state':'ROOT_AND_INDEPENDENT_GO','registered_by':'/root','worker_sha256':sha(Path(scoring.__file__).read_bytes()),'configuration_sha256':sha(raw),'execution_after_independent_configuration_review':True}
 (ROOT/'config/category-topfive-matched12-primary-score-first18-GO-v1.json').write_bytes(enc(go))
 receipt={'state':'COMPLETE_FORECAST_FREEZE_CONFIGURATION_PENDING_INDEPENDENT_REVIEW','freeze_sha256':freezeref['sha256'],'forecasts':sum(c['rows'] for c in census),'cells':18,'games':107,'weeks':7,'metadata_only_source_inspections':True,'outcomes_decoded':0,'fresh_local_CAS_readback':True,'offhost_restore':'NOT_VERIFIED','config_sha256':sha(raw),'worker_sha256':go['worker_sha256'],'actual':{'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-start,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024}}
 (ROOT/'reports/category-topfive-matched-all12-w1w7-20261030/primary-scoring/FIRST18_FREEZE_V1.json').write_bytes(enc(receipt));print(enc(receipt).decode())
if __name__=='__main__':main()
