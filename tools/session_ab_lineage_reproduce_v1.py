"""Reproduction copy of the recorded metadata-only lineage qualification.

The original inline command and actual receipt precede this repository copy.
This is not a new fit, model restore, source-value read or numerical score.
It checks immutable producer metadata without deserializing model parameters.
"""
from pathlib import Path
import gzip,hashlib,json,resource,signal,time

def main():
 resource.setrlimit(resource.RLIMIT_CPU,(240,241));resource.setrlimit(resource.RLIMIT_AS,(2147483648,)*2);signal.alarm(600)
 import nfl_lab
 from tools import category_topfive_matched12_storage_v1 as st
 from nfl_lab.owned_reference_batch import validate_owned_references
 root=Path(__file__).resolve().parents[1];r=root/'reports/session-a-b-matched-20261031'
 cfg=json.loads(gzip.decompress((root/'config/session-ab-cached-diagnostics-v1_1.private.json.gz').read_bytes()))
 def read(q):
  b=Path(q['path']).read_bytes();assert len(b)==q['bytes'] and hashlib.sha256(b).hexdigest()==q['sha256'];return json.loads(b)
 bindings=read(cfg['law_evaluation_bindings']);specs={s['cell_id']:s for s in bindings['specs']}
 diag=json.loads(gzip.decompress((r/'A_DIAGNOSTIC_AGGREGATES_V1_1.json.gz').read_bytes()));refs={}
 for x in diag['A_law_point_consistency']:
  if x['same_saved_model_hash'] and x['same_query_features']:continue
  for k in ['law_replay','source_terminal']:
   q=specs[x['cell_id']][k];refs[q['path']]=q['sha256']
 store,_=st.open_store(root,allocation_sha256=cfg['allocation_sha256'],root_go=st.GO,readonly=True)
 auth,audit=validate_owned_references(store,refs);count=0;records=[]
 for x in diag['A_law_point_consistency']:
  s=specs[x['cell_id']]
  if x['same_saved_model_hash'] and x['same_query_features']:
   n=x['same_law_comparable_valid_point_probability_rows'];count+=n;records.append({'target':x['target'],'method':x['method'],'opportunities':n,'proof':'DIRECT_MODEL_QUERY_LINEAGE'});continue
  term=read(s['source_terminal'])
  if s['kind']=='fixed_cell':
   c=next(v for v in term['cells'] if v['cell_id']==s['source_cell_id']);assert c['state']=='FROZEN_HISTORICAL_FORECASTS_UNSCORED' and c['target']==x['target']
   assert c['bundle']=={k:s['artifact'][k] for k in ['bytes','sha256']} and c['members'][s['member']]['sha256']==s['inner_sha256'] and c['members']['FORECASTS.parquet']['sha256']==s['forecast']['member_sha256']
  else:
   c=next(v for v in term['results'] if v['cell_id']==s['source_cell_id']);assert c['state']=='FROZEN_HISTORICAL_INFERENCE_COMPLETE_UNSCORED' and c['target']==x['target'] and c['forecast']['sha256']==s['forecast']['sha256'] and c['law_replay']['sha256']==s['law_replay']['sha256']
   replay=read(s['law_replay']);assert replay['artifact']==s['artifact'] and replay['member']==s['member'] and replay['features']['sha256']==s['features']['sha256']
  assert x['forecast_lineage_mismatches']==0 and x['point_law_actual_participation_exact'] and x['missing_point']==0 and x['probability_unavailable']==0
  n=x['point_line_opportunities'];count+=n;records.append({'target':x['target'],'method':x['method'],'opportunities':n,'proof':'ORIGINAL_PRODUCER_FORECAST_PARAMETER_FEATURE_CHAIN'})
 print(json.dumps({'state':'REPRODUCED_METADATA_BINDINGS_ONLY','records':records,'opportunity_procedure_incidences':count,'metadata_references':len(auth),'full_scans':audit['full_scan_calls'],'new_fits_inference_scores':0}))

if __name__=='__main__':main()
