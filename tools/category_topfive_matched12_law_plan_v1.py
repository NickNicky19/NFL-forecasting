"""Metadata-only law-plan builder; never opens a store or decodes NFL tables/models."""
import gzip,hashlib,importlib.util,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/'reports/category-topfive-matched-all12-w1w7-20261030/law-outer'
WORKER='f761c909b34cff9e44edf967ca40c8d6be0e1bf37caf938d6333dc81ba2fffa7'
def run():
 p=ROOT/'tools/category_topfive_matched12_law_outer_v1.py'
 assert hashlib.sha256(p.read_bytes()).hexdigest()==WORKER
 s=importlib.util.spec_from_file_location('law_plan_outer',p);outer=importlib.util.module_from_spec(s);s.loader.exec_module(outer)
 def doc(path):
  b=Path(path).read_bytes();return json.loads(gzip.decompress(b) if str(path).endswith('.gz') else b)
 first=doc(ROOT/'config/category-topfive-matched12-inference-v1.json')
 follow=doc(ROOT/'config/category-topfive-matched12-inference-followup-v1.json.gz')
 prior=doc(ROOT/'config/category-topfive-matched12-primary-score-first18-v1_1.json.gz')
 allfinal=doc(ROOT/'config/category-topfive-matched12-all-finalists-freeze-v1_2.json.gz')
 sources={}
 for e in allfinal['extra_entries']:
  if e.get('source_method')!='RESPONSE_CDF':continue
  r=e['producer_proof'];d=json.loads(outer.raw(r))
  if d['version'] in ['matched12-fixed-completion-v1.1','matched12-chart-event-fresh-cell-v1.1']:sources[r['sha256']]={'terminal':r,'features':first['features']}
 specs=outer.prepare_specs(fixed_runs=list(sources.values()));assert len(specs)==24
 research=Path(first['features']['path']).parent.parent
 labelroot=research/'matched12-current-qualified-label-package-v1-20261031';completion=outer.ref(labelroot/'COMPLETE.json');done=json.loads(outer.raw(completion))
 assert done['state']=='COMPLETE_CURRENT_SOURCE_LABELS_QUALIFIED_NOT_FORECAST_SCORES'
 labels=outer.ref(labelroot/'LABEL_PACKAGE.zip')
 assert labels['bytes']==171455 and labels['sha256']=='61da98ad90542b07c6c6664b674086ba4f9474e597325aba62dec44bb2fa72f5'
 assert all(labels[k]==done['package'][k] for k in ['bytes','sha256'])
 labels.update(member='QUALIFIED_LABELS.parquet',member_sha256=done['members']['QUALIFIED_LABELS.parquet']['sha256'])
 pins={k:outer.ref(ROOT/k) for k,v in first['root_code_pins'].items()}
 assert all(pins[k]['sha256']==v for k,v in first['root_code_pins'].items())
 pins.update(loss=outer.ref(ROOT/'tools/category_topfive_matched12_law_scores_v1.py'),auxiliary=outer.ref(ROOT/'tools/category_topfive_matched12_aux_runner_v1.py'),threshold=follow['source_modules']['threshold_cdf'],response=follow['source_modules']['distribution_split_cdf'],storage=outer.ref(ROOT/'tools/category_topfive_matched12_storage_v1.py'),chart=outer.ref(ROOT/'nfl_lab/next_checkpoint_chart_cdf_inference.py'),owned_batch=outer.ref(ROOT/'nfl_lab/owned_reference_batch.py'),worker=outer.ref(p),plan_builder=outer.ref(Path(__file__).resolve()))
 for r in pins.values():outer.raw(r)
 sys.path.insert(0,str(ROOT));from nfl_lab import weekly_future_inference as api
 expected=0
 for spec in specs:
  d=json.loads(outer.raw(spec['source_terminal']));rows=d['cells'] if spec['kind']=='fixed_cell' else d['results'];r=next(r for r in rows if r['cell_id']==spec['source_cell_id'])
  spec['expected_query_rows']=r.get('query_rows',r.get('forecast_rows',r.get('rows')));assert isinstance(spec['expected_query_rows'],int)
  expected+=spec['expected_query_rows']
 assert expected+40<140000
 plan={'version':outer.VERSION,'run_id':'matched12-law-all-finalists-v1-1-20261031','allocation_sha256':first['allocation_sha256'],'resources':{'CPU_seconds':1200,'wall_seconds':2400,'AS_bytes':4294967296,'RSS_bytes':2147483648,'private_bytes':16777216,'model_restorations':25,'query_law_rows':140000,'fits':0},'environment':api.environment(),'source_pins':pins,'specs':specs,'labels':labels,'label_admission':completion,'offers':prior['offers'],'uncertainty':prior['uncertainty'],'expected_query_law_rows':expected,'fixture_row_upper_bound':40,'execution_status':'REQUIRES_SEPARATE_ROOT_AND_INDEPENDENT_GO','evidence':'EXPOSED_CURRENT_VINTAGE_W1_W7_RECONSTRUCTION; no original website or pregame claim'}
 name=ROOT/'config/category-topfive-matched12-law-all-finalists-v1_1.json.gz';body=gzip.compress(outer.enc(plan),mtime=0);name.write_bytes(body)
 proposal={'state':'PROPOSAL_NOT_AUTHORIZED','registered_by':'/root','worker_sha256':WORKER,'plan_sha256':outer.sha(outer.enc(plan)),'independent_review':'PENDING_EXACT_PLAN_REVIEW','new_fits':0}
 go=ROOT/'config/category-topfive-matched12-law-all-finalists-GO-PROPOSAL-v1_1.json';go.write_bytes(outer.enc(proposal))
 receipt={'state':'METADATA_PLAN_PREPARED_NO_EXECUTION','worker_sha256':WORKER,'config_gzip_sha256':outer.sha(body),'plan_canonical_sha256':proposal['plan_sha256'],'specs':len(specs),'expected_query_law_rows':expected,'fixture_row_upper_bound':40,'label_member_sha256':labels['member_sha256'],'source_tables_models_stat_values_decoded':0,'private_config':'LOCAL_ONLY_NOT_PUBLIC'}
 (REPORT/'ACTUAL_PLAN_PREPARATION_V1.json').write_bytes(outer.enc(receipt));return receipt
if __name__=='__main__':print(json.dumps(run(),sort_keys=True))
