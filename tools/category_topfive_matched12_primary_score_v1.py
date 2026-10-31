"""Root-GO primary roster-panel scoring after immutable model-output freeze.

No fitting, model deserialization, acquisition or production operation. Source
labels are admitted only after the complete declared first-wave freeze. Later
candidates require separately registered continuation identities.
"""
from __future__ import annotations
import hashlib,importlib.util,io,json,gzip,math,resource,signal,sys,time,copy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
VERSION='matched12-primary-firstwave-score-v1'
SCORER_SHA='ab7775aae5a9178ed82d28217510f328d9903ef20633614c9a2c6bed02c67228'
AUX_SHA='9e3e060e098acdcac67607a0a0bc0b23c4fa84ecd8716169eca3cff5c2fee8e9'
ID=['target','season','week','game_id','player_id','team','opponent']
CONTEXT=['season','week','game_id','player_id','team','opponent','position','kickoff_utc','cutoff_utc']
FAMILY={'leaf_cdf_base':'LEAF_CDF','catboost_medium':'CATBOOST_MEDIUM','count_A':'COUNT_A_MEAN'}
COUNTS={'pass_td','pass_cmp','pass_att','pass_int','rush_att','rec','rec_tgt'}
ALL12=['pass_yd','pass_td','pass_cmp','pass_att','pass_int','rush_yd','rush_att','rec','rec_yd','rush_rec_yd','anytime_td','chart_ppr']


def require(ok,text):
 if not ok:raise ValueError(text)


def sha(raw):return hashlib.sha256(raw).hexdigest()

def encoded(x):
 import numpy as np,pandas as pd
 from decimal import Decimal
 def default(v):
  if isinstance(v,np.generic):return v.item()
  if isinstance(v,(pd.Timestamp,Decimal)):return str(v)
  raise TypeError(type(v).__name__)
 return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False,default=default).encode()


def load(ref,name):
 from tools.category_topfive_matched12_offer_driver_v1 import read_exact
 read_exact(ref);spec=importlib.util.spec_from_file_location(name,ref['path']);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def output_contracts(cells):
 """Pure pre-label metadata, keeping fitted procedures separate from outputs."""
 catalog={};outputs={}
 for c in cells:
  t=c['target'];family=c['family'];method=FAMILY[family];parent=c['procedure_version']
  if family=='leaf_cdf_base':products={'probability_raw':'probability','probability_normalized':'normalized_law_probability'} if t=='anytime_td' else {'mean':'mean','median':'median'}
  elif family=='catboost_medium':products={'probability':'probability'} if t=='anytime_td' else {'mean_objective_point' if t in COUNTS else 'median_objective_point':'point'}
  else:products={'mean_objective_point':'point'}
  version=sha((json.dumps({'recipe':'count-a-prior-mean-fallback-v2-20261025','parent_procedure_version':parent,'parent_model_sha256':c['model']['sha256']},sort_keys=True,separators=(',',':'))+'\n').encode()) if family=='count_A' else parent
  target=catalog.setdefault(t,{})
  require(method not in target,'duplicate procedure family/target')
  target[method]={'procedure_id':method,'procedure_version':version,'products':list(products),'shortlist_group':'COUNT_A' if family=='count_A' else method,'model_sha256':c['model']['sha256']}
  target[method]['product_procedure_versions']={product:(sha((json.dumps({'law_arithmetic':'normalized-cumulative-mixture-v1-20261025','parent_procedure_version':parent,'parent_model_sha256':c['model']['sha256']},sort_keys=True,separators=(',',':'))+'\n').encode()) if product=='probability_normalized' else version) for product in products}
  outputs[c['cell_id']]={'method':method,'products':products,'procedure_version':version,'parent_procedure_version':parent}
  if family=='count_A':
   target['COUNT_A_LEGACY_POINT']={'procedure_id':'COUNT_A_LEGACY_POINT','procedure_version':parent,'products':['legacy_empirical_point'],'shortlist_group':'COUNT_A'}
 return catalog,outputs


def expected_population(queries,catalog,query_roles,horizon):
 import pandas as pd
 require(set(CONTEXT)<=set(queries) and not queries.duplicated(['season','week','game_id','player_id']).any(),'complete unique source-only primary query packet required')
 require(queries.season.eq(2026).all() and queries.week.isin(range(1,8)).all(),'fixedW1-7only')
 parts=[]
 for t in catalog:
  require(t in query_roles,'predeclared query roles missing')
  f=queries.loc[queries.position.isin(query_roles[t]),CONTEXT].copy();f['target']=t;f['horizon_id']=horizon;parts.append(f)
 return pd.concat(parts,ignore_index=True)


def flatten_forecasts(wides,cells,contracts):
 import pandas as pd,numpy as np
 frames=[]
 for c in cells:
  if c['cell_id'] not in wides:continue
  wide=wides[c['cell_id']];contract=contracts[c['cell_id']]
  require(set(CONTEXT+['target','method','procedure_version','fallback'])<=set(wide),'frozen wide forecast schema incomplete')
  require(wide.target.eq(c['target']).all() and wide.method.eq(FAMILY[c['family']]).all(),'frozen target/method identity conflict')
  require(not wide.duplicated(['season','week','game_id','player_id']).any(),'duplicate original forecast opportunities')
  require(wide.procedure_version.eq(contract['procedure_version']).all(),'frozen procedure version not exact declared output')
  for product,column in contract['products'].items():
   f=wide[CONTEXT+['fallback']].copy();f['target']=c['target'];f['method']=contract['method'];f['product']=product;f['prediction']=wide[column]
   f['output_procedure_version']=wide['normalized_law_procedure_version'] if product=='probability_normalized' else wide.procedure_version
   f['source_forecast_sha256']=c['forecast_sha256'];frames.append(f)
  if c['family']=='count_A':
   f=wide[CONTEXT+['fallback']].copy();f['target']=c['target'];f['method']='COUNT_A_LEGACY_POINT';f['product']='legacy_empirical_point';f['prediction']=wide.legacy_point;f['output_procedure_version']=contract['parent_procedure_version'];f['source_forecast_sha256']=c['forecast_sha256'];frames.append(f)
 require(frames,'no successful frozen forecasts; no zero-error empty study')
 return pd.concat(frames,ignore_index=True)


def add_equal_ATD(frame,catalog,enabled):
 """Declared equal event-probability blend, exact common information context."""
 import pandas as pd,numpy as np
 if not enabled:return frame
 t='anytime_td'
 require(t in catalog and 'LEAF_CDF' in catalog[t] and 'CATBOOST_MEDIUM' in catalog[t],'declared probability blend requires both registered parents')
 a=frame.loc[frame.target.eq(t)&frame.method.eq('LEAF_CDF')&frame['product'].eq('probability_normalized')]
 b=frame.loc[frame.target.eq(t)&frame.method.eq('CATBOOST_MEDIUM')&frame['product'].eq('probability')]
 j=a.merge(b,on=CONTEXT+['target'],suffixes=('_cdf','_cat'),validate='one_to_one')
 f=j[CONTEXT+['target']].copy();f['prediction']=.5*j.prediction_cdf+.5*j.prediction_cat
 f['fallback']=j.fallback_cdf.fillna('').astype(str)+'|'+j.fallback_cat.fillna('').astype(str)
 f.loc[j.fallback_cdf.fillna('').eq('')&j.fallback_cat.fillna('').eq(''),'fallback']=''
 f['method']='EQUAL_CDF_CAT_PROBABILITY';f['product']='probability';version=sha(encoded({'recipe':'equal-probability-blend-v1','weight_CDF':.5,'parents':[catalog[t]['LEAF_CDF']['procedure_version'],catalog[t]['CATBOOST_MEDIUM']['procedure_version']],'CDF_output':'normalized-cumulative-mixture-v1-20261025','model_sha256s':[catalog[t]['LEAF_CDF']['model_sha256'],catalog[t]['CATBOOST_MEDIUM']['model_sha256']]}))
 f['output_procedure_version']=version;f['source_forecast_sha256']=None
 catalog[t]['EQUAL_CDF_CAT_PROBABILITY']={'procedure_id':'EQUAL_CDF_CAT_PROBABILITY','procedure_version':version,'products':['probability'],'shortlist_group':'EQUAL_CDF_CAT_PROBABILITY'}
 return pd.concat([frame,f],ignore_index=True)


def attach_labels(frame,labels):
 require(not labels.duplicated(ID).any(),'canonical target outcomes conflict')
 merged=frame.merge(labels[ID+['actual','participation_state','outcome_state','label_reason']],on=ID,how='left',validate='many_to_one',indicator=True)
 require(merged['_merge'].eq('both').all(),'frozen forecasts missing declared canonical outcome states')
 return merged.drop(columns='_merge')


def make_scope(catalog,config):
 core={};references={}
 for target,methods in catalog.items():
  require('LEAF_CDF' in methods,'strong retainedCDF core missing; separately register another control')
  core[target]=[['LEAF_CDF','probability_normalized']] if target=='anytime_td' else [['LEAF_CDF','mean'],['LEAF_CDF','median']]
  references[target]=['LEAF_CDF','probability_normalized' if target=='anytime_td' else 'median']
 return dict(panel_id=config['run_id'],seasons=[2026],weeks=list(range(1,8)),targets=list(catalog),identity_namespace='GSIS_CANONICAL_PRIMARY_ROSTER',
  source_policy_id=config['feature_source_sha256'],outcome_version=config['outcome_version'],evidence_tier='CURRENT_VINTAGE_TIMING_UNVERIFIED_HISTORICAL_RECONSTRUCTION',
  horizon_id=config['horizon_id'],chart_target_contract='nick-chart-ppr-v1',primary_core_outputs=core,reference_output=references)


def primary_numeric(frame,expected,labels,catalog,scope,primary_roles,uncertainty,scorer):
 import pandas as pd
 headline=expected.loc[[p in primary_roles[t] for t,p in zip(expected.target,expected.position)]].copy()
 main=frame.merge(headline[scorer.KEY],on=scorer.KEY,validate='many_to_one')
 report,points=scorer.score_panel(main,scope,catalog,uncertainty,expected_roster=headline,outcomes=labels)
 report['population']='PREDECLARED_RELEVANT_PRIMARY_ROLES_ONLY_NO_OUTCOME_FILTER'
 # Library limitations refer to its first cached use; retain that source receipt,
 # replace the context paragraph here with this actual separately named scope.
 report['limitations']=['Exposed current-vintage historical reconstruction, not genuine originalpregame or websitehistory.','First finite retained-control wave is not all five finalists or all historicalseasons.','Missing forecasts/outcomes/fallbacks retained; candidatecore partialcoverage is not a headlinewin.']
 return report,points


def numeric_all_roles(frame,expected,labels,catalog,scope,uncertainty,scorer):
 report,points=scorer.score_panel(frame,scope,catalog,uncertainty,expected_roster=expected,outcomes=labels)
 report['population']='FULL_REGISTERED_ATTEMPT_POPULATION_SECONDARY_NOT_HEADLINE_MAE'
 report['limitations']=['Full attempted rolepopulation includes source-qualified reserves and nonprimary positions; no structural-zero dilution used for headline ranking.','Do notcompare this error directly with a different primary-rolepopulation.']
 return report,points


def primary_side_replay(points,offers,cfg,scope,scorer,aux):
 import pandas as pd,numpy as np
 points=points.loc[~points.target.eq('anytime_td')].copy();offers=aux.validate_offers(offers.copy(),scope)
 offers['cutoff_utc']=scorer._clock(offers.cutoff_utc)
 expected=points[aux.OFFER_KEY].drop_duplicates();census=offers.merge(expected,on=aux.OFFER_KEY,how='left',validate='one_to_one',indicator=True)
 outside=census.loc[census['_merge'].eq('left_only')]
 joined=scorer.point_sides(points,offers,{'identity_namespace':scope['identity_namespace'],'forecast_identity_namespace':scope['identity_namespace']})
 joined['decision_policy']='P1_UNROUNDED_POINT_DIRECTION_V1';joined['decision_evidence']='RECONSTRUCTED_NEW_METHOD_DECISION_AT_RETAINED_ORIGINAL_THRESHOLD'
 offered=joined.loc[joined.line.notna()].copy();records=[];pairs=[]
 for (t,method,product),v in offered.groupby(['target','method','product'],sort=True):
  policies={'FULL_PRIMARY_ROSTER_INTERSECTION_RECORDED_BOARD':v}
  for cap in [6,10,20]:
   rank=v.loc[v.selected_side.isin(['over','under'])].copy();rank['rank_gap']=(rank.prediction.astype(float)-rank.line.astype(float)).abs()
   rank=rank.sort_values(['week','rank_gap','game_id','player_id'],ascending=[True,False,True,True],kind='stable');policies['TOP_'+str(cap)+'_POINT_GAP_PER_CATEGORY_WEEK']=rank.groupby('week',group_keys=False).head(cap)
  iqr=cfg.get('earlier_training_IQR',{}).get(t)
  if iqr is not None:
   require(math.isfinite(iqr) and iqr>0,'earlier frozen training IQR must be positivefinite')
   policies['ABSTAIN_UNLESS_GAP_AT_LEAST_0_1_EARLIER_TRAIN_IQR']=v.loc[v.selected_side.isin(['over','under'])&(v.prediction.astype(float)-v.line.astype(float)).abs().ge(.1*iqr)]
  for policy,g in policies.items():records.append({'target':t,'method':method,'product':product,'policy':policy,'metrics':aux._summary(g,scorer,cfg['uncertainty'],target=t),'weekly':[{'week':w,'metrics':aux._summary(g.loc[g.week.eq(w)],scorer,cfg['uncertainty'],target=t)} for w in range(1,8)]})
  ref=scope['reference_output'][t];control=offered.loc[offered.target.eq(t)&offered.method.eq(ref[0])&offered['product'].eq(ref[1])]
  pairs.append({'target':t,'method':method,'product':product,'reference':ref,'choices':aux._pair_choices(v,control,scorer,cfg['uncertainty'])})
 controls=[];base=offered.drop_duplicates(aux.OFFER_KEY)
 for side in ['over','under']:
  c=base.copy();c['prediction']=c.line.astype(float)+(1 if side=='over' else -1)
  c=scorer.point_sides(c.drop(columns=[x for x in offers if x not in aux.OFFER_KEY and x in c]),offers,{'identity_namespace':scope['identity_namespace'],'forecast_identity_namespace':scope['identity_namespace']})
  for t,g in c.groupby('target'):
   met=aux._summary(g,scorer,cfg['uncertainty'],target=t);met['MAE_on_supported_offered_point_rows']=None;met['precision']=None
   controls.append({'target':t,'control':'ALWAYS_'+side.upper(),'metrics':met})
 report={'state':'COMPLETED_PRIMARY_POINT_DIRECTION_RECONSTRUCTION' if len(offers) else 'NO_RECORDED_LINES_AVAILABLE','records':records,'paired_choices':pairs,'always_side_controls':controls,'primary_original_offer_rows':len(offers),'scored_output_offer_incidences':len(offered),'full_expected_output_rows':len(joined),'missing_offer_output_incidences':int(joined.line.isna().sum()),'recorded_offers_outside_attempted_query_population':{'rows':len(outside),'by_target_week':[dict(zip(['target','week'],k),rows=int(n)) for k,n in outside.groupby(['target','week']).size().items()]},
 'probability_track':'NOT_INFERRED_FROM_POINTS; exact savedlaw probabilityreplay remains separately required','price_EV_track':'UNQUALIFIED_PRICE_SETTLEMENT_CONTRACT_NOT_SCORED','abstention':'EarlierfrozenIQRonly; missingIQR means that policyUNAVAILABLE, no laterchosen substitute','limitations':['This uses full recoverable recorded offering pool intersected with full predeclared rosterattempts, not old selected leans or TopPicks.','Timing-unverified recorded lines do not prove authenticpregame decisions or venue settledwins.','ConditionalOver/Under hit rates concern different own-selected subsets; jointdecisions/disagreements also reported.']}
 return report,joined


def execute(cfg,go):
 """Actual managed scoring entry. Exact reviewed root GO precedes every read."""
 start=time.monotonic();cpu=time.process_time()
 require(go.get('state')=='ROOT_AND_INDEPENDENT_GO' and go.get('registered_by')=='/root','exactroot/reviewer scoring GO required')
 require(go.get('worker_sha256')==sha(Path(__file__).read_bytes()) and go.get('configuration_sha256')==sha(encoded(cfg)),'source/config GO mismatch')
 cfg=copy.deepcopy(cfg)
 caps=cfg['resources'];resource.setrlimit(resource.RLIMIT_CPU,(caps['CPU_seconds'],caps['CPU_seconds']+1));signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('primary scoring wall budget')));signal.alarm(caps['wall_seconds'])
 def offline(event,args):
  if event in ['socket.connect','socket.connect_ex','socket.getaddrinfo']:raise RuntimeError('offline primaryscoring')
 sys.addaudithook(offline);sys.path.insert(0,str(ROOT))
 import nfl_lab
 from nfl_lab import data,features,cdf_engine
 require(Path(nfl_lab.__file__).resolve().parent==ROOT/'nfl_lab','root package dependency binding required before storage')
 import pyarrow as pa,pyarrow.parquet as pq
 pa.set_cpu_count(1);pa.set_io_thread_count(1)
 from tools.category_topfive_matched12_offer_driver_v1 import read_exact
 for ref in cfg['source_pins'].values():read_exact(ref)
 require(cfg['source_pins']['scorer']['sha256']==SCORER_SHA and cfg['source_pins']['auxiliary_helpers']['sha256']==AUX_SHA,'independently reviewed scorer/helper changed')
 scorer=load(cfg['source_pins']['scorer'],'primary12_scorer');aux=load(cfg['source_pins']['auxiliary_helpers'],'primary12_aux_helpers');offer_api=load(cfg['source_pins']['offer_driver'],'primary12_offer_api');label_api=load(cfg['source_pins']['labels'],'primary12_label_api')
 storage=load(cfg['source_pins']['storage_helper'],'primary12_storage');store,_=storage.open_store(ROOT,allocation_sha256=cfg['allocation_sha256'],root_go=storage.GO)
 slug=cfg['run_id'];require(slug.startswith('matched12-primary-score-') and '/' not in slug and '..' not in slug,'new single scoring namespace required')
 output=store.forward_root/'research'/slug;require(not output.exists(),'consumed attempt cannot rerun/overwrite');store.register_root(output);refs={};written=0
 def own(ref):
  path=Path(ref['path']);owners=[s for s in [store,store.complete_peer,store.complete_peer.prior_forward,store.complete_peer.legacy] if any(path.is_relative_to(Path(r)) for r in s._roots)]
  require(len(owners)==1,'exact registered sourceowner required');r=owners[0].validate_reference(path,ref['sha256']);require(r['bytes']==ref['bytes'],'owned source size mismatch');return read_exact(ref)
 def put(name,raw):
  nonlocal written
  require(written+len(raw)+65536<=caps['private_peak_bytes'],'complete finite scoring byte envelope exhausted')
  store.write_bytes(output/name,raw);r=store.validate_reference(output/name,sha(raw));refs[name]={'bytes':r['bytes'],'sha256':r['sha256']};written+=len(raw)
 def table(name,frame):
  f=frame.copy()
  if 'line' in f:f['line']=f.line.map(lambda x:None if x is None or str(x)=='nan' else str(x))
  out=io.BytesIO();pq.write_table(pa.Table.from_pandas(f,preserve_index=False),out,compression='zstd');put(name,out.getvalue())
 put('CONSUMED.json',encoded({'run_id':slug,'state':'STARTED_BEFORE_EVALUATION_LABEL_READ','source_sha256':go['worker_sha256'],'config_sha256':go['configuration_sha256'],'fits':0,'inference':0}))
 try:
  import pandas as pd,numpy as np
  freeze=json.loads(own(cfg['forecast_freeze']));require(freeze.get('forecast_readback_verified') is True and freeze.get('state')==cfg['required_forecast_freeze_state'],'actual complete forecast freeze/readback required')
  terminal=json.loads(own(cfg['inference_terminal']));require(terminal['features_sha256']==cfg['feature_source_sha256'],'frozen feature source differs')
  require(freeze.get('inference_terminal_sha256')==cfg['inference_terminal']['sha256'] and freeze.get('feature_sha256')==cfg['feature_source_sha256'],'freeze terminal/feature chain differs')
  require(freeze.get('successful_forecasts')=={c['cell_id']:c.get('forecast',{}).get('sha256') for c in cfg['cells']},'freeze forecast membership/content differs')
  require(terminal['state'] in ['FINITE_WAVE_FORECASTS_FROZEN_UNSCORED','FINITE_WAVE_TERMINAL_WITH_FAILURES'],'source inference has not reached a durable terminal')
  queries=pd.read_parquet(io.BytesIO(own(cfg['queries'])));cells=cfg['cells'];catalog,contracts=output_contracts(cells)
  expected=expected_population(queries,catalog,cfg['query_roles_by_target'],cfg['horizon_id']);table('EXPECTED_POPULATION_BEFORE_LABEL_READ.parquet',expected)
  outcomes_by_cell={r['cell_id']:r for r in terminal['results']};require(set(outcomes_by_cell)=={c['cell_id'] for c in cells},'registered terminalcell census differs')
  wides={};failures=[]
  for c in cells:
   r=outcomes_by_cell[c['cell_id']]
   if r['state']=='FAILED_ATTEMPT_PRESERVED':failures.append({'cell_id':c['cell_id'],'state':r['state'],'reason':'Original failed inference remains retained'});continue
   require(r['state']=='FROZEN_HISTORICAL_INFERENCE_COMPLETE_UNSCORED','unsupported frozen cellstate')
   require(c['forecast']['sha256']==r['forecast']['sha256'] and c['forecast']['bytes']==r['forecast']['bytes'],'terminalforecast binding differs')
   c['forecast_sha256']=c['forecast']['sha256'];wides[c['cell_id']]=pd.read_parquet(io.BytesIO(own(c['forecast'])))
  frame=flatten_forecasts(wides,cells,contracts);frame=add_equal_ATD(frame,catalog,cfg.get('declared_equal_ATD_blend',False));scope=make_scope(catalog,cfg)
  # No outcome value has been decoded before the expected population and exact
  # successful forecast flattening are durably frozen here.
  table('FLATTENED_FORECASTS_BEFORE_LABEL_READ.parquet',frame);put('CATALOG_AND_SCOPE.json',encoded({'catalog':catalog,'scope':scope,'primary_roles':cfg['primary_roles_by_target'],'query_roles':cfg['query_roles_by_target']}))
  if cfg.get('qualified_labels'):
   labels=pd.read_parquet(io.BytesIO(own(cfg['qualified_labels'])));label_audit={'state':'AUTHENTICATED_RETAINED_LABEL_QUALIFICATION_REUSED','source_sha256':cfg['qualified_labels']['sha256']}
  else:
   label_cfg=cfg['label_configuration'];require(label_cfg['forecast_freeze']==cfg['forecast_freeze'],'labels mustbindsame verifiedglobalfreeze')
   require(label_cfg['roles_by_target']==cfg['query_roles_by_target'],'labels changed predeclared attempted rolepopulation')
   for ref in label_cfg['inputs'].values():own(ref)
   label_go={'state':'ROOT_AND_INDEPENDENT_GO','registered_by':'/root','worker_sha256':cfg['source_pins']['labels']['sha256'],'config_sha256':sha(label_api.canonical(label_cfg)),'forecast_freeze_sha256':cfg['forecast_freeze']['sha256']}
   labels,label_audit=label_api.materialize(label_cfg,label_go)
  table('QUALIFIED_LABELS.parquet',labels);put('LABEL_QUALIFICATION.json',encoded(label_audit));frame=attach_labels(frame,labels)
  require(len(frame)<=caps['maximum_output_rows'],'finite output-row scoring cap')
  headline,primary_points=primary_numeric(frame,expected,labels,catalog,scope,cfg['primary_roles_by_target'],cfg['uncertainty'],scorer)
  all_roles,all_points=numeric_all_roles(frame,expected,labels,catalog,scope,cfg['uncertainty'],scorer)
  side_report={'state':'NOT_EXECUTED_NO_PREPARED_ACTUAL_OFFER_PANEL'};side_points=None
  if cfg.get('offers'):
   own(cfg['offers']);offers=offer_api.scoring_projection(aux.read_offer_table(cfg['offers']))
   side_report,side_points=primary_side_replay(all_points,offers,cfg,scope,scorer,aux)
  table('POINT_SCORECARD_ALL_ATTEMPTED_ROLES.parquet',all_points);table('POINT_SCORECARD_PRIMARY_ROLES.parquet',primary_points)
  if side_points is not None:table('POINT_DIRECTION_SCORECARD.parquet',side_points)
  readiness=[]
  for t in ALL12+['rec_tgt']:
   methods=catalog.get(t,{})
   readiness.append({'target':t,'procedure_groups':sorted({x['shortlist_group'] for x in methods.values()}),'products':{m:x['products'] for m,x in methods.items()},'state':'FIRST_CONTROL_WAVE_SCORED_NOT_FIVE_FINALISTS' if methods else 'NOT_IN_THIS_FROZEN_CONTROL_WAVE','next':'Remaining declared finalists/qualifiedlabels/lawreplay are separately tracked; no fabricated method orzeroerror'})
  report={'version':VERSION,'state':'COMPLETED_FIRST_FROZEN_PRIMARY_W1_7_CONTROL_COMPARISON','run_id':slug,'source_worker_sha256':go['worker_sha256'],'configuration_sha256':go['configuration_sha256'],'output_procedure_bindings':{t:{m:{'parent_or_point_procedure_version':v['procedure_version'],'product_procedure_versions':v.get('product_procedure_versions',{})} for m,v in methods.items()} for t,methods in catalog.items()},'headline_numeric':headline,'full_attempt_population_secondary':all_roles,'recorded_line_point_decisions':side_report,'category_completion':readiness,'failed_inference_cells':failures,'label_qualification':label_audit,'execution_counts':{'fits':0,'model_restorations':0,'new_forecasts':0,'cached_primary_scoring_runs':1,'frozen_output_rows':len(all_points),'original_player_query_rows':len(queries),'independent_scheduled_games':int(queries.game_id.nunique()),'weeks':7},'production':{'website_reference':'UNAVAILABLE_AUTHENTIC_MATCHED_HISTORICAL_SITE_FORECASTS_NOT_RECREATED','changes':0,'release_policy':'Existing retained-owner product-specific decision remains separate','probability_EV_ranking':'No activation frompointMAE'},'limitations':['Firstwave fewerthan5procedurespercategory; notcompletionofall12five-methodrequest.','Numericpoint/distribution/probability/selectionobjectivesremainseparate.','Timing-unverified historical lines are descriptive reconstructions, not originalwebsiteleantable orauthenticatedpregame selections.','Originalfailedattempts andmissinglabels retained; no newscientificqualification claimed.']}
  public=gzip.compress(encoded(report),mtime=0);require(len(public)<=caps['public_aggregate_bytes'],'complete compressed aggregate cap');put('AGGREGATES.json.gz',public)
  store.verify_retained_checkpoint();receipt={'version':VERSION,'state':'COMPLETED_LOCAL_READBACK_PENDING_FRESH_PROCESS','run_id':slug,'artifacts':refs.copy(),'new_fits':0,'new_model_inference':0,'cached_scoring_runs':1,'actual':{'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-start,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024},'offhost_restore':'NOT_VERIFIED','deployment':False}
  require(receipt['actual']['RSS_bytes']<=caps['RSS_bytes'],'scoring RSS exceeded');put('RESULT_RECEIPT.json',encoded(receipt));store.verify_retained_checkpoint();signal.alarm(0);return receipt
 except BaseException as exc:
  failure={'version':VERSION,'state':'FAILED_ATTEMPT_EVIDENCE_PRESERVED','run_id':slug,'exception_type':type(exc).__name__,'private_message':str(exc),'retained_artifacts':refs,'fits':0,'inference':0}
  try:put('FAILURE.json',encoded(failure))
  except BaseException:pass
  raise


def fictional_checks():
 import pandas as pd,numpy as np
 from tools import category_topfive_matched12_score_v1_2 as scorer,category_topfive_matched12_aux_runner_v1 as aux
 checks=[]
 def ok(name,condition):
  require(condition,'fixture:'+name);checks.append(name)
 def rejects(name,fn):
  try:fn()
  except ValueError:checks.append(name)
  else:raise AssertionError(name)
 cells=[{'cell_id':family,'target':'rec','family':family,'procedure_version':'FICT_'+family,'model':{'sha256':'a'*64},'forecast_sha256':'b'*64} for family in FAMILY]
 catalog,contracts=output_contracts(cells);qs=[]
 for w,y in [(1,4.),(7,5.)]:
  for pos,player in [('WR','FICT-WR'),('QB','FICT-QB')]:qs.append(dict(season=2026,week=w,game_id='FICT-'+str(w),player_id=player,team='AAA',opponent='BBB',position=pos,kickoff_utc='2026-10-01T17:00:00Z',cutoff_utc='2026-10-01T17:00:00Z'))
 q=pd.DataFrame(qs);e=expected_population(q,catalog,{'rec':['QB','RB','FB','WR','TE']},'FICT_HORIZON')
 ok('expectedgridnooutcomes',len(e)==4 and 'actual' not in e)
 wides={}
 for c in cells:
  f=q.copy();f['target']='rec';f['method']=FAMILY[c['family']];f['procedure_version']=contracts[c['cell_id']]['procedure_version'];f['fallback']=''
  wr=f.position.eq('WR');f['mean']=np.where(wr,np.where(f.week.eq(1),3.,5.),0.);f['median']=np.where(wr,np.where(f.week.eq(1),2.,6.),0.)
  f['point']=np.where(wr,4.5 if c['family']=='catboost_medium' else 4.,0.);f['legacy_point']=np.where(wr,np.where(f.week.eq(1),5.,4.),0.);wides[c['cell_id']]=f
 f=flatten_forecasts(wides,cells,contracts)
 ok('CDFmeanmedianonegroup',catalog['rec']['LEAF_CDF']['products']==['mean','median'])
 ok('Countlegacyseparatelytyped',len(catalog['rec'])==4 and catalog['rec']['COUNT_A_MEAN']['shortlist_group']==catalog['rec']['COUNT_A_LEGACY_POINT']['shortlist_group'])
 ok('Countcorrectedidentityseparate',catalog['rec']['COUNT_A_MEAN']['procedure_version']!=catalog['rec']['COUNT_A_LEGACY_POINT']['procedure_version'])
 labels=e[ID].copy();labels['actual']=np.where(e.position.eq('WR'),np.where(e.week.eq(1),4.,5.),0.);labels['participation_state']='played';labels['outcome_state']='played_nonzero';labels['label_reason']='FICT_EXPLICIT'
 frame=attach_labels(f,labels);cfg={'run_id':'FICT','feature_source_sha256':'c'*64,'outcome_version':'FICT','horizon_id':'FICT_HORIZON','uncertainty':{'seed':17,'replicates':10,'minimum_clusters':2}}
 scope=make_scope(catalog,cfg);main,mp=primary_numeric(frame,e,labels,catalog,scope,{'rec':['WR']},cfg['uncertainty'],scorer)
 full,fp=numeric_all_roles(frame,e,labels,catalog,scope,cfg['uncertainty'],scorer)
 def met(report,method,product):return next(x['metrics'] for x in report['records'] if x['method']==method and x['product']==product and x['scope']=='FULL_REGISTERED_METHOD_POPULATION')
 ok('primaryrolenostructuralzerodilution',met(main,'LEAF_CDF','median')['MAE']==1.5 and met(full,'LEAF_CDF','median')['MAE']==.75)
 ok('validmeancompetesonMAE',met(main,'LEAF_CDF','mean')['MAE']==.5)
 ok('allrolefullsystemretained',len(fp)==20 and len(mp)==10)
 miss=frame.loc[~(frame.method.eq('CATBOOST_MEDIUM')&frame.week.eq(7)&frame.position.eq('WR'))]
 r,_=primary_numeric(miss,e,labels,catalog,scope,{'rec':['WR']},cfg['uncertainty'],scorer)
 partial=next(x for x in r['records'] if x['method']=='CATBOOST_MEDIUM' and x['scope']=='PREDECLARED_PRIMARY_COMMON_CORE')
 ok('missingcandidatedoesnotshrinkcore',partial['joint_finite_played_rows']==2 and not partial['headline_eligible'])
 offers=e[aux.OFFER_KEY].copy();offers['line']=np.where(e.position.eq('WR'),4.5,.5);offers['evidence_tier']='FICT';offers['primary_offer_policy']='FICT';offers['statistical_contract']='FICT'
 side,sp=primary_side_replay(fp,offers,cfg,scope,scorer,aux)
 ok('samefullboardalloutputs',len(sp)==20 and side['primary_original_offer_rows']==4)
 cat=sp.loc[sp.method.eq('CATBOOST_MEDIUM')&sp.position.eq('WR')]
 ok('fractionalpointlineequalityabstains',cat.selected_side.eq('abstain').all())
 ok('halflineactualcountnopush',not sp.statistical_result.eq('PUSH').any())
 ok('controlsdontduplicatefootballoutcomes',len(side['always_side_controls'])==2 and side['always_side_controls'][0]['metrics']['opportunities']==4)
 ok('TopNseparatewithoutsidequota',len(side['records'])==20)
 rejects('wrongforecastprocedureblocked',lambda:flatten_forecasts({**wides,'leaf_cdf_base':wides['leaf_cdf_base'].assign(procedure_version='WRONG')},cells,contracts))
 rejects('missingGOopensnosources',lambda:execute({},{}))
 return {'state':'PASS_FICTIONAL_ONLY','checks':checks,'fictional_cases':len(checks),'NFL_rows_labels_forecasts_models_decoded':0,'fits_inference_storeopens_HTTP':0}
